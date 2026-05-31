import type { CrystalMaterial } from '../types';

export const CRYSTAL_DATABASE: CrystalMaterial[] = [
  {
    id: 'linbo3',
    name: '铌酸锂 (LiNbO3)',
    formula: 'LiNbO3',
    sellmeier: {
      ordinary: {
        A1: 4.9048,
        B1: 0.11768,
        A2: 0.11768,
        B2: 0.04750,
        A3: 2.8956,
        B3: 0.04582,
      },
      extraordinary: {
        A1: 4.5820,
        B1: 0.099169,
        A2: 0.099169,
        B2: 0.044432,
        A3: 2.4214,
        B3: 0.043313,
      },
    },
    nonlinearCoefficients: {
      d33: 27.0,
      d31: -4.5,
      d22: 2.1,
    },
    thermoOpticCoefficients: {
      dn_o_dT: 3.2e-5,
      dn_e_dT: 4.2e-5,
    },
    transparencyRange: [350, 5000],
    damageThreshold: 100,
  },
  {
    id: 'mgo-linbo3',
    name: '氧化镁掺杂铌酸锂 (MgO:LiNbO3)',
    formula: 'MgO:LiNbO3',
    sellmeier: {
      ordinary: {
        A1: 4.8762,
        B1: 0.11542,
        A2: 0.09922,
        B2: 0.04676,
        A3: 2.7895,
        B3: 0.04249,
      },
      extraordinary: {
        A1: 4.5469,
        B1: 0.09705,
        A2: 0.08792,
        B2: 0.04341,
        A3: 2.3824,
        B3: 0.04135,
      },
    },
    nonlinearCoefficients: {
      d33: 25.0,
      d31: -4.2,
      d22: 2.0,
    },
    thermoOpticCoefficients: {
      dn_o_dT: 3.0e-5,
      dn_e_dT: 4.0e-5,
    },
    transparencyRange: [350, 5000],
    damageThreshold: 500,
  },
  {
    id: 'ktp',
    name: '磷酸氧钛钾 (KTP)',
    formula: 'KTiOPO4',
    sellmeier: {
      ordinary: {
        A1: 3.0065,
        B1: 0.03901,
        A2: 0.04547,
        B2: 0.04251,
        A3: 0.01327,
        B3: 0.01408,
      },
      extraordinary: {
        A1: 3.0333,
        B1: 0.04154,
        A2: 0.05083,
        B2: 0.04540,
        A3: 0.01586,
        B3: 0.01526,
      },
    },
    nonlinearCoefficients: {
      d33: 16.9,
      d31: 6.5,
      d22: 5.1,
    },
    thermoOpticCoefficients: {
      dn_o_dT: 1.1e-5,
      dn_e_dT: 1.6e-5,
    },
    transparencyRange: [350, 4500],
    damageThreshold: 300,
  },
  {
    id: 'bbo',
    name: '偏硼酸钡 (BBO)',
    formula: 'β-BaB2O4',
    sellmeier: {
      ordinary: {
        A1: 2.7405,
        B1: 0.0184,
        A2: 0.0179,
        B2: 0.0179,
        A3: 0.0155,
        B3: 0.0155,
      },
      extraordinary: {
        A1: 2.3730,
        B1: 0.0128,
        A2: 0.0156,
        B2: 0.0142,
        A3: 0.0182,
        B3: 0.0162,
      },
    },
    nonlinearCoefficients: {
      d33: 5.8,
      d31: 2.7,
      d22: 2.2,
    },
    thermoOpticCoefficients: {
      dn_o_dT: -9.3e-6,
      dn_e_dT: -16.6e-6,
    },
    transparencyRange: [190, 2600],
    damageThreshold: 150,
  },
  {
    id: 'lbo',
    name: '三硼酸锂 (LBO)',
    formula: 'LiB3O5',
    sellmeier: {
      ordinary: {
        A1: 2.4542,
        B1: 0.01125,
        A2: 0.01135,
        B2: 0.01297,
        A3: 0.01245,
        B3: 0.01378,
      },
      extraordinary: {
        A1: 2.4401,
        B1: 0.01096,
        A2: 0.01096,
        B2: 0.01247,
        A3: 0.01061,
        B3: 0.01159,
      },
    },
    nonlinearCoefficients: {
      d33: 2.8,
      d31: 2.5,
      d22: 2.7,
    },
    thermoOpticCoefficients: {
      dn_o_dT: -1.2e-5,
      dn_e_dT: -1.5e-5,
    },
    transparencyRange: [160, 2600],
    damageThreshold: 250,
  },
  {
    id: 'kdp',
    name: '磷酸二氢钾 (KDP)',
    formula: 'KH2PO4',
    sellmeier: {
      ordinary: {
        A1: 2.259276,
        B1: 0.01008956,
        A2: 0.01008956,
        B2: 0.012942625,
        A3: 0.01008956,
        B3: 0.012942625,
      },
      extraordinary: {
        A1: 2.132668,
        B1: 0.008637494,
        A2: 0.008637494,
        B2: 0.012281043,
        A3: 0.008637494,
        B3: 0.012281043,
      },
    },
    nonlinearCoefficients: {
      d33: 0.43,
      d31: 0.25,
      d22: 0.25,
    },
    thermoOpticCoefficients: {
      dn_o_dT: -2.4e-5,
      dn_e_dT: -2.0e-5,
    },
    transparencyRange: [180, 1500],
    damageThreshold: 80,
  },
  {
    id: 'dkdp',
    name: '氘代磷酸二氢钾 (DKDP)',
    formula: 'KD2PO4',
    sellmeier: {
      ordinary: {
        A1: 2.259971,
        B1: 0.01089244,
        A2: 0.01089244,
        B2: 0.01324167,
        A3: 0.01089244,
        B3: 0.01324167,
      },
      extraordinary: {
        A1: 2.129556,
        B1: 0.00914996,
        A2: 0.00914996,
        B2: 0.01255378,
        A3: 0.00914996,
        B3: 0.01255378,
      },
    },
    nonlinearCoefficients: {
      d33: 0.40,
      d31: 0.24,
      d22: 0.24,
    },
    thermoOpticCoefficients: {
      dn_o_dT: -2.2e-5,
      dn_e_dT: -1.8e-5,
    },
    transparencyRange: [200, 2000],
    damageThreshold: 100,
  },
  {
    id: 'ppln',
    name: '周期极化铌酸锂 (PPLN)',
    formula: 'LiNbO3',
    sellmeier: {
      ordinary: {
        A1: 4.9048,
        B1: 0.11768,
        A2: 0.11768,
        B2: 0.04750,
        A3: 2.8956,
        B3: 0.04582,
      },
      extraordinary: {
        A1: 4.5820,
        B1: 0.099169,
        A2: 0.099169,
        B2: 0.044432,
        A3: 2.4214,
        B3: 0.043313,
      },
    },
    nonlinearCoefficients: {
      d33: 27.0,
      d31: -4.5,
      d22: 2.1,
    },
    thermoOpticCoefficients: {
      dn_o_dT: 3.2e-5,
      dn_e_dT: 4.2e-5,
    },
    transparencyRange: [350, 5000],
    damageThreshold: 100,
  },
];

export function getCrystalById(id: string): CrystalMaterial | undefined {
  return CRYSTAL_DATABASE.find(crystal => crystal.id === id);
}
