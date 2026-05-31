import { io, type Socket } from 'socket.io-client';
import type { ProgressMessage, TaskResult, Task } from '../types';

const baseURL = import.meta.env.VITE_WS_URL || 'http://localhost:8000';

interface SocketEventMap {
  progress: (data: ProgressMessage) => void;
  completed: (data: { taskId: string; result: TaskResult }) => void;
  failed: (data: { taskId: string; error: string }) => void;
  task_created: (data: Task) => void;
  task_deleted: (data: { taskId: string }) => void;
  task_updated: (data: { taskId: string; status: string }) => void;
  result_updated: (data: { taskId: string; pageNumber: number; lineId: string; content: string }) => void;
  'task-joined': (data: { taskId: string; status: string }) => void;
  'task-left': (data: { taskId: string; status: string }) => void;
  connect: () => void;
  disconnect: () => void;
  connect_error: (error: Error) => void;
}

class SocketManager {
  private socket: Socket | null = null;
  private listeners: Map<string, Set<(data: any) => void>> = new Map();
  private reconnectAttempts: number = 0;
  private maxReconnectAttempts: number = 5;

  connect(): Socket {
    if (this.socket && this.socket.connected) {
      return this.socket;
    }

    this.socket = io(baseURL, {
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionAttempts: this.maxReconnectAttempts,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
      timeout: 20000,
    });

    this.socket.on('connect', () => {
      console.log('WebSocket connected');
      this.reconnectAttempts = 0;
      this.emit('connect');
    });

    this.socket.on('disconnect', (reason) => {
      console.log('WebSocket disconnected:', reason);
      this.emit('disconnect');
    });

    this.socket.on('connect_error', (error) => {
      console.error('WebSocket connection error:', error);
      this.reconnectAttempts++;
      if (this.reconnectAttempts >= this.maxReconnectAttempts) {
        console.error('Max reconnection attempts reached');
      }
      this.emit('connect_error', error);
    });

    this.socket.on('progress', (message: ProgressMessage) => {
      this.emit('progress', message);
    });

    this.socket.on('completed', (data: { taskId: string; result: TaskResult }) => {
      this.emit('completed', data);
    });

    this.socket.on('failed', (data: { taskId: string; error: string }) => {
      this.emit('failed', data);
    });

    this.socket.on('task_created', (data: Task) => {
      this.emit('task_created', data);
    });

    this.socket.on('task_deleted', (data: { taskId: string }) => {
      this.emit('task_deleted', data);
    });

    this.socket.on('task_updated', (data: { taskId: string; status: string }) => {
      this.emit('task_updated', data);
    });

    this.socket.on('result_updated', (data: { taskId: string; pageNumber: number; lineId: string; content: string }) => {
      this.emit('result_updated', data);
    });

    this.socket.on('task-joined', (data: { taskId: string; status: string }) => {
      this.emit('task-joined', data);
    });

    this.socket.on('task-left', (data: { taskId: string; status: string }) => {
      this.emit('task-left', data);
    });

    return this.socket;
  }

  disconnect(): void {
    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
    }
  }

  joinTask(taskId: string): void {
    const socket = this.connect();
    socket.emit('join-task', { taskId });
  }

  leaveTask(taskId: string): void {
    if (this.socket) {
      this.socket.emit('leave-task', { taskId });
    }
  }

  joinRoom(room: string): void {
    const socket = this.connect();
    socket.emit('join', { room });
  }

  leaveRoom(room: string): void {
    if (this.socket) {
      this.socket.emit('leave', { room });
    }
  }

  on<E extends keyof SocketEventMap>(event: E, callback: SocketEventMap[E]): void {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event)!.add(callback);
  }

  off<E extends keyof SocketEventMap>(event: E, callback: SocketEventMap[E]): void {
    const callbacks = this.listeners.get(event);
    if (callbacks) {
      callbacks.delete(callback);
    }
  }

  private emit(event: string, data?: any): void {
    const callbacks = this.listeners.get(event);
    if (callbacks) {
      callbacks.forEach((callback) => {
        try {
          callback(data);
        } catch (error) {
          console.error(`Error in listener for event "${event}":`, error);
        }
      });
    }
  }

  isConnected(): boolean {
    return this.socket?.connected || false;
  }

  getSocket(): Socket | null {
    return this.socket;
  }
}

export const socketManager = new SocketManager();

export default socketManager;
