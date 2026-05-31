import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  ArrowLeft,
  Play,
  Pause,
  Volume2,
  Settings,
  BarChart3,
  Music2,
  Download,
  Edit3,
  Loader2,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import {
  getScore,
  updateScore,
  synthesizeScore,
  evaluateDifficulty,
  getStyles,
  getGongche,
} from '@/services/api';
import type { SerializedScore, GuqinStyle, DifficultyReport } from '@/types/index';

const ScoreDetailPage: React.FC = () => {
  const { scoreId } = useParams<{ scoreId: string }>();
  const [score, setScore] = useState<SerializedScore | null>(null);
  const [loading, setLoading] = useState(true);
  const [currentPage, setCurrentPage] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [selectedStyle, setSelectedStyle] = useState('traditional');
  const [tempo, setTempo] = useState(60);
  const [styles, setStyles] = useState<GuqinStyle[]>([]);
  const [difficultyReport, setDifficultyReport] = useState<DifficultyReport | null>(null);
  const [showDifficulty, setShowDifficulty] = useState(false);
  const [showGongche, setShowGongche] = useState(false);
  const [gongcheData, setGongcheData] = useState<any>(null);
  const [synthesizing, setSynthesizing] = useState(false);
  const [evaluating, setEvaluating] = useState(false);
  const [selectedJianziIndex, setSelectedJianziIndex] = useState<number | null>(null);

  useEffect(() => {
    loadScore();
    loadStyles();
  }, [scoreId]);

  const loadScore = async () => {
    if (!scoreId) return;
    try {
      setLoading(true);
      const data = await getScore(scoreId);
      setScore(data);
      setSelectedStyle(data.audio_synthesis_params.style);
      setTempo(data.audio_synthesis_params.tempo);
    } catch (error) {
      console.error('Failed to load score:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadStyles = async () => {
    try {
      const data = await getStyles();
      setStyles(data);
    } catch (error) {
      console.error('Failed to load styles:', error);
    }
  };

  const handleSynthesize = async () => {
    if (!scoreId) return;
    try {
      setSynthesizing(true);
      const result = await synthesizeScore(scoreId, selectedStyle, tempo);
      if (result.success) {
        setAudioUrl(`http://localhost:5000${result.audio_url}`);
      }
    } catch (error) {
      console.error('Failed to synthesize:', error);
    } finally {
      setSynthesizing(false);
    }
  };

  const handleEvaluate = async () => {
    if (!scoreId) return;
    try {
      setEvaluating(true);
      const result = await evaluateDifficulty(scoreId);
      if (result.success) {
        setDifficultyReport(result.report);
        setShowDifficulty(true);
      }
    } catch (error) {
      console.error('Failed to evaluate:', error);
    } finally {
      setEvaluating(false);
    }
  };

  const handleShowGongche = async () => {
    if (!score) return;
    try {
      const data = await getGongche(undefined, score.jianzi_sequence);
      setGongcheData(data);
      setShowGongche(true);
    } catch (error) {
      console.error('Failed to load gongche:', error);
    }
  };

  const handleUpdateParams = async () => {
    if (!scoreId) return;
    try {
      await updateScore(scoreId, {
        audio_synthesis_params: {
          tempo,
          style: selectedStyle,
        },
      });
    } catch (error) {
      console.error('Failed to update params:', error);
    }
  };

  const getDifficultyColor = (score: number) => {
    if (score < 2.5) return 'text-green-600';
    if (score < 4.0) return 'text-lime-600';
    if (score < 5.5) return 'text-yellow-600';
    if (score < 7.0) return 'text-orange-600';
    return 'text-red-600';
  };

  const getDifficultyBg = (score: number) => {
    if (score < 2.5) return 'bg-green-500';
    if (score < 4.0) return 'bg-lime-500';
    if (score < 5.5) return 'bg-yellow-500';
    if (score < 7.0) return 'bg-orange-500';
    return 'bg-red-500';
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#F5F0E6] flex items-center justify-center">
        <Loader2 className="animate-spin text-[#C0392B]" size={48} />
      </div>
    );
  }

  if (!score) {
    return (
      <div className="min-h-screen bg-[#F5F0E6] flex flex-col items-center justify-center">
        <p className="text-[#4A2C1A]/60 mb-4">曲目不存在</p>
        <Link to="/library" className="text-[#C0392B] hover:underline">
          返回曲谱库
        </Link>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#F5F0E6]">
      <div className="bg-white border-b border-[#4A2C1A]/10 sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Link
                to="/library"
                className="p-2 hover:bg-[#4A2C1A]/10 rounded-lg transition-colors"
              >
                <ArrowLeft size={20} />
              </Link>
              <div>
                <h1 className="text-2xl font-bold text-[#4A2C1A]">{score.metadata.title}</h1>
                <p className="text-sm text-[#4A2C1A]/60">
                  {score.metadata.composer} · {score.metadata.dynasty} ·{' '}
                  {score.metadata.difficulty}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={handleSynthesize}
                disabled={synthesizing}
                className="flex items-center gap-2 bg-[#C0392B] text-white px-4 py-2 rounded-lg hover:bg-[#A93226] transition-colors disabled:opacity-50"
              >
                {synthesizing ? (
                  <Loader2 size={18} className="animate-spin" />
                ) : playing ? (
                  <Pause size={18} />
                ) : (
                  <Play size={18} />
                )}
                {synthesizing ? '合成中...' : playing ? '暂停' : '播放'}
              </button>
              <button
                onClick={handleEvaluate}
                disabled={evaluating}
                className="flex items-center gap-2 bg-white border border-[#4A2C1A]/20 text-[#4A2C1A] px-4 py-2 rounded-lg hover:bg-[#4A2C1A]/5 transition-colors disabled:opacity-50"
              >
                {evaluating ? (
                  <Loader2 size={18} className="animate-spin" />
                ) : (
                  <BarChart3 size={18} />
                )}
                难度评估
              </button>
              <button
                onClick={handleShowGongche}
                className="flex items-center gap-2 bg-white border border-[#4A2C1A]/20 text-[#4A2C1A] px-4 py-2 rounded-lg hover:bg-[#4A2C1A]/5 transition-colors"
              >
                <Music2 size={18} />
                工尺谱
              </button>
              <button className="p-2 bg-white border border-[#4A2C1A]/20 text-[#4A2C1A] rounded-lg hover:bg-[#4A2C1A]/5 transition-colors">
                <Download size={18} />
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 py-6">
        <div className="grid grid-cols-4 gap-6">
          <div className="col-span-3 space-y-6">
            <div className="bg-white rounded-xl shadow-md overflow-hidden">
              <div className="bg-[#4A2C1A] text-white px-4 py-2 flex items-center justify-between">
                <span className="font-medium">
                  第 {currentPage + 1} 页 / 共 {score.pages.length} 页
                </span>
                <div className="flex gap-2">
                  <button
                    onClick={() => setCurrentPage((p) => Math.max(0, p - 1))}
                    disabled={currentPage === 0}
                    className="p-1 hover:bg-white/20 rounded disabled:opacity-30"
                  >
                    <ChevronLeft size={20} />
                  </button>
                  <button
                    onClick={() =>
                      setCurrentPage((p) => Math.min(score.pages.length - 1, p + 1))
                    }
                    disabled={currentPage === score.pages.length - 1}
                    className="p-1 hover:bg-white/20 rounded disabled:opacity-30"
                  >
                    <ChevronRight size={20} />
                  </button>
                </div>
              </div>
              <div className="relative">
                <img
                  src={`http://localhost:5000${score.pages[currentPage].image_path}`}
                  alt={`Page ${currentPage + 1}`}
                  className="w-full"
                />
              </div>
            </div>

            <div className="bg-white rounded-xl shadow-md p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-[#4A2C1A]">减字序列</h3>
                <span className="text-sm text-[#4A2C1A]/60">
                  共 {score.jianzi_sequence.length} 个减字
                </span>
              </div>
              <div className="overflow-x-auto">
                <div className="flex gap-2 pb-2 min-w-max">
                  {score.jianzi_sequence.map((jianzi, index) => (
                    <div
                      key={jianzi.id || index}
                      onClick={() => setSelectedJianziIndex(index)}
                      className={`cursor-pointer rounded-lg overflow-hidden border-2 transition-all ${
                        selectedJianziIndex === index
                          ? 'border-[#C0392B] shadow-lg scale-105'
                          : 'border-transparent hover:border-[#4A2C1A]/30'
                      }`}
                    >
                      <div className="w-16 h-20 bg-[#F5F0E6] flex items-center justify-center">
                        {jianzi.recognized ? (
                          <div className="text-center">
                            <div className="text-xs text-[#4A2C1A]/60">{jianzi.technique || '-'}</div>
                            <div className="text-lg font-bold text-[#4A2C1A]">
                              {jianzi.string || '-'}
                            </div>
                            <div className="text-xs text-[#4A2C1A]/60">{jianzi.hui || '-'}</div>
                          </div>
                        ) : (
                          <span className="text-[#4A2C1A]/30 text-xs">未识别</span>
                        )}
                      </div>
                      <div className="text-center text-xs py-1 bg-white">
                        {index + 1}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          <div className="space-y-6">
            <div className="bg-white rounded-xl shadow-md p-5">
              <h3 className="text-lg font-semibold text-[#4A2C1A] mb-4 flex items-center gap-2">
                <Settings size={20} />
                合成参数
              </h3>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-[#4A2C1A] mb-2">
                    演奏流派
                  </label>
                  <select
                    value={selectedStyle}
                    onChange={(e) => setSelectedStyle(e.target.value)}
                    onBlur={handleUpdateParams}
                    className="w-full px-3 py-2 border border-[#4A2C1A]/20 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#C0392B]/30"
                  >
                    {styles.map((style) => (
                      <option key={style.id} value={style.id}>
                        {style.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-[#4A2C1A] mb-2">
                    速度: {tempo} BPM
                  </label>
                  <input
                    type="range"
                    min="30"
                    max="120"
                    value={tempo}
                    onChange={(e) => setTempo(Number(e.target.value))}
                    onMouseUp={handleUpdateParams}
                    onTouchEnd={handleUpdateParams}
                    className="w-full h-2 bg-[#4A2C1A]/20 rounded-lg appearance-none cursor-pointer accent-[#C0392B]"
                  />
                </div>
                {audioUrl && (
                  <div className="pt-4 border-t border-[#4A2C1A]/10">
                    <audio controls src={audioUrl} className="w-full" />
                  </div>
                )}
              </div>
            </div>

            {selectedStyle && styles.length > 0 && (
              <div className="bg-white rounded-xl shadow-md p-5">
                <h3 className="text-lg font-semibold text-[#4A2C1A] mb-3">
                  {styles.find((s) => s.id === selectedStyle)?.name}
                </h3>
                <p className="text-sm text-[#4A2C1A]/70 leading-relaxed">
                  {styles.find((s) => s.id === selectedStyle)?.description}
                </p>
                {styles.find((s) => s.id === selectedStyle)?.params && (
                  <div className="mt-4 space-y-2">
                    <div className="text-xs text-[#4A2C1A]/60">风格参数：</div>
                    {Object.entries(
                      styles.find((s) => s.id === selectedStyle)?.params || {}
                    ).map(([key, value]) => (
                      <div key={key} className="flex justify-between text-sm">
                        <span className="text-[#4A2C1A]/70">
                          {key
                            .replace(/([A-Z])/g, ' $1')
                            .replace(/_/g, ' ')
                            .trim()}
                        </span>
                        <span className="text-[#4A2C1A] font-medium">
                          {value.toFixed(2)}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {difficultyReport && (
              <div className="bg-white rounded-xl shadow-md p-5">
                <h3 className="text-lg font-semibold text-[#4A2C1A] mb-3">难度概览</h3>
                <div className="text-center mb-4">
                  <div
                    className={`text-4xl font-bold ${getDifficultyColor(
                      difficultyReport.overall.score
                    )}`}
                  >
                    {difficultyReport.overall.score.toFixed(1)}
                  </div>
                  <div className="text-[#4A2C1A]/60">{difficultyReport.overall.level}</div>
                </div>
                <div className="space-y-2">
                  {Object.entries(difficultyReport.categories).map(([key, value]) => (
                    <div key={key}>
                      <div className="flex justify-between text-sm mb-1">
                        <span className="text-[#4A2C1A]/70">
                          {key
                            .replace(/([A-Z])/g, ' $1')
                            .replace(/_/g, ' ')
                            .trim()}
                        </span>
                        <span className="text-[#4A2C1A]">{value.toFixed(1)}</span>
                      </div>
                      <div className="h-2 bg-[#4A2C1A]/10 rounded-full overflow-hidden">
                        <div
                          className={`h-full ${getDifficultyBg(value)}`}
                          style={{ width: `${(value / 10) * 100}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {showDifficulty && difficultyReport && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl max-w-4xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b border-[#4A2C1A]/10 flex justify-between items-center">
              <h2 className="text-2xl font-bold text-[#4A2C1A]">难度评估报告</h2>
              <button
                onClick={() => setShowDifficulty(false)}
                className="p-2 hover:bg-[#4A2C1A]/10 rounded-lg"
              >
                ✕
              </button>
            </div>
            <div className="p-6 space-y-6">
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-gradient-to-br from-[#4A2C1A]/5 to-[#C0392B]/5 rounded-xl p-6 text-center">
                  <div
                    className={`text-5xl font-bold ${getDifficultyColor(
                      difficultyReport.overall.score
                    )}`}
                  >
                    {difficultyReport.overall.score.toFixed(1)}
                  </div>
                  <div className="text-xl text-[#4A2C1A] mt-2">
                    {difficultyReport.overall.level}
                  </div>
                  <p className="text-sm text-[#4A2C1A]/60 mt-1">
                    {difficultyReport.overall.description}
                  </p>
                </div>
                <div className="bg-[#4A2C1A]/5 rounded-xl p-6">
                  <h4 className="font-semibold text-[#4A2C1A] mb-3">统计信息</h4>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-[#4A2C1A]/70">总音符数</span>
                      <span className="text-[#4A2C1A] font-medium">
                        {difficultyReport.summary.total_notes}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[#4A2C1A]/70">平均难度</span>
                      <span className="text-[#4A2C1A] font-medium">
                        {difficultyReport.summary.avg_difficulty.toFixed(1)}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[#4A2C1A]/70">最高难度</span>
                      <span className="text-[#4A2C1A] font-medium">
                        {difficultyReport.summary.max_difficulty.toFixed(1)}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[#4A2C1A]/70">技巧多样性</span>
                      <span className="text-[#4A2C1A] font-medium">
                        {difficultyReport.summary.technique_variety.toFixed(1)}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              <div>
                <h4 className="font-semibold text-[#4A2C1A] mb-3">各维度得分</h4>
                <div className="grid grid-cols-2 gap-4">
                  {Object.entries(difficultyReport.categories).map(([key, value]) => (
                    <div key={key} className="bg-white rounded-lg p-4 border border-[#4A2C1A]/10">
                      <div className="flex justify-between items-center mb-2">
                        <span className="text-[#4A2C1A] font-medium">
                          {key
                            .replace(/([A-Z])/g, ' $1')
                            .replace(/_/g, ' ')
                            .trim()}
                        </span>
                        <span
                          className={`font-bold ${getDifficultyColor(value)}`}
                        >
                          {value.toFixed(1)}
                        </span>
                      </div>
                      <div className="h-2 bg-[#4A2C1A]/10 rounded-full overflow-hidden">
                        <div
                          className={`h-full ${getDifficultyBg(value)}`}
                          style={{ width: `${(value / 10) * 100}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <h4 className="font-semibold text-[#4A2C1A] mb-3">练习建议</h4>
                <ul className="space-y-2">
                  {difficultyReport.recommendations.map((rec, i) => (
                    <li
                      key={i}
                      className="flex items-start gap-2 bg-[#C0392B]/5 rounded-lg p-3 text-sm text-[#4A2C1A]"
                    >
                      <span className="text-[#C0392B]">•</span>
                      {rec}
                    </li>
                  ))}
                </ul>
              </div>

              <div>
                <h4 className="font-semibold text-[#4A2C1A] mb-3">逐音难度分析</h4>
                <div className="max-h-60 overflow-y-auto space-y-2">
                  {difficultyReport.note_details.slice(0, 20).map((note) => (
                    <div
                      key={note.sequence_id}
                      className="flex items-center justify-between bg-white rounded-lg p-3 border border-[#4A2C1A]/10"
                    >
                      <div className="flex items-center gap-3">
                        <span className="w-8 h-8 bg-[#4A2C1A]/10 rounded-full flex items-center justify-center text-sm font-medium text-[#4A2C1A]">
                          {note.sequence_id + 1}
                        </span>
                        <div>
                          <div className="text-[#4A2C1A] font-medium">
                            {note.technique} {note.string}弦 {note.hui}徽
                          </div>
                          <div className="text-xs text-[#4A2C1A]/60">
                            {note.explanations.join('；')}
                          </div>
                        </div>
                      </div>
                      <span
                        className={`text-lg font-bold ${getDifficultyColor(
                          note.difficulty_score
                        )}`}
                      >
                        {note.difficulty_score.toFixed(1)}
                      </span>
                    </div>
                  ))}
                  {difficultyReport.note_details.length > 20 && (
                    <div className="text-center text-sm text-[#4A2C1A]/60 py-2">
                      ... 还有 {difficultyReport.note_details.length - 20} 个音符
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {showGongche && gongcheData && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl max-w-4xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b border-[#4A2C1A]/10 flex justify-between items-center">
              <h2 className="text-2xl font-bold text-[#4A2C1A]">工尺谱对照</h2>
              <button
                onClick={() => setShowGongche(false)}
                className="p-2 hover:bg-[#4A2C1A]/10 rounded-lg"
              >
                ✕
              </button>
            </div>
            <div className="p-6">
              <div className="overflow-x-auto">
                <table className="w-full border-collapse">
                  <thead>
                    <tr className="bg-[#4A2C1A]/5">
                      <th className="px-4 py-2 text-left text-sm font-medium text-[#4A2C1A] border-b">
                        序号
                      </th>
                      <th className="px-4 py-2 text-left text-sm font-medium text-[#4A2C1A] border-b">
                        减字
                      </th>
                      <th className="px-4 py-2 text-left text-sm font-medium text-[#4A2C1A] border-b">
                        工尺
                      </th>
                      <th className="px-4 py-2 text-left text-sm font-medium text-[#4A2C1A] border-b">
                        音高
                      </th>
                      <th className="px-4 py-2 text-left text-sm font-medium text-[#4A2C1A] border-b">
                        指法
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {gongcheData.gongche_list?.slice(0, 30).map((item: any, index: number) => (
                      <tr key={index} className="border-b border-[#4A2C1A]/10 hover:bg-[#4A2C1A]/5">
                        <td className="px-4 py-2 text-sm text-[#4A2C1A]/60">{index + 1}</td>
                        <td className="px-4 py-2 text-sm text-[#4A2C1A]">
                          {item.jianzi || '-'}
                        </td>
                        <td className="px-4 py-2 text-lg font-bold text-[#C0392B]">
                          {item.gongche || '-'}
                        </td>
                        <td className="px-4 py-2 text-sm text-[#4A2C1A]">
                          {item.pitch || '-'}
                        </td>
                        <td className="px-4 py-2 text-sm text-[#4A2C1A]/70">
                          {item.technique || '-'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ScoreDetailPage;
