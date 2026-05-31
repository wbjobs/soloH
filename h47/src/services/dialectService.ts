import { DialectMapping, DialectConfig, DialectRegion, RecognizedWord, VocabularyItem } from '@/types';
import { VOCABULARY } from '@/data/vocabulary';

const DEFAULT_DIALECT_MAPPINGS: DialectMapping[] = [
  {
    id: 'bj-001',
    dialectName: '北京手语',
    region: 'beijing',
    standardWord: '我',
    dialectWord: '咱',
    pinyin: 'zan',
    featureTemplate: [0.1, 0.2, 0.3],
    category: 'pronoun',
    description: '北京手语中"咱"等同于普通话"我"'
  },
  {
    id: 'bj-002',
    dialectName: '北京手语',
    region: 'beijing',
    standardWord: '很好',
    dialectWord: '倍儿好',
    pinyin: 'bei er hao',
    featureTemplate: [0.2, 0.3, 0.4],
    category: 'adjective',
    description: '北京手语中"倍儿好"表示"非常好"'
  },
  {
    id: 'sh-001',
    dialectName: '上海手语',
    region: 'shanghai',
    standardWord: '你',
    dialectWord: '侬',
    pinyin: 'nong',
    featureTemplate: [0.15, 0.25, 0.35],
    category: 'pronoun',
    description: '上海手语中"侬"等同于普通话"你"'
  },
  {
    id: 'sh-002',
    dialectName: '上海手语',
    region: 'shanghai',
    standardWord: '什么',
    dialectWord: '啥',
    pinyin: 'sha',
    featureTemplate: [0.25, 0.35, 0.45],
    category: 'question',
    description: '上海手语中"啥"等同于普通话"什么"'
  },
  {
    id: 'gz-001',
    dialectName: '广州手语',
    region: 'guangzhou',
    standardWord: '是',
    dialectWord: '系',
    pinyin: 'xi',
    featureTemplate: [0.12, 0.22, 0.32],
    category: 'verb',
    description: '广州手语中"系"等同于普通话"是"'
  },
  {
    id: 'gz-002',
    dialectName: '广州手语',
    region: 'guangzhou',
    standardWord: '不',
    dialectWord: '唔',
    pinyin: 'wu',
    featureTemplate: [0.18, 0.28, 0.38],
    category: 'adverb',
    description: '广州手语中"唔"等同于普通话"不"'
  },
  {
    id: 'hk-001',
    dialectName: '香港手语',
    region: 'hongkong',
    standardWord: '谢谢',
    dialectWord: '多谢',
    pinyin: 'duo xie',
    featureTemplate: [0.22, 0.32, 0.42],
    category: 'phrase',
    description: '香港手语中"多谢"表示感谢'
  },
  {
    id: 'tw-001',
    dialectName: '台湾手语',
    region: 'taiwan',
    standardWord: '吃',
    dialectWord: '食',
    pinyin: 'shi',
    featureTemplate: [0.16, 0.26, 0.36],
    category: 'verb',
    description: '台湾手语中"食"等同于普通话"吃"'
  },
  {
    id: 'cd-001',
    dialectName: '成都手语',
    region: 'chengdu',
    standardWord: '很好',
    dialectWord: '巴适',
    pinyin: 'ba shi',
    featureTemplate: [0.2, 0.3, 0.4],
    category: 'adjective',
    description: '成都手语中"巴适"表示"很好、舒适"'
  },
  {
    id: 'ne-001',
    dialectName: '东北手语',
    region: 'northeast',
    standardWord: '厉害',
    dialectWord: '贼好',
    pinyin: 'zei hao',
    featureTemplate: [0.24, 0.34, 0.44],
    category: 'adjective',
    description: '东北手语中"贼好"表示"非常好"'
  }
];

