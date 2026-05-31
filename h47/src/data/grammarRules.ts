import { GrammarRule, GrammarErrorType, RecognizedWord, GrammarCheckResult, GrammarError } from '@/types';

export const GRAMMAR_RULES: GrammarRule[] = [
  {
    id: 'topic_comment',
    name: '主题-评论结构',
    description: '中国手语遵循"主题在前，评论在后"的结构，即先说明讨论的主题，再对主题进行评论或说明。',
    pattern: /^(.)*$/,
    correction: '主题词应放在句子开头'
  },
  {
    id: 'time_action_object',
    name: '时间-动作-对象顺序',
    description: '手语句子通常遵循"时间状语 + 动作动词 + 对象宾语"的顺序。',
    pattern: /^(.)*$/,
    correction: '时间词应在动作词之前，动作词应在对象词之前'
  },
  {
    id: 'topic_first',
    name: '主题优先原则',
    description: '当句子中存在多个成分时，主题（谈论的对象）应放在最前面。',
    pattern: /^(.)*$/,
    correction: '主题词应放在句首位置'
  },
  {
    id: 'question_word_position',
    name: '疑问句句末原则',
    description: '中国手语中，疑问词（谁、什么、哪里、什么时候、为什么等）通常放在句子末尾。',
    pattern: /^(.)*$/,
    correction: '疑问词应放在句子末尾'
  },
  {
    id: 'negation_position',
    name: '否定词位置规则',
    description: '中国手语中，否定词通常放在动词之前或句子末尾，否定动作时放在动词前，否定全句时放在句末。',
    pattern: /^(.)*$/,
    correction: '否定词应放在动词之前或句末'
  }
];

export const WORD_CATEGORY_ORDER = ['time', 'noun', 'pronoun', 'adjective', 'verb', 'preposition', 'adverb', 'conjunction', 'question'];

