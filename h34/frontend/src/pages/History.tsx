import { useState, useMemo } from 'react'
import { useQuery } from 'react-query'
import {
  Calendar,
  Download,
  Filter,
  ChevronLeft,
  ChevronRight,
  Loader2,
  TrendingUp,
  AlertTriangle,
  CloudRain,
  Thermometer,
} from 'lucide-react'
import { format } from 'date-fns'
import { zhCN } from 'date-fns/locale'
import { riskGridApi, weatherDataApi } from '@/services/api'
import { CROP_TYPE_LABELS, getRiskLevel, RISK_COLORS } from '@/types/map'
import type { CropType, RiskLevel } from '@/types'
import RiskTrendChart from '@/components/charts/RiskTrendChart'
import { clsx } from 'clsx'

const DATE_RANGE_OPTIONS = [
  { value: '7d', label: '最近7天' },
  { value: '30d', label: '最近30天' },
  { value: '90d', label: '最近90天' },
  { value: 'custom', label: '自定义' },
]

const CROP_OPTIONS: { value: CropType | 'all'; label: string }[] = [
  { value: 'all', label: '全部作物' },
  { value: 'wheat', label: '小麦' },
  { value: 'corn', label: '玉米' },
  { value: 'potato', label: '马铃薯' },
  { value: 'rice', label: '水稻' },
]

const generateMockHistoryData = (days: number, crops: CropType[]) => {
  const data: any[] = []
  const today = new Date()

  for (let i = days - 1; i >= 0; i--) {
    const date = new Date(today)
    date.setDate(today.getDate() - i)
    const dateStr = date.toISOString().split('T')[0]
    const label = format(date, 'MM/dd')

    const point: any = {
      date: dateStr,
      label,
    }

    crops.forEach((crop) => {
      point[crop] = Math.random() * 70 + 15
    })

    point.avgRisk = Object.values(point).filter((v) => typeof v === 'number').reduce((a: number, b: number) => a + b, 0) / crops.length
    point.highRiskCount = Math.floor(Math.random() * 10)
    point.avgTemp = (Math.random() * 15 + 18).toFixed(1)
    point.avgHumidity = (Math.random() * 30 + 50).toFixed(1)
    point.rainfall = (Math.random() * 20).toFixed(1)

    data.push(point)
  }

  return data
}

