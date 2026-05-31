import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Download, ArrowLeft, Share2, FileText, Clock } from 'lucide-react';
import { useAppStore } from '@/store';
import { getAnalysisResult, getHistoryItem, exportResult } from '@/services/api';
import { EmotionDisplay } from '@/components/emotion/EmotionDisplay';
import { EmotionPieChart } from '@/components/charts/EmotionPieChart';
import { ValenceArousalChart } from '@/components/charts/ValenceArousalChart';
import { AttentionHeatmap } from '@/components/charts/AttentionHeatmap';
import { EmotionTimeSeries } from '@/components/charts/EmotionTimeSeries';
import { ModalityContribution } from '@/components/charts/ModalityContribution';
import { downloadFile, formatPercent } from '@/utils';
import type { EmotionResult } from '@/types';

export function ResultPage() {
  const { id } = useParams<{ id: string }>();
  const { analysis, setAnalysisResult } = useAppStore();
  const [result, setResult] = useState<EmotionResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'overview' | 'modalities' | 'timeseries' | 'attention'>('overview');

  useEffect(() => {
    const loadResult = async () => {
      if (!id) return;

      try {
        setLoading(true);

        if (analysis.result && analysis.result.id === id) {
          setResult(analysis.result);
          return;
        } else {
            let data: EmotionResult;
            try {
              const response = await getAnalysisResult(id);
              data = (await response).result;
            } catch {
              data = await getHistoryItem(id);
            }
            setResult(data);
            setAnalysisResult(data);
          }
      } catch (err) {
        setError(err instanceof Error ? err.message : '加载失败');
      } finally {
        setLoading(false);
      }
    };

    loadResult();
  }, [id, analysis.result, setAnalysisResult]);

  const handleExport = async (format: 'json' | 'csv') => {
    if (!id) return;
    try {
      const blob = await exportResult(id, format);
      const filename = `emotion-analysis-${id}.${format}`;
      downloadFile(blob, filename);
    } catch (err) {
      console.error('Export failed:', err);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen pt-24 pb-12 flex items-center justify-center">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-muted-foreground">正在加载分析结果...</p>
        </div>
      </div>
    );
  }

  if (error || !result) {
    return (
      <div className="min-h-screen pt-24 pb-12 flex items-center justify-center">
      <div className="text-center glass-card p-8">
        <p className="text-red-400 mb-4">{error || '未找到分析结果'}</p>
        <Link to="/record" className="btn-primary">
          返回录制新的分析
        </Link>
      </div>
    </div>
    );
  }

  const tabs = [
    { id: 'overview', label: '概览' },
    { id: 'modalities', label: '模态分析' },
    { id: 'timeseries', label: '时序变化' },
    { id: 'attention', label: '注意力解释' },
  ] as const;

  return (
    <div className="min-h-screen pt-24 pb-12">
      <div className="container mx-auto px-4">
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-4">
            <Link to="/record" className="p-2 rounded-lg bg-white/5 hover:bg-white/10 transition-colors">
              <ArrowLeft className="w-5 h-5" />
            </Link>
            <div>
              <h1 className="text-3xl font-bold font-display">
              分析<span className="text-gradient">结果报告</span>
            </h1>
              <p className="text-sm text-muted-foreground flex items-center gap-2">
                <Clock className="w-4 h-4" />
                {new Date(result.timestamp).toLocaleString('zh-CN')}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => handleExport('json')} className="btn-secondary flex items-center gap-2">
              <Download className="w-4 h-4" />
              导出 JSON
            </button>
            <button className="p-2 rounded-lg bg-white/5 hover:bg-white/10 transition-colors">
              <Share2 className="w-5 h-5" />
            </button>
          </div>
        </div>

        <div className="flex gap-2 mb-8 overflow-x-auto pb-2">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-6 py-3 rounded-xl font-medium transition-all whitespace-nowrap ${
                activeTab === tab.id
                  ? 'bg-primary text-white'
                  : 'bg-white/5 text-muted-foreground hover:bg-white/10'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {activeTab === 'overview' && (
          <div className="grid lg:grid-cols-3 gap-6">
            <div className="lg:col-span-1">
              <div className="glass-card p-6 h-full">
                <h2 className="text-xl font-bold mb-6 text-center">主要情感</h2>
                <EmotionDisplay
                  probabilities={result.emotion.probabilities}
                  size="lg"
                />
              </div>
            </div>

            <div className="lg:col-span-2 space-y-6">
              <div className="glass-card p-6">
                <h2 className="text-xl font-bold mb-4">情感分布</h2>
                <EmotionPieChart
                  probabilities={result.emotion.probabilities}
                  size={280}
                />
              </div>

              <div className="grid md:grid-cols-2 gap-6">
                <div className="glass-card p-6">
                <h2 className="text-xl font-bold mb-4">效价唤醒度</h2>
                <ValenceArousalChart
                  current={result.valenceArousal}
                  history={result.timeSeries.slice(-20)}
                  size={280}
                />
              </div>

              <div className="glass-card p-6">
                <h2 className="text-xl font-bold mb-4">语音转写文本</h2>
                <div className="flex items-start gap-3 p-4 rounded-xl bg-white/5 h-[280px] overflow-y-auto">
                  <FileText className="w-5 h-5 text-primary flex-shrink-0 mt-1" />
                  <p className="text-muted-foreground leading-relaxed">
                    {result.transcript || '未检测到语音内容'}
                  </p>
                </div>
              </div>
            </div>
            </div>
          </div>
        )}

        {activeTab === 'modalities' && (
          <div className="space-y-6">
            <div className="glass-card p-6">
              <h2 className="text-xl font-bold mb-6">模态贡献度分析</h2>
              <ModalityContribution modalities={result.modalities} />
            </div>

            <div className="grid md:grid-cols-3 gap-6">
              {(['audio', 'video', 'text'] as const).map((modality) => (
                <div key={modality} className="glass-card p-6">
                  <h3 className="text-lg font-bold mb-4" style={{ color: `var(--modality-${modality})` }}>
                  {modality === 'audio' ? '语音模态' : modality === 'video' ? '视频模态' : '文本模态'}
                </h3>
                <EmotionPieChart
                  probabilities={result.modalities[modality].emotionProbabilities}
                  size={220}
                  showLegend={false}
                />
                <div className="mt-4 text-center">
                  <p className="text-sm text-muted-foreground">贡献度</p>
                  <p className="text-2xl font-bold font-mono" style={{ color: `var(--modality-${modality})` }}>
                    {formatPercent(result.modalities[modality].contribution)}
                  </p>
                </div>
              </div>
            ))}
            </div>
          </div>
        )}

        {activeTab === 'timeseries' && (
          <div className="space-y-6">
            <div className="glass-card p-6">
              <h2 className="text-xl font-bold mb-6">情感时序变化</h2>
              <EmotionTimeSeries
                data={result.timeSeries}
                height={400}
              />
            </div>

            <div className="glass-card p-6">
              <h2 className="text-xl font-bold mb-6">效价唤醒度轨迹</h2>
              <ValenceArousalChart
                current={result.valenceArousal}
                history={result.timeSeries}
                size={350}
              />
            </div>
          </div>
        )}

        {activeTab === 'attention' && (
          <div className="space-y-6">
            <div className="glass-card p-6">
              <h2 className="text-xl font-bold mb-2">跨模态注意力权重热图</h2>
              <p className="text-muted-foreground mb-6 text-sm">
                展示不同时间步各模态对情感预测的贡献权重，颜色越深表示该模态在该时间点的影响越大</p>
              <AttentionHeatmap
                data={result.attentionWeights}
                height={200}
              />
            </div>

            <div className="glass-card p-6">
              <h2 className="text-xl font-bold mb-6">时序注意力权重变化</h2>
              <EmotionTimeSeries
                data={result.timeSeries}
                height={300}
                showValenceArousal={false}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default ResultPage;
