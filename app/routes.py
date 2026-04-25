from flask import Blueprint, jsonify, request
from app import db
from app.models import Task, User
from datetime import datetime

main = Blueprint('main', __name__)

# ── Health & Metrics ──────────────────────────────────────────────────────────

@main.route('/health', methods=['GET'])
def health():
    """Liveness probe used by monitoring."""
    return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()}), 200


@main.route('/metrics', methods=['GET'])
def metrics():
    """Basic Prometheus-style text metrics endpoint."""
    task_count = Task.query.count()
    completed_count = Task.query.filter_by(completed=True).count()
    user_count = User.query.count()
    metrics_text = (
        f"# HELP tasks_total Total number of tasks\n"
        f"# TYPE tasks_total gauge\n"
        f"tasks_total {task_count}\n"
        f"# HELP tasks_completed_total Completed tasks\n"
        f"# TYPE tasks_completed_total gauge\n"
        f"tasks_completed_total {completed_count}\n"
        f"# HELP users_total Total registered users\n"
        f"# TYPE users_total gauge\n"
        f"users_total {user_count}\n"
    )
    return metrics_text, 200, {'Content-Type': 'text/plain; charset=utf-8'}


@main.route('/', methods=['GET'])
def index():
    return jsonify({
        'app': 'Task Manager API',
        'version': '1.0.0',
        'endpoints': ['/health', '/metrics', '/api/tasks', '/api/users']
    })


# ── Users ─────────────────────────────────────────────────────────────────────

@main.route('/api/users', methods=['GET'])
def get_users():
    users = User.query.all()
    return jsonify([u.to_dict() for u in users]), 200


@main.route('/api/users', methods=['POST'])
def create_user():
    data = request.get_json()
    if not data or not data.get('username') or not data.get('email'):
        return jsonify({'error': 'username and email are required'}), 400
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'error': 'Username already exists'}), 409
    user = User(username=data['username'], email=data['email'])
    db.session.add(user)
    db.session.commit()
    return jsonify(user.to_dict()), 201


@main.route('/api/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    user = User.query.get_or_404(user_id)
    return jsonify(user.to_dict()), 200


@main.route('/api/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    return jsonify({'message': 'User deleted'}), 200


# ── Tasks ─────────────────────────────────────────────────────────────────────

@main.route('/api/tasks', methods=['GET'])
def get_tasks():
    priority = request.args.get('priority')
    completed = request.args.get('completed')
    query = Task.query
    if priority:
        query = query.filter_by(priority=priority)
    if completed is not None:
        query = query.filter_by(completed=completed.lower() == 'true')
    tasks = query.all()
    return jsonify([t.to_dict() for t in tasks]), 200


@main.route('/api/tasks', methods=['POST'])
def create_task():
    data = request.get_json()
    if not data or not data.get('title'):
        return jsonify({'error': 'title is required'}), 400
    priority = data.get('priority', 'medium')
    if priority not in ('low', 'medium', 'high'):
        return jsonify({'error': 'priority must be low, medium, or high'}), 400
    task = Task(
        title=data['title'],
        description=data.get('description', ''),
        priority=priority,
        user_id=data.get('user_id'),
    )
    db.session.add(task)
    db.session.commit()
    return jsonify(task.to_dict()), 201


@main.route('/api/tasks/<int:task_id>', methods=['GET'])
def get_task(task_id):
    task = Task.query.get_or_404(task_id)
    return jsonify(task.to_dict()), 200


@main.route('/api/tasks/<int:task_id>', methods=['PUT'])
def update_task(task_id):
    task = Task.query.get_or_404(task_id)
    data = request.get_json()
    if 'title' in data:
        task.title = data['title']
    if 'description' in data:
        task.description = data['description']
    if 'completed' in data:
        task.completed = bool(data['completed'])
    if 'priority' in data:
        if data['priority'] not in ('low', 'medium', 'high'):
            return jsonify({'error': 'priority must be low, medium, or high'}), 400
        task.priority = data['priority']
    task.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify(task.to_dict()), 200


@main.route('/api/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    db.session.delete(task)
    db.session.commit()
    return jsonify({'message': 'Task deleted'}), 200


@main.route('/api/tasks/<int:task_id>/complete', methods=['PATCH'])
def complete_task(task_id):
    task = Task.query.get_or_404(task_id)
    task.completed = True
    task.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify(task.to_dict()), 200
