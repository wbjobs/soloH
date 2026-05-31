import type { PlantInstance, ResourceCompetitionParams, PlantResourceState, ResourceAvailability } from '../types';

export class ResourceCompetitionSystem {
  private params: ResourceCompetitionParams = {
    rootCompetitionWeight: 0.7,
    shadeCompetitionWeight: 0.5,
    resourceDepletionRate: 0.1,
    recoveryRate: 0.05
  };

  private globalResources: ResourceAvailability = {
    light: 1,
    water: 1,
    nutrients: 1
  };

  private plantResourceStates: Map<string, PlantResourceState> = new Map();

  setParams(params: Partial<ResourceCompetitionParams>): void {
    this.params = { ...this.params, ...params };
  }

  getParams(): ResourceCompetitionParams {
    return { ...this.params };
  }

  setGlobalResources(resources: Partial<ResourceAvailability>): void {
    this.globalResources = { ...this.globalResources, ...resources };
  }

  getGlobalResources(): ResourceAvailability {
    return { ...this.globalResources };
  }

  update(plants: PlantInstance[], deltaTime: number): void {
    if (plants.length <= 1) {
      plants.forEach(plant => {
        if (plant.isAlive) {
          this.plantResourceStates.set(plant.id, {
            available: { ...this.globalResources },
            consumed: { light: 0, water: 0, nutrients: 0 },
            competitionFactor: 1
          });
        }
      });
      return;
    }

    const alivePlants = plants.filter(p => p.isAlive);

    this.recoverResources(deltaTime);
    this.calculateRootCompetition(alivePlants);
    this.calculateShadeCompetition(alivePlants);
    this.consumeResources(alivePlants, deltaTime);
  }

  private recoverResources(deltaTime: number): void {
    const recovery = this.params.recoveryRate * deltaTime;
    this.globalResources.light = Math.min(1, this.globalResources.light + recovery * 0.1);
    this.globalResources.water = Math.min(1, this.globalResources.water + recovery);
    this.globalResources.nutrients = Math.min(1, this.globalResources.nutrients + recovery);
  }

  private calculateRootCompetition(plants: PlantInstance[]): void {
    for (let i = 0; i < plants.length; i++) {
      const plantA = plants[i];
      let rootOverlap = 0;

      for (let j = 0; j < plants.length; j++) {
        if (i === j) continue;
        
        const plantB = plants[j];
        const distance = this.horizontalDistance(plantA.position, plantB.position);
        const combinedRadius = plantA.rootRadius + plantB.rootRadius;
        
        if (distance < combinedRadius) {
          const overlap = 1 - (distance / combinedRadius);
          const sizeRatio = plantB.rootRadius / (plantA.rootRadius + plantB.rootRadius);
          rootOverlap += overlap * sizeRatio * plantB.growthProgress;
        }
      }

      const state = this.getOrCreateState(plantA.id);
      const rootImpact = 1 - rootOverlap * this.params.rootCompetitionWeight;
      state.available.water = this.globalResources.water * Math.max(0.1, rootImpact);
      state.available.nutrients = this.globalResources.nutrients * Math.max(0.1, rootImpact);
    }
  }

  private calculateShadeCompetition(plants: PlantInstance[]): void {
    const sortedByHeight = [...plants].sort((a, b) => b.height - a.height);

    for (let i = 0; i < sortedByHeight.length; i++) {
      const plant = sortedByHeight[i];
      let shadeFactor = 0;

      for (let j = 0; j < i; j++) {
        const tallerPlant = sortedByHeight[j];
        if (tallerPlant.height <= plant.height * 1.1) continue;

        const horizontalDist = this.horizontalDistance(plant.position, tallerPlant.position);
        const shadeRadius = tallerPlant.crownRadius * 1.5;
        
        if (horizontalDist < shadeRadius) {
          const heightDiff = tallerPlant.height - plant.height;
          const heightFactor = Math.min(1, heightDiff / tallerPlant.height);
          const distanceFactor = 1 - (horizontalDist / shadeRadius);
          const coverage = tallerPlant.growthProgress * tallerPlant.crownRadius;
          
          shadeFactor += heightFactor * distanceFactor * coverage * this.params.shadeCompetitionWeight;
        }
      }

      const state = this.getOrCreateState(plant.id);
      state.available.light = this.globalResources.light * Math.max(0.1, 1 - shadeFactor);
    }
  }

  private consumeResources(plants: PlantInstance[], deltaTime: number): void {
    const depletion = this.params.resourceDepletionRate * deltaTime;

    for (const plant of plants) {
      const state = this.getOrCreateState(plant.id);
      
      const consumptionRate = plant.growthProgress * plant.health;
      state.consumed.light = state.available.light * consumptionRate * depletion;
      state.consumed.water = state.available.water * consumptionRate * depletion;
      state.consumed.nutrients = state.available.nutrients * consumptionRate * depletion;

      this.globalResources.light = Math.max(0, this.globalResources.light - state.consumed.light * 0.1);
      this.globalResources.water = Math.max(0, this.globalResources.water - state.consumed.water);
      this.globalResources.nutrients = Math.max(0, this.globalResources.nutrients - state.consumed.nutrients);

      state.competitionFactor = this.calculateCompetitionFactor(state);
    }
  }

  private calculateCompetitionFactor(state: PlantResourceState): number {
    const avg = (state.available.light + state.available.water + state.available.nutrients) / 3;
    return Math.max(0.1, Math.min(1, avg));
  }

  private horizontalDistance(a: [number, number, number], b: [number, number, number]): number {
    const dx = a[0] - b[0];
    const dz = a[2] - b[2];
    return Math.sqrt(dx * dx + dz * dz);
  }

  private getOrCreateState(plantId: string): PlantResourceState {
    if (!this.plantResourceStates.has(plantId)) {
      this.plantResourceStates.set(plantId, {
        available: { ...this.globalResources },
        consumed: { light: 0, water: 0, nutrients: 0 },
        competitionFactor: 1
      });
    }
    return this.plantResourceStates.get(plantId)!;
  }

  getPlantResourceState(plantId: string): PlantResourceState | undefined {
    return this.plantResourceStates.get(plantId);
  }

  getEffectiveEnvironment(plantId: string, baseEnv: ResourceAvailability): ResourceAvailability {
    const state = this.plantResourceStates.get(plantId);
    if (!state) return baseEnv;
    
    return {
      light: baseEnv.light * state.available.light,
      water: baseEnv.water * state.available.water,
      nutrients: baseEnv.nutrients * state.available.nutrients
    };
  }

  getCompetitionFactor(plantId: string): number {
    return this.plantResourceStates.get(plantId)?.competitionFactor ?? 1;
  }

  clear(): void {
    this.plantResourceStates.clear();
  }

  removePlant(plantId: string): void {
    this.plantResourceStates.delete(plantId);
  }
}
