import { createRouter, createWebHistory } from "vue-router"

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", component: () => import("@/views/Login.vue") },
    {
      path: "/",
      component: () => import("@/layouts/AppLayout.vue"),
      meta: { requiresAuth: true },
      children: [
        { path: "", redirect: "/dashboard" },
        { path: "dashboard", component: () => import("@/views/Dashboard.vue") },
        { path: "projects", component: () => import("@/views/ProjectList.vue") },
        { path: "projects/:id", component: () => import("@/views/ProjectDetail.vue") },
        { path: "tasks", component: () => import("@/views/TaskList.vue") },
        { path: "tasks/:id", component: () => import("@/views/TaskDetail.vue") },
        { path: "kb", component: () => import("@/views/KnowledgeBase.vue") },
        { path: "reports", component: () => import("@/views/ReportCenter.vue") },
        { path: "settings", component: () => import("@/views/Settings.vue") },
      ],
    },
  ],
})

router.beforeEach((to) => {
  if (to.meta?.requiresAuth && !localStorage.getItem("zhiqian_jwt")) return "/login"
  return true
})
