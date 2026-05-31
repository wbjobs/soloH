import { SimulationStatus, OptimizationStatus, WebSocketMessage } from '../types';

type MessageHandler = {
  onSimulationData?: (data: SimulationStatus) => void;
  onOptimizationUpdate?: (data: OptimizationStatus) => void;
  onOpen?: () => void;
  onClose?: () => void;
  onError?: (error: Event) => void;
};

export class SimulationWebSocket {
  private ws: WebSocket | null = null;
  private handlers: MessageHandler = {};
  private reconnectTimer: number | null = null;
  private url: string;

  constructor(url: string = 'ws://localhost:8001/ws/simulation') {
    this.url = url;
  }

  connect(handlers: MessageHandler): void {
    this.handlers = handlers;

    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      return;
    }

    try {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        console.log('WebSocket connected');
        if (this.handlers.onOpen) {
          this.handlers.onOpen();
        }
        this.startHeartbeat();
      };

      this.ws.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          if (message.type === 'simulation_data' && this.handlers.onSimulationData) {
            this.handlers.onSimulationData(message.data as SimulationStatus);
          } else if (message.type === 'optimization_update' && this.handlers.onOptimizationUpdate) {
            this.handlers.onOptimizationUpdate(message.data as OptimizationStatus);
          }
        } catch (e) {
          console.error('Error parsing WebSocket message:', e);
        }
      };

      this.ws.onclose = () => {
        console.log('WebSocket disconnected');
        if (this.handlers.onClose) {
          this.handlers.onClose();
        }
        this.scheduleReconnect();
      };

      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        if (this.handlers.onError) {
          this.handlers.onError(error);
        }
      };
    } catch (e) {
      console.error('Error connecting WebSocket:', e);
      this.scheduleReconnect();
    }
  }

  private startHeartbeat(): void {
    const heartbeat = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send('ping');
      } else {
        clearInterval(heartbeat);
      }
    }, 30000);
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) {
      return;
    }
    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null;
      this.connect(this.handlers);
    }, 3000);
  }

  disconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }
}

export const simulationWs = new SimulationWebSocket();
