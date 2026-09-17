<script setup lang="ts">
/** 运行中的题卡片。A、B 双列并排，两侧各自的实时事件分开走。 */
import { NButton } from 'naive-ui'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api, SIDES, type RunEvent, type Side, type TaskBrief, type TaskRunBrief } from '../api'
import { fmtDuration, HEX, RUN_COLOR, RUN_LABEL, SIDE_HEX, STATUS_COLOR, STATUS_LABEL } from '../status'
import { nowMs } from '../store'
import StatusPill from './StatusPill.vue'

const props = defineProps<{ task: TaskBrief }>()
const emit = defineEmits<{ (e: 'stop'): void }>()
const router = useRouter()
const color = computed(() => HEX[STATUS_COLOR[props.task.status]])
const live = computed(() => props.task.runs?.some((r) => r.status === 'RUNNING'))

const bySide = computed(() => {
  const m = {} as Partial<Record<Side, TaskRunBrief>>
  for (const r of props.task.runs || []) m[r.side] = r
  return m
})
const liveSide = (s: Side) => bySide.value[s]?.status === 'RUNNING'

// 一条流拿两侧事件，按 side 各留最近 3 条工具调用
const recent = ref<Record<Side, RunEvent[]>>({ A: [], B: [] })
let es: EventSource | null = null
function connect() {
  es?.close()
  recent.value = { A: [], B: [] }
  if (!live.value) return
  es = new EventSource(`/api/tasks/${props.task.id}/events`)
  es.onmessage = (e) => {
    try {
      const d = JSON.parse(e.data)
      if (d.type !== 'event') return
      if (!['assistant', 'user', 'system', 'stderr'].includes(d.kind)) return
      const s: Side = d.side === 'B' ? 'B' : 'A'
      const arr = [...recent.value[s], d]
      if (arr.length > 3) arr.shift()
      recent.value = { ...recent.value, [s]: arr }
    } catch { /* ignore */ }
  }
}
watch(live, connect, { immediate: true })
onBeforeUnmount(() => es?.close())

const turns = (r?: TaskRunBrief) => r?.protocol?.num_turns ?? r?.artifact?.tool_calls ?? '—'
const tokens = (r?: TaskRunBrief) => {
  const u = r?.protocol?.usage
  if (!u) return '—'
  const n = (u.input_tokens || 0) + (u.output_tokens || 0) + (u.cache_read_input_tokens || 0)
  return n > 1000 ? `${(n / 1000).toFixed(1)}k` : String(n)
}
const stage = computed(() => (props.task.analysis_status === 'RUNNING' ? '对比分析中' : STATUS_LABEL[props.task.status]))

const stopping = ref('')
async function stop(side?: Side) {
  stopping.value = side || 'all'
  try { await api.stop(props.task.id, side); emit('stop') } finally { stopping.value = '' }
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
      <div class="grid grid-cols-2 gap-2">
        <div v-for="s in SIDES" :key="s" class="inner p-2.5 space-y-2 min-w-0">
          <div class="flex items-center gap-1.5">
            <span class="mono text-[11px] font-semibold w-4 h-4 inline-flex items-center justify-center rounded"
              :style="{ color: SIDE_HEX[s], background: SIDE_HEX[s] + '1f' }">{{ s }}</span>
            <span class="dot shrink-0" :class="liveSide(s) ? 'animate-breathe' : ''"
              :style="{ background: bySide[s] ? HEX[RUN_COLOR[bySide[s]!.status]] : HEX.fg2 }" />
            <span class="text-[12px] truncate"
              :style="{ color: bySide[s] ? HEX[RUN_COLOR[bySide[s]!.status]] : HEX.fg2 }">
              {{ bySide[s] ? RUN_LABEL[bySide[s]!.status] : '未建' }}
            </span>
            <NButton v-if="liveSide(s)" size="tiny" quaternary type="error" class="ml-auto"
              :loading="stopping === s" @click="stop(s)">停</NButton>
          </div>
          <div class="grid grid-cols-3 gap-1 mono text-[11px] nums">
            <div><div class="label">耗时</div><div class="text-fg0">{{ fmtDuration(bySide[s]?.started_at, bySide[s]?.finished_at, nowMs) }}</div></div>
            <div><div class="label">轮次</div><div class="text-fg0">{{ turns(bySide[s]) }}</div></div>
            <div><div class="label">tokens</div><div class="text-fg0">{{ tokens(bySide[s]) }}</div></div>
          </div>
          <div class="space-y-0.5 min-h-[52px]">
            <template v-if="liveSide(s)">
              <div v-for="e in recent[s]" :key="e.seq" class="mono text-[11px] text-fg1 truncate animate-slidein" :title="e.summary">
                <span class="text-fg2">{{ String(e.seq).padStart(3, '0') }}</span> {{ e.summary }}
              </div>
              <div v-if="!recent[s].length" class="mono text-[11px] text-fg2">等待首个事件…</div>
            </template>
            <template v-else>
              <div v-if="bySide[s]?.abnormal?.reason" class="text-[11px] text-warn truncate" :title="bySide[s]!.abnormal.reason">
                {{ bySide[s]!.abnormal.reason }}<template v-if="bySide[s]!.attempt > 1">（第 {{ bySide[s]!.attempt }} 次）</template>
              </div>
              <div v-if="bySide[s]?.error" class="text-[11px] text-err truncate" :title="bySide[s]!.error">{{ bySide[s]!.error }}</div>
              <div class="mono text-[11px] text-fg2 truncate">session {{ bySide[s]?.session_id || '—' }}</div>
            </template>
          </div>
        </div>
      </div>
      <div class="flex gap-2 opacity-70 group-hover:opacity-100 transition-opacity">
        <NButton size="small" secondary class="flex-1" @click="router.push(`/tasks/${task.id}`)">查看事件流</NButton>
        <NButton v-if="live" size="small" type="error" secondary :loading="stopping === 'all'" @click="stop()">全停</NButton>
      </div>
    </div>
  </div>
</template>
