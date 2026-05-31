import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from 'react-query'
import { useForm, Controller } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import {
  User,
  Sprout,
  Mail,
  Webhook,
  Sliders,
  Plus,
  Edit2,
  Trash2,
  Save,
  X,
  AlertCircle,
  Bell,
} from 'lucide-react'
import { format } from 'date-fns'
import { zhCN } from 'date-fns/locale'
import { userConfigApi, authApi } from '@/services/api'
import { useAuth } from '@/store'
import { CROP_TYPE_LABELS, RISK_THRESHOLDS, getRiskColor } from '@/types/map'
import type { UserConfig, CropType } from '@/types'
import { Loader2 } from 'lucide-react'

const cropSchema = z.object({
  crop_type: z.enum(['wheat', 'corn', 'potato', 'rice']),
  variety_name: z.string().min(1, '请输入品种名称'),
  resistance_level: z.number().min(1).max(10),
  risk_threshold: z.number().min(0).max(100),
  notification_email: z.string().email('请输入有效邮箱').optional().or(z.literal('')),
  webhook_url: z.string().url('请输入有效URL').optional().or(z.literal('')),
})

type CropFormData = z.infer<typeof cropSchema>

const RESISTANCE_LEVELS = [
  { value: 1, label: '极感病' },
  { value: 3, label: '感病' },
  { value: 5, label: '中等' },
  { value: 7, label: '抗病' },
  { value: 10, label: '高抗' },
]

const CROP_OPTIONS: CropType[] = ['wheat', 'corn', 'potato', 'rice']

