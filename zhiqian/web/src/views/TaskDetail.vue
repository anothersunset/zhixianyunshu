<template>
  <div class="task-detail">
    <el-page-header>
      <template #content>
        <span>任务 #</span><span v-text="taskId"></span>
        <el-tag :type="connected ? 'success' : 'info'" style="margin-left:8px">
          <span v-text="connected ? '实时连接中' : '已断开'"></span>
        </el-tag>
      </template>
    </el-page-header>
    <el-progress :percentage="progress" :stroke-width="16" status="success" />
    <el-row :gutter="16" style="margin-top:16px">
      <el-col :span="10">
        <h3>Agent 时间线</h3>
        <AgentTimeline :steps="steps" />
      </el-col>
      <el-col :span="14">
        <h3>改造建议</h3>
        <SuggestionTable :task-id="taskId" />
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { useRoute } from "vue-router"
import AgentTimeline from "@/components/AgentTimeline.vue"
import SuggestionTable from "@/components/SuggestionTable.vue"
import { useTaskStream } from "@/composables/useTaskStream"

const route = useRoute()
const taskId = Number(route.params.id)
const { steps, connected, progress } = useTaskStream(taskId)
</script>
