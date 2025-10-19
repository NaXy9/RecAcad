# RekAcad

## Overview

The RekAcad server implements the server-side services that enable automated recording, processing and management of online lecture sessions. The server exposes a clear REST API for external clients, schedules and executes asynchronous processing jobs, controls the recording bot, and persists recordings and derived artifacts (transcripts, summaries, notes, timestamps).

## Purpose

This repository contains all server logic required to:

- Accept user requests to start and stop recording sessions.
- Launch and supervise a headless recording bot that joins online conferences.
- Store raw recordings and derived data in a persistent storage.
- Orchestrate an asynchronous processing pipeline that extracts audio, performs speech‑to‑text, and produces condensed summaries and structured lecture notes.
- Provide authenticated and access‑controlled API endpoints for clients and administrative tooling.

## Key responsibilities

- **Session control:** API endpoints to create and manage recording sessions, including group and access checks.
- **Bot orchestration:** Tasks that start, monitor and stop a headless browser instance which joins an online conference and triggers platform recording features.
- **Persistent storage:** Management of recording files and metadata in the database and configured media storage.
- **Processing pipeline orchestration:** Task orchestration for media processing stages (audio extraction, transcription, summarization, timestamp generation) using asynchronous workers.
- **Result management:** Storing transcripts, summaries, notes and task status; exposing them through the API for clients to consume.

## How it works (high level flow)

1. A client (frontend or API consumer) requests a new recording session by providing a conference link and session metadata.
2. The server validates the request, creates a session record and enqueues a worker task to start the recording bot.
3. A worker process launches the headless bot, which opens the conference link, sets the participant identity, and triggers the built‑in recording mechanism of the conference platform (or records via automated capture, depending on platform capabilities).
4. The recording bot runs until the session is stopped. After completion the raw video file is saved to configured media storage and its metadata is updated in the database.
5. The server enqueues a processing job which performs the following stages:
   - Extract audio from the recorded video file.
   - Run speech‑to‑text to produce a transcript.
   - Generate a condensed summary with timestamps and a structured lecture notes document using an LLM or other summarization service.
   - Persist all derived artifacts and update processing status.
6. Clients retrieve processing results via the API and present them to end users.

## Integration and configuration notes

- The server is designed to be configurable with different AI server and media processing tools; model endpoints and processing parameters are provided via environment configuration.
- The API is intended to be the authoritative interface for the frontend and third‑party integrations; ensure the frontend points to the correct API base URL and uses the provided authentication mechanism.
- Long running tasks and resource‑intensive processing should run in isolated worker processes and be subject to job queue limits and rate control.