const DIALECT_REGIONS: Record<DialectRegion, { name: string; description: string }> = {
  'standard': { name: '标准普通话手语', description: '国家通用手语标准' },
  'beijing': { name: '北京手语', description: '北京及北方地区方言手语' },
  'shanghai': { name: '上海手语', description: '上海及华东地区方言手语' },
  'guangzhou': { name: '广州手语', description: '广州及粤语地区方言手语' },
  'hongkong': { name: '香港手语', description: '香港特别行政区手语' },
  'taiwan': { name: '台湾手语', description: '台湾地区手语' },
  'chengdu': { name: '成都手语', description: '四川及西南地区方言手语' },
  'wuhan': { name: '武汉手语', description: '武汉及华中地区方言手语' },
  'xian': { name: '西安手语', description: '西安及西北地区方言手语' },
  'northeast': { name: '东北手语', description: '东北三省方言手语' }
};

export class DialectService {
  private config: DialectConfig;
  private dialectMappings: Map<string, DialectMapping[]>;

  constructor() {
    this.dialectMappings = new Map();
    this.initializeDialectMappings();
    this.config = this.loadConfig();
  }

  private initializeDialectMappings(): void {
    for (const mapping of DEFAULT_DIALECT_MAPPINGS) {
      if (!this.dialectMappings.has(mapping.region)) {
        this.dialectMappings.set(mapping.region, []);
      }
      this.dialectMappings.get(mapping.region)!.push(mapping);
    }
  }

  private loadConfig(): DialectConfig {
    try {
      const saved = localStorage.getItem('dialectConfig');
      if (saved) {
        return JSON.parse(saved);
      }
    } catch (e) {
      console.warn('Failed to load dialect config:', e);
    }
    
    return {
      activeDialect: 'standard',
      availableDialects: ['standard', 'beijing', 'shanghai', 'guangzhou', 'hongkong', 'taiwan', 'chengdu', 'northeast'],
      customMappings: [],
      autoDetect: false,
      confidenceThreshold: 0.6
    };
  }

  private saveConfig(): void {
    try {
      localStorage.setItem('dialectConfig', JSON.stringify(this.config));
    } catch (e) {
      console.warn('Failed to save dialect config:', e);
    }
  }

  public getConfig(): DialectConfig {
    return { ...this.config };
  }

  public setActiveDialect(dialect: string): void {
    if (this.config.availableDialects.includes(dialect)) {
      this.config.activeDialect = dialect;
      this.saveConfig();
    }
  }

  public setAutoDetect(enabled: boolean): void {
    this.config.autoDetect = enabled;
    this.saveConfig();
  }

  public setConfidenceThreshold(threshold: number): void {
    this.config.confidenceThreshold = Math.max(0.1, Math.min(0.95, threshold));
    this.saveConfig();
  }

  public addCustomMapping(mapping: Omit<DialectMapping, 'id'>): DialectMapping {
    const newMapping: DialectMapping = {
      ...mapping,
      id: `custom-${Date.now()}`
    };
    
    this.config.customMappings.push(newMapping);
    
    if (!this.dialectMappings.has(mapping.region)) {
      this.dialectMappings.set(mapping.region, []);
    }
    this.dialectMappings.get(mapping.region)!.push(newMapping);
    
    this.saveConfig();
    return newMapping;
  }

  public removeCustomMapping(id: string): boolean {
    const index = this.config.customMappings.findIndex(m => m.id === id);
    if (index >= 0) {
      const mapping = this.config.customMappings[index];
      this.config.customMappings.splice(index, 1);
      
      const regionMappings = this.dialectMappings.get(mapping.region);
      if (regionMappings) {
        const idx = regionMappings.findIndex(m => m.id === id);
        if (idx >= 0) {
          regionMappings.splice(idx, 1);
        }
      }
      
      this.saveConfig();
      return true;
    }
    return false;
  }

  public getAvailableDialects(): { code: string; name: string; description: string }[] {
    return this.config.availableDialects.map(code => ({
      code,
      name: DIALECT_REGIONS[code as DialectRegion]?.name || code,
      description: DIALECT_REGIONS[code as DialectRegion]?.description || ''
    }));
  }

