import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from 'react-query'
import {
  Bell,
  Filter,
  Search,
  Check,
  CheckCheck,
  X,
  ChevronLeft,
  ChevronRight,
  AlertTriangle,
  Clock,
  MapPin,
  Eye,
} from 'lucide-react'
import { format } from 'date-fns'
import { zhCN } from 'date-fns/locale'
import { alertApi } from '@/services/api'
import { getRiskLevel, RISK_COLORS } from '@/types/map'
import type { Alert, CropType, RiskLevel } from '@/types'
import { Loader2 } from 'lucide-react'

const SEVERITY_OPTIONS: { value: RiskLevel | 'all'; label: string; color: string }[] = [
  { value: 'all', label: '全部', color: 'bg-gray-500' },
  { value: 'low', label: '低风险', color: 'bg-green-500' },
  { value: 'medium', label: '中风险', color: 'bg-yellow-500' },
  { value: 'high', label: '高风险', color: 'bg-orange-500' },
  { value: 'extreme', label: '极高风险', color: 'bg-red-500' },
]

const CROP_OPTIONS: { value: CropType | 'all'; label: string }[] = [
  { value: 'all', label: '全部作物' },
  { value: 'wheat', label: '小麦' },
  { value: 'corn', label: '玉米' },
  { value: 'potato', label: '马铃薯' },
  { value: 'rice', label: '水稻' },
]

const READ_STATUS_OPTIONS = [
  { value: 'all', label: '全部' },
  { value: 'unread', label: '未读' },
  { value: 'read', label: '已读' },
]

