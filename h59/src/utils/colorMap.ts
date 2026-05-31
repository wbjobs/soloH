export interface RGB {
  r: number;
  g: number;
  b: number;
}

export const rainbowColormap = (t: number): RGB => {
  t = Math.max(0, Math.min(1, t));

  if (t < 0.2) {
    const f = t / 0.2;
    return { r: 0, g: Math.floor(f * 255), b: 255 };
  } else if (t < 0.4) {
    const f = (t - 0.2) / 0.2;
    return { r: 0, g: 255, b: Math.floor((1 - f) * 255) };
  } else if (t < 0.6) {
    const f = (t - 0.4) / 0.2;
    return { r: Math.floor(f * 255), g: 255, b: 0 };
  } else if (t < 0.8) {
    const f = (t - 0.6) / 0.2;
    return { r: 255, g: Math.floor((1 - f) * 255), b: 0 };
  } else {
    const f = (t - 0.8) / 0.2;
    return { r: 255, g: 0, b: Math.floor(f * 128) };
  }
};

export const viridisColormap = (t: number): RGB => {
  t = Math.max(0, Math.min(1, t));
  const data = [
    [68, 1, 84],
    [72, 35, 116],
    [62, 66, 127],
    [49, 92, 134],
    [38, 115, 137],
    [30, 136, 138],
    [26, 155, 133],
    [35, 174, 121],
    [67, 192, 100],
    [115, 208, 70],
    [173, 220, 42],
    [236, 226, 24],
    [253, 231, 37],
  ];

  const idx = t * (data.length - 1);
  const i = Math.floor(idx);
  const f = idx - i;

  if (i >= data.length - 1) {
    const [r, g, b] = data[data.length - 1];
    return { r, g, b };
  }

  const [r1, g1, b1] = data[i];
  const [r2, g2, b2] = data[i + 1];

  return {
    r: Math.floor(r1 + (r2 - r1) * f),
    g: Math.floor(g1 + (g2 - g1) * f),
    b: Math.floor(b1 + (b2 - b1) * f),
  };
};

export const valueToColor = (
  value: number,
  min: number,
  max: number,
  colormap: 'rainbow' | 'viridis' = 'rainbow'
): string => {
  if (max === min) return '#0000ff';
  const t = (value - min) / (max - min);
  const color = colormap === 'rainbow' ? rainbowColormap(t) : viridisColormap(t);
  return `rgb(${color.r}, ${color.g}, ${color.b})`;
};

export const generateContourLevels = (
  min: number,
  max: number,
  numLevels: number = 10
): number[] => {
  const levels: number[] = [];
  const step = (max - min) / numLevels;
  for (let i = 0; i <= numLevels; i++) {
    levels.push(min + i * step);
  }
  return levels;
};

export const formatScientific = (num: number): string => {
  if (num === 0) return '0';
  if (Math.abs(num) >= 0.01 && Math.abs(num) < 10000) {
    return num.toFixed(4);
  }
  return num.toExponential(2);
};
