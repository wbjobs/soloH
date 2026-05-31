import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '@/store'
import { Loader2 } from 'lucide-react'
import { ReactNode, useState, useEffect } from 'react'
import { useQuery } from 'react-query'
import { authApi } from '@/services/api'

interface ProtectedRouteProps {
  children: ReactNode
}

export const ProtectedRoute = ({ children }: ProtectedRouteProps) => {
  const location = useLocation()
  const { isAuthenticated, accessToken, setUser, setAccessToken } = useAuth()
  const [isChecking, setIsChecking] = useState(true)

  const { isLoading } = useQuery(
    ['currentUser'],
    async () => {
      if (!accessToken) {
        throw new Error('No token')
      }
      const response = await authApi.getCurrentUser()
      return response.data
    },
    {
      enabled: !!accessToken && isAuthenticated,
      onSuccess: (data) => {
        if (data) {
          setUser(data)
        }
      },
      onError: () => {
        setAccessToken(null)
      },
      onSettled: () => {
        setIsChecking(false)
      },
      retry: false,
    }
  )

  useEffect(() => {
    if (!accessToken || !isAuthenticated) {
      setIsChecking(false)
    }
  }, [accessToken, isAuthenticated])

  if (isChecking || isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="w-10 h-10 text-green-500 animate-spin" />
          <p className="text-gray-600">加载中...</p>
        </div>
      </div>
    )
  }

  if (!isAuthenticated || !accessToken) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return <>{children}</>
}

export default ProtectedRoute
