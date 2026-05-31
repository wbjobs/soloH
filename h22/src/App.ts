import type {
  EnvironmentParams,
  Season,
  PlantPresetType,
  WindParams,
  WorkerMessage,
  WorkerGenerateMessage,
  WorkerResultMessage,
  TropismParams,
  ResourceCompetitionParams,
  PlantInstance,
} from './types';
import { PlantRenderer } from './renderer/PlantRenderer';
import { EnvironmentSystem } from './environment/EnvironmentSystem';
import { ResourceCompetitionSystem } from './environment/ResourceCompetitionSystem';
import { TropismSystem } from './environment/TropismSystem';
import { LifecycleSystem } from './environment/LifecycleSystem';
import { TimelineSystem, TimelineListener } from './environment/TimelineSystem';
import { PlantManager } from './plants/PlantManager';
import { getPreset } from './plants/PlantPresets';
import { UIPanel } from './ui/UIPanel';
import { GLTFExporter } from './exporter/GLTFExporter';
import PlantGeneratorWorker from './workers/plantGenerator.worker?worker';

export class PlantGrowthApp {
  private renderer: PlantRenderer;
  private environmentSystem: EnvironmentSystem;
  private resourceCompetitionSystem: ResourceCompetitionSystem;
  private tropismSystem: TropismSystem;
  private lifecycleSystem: LifecycleSystem;
  private timelineSystem: TimelineSystem;
  private plantManager: PlantManager;
  private uiPanel: UIPanel;
  private worker: Worker;

  private currentPreset: PlantPresetType = 'tree';
  private currentIterations: number = 5;
  private isGenerating: boolean = false;
  private lastTime: number = 0;
  private lifecycleSpeed: number = 1;
  private pendingGenerations: Map<string, WorkerGenerateMessage> = new Map();
  private selectedPlantId: string | null = null;
  private isSettingWaterSource: boolean = false;

  constructor(canvasId: string, panelId: string) {
    const canvas = document.getElementById(canvasId) as HTMLCanvasElement;
    if (!canvas) throw new Error(`Canvas ${canvasId} not found`);

    this.renderer = new PlantRenderer(canvas);
    this.environmentSystem = new EnvironmentSystem();
    this.resourceCompetitionSystem = new ResourceCompetitionSystem();
    this.tropismSystem = new TropismSystem();
    this.lifecycleSystem = new LifecycleSystem();
    this.timelineSystem = new TimelineSystem(365);
    this.plantManager = new PlantManager({ maxPlants: 20 });
    this.worker = new PlantGeneratorWorker();

    this.uiPanel = new UIPanel(panelId, {
      onEnvironmentChange: this.handleEnvironmentChange.bind(this),
      onPresetChange: this.handlePresetChange.bind(this),
      onSeasonChange: this.handleSeasonChange.bind(this),
      onWindChange: this.handleWindChange.bind(this),
      onIterationsChange: this.handleIterationsChange.bind(this),
      onRegenerate: this.handleRegenerate.bind(this),
      onExportGLB: this.exportGLB.bind(this),
      onExportGLTF: this.exportGLTF.bind(this),
      onGrowthChange: this.handleGrowthChange.bind(this),
      onAutoSeasonChange: this.handleAutoSeasonChange.bind(this),
      onTimelineScrub: this.handleTimelineScrub.bind(this),
      onTimelinePlay: this.handleTimelinePlay.bind(this),
      onTimelinePause: this.handleTimelinePause.bind(this),
      onTimelineSpeedChange: this.handleTimelineSpeedChange.bind(this),
      onTimelineReset: this.handleTimelineReset.bind(this),
      onAddPlant: this.handleAddPlant.bind(this),
      onRemovePlant: this.handleRemovePlant.bind(this),
      onAddPlantGrid: this.handleAddPlantGrid.bind(this),
      onClearAllPlants: this.handleClearAllPlants.bind(this),
      onSelectPlant: this.handleSelectPlant.bind(this),
      onTropismChange: this.handleTropismChange.bind(this),
      onCompetitionChange: this.handleCompetitionChange.bind(this),
      onSetWaterSource: this.handleSetWaterSource.bind(this),
      onLifecycleSpeedChange: this.handleLifecycleSpeedChange.bind(this),
    });

    this.setupWorker();
    this.setupRenderer();
    this.setupTimelineListener();
    this.setupCanvasClickHandler(canvas);
    this.updateStatus();

    this.addInitialPlants();
  }

