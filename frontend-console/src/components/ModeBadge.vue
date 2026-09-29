<script setup lang="ts">
import { computed } from 'vue'
import type { TaskBrief } from '../api'

const props = defineProps<{ task: TaskBrief; small?: boolean }>()

const dual = computed(() => props.task.run_mode === 'dual')
const modelB = computed(() => props.task.runs?.find((r) => r.side === 'B')?.model || '')
const tip = computed(() => dual.value
  ? `双模型模式：A 侧用镜像自带模型，B 侧用 ${modelB.value || '（未记录）'}`
  : '单模型模式：A、B 两侧用镜像里同一个模型各跑一次')
</script>

<template>
  <!-- 还没入队的题没有模式可言，领取时才定下来 -->
  <span v-if="task.runs?.length" class="pill shrink-0" :class="[small ? 'h-6 text-[12px]' : 'h-7 text-xs',
    dual ? 'text-accent border-accent/40 bg-accent/10' : 'text-fg2']" :title="tip">
    {{ dual ? '双模型' : '单模型' }}
  </span>
</template>
