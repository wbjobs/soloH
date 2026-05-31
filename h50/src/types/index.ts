export type ComponentType = 'finger' | 'string' | 'hui' | 'decor';

export interface BBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface LegacyBBox {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface JianziComponent {
  id: string;
  type: ComponentType;
  label: string;
  confidence: number;
  bbox: BBox;
}

export interface JianziComponents {
  finger: string;
  string: string;
  hui: string;
}

export interface Jianzi {
  id: string;
  bbox: BBox;
  components: JianziComponents;
  confidence: number;
  gongche?: string;
  description?: string;
  isPlaying?: boolean;
  recognized?: boolean;
  technique?: string;
  string?: string;
  hui?: string;
  midi?: number;
  duration?: number;
}

export interface LegacyJianzi {
  id: string;
  bbox: BBox;
  components: JianziComponent[];
  gongche: string;
  description: string;
  confidence: number;
  isPlaying: boolean;
}

export interface DetectionResult {
  imageId: string;
  jianziList: Jianzi[];
  processingTime: number;
}

export interface AudioSynthesisRequest {
  jianziList: Jianzi[];
  tempo: number;
  technique?: string;
}

export interface AudioSynthesisResponse {
  audioUrl: string;
  midiUrl: string;
  duration: number;
}

export interface UploadResponse {
  imageId: string;
  imageUrl: string;
  width: number;
  height: number;
}

export interface PreprocessOptions {
  contrast?: number;
  brightness?: number;
  threshold?: number;
  denoise?: boolean;
  rotation?: number;
}

export interface EditorState {
  zoom: number;
  panX: number;
  panY: number;
  isEditing: boolean;
}

export interface DictionaryItem {
  name: string;
  type?: string;
  description?: string;
  open_note?: number;
  tuning?: string;
  position?: number;
  ratio?: number;
  semitones?: number;
}

export interface DictionaryEntry {
  id: string;
  gongche: string;
  description: string;
  components: string[];
}

export interface Dictionary {
  fingers: Record<string, DictionaryItem>;
  strings: Record<string, DictionaryItem>;
  hui_positions: Record<string, DictionaryItem>;
  gongche_map: Record<string, string>;
}

export type DictionaryList = DictionaryEntry[];

export interface ScoreEditorProps {
  imageUrl: string;
  jianziList: Jianzi[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
}

export interface JianziEditorProps {
  jianzi: Jianzi | null;
  dictionary: Dictionary;
  onUpdate: (id: string, updates: Partial<Jianzi>) => void;
  onClose: () => void;
}

export interface ScoreMetadata {
  title: string;
  composer: string;
  dynasty: string;
  genre: string;
  difficulty: string;
  description: string;
  total_pages: number;
  total_jianzi: number;
  created_at: string;
  updated_at: string;
}

export interface PageInfo {
  page_number: number;
  image_path: string;
  width: number;
  height: number;
  jianzi_count: number;
}

export interface SerializedScore {
  id: string;
  metadata: ScoreMetadata;
  pages: PageInfo[];
  jianzi_sequence: Jianzi[];
  gongche_sequence: any[];
  audio_synthesis_params: {
    tempo: number;
    volume: number;
    reverb: number;
    style: string;
  };
}

export interface ScoreListItem {
  id: string;
  title: string;
  composer: string;
  difficulty: string;
  total_pages: number;
  total_jianzi: number;
  created_at: string;
}

export interface TechniqueFeatures {
  vibrato_rate: number;
  vibrato_depth: number;
  glissando_speed: number;
  harmonic_purity: number;
  attack_sharpness: number;
  sustain_decay: number;
  noise_level: number;
  spectral_centroid: number;
}

export interface NoteDifficulty {
  sequence_id: number;
  technique: string;
  string: string;
  hui: string;
  difficulty_score: number;
  technique_complexity: number;
  physical_difficulty: number;
  explanations: string[];
  features: TechniqueFeatures;
}

export interface DifficultyReport {
  overall: {
    score: number;
    level: string;
    description: string;
  };
  categories: Record<string, number>;
  summary: {
    total_notes: number;
    avg_difficulty: number;
    max_difficulty: number;
    std_difficulty: number;
    technique_variety: number;
    string_change_rate: number;
    techniques_used: string[];
    strings_used: string[];
  };
  recommendations: string[];
  note_details: NoteDifficulty[];
}

export interface GuqinStyle {
  id: string;
  name: string;
  description: string;
  params?: {
    tempo_modulation: number;
    vibrato_intensity: number;
    vibrato_rate: number;
    glissando_smoothness: number;
    harmonic_emphasis: number;
    attack_smoothness: number;
    decay_extension: number;
    reverb_amount: number;
    brightness_correction: number;
    note_gap: number;
    rubato: number;
  };
}

export interface StyleComparisonResult {
  style_id: string;
  style_name: string;
  description: string;
  audio_url: string;
  overall_difficulty: number;
  level: string;
}
