<script setup lang="ts">
/** 题目列表的「最近废弃」栏。
 *
 * 一道题被废掉之后，人要回答的是三件事：为什么废的、前面那几次各跑了多久卡在哪、
 * 还值不值得捞回来再跑。三件事都在这一行里答完，不用点进详情页 —— 详情页只剩最后
 * 那一次的现场，前几次早被重跑清掉了，那些只有后端的逐次记录里有。
 */
import { NButton, NCheckbox, useDialog, useMessage } from 'naive-ui'
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api, type DiscardedTask, type DiscardKind, type RunAttemptRow, type RunStatus } from '../api'
import { fmtMs, fmtTime, HEX, RUN_LABEL, STATUS_LABEL } from '../status'
import { discardedTasks, refreshTasks } from '../store'

const props = defineProps<{ days: number }>()
const emit = defineEmits<{ 'update:days': [number] }>()

const router = useRouter()
const msg = useMessage()
const dialog = useDialog()

const DAY_OPTIONS = [1, 3, 7, 30]

const KIND_COLOR: Record<DiscardKind, string> = {
  retries: HEX.err, timeouts: HEX.err, prep: HEX.warn,
  difficulty: HEX.run, dedup: HEX.info, manual: HEX.fg1, other: HEX.fg1,
}
const OUTCOME_COLOR: Record<RunAttemptRow['outcome'], string> = {
  discard: HEX.err, failed: HEX.err, retry: HEX.warn, net_retry: HEX.info,
  manual: HEX.accent, interrupted: HEX.fg2, finished: HEX.ok, legacy: HEX.fg2,
}

const items = ref<DiscardedTask[]>([])
const loading = ref(false)
const loaded = ref(false)

async function load() {
  loading.value = true
  try {
    items.value = (await api.recentDiscarded(props.days)).items
    loaded.value = true
  } catch (e: any) {
    msg.error(e.message)
  } finally {
    loading.value = false
  }
}
onMounted(load)
watch(() => props.days, load)
// 有题进出废弃列表时才重拉。SSE 一有动静 store 就刷新，题在跑的时候相当密集，
// 盯着整份 store 拉的话每秒都在读一遍轨迹归档
watch(() => discardedTasks.value.map((t) => `${t.id}@${t.discarded_at}`).join(','), load)

// ---------------- 筛选 ----------------
const kind = ref<DiscardKind | 'all'>('all')
const kinds = computed(() => {
  const m = new Map<DiscardKind, { label: string; n: number }>()
  for (const t of items.value) {
    const k = m.get(t.kind) || { label: t.kind_label, n: 0 }
    k.n++
    m.set(t.kind, k)
  }
  return [...m].map(([key, v]) => ({ key, ...v })).sort((a, b) => b.n - a.n)
})
const shown = computed(() => (kind.value === 'all' ? items.value : items.value.filter((t) => t.kind === kind.value)))
watch(items, () => {
  if (kind.value !== 'all' && !items.value.some((t) => t.kind === kind.value)) kind.value = 'all'
})

// ---------------- 勾选 ----------------
const picked = ref(new Set<number>())
watch(shown, (list) => {
  const ids = new Set(list.map((t) => t.id))
  const keep = [...picked.value].filter((id) => ids.has(id))
  if (keep.length !== picked.value.size) picked.value = new Set(keep)
})
const allPicked = computed(() => shown.value.length > 0 && shown.value.every((t) => picked.value.has(t.id)))
function toggle(id: number, on: boolean) {
  const next = new Set(picked.value)
  on ? next.add(id) : next.delete(id)
  picked.value = next
}
function toggleAll(on: boolean) {
  picked.value = on ? new Set(shown.value.map((t) => t.id)) : new Set()
}

// ---------------- 展示 ----------------
const ATTEMPT_COLS = '52px 150px 196px 64px 64px minmax(0,1fr)'
const sec = (s: number | null | undefined) => (s == null ? '—' : fmtMs(s * 1000))
const runLabel = (s: RunStatus | '') => (s ? RUN_LABEL[s] || s : '')
/** 起止。同一天的结束时刻省掉日期，跨天的照写 —— 超时那次一跑三小时，跨零点是常事 */
function span(a: RunAttemptRow): string {
  if (!a.started_at) return '时间未留存'
  const s = fmtTime(a.started_at)
  if (!a.finished_at) return `${s.slice(0, -3)} → 未记结束`
  const e = fmtTime(a.finished_at)
  return `${s.slice(0, -3)} → ${e.slice(0, 5) === s.slice(0, 5) ? e.slice(6, -3) : e.slice(0, -3)}`
}

/** 恢复之后会发生什么。跑到一半废掉的题和没跑过的题走的是两条路，得照实说 */
function restoreHint(t: DiscardedTask): string {
  if (t.discarded_from === 'RUNNING' || t.discarded_from === 'QUEUED') {
    return '正常跑完的那一侧保留，其余侧重建工作区、归档轨迹后重新排队，重跑次数从头算。'
  }
  const to = STATUS_LABEL[(t.discarded_from || 'AVAILABLE') as keyof typeof STATUS_LABEL] || t.discarded_from
  return `回到废弃前的「${to}」。` + (t.kind === 'difficulty' ? '难度筛选之后不再拦它。' : '')
}

