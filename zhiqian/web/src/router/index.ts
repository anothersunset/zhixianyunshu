import { createRouter, createWebHashHistory } from 'vue-router'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/login', component: () => import('@/views/Login.vue'), meta: { public: true } },
    {
      path: '/',
      component: () => import('@/layouts/MainLayout.vue'),
      children: [
        { path: '', component: () => import('@/views/Dashboard.vue') },
        { path: 'projects', component: () => import('@/views/ProjectList.vue') },
        { path: 'projects/:id', component: () => import('@/views/ProjectDetail.vue') },
        { path: 'tasks', component: () => import('@/views/TaskList.vue') },
        { path: 'tasks/:id', component: () => import('@/views/TaskDetail.vue') },
        { path: 'sql-transpile', component: () => import('@/views/SqlTranspile.vue') },
        { path: 'knowledge', component: () => import('@/views/KnowledgeBase.vue') },
        { path: 'reports', component: () => import('@/views/Reports.vue') },
        { path: 'settings', component: () => import('@/views/Settings.vue') },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach((to) => {
  if (to.meta.public) return true
  const token = localStorage.getItem('zq_token')
  if (!token) return { path: '/login', query: { redirect: to.fullPath } }
  return true
})

export default router
