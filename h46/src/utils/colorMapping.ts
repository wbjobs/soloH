import * as THREE from 'three';

export interface ColorStop {
  value: number;
  color: THREE.Color;
}

export interface ColorMapOptions {
  minValue: number;
  maxValue: number;
  stops: ColorStop[];
  reverse?: boolean;
}

export class VelocityColorMap {
  private stops: ColorStop[];
  private minValue: number;
  private maxValue: number;

  constructor(minSpeed: number = 0, maxSpeed: number = 15) {
    this.minValue = minSpeed;
    this.maxValue = maxSpeed;
    
    this.stops = [
      { value: minSpeed, color: new THREE.Color(0x1e3a5f) },
      { value: minSpeed + (maxSpeed - minSpeed) * 0.25, color: new THREE.Color(0x4ecdc4) },
      { value: minSpeed + (maxSpeed - minSpeed) * 0.5, color: new THREE.Color(0x95e619) },
      { value: minSpeed + (maxSpeed - minSpeed) * 0.75, color: new THREE.Color(0xffe66d) },
      { value: maxSpeed, color: new THREE.Color(0xff6b35) }
    ];
  }

  setRange(minValue: number, maxValue: number): void {
    this.minValue = minValue;
    this.maxValue = maxValue;
    
    const range = maxValue - minValue;
    this.stops = [
      { value: minValue, color: new THREE.Color(0x1e3a5f) },
      { value: minValue + range * 0.25, color: new THREE.Color(0x4ecdc4) },
      { value: minValue + range * 0.5, color: new THREE.Color(0x95e619) },
      { value: minValue + range * 0.75, color: new THREE.Color(0xffe66d) },
      { value: maxValue, color: new THREE.Color(0xff6b35) }
    ];
  }

  getColor(speed: number): THREE.Color {
    const clampedSpeed = Math.max(this.minValue, Math.min(this.maxValue, speed));
    const t = (clampedSpeed - this.minValue) / (this.maxValue - this.minValue);

    for (let i = 0; i < this.stops.length - 1; i++) {
      const stop1 = this.stops[i];
      const stop2 = this.stops[i + 1];
      
      if (t >= stop1.value / this.maxValue && t <= stop2.value / this.maxValue) {
        const localT = (t - stop1.value / this.maxValue) / (stop2.value / this.maxValue - stop1.value / this.maxValue);
        return stop1.color.clone().lerp(stop2.color, localT);
      }
    }

    return this.stops[this.stops.length - 1].color.clone();
  }

  getColorHex(speed: number): number {
    return this.getColor(speed).getHex();
  }

  getColorRGB(speed: number): { r: number; g: number; b: number } {
    const color = this.getColor(speed);
    return { r: color.r, g: color.g, b: color.b };
  }

  getColorString(speed: number): string {
    return '#' + this.getColor(speed).getHexString();
  }

  static createJetColormap(minValue: number = 0, maxValue: number = 1): VelocityColorMap {
    const map = new VelocityColorMap(minValue, maxValue);
    map.stops = [
      { value: minValue, color: new THREE.Color(0x0000ff) },
      { value: minValue + (maxValue - minValue) * 0.25, color: new THREE.Color(0x00ffff) },
      { value: minValue + (maxValue - minValue) * 0.5, color: new THREE.Color(0x00ff00) },
      { value: minValue + (maxValue - minValue) * 0.75, color: new THREE.Color(0xffff00) },
      { value: maxValue, color: new THREE.Color(0xff0000) }
    ];
    return map;
  }
}

export class PressureColorMap {
  private stops: ColorStop[];

  constructor(minPressure: number = 0, maxPressure: number = 10000) {
    this.stops = [
      { value: minPressure, color: new THREE.Color(0x1a1a2e) },
      { value: minPressure + (maxPressure - minPressure) * 0.2, color: new THREE.Color(0x16213e) },
      { value: minPressure + (maxPressure - minPressure) * 0.4, color: new THREE.Color(0x0f3460) },
      { value: minPressure + (maxPressure - minPressure) * 0.6, color: new THREE.Color(0xe94560) },
      { value: maxPressure, color: new THREE.Color(0xff4757) }
    ];
  }

  getColor(pressure: number): THREE.Color {
    const t = Math.max(0, Math.min(1, pressure / 10000));

    for (let i = 0; i < this.stops.length - 1; i++) {
      const stop1 = this.stops[i];
      const stop2 = this.stops[i + 1];
      
      if (t >= stop1.value / 10000 && t <= stop2.value / 10000) {
        const localT = (t - stop1.value / 10000) / (stop2.value / 10000 - stop1.value / 10000);
        return stop1.color.clone().lerp(stop2.color, localT);
      }
    }

    return this.stops[this.stops.length - 1].color.clone();
  }

  getColorHex(pressure: number): number {
    return this.getColor(pressure).getHex();
  }
}

export function hsvToRgb(h: number, s: number, v: number): THREE.Color {
  const c = v * s;
  const x = c * (1 - Math.abs(((h / 60) % 2) - 1));
  const m = v - c;
  
  let r, g, b;
  
  if (h < 60) { r = c; g = x; b = 0; }
  else if (h < 120) { r = x; g = c; b = 0; }
  else if (h < 180) { r = 0; g = c; b = x; }
  else if (h < 240) { r = 0; g = x; b = c; }
  else if (h < 300) { r = x; g = 0; b = c; }
  else { r = c; g = 0; b = x; }
  
  return new THREE.Color(r + m, g + m, b + m);
}

export function getRainbowColor(t: number): THREE.Color {
  return hsvToRgb(t * 360, 0.8, 1.0);
}
