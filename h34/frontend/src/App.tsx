import { Routes, Route, Navigate, Outlet } from 'react-router-dom'
import { Sidebar } from '@/components/layout/Sidebar'
import { Header } from '@/components/layout/Header'
import { ProtectedRoute } from '@/components/layout/ProtectedRoute'
import { Login } from '@/pages/Login'
import { Dashboard } from '@/pages/Dashboard'
import { MapView } from '@/pages/MapView'
import { Alerts } from '@/pages/Alerts'
import { Settings } from '@/pages/Settings'
import { History } from '@/pages/History'
import { useUI } from '@/store'
import { clsx } from 'clsx'

const AppLayout = () => {
  const { sidebarOpen } = useUI()

  return (
    <div className="min-h-screen bg-gray-50">
      <Sidebar />
      <div
        className={clsx(
          'transition-all duration-300 min-h-screen',
          sidebarOpen ? 'ml-64' : 'ml-20'
        )}
      >
        <Header />
        <main className="min-h-[calc(100vh-4rem)]">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

const NotFound = () => {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="text-center">
        <div className="text-9xl font-bold text-gray-200 mb-4">404</div>
        <h1 className="text-2xl font-bold text-gray-900 mb-2">页面未找到</h1>
        <p className="text-gray-500 mb-6">抱歉，您访问的页面不存在或已被移除。</p>
        <button
          onClick={() => (window.location.href = '/dashboard')}
          className="px-6 py-2.5 bg-green-500 hover:bg-green-600 text-white font-medium rounded-xl transition-colors"
        >
          返回仪表盘
        </button>
      </div>
    </div>
  )
}

function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/404" element={<NotFound />} />

      <Route
        path="/"
        element={
          <ProtectedRoute>
            <AppLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="map" element={<MapView />} />
        <Route path="alerts" element={<Alerts />} />
        <Route path="history" element={<History />} />
        <Route path="settings" element={<Settings />} />
      </Route>

      <Route path="*" element={<Navigate to="/404" replace />} />
    </Routes>
  )
}

export default App