  private setupWorker(): void {
    this.worker.onmessage = (e: MessageEvent<WorkerMessage>) => {
      const data = e.data;

      if (data.type === 'progress') {
        this.uiPanel.updateProgress(data.progress);
      } else if (data.type === 'result') {
        this.handlePlantGenerated(data);
      } else if ((data as any).type === 'error') {
        console.error('Worker error:', (data as any).error);
        this.uiPanel.showProgress(false);
        this.isGenerating = false;
      }
    };

    this.worker.onerror = (error) => {
      console.error('Worker error:', error);
      this.uiPanel.showProgress(false);
      this.isGenerating = false;
    };
  }

  private setupRenderer(): void {
    this.renderer.setLightIntensity(this.environmentSystem.getParam('light'));

    window.addEventListener('resize', () => {
      this.renderer.resize();
    });
  }

  private setupTimelineListener(): void {
    const listener: TimelineListener = {
      onTimeChange: (time: number, normalized: number) => {
        this.uiPanel.updateTimeline(
          time,
          normalized,
          this.timelineSystem.getCurrentSeason(),
          this.timelineSystem.isPlaying()
        );
        this.syncPlantAgesToTimeline();
      },
      onPlayStateChange: (isPlaying: boolean) => {
        this.uiPanel.setTimelinePlaying(isPlaying);
      },
      onSeasonChange: (season: Season) => {
        this.renderer.getSeasonSystem().setSeason(season);
      },
    };
    this.timelineSystem.subscribe(listener);
  }

  private setupCanvasClickHandler(canvas: HTMLCanvasElement): void {
    canvas.addEventListener('click', (e) => {
      if (this.isSettingWaterSource) {
        const pickResult = this.renderer.getScene().pick(e.offsetX, e.offsetY);
        if (pickResult && pickResult.pickedPoint) {
          const point = pickResult.pickedPoint;
          this.tropismSystem.setWaterSource([point.x, 0, point.z]);
          this.isSettingWaterSource = false;
          alert(`Water source set at (${point.x.toFixed(1)}, ${point.z.toFixed(1)})`);
        }
      }
    });
  }

  private addInitialPlants(): void {
    const plants = this.plantManager.addPlantGrid(9, 5);
    plants.forEach((plant) => {
      this.initializePlantVisualization(plant);
    });
    this.updatePlantListUI();
    this.renderer.frameCameraToPlants();
  }

  private initializePlantVisualization(plant: PlantInstance): void {
    const preset = getPreset(plant.presetType);
    this.renderer.createSeedVisualization(plant);
    this.renderer.setSeasonColors(plant.id, preset.seasonColors);
    this.renderer.setWindResistance(plant.id, preset.windResistance);
    this.renderer.setColorModifier(plant.id, [1, 1, 1]);
  }

  private generatePlant(plant: PlantInstance): void {
    if (this.isGenerating) {
      this.pendingGenerations.set(plant.id, this.createGenerateMessage(plant));
      return;
    }

    const message = this.createGenerateMessage(plant);
    this.isGenerating = true;
    this.uiPanel.showProgress(true);
    this.uiPanel.updateProgress(0);
    this.worker.postMessage(message);
  }

  private createGenerateMessage(plant: PlantInstance): WorkerGenerateMessage {
    const preset = getPreset(plant.presetType);
    const envParams = this.environmentSystem.getParams();
    const resourceState = this.resourceCompetitionSystem.getPlantResourceState(plant.id);
    const effectiveEnv = this.plantManager.getPlantEffectiveEnvironment(
      plant.id,
      envParams,
      resourceState
    );

    const tropismBias = this.tropismSystem.getGrowthDirectionModifier(
      plant.position,
      0,
      this.currentIterations
    );

    const ageFactor = this.lifecycleSystem.getIterationModifier(plant);
    const iterations = Math.max(2, Math.floor(this.currentIterations * ageFactor));

    return {
      type: 'generate',
      plantId: plant.id,
      config: {
        ...preset.lsystem,
        iterations,
      },
      environment: effectiveEnv,
      iterations,
      tropismBias,
      ageFactor,
    };
  }

