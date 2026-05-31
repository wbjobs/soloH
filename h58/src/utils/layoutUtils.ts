import { 
  GeneratedCharacter, 
  LayoutParameters, 
  SealConfig, 
  SignatureConfig,
  RubbingEffect,
  Stroke,
  Point
} from '../types';

class LayoutPerlinNoise {
  private perm: number[];
  
  constructor(seed: number = 42) {
    this.perm = this.generatePermutation(seed);
  }
  
  private generatePermutation(seed: number): number[] {
    const p: number[] = [];
    for (let i = 0; i < 256; i++) p[i] = i;
    
    let s = seed;
    for (let i = 255; i > 0; i--) {
      s = (s * 16807) % 2147483647;
      const j = s % (i + 1);
      [p[i], p[j]] = [p[j], p[i]];
    }
    return [...p, ...p];
  }
  
  private fade(t: number): number {
    return t * t * t * (t * (t * 6 - 15) + 10);
  }
  
  private lerp(a: number, b: number, t: number): number {
    return a + t * (b - a);
  }
  
  private grad(hash: number, x: number): number {
    return (hash & 1) === 0 ? x : -x;
  }
  
  noise(x: number): number {
    const X = Math.floor(x) & 255;
    x -= Math.floor(x);
    const u = this.fade(x);
    return this.lerp(
      this.grad(this.perm[X], x),
      this.grad(this.perm[X + 1], x - 1),
      u
    );
  }
  
  noise2D(x: number, y: number): number {
    const X = Math.floor(x) & 255;
    const Y = Math.floor(y) & 255;
    x -= Math.floor(x);
    y -= Math.floor(y);
    
    const u = this.fade(x);
    const v = this.fade(y);
    
    const A = this.perm[X] + Y;
    const B = this.perm[X + 1] + Y;
    
    return this.lerp(
      this.lerp(
        this.grad(this.perm[A], x),
        this.grad(this.perm[B], x - 1),
        u
      ),
      this.lerp(
        this.grad(this.perm[A + 1], x),
        this.grad(this.perm[B + 1], x - 1),
        u
      ),
      v
    );
  }
  
  octaveNoise2D(x: number, y: number, octaves: number = 3, persistence: number = 0.5): number {
    let total = 0;
    let freq = 1;
    let amp = 1;
    let max = 0;
    for (let i = 0; i < octaves; i++) {
      total += this.noise2D(x * freq, y * freq) * amp;
      max += amp;
      amp *= persistence;
      freq *= 2;
    }
    return total / max;
  }
}

const layoutNoise = new LayoutPerlinNoise(12345);
const sealNoise = new LayoutPerlinNoise(67890);
const rubbingNoise = new LayoutPerlinNoise(99999);

export interface CharacterPosition {
  x: number;
  y: number;
  rotation: number;
  scale: number;
  lineIndex: number;
  charIndex: number;
}