const TIME_WORDS = ['今天', '明天', '昨天', '现在', '早上', '中午', '晚上', '以前', '以后', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日', '今年', '去年', '明年', '刚才', '马上', '立刻', '有时候', '经常', '偶尔', '总是', '从不', '已经', '刚刚', '将要', '春天', '夏天', '秋天', '冬天'];
const TOPIC_INDICATORS = ['我', '你', '他', '她', '我们', '你们', '他们', '这', '那'];
const QUESTION_WORDS = ['谁', '什么', '哪里', '什么时候', '为什么', '怎么', '多少', '几', '哪个', '怎样'];
const NEGATION_WORDS = ['不', '没有', '不是', '没', '别', '不要', '不用', '未曾', '未必'];

export const checkChineseSignLanguageGrammar = (sequence: RecognizedWord[]): GrammarCheckResult => {
  const errors: GrammarError[] = [];
  const words = sequence.map(w => w.word);
  let correctedSequence: RecognizedWord[] = [...sequence];
  const ruleApplied: string[] = [];

  if (sequence.length === 0) {
    return {
      isCorrect: true,
      errors: [],
      correctedSequence: [],
      translation: '',
      ruleApplied: []
    };
  }

  const processedSequence = handleRepeatedWords(sequence);

  const sequenceWithCategories = processedSequence.map((word, index) => ({
    ...word,
    index,
    category: getWordCategory(word.word)
  }));

  let hasTimeError = false;
  let hasActionObjectError = false;
  let hasTopicError = false;
  let hasQuestionError = false;
  let hasNegationError = false;

  const isQuestion = sequence.some(w => QUESTION_WORDS.includes(w.word));
  const isNegation = sequence.some(w => NEGATION_WORDS.includes(w.word));

  const timeIndices = sequenceWithCategories
    .filter(w => w.category === 'time' || TIME_WORDS.includes(w.word))
    .map(w => w.index);
  
  const verbIndices = sequenceWithCategories
    .filter(w => w.category === 'verb')
    .map(w => w.index);
  
  const nounIndices = sequenceWithCategories
    .filter(w => w.category === 'noun' || w.category === 'pronoun')
    .map(w => w.index);

  const questionIndices = sequenceWithCategories
    .filter(w => QUESTION_WORDS.includes(w.word))
    .map(w => w.index);

  const negationIndices = sequenceWithCategories
    .filter(w => NEGATION_WORDS.includes(w.word))
    .map(w => w.index);

  if (isQuestion && questionIndices.length > 0) {
    const lastQuestion = Math.max(...questionIndices);
    const lastIndex = processedSequence.length - 1;

    if (lastQuestion < lastIndex - 1) {
      hasQuestionError = true;
      const questionWord = sequenceWithCategories.find(w => w.index === lastQuestion)!;
      errors.push({
        type: 'word_order',
        position: lastQuestion,
        word: questionWord.word,
        description: '中国手语中疑问词应放在句子末尾',
        suggestion: `将疑问词"${questionWord.word}"移到句子末尾`
      });
      ruleApplied.push('疑问句句末原则');
    }
  }

  if (isNegation && negationIndices.length > 0 && verbIndices.length > 0) {
    for (const negIndex of negationIndices) {
      const negWord = sequenceWithCategories.find(w => w.index === negIndex)!;
      const nearestVerb = verbIndices.reduce((nearest, v) =>
        Math.abs(v - negIndex) < Math.abs(nearest - negIndex) ? v : nearest
      , verbIndices[0]);

      const isSentenceNegation = negIndex === processedSequence.length - 1;
      const isVerbNegation = negIndex === nearestVerb - 1 || negIndex === nearestVerb + 1;

      if (!isSentenceNegation && !isVerbNegation) {
        hasNegationError = true;
        errors.push({
          type: 'word_order',
          position: negIndex,
          word: negWord.word,
          description: '否定词应放在动词之前或句子末尾',
          suggestion: `将否定词"${negWord.word}"移到动词"${processedSequence[nearestVerb].word}"之前或句末`
        });
        ruleApplied.push('否定词位置规则');
      }
    }
  }

  if (!isQuestion && timeIndices.length > 0 && verbIndices.length > 0) {
    const firstTime = Math.min(...timeIndices);
    const firstVerb = Math.min(...verbIndices);
    if (firstTime > firstVerb) {
      hasTimeError = true;
      const timeWord = sequenceWithCategories.find(w => w.index === firstTime)!;
      errors.push({
        type: 'word_order',
        position: firstTime,
        word: timeWord.word,
        description: '时间词应该放在动作词之前',
        suggestion: `将"${timeWord.word}"移到动词"${processedSequence[firstVerb].word}"之前`
      });
      ruleApplied.push('时间-动作-对象顺序');
    }
  }

  if (verbIndices.length > 0 && nounIndices.length > 0) {
    const lastVerb = Math.max(...verbIndices);
    const objectNouns = nounIndices.filter(n => n > lastVerb);

    if (!isQuestion && objectNouns.length === 0 && nounIndices.some(n => n < Math.min(...verbIndices))) {
      const firstNounBeforeVerb = Math.max(...nounIndices.filter(n => n < Math.min(...verbIndices)));
      const nounWord = sequenceWithCategories.find(w => w.index === firstNounBeforeVerb)!;
      const isTopic = TOPIC_INDICATORS.includes(nounWord.word);
      if (!isTopic) {
        hasActionObjectError = true;
        errors.push({
          type: 'missing_object',
          position: firstNounBeforeVerb,
          word: nounWord.word,
          description: '动作对象应该放在动作词之后',
          suggestion: `将"${nounWord.word}"移到动词"${processedSequence[lastVerb].word}"之后作为对象`
        });
        ruleApplied.push('动作-对象顺序');
      }
    }
  }

  const topicWords = sequenceWithCategories.filter(w => TOPIC_INDICATORS.includes(w.word));
  if (!isQuestion && topicWords.length > 0) {
    const firstTopic = Math.min(...topicWords.map(w => w.index));
    const timeBeforeTopic = timeIndices.filter(t => t < firstTopic);
    if (timeBeforeTopic.length === 0 && firstTopic > 0) {
      const nonTimeBefore = sequenceWithCategories.filter((w, i) => i < firstTopic && !TIME_WORDS.includes(w.word));
      if (nonTimeBefore.length > 0) {
        hasTopicError = true;
        const topicWord = topicWords[0];
        errors.push({
          type: 'missing_topic',
          position: firstTopic,
          word: topicWord.word,
          description: '主题词应放在句首（时间词之后，其他成分之前）',
          suggestion: `将主题词"${topicWord.word}"移到句子开头`
        });
        ruleApplied.push('主题-评论结构');
      }
    }
  }

  if (timeIndices.length === 0 && verbIndices.length === 0 && processedSequence.length >= 2 && !isQuestion) {
    errors.push({
      type: 'structure_error',
      position: 0,
      word: processedSequence[0].word,
      description: '句子结构不完整，缺少必要的时间、动作或主题成分',
      suggestion: '建议补充时间词、动作动词或主题词使句子更完整'
    });
    ruleApplied.push('句子完整性检查');
  }

  if (errors.length > 0) {
    const sorted = reorderToGrammatical(sequenceWithCategories, isQuestion, isNegation);
    correctedSequence = sorted;
  } else {
    correctedSequence = processedSequence;
  }

  const translation = generateTranslation(correctedSequence, isQuestion, isNegation);

  return {
    isCorrect: errors.length === 0,
    errors,
    correctedSequence,
    translation,
    ruleApplied
  };
};

const handleRepeatedWords = (sequence: RecognizedWord[]): RecognizedWord[] => {
  if (sequence.length < 2) return sequence;

  const result: RecognizedWord[] = [];
  let i = 0;

  while (i < sequence.length) {
    const currentWord = sequence[i];
    let repeatCount = 1;

    while (i + repeatCount < sequence.length &&
           sequence[i + repeatCount].word === currentWord.word &&
           (sequence[i + repeatCount].startTime - currentWord.endTime) < 2000) {
      repeatCount++;
    }

    if (repeatCount > 1) {
      result.push({
        ...currentWord,
        word: currentWord.word.repeat(repeatCount),
        endTime: sequence[i + repeatCount - 1].endTime,
        confidence: Math.max(...sequence.slice(i, i + repeatCount).map(w => w.confidence)),
        isCorrect: true
      });
      i += repeatCount;
    } else {
      result.push(currentWord);
      i++;
    }
  }

  return result;
};

const getWordCategory = (word: string): string => {
  if (TIME_WORDS.includes(word)) return 'time';
  if (TOPIC_INDICATORS.includes(word)) return 'pronoun';
  if (QUESTION_WORDS.includes(word)) return 'question';
  if (NEGATION_WORDS.includes(word)) return 'adverb';
  
  const timeVerbs = ['看', '听', '说', '写', '读', '吃', '喝', '睡', '走', '跑', '坐', '站', '打', '买', '卖', '学', '教', '工作', '休息', '喜欢', '爱', '想', '要', '能', '会', '可以', '有', '是', '去', '来', '下雨', '下雪', '谢谢', '对不起', '请', '帮忙', '等待', '开始', '结束', '继续', '停止', '准备', '计划', '希望', '努力', '成功', '失败', '检查', '治疗', '恢复', '锻炼', '跑步', '游泳', '合作', '沟通', '理解', '尊重', '信任'];
  if (timeVerbs.includes(word)) return 'verb';
  
  return 'noun';
};

const reorderToGrammatical = (
  sequence: (RecognizedWord & { index: number; category: string })[],
  isQuestion: boolean = false,
  isNegation: boolean = false
): RecognizedWord[] => {
  const timeWords = sequence.filter(w => w.category === 'time' || TIME_WORDS.includes(w.word));
  const topicWords = sequence.filter(w => TOPIC_INDICATORS.includes(w.word));
  const adjectives = sequence.filter(w => w.category === 'adjective');
  const verbs = sequence.filter(w => w.category === 'verb');
  const negationWords = sequence.filter(w => NEGATION_WORDS.includes(w.word));
  const questionWords = sequence.filter(w => QUESTION_WORDS.includes(w.word));
  const otherNouns = sequence.filter(w =>
    w.category === 'noun' &&
    !TOPIC_INDICATORS.includes(w.word) &&
    !QUESTION_WORDS.includes(w.word) &&
    !NEGATION_WORDS.includes(w.word)
  );
  const others = sequence.filter(w =>
    !timeWords.includes(w) &&
    !topicWords.includes(w) &&
    !adjectives.includes(w) &&
    !verbs.includes(w) &&
    !negationWords.includes(w) &&
    !questionWords.includes(w) &&
    !otherNouns.includes(w)
  );

  const result: RecognizedWord[] = [];

  timeWords.forEach(w => result.push({ ...w, isCorrect: true }));
  topicWords.forEach(w => result.push({ ...w, isCorrect: true }));
  adjectives.forEach(w => result.push({ ...w, isCorrect: true }));

  if (isNegation && negationWords.length > 0) {
    negationWords.forEach(w => result.push({ ...w, isCorrect: true }));
  }

  verbs.forEach(w => result.push({ ...w, isCorrect: true }));
  otherNouns.forEach(w => result.push({ ...w, isCorrect: true }));
  others.forEach(w => result.push({ ...w, isCorrect: true }));

  if (isNegation && negationWords.length > 0 && verbs.length === 0) {
    negationWords.forEach(w => result.push({ ...w, isCorrect: true }));
  }

  if (isQuestion && questionWords.length > 0) {
    questionWords.forEach(w => result.push({ ...w, isCorrect: true }));
  } else {
    questionWords.forEach(w => result.push({ ...w, isCorrect: true }));
    if (!isNegation) {
      negationWords.forEach(w => result.push({ ...w, isCorrect: true }));
    }
  }

  return result;
};

const generateTranslation = (
  sequence: RecognizedWord[],
  isQuestion: boolean = false,
  isNegation: boolean = false
): string => {
  if (sequence.length === 0) return '';

  const words = sequence.map(w => w.word);
  let translation = words.join('');

  if (isQuestion && !translation.endsWith('？') && !translation.endsWith('?')) {
    translation = translation + '？';
  }

  if (isNegation && !isQuestion) {
    if (translation.includes('不不')) {
      translation = translation.replace('不不', '不');
    }
    if (translation.includes('没有没有')) {
      translation = translation.replace('没有没有', '没有');
    }
  }

  return translation;
};

export const getErrorTypeName = (type: GrammarErrorType): string => {
  const names: Record<GrammarErrorType, string> = {
    word_order: '词序错误',
    missing_topic: '主题缺失',
    missing_time: '时间缺失',
    structure_error: '结构错误',
    missing_action: '动作缺失',
    missing_object: '对象缺失'
  };
  return names[type] || type;
};

export const getGrammarRules = (): GrammarRule[] => GRAMMAR_RULES;
