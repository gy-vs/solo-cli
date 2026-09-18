<script setup lang="ts">
/** 题目设计：输入数量 → Cursor CLI 跑 solo-prompt → 产出自动导入 → 规则 A+C 查重。 */
import { NButton, NInput, NInputNumber, NTag, useMessage } from 'naive-ui'
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, type DesignCheck, type DesignRun } from '../api'
import { DESIGN_LABEL, fmtDuration, fmtTime } from '../status'
import { refreshTasks } from '../store'

const router = useRouter()
const msg = useMessage()
const count = ref(5)
const note = ref('')
const checks = ref<DesignCheck[]>([])
const ready = ref(false)
const runs = ref<DesignRun[]>([])
const starting = ref(false)
const openLog = ref<number | null>(null)
const logBox = ref<HTMLElement | null>(null)
let timer = 0

/** agent 的进度是往后追加的，一行就够说明它正在哪一步 */
const lastLine = (r: DesignRun) => (r.log_tail || '').trimEnd().split('\n').pop() || ''

async function toggleLog(id: number) {
  openLog.value = openLog.value === id ? null : id
  await nextTick()
  if (logBox.value) logBox.value.scrollTop = logBox.value.scrollHeight
}

const CHECK_LABEL: Record<string, string> = {
  cursor_cli: 'Cursor CLI', cursor_key: 'Cursor API Key', skill: 'solo-prompt SOP',
  gh: 'GitHub CLI', gh_token: 'GitHub Token', requirements: '需求文档', dedup: '查重通道',
  pool: '跨设备查重池', isolation: '出题资料隔离',
}
/**
 * 缺了就跑不起来的项；gh 类只影响建仓库那一步，先放行。
 *
 * isolation 在列：它不是"缺了什么"，而是路径配错让模型能读到题库，
 * 这种情况下出的题全部作废，必须挡在开始之前。
 */
const BLOCKING = ['cursor_cli', 'cursor_key', 'skill', 'requirements', 'isolation']
const blocking = computed(() => checks.value.filter((c) => !c.ok && BLOCKING.includes(c.name)))
const active = computed(() => runs.value.find((r) => ['QUEUED', 'RUNNING', 'DEDUP'].includes(r.status)))

async function load() {
  try {
    const [p, r] = await Promise.all([api.designPreflight(), api.designRuns()])
    checks.value = p.checks
    ready.value = p.ready
    if (!count.value) count.value = p.default_count
    runs.value = r.items
  } catch (e: any) { msg.error(e.message) }
}
async function start() {
  if (!confirm(`设计 ${count.value} 道题？出题会在工作区建仓库、写 drafts/，过程要跑一段时间。`)) return
  starting.value = true
  try {
    await api.designStart(count.value, note.value)
    msg.success('已开始设计，进度在下面的记录里看')
    await load()
  } catch (e: any) { msg.error(e.message) } finally { starting.value = false }
}
async function cancel(r: DesignRun) {
  if (!confirm('取消这次设计？已经写进工作区的文件不会回滚。')) return
  try { await api.designCancel(r.id); await load() } catch (e: any) { msg.error(e.message) }
}
async function redoDedup(r: DesignRun) {
  try {
    const res = await api.designDedup(r.task_ids)
    msg.success(`查重完成：通过 ${res.passed}，废弃 ${res.discarded}`)
    await Promise.all([load(), refreshTasks()])
  } catch (e: any) { msg.error(e.message) }
}
onMounted(() => { load(); timer = window.setInterval(load, 5000) })
onUnmounted(() => clearInterval(timer))
</script>