export function calculateLayout(
  characters: GeneratedCharacter[],
  charSize: number,
  layout: LayoutParameters
): { positions: CharacterPosition[]; totalWidth: number; totalHeight: number; lines: number } {
  const positions: CharacterPosition[] = [];
  const { charSpacing, lineSpacing, scatterAmount, direction, alignment, charsPerLine } = layout;
  
  const effectiveSpacing = charSize + charSpacing;
  const effectiveLineSpacing = charSize + lineSpacing;
  
  let lines: number;
  let chars: number;
  
  if (direction === 'horizontal') {
    lines = Math.ceil(characters.length / charsPerLine);
    chars = charsPerLine;
  } else {
    chars = Math.ceil(characters.length / charsPerLine);
    lines = charsPerLine;
  }
  
  const totalWidth = direction === 'horizontal' 
    ? chars * effectiveSpacing - charSpacing
    : lines * effectiveLineSpacing - lineSpacing;
  
  const totalHeight = direction === 'horizontal'
    ? lines * effectiveLineSpacing - lineSpacing
    : chars * effectiveSpacing - charSpacing;
  
  for (let i = 0; i < characters.length; i++) {
    let lineIndex: number;
    let charIndex: number;
    
    if (direction === 'horizontal') {
      lineIndex = Math.floor(i / charsPerLine);
      charIndex = i % charsPerLine;
    } else {
      lineIndex = charsPerLine - 1 - (i % charsPerLine);
      charIndex = Math.floor(i / charsPerLine);
    }
    
    let x: number;
    let y: number;
    
    if (direction === 'horizontal') {
      const lineCharCount = Math.min(charsPerLine, characters.length - lineIndex * charsPerLine);
      const lineWidth = lineCharCount * effectiveSpacing - charSpacing;
      let lineOffset = 0;
      
      if (alignment === 'center') {
        lineOffset = (totalWidth - lineWidth) / 2;
      } else if (alignment === 'right') {
        lineOffset = totalWidth - lineWidth;
      }
      
      x = lineOffset + charIndex * effectiveSpacing;
      y = lineIndex * effectiveLineSpacing;
    } else {
      const colCharCount = Math.min(charsPerLine, characters.length - charIndex * charsPerLine);
      const colHeight = colCharCount * effectiveSpacing - charSpacing;
      let colOffset = 0;
      
      if (alignment === 'center') {
        colOffset = (totalHeight - colHeight) / 2;
      } else if (alignment === 'right') {
        colOffset = totalHeight - colHeight;
      }
      
      x = lineIndex * effectiveLineSpacing;
      y = colOffset + (charsPerLine - colCharCount) * effectiveSpacing + (i % charsPerLine) * effectiveSpacing;
    }
    
    let rotation = 0;
    let scale = 1;
    
    if (scatterAmount > 0) {
      const noiseSeed = i * 0.1;
      rotation = layoutNoise.noise(noiseSeed) * scatterAmount * 0.03;
      const posNoiseX = layoutNoise.noise(noiseSeed + 100) * scatterAmount * 0.15;
      const posNoiseY = layoutNoise.noise(noiseSeed + 200) * scatterAmount * 0.15;
      x += posNoiseX;
      y += posNoiseY;
      scale = 1 + layoutNoise.noise(noiseSeed + 300) * scatterAmount * 0.003;
    }
    
    positions.push({
      x,
      y,
      rotation,
      scale,
      lineIndex,
      charIndex
    });
  }
  
  return { positions, totalWidth, totalHeight, lines };
}

export function generateSealSVG(seal: SealConfig): string {
  const { text, size, style, color, rotation, opacity } = seal;
  
  let shapePath = '';
  const halfSize = size / 2;
  
  switch (style) {
    case 'circle':
      shapePath = `<circle cx="${halfSize}" cy="${halfSize}" r="${halfSize - 2}" fill="none" stroke="${color}" stroke-width="2"/>`;
      break;
    case 'oval':
      shapePath = `<ellipse cx="${halfSize}" cy="${halfSize}" rx="${halfSize - 2}" ry="${halfSize * 0.7 - 2}" fill="none" stroke="${color}" stroke-width="2"/>`;
      break;
    case 'square':
    default:
      shapePath = `<rect x="1" y="1" width="${size - 2}" height="${size - 2}" fill="none" stroke="${color}" stroke-width="2"/>`;
      break;
  }
  
  const fontSize = Math.max(8, size / (text.length > 2 ? 2.5 : 2));
  const chars = text.split('');
  
  let textContent = '';
  if (chars.length <= 2) {
    textContent = `<text x="${halfSize}" y="${halfSize + fontSize * 0.35}" 
      text-anchor="middle" 
      font-size="${fontSize}" 
      fill="${color}"
      font-family="'Ma Shan Zheng', 'STKaiti', 'KaiTi', serif"
      font-weight="bold">${text}</text>`;
  } else {
    const charsPerLine = Math.ceil(Math.sqrt(chars.length));
    const lines = Math.ceil(chars.length / charsPerLine);
    const lineHeight = fontSize * 1.1;
    const totalTextHeight = lines * lineHeight;
    const startY = halfSize - totalTextHeight / 2 + fontSize * 0.35;
    
    for (let line = 0; line < lines; line++) {
      const lineChars = chars.slice(line * charsPerLine, (line + 1) * charsPerLine);
      const lineText = lineChars.join('');
      const y = startY + line * lineHeight;
      
      textContent += `<text x="${halfSize}" y="${y}" 
        text-anchor="middle" 
        font-size="${fontSize}" 
        fill="${color}"
        font-family="'Ma Shan Zheng', 'STKaiti', 'KaiTi', serif"
        font-weight="bold">${lineText}</text>`;
    }
  }
  
  const defectCount = Math.floor(size / 8);
  let defects = '';
  for (let i = 0; i < defectCount; i++) {
    const nx = sealNoise.noise(i * 0.5) * 0.5 + 0.5;
    const ny = sealNoise.noise(i * 0.5 + 100) * 0.5 + 0.5;
    const defectX = nx * size;
    const defectY = ny * size;
    const defectR = sealNoise.noise(i * 0.5 + 200) * 2 + 1;
    defects += `<circle cx="${defectX}" cy="${defectY}" r="${defectR}" fill="${color}" opacity="0.3"/>`;
  }
  
  return `
    <svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
      <g transform="rotate(${rotation} ${halfSize} ${halfSize})" opacity="${opacity}">
        ${shapePath}
        ${textContent}
        ${defects}
      </g>
    </svg>
  `;
}

