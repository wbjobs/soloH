import { useState } from 'react';
import { useAppStore } from '@/store/appStore';
import { dialectService } from '@/services/dialectService';
import { 
  Settings, Brain, Languages, Smile, 
  ChevronDown, ChevronUp, Plus, Trash2, 
  Download, Upload, Info, Zap, Lightbulb,
  CheckCircle2, XCircle, AlertCircle
} from 'lucide-react';

const EnhancedFeaturesPanel = () => {
  const [expandedSection, setExpandedSection] = useState<string | null>('context');
  const [showAddMapping, setShowAddMapping] = useState(false);
  const [newMapping, setNewMapping] = useState({
    dialectName: '自定义',
    region: 'beijing',
    standardWord: '',
    dialectWord: '',
    pinyin: '',
    category: 'noun' as const,
    description: ''
  });

  const {
    contextState,
    dialectConfig,
    enableFaceDetection,
    enableContextAwareness,
    latestNonManualFeatures,
    setEnableFaceDetection,
    setEnableContextAwareness,
    setActiveDialect,
    addCustomDialectMapping,
    resetContext
  } = useAppStore();

  const dialects = dialectService.getAvailableDialects();

  const toggleSection = (section: string) => {
    setExpandedSection(expandedSection === section ? null : section);
  };

  const handleAddMapping = () => {
    if (newMapping.standardWord && newMapping.dialectWord) {
      addCustomDialectMapping({
        ...newMapping,
        featureTemplate: [0.1, 0.2, 0.3]
      });
      setNewMapping({
        dialectName: '自定义',
        region: 'beijing',
        standardWord: '',
        dialectWord: '',
        pinyin: '',
        category: 'noun',
        description: ''
      });
      setShowAddMapping(false);
    }
  };

  const getSentenceTypeColor = (type: string) => {
    const colors: Record<string, string> = {
      'declarative': 'text-blue-400',
      'question': 'text-yellow-400',
      'negative': 'text-red-400',
      'imperative': 'text-green-400',
      'unknown': 'text-slate-500'
    };
    return colors[type] || 'text-slate-400';
  };

  const getSentenceTypeName = (type: string) => {
    const names: Record<string, string> = {
      'declarative': '陈述句',
      'question': '疑问句',
      'negative': '否定句',
      'imperative': '祈使句',
      'unknown': '未确定'
    };
    return names[type] || type;
  };

  const getExpressionColor = (type: string) => {
    const colors: Record<string, string> = {
      'neutral': 'bg-slate-500',
      'happy': 'bg-green-500',
      'sad': 'bg-blue-500',
      'angry': 'bg-red-500',
      'surprised': 'bg-yellow-500',
      'questioning': 'bg-purple-500',
      'affirmative': 'bg-teal-500',
      'negative': 'bg-orange-500'
    };
    return colors[type] || 'bg-slate-500';
  };

  const getExpressionName = (type: string) => {
    const names: Record<string, string> = {
      'neutral': '中性',
      'happy': '开心',
      'sad': '悲伤',
      'angry': '生气',
      'surprised': '惊讶',
      'questioning': '疑问',
      'affirmative': '肯定',
      'negative': '否定'
    };
    return names[type] || type;
  };

  const getMouthShapeName = (type: string) => {
    const names: Record<string, string> = {
      'closed': '闭合',
      'open': '张开',
      'rounded': '圆形',
      'spread': '展开',
      'pursed': '噘嘴'
    };
    return names[type] || type;
  };

  return (
    <div className="space-y-3">
      <div className="bg-slate-800/80 rounded-xl overflow-hidden border border-slate-700/50">
        <button
          onClick={() => toggleSection('context')}
          className="w-full px-4 py-3 flex items-center justify-between hover:bg-slate-700/30 transition-colors"
        >
          <div className="flex items-center gap-2">
            <Brain className="w-4 h-4 text-purple-400" />
            <span className="text-sm font-medium text-slate-200">上下文感知</span>
            {enableContextAwareness && (
              <span className="px-1.5 py-0.5 bg-green-500/20 text-green-400 text-xs rounded">已启用</span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <span className={`text-xs ${getSentenceTypeColor(contextState.sentenceType)}`}>
              {getSentenceTypeName(contextState.sentenceType)}
            </span>
            {expandedSection === 'context' ? 
              <ChevronUp className="w-4 h-4 text-slate-400" /> : 
              <ChevronDown className="w-4 h-4 text-slate-400" />
            }
          </div>
        </button>

        {expandedSection === 'context' && (
          <div className="px-4 pb-4 space-y-3 border-t border-slate-700/50">
            <div className="pt-3 flex items-center justify-between">
              <label className="flex items-center gap-2 cursor-pointer">
                <div 
                  onClick={() => setEnableContextAwareness(!enableContextAwareness)}
                  className={`w-9 h-5 rounded-full transition-colors relative ${
                    enableContextAwareness ? 'bg-purple-500' : 'bg-slate-600'
                  }`}
                >
                  <div className={`absolute top-0.5 w-4 h-4 bg-white rounded-full transition-transform ${
                    enableContextAwareness ? 'translate-x-4' : 'translate-x-0.5'
                  }`} />
                </div>
                <span className="text-sm text-slate-300">启用上下文约束</span>
              </label>
              <button
                onClick={resetContext}
                className="px-2 py-1 text-xs bg-slate-700 hover:bg-slate-600 text-slate-300 rounded transition-colors"
              >
                重置上下文
              </button>
            </div>

            {contextState.recentWords.length > 0 && (
              <div className="bg-slate-900/50 rounded-lg p-3">
                <div className="text-xs text-slate-400 mb-2 flex items-center gap-1">
                  <Info className="w-3 h-3" />
                  上下文状态
                </div>
                <div className="space-y-2 text-xs">
                  <div className="flex justify-between">
                    <span className="text-slate-500">最近词汇</span>
                    <span className="text-slate-300">
                      {contextState.recentWords.slice(-3).map(w => w.word).join(' → ')}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">句型检测</span>
                    <span className={getSentenceTypeColor(contextState.sentenceType)}>
                      {getSentenceTypeName(contextState.sentenceType)}
                    </span>
                  </div>
                  {contextState.topicWord && (
                    <div className="flex justify-between">
                      <span className="text-slate-500">主题</span>
                      <span className="text-blue-400">{contextState.topicWord.word}</span>
                    </div>
                  )}
                  {contextState.timeWord && (
                    <div className="flex justify-between">
                      <span className="text-slate-500">时间</span>
                      <span className="text-teal-400">{contextState.timeWord.word}</span>
                    </div>
                  )}
                </div>
              </div>
            )}

            {contextState.predictedNextCategories.length > 0 && (
              <div className="bg-slate-900/50 rounded-lg p-3">
                <div className="text-xs text-slate-400 mb-2 flex items-center gap-1">
                  <Lightbulb className="w-3 h-3 text-yellow-400" />
                  预测下一个词类
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {contextState.predictedNextCategories.map((pred, i) => (
                    <div
                      key={i}
                      className="px-2 py-1 bg-gradient-to-r from-purple-500/20 to-blue-500/20 border border-purple-500/30 rounded text-xs"
                    >
                      <span className="text-purple-300">{pred.category}</span>
                      <span className="text-slate-500 ml-1">{Math.round(pred.probability * 100)}%</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {contextState.recentWords.length === 0 && (
              <div className="text-center py-4 text-slate-500 text-xs">
                开始手势输入以建立上下文
              </div>
            )}
          </div>
        )}
      </div>

      <div className="bg-slate-800/80 rounded-xl overflow-hidden border border-slate-700/50">
        <button
          onClick={() => toggleSection('dialect')}
          className="w-full px-4 py-3 flex items-center justify-between hover:bg-slate-700/30 transition-colors"
        >
          <div className="flex items-center gap-2">
            <Languages className="w-4 h-4 text-teal-400" />
            <span className="text-sm font-medium text-slate-200">方言适配</span>
            {dialectConfig.activeDialect !== 'standard' && (
              <span className="px-1.5 py-0.5 bg-teal-500/20 text-teal-400 text-xs rounded">
                {dialects.find(d => d.code === dialectConfig.activeDialect)?.name || dialectConfig.activeDialect}
              </span>
            )}
          </div>
          {expandedSection === 'dialect' ? 
            <ChevronUp className="w-4 h-4 text-slate-400" /> : 
            <ChevronDown className="w-4 h-4 text-slate-400" />
          }
        </button>

        {expandedSection === 'dialect' && (
          <div className="px-4 pb-4 space-y-3 border-t border-slate-700/50">
            <div className="pt-3">
              <label className="text-xs text-slate-400 block mb-2">选择方言区域</label>
              <div className="grid grid-cols-2 gap-2">
                {dialects.map((dialect) => (
                  <button
                    key={dialect.code}
                    onClick={() => setActiveDialect(dialect.code)}
                    className={`px-3 py-2 text-left rounded-lg transition-all ${
                      dialectConfig.activeDialect === dialect.code
                        ? 'bg-teal-500/20 border border-teal-500/50 text-teal-300'
                        : 'bg-slate-700/30 border border-transparent text-slate-300 hover:bg-slate-700/50'
                    }`}
                  >
                    <div className="text-sm font-medium">{dialect.name}</div>
                    <div className="text-xs opacity-60">{dialect.code}</div>
                  </button>
                ))}
              </div>
            </div>

            {dialectConfig.activeDialect !== 'standard' && (
              <div className="bg-slate-900/50 rounded-lg p-3">
                <div className="text-xs text-slate-400 mb-2">常用方言映射</div>
                <div className="space-y-1 max-h-32 overflow-y-auto">
                  {dialectService.getDialectMappings(dialectConfig.activeDialect).slice(0, 5).map((mapping, i) => (
                    <div key={i} className="flex items-center justify-between text-xs py-1 border-b border-slate-700/50 last:border-0">
                      <span className="text-teal-400">{mapping.dialectWord}</span>
                      <span className="text-slate-500">→</span>
                      <span className="text-slate-300">{mapping.standardWord}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div>
              <button
                onClick={() => setShowAddMapping(!showAddMapping)}
                className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-slate-700/50 hover:bg-slate-700 rounded-lg text-sm text-slate-300 transition-colors"
              >
                <Plus className="w-4 h-4" />
                添加自定义映射
              </button>

              {showAddMapping && (
                <div className="mt-3 bg-slate-900/50 rounded-lg p-3 space-y-2">
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="text-xs text-slate-500 block mb-1">标准词</label>
                      <input
                        type="text"
                        value={newMapping.standardWord}
                        onChange={(e) => setNewMapping({...newMapping, standardWord: e.target.value})}
                        className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-sm text-slate-200"
                        placeholder="如：我"
                      />
                    </div>
                    <div>
                      <label className="text-xs text-slate-500 block mb-1">方言词</label>
                      <input
                        type="text"
                        value={newMapping.dialectWord}
                        onChange={(e) => setNewMapping({...newMapping, dialectWord: e.target.value})}
                        className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-sm text-slate-200"
                        placeholder="如：咱"
                      />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="text-xs text-slate-500 block mb-1">拼音</label>
                      <input
                        type="text"
                        value={newMapping.pinyin}
                        onChange={(e) => setNewMapping({...newMapping, pinyin: e.target.value})}
                        className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-sm text-slate-200"
                      />
                    </div>
                    <div>
                      <label className="text-xs text-slate-500 block mb-1">词类</label>
                      <select
                        value={newMapping.category}
                        onChange={(e) => setNewMapping({...newMapping, category: e.target.value as any})}
                        className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-sm text-slate-200"
                      >
                        <option value="noun">名词</option>
                        <option value="verb">动词</option>
                        <option value="adjective">形容词</option>
                        <option value="pronoun">代词</option>
                        <option value="adverb">副词</option>
                      </select>
                    </div>
                  </div>
                  <div>
                    <label className="text-xs text-slate-500 block mb-1">区域</label>
                    <select
                      value={newMapping.region}
                      onChange={(e) => setNewMapping({...newMapping, region: e.target.value})}
                      className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-sm text-slate-200"
                    >
                      {dialects.map(d => (
                        <option key={d.code} value={d.code}>{d.name}</option>
                      ))}
                    </select>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={handleAddMapping}
                      className="flex-1 px-3 py-1.5 bg-teal-500 hover:bg-teal-600 text-white rounded text-sm transition-colors"
                    >
                      保存
                    </button>
                    <button
                      onClick={() => setShowAddMapping(false)}
                      className="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded text-sm transition-colors"
                    >
                      取消
                    </button>
                  </div>
                </div>
              )}
            </div>

            {dialectConfig.customMappings.length > 0 && (
              <div>
                <div className="text-xs text-slate-400 mb-2">自定义映射 ({dialectConfig.customMappings.length})</div>
                <div className="space-y-1 max-h-24 overflow-y-auto">
                  {dialectConfig.customMappings.map((mapping) => (
                    <div key={mapping.id} className="flex items-center justify-between px-2 py-1 bg-slate-700/30 rounded text-xs">
                      <div>
                        <span className="text-teal-400">{mapping.dialectWord}</span>
                        <span className="text-slate-500 mx-1">→</span>
                        <span className="text-slate-300">{mapping.standardWord}</span>
                      </div>
                      <button
                        onClick={() => dialectService.removeCustomMapping(mapping.id)}
                        className="text-red-400 hover:text-red-300 p-0.5"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      <div className="bg-slate-800/80 rounded-xl overflow-hidden border border-slate-700/50">
        <button
          onClick={() => toggleSection('facial')}
          className="w-full px-4 py-3 flex items-center justify-between hover:bg-slate-700/30 transition-colors"
        >
          <div className="flex items-center gap-2">
            <Smile className="w-4 h-4 text-pink-400" />
            <span className="text-sm font-medium text-slate-200">面部表情与口形</span>
            {enableFaceDetection && latestNonManualFeatures && (
              <span className={`w-2 h-2 rounded-full ${getExpressionColor(latestNonManualFeatures.facialExpression.type)} animate-pulse`} />
            )}
          </div>
          <div className="flex items-center gap-2">
            {latestNonManualFeatures && (
              <span className="text-xs text-slate-400">
                {getExpressionName(latestNonManualFeatures.facialExpression.type)}
              </span>
            )}
            {expandedSection === 'facial' ? 
              <ChevronUp className="w-4 h-4 text-slate-400" /> : 
              <ChevronDown className="w-4 h-4 text-slate-400" />
            }
          </div>
        </button>

        {expandedSection === 'facial' && (
          <div className="px-4 pb-4 space-y-3 border-t border-slate-700/50">
            <div className="pt-3 flex items-center justify-between">
              <label className="flex items-center gap-2 cursor-pointer">
                <div 
                  onClick={() => setEnableFaceDetection(!enableFaceDetection)}
                  className={`w-9 h-5 rounded-full transition-colors relative ${
                    enableFaceDetection ? 'bg-pink-500' : 'bg-slate-600'
                  }`}
                >
                  <div className={`absolute top-0.5 w-4 h-4 bg-white rounded-full transition-transform ${
                    enableFaceDetection ? 'translate-x-4' : 'translate-x-0.5'
                  }`} />
                </div>
                <span className="text-sm text-slate-300">启用面部特征提取</span>
              </label>
            </div>

            {!enableFaceDetection && (
              <div className="text-center py-4 text-slate-500 text-xs">
                面部特征提取已禁用
              </div>
            )}

            {enableFaceDetection && !latestNonManualFeatures && (
              <div className="text-center py-4 text-slate-500 text-xs">
                <AlertCircle className="w-6 h-6 mx-auto mb-1 text-slate-600" />
                等待面部检测...
                <div className="text-slate-600 mt-1">请确保面部在摄像头范围内</div>
              </div>
            )}

            {enableFaceDetection && latestNonManualFeatures && (
              <>
                <div className="bg-slate-900/50 rounded-lg p-3">
                  <div className="text-xs text-slate-400 mb-2 flex items-center gap-1">
                    <Smile className="w-3 h-3" />
                    面部表情
                  </div>
                  <div className="space-y-2 text-xs">
                    <div className="flex items-center justify-between">
                      <span className="text-slate-500">表情类型</span>
                      <div className="flex items-center gap-2">
                        <span className={`w-2 h-2 rounded-full ${getExpressionColor(latestNonManualFeatures.facialExpression.type)}`} />
                        <span className={`font-medium ${
                          latestNonManualFeatures.facialExpression.confidence > 0.7 ? 'text-white' : 'text-slate-300'
                        }`}>
                          {getExpressionName(latestNonManualFeatures.facialExpression.type)}
                        </span>
                        <span className="text-slate-500">
                          {Math.round(latestNonManualFeatures.facialExpression.confidence * 100)}%
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-slate-500">抬眉程度</span>
                      <div className="flex items-center gap-1.5">
                        <div className="w-16 h-1.5 bg-slate-700 rounded-full overflow-hidden">
                          <div 
                            className="h-full bg-blue-400 transition-all"
                            style={{ width: `${latestNonManualFeatures.facialExpression.eyebrowRaise * 100}%` }}
                          />
                        </div>
                        <span className="text-blue-400 w-8 text-right">
                          {Math.round(latestNonManualFeatures.facialExpression.eyebrowRaise * 100)}%
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-slate-500">嘴部张开</span>
                      <div className="flex items-center gap-1.5">
                        <div className="w-16 h-1.5 bg-slate-700 rounded-full overflow-hidden">
                          <div 
                            className="h-full bg-pink-400 transition-all"
                            style={{ width: `${latestNonManualFeatures.facialExpression.mouthOpen * 100}%` }}
                          />
                        </div>
                        <span className="text-pink-400 w-8 text-right">
                          {Math.round(latestNonManualFeatures.facialExpression.mouthOpen * 100)}%
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-slate-500">嘴角上扬</span>
                      <div className="flex items-center gap-1.5">
                        <div className="w-16 h-1.5 bg-slate-700 rounded-full overflow-hidden">
                          <div 
                            className="h-full bg-green-400 transition-all"
                            style={{ width: `${latestNonManualFeatures.facialExpression.lipCornerRaise * 100}%` }}
                          />
                        </div>
                        <span className="text-green-400 w-8 text-right">
                          {Math.round(latestNonManualFeatures.facialExpression.lipCornerRaise * 100)}%
                        </span>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="bg-slate-900/50 rounded-lg p-3">
                  <div className="text-xs text-slate-400 mb-2">口形分析</div>
                  <div className="space-y-2 text-xs">
                    <div className="flex justify-between">
                      <span className="text-slate-500">口形类型</span>
                      <span className="text-purple-300 font-medium">
                        {getMouthShapeName(latestNonManualFeatures.mouthShape.type)}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">宽高比</span>
                      <span className="text-slate-300">
                        {latestNonManualFeatures.mouthShape.aspectRatio.toFixed(2)}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="bg-slate-900/50 rounded-lg p-3">
                  <div className="text-xs text-slate-400 mb-2">头部姿态</div>
                  <div className="space-y-2 text-xs">
                    <div className="flex justify-between">
                      <span className="text-slate-500">歪头角度</span>
                      <span className={`font-medium ${
                        Math.abs(latestNonManualFeatures.headTilt) > 10 ? 'text-yellow-400' : 'text-slate-300'
                      }`}>
                        {latestNonManualFeatures.headTilt > 0 ? '右倾' : 
                         latestNonManualFeatures.headTilt < 0 ? '左倾' : '正'}
                        {Math.abs(latestNonManualFeatures.headTilt) > 1 ? 
                          ` ${Math.abs(latestNonManualFeatures.headTilt).toFixed(1)}°` : ''}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">身体姿态</span>
                      <span className="text-cyan-300">{latestNonManualFeatures.bodyPosture}</span>
                    </div>
                  </div>
                </div>

                <div className="bg-gradient-to-r from-purple-500/10 to-pink-500/10 border border-purple-500/30 rounded-lg p-3">
                  <div className="text-xs text-purple-300 mb-1.5 flex items-center gap-1">
                    <Zap className="w-3 h-3" />
                    非手控特征融合
                  </div>
                  <div className="text-xs text-slate-400">
                    {contextState.sentenceType === 'question' && latestNonManualFeatures.facialExpression.type === 'questioning' && (
                      <span className="text-green-400 flex items-center gap-1">
                        <CheckCircle2 className="w-3 h-3" />
                        疑问表情与疑问句匹配，置信度提升
                      </span>
                    )}
                    {contextState.sentenceType === 'negative' && latestNonManualFeatures.facialExpression.type === 'negative' && (
                      <span className="text-green-400 flex items-center gap-1">
                        <CheckCircle2 className="w-3 h-3" />
                        否定表情与否定句匹配，置信度提升
                      </span>
                    )}
                    {contextState.sentenceType === 'declarative' && 
                     (latestNonManualFeatures.facialExpression.type === 'affirmative' || 
                      latestNonManualFeatures.facialExpression.type === 'happy') && (
                      <span className="text-green-400 flex items-center gap-1">
                        <CheckCircle2 className="w-3 h-3" />
                        肯定表情与陈述句匹配，置信度提升
                      </span>
                    )}
                    {contextState.sentenceType === 'question' && 
                     latestNonManualFeatures.facialExpression.type !== 'questioning' &&
                     latestNonManualFeatures.facialExpression.type !== 'surprised' && (
                      <span className="text-yellow-400 flex items-center gap-1">
                        <XCircle className="w-3 h-3" />
                        疑问句缺少疑问表情（抬眉+歪头）
                      </span>
                    )}
                    {contextState.sentenceType === 'unknown' && (
                      <span className="text-slate-400">
                        等待更多输入以进行语法-表情一致性校验
                      </span>
                    )}
                  </div>
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default EnhancedFeaturesPanel;
