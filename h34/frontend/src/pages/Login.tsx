import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useMutation, useQueryClient } from 'react-query'
import { useNavigate, useLocation } from 'react-router-dom'
import { Leaf, Mail, Lock, Eye, EyeOff, AlertCircle, Loader2 } from 'lucide-react'
import { authApi } from '@/services/api'
import { useAuth } from '@/store'
import { clsx } from 'clsx'

const loginSchema = z.object({
  email: z.string().email('请输入有效的邮箱地址').min(1, '邮箱不能为空'),
  password: z.string().min(6, '密码至少需要6个字符').min(1, '密码不能为空'),
})

type LoginFormData = z.infer<typeof loginSchema>

export const Login = () => {
  const navigate = useNavigate()
  const location = useLocation()
  const queryClient = useQueryClient()
  const { login } = useAuth()
  const [showPassword, setShowPassword] = useState(false)

  const from = (location.state as any)?.from?.pathname || '/dashboard'

  const {
    register,
    handleSubmit,
    formState: { errors },
    setError,
  } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: '',
      password: '',
    },
  })

  const loginMutation = useMutation(
    async (data: LoginFormData) => {
      const response = await authApi.login(data)
      return response.data
    },
    {
      onSuccess: (data) => {
        if (data) {
          login(data.user, data.access_token)
          localStorage.setItem('access_token', data.access_token)
          localStorage.setItem('user', JSON.stringify(data.user))
          queryClient.clear()
          navigate(from, { replace: true })
        }
      },
      onError: (error: any) => {
        const errorMessage = error.response?.data?.message || '登录失败，请检查邮箱和密码'
        setError('root', { message: errorMessage })
      },
    }
  )

  const onSubmit = (data: LoginFormData) => {
    loginMutation.mutate(data)
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-green-50 via-white to-green-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="bg-white rounded-2xl shadow-xl border border-gray-100 p-8">
          <div className="text-center mb-8">
            <div className="w-16 h-16 bg-gradient-to-br from-green-500 to-green-600 rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-lg shadow-green-200">
              <Leaf className="w-9 h-9 text-white" />
            </div>
            <h1 className="text-2xl font-bold text-gray-900 mb-2">农业风险预警系统</h1>
            <p className="text-gray-500">请登录您的账户</p>
          </div>

          {(errors.root || loginMutation.error) && (
            <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-xl flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-red-600">
                {errors.root?.message || (loginMutation.error as any)?.response?.data?.message || '登录失败'}
              </p>
            </div>
          )}

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                邮箱地址
              </label>
              <div className="relative">
                <Mail className="absolute left-3.5 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                <input
                  type="email"
                  {...register('email')}
                  className={clsx(
                    'w-full pl-11 pr-4 py-3 border rounded-xl text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 transition-all',
                    errors.email
                      ? 'border-red-300 focus:ring-red-500 focus:border-transparent'
                      : 'border-gray-300 focus:ring-green-500 focus:border-transparent'
                  )}
                  placeholder="your@email.com"
                />
              </div>
              {errors.email && (
                <p className="mt-2 text-sm text-red-600 flex items-center gap-1">
                  <AlertCircle className="w-4 h-4" />
                  {errors.email.message}
                </p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                密码
              </label>
              <div className="relative">
                <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                <input
                  type={showPassword ? 'text' : 'password'}
                  {...register('password')}
                  className={clsx(
                    'w-full pl-11 pr-12 py-3 border rounded-xl text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 transition-all',
                    errors.password
                      ? 'border-red-300 focus:ring-red-500 focus:border-transparent'
                      : 'border-gray-300 focus:ring-green-500 focus:border-transparent'
                  )}
                  placeholder="请输入密码"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors"
                >
                  {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
              {errors.password && (
                <p className="mt-2 text-sm text-red-600 flex items-center gap-1">
                  <AlertCircle className="w-4 h-4" />
                  {errors.password.message}
                </p>
              )}
            </div>

            <div className="flex items-center justify-between">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  className="w-4 h-4 rounded border-gray-300 text-green-600 focus:ring-green-500"
                />
                <span className="text-sm text-gray-600">记住我</span>
              </label>
              <button type="button" className="text-sm text-green-600 hover:text-green-700 font-medium">
                忘记密码?
              </button>
            </div>

            <button
              type="submit"
              disabled={loginMutation.isLoading}
              className="w-full py-3.5 bg-gradient-to-r from-green-500 to-green-600 hover:from-green-600 hover:to-green-700 text-white font-semibold rounded-xl transition-all shadow-lg shadow-green-200 hover:shadow-xl hover:shadow-green-300 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {loginMutation.isLoading ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  登录中...
                </>
              ) : (
                '登 录'
              )}
            </button>
          </form>

          <div className="mt-6 pt-6 border-t border-gray-100 text-center">
            <p className="text-sm text-gray-500">
              还没有账户?{' '}
              <button className="text-green-600 hover:text-green-700 font-medium">
                立即注册
              </button>
            </p>
          </div>
        </div>

        <p className="text-center text-xs text-gray-400 mt-6">
          © 2024 农业病害风险预警系统 · 保护作物健康
        </p>
      </div>
    </div>
  )
}

export default Login
