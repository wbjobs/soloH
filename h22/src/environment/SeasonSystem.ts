import type { Season, SeasonColors } from '../types';

export class SeasonSystem {
  private currentSeason: Season = 'summer';
  private transitionProgress: number = 0;
  private targetSeason: Season = 'summer';
  private autoTransition: boolean = false;
  private transitionSpeed: number = 0.01;

  private readonly seasonOrder: Season[] = ['spring', 'summer', 'autumn', 'winter'];

  setSeason(season: Season): void {
    this.currentSeason = season;
    this.targetSeason = season;
    this.transitionProgress = 0;
  }

  getCurrentSeason(): Season {
    return this.currentSeason;
  }

  setAutoTransition(enabled: boolean): void {
    this.autoTransition = enabled;
  }

  setTransitionSpeed(speed: number): void {
    this.transitionSpeed = Math.max(0.001, Math.min(0.1, speed));
  }

  update(deltaTime: number): void {
    if (this.autoTransition && this.transitionProgress < 1) {
      this.transitionProgress += this.transitionSpeed * deltaTime * 60;
      
      if (this.transitionProgress >= 1) {
        this.transitionProgress = 0;
        const currentIndex = this.seasonOrder.indexOf(this.currentSeason);
        const nextIndex = (currentIndex + 1) % this.seasonOrder.length;
        this.currentSeason = this.seasonOrder[nextIndex];
        this.targetSeason = this.seasonOrder[(nextIndex + 1) % this.seasonOrder.length];
      }
    }
  }

  private rgbToHsl(rgb: [number, number, number]): [number, number, number] {
    const r = rgb[0];
    const g = rgb[1];
    const b = rgb[2];
    
    const max = Math.max(r, g, b);
    const min = Math.min(r, g, b);
    let h = 0;
    let s = 0;
    const l = (max + min) / 2;
    
    if (max !== min) {
      const d = max - min;
      s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
      
      switch (max) {
        case r: h = ((g - b) / d + (g < b ? 6 : 0)) / 6; break;
        case g: h = ((b - r) / d + 2) / 6; break;
        case b: h = ((r - g) / d + 4) / 6; break;
      }
    }
    
    return [h, s, l];
  }

  private hue2rgb(p: number, q: number, t: number): number {
    if (t < 0) t += 1;
    if (t > 1) t -= 1;
    if (t < 1/6) return p + (q - p) * 6 * t;
    if (t < 1/2) return q;
    if (t < 2/3) return p + (q - p) * (2/3 - t) * 6;
    return p;
  }

  private hslToRgb(hsl: [number, number, number]): [number, number, number] {
    const [h, s, l] = hsl;
    let r, g, b;
    
    if (s === 0) {
      r = g = b = l;
    } else {
      const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
      const p = 2 * l - q;
      r = this.hue2rgb(p, q, h + 1/3);
      g = this.hue2rgb(p, q, h);
      b = this.hue2rgb(p, q, h - 1/3);
    }
    
    return [r, g, b];
  }

  private lerpHue(h1: number, h2: number, t: number): number {
    let diff = h2 - h1;
    
    if (diff > 0.5) {
      diff -= 1;
    } else if (diff < -0.5) {
      diff += 1;
    }
    
    let result = h1 + diff * t;
    
    if (result < 0) result += 1;
    if (result > 1) result -= 1;
    
    return result;
  }

  getCurrentColor(colors: SeasonColors): [number, number, number] {
    const currentRgb = colors[this.currentSeason];
    
    if (!this.autoTransition || this.transitionProgress === 0) {
      return currentRgb;
    }
    
    const targetRgb = colors[this.targetSeason];
    const t = this.easeInOutCubic(this.transitionProgress);
    
    const currentHsl = this.rgbToHsl(currentRgb);
    const targetHsl = this.rgbToHsl(targetRgb);
    
    const interpolatedHsl: [number, number, number] = [
      this.lerpHue(currentHsl[0], targetHsl[0], t),
      currentHsl[1] + (targetHsl[1] - currentHsl[1]) * t,
      currentHsl[2] + (targetHsl[2] - currentHsl[2]) * t
    ];
    
    const resultRgb = this.hslToRgb(interpolatedHsl);
    
    return resultRgb;
  }

  getSeasonColors(season: Season): [number, number, number] {
    const presetColors: Record<Season, [number, number, number]> = {
      spring: [0.95, 0.85, 0.75],
      summer: [1, 1, 1],
      autumn: [1, 0.9, 0.8],
      winter: [0.85, 0.9, 0.95]
    };
    return presetColors[season];
  }

  getFoliageDensity(): number {
    const densities: Record<Season, number> = {
      spring: 0.7,
      summer: 1.0,
      autumn: 0.6,
      winter: 0.1
    };
    
    if (!this.autoTransition || this.transitionProgress === 0) {
      return densities[this.currentSeason];
    }
    
    const current = densities[this.currentSeason];
    const target = densities[this.targetSeason];
    const t = this.easeInOutCubic(this.transitionProgress);
    
    return current + (target - current) * t;
  }

  private easeInOutCubic(t: number): number {
    return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
  }

  getAmbientColor(): [number, number, number] {
    return this.getSeasonColors(this.currentSeason);
  }

  getFogColor(): [number, number, number] {
    const colors: Record<Season, [number, number, number]> = {
      spring: [0.7, 0.8, 0.9],
      summer: [0.6, 0.75, 0.95],
      autumn: [0.9, 0.7, 0.5],
      winter: [0.85, 0.9, 0.95]
    };
    return colors[this.currentSeason];
  }
}
