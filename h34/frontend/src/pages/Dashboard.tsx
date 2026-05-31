import { useMemo } from 'react'
import { useQuery } from 'react-query'
import { useNavigate } from 'react-router-dom'
import {
  MapPin,
  Bell,
  ThermometerSun,
  ArrowRight,
  AlertTriangle,
  Clock,
  ChevronRight,
} from 'lucide-react'
import { format } from 'date-fns'
import { zhCN } from 'date-fns/locale'
import { riskGridApi, alertApi, weatherStationApi } from '@/services/api'
import { useFilters } from '@/store'
import { generateDateOptions, getRiskLevel, RISK_COLORS, CROP_TYPE_LABELS } from '@/types/map'
import type { CropType } from '@/types'
import StatsCards from '@/components/charts/StatsCards'
import RiskTrendChart from '@/components/charts/RiskTrendChart'
import { Loader2 } from 'lucide-react'

const generateMockTrendData = (crops: CropType[], days: number = 7) => {
  const dateOptions = generateDateOptions(days)
  return dateOptions.map((option) => {
    const point: any = {
      date: option.date,
      label: option.label,
    }
    crops.forEach((crop) => {
      point[crop] = Math.random() * 60 + 20
    })
    return point
  })
}

export const Dashboard = () => {
  const navigate = useNavigate()
  const { selectedCropType } = useFilters()

  const today = new Date().toISOString().split('T')[0]
  const yesterday = new Date(Date.now() - 86400000).toISOString().split('T')[0]

  const { data: todayRiskData, isLoading: riskLoading } = useQuery(
    ['riskGrid', selectedCropType, today],
    async () => {
      const response = await riskGridApi.getHeatmap(selectedCropType, today)
      return response.data || []
    }
  )

  const { data: yesterdayRiskData } = useQuery(
    ['riskGrid', selectedCropType, yesterday],
    async () => {
      const response = await riskGridApi.getHeatmap(selectedCropType, yesterday)
      return response.data || []
    }
  )

  const { data: alertsData, isLoading: alertsLoading } = useQuery(
    ['alerts', 'dashboard'],
    async () => {
      const response = await alertApi.list({ page_size: 5, is_read: false })
      return response.data?.items || []
    }
  )

  const { data: stationsData, isLoading: stationsLoading } = useQuery(
    ['weatherStations', 'dashboard'],
    async () => {
      const response = await weatherStationApi.list({ page_size: 100 })
      return response.data?.items || []
    }
  )

  const stats = useMemo(() => {
    const data = todayRiskData || []
    const highRiskCount = data.filter((item) => getRiskLevel(item.risk_index) === 'high' || getRiskLevel(item.risk_index) === 'extreme').length
    const onlineStations = stationsData?.filter((s) => s.is_active).length || 0
    const todayAlerts = alertsData?.length || 0

    return {
      highRiskCount,
      todayAlerts,
      onlineStations,
      totalStations: stationsData?.length || 0,
    }
  }, [todayRiskData, alertsData, stationsData])

  const trendData = useMemo(() => {
    return generateMockTrendData(['wheat', 'corn'], 7)
  }, [])

  const isLoading = riskLoading || alertsLoading || stationsLoading

  if (isLoading) {
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
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">仪表盘</h1>
          <p className="text-gray-500 mt-1">
            {format(new Date(), 'yyyy年MM月dd日 EEEE', { locale: zhCN })} · {CROP_TYPE_LABELS[selectedCropType]}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
          <div className="flex items-center gap-3">
            <div className="p-3 bg-red-100 rounded-lg">
              <AlertTriangle className="w-6 h-6 text-red-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">高风险区域</p>
              <p className="text-2xl font-bold text-gray-900">{stats.highRiskCount}</p>
              <p className="text-xs text-gray-400">个网格</p>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
          <div className="flex items-center gap-3">
            <div className="p-3 bg-orange-100 rounded-lg">
              <Bell className="w-6 h-6 text-orange-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">今日预警</p>
              <p className="text-2xl font-bold text-gray-900">{stats.todayAlerts}</p>
              <p className="text-xs text-gray-400">条未读</p>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
          <div className="flex items-center gap-3">
            <div className="p-3 bg-green-100 rounded-lg">
              <ThermometerSun className="w-6 h-6 text-green-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">气象站在线</p>
              <p className="text-2xl font-bold text-gray-900">
                {stats.onlineStations}
                <span className="text-base text-gray-400 font-normal">/{stats.totalStations}</span>
              </p>
              <p className="text-xs text-gray-400">个站点</p>
            </div>
          </div>
        </div>
      </div>

      <StatsCards data={todayRiskData || []} yesterdayData={yesterdayRiskData || []} />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-white rounded-xl p-6 shadow-sm border border-gray-100">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-semibold text-gray-900">风险趋势</h2>
            <span className="text-sm text-gray-500">最近7天</span>
          </div>
          <RiskTrendChart data={trendData} crops={['wheat', 'corn']} height={300} />
        </div>

        <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-100">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900">最新预警</h2>
            <button
              onClick={() => navigate('/alerts')}
              className="text-sm text-green-600 hover:text-green-700 flex items-center gap-1"
            >
              查看全部 <ChevronRight className="w-4 h-4" />
            </button>
          </div>

          <div className="space-y-3">
            {alertsData && alertsData.length > 0 ? (
              alertsData.map((alert) => {
                const riskColor = RISK_COLORS[getRiskLevel(alert.threshold_exceeded || 50)]
                return (
                  <div
                    key={alert.id}
                    className="p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors cursor-pointer"
                    onClick={() => navigate('/alerts')}
                  >
                    <div className="flex items-start gap-3">
                      <div
                        className="w-2 h-2 rounded-full mt-2 flex-shrink-0"
                        style={{ backgroundColor: riskColor }}
                      />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-900 truncate">
                          {alert.message}
                        </p>
                        <div className="flex items-center gap-2 mt-1">
                          <Clock className="w-3 h-3 text-gray-400" />
                          <span className="text-xs text-gray-500">
                            {format(new Date(alert.triggered_at), 'MM-dd HH:mm')}
                          </span>
                          {!alert.is_read && (
                            <span className="px-1.5 py-0.5 bg-red-100 text-red-600 text-xs rounded">
                              未读
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                )
              })
            ) : (
              <div className="text-center py-8 text-gray-400">
                <Bell className="w-10 h-10 mx-auto mb-2 opacity-50" />
                <p>暂无预警</p>
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <button
          onClick={() => navigate('/map')}
          className="flex items-center justify-between p-5 bg-white rounded-xl shadow-sm border border-gray-100 hover:border-green-200 hover:shadow-md transition-all group"
        >
          <div className="flex items-center gap-4">
            <div className="p-3 bg-green-100 rounded-lg group-hover:bg-green-200 transition-colors">
              <MapPin className="w-6 h-6 text-green-600" />
            </div>
            <div className="text-left">
              <h3 className="font-semibold text-gray-900">地图视图</h3>
              <p className="text-sm text-gray-500">查看区域风险分布热力图</p>
            </div>
          </div>
          <ArrowRight className="w-5 h-5 text-gray-400 group-hover:text-green-600 group-hover:translate-x-1 transition-all" />
        </button>

        <button
          onClick={() => navigate('/alerts')}
          className="flex items-center justify-between p-5 bg-white rounded-xl shadow-sm border border-gray-100 hover:border-orange-200 hover:shadow-md transition-all group"
        >
          <div className="flex items-center gap-4">
            <div className="p-3 bg-orange-100 rounded-lg group-hover:bg-orange-200 transition-colors">
              <Bell className="w-6 h-6 text-orange-600" />
            </div>
            <div className="text-left">
              <h3 className="font-semibold text-gray-900">预警管理</h3>
              <p className="text-sm text-gray-500">查看和处理风险预警通知</p>
            </div>
          </div>
          <ArrowRight className="w-5 h-5 text-gray-400 group-hover:text-orange-600 group-hover:translate-x-1 transition-all" />
        </button>
      </div>
    </div>
  )
}

export default Dashboard
