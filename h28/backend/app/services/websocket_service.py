from typing import Dict, Set, Optional, Any
from flask_socketio import SocketIO
from app.repositories.task_repository import TaskRepository


class WebSocketService:
    def __init__(self, socketio: SocketIO, task_repository: TaskRepository):
        self.socketio = socketio
        self.task_repository = task_repository
        self.connected_clients: Set[str] = set()
        self.task_rooms: Dict[str, Set[str]] = {}

    def add_client(self, client_id: str) -> None:
        self.connected_clients.add(client_id)

    def remove_client(self, client_id: str) -> None:
        self.connected_clients.discard(client_id)
        for task_id, clients in self.task_rooms.items():
            clients.discard(client_id)

    def join_task(self, client_id: str, task_id: str) -> None:
        if task_id not in self.task_rooms:
            self.task_rooms[task_id] = set()
        self.task_rooms[task_id].add(client_id)

    def leave_task(self, client_id: str, task_id: str) -> None:
        if task_id in self.task_rooms:
            self.task_rooms[task_id].discard(client_id)

    def get_connected_clients_count(self) -> int:
        return len(self.connected_clients)

    def get_task_watchers_count(self, task_id: str) -> int:
        return len(self.task_rooms.get(task_id, set()))

    def push_progress(
        self,
        task_id: str,
        status: str,
        progress: int,
        message: str,
        current_page: Optional[int] = None,
        total_pages: Optional[int] = None
    ) -> None:
        data = {
            'taskId': task_id,
            'status': status,
            'progress': progress,
            'message': message,
            'currentPage': current_page,
            'totalPages': total_pages
        }
        
        self.socketio.emit('progress', data, room=task_id)
        self.socketio.emit('progress', data, broadcast=True)

    def push_task_created(self, task: Any) -> None:
        data = {
            'id': task.id,
            'fileName': task.file_name,
            'fileType': task.file_type,
            'status': task.status,
            'progress': task.progress,
            'createdAt': task.created_at.isoformat() if task.created_at else None,
            'pageCount': task.page_count,
            'currentPage': task.current_page
        }
        
        self.socketio.emit('task_created', data, broadcast=True)

    def push_task_updated(self, task: Any) -> None:
        data = {
            'id': task.id,
            'fileName': task.file_name,
            'fileType': task.file_type,
            'status': task.status,
            'progress': task.progress,
            'createdAt': task.created_at.isoformat() if task.created_at else None,
            'completedAt': task.completed_at.isoformat() if task.completed_at else None,
            'pageCount': task.page_count,
            'currentPage': task.current_page,
            'errorMessage': task.error_message
        }
        
        self.socketio.emit('task_updated', data, room=task.id)
        self.socketio.emit('task_updated', data, broadcast=True)

    def push_task_completed(self, task: Any) -> None:
        data = {
            'id': task.id,
            'fileName': task.file_name,
            'status': task.status,
            'completedAt': task.completed_at.isoformat() if task.completed_at else None
        }
        
        self.socketio.emit('task_completed', data, room=task.id)
        self.socketio.emit('task_completed', data, broadcast=True)

    def push_task_failed(self, task: Any) -> None:
        data = {
            'id': task.id,
            'fileName': task.file_name,
            'status': task.status,
            'errorMessage': task.error_message,
            'completedAt': task.completed_at.isoformat() if task.completed_at else None
        }
        
        self.socketio.emit('task_failed', data, room=task.id)
        self.socketio.emit('task_failed', data, broadcast=True)

    def make_progress_callback(self):
        def callback(
            task_id: str,
            status: str,
            progress: int,
            current_page: Optional[int],
            total_pages: int,
            message: str
        ) -> None:
            self.push_progress(
                task_id=task_id,
                status=status,
                progress=progress,
                message=message,
                current_page=current_page,
                total_pages=total_pages
            )
        return callback
