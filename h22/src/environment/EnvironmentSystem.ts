import type { EnvironmentParams, GrowthModifier, LSystemConfig } from '../types';
import { LSystemParser } from '../lsystem/LSystemParser';

export class EnvironmentSystem {
  private params: EnvironmentParams = {
    light: 0.7,
    water: 0.6,
    nutrients: 0.5,
    temperature: 0.6
  };

  private listeners: Set<(params: EnvironmentParams) => void> = new Set();

  setParams(params: Partial<EnvironmentParams>): void {
    this.params = { ...this.params, ...params };
    this.notifyListeners();
  }

  getParams(): EnvironmentParams {
    return { ...this.params };
  }

  getParam(key: keyof EnvironmentParams): number {
    return this.params[key];
  }

  calculateGrowthModifier(config: LSystemConfig): GrowthModifier {
    return LSystemParser.applyEnvironmentModifiers(config, this.params);
  }

  subscribe(callback: (params: EnvironmentParams) => void): () => void {
    this.listeners.add(callback);
    return () => this.listeners.delete(callback);
  }

  private notifyListeners(): void {
    this.listeners.forEach(callback => callback(this.params));
  }

  getGrowthStatus(): { status: string; description: string } {
    const avg = (this.params.light + this.params.water + this.params.nutrients + this.params.temperature) / 4;
    
    if (avg > 0.8) return { status: 'Excellent', description: 'Optimal growing conditions' };
    if (avg > 0.6) return { status: 'Good', description: 'Favorable conditions' };
    if (avg > 0.4) return { status: 'Moderate', description: 'Acceptable conditions' };
    if (avg > 0.2) return { status: 'Poor', description: 'Stressed conditions' };
    return { status: 'Critical', description: 'Survival only' };
  }
}
