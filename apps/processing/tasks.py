import os
import subprocess
import traceback
import json
import torch
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline

import requests
from decouple import config
from celery import shared_task
from django.utils import timezone

from .models import VideoJob, Transcript, Summary, Notes

# Константы
OPENROUTER_API_KEY = config("OPENROUTER_API_KEY", default='')
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
LLAMA_MODEL_ID = "meta-llama/llama-4-scout:free"

# Проверка наличия ключа
if not OPENROUTER_API_KEY:
    raise EnvironmentError("OPENROUTER_API_KEY is not set in environment.")


def call_llama(prompt, max_tokens=1000):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": LLAMA_MODEL_ID,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens
    }

    response = requests.post(OPENROUTER_API_URL, headers=headers, data=json.dumps(payload))
    if response.status_code == 200:
        data = response.json()
        return data["choices"][0]["message"]["content"]
    else:
        raise Exception(f"LLaMA request failed with status {response.status_code}: {response.text}")


def format_timestamp(seconds: float) -> str:
    mins, secs = divmod(int(seconds), 60)
    return f"{mins:02}:{secs:02}"

# DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
# TORCH_DTYPE = torch.float16 if torch.cuda.is_available() else torch.float32

# MODEL_ID = "openai/whisper-large-v3-turbo"

# try:
#     whisper_model = AutoModelForSpeechSeq2Seq.from_pretrained(
#         MODEL_ID,
#         torch_dtype=TORCH_DTYPE,
#         low_cpu_mem_usage=True,
#         use_safetensors=True,
#         attn_implementation="eager",
#     ).to(DEVICE)
#     whisper_processor = AutoProcessor.from_pretrained(MODEL_ID)
#     whisper_pipe = pipeline(
#         "automatic-speech-recognition",
#         model=whisper_model,
#         tokenizer=whisper_processor.tokenizer,
#         feature_extractor=whisper_processor.feature_extractor,
#         torch_dtype=TORCH_DTYPE,
#         device=DEVICE,
#         chunk_length_s=30,
#         batch_size=1
#     )
# except Exception as e:
#     print("Ошибка при загрузке Whisper-модели:", e)
#     whisper_pipe = None

@shared_task(bind=True)
def process_video_job(self, job_id):
    job = VideoJob.objects.get(id=job_id)
    job.status = 'RUNNING'
    job.started_at = timezone.now()
    job.save()
    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
    TORCH_DTYPE = torch.float16 if torch.cuda.is_available() else torch.float32

    MODEL_ID = "openai/whisper-large-v3-turbo"

    try:
        whisper_model = AutoModelForSpeechSeq2Seq.from_pretrained(
            MODEL_ID,
            torch_dtype=TORCH_DTYPE,
            low_cpu_mem_usage=True,
            use_safetensors=True,
            attn_implementation="eager",
        ).to(DEVICE)
        whisper_processor = AutoProcessor.from_pretrained(MODEL_ID)
        whisper_pipe = pipeline(
            "automatic-speech-recognition",
            model=whisper_model,
            tokenizer=whisper_processor.tokenizer,
            feature_extractor=whisper_processor.feature_extractor,
            torch_dtype=TORCH_DTYPE,
            device=DEVICE,
            chunk_length_s=30,
            batch_size=1
        )
    except Exception as e:
        print("Ошибка при загрузке Whisper-модели:", e)
        whisper_pipe = None
    try:
        recording = job.recording
        input_path = recording.video_file.path

        # Извлечение аудио
        audio_path = input_path.rsplit('.', 1)[0] + '.wav'
        subprocess.run([
            'ffmpeg', '-i', input_path, '-vn',
            '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1', audio_path
        ], check=True)

        # Транскрипция через Whisper
        text = ""
        timestamps = []
        if whisper_pipe is None:
            raise RuntimeError("Whisper-пайплайн не загружен")
        generate_kwargs = {
            "language": "russian",
            "task": "transcribe",
        }
        try:
            result = whisper_pipe(audio_path, return_timestamps="word", generate_kwargs=generate_kwargs)
            text = result.get("text", "")
            raw_chunks = result.get("chunks", [])
        except RuntimeError as e:
            print("Word-level timestamps failed, fallback to sentence-level:", e)
            result = whisper_pipe(audio_path, return_timestamps=True, generate_kwargs=generate_kwargs)
            text = result.get("text", "")
            raw_chunks = result.get("chunks", [])
        for c in raw_chunks or []:
            start = None
            end = None
            if isinstance(c, dict):
                if "start" in c and "end" in c:
                    start = c.get("start")
                    end = c.get("end")
                elif "timestamp" in c:
                    ts = c.get("timestamp")
                    if isinstance(ts, (list, tuple)) and len(ts) >= 1:
                        start = ts[0]
                        if len(ts) >= 2:
                            end = ts[1]
            if start is not None:
                ts_dict = {
                    "start": format_timestamp(start),
                    "end": format_timestamp(end) if end is not None else None,
                    "text": c.get("text", "").strip()
                }
                timestamps.append(ts_dict)

        Transcript.objects.create(job=job, text=text, timestamps=timestamps)

        # Генерация краткого пересказа
        summary_prompt = (
            "Ты — ассистент, который помогает студентам. Прочитай лекцию ниже и сгенерируй краткий пересказ по таймкодам. "
            "Формат: '00:00 - 06:30: краткий пересказ момента'. Если тайминги отсутствуют, раздели текст логически."
            f"\n\n{text}"
        )
        try:
            summary_text = call_llama(summary_prompt, max_tokens=1500)
        except Exception as e:
            raise Exception(f"Ошибка генерации краткого пересказа: {e}")

        Summary.objects.create(job=job, text=summary_text)

        # Генерация конспекта
        notes_prompt = (
            "Прочитай лекцию ниже и создай подробный текстовый конспект с сохранением структуры: формулы, определения, ключевые примеры и выводы. "
            f"\n\n{text}"
        )
        try:
            notes_text = call_llama(notes_prompt, max_tokens=5000)
        except Exception as e:
            raise Exception(f"Ошибка генерации конспекта: {e}")

        Notes.objects.create(job=job, text=notes_text)

        job.status = 'SUCCESS'

    except Exception as e:
        job.status = 'FAILED'
        job.log = f"{str(e)}\n{traceback.format_exc()}"

    finally:
        job.finished_at = timezone.now()
        job.save()
