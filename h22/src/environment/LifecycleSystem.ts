import type { LifecycleStage, LifecycleConfig, PlantInstance, EnvironmentParams } from '../types';

export class LifecycleSystem {
  private config: LifecycleConfig = {
    totalLifespan: 365,
    seedDuration: 3,
    germinationDuration: 7,
    seedlingDuration: 30,
    juvenileDuration: 90,
    matureDuration: 180,
    senescentDuration: 45,
    dyingDuration: 10
  };

  private stageOrder: LifecycleStage[] = [
    'seed', 'germination', 'seedling', 'juvenile', 'mature', 'senescent', 'dying', 'dead'
  ];

  setConfig(config: Partial<LifecycleConfig>): void {
    this.config = { ...this.config, ...config };
  }

  getConfig(): LifecycleConfig {
    return { ...this.config };
  }

  updatePlant(plant: PlantInstance, environment: EnvironmentParams, competitionFactor: number, deltaTime: number): void {
    if (!plant.isAlive) return;

    const normalizedAge = this.getNormalizedAge(plant.age);
    const currentStageIndex = this.stageOrder.indexOf(plant.lifecycleStage);
    
    if (normalizedAge >= 1 && currentStageIndex < this.stageOrder.length - 1) {
      this.advanceStage(plant);
    }

    this.updateHealth(plant, environment, competitionFactor, deltaTime);
    this.updateGrowthProgress(plant);

    if (plant.health <= 0) {
      this.killPlant(plant);
    }
  }

  getNormalizedAge(age: number): number {
    const stageDurations = this.getStageDurations();
    let cumulative = 0;
    
    for (let i = 0; i < stageDurations.length - 1; i++) {
      cumulative += stageDurations[i];
      if (age < cumulative) {
        const prevCumulative = cumulative - stageDurations[i];
        return (prevCumulative + (age - prevCumulative)) / this.config.totalLifespan;
      }
    }
    
    return 1;
  }

  getStageFromAge(age: number): LifecycleStage {
    const stageDurations = this.getStageDurations();
    let cumulative = 0;
    
    for (let i = 0; i < this.stageOrder.length; i++) {
      cumulative += stageDurations[i];
      if (age < cumulative) {
        return this.stageOrder[i];
      }
    }
    
    return 'dead';
  }

  getStageProgress(plant: PlantInstance): number {
    const stageDurations = this.getStageDurations();
    const currentStageIndex = this.stageOrder.indexOf(plant.lifecycleStage);
    
    let cumulative = 0;
    for (let i = 0; i < currentStageIndex; i++) {
      cumulative += stageDurations[i];
    }
    
    const stageAge = plant.age - cumulative;
    const stageDuration = stageDurations[currentStageIndex];
    
    return Math.max(0, Math.min(1, stageAge / stageDuration));
  }

  getStageScale(plant: PlantInstance): number {
    const stage = plant.lifecycleStage;
    const progress = this.getStageProgress(plant);
    
    switch (stage) {
      case 'seed':
        return 0.02;
      case 'germination':
        return 0.02 + progress * 0.08;
      case 'seedling':
        return 0.1 + progress * 0.2;
      case 'juvenile':
        return 0.3 + progress * 0.5;
      case 'mature':
        return 0.8 + progress * 0.2;
      case 'senescent':
        return 1 - progress * 0.1;
      case 'dying':
        return 0.9 - progress * 0.3;
      case 'dead':
        return 0.6;
      default:
        return 1;
    }
  }

  getColorModifier(plant: PlantInstance): [number, number, number] {
    const stage = plant.lifecycleStage;
    const health = plant.health;
    
    switch (stage) {
      case 'seed':
        return [0.8, 0.6, 0.4];
      case 'germination':
        return [0.7, 0.85, 0.4];
      case 'seedling':
        return [0.6, 1, 0.5];
      case 'juvenile':
        return [0.9 + health * 0.1, 1, 0.9 + health * 0.1];
      case 'mature':
        return [1, 1, 1];
      case 'senescent':
        return [1.2 - health * 0.2, 0.8 + health * 0.2, 0.5 + health * 0.3];
      case 'dying':
        return [0.8, 0.5, 0.3];
      case 'dead':
        return [0.5, 0.4, 0.3];
      default:
        return [1, 1, 1];
    }
  }