export const History = () => {
  const [dateRange, setDateRange] = useState('30d')
  const [startDate, setStartDate] = useState(() => {
    const date = new Date()
    date.setDate(date.getDate() - 30)
    return date.toISOString().split('T')[0]
  })
  const [endDate, setEndDate] = useState(() => {
    return new Date().toISOString().split('T')[0]
  })
  const [cropFilter, setCropFilter] = useState<CropType | 'all'>('all')
  const [page, setPage] = useState(1)
  const [pageSize] = useState(10)
  const [showFilters, setShowFilters] = useState(false)

  const days = useMemo(() => {
    switch (dateRange) {
      case '7d': return 7
      case '30d': return 30
      case '90d': return 90
      default: return 30
    }
  }, [dateRange])

  const chartCrops = useMemo(() => {
    return cropFilter === 'all' ? ['wheat', 'corn', 'potato', 'rice'] as CropType[] : [cropFilter]
  }, [cropFilter])

  const trendData = useMemo(() => {
    return generateMockHistoryData(days, chartCrops)
  }, [days, chartCrops])

  const { data: riskGridData, isLoading: riskLoading } = useQuery(
    ['historyRiskGrid', cropFilter, startDate, endDate, page, pageSize],
    async () => {
      const params: any = {
        page,
        page_size: pageSize,
        start_date: startDate,
        end_date: endDate,
      }
      if (cropFilter !== 'all') {
        params.crop_type = cropFilter
      }
      const response = await riskGridApi.list(params)
      return response.data
    }
  )

  const { isLoading: weatherLoading } = useQuery(
    ['historyWeather', startDate, endDate],
    async () => {
      const response = await weatherDataApi.list({
        start_date: startDate,
        end_date: endDate,
        page_size: 1,
      })
      return response.data
    }
  )

  const stats = useMemo(() => {
    if (trendData.length === 0) {
      return { avgRisk: 0, maxRisk: 0, highRiskDays: 0, totalRecords: 0 }
    }

    const avgRisk = trendData.reduce((sum, d) => sum + d.avgRisk, 0) / trendData.length
    const maxRisk = Math.max(...trendData.map((d) => d.avgRisk))
    const highRiskDays = trendData.filter((d) => getRiskLevel(d.avgRisk) === 'high' || getRiskLevel(d.avgRisk) === 'extreme').length
    const totalRecords = riskGridData?.total || trendData.length * 100

    return { avgRisk, maxRisk, highRiskDays, totalRecords }
  }, [trendData, riskGridData])

  const tableData = useMemo(() => {
    return trendData.slice().reverse().slice((page - 1) * pageSize, page * pageSize).map((item, index) => ({
      id: (page - 1) * pageSize + index + 1,
      date: item.date,
      cropType: chartCrops[index % chartCrops.length],
      riskIndex: item[chartCrops[index % chartCrops.length]] || item.avgRisk,
      temperature: item.avgTemp,
      humidity: item.avgHumidity,
      rainfall: item.rainfall,
    }))
  }, [trendData, page, pageSize, chartCrops])

  const totalPages = Math.ceil(trendData.length / pageSize)
  const isLoading = riskLoading || weatherLoading

  const getRiskBadgeClass = (level: RiskLevel) => {
    return clsx('risk-badge', {
      'risk-low': level === 'low',
      'risk-medium': level === 'medium',
      'risk-high': level === 'high',
      'risk-extreme': level === 'extreme',
    })
  }

  const getRiskLabel = (level: RiskLevel) => {
    const labels: Record<RiskLevel, string> = {
      low: '低风险',
      medium: '中风险',
      high: '高风险',
      extreme: '极高风险',
    }
    return labels[level]
  }

  if (isLoading && trendData.length === 0) {
    return (
      <div className="flex items-center justify-center min-h-[600px]">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="w-10 h-10 text-green-500 animate-spin" />
          <p className="text-gray-600">加载中...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">历史数据</h1>
          <p className="text-gray-500 mt-1">
            查看历史风险趋势和气象数据统计
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={clsx(
              'px-4 py-2 rounded-lg flex items-center gap-2 transition-colors',
              showFilters
                ? 'bg-green-100 text-green-700'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            )}
          >
            <Filter className="w-4 h-4" />
            筛选
          </button>
          <button className="px-4 py-2 bg-white border border-gray-200 rounded-lg text-gray-600 hover:bg-gray-50 flex items-center gap-2 transition-colors">
            <Download className="w-4 h-4" />
            导出数据
          </button>
        </div>
      </div>

      {showFilters && (
        <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                时间范围
              </label>
              <div className="flex flex-wrap gap-1">
                {DATE_RANGE_OPTIONS.map((option) => (
                  <button
                    key={option.value}
                    onClick={() => {
                      setDateRange(option.value)
                      if (option.value !== 'custom') {
                        const days = parseInt(option.value)
                        const end = new Date()
                        const start = new Date()
                        start.setDate(end.getDate() - days)
                        setEndDate(end.toISOString().split('T')[0])
                        setStartDate(start.toISOString().split('T')[0])
                      }
                    }}
                    className={clsx(
                      'px-3 py-1.5 rounded-md text-xs font-medium transition-all',
                      dateRange === option.value
                        ? 'bg-green-500 text-white'
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    )}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>

            {dateRange === 'custom' && (
              <>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    开始日期
                  </label>
                  <div className="relative">
                    <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                    <input
                      type="date"
                      value={startDate}
                      onChange={(e) => setStartDate(e.target.value)}
                      className="w-full pl-10 pr-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent outline-none"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    结束日期
                  </label>
                  <div className="relative">
                    <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                    <input
                      type="date"
                      value={endDate}
                      onChange={(e) => setEndDate(e.target.value)}
                      className="w-full pl-10 pr-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent outline-none"
                    />
                  </div>
                </div>
              </>
            )}

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                作物类型
              </label>
              <select
                value={cropFilter}
                onChange={(e) => setCropFilter(e.target.value as CropType | 'all')}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent outline-none"
              >
                {CROP_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
          <div className="flex items-center gap-3">
            <div className="p-3 bg-green-100 rounded-lg">
              <TrendingUp className="w-6 h-6 text-green-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">平均风险指数</p>
              <p className="text-2xl font-bold text-gray-900">{stats.avgRisk.toFixed(1)}</p>
              <span className={getRiskBadgeClass(getRiskLevel(stats.avgRisk))}>
                {getRiskLabel(getRiskLevel(stats.avgRisk))}
              </span>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
          <div className="flex items-center gap-3">
            <div className="p-3 bg-red-100 rounded-lg">
              <AlertTriangle className="w-6 h-6 text-red-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">最高风险指数</p>
              <p className="text-2xl font-bold text-gray-900">{stats.maxRisk.toFixed(1)}</p>
              <span className={getRiskBadgeClass(getRiskLevel(stats.maxRisk))}>
                {getRiskLabel(getRiskLevel(stats.maxRisk))}
              </span>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
          <div className="flex items-center gap-3">
            <div className="p-3 bg-orange-100 rounded-lg">
              <AlertTriangle className="w-6 h-6 text-orange-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">高风险天数</p>
              <p className="text-2xl font-bold text-gray-900">{stats.highRiskDays}</p>
              <p className="text-xs text-gray-400">共 {trendData.length} 天</p>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
          <div className="flex items-center gap-3">
            <div className="p-3 bg-blue-100 rounded-lg">
              <Calendar className="w-6 h-6 text-blue-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">数据记录数</p>
              <p className="text-2xl font-bold text-gray-900">{stats.totalRecords.toLocaleString()}</p>
              <p className="text-xs text-gray-400">条历史记录</p>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100 flex items-center gap-4">
          <div className="p-3 bg-orange-100 rounded-lg">
            <Thermometer className="w-6 h-6 text-orange-600" />
          </div>
          <div>
            <p className="text-sm text-gray-500">平均温度</p>
            <p className="text-xl font-bold text-gray-900">
              {trendData.length > 0
                ? (trendData.reduce((sum, d) => sum + parseFloat(d.avgTemp), 0) / trendData.length).toFixed(1)
                : '0.0'}
              °C
            </p>
          </div>
        </div>

        <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100 flex items-center gap-4">
          <div className="p-3 bg-blue-100 rounded-lg">
            <CloudRain className="w-6 h-6 text-blue-600" />
          </div>
          <div>
            <p className="text-sm text-gray-500">平均湿度</p>
            <p className="text-xl font-bold text-gray-900">
              {trendData.length > 0
                ? (trendData.reduce((sum, d) => sum + parseFloat(d.avgHumidity), 0) / trendData.length).toFixed(1)
                : '0.0'}
              %
            </p>
          </div>
        </div>

        <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100 flex items-center gap-4">
          <div className="p-3 bg-cyan-100 rounded-lg">
            <CloudRain className="w-6 h-6 text-cyan-600" />
          </div>
          <div>
            <p className="text-sm text-gray-500">累计降雨量</p>
            <p className="text-xl font-bold text-gray-900">
              {trendData.length > 0
                ? trendData.reduce((sum, d) => sum + parseFloat(d.rainfall), 0).toFixed(1)
                : '0.0'}
              mm
            </p>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-100">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold text-gray-900">风险趋势图</h2>
          <span className="text-sm text-gray-500">
            {format(new Date(startDate), 'yyyy年MM月dd日', { locale: zhCN })} - {format(new Date(endDate), 'yyyy年MM月dd日', { locale: zhCN })}
          </span>
        </div>
        <RiskTrendChart data={trendData} crops={chartCrops} height={350} showThreshold={true} />
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">历史数据明细</h2>
          <p className="text-sm text-gray-500">共 {trendData.length} 条记录</p>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                  日期
                </th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                  作物类型
                </th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                  风险指数
                </th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                  风险等级
                </th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                  温度
                </th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                  湿度
                </th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                  降雨量
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {tableData.map((row) => {
                const riskLevel = getRiskLevel(row.riskIndex)
                return (
                  <tr key={row.id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                      {format(new Date(row.date), 'yyyy-MM-dd', { locale: zhCN })}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                      {CROP_TYPE_LABELS[row.cropType]}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span
                        className="text-sm font-semibold"
                        style={{ color: RISK_COLORS[riskLevel] }}
                      >
                        {row.riskIndex.toFixed(1)}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={getRiskBadgeClass(riskLevel)}>
                        {getRiskLabel(riskLevel)}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                      {row.temperature}°C
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                      {row.humidity}%
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                      {row.rainfall}mm
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

        {totalPages > 1 && (
          <div className="flex items-center justify-between px-6 py-4 border-t border-gray-100">
            <p className="text-sm text-gray-500">
              第 {page} / {totalPages} 页
            </p>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="p-2 rounded-lg hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                let pageNum = i + 1
                if (totalPages > 5) {
                  if (page > 3) {
                    pageNum = page - 2 + i
                  }
                  if (page > totalPages - 2) {
                    pageNum = totalPages - 4 + i
                  }
                }
                if (pageNum > totalPages || pageNum < 1) return null
                return (
                  <button
                    key={pageNum}
                    onClick={() => setPage(pageNum)}
                    className={clsx(
                      'w-8 h-8 rounded-lg text-sm font-medium transition-colors',
                      page === pageNum
                        ? 'bg-green-500 text-white'
                        : 'hover:bg-gray-100 text-gray-600'
                    )}
                  >
                    {pageNum}
                  </button>
                )
              })}
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="p-2 rounded-lg hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default History