  private handlePlantGenerated(data: WorkerResultMessage): void {
    const targetPlant = this.plantManager.getPlant(data.plantId);

    if (targetPlant) {
      this.plantManager.updatePlantData(targetPlant.id, {
        plantData: data.data,
      });
      this.renderer.createPlantGeometry(targetPlant, data.data);
      this.updatePlantVisualization(targetPlant);
    }

    this.uiPanel.showProgress(false);
    this.isGenerating = false;

    if (this.pendingGenerations.size > 0) {
      const nextEntry = this.pendingGenerations.entries().next();
      if (!nextEntry.done) {
        const [plantId, _message] = nextEntry.value;
        this.pendingGenerations.delete(plantId);
        const plant = this.plantManager.getPlant(plantId);
        if (plant) {
          this.generatePlant(plant);
        }
      }
    }

    this.updatePlantListUI();
  }

  private updatePlantVisualization(plant: PlantInstance): void {
    const colorModifier = this.lifecycleSystem.getColorModifier(plant);
    this.renderer.updatePlantLifecycle(plant, colorModifier);
    this.renderer.setPlantGrowthProgress(plant.id, plant.growthProgress);
    this.renderer.setColorModifier(plant.id, colorModifier);
  }

  private syncPlantAgesToTimeline(): void {
    const normalizedTime = this.timelineSystem.getNormalizedTime();
    const totalAge = normalizedTime * 365;

    this.plantManager.getAllPlants().forEach((plant) => {
      if (plant.isAlive) {
        this.plantManager.updatePlantData(plant.id, { age: totalAge });
      }
    });
  }

  private updatePlantListUI(): void {
    const plants = this.plantManager.getAllPlants();
    const competitionFactors = new Map<string, number>();
    plants.forEach((plant) => {
      competitionFactors.set(
        plant.id,
        this.resourceCompetitionSystem.getCompetitionFactor(plant.id)
      );
    });
    this.uiPanel.updatePlants(plants, competitionFactors);
  }

  private handleEnvironmentChange(params: Partial<EnvironmentParams>): void {
    this.environmentSystem.setParams(params);

    if (params.light !== undefined) {
      this.renderer.setLightIntensity(params.light);
    }

    this.resourceCompetitionSystem.setGlobalResources({
      light: this.environmentSystem.getParam('light'),
      water: this.environmentSystem.getParam('water'),
      nutrients: this.environmentSystem.getParam('nutrients'),
    });

    this.updateStatus();
  }

  private handlePresetChange(preset: PlantPresetType): void {
    this.currentPreset = preset;
  }

  private handleSeasonChange(season: Season): void {
    this.timelineSystem.goToSeason(season);
    this.renderer.getSeasonSystem().setAutoTransition(false);

    const checkboxes = document.querySelectorAll('#auto-season');
    checkboxes.forEach((cb) => (cb as HTMLInputElement).checked = false);
  }

  private handleAutoSeasonChange(enabled: boolean): void {
    this.renderer.getSeasonSystem().setAutoTransition(enabled);
  }

  private handleWindChange(params: Partial<WindParams>): void {
    this.renderer.setWindParams(params);
  }

  private handleIterationsChange(iterations: number): void {
    this.currentIterations = iterations;
  }

  private handleGrowthChange(progress: number): void {
    if (this.selectedPlantId) {
      this.renderer.setPlantGrowthProgress(this.selectedPlantId, progress);
    } else {
      this.plantManager.getAllPlants().forEach((plant) => {
        this.renderer.setPlantGrowthProgress(plant.id, progress);
      });
    }
  }

  private handleRegenerate(): void {
    if (this.selectedPlantId) {
      const plant = this.plantManager.getPlant(this.selectedPlantId);
      if (plant) {
        this.lifecycleSystem.resetPlant(plant);
        this.initializePlantVisualization(plant);
        this.generatePlant(plant);
      }
    } else {
      this.plantManager.getAllPlants().forEach((plant) => {
        this.lifecycleSystem.resetPlant(plant);
        this.initializePlantVisualization(plant);
        this.generatePlant(plant);
      });
    }
    this.updatePlantListUI();
  }

  private handleTimelineScrub(normalizedTime: number): void {
    this.timelineSystem.scrubTo(normalizedTime);
  }

  private handleTimelinePlay(): void {
    this.timelineSystem.play();
  }

  private handleTimelinePause(): void {
    this.timelineSystem.pause();
  }

  private handleTimelineSpeedChange(speed: number): void {
    this.timelineSystem.setPlaybackSpeed(speed);
  }

  private handleTimelineReset(): void {
    this.timelineSystem.stop();
    this.plantManager.resetAllPlants();
    this.plantManager.getAllPlants().forEach((plant) => {
      this.initializePlantVisualization(plant);
    });
    this.resourceCompetitionSystem.clear();
    this.updatePlantListUI();
  }

