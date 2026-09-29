<script setup lang="ts">
import { computed } from 'vue'
import type { TaskBrief } from '../api'

const props = defineProps<{ task: TaskBrief; small?: boolean }>()

const modelB = computed(() => props.task.runs?.find((r) => r.side === 'B')?.model || '')
const view = computed(() => {
  switch (props.task.run_mode) {
    case 'dual':
      return { text: '双模型', cls: 'text-accent border-accent/40 bg-accent/10',
        tip: `双模型模式：A 侧用镜像自带模型，B 侧用 ${modelB.value || '（未记录）'}` }
    case 'auto':
      return { text: '待定', cls: 'text-fg1 border-dashed',
        tip: '自动配比：第一个容器出闸时按当天「先双模型、再单模型」的循环定' }
    default:
      return { text: '单模型', cls: 'text-fg2', tip: '单模型模式：A、B 两侧用镜像里同一个模型各跑一次' }
  }
})
</script>

<template>
  <!-- 还没入队的题没有模式可言，领取时才定下来 -->
  <span v-if="task.runs?.length" class="pill shrink-0" :class="[small ? 'h-6 text-[12px]' : 'h-7 text-xs', view.cls]"
    :title="view.tip">
    {{ view.text }}
  </span>
</template>
