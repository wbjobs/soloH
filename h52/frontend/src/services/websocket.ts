import type { StreamResult, StreamFrame } from '@/types';

const WS_BASE_URL = import.meta.env.VITE_WS_BASE_URL || 'ws://localhost:8000';

type MessageType = 'frame' | 'result' | 'error' | 'ping' | 'pong' | 'start' | 'stop';

interface WebSocketMessage<T = unknown> {
  type: MessageType;
  data?: T;
  timestamp: number;
}

export class EmotionStreamClient {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private isManualClose = false;
  private onResultCallback: ((result: StreamResult) => void) | null = null;
  private onErrorCallback: ((error: string) => void) | null = null;
  private onOpenCallback: (() => void) | null = null;
  private onCloseCallback: ((code: number, reason: string) => void) | null = null;

  constructor() {}

  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      try {
        const url = `${WS_BASE_URL}/api/v1/stream`;
        this.ws = new WebSocket(url);

        this.ws.onopen = () => {
          console.log('WebSocket connected');
          this.reconnectAttempts = 0;
          this.onOpenCallback?.();
          resolve();
        };

        this.ws.onmessage = (event) => {
          try {
            const message: WebSocketMessage = JSON.parse(event.data);
            this.handleMessage(message);
          } catch (error) {
            console.error('Failed to parse WebSocket message:', error);
          }
        };

        this.ws.onerror = (error) => {
          console.error('WebSocket error:', error);
          this.onErrorCallback?.('WebSocket connection error');
          reject(error);
        };

        this.ws.onclose = (event) => {
          console.log('WebSocket closed:', event.code, event.reason);
          this.onCloseCallback?.(event.code, event.reason);

          if (!this.isManualClose && this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
            console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);
            setTimeout(() => this.connect(), delay);
          }
        };
      } catch (error) {
        reject(error);
      }
    });
  }

  private handleMessage(message: WebSocketMessage): void {
    switch (message.type) {
      case 'result':
        if (this.onResultCallback && message.data) {
          this.onResultCallback(message.data as StreamResult);
        }
        break;
      case 'error':
        if (this.onErrorCallback && message.data) {
          this.onErrorCallback(message.data as string);
        }
        break;
      case 'ping':
        this.send('pong');
        break;
    }
  }

  sendFrame(frame: StreamFrame): void {
    this.send('frame', frame);
  }

  startStream(): void {
    this.send('start');
  }

  stopStream(): void {
    this.send('stop');
  }

  private send(type: MessageType, data?: unknown): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      const message: WebSocketMessage = {
        type,
        data,
        timestamp: Date.now(),
      };
      this.ws.send(JSON.stringify(message));
    }
  }

  onResult(callback: (result: StreamResult) => void): void {
    this.onResultCallback = callback;
  }

  onError(callback: (error: string) => void): void {
    this.onErrorCallback = callback;
  }

  onOpen(callback: () => void): void {
    this.onOpenCallback = callback;
  }

  onClose(callback: (code: number, reason: string) => void): void {
    this.onCloseCallback = callback;
  }

  close(): void {
    this.isManualClose = true;
    if (this.ws) {
      this.stopStream();
      this.ws.close();
      this.ws = null;
    }
  }

  getReadyState(): number {
    return this.ws?.readyState ?? WebSocket.CLOSED;
  }

  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}

export const createStreamClient = (): EmotionStreamClient => {
  return new EmotionStreamClient();
};
