from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from apps.groups.models import Group

User = get_user_model()

class GroupTests(APITestCase):
    def setUp(self):
        # создаём трех пользователей
        self.owner = User.objects.create_user(username='owner', email='owner@example.com', password='pass')
        self.user2 = User.objects.create_user(username='member', email='member@example.com', password='pass')
        self.user3 = User.objects.create_user(username='other',  email='other@example.com',  password='pass')
        # URL-ы
        self.create_url = reverse('group-create')
        self.list_url   = reverse('group-list')
        # detail/add/remove/delete строятся динамически

    def auth(self, user):
        """Вспомогательный метод логина через JWT."""
        token_url = reverse('token_obtain_pair')
        resp = self.client.post(token_url, {'username': user.username, 'password': 'pass'})
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + resp.data['access'])

    def test_create_group(self):
        # логинимся как owner
        self.auth(self.owner)
        resp = self.client.post(self.create_url, {'title': 'TestGroup'})
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        gid = resp.data['id']
        grp = Group.objects.get(id=gid)
        self.assertEqual(grp.owner, self.owner)
        # владелец должен автоматически состоять в members
        self.assertIn(self.owner, grp.members.all())

    def test_list_groups(self):
        # создаём две группы: одну для owner, одну для user2
        g1 = Group.objects.create(owner=self.owner, title='G1')
        g1.members.add(self.owner)
        g2 = Group.objects.create(owner=self.user2, title='G2')
        g2.members.add(self.user2)
        # owner видит только свою
        self.auth(self.owner)
        resp1 = self.client.get(self.list_url)
        self.assertEqual(resp1.status_code, status.HTTP_200_OK)
        titles1 = {g['title'] for g in resp1.data}
        self.assertSetEqual(titles1, {'G1'})
        # member (user2) видит G2
        self.auth(self.user2)
        resp2 = self.client.get(self.list_url)
        titles2 = {g['title'] for g in resp2.data}
        self.assertSetEqual(titles2, {'G2'})

    def test_group_detail(self):
        g = Group.objects.create(owner=self.owner, title='DetailGroup')
        g.members.add(self.owner, self.user2)
        url = reverse('group-detail', args=[g.id])
        # владелец
        self.auth(self.owner)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['title'], 'DetailGroup')
        # другой член
        self.auth(self.user2)
        resp2 = self.client.get(url)
        # ListAPIView не фильтрует detail, но permission — IsAuthenticated → OK
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)

    def test_add_member(self):
        g = Group.objects.create(owner=self.owner, title='AddTest')
        g.members.add(self.owner)
        url = reverse('group-add-member', args=[g.id])
        # успешное добавление
        self.auth(self.owner)
        resp = self.client.post(url, {'username': self.user2.username})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn(self.user2, g.members.all())
        # попытка добавить несуществующего
        resp_not = self.client.post(url, {'username': 'no_such'})
        self.assertEqual(resp_not.status_code, status.HTTP_404_NOT_FOUND)
        # не-владелец → 404
        self.auth(self.user2)
        resp_forb = self.client.post(url, {'username': self.user3.username})
        self.assertEqual(resp_forb.status_code, status.HTTP_404_NOT_FOUND)

    def test_remove_member(self):
        g = Group.objects.create(owner=self.owner, title='RemTest')
        g.members.set([self.owner, self.user2])
        url = reverse('group-remove-member', args=[g.id])
        # владелец удаляет участника
        self.auth(self.owner)
        resp = self.client.post(url, {'username': self.user2.username})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertNotIn(self.user2, g.members.all())
        # попытка удалить не-члена
        resp_bad = self.client.post(url, {'username': self.user3.username})
        self.assertEqual(resp_bad.status_code, status.HTTP_400_BAD_REQUEST)
        # попытка удалить владельца
        resp_owner = self.client.post(url, {'username': self.owner.username})
        self.assertEqual(resp_owner.status_code, status.HTTP_400_BAD_REQUEST)
        # член удаляет себя
        g.members.add(self.user2)
        self.auth(self.user2)
        resp_self = self.client.post(url, {'username': self.user2.username})
        self.assertEqual(resp_self.status_code, status.HTTP_200_OK)
        # кто-то третий пытается удалить
        g.members.add(self.user2)
        self.auth(self.user3)
        resp_third = self.client.post(url, {'username': self.user2.username})
        self.assertEqual(resp_third.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_group(self):
        g = Group.objects.create(owner=self.owner, title='DelTest')
        g.members.add(self.owner)
        url = reverse('group-delete', args=[g.id])
        # чужой → 404
        self.auth(self.user2)
        resp_forb = self.client.delete(url)
        self.assertEqual(resp_forb.status_code, status.HTTP_404_NOT_FOUND)
        # владелец удаляет
        self.auth(self.owner)
        resp_ok = self.client.delete(url)
        self.assertEqual(resp_ok.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Group.objects.filter(id=g.id).exists())
