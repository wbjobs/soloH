import type { PlantPreset, PlantPresetType } from '../types';

export const plantPresets: Record<PlantPresetType, PlantPreset> = {
  tree: {
    name: 'Tree',
    type: 'tree',
    lsystem: {
      axiom: 'X',
      rules: [
        {
          predecessor: 'X',
          successors: [
            { string: 'F-[[X]+X]+F[+FX]-X', probability: 0.7 },
            { string: 'F[+X][-X]FX', probability: 0.3 }
          ]
        },
        {
          predecessor: 'F',
          successors: [
            { string: 'FF', probability: 0.8 },
            { string: 'F[+F]F[-F]F', probability: 0.2 }
          ]
        }
      ],
      angle: 25.7,
      stepLength: 0.5,
      trunkRadius: 0.15,
      leafSize: 0.8,
      randomness: 0.3
    },
    seasonColors: {
      spring: [0.7, 0.9, 0.4],
      summer: [0.2, 0.6, 0.2],
      autumn: [0.9, 0.5, 0.1],
      winter: [0.6, 0.6, 0.5]
    },
    windResistance: 0.6,
    lifecycle: {
      totalLifespan: 365,
      seedDuration: 5,
      germinationDuration: 10,
      seedlingDuration: 45,
      juvenileDuration: 120,
      matureDuration: 150,
      senescentDuration: 30,
      dyingDuration: 5
    },
    rootCompetitionRadius: 3,
    crownCompetitionRadius: 4
  },

  fern: {
    name: 'Fern',
    type: 'fern',
    lsystem: {
      axiom: 'X',
      rules: [
        {
          predecessor: 'X',
          successors: [
            { string: 'F+[[X]-X]-F[-FX]+X', probability: 0.6 },
            { string: 'F[+X]F[-X]+X', probability: 0.4 }
          ]
        },
        {
          predecessor: 'F',
          successors: [
            { string: 'FF', probability: 0.9 },
            { string: 'F', probability: 0.1 }
          ]
        }
      ],
      angle: 22.5,
      stepLength: 0.3,
      trunkRadius: 0.05,
      leafSize: 0.4,
      randomness: 0.2
    },
    seasonColors: {
      spring: [0.5, 0.8, 0.3],
      summer: [0.1, 0.5, 0.1],
      autumn: [0.7, 0.6, 0.2],
      winter: [0.4, 0.4, 0.3]
    },
    windResistance: 0.4,
    lifecycle: {
      totalLifespan: 180,
      seedDuration: 2,
      germinationDuration: 5,
      seedlingDuration: 20,
      juvenileDuration: 50,
      matureDuration: 80,
      senescentDuration: 20,
      dyingDuration: 3
    },
    rootCompetitionRadius: 1.5,
    crownCompetitionRadius: 2
  },

  vine: {
    name: 'Vine',
    type: 'vine',
    lsystem: {
      axiom: 'F',
      rules: [
        {
          predecessor: 'F',
          successors: [
            { string: 'F[+F]F[-F][F]', probability: 0.5 },
            { string: 'F[+F[+F]]F[-F]', probability: 0.3 },
            { string: 'FF-[-F+F+F]+[+F-F-F]', probability: 0.2 }
          ]
        }
      ],
      angle: 20,
      stepLength: 0.25,
      trunkRadius: 0.04,
      leafSize: 0.35,
      randomness: 0.4
    },
    seasonColors: {
      spring: [0.6, 0.85, 0.35],
      summer: [0.15, 0.55, 0.15],
      autumn: [0.8, 0.45, 0.15],
      winter: [0.5, 0.5, 0.4]
    },
    windResistance: 0.3,
    lifecycle: {
      totalLifespan: 120,
      seedDuration: 2,
      germinationDuration: 4,
      seedlingDuration: 15,
      juvenileDuration: 35,
      matureDuration: 50,
      senescentDuration: 12,
      dyingDuration: 2
    },
    rootCompetitionRadius: 1,
    crownCompetitionRadius: 1.5
  }
};

export function getPreset(type: PlantPresetType): PlantPreset {
  return plantPresets[type];
}

export function getAllPresets(): PlantPreset[] {
  return Object.values(plantPresets);
}
