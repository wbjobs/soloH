import type { HapticSettings } from '../types/audio';

export class HapticFeedback {
  private settings: HapticSettings;
  private gamepads: Map<number, Gamepad> = new Map();
  private isMonitoring: boolean = false;
  private beatIntervalId: number | null = null;
  private lastVibrateTime: number = 0;
  private readonly MIN_VIBRATE_INTERVAL = 100;

  constructor(settings: HapticSettings) {
    this.settings = settings;
    this.setupGamepadListeners();
  }

  private setupGamepadListeners(): void {
    window.addEventListener('gamepadconnected', (e: GamepadEvent) => {
      this.gamepads.set(e.gamepad.index, e.gamepad);
      this.settings.isConnected = true;
      console.log('游戏手柄已连接:', e.gamepad.id);
      this.startMonitoring();
    });

    window.addEventListener('gamepaddisconnected', (e: GamepadEvent) => {
      this.gamepads.delete(e.gamepad.index);
      if (this.gamepads.size === 0) {
        this.settings.isConnected = false;
        this.stopMonitoring();
      }
      console.log('游戏手柄已断开:', e.gamepad.id);
    });

    const existingGamepads = navigator.getGamepads();
    existingGamepads.forEach((gamepad, index) => {
      if (gamepad) {
        this.gamepads.set(index, gamepad);
        this.settings.isConnected = true;
      }
    });

    if (this.gamepads.size > 0) {
      this.startMonitoring();
    }
  }

  private startMonitoring(): void {
    if (this.isMonitoring) return;
    this.isMonitoring = true;
    this.monitorGamepads();
  }

  private stopMonitoring(): void {
    this.isMonitoring = false;
  }

  private monitorGamepads = (): void => {
    if (!this.isMonitoring) return;

    const gamepads = navigator.getGamepads();
    gamepads.forEach((gamepad, index) => {
      if (gamepad) {
        this.gamepads.set(index, gamepad);
      }
    });

    requestAnimationFrame(this.monitorGamepads);
  };

  vibrate(duration: number = 100, strongMagnitude: number = 0.5, weakMagnitude: number = 0.2): boolean {
    const now = performance.now();
    if (now - this.lastVibrateTime < this.MIN_VIBRATE_INTERVAL) {
      return false;
    }

    if (!this.settings.enabled || this.gamepads.size === 0) {
      return false;
    }

    const intensity = this.settings.intensity;
    const actualStrong = strongMagnitude * intensity;
    const actualWeak = weakMagnitude * intensity;

    let success = false;
    this.gamepads.forEach((gamepad, index) => {
      const currentGamepad = navigator.getGamepads()[index];
      if (currentGamepad) {
        if ('vibrationActuator' in currentGamepad && currentGamepad.vibrationActuator) {
          currentGamepad.vibrationActuator.playEffect('dual-rumble', {
            duration,
            strongMagnitude: actualStrong,
            weakMagnitude: actualWeak
          });
          success = true;
        }
      }
    });

    if (success) {
      this.lastVibrateTime = now;
    }

    return success;
  }

  startBeatPattern(beatFrequency: number): void {
    this.stopBeatPattern();

    const interval = (60 / beatFrequency) * 1000;

    const vibrateBeat = () => {
      if (!this.settings.enabled) return;

      switch (this.settings.pattern) {
        case 'beat':
          this.vibrate(80, 0.8, 0.3);
          break;
        case 'wave':
          this.vibrate(200, 0.3, 0.6);
          setTimeout(() => this.vibrate(150, 0.5, 0.4), 100);
          setTimeout(() => this.vibrate(100, 0.3, 0.2), 250);
          break;
        case 'breathing':
          this.vibrate(1500, 0.15, 0.1);
          break;
      }
    };

    vibrateBeat();
    this.beatIntervalId = window.setInterval(vibrateBeat, interval);
  }

  stopBeatPattern(): void {
    if (this.beatIntervalId !== null) {
      clearInterval(this.beatIntervalId);
      this.beatIntervalId = null;
    }
  }

  startBreathingPattern(inhaleTime: number, holdTime: number, exhaleTime: number): void {
    this.stopBeatPattern();

    const runCycle = () => {
      if (!this.settings.enabled) return;

      this.vibrate(inhaleTime * 1000 * 0.8, 0.1, 0.2);

      setTimeout(() => {
        if (!this.settings.enabled) return;
        this.vibrate(holdTime * 1000 * 0.5, 0.05, 0.1);
      }, inhaleTime * 1000);

      setTimeout(() => {
        if (!this.settings.enabled) return;
        this.vibrate(exhaleTime * 1000 * 0.8, 0.2, 0.3);
      }, (inhaleTime + holdTime) * 1000);

      const totalCycle = inhaleTime + holdTime + exhaleTime + 2;
      setTimeout(runCycle, totalCycle * 1000);
    };

    runCycle();
  }

  updateSettings(settings: Partial<HapticSettings>): void {
    Object.assign(this.settings, settings);

    if (settings.pattern) {
      this.stopBeatPattern();
    }
  }

  isConnected(): boolean {
    return this.gamepads.size > 0;
  }

  getConnectedGamepads(): string[] {
    const names: string[] = [];
    this.gamepads.forEach((gamepad) => {
      names.push(gamepad.id);
    });
    return names;
  }

  destroy(): void {
    this.stopBeatPattern();
    this.stopMonitoring();
    this.gamepads.clear();
  }
}
