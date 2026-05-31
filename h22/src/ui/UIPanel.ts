import type { EnvironmentParams, Season, PlantPresetType, WindParams, TropismParams, ResourceCompetitionParams, PlantInstance, LifecycleStage } from '../types';

export interface UIControls {
  onEnvironmentChange: (params: Partial<EnvironmentParams>) => void;
  onPresetChange: (preset: PlantPresetType) => void;
  onSeasonChange: (season: Season) => void;
  onWindChange: (params: Partial<WindParams>) => void;
  onIterationsChange: (iterations: number) => void;
  onRegenerate: () => void;
  onExportGLB: () => void;
  onExportGLTF: () => void;
  onGrowthChange: (progress: number) => void;
  onAutoSeasonChange: (enabled: boolean) => void;
  onTimelineScrub: (normalizedTime: number) => void;
  onTimelinePlay: () => void;
  onTimelinePause: () => void;
  onTimelineSpeedChange: (speed: number) => void;
  onTimelineReset: () => void;
  onAddPlant: (presetType?: PlantPresetType) => void;
  onRemovePlant: (plantId: string) => void;
  onAddPlantGrid: () => void;
  onClearAllPlants: () => void;
  onSelectPlant: (plantId: string | null) => void;
  onTropismChange: (params: Partial<TropismParams>) => void;
  onCompetitionChange: (params: Partial<ResourceCompetitionParams>) => void;
  onSetWaterSource: () => void;
  onLifecycleSpeedChange: (speed: number) => void;
}

export class UIPanel {
  private container: HTMLElement;
  private controls: UIControls;
  private iterations: number = 5;
  private growthProgress: number = 1;
  private selectedPlantId: string | null = null;
  private plants: PlantInstance[] = [];
  private timelineTime: number = 0;
  private isTimelinePlaying: boolean = false;

  constructor(containerId: string, controls: UIControls) {
    const container = document.getElementById(containerId);
    if (!container) throw new Error(`Container ${containerId} not found`);
    this.container = container;
    this.controls = controls;
    
    this.buildUI();
  }

