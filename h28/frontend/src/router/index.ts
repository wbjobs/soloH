import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router';
import HomeView from '../views/HomeView.vue';
import TaskListView from '../views/TaskListView.vue';
import TaskEditorView from '../views/TaskEditorView.vue';
import AboutView from '../views/AboutView.vue';

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'home',
    component: HomeView,
    meta: { title: '首页 - 古籍文字识别系统' },
  },
  {
    path: '/tasks',
    name: 'tasks',
    component: TaskListView,
    meta: { title: '任务列表 - 古籍文字识别系统' },
  },
  {
    path: '/task/:id',
    name: 'task-editor',
    component: TaskEditorView,
    meta: { title: '校对编辑 - 古籍文字识别系统' },
    props: true,
  },
  {
    path: '/about',
    name: 'about',
    component: AboutView,
    meta: { title: '关于 - 古籍文字识别系统' },
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() {
    return { top: 0 };
  },
});

router.beforeEach((to, _from, next) => {
  if (to.meta.title) {
    document.title = to.meta.title as string;
  }
  next();
});

export default router;
