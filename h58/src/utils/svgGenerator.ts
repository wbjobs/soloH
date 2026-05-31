import { 
  Stroke, 
  Point, 
  GeneratedCharacter, 
  RenderParameters,
  LayoutParameters,
  SealConfig,
  SignatureConfig,
  RubbingEffect
} from '../types';
import { 
  calculateLayout, 
  generateSealSVG, 
  generateSignatureSVG, 
  generateRubbingFilterSVG,
  getLayoutBackground,
  getInkColor
} from './layoutUtils';

export function strokeToPath(stroke: Stroke, scale: number = 1): string {
  if (stroke.points.length === 0) return '';
  
  const points = stroke.points;
  let path = `M ${points[0].x * scale} ${points[0].y * scale}`;
  
  if (points.length === 1) return path;
  
  if (points.length === 2) {
    path += ` L ${points[1].x * scale} ${points[1].y * scale}`;
    return path;
  }
  
  for (let i = 1; i < points.length - 1; i++) {
    const xc = (points[i].x + points[i + 1].x) / 2 * scale;
    const yc = (points[i].y + points[i + 1].y) / 2 * scale;
    path += ` Q ${points[i].x * scale} ${points[i].y * scale} ${xc} ${yc}`;
  }
  
  const last = points[points.length - 1];
  path += ` L ${last.x * scale} ${last.y * scale}`;
  
  return path;
}

export function strokeToVariableWidthPath(
  stroke: Stroke,
  scale: number = 1
): string {
  if (stroke.points.length < 2) return '';
  
  const points = stroke.points;
  const thickness = stroke.thickness;
  
  const leftPoints: Point[] = [];
  const rightPoints: Point[] = [];
  
  for (let i = 0; i < points.length; i++) {
    const p = points[i];
    const t = thickness[i] * scale * 0.5;
    
    let angle: number;
    if (i === 0) {
      const next = points[i + 1];
      angle = Math.atan2(next.y - p.y, next.x - p.x);
    } else if (i === points.length - 1) {
      const prev = points[i - 1];
      angle = Math.atan2(p.y - prev.y, p.x - prev.x);
    } else {
      const prev = points[i - 1];
      const next = points[i + 1];
      angle = Math.atan2(next.y - prev.y, next.x - prev.x);
    }
    
    const perpAngle = angle + Math.PI / 2;
    const cos = Math.cos(perpAngle);
    const sin = Math.sin(perpAngle);
    
    leftPoints.push({
      x: p.x * scale + cos * t,
      y: p.y * scale + sin * t
    });
    rightPoints.unshift({
      x: p.x * scale - cos * t,
      y: p.y * scale - sin * t
    });
  }
  
  let path = `M ${leftPoints[0].x} ${leftPoints[0].y}`;
  
  for (let i = 1; i < leftPoints.length - 1; i++) {
    const xc = (leftPoints[i].x + leftPoints[i + 1].x) / 2;
    const yc = (leftPoints[i].y + leftPoints[i + 1].y) / 2;
    path += ` Q ${leftPoints[i].x} ${leftPoints[i].y} ${xc} ${yc}`;
  }
  path += ` L ${leftPoints[leftPoints.length - 1].x} ${leftPoints[leftPoints.length - 1].y}`;
  
  for (let i = 0; i < rightPoints.length - 1; i++) {
    const xc = (rightPoints[i].x + rightPoints[i + 1].x) / 2;
    const yc = (rightPoints[i].y + rightPoints[i + 1].y) / 2;
    path += ` Q ${rightPoints[i].x} ${rightPoints[i].y} ${xc} ${yc}`;
  }
  path += ` L ${rightPoints[rightPoints.length - 1].x} ${rightPoints[rightPoints.length - 1].y}`;
  
  path += ' Z';
  
  return path;
}