  private buildUI(): void {
    this.container.innerHTML = `
      <div class="panel-header">
        <h1>🌿 L-System Plant Generator</h1>
      </div>

      <div class="section">
        <h3>⏱️ Timeline Control</h3>
        <div class="timeline-container">
          <div class="timeline-info">
            <span id="timeline-time">Day 1, 00:00</span>
            <span id="timeline-season">🌸 Spring</span>
          </div>
          <input type="range" id="timeline-scrub" min="0" max="1000" value="0" step="1">
          <div class="timeline-milestones">
            <span title="Seed">🌰</span>
            <span title="Germination">🌱</span>
            <span title="Seedling">🌿</span>
            <span title="Juvenile">🌳</span>
            <span title="Mature">🌲</span>
            <span title="Senescent">🍂</span>
            <span title="Dying">💀</span>
            <span title="Dead">⚰️</span>
          </div>
          <div class="timeline-controls">
            <button class="timeline-btn" id="timeline-reset" title="Reset">⏮️</button>
            <button class="timeline-btn" id="timeline-step-back" title="Step Back">⏪</button>
            <button class="timeline-btn" id="timeline-play" title="Play/Pause">▶️</button>
            <button class="timeline-btn" id="timeline-step-forward" title="Step Forward">⏩</button>
            <button class="timeline-btn" id="timeline-end" title="Go to End">⏭️</button>
          </div>
          <div class="slider-group">
            <label>
              <span>Speed: <span id="timeline-speed-value">1.0x</span></span>
              <input type="range" id="timeline-speed" min="1" max="100" value="10" step="1">
            </label>
            <label>
              <span>Lifecycle: <span id="lifecycle-speed-value">1.0x</span></span>
              <input type="range" id="lifecycle-speed" min="1" max="100" value="10" step="1">
            </label>
          </div>
        </div>
      </div>

      <div class="section">
        <h3>🌱 Plant Management</h3>
        <div class="plant-controls">
          <div class="preset-buttons">
            <button class="preset-btn active" data-preset="tree">🌳 Tree</button>
            <button class="preset-btn" data-preset="fern">🌿 Fern</button>
            <button class="preset-btn" data-preset="vine">🍃 Vine</button>
          </div>
          <div class="action-buttons-row">
            <button class="action-btn small" id="add-plant">➕ Add Plant</button>
            <button class="action-btn small" id="add-grid">🔲 Grid (9)</button>
            <button class="action-btn small danger" id="clear-all">🗑️ Clear All</button>
          </div>
        </div>
        <div class="plant-list" id="plant-list">
          <div class="empty-list">No plants yet. Click "Add Plant" to start.</div>
        </div>
        <div id="selected-plant-info" class="plant-info" style="display: none;">
          <h4>Selected Plant</h4>
          <div class="info-row"><span>Stage:</span><span id="info-stage">-</span></div>
          <div class="info-row"><span>Age:</span><span id="info-age">-</span></div>
          <div class="info-row"><span>Health:</span><span id="info-health">-</span></div>
          <div class="info-row"><span>Height:</span><span id="info-height">-</span></div>
          <div class="info-row"><span>Competition:</span><span id="info-competition">-</span></div>
          <button class="action-btn small danger" id="remove-selected">Remove Selected</button>
        </div>
      </div>

      <div class="section">
        <h3>Growth Parameters</h3>
        <div class="slider-group">
          <label>
            <span>Iterations: <span id="iterations-value">5</span></span>
            <input type="range" id="iterations" min="1" max="8" value="5" step="1">
          </label>
          <label>
            <span>Growth: <span id="growth-value">100%</span></span>
            <input type="range" id="growth" min="0" max="100" value="100" step="1">
          </label>
        </div>
        <button class="action-btn" id="regenerate">🔄 Regenerate Selected</button>
      </div>

      <div class="section">
        <h3>🌍 Environment</h3>
        <div class="slider-group">
          <label>
            <span>☀️ Light: <span id="light-value">70%</span></span>
            <input type="range" id="light" min="0" max="100" value="70">
          </label>
          <label>
            <span>💧 Water: <span id="water-value">60%</span></span>
            <input type="range" id="water" min="0" max="100" value="60">
          </label>
          <label>
            <span>🌱 Nutrients: <span id="nutrients-value">50%</span></span>
            <input type="range" id="nutrients" min="0" max="100" value="50">
          </label>
          <label>
            <span>🌡️ Temperature: <span id="temperature-value">60%</span></span>
            <input type="range" id="temperature" min="0" max="100" value="60">
          </label>
        </div>
        <button class="action-btn small" id="set-water-source">💧 Set Water Source</button>
        <div class="status" id="growth-status">Good - Favorable conditions</div>
      </div>

      <div class="section">
        <h3>🌱 Tropism</h3>
        <div class="slider-group">
          <label>
            <span>☀️ Phototropism: <span id="photo-value">60%</span></span>
            <input type="range" id="phototropism" min="0" max="100" value="60">
          </label>
          <label>
            <span>💧 Hydrotropism: <span id="hydro-value">40%</span></span>
            <input type="range" id="hydrotropism" min="0" max="100" value="40">
          </label>
          <label>
            <span>Strength: <span id="tropism-strength-value">30%</span></span>
            <input type="range" id="tropism-strength" min="0" max="100" value="30">
          </label>
        </div>
      </div>

      <div class="section">
        <h3>⚔️ Competition</h3>
        <div class="slider-group">
          <label>
            <span>🌱 Root Weight: <span id="root-comp-value">70%</span></span>
            <input type="range" id="root-competition" min="0" max="100" value="70">
          </label>
          <label>
            <span>🌤️ Shade Weight: <span id="shade-comp-value">50%</span></span>
            <input type="range" id="shade-competition" min="0" max="100" value="50">
          </label>
          <label>
            <span>Depletion: <span id="depletion-value">10%</span></span>
            <input type="range" id="depletion" min="0" max="100" value="10">
          </label>
          <label>
            <span>Recovery: <span id="recovery-value">5%</span></span>
            <input type="range" id="recovery" min="0" max="100" value="5">
          </label>
        </div>
      </div>

      <div class="section">
        <h3>🌬️ Wind</h3>
        <div class="slider-group">
          <label>
            <span>Strength: <span id="wind-strength-value">30%</span></span>
            <input type="range" id="wind-strength" min="0" max="100" value="30">
          </label>
          <label>
            <span>Frequency: <span id="wind-freq-value">1.0</span></span>
            <input type="range" id="wind-freq" min="0" max="100" value="50">
          </label>
        </div>
      </div>

      <div class="section">
        <h3>🌸 Season</h3>
        <div class="season-buttons">
          <button class="season-btn active" data-season="spring">🌸 Spring</button>
          <button class="season-btn" data-season="summer">☀️ Summer</button>
          <button class="season-btn" data-season="autumn">🍂 Autumn</button>
          <button class="season-btn" data-season="winter">❄️ Winter</button>
        </div>
        <label class="checkbox">
          <input type="checkbox" id="auto-season">
          <span>Auto-transition with timeline</span>
        </label>
      </div>

      <div class="section">
        <h3>📦 Export</h3>
        <div class="export-buttons">
          <button class="action-btn" id="export-glb">📦 Export GLB</button>
          <button class="action-btn" id="export-gltf">📄 Export glTF</button>
        </div>
      </div>

      <div class="progress-container" id="progress-container" style="display: none;">
        <div class="progress-bar">
          <div class="progress-fill" id="progress-fill"></div>
        </div>
        <span class="progress-text" id="progress-text">Generating...</span>
      </div>
    `;

    this.attachEventListeners();
  }

