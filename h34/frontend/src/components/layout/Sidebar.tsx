import { NavLink, useLocation } from 'react-router-dom'
import {
  LayoutDashboard,
  Map,
  Bell,
  History,
  Settings,
  ChevronLeft,
  ChevronRight,
  Leaf,
} from 'lucide-react'
import { useUI } from '@/store'
import { clsx } from 'clsx'

const menuItems = [
  { path: '/dashboard', label: '仪表盘', icon: LayoutDashboard },
  { path: '/map', label: '风险地图', icon: Map },
  { path: '/alerts', label: '预警管理', icon: Bell },
  { path: '/history', label: '历史数据', icon: History },
  { path: '/settings', label: '系统设置', icon: Settings },
]

export const Sidebar = () => {
  const location = useLocation()
  const { sidebarOpen, toggleSidebar } = useUI()

  return (
    <aside
      className={clsx(
        'fixed left-0 top-0 z-40 h-screen bg-white border-r border-gray-200 transition-all duration-300 flex flex-col',
        sidebarOpen ? 'w-64' : 'w-20'
      )}
    >
      <div className="flex items-center justify-between h-16 px-4 border-b border-gray-200">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-gradient-to-br from-green-500 to-green-600 rounded-xl flex items-center justify-center flex-shrink-0">
            <Leaf className="w-6 h-6 text-white" />
          </div>
          {sidebarOpen && (
            <div className="flex flex-col">
              <span className="font-bold text-gray-900 text-lg">农业风险</span>
              <span className="text-xs text-gray-500">预警系统</span>
            </div>
          )}
        </div>
      </div>

      <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
        {menuItems.map((item) => {
          const Icon = item.icon
          const isActive = location.pathname === item.path
          return (
            <NavLink
              key={item.path}
              to={item.path}
              className={clsx(
                'flex items-center gap-3 px-3 py-3 rounded-xl transition-all duration-200 group',
                isActive
                  ? 'bg-green-50 text-green-600 font-medium'
                  : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
              )}
            >
              <Icon
                className={clsx(
                  'w-5 h-5 flex-shrink-0 transition-colors',
                  isActive ? 'text-green-600' : 'text-gray-400 group-hover:text-gray-600'
                )}
              />
              {sidebarOpen && <span className="whitespace-nowrap">{item.label}</span>}
              {!sidebarOpen && (
                <div className="absolute left-20 px-2 py-1 bg-gray-900 text-white text-sm rounded-md opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-50">
                  {item.label}
                </div>
              )}
            </NavLink>
          )
        })}
      </nav>

      <div className="p-4 border-t border-gray-200">
        <button
          onClick={toggleSidebar}
          className="w-full flex items-center justify-center gap-2 px-3 py-2.5 text-gray-500 hover:bg-gray-100 rounded-xl transition-colors"
        >
          {sidebarOpen ? (
            <>
              <ChevronLeft className="w-5 h-5" />
              <span>收起菜单</span>
            </>
          ) : (
            <ChevronRight className="w-5 h-5" />
          )}
        </button>
      </div>
    </aside>
  )
}

export default Sidebar
