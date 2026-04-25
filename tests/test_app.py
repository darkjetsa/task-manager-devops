import pytest
import json
from app import create_app, db


@pytest.fixture
def app():
    app = create_app({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
    })
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


# ── Health & Index ────────────────────────────────────────────────────────────

class TestHealth:
    def test_health_returns_200(self, client):
        r = client.get('/health')
        assert r.status_code == 200

    def test_health_status_field(self, client):
        data = json.loads(client.get('/health').data)
        assert data['status'] == 'healthy'

    def test_health_has_timestamp(self, client):
        data = json.loads(client.get('/health').data)
        assert 'timestamp' in data

    def test_index_returns_200(self, client):
        r = client.get('/')
        assert r.status_code == 200

    def test_index_has_app_name(self, client):
        data = json.loads(client.get('/').data)
        assert data['app'] == 'Task Manager API'


# ── Metrics ───────────────────────────────────────────────────────────────────

class TestMetrics:
    def test_metrics_returns_200(self, client):
        r = client.get('/metrics')
        assert r.status_code == 200

    def test_metrics_content_type(self, client):
        r = client.get('/metrics')
        assert 'text/plain' in r.content_type

    def test_metrics_contains_tasks_total(self, client):
        r = client.get('/metrics')
        assert b'tasks_total' in r.data


# ── Tasks CRUD ────────────────────────────────────────────────────────────────

class TestTasksCRUD:
    def _create_task(self, client, title='Test Task', priority='medium'):
        return client.post('/api/tasks',
                           data=json.dumps({'title': title, 'priority': priority}),
                           content_type='application/json')

    def test_get_empty_tasks(self, client):
        r = client.get('/api/tasks')
        assert r.status_code == 200
        assert json.loads(r.data) == []

    def test_create_task_success(self, client):
        r = self._create_task(client)
        assert r.status_code == 201
        data = json.loads(r.data)
        assert data['title'] == 'Test Task'
        assert data['priority'] == 'medium'
        assert data['completed'] is False

    def test_create_task_missing_title(self, client):
        r = client.post('/api/tasks',
                        data=json.dumps({'description': 'no title'}),
                        content_type='application/json')
        assert r.status_code == 400

    def test_create_task_invalid_priority(self, client):
        r = client.post('/api/tasks',
                        data=json.dumps({'title': 'T', 'priority': 'urgent'}),
                        content_type='application/json')
        assert r.status_code == 400

    def test_get_task_by_id(self, client):
        self._create_task(client, title='Specific Task')
        r = client.get('/api/tasks/1')
        assert r.status_code == 200
        assert json.loads(r.data)['title'] == 'Specific Task'

    def test_get_task_not_found(self, client):
        r = client.get('/api/tasks/999')
        assert r.status_code == 404

    def test_update_task(self, client):
        self._create_task(client)
        r = client.put('/api/tasks/1',
                       data=json.dumps({'title': 'Updated', 'completed': True}),
                       content_type='application/json')
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data['title'] == 'Updated'
        assert data['completed'] is True

    def test_delete_task(self, client):
        self._create_task(client)
        r = client.delete('/api/tasks/1')
        assert r.status_code == 200
        assert client.get('/api/tasks/1').status_code == 404

    def test_complete_task(self, client):
        self._create_task(client)
        r = client.patch('/api/tasks/1/complete')
        assert r.status_code == 200
        assert json.loads(r.data)['completed'] is True

    def test_filter_tasks_by_priority(self, client):
        self._create_task(client, title='High Task', priority='high')
        self._create_task(client, title='Low Task', priority='low')
        r = client.get('/api/tasks?priority=high')
        data = json.loads(r.data)
        assert len(data) == 1
        assert data[0]['priority'] == 'high'

    def test_filter_tasks_by_completed(self, client):
        self._create_task(client)
        client.patch('/api/tasks/1/complete')
        self._create_task(client, title='Pending')
        r = client.get('/api/tasks?completed=true')
        data = json.loads(r.data)
        assert all(t['completed'] for t in data)


# ── Users CRUD ────────────────────────────────────────────────────────────────

class TestUsersCRUD:
    def _create_user(self, client, username='alice', email='alice@example.com'):
        return client.post('/api/users',
                           data=json.dumps({'username': username, 'email': email}),
                           content_type='application/json')

    def test_create_user_success(self, client):
        r = self._create_user(client)
        assert r.status_code == 201
        data = json.loads(r.data)
        assert data['username'] == 'alice'

    def test_create_user_duplicate(self, client):
        self._create_user(client)
        r = self._create_user(client)
        assert r.status_code == 409

    def test_create_user_missing_fields(self, client):
        r = client.post('/api/users',
                        data=json.dumps({'username': 'bob'}),
                        content_type='application/json')
        assert r.status_code == 400

    def test_get_users(self, client):
        self._create_user(client)
        r = client.get('/api/users')
        assert r.status_code == 200
        assert len(json.loads(r.data)) == 1

    def test_get_user_by_id(self, client):
        self._create_user(client)
        r = client.get('/api/users/1')
        assert r.status_code == 200

    def test_delete_user(self, client):
        self._create_user(client)
        r = client.delete('/api/users/1')
        assert r.status_code == 200
        assert client.get('/api/users/1').status_code == 404


# ── Model Unit Tests ──────────────────────────────────────────────────────────

class TestModels:
    def test_task_to_dict(self, app):
        from app.models import Task
        with app.app_context():
            t = Task(title='Model Test', priority='high')
            db.session.add(t)
            db.session.commit()
            d = t.to_dict()
            assert d['title'] == 'Model Test'
            assert d['priority'] == 'high'
            assert 'created_at' in d

    def test_user_to_dict(self, app):
        from app.models import User
        with app.app_context():
            u = User(username='testuser', email='test@test.com')
            db.session.add(u)
            db.session.commit()
            d = u.to_dict()
            assert d['username'] == 'testuser'
            assert 'created_at' in d