  getIterationModifier(plant: PlantInstance): number {
    const stage = plant.lifecycleStage;
    const progress = this.getStageProgress(plant);
    
    switch (stage) {
      case 'seed':
        return 0;
      case 'germination':
        return progress * 0.5;
      case 'seedling':
        return 0.5 + progress * 0.5;
      case 'juvenile':
        return 1 + progress * 0.5;
      case 'mature':
        return 1.5 + progress * 0.5;
      case 'senescent':
        return 2 - progress * 0.3;
      case 'dying':
        return 1.7 - progress * 0.5;
      case 'dead':
        return 1;
      default:
        return 1;
    }
  }

  private advanceStage(plant: PlantInstance): void {
    const currentIndex = this.stageOrder.indexOf(plant.lifecycleStage);
    if (currentIndex < this.stageOrder.length - 1) {
      plant.lifecycleStage = this.stageOrder[currentIndex + 1];
      
      if (plant.lifecycleStage === 'dead') {
        plant.isAlive = false;
      }
    }
  }

  private updateHealth(plant: PlantInstance, environment: EnvironmentParams, competitionFactor: number, deltaTime: number): void {
    const envAvg = (environment.light + environment.water + environment.nutrients + environment.temperature) / 4;
    
    const stage = plant.lifecycleStage;
    let recoveryRate = 0.01;
    let decayRate = 0.005;
    
    if (stage === 'germination' || stage === 'seedling') {
      recoveryRate = 0.02;
      decayRate = 0.01;
    } else if (stage === 'mature') {
      recoveryRate = 0.015;
      decayRate = 0.003;
    } else if (stage === 'senescent' || stage === 'dying') {
      recoveryRate = 0.002;
      decayRate = 0.02;
    }
    
    const tempFactor = 1 - Math.abs(environment.temperature - 0.6) * 0.5;
    const healthChange = (envAvg * recoveryRate * tempFactor - decayRate) * deltaTime * 60;
    
    plant.health = Math.max(0, Math.min(1, plant.health + healthChange * competitionFactor));
  }

  private updateGrowthProgress(plant: PlantInstance): void {
    const stageScale = this.getStageScale(plant);
    const healthFactor = 0.5 + plant.health * 0.5;
    
    plant.growthProgress = stageScale * healthFactor;
    
    const baseRootRadius = this.getBaseRootRadius(plant.presetType);
    const baseCrownRadius = this.getBaseCrownRadius(plant.presetType);
    const baseHeight = this.getBaseHeight(plant.presetType);
    
    plant.rootRadius = baseRootRadius * plant.growthProgress;
    plant.crownRadius = baseCrownRadius * plant.growthProgress;
    plant.height = baseHeight * plant.growthProgress;
  }

  private killPlant(plant: PlantInstance): void {
    plant.lifecycleStage = 'dead';
    plant.isAlive = false;
    plant.health = 0;
  }

  private getStageDurations(): number[] {
    return [
      this.config.seedDuration,
      this.config.germinationDuration,
      this.config.seedlingDuration,
      this.config.juvenileDuration,
      this.config.matureDuration,
      this.config.senescentDuration,
      this.config.dyingDuration,
      0
    ];
  }

  private getBaseRootRadius(presetType: string): number {
    switch (presetType) {
      case 'tree': return 3;
      case 'fern': return 1.5;
      case 'vine': return 1;
      default: return 2;
    }
  }

  private getBaseCrownRadius(presetType: string): number {
    switch (presetType) {
      case 'tree': return 4;
      case 'fern': return 2;
      case 'vine': return 1.5;
      default: return 2.5;
    }
  }

  private getBaseHeight(presetType: string): number {
    switch (presetType) {
      case 'tree': return 8;
      case 'fern': return 2;
      case 'vine': return 3;
      default: return 4;
    }
  }

  resetPlant(plant: PlantInstance): void {
    plant.age = 0;
    plant.health = 0.8;
    plant.growthProgress = 0;
    plant.lifecycleStage = 'seed';
    plant.isAlive = true;
    plant.height = 0;
    plant.rootRadius = 0.1;
    plant.crownRadius = 0.1;
  }

  getStageName(stage: LifecycleStage): string {
    const names: Record<LifecycleStage, string> = {
      seed: '🌰 Seed',
      germination: '🌱 Germination',
      seedling: '🌿 Seedling',
      juvenile: '🌳 Juvenile',
      mature: '🌲 Mature',
      senescent: '🍂 Senescent',
      dying: '💀 Dying',
      dead: '⚰️ Dead'
    };
    return names[stage];
  }
}