  public getDialectMappings(region?: string): DialectMapping[] {
    const targetRegion = region || this.config.activeDialect;
    const mappings = this.dialectMappings.get(targetRegion) || [];
    return [...mappings];
  }

  public getDialectToStandardMapping(region?: string): Map<string, DialectMapping> {
    const mappings = this.getDialectMappings(region);
    const map = new Map<string, DialectMapping>();
    
    for (const m of mappings) {
      map.set(m.dialectWord, m);
    }
    
    return map;
  }

  public getStandardToDialectMapping(region?: string): Map<string, DialectMapping> {
    const mappings = this.getDialectMappings(region);
    const map = new Map<string, DialectMapping>();
    
    for (const m of mappings) {
      if (!map.has(m.standardWord)) {
        map.set(m.standardWord, m);
      }
    }
    
    return map;
  }

  public recognizeDialectWord(
    featureVector: number[],
    region?: string
  ): { mapping: DialectMapping; similarity: number } | null {
    const mappings = this.getDialectMappings(region);
    let bestMatch: DialectMapping | null = null;
    let bestSimilarity = 0;

    for (const mapping of mappings) {
      const similarity = this.cosineSimilarity(featureVector, mapping.featureTemplate);
      if (similarity > bestSimilarity && similarity >= this.config.confidenceThreshold) {
        bestSimilarity = similarity;
        bestMatch = mapping;
      }
    }

    return bestMatch ? { mapping: bestMatch, similarity: bestSimilarity } : null;
  }

  private cosineSimilarity(vec1: number[], vec2: number[]): number {
    if (vec1.length !== vec2.length) {
      const minLen = Math.min(vec1.length, vec2.length);
      vec1 = vec1.slice(0, minLen);
      vec2 = vec2.slice(0, minLen);
    }

    let dotProduct = 0;
    let norm1 = 0;
    let norm2 = 0;

    for (let i = 0; i < vec1.length; i++) {
      dotProduct += vec1[i] * vec2[i];
      norm1 += vec1[i] * vec1[i];
      norm2 += vec2[i] * vec2[i];
    }

    if (norm1 === 0 || norm2 === 0) return 0;
    return dotProduct / (Math.sqrt(norm1) * Math.sqrt(norm2));
  }

  public translateDialectToStandard(
    word: RecognizedWord,
    region?: string
  ): { word: RecognizedWord; mapping?: DialectMapping; isDialect: boolean } {
    const targetRegion = region || this.config.activeDialect;
    
    if (targetRegion === 'standard') {
      return { word, isDialect: false };
    }

    const dialectMap = this.getDialectToStandardMapping(targetRegion);
    const mapping = dialectMap.get(word.word);

    if (mapping) {
      const standardVocab = VOCABULARY.find(v => v.word === mapping.standardWord);
      return {
        word: {
          ...word,
          word: mapping.standardWord,
          pinyin: standardVocab?.pinyin || word.pinyin,
          category: standardVocab?.category || word.category
        },
        mapping,
        isDialect: true
      };
    }

    return { word, isDialect: false };
  }

  public translateStandardToDialect(
    word: RecognizedWord,
    region?: string
  ): { word: RecognizedWord; mapping?: DialectMapping } {
    const targetRegion = region || this.config.activeDialect;
    
    if (targetRegion === 'standard') {
      return { word };
    }

    const standardMap = this.getStandardToDialectMapping(targetRegion);
    const mapping = standardMap.get(word.word);

    if (mapping) {
      return {
        word: {
          ...word,
          word: mapping.dialectWord,
          pinyin: mapping.pinyin
        },
        mapping
      };
    }

    return { word };
  }

