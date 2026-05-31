import { RecognizedWord, ContextState, ContextualConstraint } from '@/types';

const CATEGORY_SEQUENCE_PATTERNS: Record<string, { next: string[]; weight: number }[]> = {
  'pronoun': [
    { next: ['verb', 'adjective', 'noun'], weight: 0.8 },
    { next: ['preposition'], weight: 0.6 }
  ],
  'noun': [
    { next: ['verb', 'adjective', 'preposition', 'conjunction'], weight: 0.85 },
    { next: ['noun'], weight: 0.4 }
  ],
  'time': [
    { next: ['pronoun', 'noun', 'verb'], weight: 0.9 },
    { next: ['preposition'], weight: 0.5 }
  ],
  'verb': [
    { next: ['noun', 'pronoun', 'adverb', 'preposition'], weight: 0.85 },
    { next: ['question'], weight: 0.3 }
  ],
  'adjective': [
    { next: ['noun', 'conjunction'], weight: 0.8 },
    { next: ['verb'], weight: 0.5 }
  ],
  'question': [
    { next: ['verb', 'noun', 'pronoun'], weight: 0.7 },
    { next: [], weight: 0.1 }
  ],
  'preposition': [
    { next: ['noun', 'pronoun', 'time'], weight: 0.9 }
  ],
  'adverb': [
    { next: ['verb', 'adjective'], weight: 0.85 }
  ],
  'conjunction': [
    { next: ['noun', 'pronoun', 'verb', 'adjective'], weight: 0.8 }
  ]
};

const SENTENCE_TYPE_PATTERNS: Record<string, { triggers: string[]; constraints: ContextualConstraint }> = {
  'topic_comment': {
    triggers: ['pronoun', 'noun'],
    constraints: {
      type: 'topic_comment',
      weight: 0.7,
      allowedNextCategories: ['verb', 'adjective', 'preposition'],
      forbiddenNextCategories: ['question', 'conjunction'],
      description: '主题-评论结构：主题后应接评论'
    }
  },
  'time_action_object': {
    triggers: ['time'],
    constraints: {
      type: 'time_action_object',
      weight: 0.8,
      allowedNextCategories: ['pronoun', 'noun', 'verb'],
      forbiddenNextCategories: ['question', 'adjective'],
      description: '时间-动作-对象顺序：时间词后应接动作或主体'
    }
  },
  'question_sentence': {
    triggers: ['question'],
    constraints: {
      type: 'sentence_type',
      weight: 0.9,
      allowedNextCategories: [],
      forbiddenNextCategories: ['time', 'preposition', 'conjunction'],
      description: '疑问句：疑问词应在句末'
    }
  }
};

export class ContextAwareService {
  private contextState: ContextState;
  private contextWindowSize: number;
  private nGramModel: Map<string, Map<string, number>>;
  private categoryTransitions: Map<string, Map<string, number>>;

  constructor(windowSize: number = 5) {
    this.contextWindowSize = windowSize;
    this.contextState = this.createInitialContext();
    this.nGramModel = new Map();
    this.categoryTransitions = new Map();
    this.initializeNGramModel();
  }

  private createInitialContext(): ContextState {
    return {
      recentWords: [],
      recentCategories: [],
      sentenceType: 'unknown',
      predictedNextCategories: [],
      contextWindowSize: this.contextWindowSize
    };
  }

  private initializeNGramModel(): void {
    const commonPatterns = [
      ['pronoun', 'verb', 'noun'],
      ['time', 'pronoun', 'verb'],
      ['noun', 'adjective', 'noun'],
      ['pronoun', 'adverb', 'verb'],
      ['time', 'noun', 'verb', 'noun'],
      ['pronoun', 'verb', 'noun', 'question'],
      ['noun', 'verb', 'noun'],
      ['pronoun', 'verb', 'adjective'],
      ['time', 'verb', 'noun'],
      ['noun', 'preposition', 'noun']
    ];

    for (const pattern of commonPatterns) {
      for (let i = 0; i < pattern.length - 1; i++) {
        const history = pattern.slice(0, i + 1).join(',');
        const next = pattern[i + 1];
        this.updateNGramCount(history, next);
      }
    }
  }