export const Alerts = () => {
  const queryClient = useQueryClient()
  const [page, setPage] = useState(1)
  const [pageSize] = useState(10)
  const [severityFilter, setSeverityFilter] = useState<RiskLevel | 'all'>('all')
  const [cropFilter, setCropFilter] = useState<CropType | 'all'>('all')
  const [readFilter, setReadFilter] = useState<'all' | 'unread' | 'read'>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null)
  const [showFilters, setShowFilters] = useState(false)

  const { data: alertsResponse, isLoading } = useQuery(
    ['alerts', page, pageSize, severityFilter, readFilter],
    async () => {
      const params: any = {
        page,
        page_size: pageSize,
      }
      if (readFilter === 'unread') params.is_read = false
      if (readFilter === 'read') params.is_read = true

      const response = await alertApi.list(params)
      return response.data
    }
  )

  const { data: unreadCount } = useQuery(
    ['alerts', 'unread-count'],
    async () => {
      const response = await alertApi.getUnreadCount()
      return response.data?.count || 0
    }
  )

  const markAsReadMutation = useMutation(
    (id: number) => alertApi.markAsRead(id),
    {
      onSuccess: () => {
        queryClient.invalidateQueries(['alerts'])
        queryClient.invalidateQueries(['alerts', 'unread-count'])
      },
    }
  )

  const markAllAsReadMutation = useMutation(
    () => alertApi.markAllAsRead(),
    {
      onSuccess: () => {
        queryClient.invalidateQueries(['alerts'])
        queryClient.invalidateQueries(['alerts', 'unread-count'])
      },
    }
  )

  const filteredAlerts = useMemo(() => {
    let alerts = alertsResponse?.items || []

    if (searchQuery) {
      alerts = alerts.filter(
        (alert) =>
          alert.message.toLowerCase().includes(searchQuery.toLowerCase())
      )
    }

    if (severityFilter !== 'all') {
      alerts = alerts.filter((alert) => {
        const level = getRiskLevel(alert.threshold_exceeded || 50)
        return level === severityFilter
      })
    }

    return alerts
  }, [alertsResponse?.items, searchQuery, severityFilter])

  const handleMarkAsRead = (alert: Alert) => {
    if (!alert.is_read) {
      markAsReadMutation.mutate(alert.id)
    }
    setSelectedAlert(alert)
  }

  const handleMarkAllAsRead = () => {
    if (confirm('确定要将所有预警标记为已读吗？')) {
      markAllAsReadMutation.mutate()
    }
  }

  const totalPages = alertsResponse?.total_pages || 1

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
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">预警管理</h1>
          <p className="text-gray-500 mt-1">
            共 {alertsResponse?.total || 0} 条预警
            {unreadCount !== undefined && unreadCount > 0 && (
              <span className="ml-2 px-2 py-0.5 bg-red-100 text-red-600 text-sm rounded-full">
                {unreadCount} 条未读
              </span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`px-4 py-2 rounded-lg flex items-center gap-2 transition-colors ${
              showFilters
                ? 'bg-green-100 text-green-700'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            <Filter className="w-4 h-4" />
            筛选
          </button>
          {(unreadCount || 0) > 0 && (
            <button
              onClick={handleMarkAllAsRead}
              disabled={markAllAsReadMutation.isLoading}
              className="px-4 py-2 bg-white border border-gray-200 rounded-lg text-gray-600 hover:bg-gray-50 flex items-center gap-2 transition-colors disabled:opacity-50"
            >
              <CheckCheck className="w-4 h-4" />
              全部已读
            </button>
          )}
        </div>
      </div>

      {showFilters && (
        <div className="bg-white rounded-xl p-4 mb-6 shadow-sm border border-gray-100">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                搜索
              </label>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="搜索预警内容..."
                  className="w-full pl-10 pr-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent outline-none"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                严重程度
              </label>
              <div className="flex flex-wrap gap-1">
                {SEVERITY_OPTIONS.map((option) => (
                  <button
                    key={option.value}
                    onClick={() => setSeverityFilter(option.value)}
                    className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                      severityFilter === option.value
                        ? `${option.color} text-white`
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    }`}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>

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

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                阅读状态
              </label>
              <div className="flex gap-2">
                {READ_STATUS_OPTIONS.map((option) => (
                  <button
                    key={option.value}
                    onClick={() => setReadFilter(option.value as 'all' | 'unread' | 'read')}
                    className={`flex-1 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                      readFilter === option.value
                        ? 'bg-green-500 text-white'
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    }`}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
            <div className="divide-y divide-gray-100">
              {filteredAlerts.length > 0 ? (
                filteredAlerts.map((alert) => {
                  const riskLevel = getRiskLevel(alert.threshold_exceeded || 50)
                  const riskColor = RISK_COLORS[riskLevel]

                  return (
                    <div
                      key={alert.id}
                      onClick={() => handleMarkAsRead(alert)}
                      className={`p-4 hover:bg-gray-50 cursor-pointer transition-colors ${
                        !alert.is_read ? 'bg-blue-50/50' : ''
                      } ${selectedAlert?.id === alert.id ? 'bg-green-50 border-l-4 border-l-green-500' : ''}`}
                    >
                      <div className="flex items-start gap-3">
                        <div
                          className="w-2 h-2 rounded-full mt-2 flex-shrink-0"
                          style={{ backgroundColor: riskColor }}
                        />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-start justify-between gap-2">
                            <p className={`font-medium ${!alert.is_read ? 'text-gray-900' : 'text-gray-600'}`}>
                              {alert.message}
                            </p>
                            {!alert.is_read && (
                              <span className="flex-shrink-0 w-2 h-2 bg-blue-500 rounded-full" />
                            )}
                          </div>
                          <div className="flex items-center gap-4 mt-2 text-xs text-gray-500">
                            <span className="flex items-center gap-1">
                              <Clock className="w-3 h-3" />
                              {format(new Date(alert.triggered_at), 'yyyy-MM-dd HH:mm', { locale: zhCN })}
                            </span>
                            {alert.threshold_exceeded !== undefined && (
                              <span
                                className="px-2 py-0.5 rounded text-white font-medium"
                                style={{ backgroundColor: riskColor }}
                              >
                                {alert.threshold_exceeded.toFixed(1)}
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  )
                })
              ) : (
                <div className="p-12 text-center text-gray-400">
                  <Bell className="w-12 h-12 mx-auto mb-3 opacity-50" />
                  <p className="text-lg">暂无预警记录</p>
                </div>
              )}
            </div>

            {totalPages > 1 && (
              <div className="flex items-center justify-between px-4 py-3 border-t border-gray-100">
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
                        className={`w-8 h-8 rounded-lg text-sm font-medium transition-colors ${
                          page === pageNum
                            ? 'bg-green-500 text-white'
                            : 'hover:bg-gray-100 text-gray-600'
                        }`}
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

        <div>
          {selectedAlert ? (
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden sticky top-6">
              <div className="flex items-center justify-between p-4 border-b border-gray-100">
                <h3 className="font-semibold text-gray-900">预警详情</h3>
                <button
                  onClick={() => setSelectedAlert(null)}
                  className="p-1 hover:bg-gray-100 rounded transition-colors"
                >
                  <X className="w-5 h-5 text-gray-500" />
                </button>
              </div>

              <div className="p-4 space-y-4">
                <div
                  className="p-4 rounded-lg"
                  style={{
                    backgroundColor: `${RISK_COLORS[getRiskLevel(selectedAlert.threshold_exceeded || 50)]}15`,
                  }}
                >
                  <div className="flex items-center gap-2 mb-2">
                    <AlertTriangle
                      className="w-5 h-5"
                      style={{ color: RISK_COLORS[getRiskLevel(selectedAlert.threshold_exceeded || 50)] }}
                    />
                    <span
                      className="font-semibold"
                      style={{ color: RISK_COLORS[getRiskLevel(selectedAlert.threshold_exceeded || 50)] }}
                    >
                      {getRiskLevel(selectedAlert.threshold_exceeded || 50) === 'low' && '低风险'}
                      {getRiskLevel(selectedAlert.threshold_exceeded || 50) === 'medium' && '中风险'}
                      {getRiskLevel(selectedAlert.threshold_exceeded || 50) === 'high' && '高风险'}
                      {getRiskLevel(selectedAlert.threshold_exceeded || 50) === 'extreme' && '极高风险'}
                    </span>
                  </div>
                  <p className="text-gray-700">{selectedAlert.message}</p>
                </div>

                <div className="space-y-3">
                  <div className="flex items-center justify-between py-2 border-b border-gray-100">
                    <span className="text-sm text-gray-500">预警ID</span>
                    <span className="text-sm font-medium text-gray-900">#{selectedAlert.id}</span>
                  </div>

                  <div className="flex items-center justify-between py-2 border-b border-gray-100">
                    <span className="text-sm text-gray-500">触发时间</span>
                    <span className="text-sm font-medium text-gray-900">
                      {format(new Date(selectedAlert.triggered_at), 'yyyy-MM-dd HH:mm:ss', { locale: zhCN })}
                    </span>
                  </div>

                  {selectedAlert.threshold_exceeded !== undefined && (
                    <div className="flex items-center justify-between py-2 border-b border-gray-100">
                      <span className="text-sm text-gray-500">风险指数</span>
                      <span
                        className="text-sm font-semibold"
                        style={{ color: RISK_COLORS[getRiskLevel(selectedAlert.threshold_exceeded)] }}
                      >
                        {selectedAlert.threshold_exceeded.toFixed(1)}
                      </span>
                    </div>
                  )}

                  <div className="flex items-center justify-between py-2 border-b border-gray-100">
                    <span className="text-sm text-gray-500">阅读状态</span>
                    <span
                      className={`text-sm font-medium flex items-center gap-1 ${
                        selectedAlert.is_read ? 'text-green-600' : 'text-blue-600'
                      }`}
                    >
                      {selectedAlert.is_read ? (
                        <>
                          <Check className="w-4 h-4" />
                          已读
                        </>
                      ) : (
                        <>
                          <Eye className="w-4 h-4" />
                          未读
                        </>
                      )}
                    </span>
                  </div>

                  {selectedAlert.grid_cell && (
                    <div className="flex items-center justify-between py-2 border-b border-gray-100">
                      <span className="text-sm text-gray-500">关联网格</span>
                      <span className="text-sm font-medium text-gray-900 flex items-center gap-1">
                        <MapPin className="w-3 h-3" />
                        网格 {selectedAlert.grid_cell.id}
                      </span>
                    </div>
                  )}

                  {selectedAlert.notified_at && (
                    <div className="flex items-center justify-between py-2">
                      <span className="text-sm text-gray-500">通知时间</span>
                      <span className="text-sm font-medium text-gray-900">
                        {format(new Date(selectedAlert.notified_at), 'yyyy-MM-dd HH:mm', { locale: zhCN })}
                      </span>
                    </div>
                  )}
                </div>

                <div className="flex gap-2 pt-2">
                  {!selectedAlert.is_read && (
                    <button
                      onClick={() => markAsReadMutation.mutate(selectedAlert.id)}
                      disabled={markAsReadMutation.isLoading}
                      className="flex-1 py-2 bg-green-500 hover:bg-green-600 text-white rounded-lg font-medium transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
                    >
                      <Check className="w-4 h-4" />
                      标记已读
                    </button>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-8 text-center text-gray-400 sticky top-6">
              <Eye className="w-12 h-12 mx-auto mb-3 opacity-50" />
              <p>点击预警查看详情</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default Alerts
