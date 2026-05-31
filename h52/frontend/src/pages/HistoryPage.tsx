import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { History, Trash2, Eye, ArrowLeft, ArrowRight, Calendar, Clock, Search, Filter } from 'lucide-react';
import { getHistory, deleteHistoryItem } from '@/services/api';
import { formatPercent, generateMockHistoryItems } from '@/utils';
import { EMOTION_LABELS, EMOTION_COLORS } from '@/types';
import type { HistoryItem, EmotionCategory } from '@/types';

export function HistoryPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterEmotion, setFilterEmotion] = useState<EmotionCategory | 'all'>('all');
  const pageSize = 10;

  useEffect(() => {
    const loadHistory = async () => {
      try {
        setLoading(true);
        const data = await getHistory(page, pageSize);
        setItems(data.items);
        setTotal(data.total);
      } catch {
        const mockData = generateMockHistoryItems(15);
        const start = (page - 1) * pageSize;
        const end = start + pageSize;
        setItems(mockData.slice(start, end));
        setTotal(mockData.length);
      } finally {
        setLoading(false);
      }
    };

    loadHistory();
  }, [page]);

  const handleDelete = async (id: string) => {
    if (!confirm('确定要删除这条记录吗？')) return;
    try {
      await deleteHistoryItem(id);
      setItems(items.filter(item => item.id !== id));
    } catch {
      setItems(items.filter(item => item.id !== id));
    }
  };

  const filteredItems = items.filter(item => {
    const matchesSearch = searchQuery === '' || 
      EMOTION_LABELS[item.primaryEmotion].includes(searchQuery);
    const matchesEmotion = filterEmotion === 'all' || item.primaryEmotion === filterEmotion;
    return matchesSearch && matchesEmotion;
  });

  const totalPages = Math.ceil(total / pageSize);

  const getValenceLabel = (valence: number) => {
    if (valence > 0.3) return '积极';
    if (valence < -0.3) return '消极';
    return '中性';
  };

  const getArousalLabel = (arousal: number) => {
    if (arousal > 0.3) return '高唤醒';
    if (arousal < -0.3) return '低唤醒';
    return '中唤醒';
  };

  return (
    <div className="min-h-screen pt-24 pb-12">
      <div className="container mx-auto px-4">
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-4">
            <Link to="/" className="p-2 rounded-lg bg-white/5 hover:bg-white/10 transition-colors">
              <ArrowLeft className="w-5 h-5" />
            </Link>
            <div>
              <h1 className="text-3xl font-bold font-display">
                分析<span className="text-gradient">历史记录</span>
              </h1>
              <p className="text-sm text-muted-foreground">
                共 {total} 条记录
              </p>
            </div>
          </div>

          <Link to="/record" className="btn-primary">
            新建分析
          </Link>
        </div>

        <div className="glass-card p-4 mb-6">
          <div className="flex flex-col md:flex-row gap-4">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="搜索情感类型..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none focus:border-primary transition-colors"
              />
            </div>
            <div className="flex items-center gap-2">
              <Filter className="w-4 h-4 text-muted-foreground" />
              <select
                value={filterEmotion}
                onChange={(e) => setFilterEmotion(e.target.value as EmotionCategory | 'all')}
                className="px-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none focus:border-primary transition-colors"
              >
                <option value="all">全部情感</option>
                {(Object.keys(EMOTION_LABELS) as EmotionCategory[]).map(emotion => (
                  <option key={emotion} value={emotion}>
                    {EMOTION_LABELS[emotion]}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="text-center">
              <div className="w-12 h-12 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-4" />
              <p className="text-muted-foreground">加载中...</p>
            </div>
          </div>
        ) : filteredItems.length === 0 ? (
          <div className="glass-card p-12 text-center">
            <History className="w-16 h-16 mx-auto mb-4 text-muted-foreground/50" />
            <h3 className="text-xl font-bold mb-2">暂无记录</h3>
            <p className="text-muted-foreground mb-6">还没有分析记录，开始您的第一次情感分析吧</p>
            <Link to="/record" className="btn-primary">
              开始分析
            </Link>
          </div>
        ) : (
          <>
            <div className="space-y-4">
              {filteredItems.map((item, index) => (
                <div
                  key={item.id}
                  className="glass-card p-4 hover:bg-white/5 transition-colors animate-fade-in"
                  style={{ animationDelay: `${index * 50}ms` }}
                >
                  <div className="flex flex-col md:flex-row md:items-center gap-4">
                    <div
                      className="w-16 h-16 rounded-2xl flex items-center justify-center text-2xl font-bold flex-shrink-0"
                      style={{ backgroundColor: `${EMOTION_COLORS[item.primaryEmotion]}20`, color: EMOTION_COLORS[item.primaryEmotion] }}
                    >
                      {EMOTION_LABELS[item.primaryEmotion].charAt(0)}
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex flex-wrap items-center gap-3 mb-2">
                        <h3 className="font-semibold text-lg">
                          <span style={{ color: EMOTION_COLORS[item.primaryEmotion] }}>
                            {EMOTION_LABELS[item.primaryEmotion]}
                          </span>
                          <span className="text-muted-foreground ml-2">
                            {formatPercent(item.confidence)} 置信度
                          </span>
                        </h3>
                      </div>
                      <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
                        <span className="flex items-center gap-1">
                          <Calendar className="w-4 h-4" />
                          {new Date(item.createdAt).toLocaleDateString('zh-CN')}
                        </span>
                        <span className="flex items-center gap-1">
                          <Clock className="w-4 h-4" />
                          {new Date(item.createdAt).toLocaleTimeString('zh-CN')}
                        </span>
                        <span>时长: {item.duration}秒</span>
                        <span className="px-2 py-0.5 rounded-full text-xs bg-white/10">
                          {getValenceLabel(item.valence)} · {getArousalLabel(item.arousal)}
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 flex-shrink-0">
                      <button
                        onClick={() => navigate(`/result/${item.id}`)}
                        className="p-2 rounded-lg bg-white/5 hover:bg-white/10 transition-colors"
                        title="查看详情"
                      >
                        <Eye className="w-5 h-5" />
                      </button>
                      <button
                        onClick={() => handleDelete(item.id)}
                        className="p-2 rounded-lg bg-white/5 hover:bg-red-500/20 text-red-400 transition-colors"
                        title="删除"
                      >
                        <Trash2 className="w-5 h-5" />
                      </button>
                    </div>
                  </div>

                  <div className="mt-4 grid grid-cols-7 gap-1">
                    {(Object.keys(EMOTION_LABELS) as EmotionCategory[]).map(emotion => (
                      <div key={emotion} className="text-center">
                        <div
                          className="h-1 rounded-full mx-0.5"
                          style={{
                            backgroundColor: emotion === item.primaryEmotion
                              ? EMOTION_COLORS[emotion]
                              : `${EMOTION_COLORS[emotion]}40`,
                            height: emotion === item.primaryEmotion ? '8px' : '4px',
                          }}
                        />
                        <p className="text-[10px] text-muted-foreground mt-1 truncate">
                          {EMOTION_LABELS[emotion]}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>

            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-2 mt-8">
                <button
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="p-2 rounded-lg bg-white/5 hover:bg-white/10 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  <ArrowLeft className="w-5 h-5" />
                </button>
                {Array.from({ length: totalPages }, (_, i) => i + 1).map(p => (
                  <button
                    key={p}
                    onClick={() => setPage(p)}
                    className={`w-10 h-10 rounded-lg font-medium transition-all ${
                      page === p
                        ? 'bg-primary text-white'
                        : 'bg-white/5 hover:bg-white/10'
                    }`}
                  >
                    {p}
                  </button>
                ))}
                <button
                  onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  className="p-2 rounded-lg bg-white/5 hover:bg-white/10 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  <ArrowRight className="w-5 h-5" />
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export default HistoryPage;