export function generateSignatureSVG(signature: SignatureConfig): string {
  const { text, fontSize, color, rotation, style } = signature;
  
  const fontFamily = style === 'cursive' 
    ? "'Ma Shan Zheng', 'STKaiti', 'KaiTi', cursive"
    : style === 'running'
    ? "'ZCOOL XiaoWei', 'STKaiti', 'KaiTi', serif"
    : "'Noto Serif SC', 'SimSun', serif";
  
  const width = text.length * fontSize * 1.2 + 20;
  const height = fontSize * 2;
  
  let textPath = '';
  if (style === 'cursive') {
    let pathD = `M 10 ${height * 0.6}`;
    let x = 10;
    for (let i = 0; i < text.length; i++) {
      const char = text[i];
      const charWidth = fontSize * 1.1;
      const yOffset = Math.sin(i * 0.8) * fontSize * 0.15;
      pathD += ` q ${charWidth * 0.3} ${-fontSize * 0.3 + yOffset}, ${charWidth} ${yOffset}`;
      x += charWidth;
    }
    
    textPath = `
      <path id="signature-path" d="${pathD}" fill="none"/>
      <text fill="${color}" font-family="${fontFamily}" font-size="${fontSize}" font-style="italic">
        <textPath href="#signature-path" startOffset="0">${text}</textPath>
      </text>
    `;
  } else {
    textPath = `<text x="10" y="${height * 0.7}" fill="${color}" font-family="${fontFamily}" font-size="${fontSize}" ${style === 'running' ? 'font-style="italic"' : ''}>${text}</text>`;
  }
  
  return `
    <svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">
      <g transform="rotate(${rotation} 10 ${height * 0.5})">
        ${textPath}
      </g>
    </svg>
  `;
}

export function applyRubbingEffectToCanvas(
  ctx: CanvasRenderingContext2D,
  width: number,
  height: number,
  rubbing: RubbingEffect
): void {
  if (!rubbing.enabled) return;
  
  const imageData = ctx.getImageData(0, 0, width, height);
  const data = imageData.data;
  
  const { invert, mottleIntensity, edgeRoughness, contrast } = rubbing;
  const contrastFactor = (259 * (contrast + 255)) / (255 * (259 - contrast));
  
  for (let i = 0; i < data.length; i += 4) {
    let r = data[i];
    let g = data[i + 1];
    let b = data[i + 2];
    const a = data[i + 3];
    
    if (invert) {
      r = 255 - r;
      g = 255 - g;
      b = 255 - b;
    }
    
    r = contrastFactor * (r - 128) + 128;
    g = contrastFactor * (g - 128) + 128;
    b = contrastFactor * (b - 128) + 128;
    
    const x = (i / 4) % width;
    const y = Math.floor((i / 4) / width);
    
    if (mottleIntensity > 0) {
      const noiseVal = rubbingNoise.octaveNoise2D(x * 0.05, y * 0.05, 3, 0.6);
      const mottle = noiseVal * mottleIntensity * 0.5;
      r += mottle;
      g += mottle;
      b += mottle;
    }
    
    if (edgeRoughness > 0) {
      const edgeNoise = rubbingNoise.octaveNoise2D(x * 0.1, y * 0.1, 2, 0.5);
      const edgeThreshold = 128 + edgeRoughness * 1.28;
      const gray = 0.299 * r + 0.587 * g + 0.114 * b;
      
      if (gray < edgeThreshold && edgeNoise > 0.3) {
        const edgeFade = (edgeThreshold - gray) / edgeThreshold;
        r += edgeFade * edgeRoughness * 0.3;
        g += edgeFade * edgeRoughness * 0.3;
        b += edgeFade * edgeRoughness * 0.3;
      }
    }
    
    data[i] = Math.max(0, Math.min(255, r));
    data[i + 1] = Math.max(0, Math.min(255, g));
    data[i + 2] = Math.max(0, Math.min(255, b));
    data[i + 3] = a;
  }
  
  ctx.putImageData(imageData, 0, 0);
  
  if (rubbing.paperTexture) {
    ctx.save();
    ctx.globalAlpha = 0.1;
    for (let i = 0; i < 500; i++) {
      const x = Math.random() * width;
      const y = Math.random() * height;
      const fiberWidth = Math.random() * 2 + 0.5;
      const fiberHeight = Math.random() * 10 + 2;
      const rotation = Math.random() * Math.PI;
      
      ctx.save();
      ctx.translate(x, y);
      ctx.rotate(rotation);
      ctx.fillStyle = invert ? '#333' : '#d4c9b8';
      ctx.fillRect(-fiberWidth / 2, -fiberHeight / 2, fiberWidth, fiberHeight);
      ctx.restore();
    }
    ctx.restore();
  }
}