  private updateNGramCount(history: string, next: string): void {
    if (!this.nGramModel.has(history)) {
      this.nGramModel.set(history, new Map());
    }
    const nextMap = this.nGramModel.get(history)!;
    nextMap.set(next, (nextMap.get(next) || 0) + 1);

    const lastCategory = history.split(',').pop() || history;
    if (!this.categoryTransitions.has(lastCategory)) {
      this.categoryTransitions.set(lastCategory, new Map());
    }
    const transMap = this.categoryTransitions.get(lastCategory)!;
    transMap.set(next, (transMap.get(next) || 0) + 1);
  }

  public updateContext(newWord: RecognizedWord): ContextState {
    this.contextState.recentWords = [...this.contextState.recentWords, newWord].slice(-this.contextWindowSize);
    this.contextState.recentCategories = [...this.contextState.recentCategories, newWord.category || 'noun'].slice(-this.contextWindowSize);

    this.detectSentenceType();
    this.identifyTopicAndTime();
    this.predictNextCategories();

    if (this.contextState.recentCategories.length >= 2) {
      const history = this.contextState.recentCategories.slice(-2).join(',');
      this.updateNGramCount(history, newWord.category || 'noun');
    }

    return this.getContextState();
  }

  private detectSentenceType(): void {
    const categories = this.contextState.recentCategories;
    
    if (categories.includes('question')) {
      this.contextState.sentenceType = 'question';
      return;
    }

    const recentWords = this.contextState.recentWords;
    const hasNegation = recentWords.some(w => 
      ['不', '没有', '不是', '没', '别', '不要', '非', '无', '否'].includes(w.word)
    );
    
    if (hasNegation) {
      this.contextState.sentenceType = 'negative';
      return;
    }

    if (categories.length >= 2 && categories[0] === 'verb' && !categories.includes('pronoun')) {
      this.contextState.sentenceType = 'imperative';
      return;
    }

    if (categories.length >= 2) {
      this.contextState.sentenceType = 'declarative';
    }
  }

  private identifyTopicAndTime(): void {
    const words = this.contextState.recentWords;
    
    this.contextState.topicWord = words.find(w => 
      w.category === 'noun' || w.category === 'pronoun'
    );

    this.contextState.timeWord = words.find(w => w.category === 'time');
  }

  private predictNextCategories(): { category: string; probability: number }[] {
    const categories = this.contextState.recentCategories;
    if (categories.length === 0) {
      this.contextState.predictedNextCategories = [
        { category: 'pronoun', probability: 0.3 },
        { category: 'noun', probability: 0.35 },
        { category: 'time', probability: 0.25 },
        { category: 'verb', probability: 0.1 }
      ];
      return this.contextState.predictedNextCategories;
    }

    const predictions: Map<string, number> = new Map();
    const lastCategory = categories[categories.length - 1];

    const patternPredictions = CATEGORY_SEQUENCE_PATTERNS[lastCategory] || [];
    for (const p of patternPredictions) {
      for (const nextCat of p.next) {
        predictions.set(nextCat, (predictions.get(nextCat) || 0) + p.weight * 0.5);
      }
    }

    if (this.categoryTransitions.has(lastCategory)) {
      const transMap = this.categoryTransitions.get(lastCategory)!;
      let total = 0;
      transMap.forEach(v => total += v);
      transMap.forEach((count, nextCat) => {
        const prob = count / total;
        predictions.set(nextCat, (predictions.get(nextCat) || 0) + prob * 0.5);
      });
    }

    if (categories.length >= 2) {
      const history = categories.slice(-2).join(',');
      if (this.nGramModel.has(history)) {
        const ngramMap = this.nGramModel.get(history)!;
        let total = 0;
        ngramMap.forEach(v => total += v);
        ngramMap.forEach((count, nextCat) => {
          const prob = count / total;
          predictions.set(nextCat, (predictions.get(nextCat) || 0) + prob * 0.3);
        });
      }
    }

    const sentenceTypeConstraints = this.getSentenceTypeConstraints();
    for (const constraint of sentenceTypeConstraints) {
      for (const allowedCat of constraint.allowedNextCategories) {
        predictions.set(allowedCat, (predictions.get(allowedCat) || 0) + constraint.weight * 0.2);
      }
      for (const forbiddenCat of constraint.forbiddenNextCategories) {
        predictions.set(forbiddenCat, (predictions.get(forbiddenCat) || 0) * 0.3);
      }
    }

    let totalScore = 0;
    predictions.forEach(v => totalScore += v);
    
    const result = Array.from(predictions.entries())
      .map(([category, score]) => ({
        category,
        probability: totalScore > 0 ? score / totalScore : 0
      }))
      .filter(p => p.probability > 0.01)
      .sort((a, b) => b.probability - a.probability)
      .slice(0, 5);

    this.contextState.predictedNextCategories = result;
    return result;
  }