  private attachEventListeners(): void {
    document.querySelectorAll('.preset-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        document.querySelectorAll('.preset-btn').forEach(b => b.classList.remove('active'));
        (e.target as HTMLElement).classList.add('active');
      });
    });

    document.querySelectorAll('.season-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        document.querySelectorAll('.season-btn').forEach(b => b.classList.remove('active'));
        (e.target as HTMLElement).classList.add('active');
        const season = (e.target as HTMLElement).dataset.season as Season;
        this.controls.onSeasonChange(season);
      });
    });

    const timelineScrub = document.getElementById('timeline-scrub') as HTMLInputElement;
    timelineScrub.addEventListener('input', (e) => {
      const value = parseInt((e.target as HTMLInputElement).value) / 1000;
      this.controls.onTimelineScrub(value);
    });

    document.getElementById('timeline-play')!.addEventListener('click', () => {
      if (this.isTimelinePlaying) {
        this.controls.onTimelinePause();
      } else {
        this.controls.onTimelinePlay();
      }
    });

    document.getElementById('timeline-reset')!.addEventListener('click', () => {
      this.controls.onTimelineReset();
    });

    document.getElementById('timeline-step-back')!.addEventListener('click', () => {
      const newTime = Math.max(0, (this.timelineTime / 365) - 0.01);
      this.controls.onTimelineScrub(newTime);
    });

    document.getElementById('timeline-step-forward')!.addEventListener('click', () => {
      const newTime = Math.min(1, (this.timelineTime / 365) + 0.01);
      this.controls.onTimelineScrub(newTime);
    });

    document.getElementById('timeline-end')!.addEventListener('click', () => {
      this.controls.onTimelineScrub(1);
    });

    const timelineSpeed = document.getElementById('timeline-speed') as HTMLInputElement;
    timelineSpeed.addEventListener('input', (e) => {
      const value = parseInt((e.target as HTMLInputElement).value) / 10;
      document.getElementById('timeline-speed-value')!.textContent = `${value.toFixed(1)}x`;
      this.controls.onTimelineSpeedChange(value);
    });

    const lifecycleSpeed = document.getElementById('lifecycle-speed') as HTMLInputElement;
    lifecycleSpeed.addEventListener('input', (e) => {
      const value = parseInt((e.target as HTMLInputElement).value) / 10;
      document.getElementById('lifecycle-speed-value')!.textContent = `${value.toFixed(1)}x`;
      this.controls.onLifecycleSpeedChange(value);
    });

    document.getElementById('add-plant')!.addEventListener('click', () => {
      const activePreset = document.querySelector('.preset-btn.active') as HTMLElement;
      const presetType = activePreset?.dataset.preset as PlantPresetType || 'tree';
      this.controls.onAddPlant(presetType);
    });

    document.getElementById('add-grid')!.addEventListener('click', () => {
      this.controls.onAddPlantGrid();
    });

    document.getElementById('clear-all')!.addEventListener('click', () => {
      if (confirm('Clear all plants?')) {
        this.controls.onClearAllPlants();
      }
    });

    document.getElementById('remove-selected')!.addEventListener('click', () => {
      if (this.selectedPlantId) {
        this.controls.onRemovePlant(this.selectedPlantId);
      }
    });

    document.getElementById('set-water-source')!.addEventListener('click', () => {
      this.controls.onSetWaterSource();
    });

    const iterationsSlider = document.getElementById('iterations') as HTMLInputElement;
    iterationsSlider.addEventListener('input', (e) => {
      const value = parseInt((e.target as HTMLInputElement).value);
      this.iterations = value;
      document.getElementById('iterations-value')!.textContent = value.toString();
      this.controls.onIterationsChange(value);
    });

    const growthSlider = document.getElementById('growth') as HTMLInputElement;
    growthSlider.addEventListener('input', (e) => {
      const value = parseInt((e.target as HTMLInputElement).value);
      this.growthProgress = value / 100;
      document.getElementById('growth-value')!.textContent = `${value}%`;
      this.controls.onGrowthChange(this.growthProgress);
    });

    const envSliders = ['light', 'water', 'nutrients', 'temperature'];
    envSliders.forEach(param => {
      const slider = document.getElementById(param) as HTMLInputElement;
      slider.addEventListener('input', (e) => {
        const value = parseInt((e.target as HTMLInputElement).value) / 100;
        document.getElementById(`${param}-value`)!.textContent = `${Math.round(value * 100)}%`;
        this.controls.onEnvironmentChange({ [param]: value } as Partial<EnvironmentParams>);
      });
    });

    const tropismSliders: [string, keyof TropismParams][] = [
      ['phototropism', 'phototropism'],
      ['hydrotropism', 'hydrotropism'],
      ['tropism-strength', 'strength']
    ];
    tropismSliders.forEach(([id, param]) => {
      const slider = document.getElementById(id) as HTMLInputElement;
      slider.addEventListener('input', (e) => {
        const value = parseInt((e.target as HTMLInputElement).value) / 100;
        const valueId = id === 'tropism-strength' ? 'tropism-strength-value' : 
                       id === 'phototropism' ? 'photo-value' : 'hydro-value';
        document.getElementById(valueId)!.textContent = `${Math.round(value * 100)}%`;
        this.controls.onTropismChange({ [param]: value } as Partial<TropismParams>);
      });
    });

    const compSliders: [string, keyof ResourceCompetitionParams][] = [
      ['root-competition', 'rootCompetitionWeight'],
      ['shade-competition', 'shadeCompetitionWeight'],
      ['depletion', 'resourceDepletionRate'],
      ['recovery', 'recoveryRate']
    ];
    compSliders.forEach(([id, param]) => {
      const slider = document.getElementById(id) as HTMLInputElement;
      slider.addEventListener('input', (e) => {
        const value = parseInt((e.target as HTMLInputElement).value) / 100;
        const valueId = id === 'root-competition' ? 'root-comp-value' :
                       id === 'shade-competition' ? 'shade-comp-value' :
                       id === 'depletion' ? 'depletion-value' : 'recovery-value';
        document.getElementById(valueId)!.textContent = `${Math.round(value * 100)}%`;
        this.controls.onCompetitionChange({ [param]: value } as Partial<ResourceCompetitionParams>);
      });
    });

    const windStrength = document.getElementById('wind-strength') as HTMLInputElement;
    windStrength.addEventListener('input', (e) => {
      const value = parseInt((e.target as HTMLInputElement).value) / 100;
      document.getElementById('wind-strength-value')!.textContent = `${Math.round(value * 100)}%`;
      this.controls.onWindChange({ strength: value });
    });

    const windFreq = document.getElementById('wind-freq') as HTMLInputElement;
    windFreq.addEventListener('input', (e) => {
      const value = parseInt((e.target as HTMLInputElement).value) / 50;
      document.getElementById('wind-freq-value')!.textContent = value.toFixed(1);
      this.controls.onWindChange({ frequency: value });
    });

    const autoSeason = document.getElementById('auto-season') as HTMLInputElement;
    autoSeason.addEventListener('change', (e) => {
      this.controls.onAutoSeasonChange((e.target as HTMLInputElement).checked);
    });

    document.getElementById('regenerate')!.addEventListener('click', () => {
      this.controls.onRegenerate();
    });

    document.getElementById('export-glb')!.addEventListener('click', () => {
      this.controls.onExportGLB();
    });

    document.getElementById('export-gltf')!.addEventListener('click', () => {
      this.controls.onExportGLTF();
    });
  }

  updateGrowthStatus(status: string, description: string): void {
    const statusEl = document.getElementById('growth-status');
    if (statusEl) {
      statusEl.textContent = `${status} - ${description}`;
      statusEl.className = `status status-${status.toLowerCase()}`;
    }
  }

  showProgress(show: boolean): void {
    const container = document.getElementById('progress-container');
    if (container) {
      container.style.display = show ? 'block' : 'none';
    }
  }

  updateProgress(progress: number): void {
    const fill = document.getElementById('progress-fill');
    const text = document.getElementById('progress-text');
    if (fill) {
      fill.style.width = `${Math.round(progress * 100)}%`;
    }
    if (text) {
      text.textContent = `Generating... ${Math.round(progress * 100)}%`;
    }
  }

  getIterations(): number {
    return this.iterations;
  }

  getGrowthProgress(): number {
    return this.growthProgress;
  }

  getSelectedPreset(): PlantPresetType {
    const activePreset = document.querySelector('.preset-btn.active') as HTMLElement;
    return (activePreset?.dataset.preset as PlantPresetType) || 'tree';
  }

  getSelectedPlantId(): string | null {
    return this.selectedPlantId;
  }

  updateTimeline(time: number, normalized: number, season: Season, isPlaying: boolean): void {
    this.timelineTime = time;
    this.isTimelinePlaying = isPlaying;

    const scrub = document.getElementById('timeline-scrub') as HTMLInputElement;
    if (scrub) scrub.value = (normalized * 1000).toString();

    const timeEl = document.getElementById('timeline-time');
    if (timeEl) {
      const days = Math.floor(time);
      const hours = Math.floor((time - days) * 24);
      timeEl.textContent = `Day ${days + 1}, ${hours.toString().padStart(2, '0')}:00`;
    }

    const seasonEl = document.getElementById('timeline-season');
    if (seasonEl) {
      const seasonEmojis: Record<Season, string> = {
        spring: '🌸 Spring',
        summer: '☀️ Summer',
        autumn: '🍂 Autumn',
        winter: '❄️ Winter'
      };
      seasonEl.textContent = seasonEmojis[season];
    }

    const playBtn = document.getElementById('timeline-play');
    if (playBtn) playBtn.textContent = isPlaying ? '⏸️' : '▶️';

    document.querySelectorAll('.season-btn').forEach(btn => {
      const btnSeason = (btn as HTMLElement).dataset.season as Season;
      btn.classList.toggle('active', btnSeason === season);
    });
  }

  updatePlants(plants: PlantInstance[], competitionFactors: Map<string, number>): void {
    this.plants = plants;
    const listEl = document.getElementById('plant-list');
    if (!listEl) return;

    if (plants.length === 0) {
      listEl.innerHTML = '<div class="empty-list">No plants yet. Click "Add Plant" to start.</div>';
      this.updateSelectedPlantInfo(null, null);
      return;
    }

    const stageEmojis: Record<LifecycleStage, string> = {
      seed: '🌰',
      germination: '🌱',
      seedling: '🌿',
      juvenile: '🌳',
      mature: '🌲',
      senescent: '🍂',
      dying: '💀',
      dead: '⚰️'
    };

    const presetEmojis: Record<PlantPresetType, string> = {
      tree: '🌳',
      fern: '🌿',
      vine: '🍃'
    };

    let html = '';
    plants.forEach((plant, index) => {
      const compFactor = competitionFactors.get(plant.id) ?? 1;
      const isSelected = plant.id === this.selectedPlantId;
      const healthColor = plant.health > 0.7 ? 'good' : plant.health > 0.4 ? 'warning' : 'danger';
      
      html += `
        <div class="plant-item ${isSelected ? 'selected' : ''} ${!plant.isAlive ? 'dead' : ''}" data-plant-id="${plant.id}">
          <span class="plant-emoji">${presetEmojis[plant.presetType]}${stageEmojis[plant.lifecycleStage]}</span>
          <span class="plant-name">${plant.presetType} #${index + 1}</span>
          <span class="plant-health health-${healthColor}">${Math.round(plant.health * 100)}%</span>
          <span class="plant-comp">⚔️${Math.round(compFactor * 100)}%</span>
        </div>
      `;
    });
    listEl.innerHTML = html;

    listEl.querySelectorAll('.plant-item').forEach(item => {
      item.addEventListener('click', () => {
        const plantId = (item as HTMLElement).dataset.plantId || null;
        this.selectPlant(plantId);
      });
    });

    if (this.selectedPlantId) {
      const selectedPlant = plants.find(p => p.id === this.selectedPlantId);
      const compFactor = competitionFactors.get(this.selectedPlantId) ?? null;
      this.updateSelectedPlantInfo(selectedPlant || null, compFactor);
    }
  }

  selectPlant(plantId: string | null): void {
    this.selectedPlantId = plantId;
    this.controls.onSelectPlant(plantId);
    
    document.querySelectorAll('.plant-item').forEach(item => {
      const id = (item as HTMLElement).dataset.plantId;
      item.classList.toggle('selected', id === plantId);
    });

    if (plantId) {
      const plant = this.plants.find(p => p.id === plantId);
      this.updateSelectedPlantInfo(plant || null, null);
    } else {
      this.updateSelectedPlantInfo(null, null);
    }
  }

  updateSelectedPlantInfo(plant: PlantInstance | null, competitionFactor: number | null): void {
    const infoEl = document.getElementById('selected-plant-info');
    if (!infoEl) return;

    if (!plant) {
      infoEl.style.display = 'none';
      return;
    }

    infoEl.style.display = 'block';

    const stageNames: Record<LifecycleStage, string> = {
      seed: '🌰 Seed',
      germination: '🌱 Germination',
      seedling: '🌿 Seedling',
      juvenile: '🌳 Juvenile',
      mature: '🌲 Mature',
      senescent: '🍂 Senescent',
      dying: '💀 Dying',
      dead: '⚰️ Dead'
    };

    const stageEl = document.getElementById('info-stage');
    if (stageEl) stageEl.textContent = stageNames[plant.lifecycleStage];

    const ageEl = document.getElementById('info-age');
    if (ageEl) ageEl.textContent = `Day ${Math.floor(plant.age) + 1}`;

    const healthEl = document.getElementById('info-health');
    if (healthEl) {
      const healthPct = Math.round(plant.health * 100);
      healthEl.textContent = `${healthPct}%`;
      healthEl.className = healthPct > 70 ? 'good' : healthPct > 40 ? 'warning' : 'danger';
    }

    const heightEl = document.getElementById('info-height');
    if (heightEl) heightEl.textContent = `${plant.height.toFixed(1)}m`;

    const compEl = document.getElementById('info-competition');
    if (compEl) {
      const comp = competitionFactor ?? 1;
      const compPct = Math.round(comp * 100);
      compEl.textContent = `${compPct}%`;
      compEl.className = compPct > 70 ? 'good' : compPct > 40 ? 'warning' : 'danger';
    }
  }

  setTimelinePlaying(isPlaying: boolean): void {
    this.isTimelinePlaying = isPlaying;
    const playBtn = document.getElementById('timeline-play');
    if (playBtn) playBtn.textContent = isPlaying ? '⏸️' : '▶️';
  }
}
