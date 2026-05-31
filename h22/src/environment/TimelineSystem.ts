import type { TimelineState, Season } from '../types';

export interface TimelineListener {
  onTimeChange?: (time: number, normalized: number) => void;
  onPlayStateChange?: (isPlaying: boolean) => void;
  onSeasonChange?: (season: Season) => void;
}

export class TimelineSystem {
  private state: TimelineState = {
    currentTime: 0,
    totalDuration: 365,
    isPlaying: false,
    playbackSpeed: 1,
    seasonTime: 0
  };

  private listeners: Set<TimelineListener> = new Set();
  private seasonOrder: Season[] = ['spring', 'summer', 'autumn', 'winter'];
  private currentSeason: Season = 'spring';

  constructor(totalDuration: number = 365) {
    this.state.totalDuration = totalDuration;
  }

  setTotalDuration(duration: number): void {
    this.state.totalDuration = Math.max(1, duration);
    this.notifyTimeChange();
  }

  getTotalDuration(): number {
    return this.state.totalDuration;
  }

  getCurrentTime(): number {
    return this.state.currentTime;
  }

  getNormalizedTime(): number {
    return this.state.currentTime / this.state.totalDuration;
  }

  setTime(time: number): void {
    const oldTime = this.state.currentTime;
    this.state.currentTime = Math.max(0, Math.min(this.state.totalDuration, time));
    
    if (oldTime !== this.state.currentTime) {
      this.updateSeason();
      this.notifyTimeChange();
    }
  }

  scrubTo(normalizedTime: number): void {
    this.setTime(normalizedTime * this.state.totalDuration);
  }

  play(): void {
    if (!this.state.isPlaying) {
      this.state.isPlaying = true;
      this.notifyPlayStateChange();
    }
  }

  pause(): void {
    if (this.state.isPlaying) {
      this.state.isPlaying = false;
      this.notifyPlayStateChange();
    }
  }

  togglePlay(): void {
    if (this.state.isPlaying) {
      this.pause();
    } else {
      this.play();
    }
  }

  stop(): void {
    this.pause();
    this.setTime(0);
  }

  isPlaying(): boolean {
    return this.state.isPlaying;
  }

  setPlaybackSpeed(speed: number): void {
    this.state.playbackSpeed = Math.max(0.1, Math.min(100, speed));
  }

  getPlaybackSpeed(): number {
    return this.state.playbackSpeed;
  }

  getCurrentSeason(): Season {
    return this.currentSeason;
  }

  getSeasonProgress(): number {
    const seasonLength = this.state.totalDuration / 4;
    const seasonTime = this.state.currentTime % seasonLength;
    return seasonTime / seasonLength;
  }

  update(deltaTime: number): void {
    if (this.state.isPlaying) {
      const timeIncrement = deltaTime * this.state.playbackSpeed;
      let newTime = this.state.currentTime + timeIncrement;
      
      if (newTime >= this.state.totalDuration) {
        newTime = 0;
      }
      
      this.setTime(newTime);
    }
  }

  stepForward(amount: number = 1): void {
    this.setTime(this.state.currentTime + amount);
  }

  stepBackward(amount: number = 1): void {
    this.setTime(this.state.currentTime - amount);
  }

  goToStart(): void {
    this.setTime(0);
  }

  goToEnd(): void {
    this.setTime(this.state.totalDuration);
  }

  goToSeason(season: Season): void {
    const seasonIndex = this.seasonOrder.indexOf(season);
    const seasonStart = (seasonIndex / 4) * this.state.totalDuration;
    this.setTime(seasonStart + this.state.totalDuration / 8);
  }

  private updateSeason(): void {
    const seasonIndex = Math.floor((this.state.currentTime / this.state.totalDuration) * 4) % 4;
    const newSeason = this.seasonOrder[seasonIndex];
    
    if (newSeason !== this.currentSeason) {
      this.currentSeason = newSeason;
      this.notifySeasonChange();
    }
  }

  subscribe(listener: TimelineListener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private notifyTimeChange(): void {
    const normalized = this.getNormalizedTime();
    this.listeners.forEach(l => l.onTimeChange?.(this.state.currentTime, normalized));
  }

  private notifyPlayStateChange(): void {
    this.listeners.forEach(l => l.onPlayStateChange?.(this.state.isPlaying));
  }

  private notifySeasonChange(): void {
    this.listeners.forEach(l => l.onSeasonChange?.(this.currentSeason));
  }

  getState(): TimelineState {
    return { ...this.state };
  }

  formatTime(time: number): string {
    const days = Math.floor(time);
    const hours = Math.floor((time - days) * 24);
    return `Day ${days + 1}, ${hours.toString().padStart(2, '0')}:00`;
  }

  getYearProgress(): number {
    return (this.state.currentTime % (this.state.totalDuration / 1)) / (this.state.totalDuration / 1);
  }

  getDayOfYear(): number {
    return Math.floor(this.state.currentTime) + 1;
  }
}
