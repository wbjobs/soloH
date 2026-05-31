import { useState, useEffect } from 'react';
import { storageService } from '@/services/storageService';
import { ErrorStatistics, ErrorRecord } from '@/types';
import { getErrorTypeName } from '@/data/grammarRules';
import {
  PieChart,
  Pie,
  Cell,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar
} from 'recharts';
import {
  BarChart3,
  TrendingDown,
  Download,
  Trash2,
  Calendar,
  AlertTriangle,
  CheckCircle2,
  Clock,
  ChevronRight
} from 'lucide-react';

const COLORS = ['#FF6B6B', '#4ECDC4', '#FFD93D', '#6C5CE7', '#A8E6CF', '#FF8C42'];

const Statistics = () => {
  const [statistics, setStatistics] = useState<ErrorStatistics | null>(null);
  const [records, setRecords] = useState<ErrorRecord[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [todayCount, setTodayCount] = useState(0);
  const [weeklyCount, setWeeklyCount] = useState(0);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setIsLoading(true);
    try {
      const [stats, recs, today, weekly] = await Promise.all([
        storageService.getStatistics(),
        storageService.getErrorRecords(50),
        storageService.getTodayErrorCount(),
        storageService.getWeeklyErrorCount()
      ]);
      setStatistics(stats);
      setRecords(recs);
      setTodayCount(today);
      setWeeklyCount(weekly);
    } catch (e) {
      console.error('Failed to load statistics:', e);
    } finally {
      setIsLoading(false);
    }
  };

  const handleExport = async () => {
    try {
      await storageService.downloadExport();
    } catch (e) {
      console.error('Export failed:', e);
    }
  };

  const handleClear = async () => {
    if (window.confirm('确定要清除所有历史数据吗？此操作不可恢复。')) {
      try {
        await storageService.clearErrorRecords();
        await loadData();
      } catch (e) {
        console.error('Clear failed:', e);
      }
    }
  };

  const handleDeleteRecord = async (id: string) => {
    try {
      await storageService.deleteErrorRecord(id);
      await loadData();
    } catch (e) {
      console.error('Delete failed:', e);
    }
  };

  const formatDate = (timestamp: number) => {
    return new Date(timestamp).toLocaleString('zh-CN', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const pieData = statistics
    ? Object.entries(statistics.byType).map(([name, value]) => ({
        name: getErrorTypeName(name as any),
        value
      }))
    : [];

  const wordData = statistics
    ? Object.entries(statistics.byWord)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 10)
        .map(([word, count]) => ({ word, count }))
    : [];

  const trendData = statistics?.trend || [];

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-teal-500/30 border-t-teal-500 rounded-full animate-spin mx-auto mb-4" />
          <p className="text-slate-400">加载统计数据...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950">
      <div className="max-w-7xl mx-auto px-4 py-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-xl font-bold text-white">历史统计</h2>
            <p className="text-sm text-slate-400 mt-1">
              错误类型分析和学习进度追踪
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleExport}
              className="flex items-center gap-2 px-4 py-2 bg-teal-500/20 text-teal-400 border border-teal-500/30 hover:bg-teal-500/30 rounded-lg text-sm font-medium transition-colors"
            >
              <Download className="w-4 h-4" />
              导出数据
            </button>
            <button
              onClick={handleClear}
              className="flex items-center gap-2 px-4 py-2 bg-red-500/20 text-red-400 border border-red-500/30 hover:bg-red-500/30 rounded-lg text-sm font-medium transition-colors"
            >
              <Trash2 className="w-4 h-4" />
              清除数据
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <div className="bg-slate-800/50 rounded-xl p-5 border border-slate-700/50">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-400">总错误次数</p>
                <p className="text-3xl font-bold text-white mt-1">
                  {statistics?.totalCount || 0}
                </p>
              </div>
              <div className="w-12 h-12 bg-red-500/20 rounded-xl flex items-center justify-center">
                <AlertTriangle className="w-6 h-6 text-red-400" />
              </div>
            </div>
          </div>

          <div className="bg-slate-800/50 rounded-xl p-5 border border-slate-700/50">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-400">今日错误</p>
                <p className="text-3xl font-bold text-white mt-1">{todayCount}</p>
              </div>
              <div className="w-12 h-12 bg-amber-500/20 rounded-xl flex items-center justify-center">
                <Calendar className="w-6 h-6 text-amber-400" />
              </div>
            </div>
          </div>

          <div className="bg-slate-800/50 rounded-xl p-5 border border-slate-700/50">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-400">本周错误</p>
                <p className="text-3xl font-bold text-white mt-1">{weeklyCount}</p>
              </div>
              <div className="w-12 h-12 bg-blue-500/20 rounded-xl flex items-center justify-center">
                <Clock className="w-6 h-6 text-blue-400" />
              </div>
            </div>
          </div>

          <div className="bg-slate-800/50 rounded-xl p-5 border border-slate-700/50">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-400">正确率趋势</p>
                <p className="text-3xl font-bold text-green-400 mt-1">
                  {statistics && statistics.totalCount > 10
                    ? Math.max(0, Math.min(100, 100 - (weeklyCount / 7) * 10)).toFixed(0)
                    : '--'}
                  %
                </p>
              </div>
              <div className="w-12 h-12 bg-green-500/20 rounded-xl flex items-center justify-center">
                <TrendingDown className="w-6 h-6 text-green-400" />
              </div>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
          <div className="bg-slate-800/50 rounded-xl p-5 border border-slate-700/50">
            <h3 className="text-sm font-medium text-slate-300 mb-4 flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-teal-400" />
              错误类型分布
            </h3>
            <div className="h-64">
              {pieData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={pieData}
                      cx="50%"
                      cy="50%"
                      innerRadius={50}
                      outerRadius={80}
                      paddingAngle={2}
                      dataKey="value"
                    >
                      {pieData.map((entry, index) => (
                        <Cell
                          key={`cell-${index}`}
                          fill={COLORS[index % COLORS.length]}
                        />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#1e293b',
                        border: '1px solid #334155',
                        borderRadius: '8px',
                        color: '#fff'
                      }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-full flex items-center justify-center text-slate-500 text-sm">
                  暂无数据
                </div>
              )}
            </div>
            <div className="flex flex-wrap gap-2 mt-2">
              {pieData.map((item, index) => (
                <div key={item.name} className="flex items-center gap-1.5 text-xs">
                  <span
                    className="w-2.5 h-2.5 rounded-full"
                    style={{ backgroundColor: COLORS[index % COLORS.length] }}
                  />
                  <span className="text-slate-400">
                    {item.name} ({item.value})
                  </span>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-slate-800/50 rounded-xl p-5 border border-slate-700/50 lg:col-span-2">
            <h3 className="text-sm font-medium text-slate-300 mb-4 flex items-center gap-2">
              <TrendingDown className="w-4 h-4 text-teal-400" />
              近30天错误趋势
            </h3>
            <div className="h-64">
              {trendData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={trendData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                    <XAxis
                      dataKey="date"
                      stroke="#64748b"
                      fontSize={11}
                      tickFormatter={(value) => value.slice(5)}
                    />
                    <YAxis stroke="#64748b" fontSize={11} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#1e293b',
                        border: '1px solid #334155',
                        borderRadius: '8px',
                        color: '#fff'
                      }}
                      labelStyle={{ color: '#fff' }}
                    />
                    <Line
                      type="monotone"
                      dataKey="count"
                      stroke="#4ECDC4"
                      strokeWidth={2}
                      dot={{ fill: '#4ECDC4', r: 4 }}
                      activeDot={{ r: 6, fill: '#FF6B6B' }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-full flex items-center justify-center text-slate-500 text-sm">
                  暂无数据
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          <div className="bg-slate-800/50 rounded-xl p-5 border border-slate-700/50">
            <h3 className="text-sm font-medium text-slate-300 mb-4">常错词汇 TOP 10</h3>
            <div className="h-64">
              {wordData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={wordData} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                    <XAxis type="number" stroke="#64748b" fontSize={11} />
                    <YAxis
                      dataKey="word"
                      type="category"
                      stroke="#64748b"
                      fontSize={11}
                      width={50}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#1e293b',
                        border: '1px solid #334155',
                        borderRadius: '8px',
                        color: '#fff'
                      }}
                    />
                    <Bar dataKey="count" fill="#FF6B6B" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-full flex items-center justify-center text-slate-500 text-sm">
                  暂无数据
                </div>
              )}
            </div>
          </div>

          <div className="bg-slate-800/50 rounded-xl p-5 border border-slate-700/50">
            <h3 className="text-sm font-medium text-slate-300 mb-4">错误类型详解</h3>
            <div className="space-y-3">
              {pieData.length > 0 ? (
                pieData
                  .sort((a, b) => b.value - a.value)
                  .map((item, index) => {
                    const total = statistics?.totalCount || 1;
                    const percentage = ((item.value / total) * 100).toFixed(1);
                    return (
                      <div key={item.name} className="space-y-1">
                        <div className="flex items-center justify-between text-sm">
                          <div className="flex items-center gap-2">
                            <span
                              className="w-3 h-3 rounded-full"
                              style={{ backgroundColor: COLORS[index % COLORS.length] }}
                            />
                            <span className="text-slate-300">{item.name}</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="text-slate-400">{item.value} 次</span>
                            <span className="text-slate-500 text-xs">({percentage}%)</span>
                          </div>
                        </div>
                        <div className="h-2 bg-slate-700/50 rounded-full overflow-hidden">
                          <div
                            className="h-full rounded-full transition-all duration-500"
                            style={{
                              width: `${percentage}%`,
                              backgroundColor: COLORS[index % COLORS.length]
                            }}
                          />
                        </div>
                      </div>
                    );
                  })
              ) : (
                <div className="h-48 flex items-center justify-center text-slate-500 text-sm">
                  暂无数据
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-700/50">
            <h3 className="text-sm font-medium text-slate-300">最近错误记录</h3>
          </div>
          {records.length > 0 ? (
            <div className="divide-y divide-slate-700/50">
              {records.map((record) => (
                <div
                  key={record.id}
                  className="px-5 py-4 hover:bg-slate-800/30 transition-colors"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-1">
                        <span className="text-xs text-slate-500 font-mono">
                          {formatDate(record.timestamp)}
                        </span>
                        <CheckCircle2 className="w-3.5 h-3.5 text-red-400" />
                        <span className="text-xs text-red-400">
                          {record.errors.length} 处错误
                        </span>
                      </div>
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm text-slate-400">原文：</span>
                        <div className="flex items-center gap-1 flex-wrap">
                          {record.originalSequence.map((word, i) => {
                            const hasError = record.errors.some(e => e.position === i);
                            return (
                              <span
                                key={i}
                                className={`px-1.5 py-0.5 rounded text-sm ${
                                  hasError
                                    ? 'bg-red-500/20 text-red-400'
                                    : 'text-slate-300'
                                }`}
                              >
                                {word}
                              </span>
                            );
                          })}
                        </div>
                        <ChevronRight className="w-4 h-4 text-teal-400" />
                        <span className="text-sm text-teal-400">
                          {record.correctedSequence.join(' ')}
                        </span>
                      </div>
                      <div className="mt-2 text-xs text-slate-500">
                        翻译：{record.translation}
                      </div>
                    </div>
                    <button
                      onClick={() => handleDeleteRecord(record.id)}
                      className="p-1.5 text-slate-500 hover:text-red-400 hover:bg-red-500/10 rounded transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-8 text-center">
              <div className="w-12 h-12 bg-slate-700/30 rounded-full flex items-center justify-center mx-auto mb-3">
                <BarChart3 className="w-6 h-6 text-slate-600" />
              </div>
              <p className="text-slate-500 text-sm">暂无错误记录</p>
              <p className="text-slate-600 text-xs mt-1">完成识别练习后，错误记录将显示在这里</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Statistics;
