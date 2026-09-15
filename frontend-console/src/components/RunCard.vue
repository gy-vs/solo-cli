<script setup lang="ts">
import { NButton } from 'naive-ui'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api, type RunEvent, type TaskBrief } from '../api'
import { fmtDuration, HEX, STATUS_COLOR, STATUS_LABEL } from '../status'
import { nowMs } from '../store'
import StatusPill from './StatusPill.vue'

const props = defineProps<{ task: TaskBrief }>()
const emit = defineEmits<{ (e: 'stop'): void }>()
const router = useRouter()
const color = computed(() => HEX[STATUS_COLOR[props.task.status]])
const live = computed(() => props.task.status === 'RUNNING')

// 运行中卡片订阅事件流，只保留最近 3 条工具调用
const recent = ref<RunEvent[]>([])
let es: EventSource | null = null
function connect() {
  es?.close()
  recent.value = []
  if (!live.value) return
  es = new EventSource(`/api/tasks/${props.task.id}/events`)
  es.onmessage = (e) => {
    try {
      const d = JSON.parse(e.data)
      if (d.type === 'event' && (d.kind === 'assistant' || d.kind === 'user' || d.kind === 'system' || d.kind === 'stderr')) {
        recent.value.push(d)
        if (recent.value.length > 3) recent.value.shift()
      }
    } catch { /* ignore */ }
  }
}
watch(live, connect, { immediate: true })
onBeforeUnmount(() => es?.close())

const turns = computed(() => props.task.protocol?.num_turns ?? props.task.artifact?.tool_calls ?? '—')
const tokens = computed(() => {
  const u = props.task.protocol?.usage
  if (!u) return '—'
  const n = (u.input_tokens || 0) + (u.output_tokens || 0) + (u.cache_read_input_tokens || 0)
  return n > 1000 ? `${(n / 1000).toFixed(1)}k` : String(n)
})
const stage = computed(() => {
  if (props.task.analysis_status === 'RUNNING') return '分析中'
  return STATUS_LABEL[props.task.status]
})
const stopping = ref(false)
async function stop() {
  stopping.value = true
  try { await api.stop(props.task.id); emit('stop') } finally { stopping.value = false }
}
</script>

<template>
  <div class="card card-hover overflow-hidden group">
    <div class="h-[3px]" :class="live ? 'animate-breathe' : ''" :style="{ background: color }" />
    <div class="p-4 space-y-3">
      <div class="flex items-center gap-2">
        <span class="mono text-xs px-2 h-6 inline-flex items-center rounded-md bg-bg3 text-fg0 border border-line">#{{ task.task_no }}</span>
        <span class="text-fg0 font-medium">{{ stage }}</span>
        <StatusPill :status="task.status" small class="ml-auto" />
      </div>
      <div class="grid grid-cols-3 gap-2">
        <div class="inner p-2">
          <div class="label">耗时</div>
          <div class="mono nums text-fg0">{{ fmtDuration(task.started_at, task.finished_at, nowMs) }}</div>
        </div>
        <div class="inner p-2">
          <div class="label">轮次/调用</div>
          <div class="mono nums text-fg0">{{ turns }}</div>
        </div>
        <div class="inner p-2">
          <div class="label">tokens</div>
          <div class="mono nums text-fg0">{{ tokens }}</div>
        </div>
      </div>
      <div class="space-y-1 min-h-[60px]">
        <template v-if="live">
          <div v-for="e in recent" :key="e.seq" class="mono text-[12px] text-fg1 truncate animate-slidein" :title="e.summary">
            <span class="text-fg2">{{ String(e.seq).padStart(3, '0') }}</span> {{ e.summary }}
          </div>
          <div v-if="!recent.length" class="mono text-[12px] text-fg2">等待首个事件…</div>
        </template>
        <template v-else>
          <div v-for="n in task.verdict_notes.slice(0, 2)" :key="n" class="text-[12px] text-warn truncate" :title="n">{{ n }}</div>
          <div v-if="task.error" class="text-[12px] text-err truncate" :title="task.error">{{ task.error }}</div>
          <div class="mono text-[12px] text-fg2 truncate">session {{ task.session_id || '—' }}</div>
        </template>
      </div>
      <div class="flex gap-2 opacity-70 group-hover:opacity-100 transition-opacity">
        <NButton size="small" secondary class="flex-1" @click="router.push(`/tasks/${task.id}`)">查看事件流</NButton>
        <NButton v-if="live" size="small" type="error" secondary :loading="stopping" @click="stop">停止</NButton>
      </div>
    </div>
  </div>
</template>