export function generateRubbingFilterSVG(rubbing: RubbingEffect): string {
  if (!rubbing.enabled) return '';
  
  const { invert, mottleIntensity, edgeRoughness, contrast } = rubbing;
  
  const colorMatrix = invert 
    ? `
      <feColorMatrix type="matrix" values="
        -1  0  0  0  1
         0 -1  0  0  1
         0  0 -1  0  1
         0  0  0  1  0
      "/>
    ` : '';
  
  const contrastValue = contrast / 100;
  const contrastFilter = contrastValue !== 1
    ? `<feComponentTransfer>
        <feFuncR type="linear" slope="${contrastValue}" intercept="${(1 - contrastValue) * 0.5}"/>
        <feFuncG type="linear" slope="${contrastValue}" intercept="${(1 - contrastValue) * 0.5}"/>
        <feFuncB type="linear" slope="${contrastValue}" intercept="${(1 - contrastValue) * 0.5}"/>
      </feComponentTransfer>`
    : '';
  
  const turbulence = mottleIntensity > 0
    ? `<feTurbulence type="fractalNoise" baseFrequency="0.02" numOctaves="3" seed="5" result="noise"/>
       <feColorMatrix in="noise" type="matrix" values="
         1 0 0 0 0
         0 1 0 0 0
         0 0 1 0 0
         0 0 0 ${mottleIntensity / 200} 0
       " result="mottle"/>
       <feComposite in="SourceGraphic" in2="mottle" operator="arithmetic" k1="0" k2="1" k3="1" k4="0"/>`
    : '';
  
  return `
    <filter id="rubbing-effect" x="0%" y="0%" width="100%" height="100%">
      ${colorMatrix}
      ${contrastFilter}
      ${turbulence}
    </filter>
  `;
}

export function getLayoutBackground(
  width: number,
  height: number,
  rubbing: RubbingEffect
): string {
  if (rubbing.enabled && rubbing.invert) {
    return '#1a1a1a';
  }
  return '#f5f0e6';
}

export function getInkColor(rubbing: RubbingEffect, defaultColor: string = '#1a1a1a'): string {
  if (rubbing.enabled && rubbing.invert) {
    return '#f5f0e6';
  }
  return defaultColor;
}

export function applyScatterToStroke(
  stroke: Stroke,
  scatterAmount: number,
  charIndex: number
): Stroke {
  if (scatterAmount <= 0) return stroke;
  
  const seed = charIndex * 0.1;
  const rotNoise = layoutNoise.noise(seed + 500) * scatterAmount * 0.02;
  const scaleNoise = 1 + layoutNoise.noise(seed + 600) * scatterAmount * 0.002;
  
  const centerX = stroke.points.reduce((sum, p) => sum + p.x, 0) / stroke.points.length;
  const centerY = stroke.points.reduce((sum, p) => sum + p.y, 0) / stroke.points.length;
  
  const cos = Math.cos(rotNoise);
  const sin = Math.sin(rotNoise);
  
  const newPoints = stroke.points.map(p => {
    const dx = p.x - centerX;
    const dy = p.y - centerY;
    return {
      ...p,
      x: centerX + (dx * cos - dy * sin) * scaleNoise,
      y: centerY + (dx * sin + dy * cos) * scaleNoise
    };
  });
  
  return {
    ...stroke,
    points: newPoints
  };
}
