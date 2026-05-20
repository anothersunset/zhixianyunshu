<template>
  <div class="page">
    <el-card shadow="never"><template #header>迁移报告</template>
      <el-empty description="已生成 1 份演示报告" :image-size="120">
        <el-button type="primary" @click="open">查看演示报告</el-button>
      </el-empty>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ElMessageBox } from 'element-plus'
function open() {
  ElMessageBox.alert(
    '本版本为演示数据，真实报告由 Reporter Agent 在任务完成时生成，包含：1) 改造建议清单；2) 风险矩阵；3) 验证脚本执行结果；4) 数据一致性报表；5) 回滚预案。',
    '智迁云枢 · 演示报告',
    { confirmButtonText: '我知道了' },
  )
}
</script>

<style scoped>.page{padding:16px}</style>
