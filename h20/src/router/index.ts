import { createRouter, createWebHistory } from 'vue-router'
import HomePage from '@/pages/HomePage.vue'
import DashboardPage from '@/pages/DashboardPage.vue'
import GraphExplorerPage from '@/pages/GraphExplorerPage.vue'
import AddressDetailPage from '@/pages/AddressDetailPage.vue'
import DataImportPage from '@/pages/DataImportPage.vue'
import TaskManagerPage from '@/pages/TaskManagerPage.vue'
import ClusteringPage from '@/pages/ClusteringPage.vue'
import GNNAnomalyAnalysisPage from '@/pages/GNNAnomalyAnalysisPage.vue'
import PrivacyCoinAnalysisPage from '@/pages/PrivacyCoinAnalysisPage.vue'
import ComplianceReportPage from '@/pages/ComplianceReportPage.vue'
import LoginPage from '@/pages/LoginPage.vue'
import NotFoundPage from '@/pages/NotFoundPage.vue'

const routes = [
  {
    path: '/',
    name: 'home',
    component: HomePage,
  },
  {
    path: '/login',
    name: 'login',
    component: LoginPage,
    meta: { requiresAuth: false, layout: 'empty' },
  },
  {
    path: '/dashboard',
    name: 'dashboard',
    component: DashboardPage,
    meta: { requiresAuth: true },
  },
  {
    path: '/graph',
    name: 'graph',
    component: GraphExplorerPage,
    meta: { requiresAuth: true },
  },
  {
    path: '/address/:address',
    name: 'address-detail',
    component: AddressDetailPage,
    meta: { requiresAuth: true },
    props: true,
  },
  {
    path: '/import',
    name: 'import',
    component: DataImportPage,
    meta: { requiresAuth: true },
  },
  {
    path: '/tasks',
    name: 'tasks',
    component: TaskManagerPage,
    meta: { requiresAuth: true },
  },
  {
    path: '/clustering',
    name: 'clustering',
    component: ClusteringPage,
    meta: { requiresAuth: true },
  },
  {
    path: '/gnn-analysis',
    name: 'gnn-analysis',
    component: GNNAnomalyAnalysisPage,
    meta: { requiresAuth: true },
  },
  {
    path: '/privacy-analysis',
    name: 'privacy-analysis',
    component: PrivacyCoinAnalysisPage,
    meta: { requiresAuth: true },
  },
  {
    path: '/compliance-report',
    name: 'compliance-report',
    component: ComplianceReportPage,
    meta: { requiresAuth: true },
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: NotFoundPage,
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() {
    return { top: 0 }
  },
})

router.beforeEach((to, from, next) => {
  const isAuthenticated = localStorage.getItem('auth_token')
  
  if (to.meta.requiresAuth && !isAuthenticated) {
    next({ name: 'login', query: { redirect: to.fullPath } })
  } else {
    next()
  }
})

export default router