<template>
  <div class="page">
    <div>
      <div class="h1">设计题目</div>
      <div class="text-fg1 text-xs mt-0.5">
        Cursor CLI 按 solo-prompt 的 SOP 出题，产出直接进题库，随后用 solo-qa 的规则 A 与规则 C 查重，命中的自动废弃
      </div>
    </div>

    <div class="card p-4 space-y-4">
      <div class="flex items-end gap-4 flex-wrap">
        <div>
          <div class="text-xs text-fg1 mb-1.5">题目数量</div>
          <NInputNumber v-model:value="count" size="small" class="w-[120px]" :min="1" :max="20" />
        </div>
        <div class="flex-1 min-w-[260px]">
          <div class="text-xs text-fg1 mb-1.5">补充说明（可选，会拼进出题指令）</div>
          <NInput v-model:value="note" size="small" placeholder="例如：集中在 Go 后端、难度偏高" />
        </div>
        <NButton type="primary" :loading="starting" :disabled="!!active || !!blocking.length" @click="start">
          {{ active ? '正在设计中' : `开始设计 ${count} 道题` }}
        </NButton>
      </div>

      <div class="flex flex-wrap gap-2 pt-1">
        <span v-for="c in checks" :key="c.name" class="inner px-2.5 py-1 text-[12px] flex items-center gap-1.5"
          :class="c.ok ? 'text-fg1' : (BLOCKING.includes(c.name) ? 'text-err' : 'text-warn')" :title="c.message">
          <span class="dot" :class="c.ok ? 'bg-ok' : (BLOCKING.includes(c.name) ? 'bg-err' : 'bg-warn')" />
          {{ CHECK_LABEL[c.name] || c.name }}
        </span>
      </div>
      <div v-if="blocking.length" class="text-xs text-err leading-5">
        还不能开始：{{ blocking.map((c) => `${CHECK_LABEL[c.name] || c.name} ${c.message}`).join('；') }}
      </div>
      <div v-else-if="checks.some((c) => !c.ok)" class="text-xs text-warn leading-5">
        能跑，但缺的这几项会影响出题中的建仓库与查重环节，建议先在设置里补上。
      </div>
    </div>

    <div class="card">
      <div class="px-4 pt-4 pb-2 flex items-center gap-3">
        <div class="h2">设计记录</div><span class="text-xs text-fg2">{{ runs.length }}</span>
      </div>
      <div v-if="!runs.length" class="empty">还没有设计过题目</div>
      <div v-for="r in runs" :key="r.id" class="border-t border-line">
        <div class="px-4 py-3 grid grid-cols-[46px_96px_1fr_170px_auto] items-center gap-3">
          <span class="mono text-xs text-fg2">#{{ r.id }}</span>
          <NTag size="small" :bordered="false"
            :type="r.status === 'DONE' ? 'success' : r.status === 'FAILED' ? 'error' : r.status === 'CANCELLED' ? 'default' : 'warning'">
            {{ DESIGN_LABEL[r.status] || r.status }}
          </NTag>
          <div class="min-w-0">
            <div class="text-xs text-fg0 truncate">
              设计 {{ r.count }} 题
              <template v-if="r.stats?.imported != null"> · 导入 {{ r.stats.imported }}</template>
              <template v-if="r.stats?.passed != null"> · 通过 {{ r.stats.passed }}</template>
              <template v-if="r.stats?.discarded"> · <span class="text-err">查重废弃 {{ r.stats.discarded }}</span></template>
            </div>
            <div class="text-[12px] truncate" :class="r.error ? 'text-err' : 'text-fg2'">
              {{ r.error || r.stats?.dedup_error || (r.status === 'RUNNING' && lastLine(r)) || r.note || r.model }}
            </div>
          </div>
          <div class="mono text-[12px] text-fg2 nums">
            <div>{{ fmtTime(r.started_at) }}</div>
            <div>耗时 {{ fmtDuration(r.started_at, r.finished_at) }}</div>
          </div>
          <div class="flex items-center gap-1">
            <NButton v-if="['QUEUED', 'RUNNING', 'DEDUP'].includes(r.status)" size="tiny" quaternary @click="cancel(r)">取消</NButton>
            <NButton v-if="r.stats?.dedup_error && r.task_ids?.length" size="tiny" quaternary @click="redoDedup(r)">重跑查重</NButton>
            <NButton size="tiny" quaternary @click="toggleLog(r.id)">
              {{ openLog === r.id ? '收起' : '日志' }}
            </NButton>
          </div>
        </div>
        <div v-if="r.stats?.task_nos?.length" class="px-4 pb-3 flex flex-wrap gap-1.5">
          <span v-for="no in r.stats.task_nos" :key="no"
            class="inner px-2 py-0.5 mono text-[12px] text-fg1 cursor-pointer hover:text-accent"
            @click="router.push(`/bank?q=${no}`)">#{{ no }}</span>
        </div>
        <div v-if="openLog === r.id" class="px-4 pb-4">
          <pre ref="logBox"
            class="inner p-3 text-[12px] text-fg1 leading-5 max-h-[320px] overflow-auto whitespace-pre-wrap">{{ r.log_tail || '（还没有输出）' }}</pre>
        </div>
      </div>
    </div>
  </div>
</template>