// ---------------- 恢复 ----------------
const busy = ref(0)
const batching = ref(false)

function restore(t: DiscardedTask) {
  dialog.info({
    title: `恢复 #${t.task_no} 到池子`,
    content: restoreHint(t),
    positiveText: '恢复',
    negativeText: '取消',
    onPositiveClick: async () => {
      busy.value = t.id
      try {
        msg.success(`#${t.task_no}：${(await api.restore(t.id)).message}`)
      } catch (e: any) {
        msg.error(`#${t.task_no}：${e.message}`)
      } finally {
        busy.value = 0
        await Promise.all([refreshTasks(), load()])
      }
    },
  })
}

function restorePicked() {
  const chosen = shown.value.filter((t) => picked.value.has(t.id))
  dialog.info({
    title: `恢复 ${chosen.length} 道题到池子`,
    content: '跑到一半被废掉的，正常跑完的那一侧保留，其余侧重新排队、重跑次数从头算；'
      + '没跑过的回到废弃前的状态。逐道恢复，失败的会单独列出来。',
    positiveText: '开始',
    negativeText: '取消',
    onPositiveClick: async () => {
      batching.value = true
      const bad: string[] = []
      for (const t of chosen) {
        try { await api.restore(t.id) } catch (e: any) { bad.push(`#${t.task_no} ${e.message}`) }
      }
      batching.value = false
      picked.value = new Set()
      const ok = chosen.length - bad.length
      if (bad.length) msg.warning(`${ok} 道已恢复，${bad.length} 道没成：${bad.join('；')}`, { duration: 10000 })
      else msg.success(`${ok} 道已恢复到池子`)
      await Promise.all([refreshTasks(), load()])
    },
  })
}
</script>

