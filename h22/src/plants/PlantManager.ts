import type { PlantInstance, PlantPresetType, EnvironmentParams, ResourceAvailability, LifecycleStage } from '../types';
import { getPreset } from './PlantPresets';

export interface PlantManagerOptions {
  maxPlants?: number;
}

export class PlantManager {
  private plants: Map<string, PlantInstance> = new Map();
  private maxPlants: number;
  private idCounter: number = 0;

  constructor(options: PlantManagerOptions = {}) {
    this.maxPlants = options.maxPlants ?? 20;
  }

  addPlant(
    presetType: PlantPresetType,
    position: [number, number, number] = [0, 0, 0]
  ): PlantInstance | null {
    if (this.plants.size >= this.maxPlants) {
      console.warn(`Maximum number of plants (${this.maxPlants}) reached`);
      return null;
    }

    const preset = getPreset(presetType);
    const id = `plant_${++this.idCounter}`;

    const plant: PlantInstance = {
      id,
      position,
      presetType,
      plantData: null,
      growthProgress: 0,
      age: 0,
      health: 0.8,
      height: 0,
      rootRadius: preset.rootCompetitionRadius * 0.1,
      crownRadius: preset.crownCompetitionRadius * 0.1,
      isAlive: true,
      lifecycleStage: 'seed'
    };

    this.plants.set(id, plant);
    return plant;
  }

  removePlant(plantId: string): boolean {
    return this.plants.delete(plantId);
  }

  getPlant(plantId: string): PlantInstance | undefined {
    return this.plants.get(plantId);
  }

  getAllPlants(): PlantInstance[] {
    return Array.from(this.plants.values());
  }

  getAlivePlants(): PlantInstance[] {
    return this.getAllPlants().filter(p => p.isAlive);
  }

  getPlantsByStage(stage: LifecycleStage): PlantInstance[] {
    return this.getAllPlants().filter(p => p.lifecycleStage === stage);
  }

  updatePlantData(plantId: string, data: Partial<PlantInstance>): boolean {
    const plant = this.plants.get(plantId);
    if (!plant) return false;
    
    Object.assign(plant, data);
    return true;
  }

  setPlantPosition(plantId: string, position: [number, number, number]): boolean {
    return this.updatePlantData(plantId, { position });
  }

  clear(): void {
    this.plants.clear();
  }

  getCount(): number {
    return this.plants.size;
  }

  getAliveCount(): number {
    return this.getAlivePlants().length;
  }

  getAverageGrowth(): number {
    const alive = this.getAlivePlants();
    if (alive.length === 0) return 0;
    return alive.reduce((sum, p) => sum + p.growthProgress, 0) / alive.length;
  }

  getAverageHealth(): number {
    const alive = this.getAlivePlants();
    if (alive.length === 0) return 0;
    return alive.reduce((sum, p) => sum + p.health, 0) / alive.length;
  }

  getPlantEffectiveEnvironment(
    _plantId: string,
    baseEnvironment: EnvironmentParams,
    resourceState?: { available: ResourceAvailability; competitionFactor: number }
  ): EnvironmentParams {
    if (!resourceState) return baseEnvironment;
    
    return {
      light: baseEnvironment.light * resourceState.available.light,
      water: baseEnvironment.water * resourceState.available.water,
      nutrients: baseEnvironment.nutrients * resourceState.available.nutrients,
      temperature: baseEnvironment.temperature * (0.8 + resourceState.competitionFactor * 0.2)
    };
  }

  addRandomPlant(presetType?: PlantPresetType): PlantInstance | null {
    const types: PlantPresetType[] = ['tree', 'fern', 'vine'];
    const type = presetType ?? types[Math.floor(Math.random() * types.length)];
    
    const angle = Math.random() * Math.PI * 2;
    const distance = 2 + Math.random() * 8;
    const position: [number, number, number] = [
      Math.cos(angle) * distance,
      0,
      Math.sin(angle) * distance
    ];
    
    return this.addPlant(type, position);
  }

  addPlantGrid(count: number, spacing: number = 4): PlantInstance[] {
    const plants: PlantInstance[] = [];
    const types: PlantPresetType[] = ['tree', 'fern', 'vine'];
    const gridSize = Math.ceil(Math.sqrt(count));
    
    for (let i = 0; i < count && this.plants.size < this.maxPlants; i++) {
      const row = Math.floor(i / gridSize);
      const col = i % gridSize;
      const offsetX = (col - gridSize / 2) * spacing + (Math.random() - 0.5) * spacing * 0.3;
      const offsetZ = (row - gridSize / 2) * spacing + (Math.random() - 0.5) * spacing * 0.3;
      
      const type = types[Math.floor(Math.random() * types.length)];
      const plant = this.addPlant(type, [offsetX, 0, offsetZ]);
      
      if (plant) plants.push(plant);
    }
    
    return plants;
  }

  resetAllPlants(): void {
    this.plants.forEach(plant => {
      plant.age = 0;
      plant.health = 0.8;
      plant.growthProgress = 0;
      plant.isAlive = true;
      plant.lifecycleStage = 'seed';
      plant.height = 0;
      plant.plantData = null;
      
      const preset = getPreset(plant.presetType);
      plant.rootRadius = preset.rootCompetitionRadius * 0.1;
      plant.crownRadius = preset.crownCompetitionRadius * 0.1;
    });
  }

  removeDeadPlants(): number {
    let removed = 0;
    this.plants.forEach(plant => {
      if (!plant.isAlive) {
        this.plants.delete(plant.id);
        removed++;
      }
    });
    return removed;
  }
}