  public autoDetectDialect(
    recognizedWords: RecognizedWord[],
    featureVectors: number[][]
  ): { detectedDialect: string; confidence: number; evidences: string[] } {
    const dialectScores: Map<string, { score: number; matches: string[] }> = new Map();
    const evidences: string[] = [];

    for (const dialect of this.config.availableDialects) {
      if (dialect === 'standard') continue;
      
      let totalScore = 0;
      const matches: string[] = [];

      for (let i = 0; i < recognizedWords.length; i++) {
        const word = recognizedWords[i];
        const features = featureVectors[i] || [];
        
        const result = this.recognizeDialectWord(features, dialect);
        if (result && result.mapping.standardWord === word.word) {
          totalScore += result.similarity;
          matches.push(`${word.word} → ${result.mapping.dialectWord}`);
        }
      }

      if (matches.length > 0) {
        dialectScores.set(dialect, {
          score: totalScore / recognizedWords.length,
          matches
        });
      }
    }

    let bestDialect = 'standard';
    let bestConfidence = 0;

    dialectScores.forEach((data, dialect) => {
      if (data.score > bestConfidence && data.score >= 0.5) {
        bestConfidence = data.score;
        bestDialect = dialect;
        evidences.push(...data.matches);
      }
    });

    return {
      detectedDialect: bestDialect,
      confidence: bestConfidence,
      evidences
    };
  }

  public calculateDialectScore(
    word: RecognizedWord,
    featureVector: number[]
  ): { score: number; isDialect: boolean; mapping?: DialectMapping } {
    const region = this.config.activeDialect;
    
    if (region === 'standard') {
      return { score: 1.0, isDialect: false };
    }

    const dialectMap = this.getDialectToStandardMapping(region);
    const mapping = dialectMap.get(word.word);

    if (mapping) {
      const similarity = this.cosineSimilarity(featureVector, mapping.featureTemplate);
      return {
        score: similarity,
        isDialect: true,
        mapping
      };
    }

    const standardMap = this.getStandardToDialectMapping(region);
    const reverseMapping = standardMap.get(word.word);
    
    if (reverseMapping) {
      const similarity = this.cosineSimilarity(featureVector, reverseMapping.featureTemplate);
      return {
        score: similarity * 0.8,
        isDialect: false,
        mapping: reverseMapping
      };
    }

    return { score: 0.8, isDialect: false };
  }

  public getDialectInfo(region: string): { name: string; description: string; mappingCount: number } | null {
    const info = DIALECT_REGIONS[region as DialectRegion];
    if (!info) return null;

    const mappings = this.dialectMappings.get(region) || [];
    return {
      ...info,
      mappingCount: mappings.length
    };
  }

  public exportCustomMappings(): string {
    return JSON.stringify(this.config.customMappings, null, 2);
  }

  public importCustomMappings(jsonString: string): number {
    try {
      const mappings = JSON.parse(jsonString) as DialectMapping[];
      let imported = 0;

      for (const mapping of mappings) {
        if (mapping.dialectWord && mapping.standardWord && mapping.region) {
          this.addCustomMapping({
            dialectName: mapping.dialectName || '自定义',
            region: mapping.region,
            standardWord: mapping.standardWord,
            dialectWord: mapping.dialectWord,
            pinyin: mapping.pinyin || '',
            featureTemplate: mapping.featureTemplate || [0, 0, 0],
            category: mapping.category || 'noun',
            description: mapping.description
          });
          imported++;
        }
      }

      return imported;
    } catch (e) {
      console.error('Failed to import custom mappings:', e);
      return 0;
    }
  }

  public resetToDefaults(): void {
    this.config = {
      activeDialect: 'standard',
      availableDialects: ['standard', 'beijing', 'shanghai', 'guangzhou', 'hongkong', 'taiwan', 'chengdu', 'northeast'],
      customMappings: [],
      autoDetect: false,
      confidenceThreshold: 0.6
    };
    this.dialectMappings.clear();
    this.initializeDialectMappings();
    this.saveConfig();
  }
}

export const dialectService = new DialectService();
