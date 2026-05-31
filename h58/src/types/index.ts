export interface Point {
  x: number;
  y: number;
  pressure?: number;
  speed?: number;
}

export interface Stroke {
  id: string;
  points: Point[];
  thickness: number[];
  order: number;
  type: string;
}

export interface StyleFeatures {
  avgThickness: number;
  thicknessVariance: number;
  slantAngle: number;
  speedVariation: number;
  flyingWhite: number;
  smoothness: number;
  strokeLengths: number[];
  strokeDirections: number[];
}

export interface CharacterStyle {
  id: string;
  name: string;
  character: string;
  originalImage: string;
  strokes: Stroke[];
  features: StyleFeatures;
  weight: number;
}

export interface GeneratedCharacter {
  character: string;
  strokes: Stroke[];
  styleId: string;
  svg: string;
}

export interface RenderParameters {
  thickness: number;
  speed: number;
  flyingWhite: number;
}

export interface LayoutParameters {
  charSpacing: number;
  lineSpacing: number;
  scatterAmount: number;
  direction: 'horizontal' | 'vertical';
  alignment: 'left' | 'center' | 'right';
  charsPerLine: number;
}

export interface SealConfig {
  enabled: boolean;
  text: string;
  size: number;
  positionX: number;
  positionY: number;
  style: 'square' | 'circle' | 'oval';
  color: string;
  rotation: number;
  opacity: number;
}

export interface SignatureConfig {
  enabled: boolean;
  text: string;
  fontSize: number;
  positionX: number;
  positionY: number;
  color: string;
  rotation: number;
  style: 'regular' | 'running' | 'cursive';
}

export interface RubbingEffect {
  enabled: boolean;
  invert: boolean;
  mottleIntensity: number;
  edgeRoughness: number;
  paperTexture: boolean;
  contrast: number;
}

export interface AppState {
  samples: CharacterStyle[];
  targetText: string;
  parameters: RenderParameters;
  layout: LayoutParameters;
  seal: SealConfig;
  signature: SignatureConfig;
  rubbing: RubbingEffect;
  generatedCharacters: GeneratedCharacter[];
  isPlaying: boolean;
  currentStrokeIndex: number;
  currentCharacterIndex: number;
  selectedSampleId: string | null;
}

export type NodeType = 'endpoint' | 'junction' | 'normal';

export interface GraphNode {
  x: number;
  y: number;
  type: NodeType;
  neighbors: GraphNode[];
  visited: boolean;
}

export interface ProcessedImage {
  width: number;
  height: number;
  binaryData: Uint8ClampedArray;
  skeletonData: Uint8ClampedArray;
}