export function generateAnimatedStrokeSVG(
  stroke: Stroke,
  width: number,
  height: number,
  duration: number = 1,
  delay: number = 0,
  color: string = '#1a1a1a',
  useVariableWidth: boolean = true
): string {
  const scale = 1;
  
  let pathData: string;
  let strokeWidth = stroke.thickness[0] * scale || 4;
  
  if (useVariableWidth) {
    pathData = strokeToVariableWidthPath(stroke, scale);
  } else {
    pathData = strokeToPath(stroke, scale);
  }
  
  const pathId = `path-${stroke.id}`;
  const totalLength = calculatePathLength(stroke.points) * scale;
  
  const animId = `anim-${stroke.id}`;
  
  if (useVariableWidth) {
    return `
    <path d="${pathData}" fill="${color}" opacity="0">
      <animate
        id="${animId}"
        attributeName="opacity"
        from="0"
        to="1"
        dur="${duration}s"
        begin="${delay}s"
        fill="freeze"
      />
    </path>
    `;
  } else {
    return `
    <path
      id="${pathId}"
      d="${pathData}"
      fill="none"
      stroke="${color}"
      stroke-width="${strokeWidth}"
      stroke-linecap="round"
      stroke-linejoin="round"
      stroke-dasharray="${totalLength}"
      stroke-dashoffset="${totalLength}"
    >
      <animate
        id="${animId}"
        attributeName="stroke-dashoffset"
        from="${totalLength}"
        to="0"
        dur="${duration}s"
        begin="${delay}s"
        fill="freeze"
      />
    </path>
    `;
  }
}

export function generateCharacterSVG(
  strokes: Stroke[],
  width: number = 200,
  height: number = 200,
  parameters?: RenderParameters,
  animated: boolean = true,
  color: string = '#1a1a1a',
  rubbing?: RubbingEffect
): string {
  const baseSpeed = parameters ? (100 - parameters.speed) / 50 : 1;
  const inkColor = rubbing ? getInkColor(rubbing, color) : color;
  const bgColor = rubbing ? getLayoutBackground(width, height, rubbing) : '#f5f0e6';
  
  let paths = '';
  let totalDelay = 0;
  
  for (const stroke of strokes) {
    const strokeDuration = (stroke.points.length / 30) * baseSpeed;
    const animatedStroke = generateAnimatedStrokeSVG(
      stroke,
      width,
      height,
      animated ? strokeDuration : 0.001,
      animated ? totalDelay : 0,
      inkColor,
      parameters ? parameters.flyingWhite < 50 : true
    );
    paths += animatedStroke;
    totalDelay += animated ? strokeDuration * 0.3 : 0;
  }
  
  const filter = rubbing ? generateRubbingFilterSVG(rubbing) : '';
  const filterAttr = rubbing && rubbing.enabled ? 'filter="url(#rubbing-effect)"' : '';
  
  return `
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${height}" width="${width}" height="${height}">
  <defs>
    ${filter}
  </defs>
  <g ${filterAttr}>
    <rect width="100%" height="100%" fill="${bgColor}"/>
    ${paths}
  </g>
</svg>
  `.trim();
}

