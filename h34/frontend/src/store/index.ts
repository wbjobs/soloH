import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { User, CropType, RiskLevel } from '@/types'

interface AppState {
  user: User | null
  accessToken: string | null
  isAuthenticated: boolean
  selectedCropType: CropType
  selectedDate: string
  mapCenter: [number, number]
  mapZoom: number
  riskLevelFilter: RiskLevel | 'all'
  sidebarOpen: boolean

  setUser: (user: User | null) => void
  setAccessToken: (token: string | null) => void
  login: (user: User, token: string) => void
  logout: () => void
  setSelectedCropType: (cropType: CropType) => void
  setSelectedDate: (date: string) => void
  setMapCenter: (center: [number, number]) => void
  setMapZoom: (zoom: number) => void
  setRiskLevelFilter: (level: RiskLevel | 'all') => void
  toggleSidebar: () => void
  setSidebarOpen: (open: boolean) => void
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      user: null,
      accessToken: null,
      isAuthenticated: false,
      selectedCropType: 'wheat',
      selectedDate: new Date().toISOString().split('T')[0],
      mapCenter: [116.4074, 39.9042],
      mapZoom: 10,
      riskLevelFilter: 'all',
      sidebarOpen: true,

      setUser: (user) => set({ user }),
      setAccessToken: (accessToken) => set({ accessToken, isAuthenticated: !!accessToken }),
      login: (user, accessToken) => set({ user, accessToken, isAuthenticated: true }),
      logout: () => set({ user: null, accessToken: null, isAuthenticated: false }),
      setSelectedCropType: (selectedCropType) => set({ selectedCropType }),
      setSelectedDate: (selectedDate) => set({ selectedDate }),
      setMapCenter: (mapCenter) => set({ mapCenter }),
      setMapZoom: (mapZoom) => set({ mapZoom }),
      setRiskLevelFilter: (riskLevelFilter) => set({ riskLevelFilter }),
      toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
      setSidebarOpen: (sidebarOpen) => set({ sidebarOpen }),
    }),
    {
      name: 'app-storage',
      partialize: (state) => ({
        user: state.user,
        accessToken: state.accessToken,
        isAuthenticated: state.isAuthenticated,
        selectedCropType: state.selectedCropType,
        mapCenter: state.mapCenter,
        mapZoom: state.mapZoom,
        sidebarOpen: state.sidebarOpen,
      }),
    }
  )
)

export const useAuth = () => {
  const { user, accessToken, isAuthenticated, login, logout, setUser, setAccessToken } = useAppStore()
  return { user, accessToken, isAuthenticated, login, logout, setUser, setAccessToken }
}

export const useMapSettings = () => {
  const { mapCenter, mapZoom, setMapCenter, setMapZoom } = useAppStore()
  return { mapCenter, mapZoom, setMapCenter, setMapZoom }
}

export const useFilters = () => {
  const { selectedCropType, selectedDate, riskLevelFilter, setSelectedCropType, setSelectedDate, setRiskLevelFilter } = useAppStore()
  return { selectedCropType, selectedDate, riskLevelFilter, setSelectedCropType, setSelectedDate, setRiskLevelFilter }
}

export const useUI = () => {
  const { sidebarOpen, toggleSidebar, setSidebarOpen } = useAppStore()
  return { sidebarOpen, toggleSidebar, setSidebarOpen }
}