  public getContextualConstraints(): ContextualConstraint[] {
    const constraints: ContextualConstraint[] = [];
    const categories = this.contextState.recentCategories;

    if (categories.length > 0) {
      const lastCategory = categories[categories.length - 1];
      const pattern = CATEGORY_SEQUENCE_PATTERNS[lastCategory];
      if (pattern) {
        const allowedNext = [...new Set(pattern.flatMap(p => p.next))];
        const maxWeight = Math.max(...pattern.map(p => p.weight));
        constraints.push({
          type: 'category_sequence',
          weight: maxWeight,
          allowedNextCategories: allowedNext,
          forbiddenNextCategories: [],
          description: `${lastCategory} 类词后通常接 ${allowedNext.join('、')}`
        });
      }
    }

    constraints.push(...this.getSentenceTypeConstraints());

    if (this.contextState.topicWord && !this.contextState.recentCategories.includes('verb')) {
      constraints.push({
        type: 'topic_comment',
        weight: 0.6,
        allowedNextCategories: ['verb', 'adjective', 'preposition'],
        forbiddenNextCategories: ['question', 'time'],
        description: '已有主题，期待评论（动作或描述）'
      });
    }

    return constraints;
  }

  private getSentenceTypeConstraints(): ContextualConstraint[] {
    const constraints: ContextualConstraint[] = [];
    
    switch (this.contextState.sentenceType) {
      case 'question':
        constraints.push({
          type: 'sentence_type',
          weight: 0.9,
          allowedNextCategories: [],
          forbiddenNextCategories: ['time', 'preposition', 'conjunction'],
          description: '疑问句：疑问词后不宜再接时间词或介词'
        });
        break;
      case 'negative':
        constraints.push({
          type: 'sentence_type',
          weight: 0.7,
          allowedNextCategories: ['verb', 'adjective'],
          forbiddenNextCategories: ['noun', 'time'],
          description: '否定句：否定词后通常接动词或形容词'
        });
        break;
      case 'imperative':
        constraints.push({
          type: 'sentence_type',
          weight: 0.6,
          allowedNextCategories: ['noun', 'adverb'],
          forbiddenNextCategories: ['pronoun', 'question'],
          description: '祈使句：动词开头后通常接宾语或状语'
        });
        break;
    }

    return constraints;
  }