export function generateFullTextSVG(
  characters: GeneratedCharacter[],
  charWidth: number = 200,
  charHeight: number = 200,
  animated: boolean = true,
  layout?: LayoutParameters,
  seal?: SealConfig,
  signature?: SignatureConfig,
  rubbing?: RubbingEffect
): string {
  const actualLayout = layout || {
    charSpacing: 20,
    lineSpacing: 30,
    scatterAmount: 0,
    direction: 'horizontal',
    alignment: 'left',
    charsPerLine: 10
  };
  
  const { positions, totalWidth, totalHeight } = calculateLayout(
    characters,
    charWidth,
    actualLayout
  );
  
  const padding = 40;
  const finalWidth = Math.ceil(totalWidth + padding * 2);
  const finalHeight = Math.ceil(totalHeight + padding * 2 + (signature?.enabled || seal?.enabled ? 80 : 0));
  
  const bgColor = rubbing ? getLayoutBackground(finalWidth, finalHeight, rubbing) : '#f5f0e6';
  const inkColor = rubbing ? getInkColor(rubbing, '#1a1a1a') : '#1a1a1a';
  
  let content = '';
  let currentDelay = 0;
  const filter = rubbing ? generateRubbingFilterSVG(rubbing) : '';
  const filterAttr = rubbing && rubbing.enabled ? 'filter="url(#rubbing-effect)"' : '';
  
  for (let i = 0; i < characters.length; i++) {
    const char = characters[i];
    const pos = positions[i];
    
    const charSVG = generateCharacterSVG(
      char.strokes,
      charWidth,
      charHeight,
      undefined,
      animated,
      inkColor,
      undefined
    );
    
    let charContent = charSVG
      .replace(/<svg[^>]*>|<\/svg>/g, '')
      .replace(/<defs>[\s\S]*?<\/defs>/g, '')
      .replace(/<g[^>]*>|<\/g>/g, '')
      .replace(/<rect[^/]*\/>/, '')
      .trim();
    
    charContent = charContent.replace(
      /begin="([\d.]+)s"/g,
      (match, delay) => `begin="${parseFloat(delay) + currentDelay}s"`
    );
    
    const cx = charWidth / 2;
    const cy = charHeight / 2;
    const tx = pos.x + padding;
    const ty = pos.y + padding;
    
    const transform = `translate(${tx}, ${ty}) rotate(${pos.rotation * 180 / Math.PI} ${cx} ${cy}) scale(${pos.scale})`;
    content += `<g transform="${transform}">${charContent}</g>`;
    
    const strokeCount = char.strokes.length;
    currentDelay += strokeCount * 0.2;
  }
  
  let signatureContent = '';
  let sealContent = '';
  
  if (signature?.enabled && signature.text) {
    const sigSVG = generateSignatureSVG({
      ...signature,
      color: inkColor
    });
    
    const sigContent = sigSVG
      .replace(/<svg[^>]*>|<\/svg>/g, '')
      .trim();
    
    const sigX = (finalWidth * signature.positionX) / 100;
    const sigY = finalHeight - 60 + (signature.positionY - 75) * 0.5;
    
    signatureContent = `<g transform="translate(${sigX}, ${sigY})">${sigContent}</g>`;
  }
  
  if (seal?.enabled && seal.text) {
    const sealSVG = generateSealSVG(seal);
    
    const sealContentInner = sealSVG
      .replace(/<svg[^>]*>|<\/svg>/g, '')
      .trim();
    
    const sealX = (finalWidth * seal.positionX) / 100 - seal.size / 2;
    const sealY = finalHeight - 80 + (seal.positionY - 90) * 0.5;
    
    sealContent = `<g transform="translate(${sealX}, ${sealY})">${sealContentInner}</g>`;
  }
  
  const paperTexture = rubbing?.paperTexture && rubbing.enabled
    ? `
    <filter id="paper-texture">
      <feTurbulence type="fractalNoise" baseFrequency="0.04" numOctaves="2" seed="1"/>
      <feColorMatrix type="matrix" values="
        0 0 0 0 0.83
        0 0 0 0 0.79
        0 0 0 0 0.72
        0 0 0 0.1 0
      "/>
    </filter>
    <rect width="100%" height="100%" filter="url(#paper-texture)" opacity="0.3"/>
  ` : '';
  
  return `
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${finalWidth} ${finalHeight}" width="${finalWidth}" height="${finalHeight}">
  <defs>
    ${filter}
    ${paperTexture}
  </defs>
  <g ${filterAttr}>
    <rect width="100%" height="100%" fill="${bgColor}"/>
    ${content}
    ${signatureContent}
    ${sealContent}
  </g>
</svg>
  `.trim();
}

export function downloadSVG(svgContent: string, filename: string = 'handwriting.svg'): void {
  const blob = new Blob([svgContent], { type: 'image/svg+xml' });
  const url = URL.createObjectURL(blob);
  
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export function copySVGToClipboard(svgContent: string): Promise<void> {
  return navigator.clipboard.writeText(svgContent);
}

function calculatePathLength(points: Point[]): number {
  let length = 0;
  for (let i = 1; i < points.length; i++) {
    const dx = points[i].x - points[i - 1].x;
    const dy = points[i].y - points[i - 1].y;
    length += Math.sqrt(dx * dx + dy * dy);
  }
  return length;
}

export function generateStaticSVG(
  strokes: Stroke[],
  width: number = 200,
  height: number = 200,
  color: string = '#1a1a1a'
): string {
  const scale = 1;
  
  let paths = '';
  for (const stroke of strokes) {
    const pathData = strokeToVariableWidthPath(stroke, scale);
    paths += `<path d="${pathData}" fill="${color}"/>`;
  }
  
  return `
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${height}" width="${width}" height="${height}">
  <rect width="100%" height="100%" fill="#f5f0e6"/>
  ${paths}
</svg>
  `.trim();
}
