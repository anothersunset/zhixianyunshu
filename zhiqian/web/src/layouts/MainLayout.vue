<template>
  <el-container class="app-shell">
    <el-aside width="220px" class="desktop-side">
      <div class="logo">智迁云枢</div>
      <el-menu
        :default-active="route.path"
        router
        background-color="#0f172a"
        text-color="#cbd5e1"
        active-text-color="#38bdf8"
      >
        <el-menu-item v-for="item in menuItems" :key="item.path" :index="item.path">
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.label }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-drawer
      v-model="mobileMenuOpen"
      class="mobile-nav-drawer"
      direction="ltr"
      size="260px"
      :with-header="false"
      append-to-body
    >
      <nav aria-label="主导航" class="mobile-nav">
        <div class="logo">智迁云枢</div>
        <el-menu
          :default-active="route.path"
          router
          background-color="#0f172a"
          text-color="#cbd5e1"
          active-text-color="#38bdf8"
          @select="mobileMenuOpen = false"
        >
          <el-menu-item v-for="item in menuItems" :key="item.path" :index="item.path">
            <el-icon><component :is="item.icon" /></el-icon>
            <span>{{ item.label }}</span>
          </el-menu-item>
        </el-menu>
      </nav>
    </el-drawer>

    <el-container class="content-shell">
      <el-header class="top-header">
        <div class="header-leading">
          <el-button
            class="menu-toggle"
            :icon="Menu"
            circle
            text
            aria-label="打开主导航"
            @click="mobileMenuOpen = true"
          />
          <div class="app-title">{{ title }}</div>
        </div>
        <div class="header-actions">
          <div class="header-select locale-control"><LocaleSwitcher /></div>
          <div class="header-select theme-control"><ThemeSwitcher /></div>
          <el-dropdown>
            <el-button text class="account-button">
              <span>{{ roleLabel }}</span>
              <el-icon><CaretBottom /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>
      <el-main class="main-content"><router-view /></el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  CaretBottom,
  Connection,
  Document,
  Edit,
  FolderOpened,
  Menu,
  Odometer,
  Operation,
  Reading,
  Setting,
} from '@element-plus/icons-vue'
import ThemeSwitcher from '@/components/ThemeSwitcher.vue'
import LocaleSwitcher from '@/components/LocaleSwitcher.vue'

const route = useRoute()
const router = useRouter()
const mobileMenuOpen = ref(false)
const title = import.meta.env.VITE_APP_TITLE || '智迁云枢'
const roleLabel = localStorage.getItem('zq_role') === 'ADMIN' ? '管理员' : '用户'
const menuItems = [
  { path: '/', label: '仪表盘', icon: Odometer },
  { path: '/projects', label: '项目', icon: FolderOpened },
  { path: '/tasks', label: '任务', icon: Operation },
  { path: '/sql-transpile', label: 'SQL 转译', icon: Edit },
  { path: '/knowledge', label: '知识库', icon: Reading },
  { path: '/ckg', label: 'CKG 图谱', icon: Connection },
  { path: '/reports', label: '报告', icon: Document },
  { path: '/settings', label: '设置', icon: Setting },
]

watch(() => route.fullPath, () => {
  mobileMenuOpen.value = false
})

function logout() {
  localStorage.removeItem('zq_token')
  localStorage.removeItem('zq_role')
  void router.push('/login')
}
</script>

<style scoped>
.app-shell {
  height: 100vh;
  min-width: 0;
}

.desktop-side,
.mobile-nav {
  background: #0f172a;
  color: #cbd5e1;
}

.desktop-side {
  flex: 0 0 220px;
  height: 100vh;
  overflow-y: auto;
}

.desktop-side :deep(.el-menu),
.mobile-nav :deep(.el-menu) {
  border-right: 0;
}

.logo {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #38bdf8;
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 2px;
}

.content-shell,
.main-content {
  min-width: 0;
}

.content-shell {
  height: 100vh;
}

.top-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex: 0 0 60px;
  height: 60px;
  padding: 0 16px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  background: var(--el-bg-color);
  color: var(--el-text-color-primary);
  font-weight: 600;
}

.header-leading,
.header-actions {
  display: flex;
  align-items: center;
  min-width: 0;
}

.header-leading {
  gap: 8px;
}

.header-actions {
  flex: 0 0 auto;
  gap: 12px;
}

.app-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.menu-toggle {
  display: none;
  flex: 0 0 auto;
}

.main-content {
  padding: 0;
  overflow: auto;
}

.mobile-nav {
  min-height: 100%;
}

@media (max-width: 1024px) {
  .desktop-side {
    display: none;
  }

  .menu-toggle {
    display: inline-flex;
  }
}

@media (max-width: 600px) {
  .top-header {
    height: 56px;
    padding: 0 8px;
    gap: 6px;
  }

  .header-actions {
    gap: 2px;
  }

  .locale-control,
  .theme-control {
    display: none;
  }

  .account-button {
    padding-inline: 6px;
  }
}
</style>