<template>
  <div class="space-y-3">
    <div class="card px-4 py-2.5 flex items-center gap-2 flex-wrap text-xs">
      <span class="text-fg2">时间范围</span>
      <div class="inner flex p-0.5 gap-0.5">
        <button v-for="d in DAY_OPTIONS" :key="d"
          class="px-2.5 h-7 rounded-[6px] transition-colors"
          :class="days === d ? 'bg-bg1 text-accent shadow-card' : 'text-fg1 hover:text-fg0'"
          @click="emit('update:days', d)">
          {{ d === 1 ? '24 小时' : `${d} 天` }}
        </button>
      </div>

      <span class="w-px h-5 bg-line mx-1" />
      <button class="px-2.5 h-7 rounded-inner transition-colors"
        :class="kind === 'all' ? 'bg-accent/15 text-accent' : 'text-fg1 hover:bg-bg3/60'"
        @click="kind = 'all'">
        全部<span class="mono nums ml-1 opacity-70">{{ items.length }}</span>
      </button>
      <button v-for="k in kinds" :key="k.key" class="px-2.5 h-7 rounded-inner transition-colors"
        :class="kind === k.key ? 'bg-accent/15 text-accent' : 'text-fg1 hover:bg-bg3/60'"
        @click="kind = k.key">
        <span class="dot mr-1" :style="{ background: KIND_COLOR[k.key] }" />{{ k.label }}<span
          class="mono nums ml-1 opacity-70">{{ k.n }}</span>
      </button>

      <div class="ml-auto flex items-center gap-2">
        <template v-if="picked.size">
          <span class="text-fg0">已选 <span class="mono nums font-semibold">{{ picked.size }}</span> 道</span>
          <NButton size="small" type="primary" :loading="batching" @click="restorePicked">
            批量恢复到池子（{{ picked.size }}）
          </NButton>
          <NButton size="small" quaternary @click="picked = new Set()">清空</NButton>
        </template>
        <NButton size="small" tertiary :loading="loading" @click="load">刷新</NButton>
      </div>
    </div>

    <div class="card">
      <div class="px-4 h-10 flex items-center gap-3 border-b border-line text-[12px] text-fg2">
        <NCheckbox :checked="allPicked" :disabled="!shown.length" @update:checked="toggleAll" />
        <span>按废弃时间倒序 · 每道题列出每次废弃的原因与两侧逐次运行</span>
      </div>

      <div v-if="!shown.length" class="empty">
        {{ loading && !loaded ? '加载中…' : `最近 ${days === 1 ? '24 小时' : days + ' 天'}没有废弃的题` }}
      </div>

      <div v-for="t in shown" :key="t.id" class="px-4 py-3 border-b border-line last:border-0 space-y-2.5">
        <!-- 头：是谁、为什么废、废了几回重试了几回 -->
        <div class="flex items-center gap-3 min-w-0">
          <NCheckbox :checked="picked.has(t.id)" @update:checked="(v) => toggle(t.id, v)" />
          <button class="mono text-xs text-fg0 hover:text-accent transition-colors shrink-0"
            title="打开题目详情" @click="router.push(`/tasks/${t.id}`)">
            #{{ t.task_no }}
          </button>
          <span class="pill h-5 text-[12px] shrink-0"
            :style="{ color: KIND_COLOR[t.kind], borderColor: KIND_COLOR[t.kind] + '55', background: KIND_COLOR[t.kind] + '14' }">
            {{ t.kind_label }}
          </span>
          <span class="text-xs text-fg0 truncate min-w-0">
            {{ t.question_type || '未标任务类型' }}
            <span class="text-fg2">·</span>
            <span class="text-fg1">{{ t.languages || '—' }}</span>
          </span>

          <div class="ml-auto flex items-center gap-4 shrink-0 text-[12px]">
            <span class="text-fg1">废弃 <span class="mono nums text-err font-semibold">{{ t.discard_count }}</span> 次</span>
            <span class="text-fg1">
              重试
              <template v-for="(s, i) in t.sides" :key="s.side">
                <span v-if="i" class="text-fg2"> / </span>
                <span class="mono">{{ s.side }}</span>
                <span class="mono nums text-fg0 font-semibold ml-0.5">{{ s.retries }}</span>
              </template>
              次
            </span>
            <span class="text-fg1">累计跑 <span class="mono nums text-fg0">{{ sec(t.run_s) }}</span></span>
            <span class="mono nums text-fg2 whitespace-nowrap" title="最后一次废弃的时刻">{{ fmtTime(t.discarded_at) }}</span>
            <NButton size="tiny" type="primary" secondary :loading="busy === t.id"
              :title="restoreHint(t)" @click="restore(t)">
              恢复到池子
            </NButton>
          </div>
        </div>

        <!-- 每一次废弃。只废过一次的就只有一行 -->
        <div class="pl-8 space-y-1">
          <div v-for="(d, i) in t.discards" :key="i" class="flex items-start gap-2 text-[12px] leading-[18px]">
            <span class="mono text-fg2 shrink-0 whitespace-nowrap">第 {{ i + 1 }} 次废弃</span>
            <span class="mono nums text-fg2 shrink-0 whitespace-nowrap">{{ fmtTime(d.at) }}</span>
            <span class="shrink-0 whitespace-nowrap" :style="{ color: KIND_COLOR[d.kind] }">{{ d.kind_label }}</span>
            <span class="text-fg1 break-all">{{ d.reason || '没有留下理由' }}</span>
          </div>
        </div>

        <!-- 两侧逐次运行。上下排而不是左右并排：原因那一列是整句话，并排就只剩两个字宽 -->
        <div class="pl-8 space-y-2">
          <div v-for="s in t.sides" :key="s.side" class="inner bg-bg3/50 px-3 py-2">
            <div class="flex items-center gap-2 text-[12px] mb-1">
              <span class="mono font-semibold text-fg0">{{ s.side }} 侧</span>
              <span class="text-fg2">
                跑了 <span class="mono nums text-fg1">{{ s.attempts.length }}</span> 次
                · 重试 <span class="mono nums text-fg1">{{ s.retries }}</span> 次
                · 超时 <span class="mono nums text-fg1">{{ s.timeouts }}</span> 次
                · 共跑 <span class="mono nums text-fg1">{{ sec(s.run_s) }}</span>
              </span>
              <span v-if="s.status" class="ml-auto text-fg2">最后状态 {{ runLabel(s.status) }}</span>
            </div>

            <div v-if="!s.attempts.length" class="text-[12px] text-fg2 py-1">
              一次都没开跑，排队时随整道题一起废弃
            </div>
            <template v-else>
              <div class="grid gap-x-3 py-1 text-[11px] text-fg2" :style="{ gridTemplateColumns: ATTEMPT_COLS }">
                <span>次序</span><span>结果</span><span>开始 → 结束</span>
                <span class="text-right">耗时</span><span class="text-right" title="上一次结束到这一次开跑：归档、重建工作区、排队等槽位">排队等待</span>
                <span>原因</span>
              </div>
              <div v-for="a in s.attempts" :key="a.seq"
                class="grid gap-x-3 py-1 border-t border-line text-[12px] leading-[18px]"
                :style="{ gridTemplateColumns: ATTEMPT_COLS }">
                <span class="mono text-fg1">第 {{ a.seq }} 次</span>
                <span class="truncate" :style="{ color: OUTCOME_COLOR[a.outcome] }" :title="a.outcome_label">
                  {{ a.outcome_label }}
                </span>
                <span class="mono nums text-fg2 whitespace-nowrap">{{ span(a) }}</span>
                <span class="mono nums text-fg0 text-right">{{ sec(a.duration_s) }}</span>
                <span class="mono nums text-fg2 text-right">{{ sec(a.wait_s) }}</span>
                <span class="break-all" :class="a.legacy ? 'text-fg2 italic' : 'text-fg1'">
                  <span v-if="a.run_status" class="text-fg2 not-italic mr-1">[{{ runLabel(a.run_status) }}]</span>
                  {{ a.reason || '—' }}
                </span>
              </div>
            </template>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