  private handleAddPlant(presetType?: PlantPresetType): void {
    const plant = this.plantManager.addRandomPlant(presetType || this.currentPreset);
    if (plant) {
      this.initializePlantVisualization(plant);
      this.generatePlant(plant);
      this.updatePlantListUI();
    }
  }

  private handleRemovePlant(plantId: string): void {
    this.renderer.clearPlant(plantId);
    this.plantManager.removePlant(plantId);
    this.resourceCompetitionSystem.removePlant(plantId);
    if (this.selectedPlantId === plantId) {
      this.selectedPlantId = null;
    }
    this.updatePlantListUI();
  }

  private handleAddPlantGrid(): void {
    const plants = this.plantManager.addPlantGrid(9, 5);
    plants.forEach((plant) => {
      this.initializePlantVisualization(plant);
      this.generatePlant(plant);
    });
    this.updatePlantListUI();
    this.renderer.frameCameraToPlants();
  }

  private handleClearAllPlants(): void {
    this.renderer.clearAllPlants();
    this.plantManager.clear();
    this.resourceCompetitionSystem.clear();
    this.selectedPlantId = null;
    this.pendingGenerations.clear();
    this.updatePlantListUI();
  }

  private handleSelectPlant(plantId: string | null): void {
    this.selectedPlantId = plantId;
  }

  private handleTropismChange(params: Partial<TropismParams>): void {
    this.tropismSystem.setParams(params);
  }

  private handleCompetitionChange(params: Partial<ResourceCompetitionParams>): void {
    this.resourceCompetitionSystem.setParams(params);
  }

  private handleSetWaterSource(): void {
    this.isSettingWaterSource = true;
    alert('Click on the ground to set water source position');
  }

  private handleLifecycleSpeedChange(speed: number): void {
    this.lifecycleSpeed = speed;
  }

  private updateStatus(): void {
    const status = this.environmentSystem.getGrowthStatus();
    this.uiPanel.updateGrowthStatus(status.status, status.description);
  }

  private async exportGLB(): Promise<void> {
    try {
      await GLTFExporter.exportPlant(
        this.renderer.getScene(),
        `plants_${Date.now()}`
      );
    } catch (error) {
      console.error('Export failed:', error);
      alert('Export failed. Check console for details.');
    }
  }

  private async exportGLTF(): Promise<void> {
    try {
      await GLTFExporter.exportGLTF(
        this.renderer.getScene(),
        `plants_${Date.now()}`
      );
    } catch (error) {
      console.error('Export failed:', error);
      alert('Export failed. Check console for details.');
    }
  }

  start(): void {
    const animate = (time: number) => {
      const deltaTime = this.lastTime ? (time - this.lastTime) / 1000 : 0.016;
      this.lastTime = time;

      this.timelineSystem.update(deltaTime);

      const timelineDelta = deltaTime * this.lifecycleSpeed * this.timelineSystem.getPlaybackSpeed();

      const plants = this.plantManager.getAllPlants();
      this.resourceCompetitionSystem.update(plants, timelineDelta);

      const envParams = this.environmentSystem.getParams();
      plants.forEach((plant) => {
        if (plant.isAlive) {
          const competitionFactor = this.resourceCompetitionSystem.getCompetitionFactor(plant.id);
          const resourceState = this.resourceCompetitionSystem.getPlantResourceState(plant.id);
          const effectiveEnv = this.plantManager.getPlantEffectiveEnvironment(
            plant.id,
            envParams,
            resourceState
          );

          this.lifecycleSystem.updatePlant(plant, effectiveEnv, competitionFactor, timelineDelta);
          this.updatePlantVisualization(plant);

          if (plant.lifecycleStage !== 'seed' && !plant.plantData && !this.pendingGenerations.has(plant.id)) {
            this.generatePlant(plant);
          }
        }
      });

      const sunDir = this.renderer.getSunDirection();
      this.tropismSystem.setLightDirection([sunDir.x, sunDir.y, sunDir.z]);

      this.renderer.update(deltaTime);

      if (Math.floor(time / 500) !== Math.floor((time - deltaTime * 1000) / 500)) {
        this.updatePlantListUI();
        this.updateStatus();
      }

      requestAnimationFrame(animate);
    };

    requestAnimationFrame(animate);
  }

  dispose(): void {
    this.worker.terminate();
    this.renderer.dispose();
  }
}