export const Settings = () => {
  const queryClient = useQueryClient()
  const { user } = useAuth()
  const [activeTab, setActiveTab] = useState<'profile' | 'crops' | 'notifications' | 'thresholds'>('profile')
  const [editingCrop, setEditingCrop] = useState<UserConfig | null>(null)
  const [showCropModal, setShowCropModal] = useState(false)

  const { data: userConfigs, isLoading: configsLoading } = useQuery(
    ['user-configs'],
    async () => {
      const response = await userConfigApi.list({ page_size: 100 })
      return response.data?.items || []
    }
  )

  const { data: currentUser } = useQuery(['current-user'], async () => {
    const response = await authApi.getCurrentUser()
    return response.data
  })

  const {
    control,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<CropFormData>({
    resolver: zodResolver(cropSchema),
    defaultValues: {
      crop_type: 'wheat',
      variety_name: '',
      resistance_level: 5,
      risk_threshold: RISK_THRESHOLDS.high,
      notification_email: '',
      webhook_url: '',
    },
  })

  const createCropMutation = useMutation(
    (data: CropFormData) => userConfigApi.create(data),
    {
      onSuccess: () => {
        queryClient.invalidateQueries(['user-configs'])
        setShowCropModal(false)
        reset()
      },
    }
  )

  const updateCropMutation = useMutation(
    ({ id, data }: { id: number; data: Partial<CropFormData> }) =>
      userConfigApi.update(id, data),
    {
      onSuccess: () => {
        queryClient.invalidateQueries(['user-configs'])
        setEditingCrop(null)
        setShowCropModal(false)
        reset()
      },
    }
  )

  const deleteCropMutation = useMutation(
    (id: number) => userConfigApi.delete(id),
    {
      onSuccess: () => {
        queryClient.invalidateQueries(['user-configs'])
      },
    }
  )

  const handleOpenAddModal = () => {
    setEditingCrop(null)
    reset({
      crop_type: 'wheat',
      variety_name: '',
      resistance_level: 5,
      risk_threshold: RISK_THRESHOLDS.high,
      notification_email: user?.email || '',
      webhook_url: '',
    })
    setShowCropModal(true)
  }

  const handleOpenEditModal = (config: UserConfig) => {
    setEditingCrop(config)
    reset({
      crop_type: config.crop_type,
      variety_name: config.variety_name,
      resistance_level: config.resistance_level,
      risk_threshold: config.risk_threshold,
      notification_email: config.notification_email || '',
      webhook_url: config.webhook_url || '',
    })
    setShowCropModal(true)
  }

  const handleCropSubmit = (data: CropFormData) => {
    if (editingCrop) {
      updateCropMutation.mutate({ id: editingCrop.id, data })
    } else {
      createCropMutation.mutate(data)
    }
  }

  const handleDeleteCrop = (id: number) => {
    if (confirm('确定要删除这个作物配置吗？')) {
      deleteCropMutation.mutate(id)
    }
  }

  const tabs = [
    { id: 'profile', label: '个人信息', icon: User },
    { id: 'crops', label: '作物配置', icon: Sprout },
    { id: 'notifications', label: '通知渠道', icon: Bell },
    { id: 'thresholds', label: '风险阈值', icon: Sliders },
  ]

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">系统设置</h1>
        <p className="text-gray-500 mt-1">管理您的个人信息和系统偏好</p>
      </div>

      <div className="flex gap-6">
        <div className="w-56 flex-shrink-0">
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-2 space-y-1">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-left transition-all ${
                  activeTab === tab.id
                    ? 'bg-green-50 text-green-700 font-medium'
                    : 'text-gray-600 hover:bg-gray-50'
                }`}
              >
                <tab.icon className="w-5 h-5" />
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        <div className="flex-1">
          {activeTab === 'profile' && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-6">个人信息</h2>

              <div className="flex items-start gap-6">
                <div className="w-24 h-24 bg-gradient-to-br from-green-400 to-green-600 rounded-2xl flex items-center justify-center text-white text-3xl font-bold shadow-lg">
                  {currentUser?.full_name?.charAt(0) || currentUser?.email?.charAt(0).toUpperCase()}
                </div>

                <div className="flex-1 space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm text-gray-500 mb-1">邮箱</label>
                      <p className="text-gray-900 font-medium">{currentUser?.email}</p>
                    </div>
                    <div>
                      <label className="block text-sm text-gray-500 mb-1">姓名</label>
                      <p className="text-gray-900 font-medium">{currentUser?.full_name || '-'}</p>
                    </div>
                    <div>
                      <label className="block text-sm text-gray-500 mb-1">用户ID</label>
                      <p className="text-gray-900 font-medium">#{currentUser?.id}</p>
                    </div>
                    <div>
                      <label className="block text-sm text-gray-500 mb-1">注册时间</label>
                      <p className="text-gray-900 font-medium">
                        {currentUser?.created_at
                          ? format(new Date(currentUser.created_at), 'yyyy-MM-dd', { locale: zhCN })
                          : '-'}
                      </p>
                    </div>
                  </div>

                  <div className="pt-4">
                    <span
                      className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium ${
                        currentUser?.is_active
                          ? 'bg-green-100 text-green-700'
                          : 'bg-red-100 text-red-700'
                      }`}
                    >
                      <span className="w-2 h-2 rounded-full bg-current" />
                      {currentUser?.is_active ? '账户活跃' : '账户未激活'}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'crops' && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-100">
              <div className="flex items-center justify-between p-6 border-b border-gray-100">
                <h2 className="text-lg font-semibold text-gray-900">作物配置</h2>
                <button
                  onClick={handleOpenAddModal}
                  className="px-4 py-2 bg-green-500 hover:bg-green-600 text-white rounded-lg font-medium transition-colors flex items-center gap-2"
                >
                  <Plus className="w-4 h-4" />
                  添加作物
                </button>
              </div>

              <div className="p-6">
                {configsLoading ? (
                  <div className="flex items-center justify-center py-12">
                    <Loader2 className="w-8 h-8 text-green-500 animate-spin" />
                  </div>
                ) : userConfigs && userConfigs.length > 0 ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {userConfigs.map((config) => (
                      <div
                        key={config.id}
                        className="border border-gray-200 rounded-xl p-4 hover:border-green-200 hover:shadow-md transition-all"
                      >
                        <div className="flex items-start justify-between mb-3">
                          <div className="flex items-center gap-3">
                            <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
                              <Sprout className="w-5 h-5 text-green-600" />
                            </div>
                            <div>
                              <h3 className="font-medium text-gray-900">
                                {CROP_TYPE_LABELS[config.crop_type]}
                              </h3>
                              <p className="text-sm text-gray-500">{config.variety_name}</p>
                            </div>
                          </div>
                          <div className="flex items-center gap-1">
                            <button
                              onClick={() => handleOpenEditModal(config)}
                              className="p-2 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                            >
                              <Edit2 className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => handleDeleteCrop(config.id)}
                              className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        </div>

                        <div className="space-y-2 text-sm">
                          <div className="flex justify-between">
                            <span className="text-gray-500">抗性等级</span>
                            <span className="font-medium text-gray-700">
                              {RESISTANCE_LEVELS.find((l) => l.value === config.resistance_level)?.label || config.resistance_level}
                            </span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-gray-500">风险阈值</span>
                            <span
                              className="font-medium"
                              style={{ color: getRiskColor(config.risk_threshold) }}
                            >
                              {config.risk_threshold}
                            </span>
                          </div>
                          {config.notification_email && (
                            <div className="flex items-center gap-2 text-gray-500">
                              <Mail className="w-3.5 h-3.5" />
                              <span className="truncate">{config.notification_email}</span>
                            </div>
                          )}
                          {config.webhook_url && (
                            <div className="flex items-center gap-2 text-gray-500">
                              <Webhook className="w-3.5 h-3.5" />
                              <span className="truncate">Webhook 已配置</span>
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-12 text-gray-400">
                    <Sprout className="w-12 h-12 mx-auto mb-3 opacity-50" />
                    <p className="text-lg mb-2">暂无作物配置</p>
                    <p className="text-sm">点击上方按钮添加您的第一个作物</p>
                  </div>
                )}
              </div>
            </div>
          )}

          {activeTab === 'notifications' && (
            <div className="space-y-6">
              <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
                <h2 className="text-lg font-semibold text-gray-900 mb-4">通知渠道配置</h2>
                <p className="text-gray-500 mb-6">配置预警通知的接收方式</p>

                <div className="space-y-6">
                  <div className="p-4 border border-gray-200 rounded-xl">
                    <div className="flex items-center gap-3 mb-4">
                      <div className="p-2 bg-blue-100 rounded-lg">
                        <Mail className="w-5 h-5 text-blue-600" />
                      </div>
                      <div>
                        <h3 className="font-medium text-gray-900">邮件通知</h3>
                        <p className="text-sm text-gray-500">通过邮件接收风险预警</p>
                      </div>
                    </div>
                    <div className="space-y-3">
                      <div>
                        <label className="block text-sm text-gray-600 mb-1">通知邮箱</label>
                        <input
                          type="email"
                          defaultValue={user?.email}
                          placeholder="your@email.com"
                          className="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent outline-none"
                        />
                      </div>
                      <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                        <span className="text-sm text-gray-600">启用邮件通知</span>
                        <button className="w-12 h-6 bg-green-500 rounded-full relative">
                          <span className="absolute right-1 top-1 w-4 h-4 bg-white rounded-full shadow" />
                        </button>
                      </div>
                    </div>
                  </div>

                  <div className="p-4 border border-gray-200 rounded-xl">
                    <div className="flex items-center gap-3 mb-4">
                      <div className="p-2 bg-purple-100 rounded-lg">
                        <Webhook className="w-5 h-5 text-purple-600" />
                      </div>
                      <div>
                        <h3 className="font-medium text-gray-900">Webhook 通知</h3>
                        <p className="text-sm text-gray-500">通过 Webhook 推送预警到您的系统</p>
                      </div>
                    </div>
                    <div className="space-y-3">
                      <div>
                        <label className="block text-sm text-gray-600 mb-1">Webhook URL</label>
                        <input
                          type="url"
                          placeholder="https://your-domain.com/webhook"
                          className="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent outline-none font-mono text-sm"
                        />
                      </div>
                      <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                        <span className="text-sm text-gray-600">启用 Webhook 通知</span>
                        <button className="w-12 h-6 bg-gray-200 rounded-full relative">
                          <span className="absolute left-1 top-1 w-4 h-4 bg-white rounded-full shadow" />
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'thresholds' && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">风险阈值设置</h2>
              <p className="text-gray-500 mb-6">调整各风险等级的阈值范围</p>

              <div className="space-y-6">
                {[
                  { key: 'low', label: '低风险', color: RISK_THRESHOLDS.low, desc: '一般气象条件，病害发生风险低' },
                  { key: 'medium', label: '中风险', color: RISK_THRESHOLDS.medium, desc: '气象条件较为适宜，需关注病害发展' },
                  { key: 'high', label: '高风险', color: RISK_THRESHOLDS.high, desc: '气象条件适宜，病害发生风险较高' },
                  { key: 'extreme', label: '极高风险', color: RISK_THRESHOLDS.extreme, desc: '气象条件非常适宜，病害极易发生流行' },
                ].map((item, index, arr) => (
                  <div key={item.key} className="p-4 border border-gray-200 rounded-xl">
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-3">
                        <div
                          className="w-4 h-4 rounded-full"
                          style={{ backgroundColor: getRiskColor(item.color) }}
                        />
                        <div>
                          <h3 className="font-medium text-gray-900">{item.label}</h3>
                          <p className="text-sm text-gray-500">{item.desc}</p>
                        </div>
                      </div>
                      <div className="text-right">
                        <p className="text-sm text-gray-500">当前阈值</p>
                        <p
                          className="text-2xl font-bold"
                          style={{ color: getRiskColor(item.color) }}
                        >
                          {item.color}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-4">
                      <span className="text-sm text-gray-400 w-8">
                        {index === 0 ? 0 : arr[index - 1].color}
                      </span>
                      <input
                        type="range"
                        min={index === 0 ? 0 : arr[index - 1].color + 1}
                        max={100}
                        value={item.color}
                        disabled
                        className="flex-1 h-2 bg-gray-200 rounded-lg appearance-none cursor-not-allowed"
                      />
                      <span className="text-sm text-gray-400 w-8">
                        {index === arr.length - 1 ? 100 : arr[index + 1].color - 1}
                      </span>
                    </div>
                  </div>
                ))}
              </div>

              <div className="mt-6 p-4 bg-amber-50 border border-amber-200 rounded-xl">
                <div className="flex items-start gap-3">
                  <AlertCircle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="text-sm font-medium text-amber-800">提示</p>
                    <p className="text-sm text-amber-700 mt-1">
                      风险阈值由系统管理员统一配置，如需调整请联系管理员。阈值设置将影响所有用户的预警判断。
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {showCropModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl w-full max-w-lg shadow-xl">
            <div className="flex items-center justify-between p-6 border-b border-gray-100">
              <h3 className="text-lg font-semibold text-gray-900">
                {editingCrop ? '编辑作物配置' : '添加作物配置'}
              </h3>
              <button
                onClick={() => {
                  setShowCropModal(false)
                  setEditingCrop(null)
                  reset()
                }}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <X className="w-5 h-5 text-gray-500" />
              </button>
            </div>

            <form onSubmit={handleSubmit(handleCropSubmit)} className="p-6 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    作物类型 <span className="text-red-500">*</span>
                  </label>
                  <Controller
                    name="crop_type"
                    control={control}
                    render={({ field }) => (
                      <select
                        {...field}
                        className="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent outline-none"
                      >
                        {CROP_OPTIONS.map((crop) => (
                          <option key={crop} value={crop}>
                            {CROP_TYPE_LABELS[crop]}
                          </option>
                        ))}
                      </select>
                    )}
                  />
                  {errors.crop_type && (
                    <p className="mt-1 text-sm text-red-500">{errors.crop_type.message}</p>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    品种名称 <span className="text-red-500">*</span>
                  </label>
                  <Controller
                    name="variety_name"
                    control={control}
                    render={({ field }) => (
                      <input
                        {...field}
                        type="text"
                        placeholder="如：济麦22"
                        className="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent outline-none"
                      />
                    )}
                  />
                  {errors.variety_name && (
                    <p className="mt-1 text-sm text-red-500">{errors.variety_name.message}</p>
                  )}
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  抗性等级 <span className="text-red-500">*</span>
                </label>
                <Controller
                  name="resistance_level"
                  control={control}
                  render={({ field }) => (
                    <div className="grid grid-cols-5 gap-2">
                      {RESISTANCE_LEVELS.map((level) => (
                        <button
                          key={level.value}
                          type="button"
                          onClick={() => field.onChange(level.value)}
                          className={`px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                            field.value === level.value
                              ? 'bg-green-500 text-white'
                              : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                          }`}
                        >
                          {level.label}
                        </button>
                      ))}
                    </div>
                  )}
                />
                {errors.resistance_level && (
                  <p className="mt-1 text-sm text-red-500">{errors.resistance_level.message}</p>
                )}
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  风险阈值 <span className="text-red-500">*</span>
                </label>
                <Controller
                  name="risk_threshold"
                  control={control}
                  render={({ field }) => (
                    <div className="flex items-center gap-4">
                      <input
                        {...field}
                        type="range"
                        min={0}
                        max={100}
                        onChange={(e) => field.onChange(Number(e.target.value))}
                        className="flex-1 h-2 bg-gray-200 rounded-lg appearance-none"
                      />
                      <div
                        className="w-16 text-center py-2 rounded-lg font-bold text-white"
                        style={{ backgroundColor: getRiskColor(field.value) }}
                      >
                        {field.value}
                      </div>
                    </div>
                  )}
                />
                <p className="mt-1 text-xs text-gray-500">
                  当风险指数超过此阈值时触发预警，推荐值：{RISK_THRESHOLDS.high}
                </p>
                {errors.risk_threshold && (
                  <p className="mt-1 text-sm text-red-500">{errors.risk_threshold.message}</p>
                )}
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  通知邮箱
                </label>
                <Controller
                  name="notification_email"
                  control={control}
                  render={({ field }) => (
                    <div className="relative">
                      <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                      <input
                        {...field}
                        type="email"
                        placeholder="your@email.com"
                        className="w-full pl-10 pr-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent outline-none"
                      />
                    </div>
                  )}
                />
                {errors.notification_email && (
                  <p className="mt-1 text-sm text-red-500">{errors.notification_email.message}</p>
                )}
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Webhook URL
                </label>
                <Controller
                  name="webhook_url"
                  control={control}
                  render={({ field }) => (
                    <div className="relative">
                      <Webhook className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                      <input
                        {...field}
                        type="url"
                        placeholder="https://your-domain.com/webhook"
                        className="w-full pl-10 pr-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent outline-none font-mono text-sm"
                      />
                    </div>
                  )}
                />
                {errors.webhook_url && (
                  <p className="mt-1 text-sm text-red-500">{errors.webhook_url.message}</p>
                )}
              </div>

              <div className="flex justify-end gap-3 pt-4 border-t border-gray-100">
                <button
                  type="button"
                  onClick={() => {
                    setShowCropModal(false)
                    setEditingCrop(null)
                    reset()
                  }}
                  className="px-6 py-2 border border-gray-200 rounded-lg text-gray-600 hover:bg-gray-50 transition-colors"
                >
                  取消
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting || createCropMutation.isLoading || updateCropMutation.isLoading}
                  className="px-6 py-2 bg-green-500 hover:bg-green-600 text-white rounded-lg font-medium transition-colors disabled:opacity-50 flex items-center gap-2"
                >
                  <Save className="w-4 h-4" />
                  {editingCrop ? '保存修改' : '添加配置'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

export default Settings