  public calculateContextScore(word: RecognizedWord): { score: number; violations: string[] } {
    const constraints = this.getContextualConstraints();
    const category = word.category || 'noun';
    let totalWeight = 0;
    let weightedScore = 0;
    const violations: string[] = [];

    for (const constraint of constraints) {
      totalWeight += constraint.weight;
      
      if (constraint.allowedNextCategories.length > 0 && 
          !constraint.allowedNextCategories.includes(category)) {
        weightedScore += constraint.weight * 0.3;
        if (constraint.weight >= 0.7) {
          violations.push(constraint.description);
        }
      } else if (constraint.forbiddenNextCategories.includes(category)) {
        weightedScore += constraint.weight * 0.1;
        violations.push(constraint.description);
      } else {
        weightedScore += constraint.weight;
      }
    }

    const predictions = this.contextState.predictedNextCategories;
    const categoryPrediction = predictions.find(p => p.category === category);
    if (categoryPrediction) {
      totalWeight += 0.5;
      weightedScore += categoryPrediction.probability * 0.5;
    } else if (predictions.length > 0) {
      totalWeight += 0.5;
      weightedScore += 0.2 * 0.5;
    }

    const finalScore = totalWeight > 0 ? weightedScore / totalWeight : 0.5;

    return {
      score: Math.max(0.1, Math.min(1.0, finalScore)),
      violations
    };
  }

  public adjustRecognitionConfidence(
    candidates: { word: RecognizedWord; similarity: number }[]
  ): { word: RecognizedWord; adjustedScore: number; isRecommended: boolean }[] {
    return candidates.map(({ word, similarity }) => {
      const { score: contextScore, violations } = this.calculateContextScore(word);
      const adjustedScore = similarity * 0.5 + contextScore * 0.5;

      return {
        word: {
          ...word,
          confidence: adjustedScore
        },
        adjustedScore,
        isRecommended: violations.length === 0 && adjustedScore > 0.5
      };
    }).sort((a, b) => b.adjustedScore - a.adjustedScore);
  }

  public getContextState(): ContextState {
    return { ...this.contextState };
  }

  public resetContext(): void {
    this.contextState = this.createInitialContext();
  }

  public updateContextWindowSize(newSize: number): void {
    this.contextWindowSize = newSize;
    this.contextState.contextWindowSize = newSize;
    this.contextState.recentWords = this.contextState.recentWords.slice(-newSize);
    this.contextState.recentCategories = this.contextState.recentCategories.slice(-newSize);
  }

  public getSuggestedWords(): { category: string; probability: number; examples: string[] }[] {
    const predictions = this.contextState.predictedNextCategories;
    
    return predictions.map(p => ({
      category: p.category,
      probability: p.probability,
      examples: this.getExampleWords(p.category)
    }));
  }

  private getExampleWords(category: string): string[] {
    const examples: Record<string, string[]> = {
      'pronoun': ['我', '你', '他', '我们', '你们', '他们'],
      'noun': ['人', '家', '学校', '工作', '朋友', '书'],
      'verb': ['去', '吃', '看', '学习', '喜欢', '帮助'],
      'adjective': ['好', '大', '小', '漂亮', '开心', '快'],
      'time': ['今天', '明天', '昨天', '现在', '以后', '早上'],
      'question': ['什么', '谁', '哪里', '什么时候', '为什么', '怎么'],
      'preposition': ['在', '从', '到', '和', '对', '向'],
      'adverb': ['很', '非常', '也', '都', '就', '才'],
      'conjunction': ['和', '但是', '因为', '所以', '如果', '虽然']
    };
    return examples[category] || [];
  }

  public getContextSummary(): string {
    const { recentWords, sentenceType, topicWord, timeWord } = this.contextState;
    
    if (recentWords.length === 0) {
      return '尚未建立上下文';
    }

    const parts: string[] = [];
    
    const typeNames: Record<string, string> = {
      'declarative': '陈述句',
      'question': '疑问句',
      'negative': '否定句',
      'imperative': '祈使句',
      'unknown': '未确定'
    };
    parts.push(`句型: ${typeNames[sentenceType]}`);
    
    if (topicWord) {
      parts.push(`主题: ${topicWord.word}`);
    }
    if (timeWord) {
      parts.push(`时间: ${timeWord.word}`);
    }
    
    return parts.join(' | ');
  }
}

export const contextAwareService = new ContextAwareService(5);
