import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores'

const LoginPage = () => import('@/pages/LoginPage.vue')
const UploadPage = () => import('@/pages/UploadPage.vue')
const AnalysisConfigPage = () => import('@/pages/AnalysisConfigPage.vue')
const TasksPage = () => import('@/pages/TasksPage.vue')
const ResultsPage = () => import('@/pages/ResultsPage.vue')
const ReferencePage = () => import('@/pages/ReferencePage.vue')
const SettingsPage = () => import('@/pages/SettingsPage.vue')
const MainLayout = () => import('@/layouts/MainLayout.vue')

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: LoginPage,
    meta: { requiresAuth: false },
  },
  {
    path: '/',
    component: MainLayout,
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        redirect: '/upload',
      },
      {
        path: 'upload',
        name: 'upload',
        component: UploadPage,
      },
      {
        path: 'analysis/config',
        name: 'analysis-config',
        component: AnalysisConfigPage,
      },
      {
        path: 'tasks',
        name: 'tasks',
        component: TasksPage,
      },
      {
        path: 'results/:taskId',
        name: 'results',
        component: ResultsPage,
      },
      {
        path: 'reference',
        name: 'reference',
        component: ReferencePage,
      },
      {
        path: 'settings',
        name: 'settings',
        component: SettingsPage,
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/upload',
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() {
    return { top: 0 }
  },
})

router.beforeEach((to, _from, next) => {
  const authStore = useAuthStore()
  const token = localStorage.getItem('access_token')
  
  if (to.meta.requiresAuth && !token) {
    next('/login')
  } else if (to.path === '/login' && token) {
    next('/upload')
  } else {
    next()
  }
})

export default router
