from flask_socketio import join_room, leave_room, emit
from app.extensions import socketio


def register_events(socketio_instance):
    @socketio_instance.on('connect')
    def handle_connect():
        pass

    @socketio_instance.on('disconnect')
    def handle_disconnect():
        pass

    @socketio_instance.on('join-task')
    def handle_join_task(data):
        task_id = data.get('taskId')
        if task_id:
            room = f'task:{task_id}'
            join_room(room)
            emit('task-joined', {'taskId': task_id, 'status': 'success'}, room=room)

    @socketio_instance.on('leave-task')
    def handle_leave_task(data):
        task_id = data.get('taskId')
        if task_id:
            room = f'task:{task_id}'
            leave_room(room)
            emit('task-left', {'taskId': task_id, 'status': 'success'}, room=room)

    @socketio_instance.on('join')
    def handle_join(data):
        room = data.get('room')
        if room:
            join_room(room)

    @socketio_instance.on('leave')
    def handle_leave(data):
        room = data.get('room')
        if room:
            leave_room(room)


def emit_progress(task_id, status, progress, message, current_page=None, total_pages=None):
    room = f'task:{task_id}'
    progress_data = {
        'taskId': task_id,
        'status': status,
        'progress': progress,
        'message': message
    }
    if current_page is not None:
        progress_data['currentPage'] = current_page
    if total_pages is not None:
        progress_data['totalPages'] = total_pages
    socketio.emit('progress', progress_data, room=room)


def emit_completed(task_id, result):
    room = f'task:{task_id}'
    socketio.emit('completed', {'taskId': task_id, 'result': result}, room=room)


def emit_failed(task_id, error_message):
    room = f'task:{task_id}'
    socketio.emit('failed', {'taskId': task_id, 'error': error_message}, room=room)
