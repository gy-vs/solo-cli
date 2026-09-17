<script setup lang="ts">
/** 队列管理台：看排队与在跑、调顺序与并发、盯自动流水线跑到哪一步。 */
import { NButton, NInputNumber, NSwitch, useMessage } from 'naive-ui'
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, type TaskBrief } from '../api'
import StatusPill from '../components/StatusPill.vue'
import { STAGE_LABEL, fmtDuration, fmtTime } from '../status'
import { liveTasks, nowMs, refreshStatus, refreshTasks, store } from '../store'

const router = useRouter()
const msg = useMessage()
const busy = ref(0)

const sch = computed(() => store.status?.scheduler)
const pipe = computed(() => store.status?.pipeline)
const running = computed(() => liveTasks.value.filter((t) => t.status === 'RUNNING'))
const queued = computed(() => liveTasks.value
  .filter((t) => t.status === 'QUEUED')
  .sort((a, b) => a.priority - b.priority || (a.claimed_at || '').localeCompare(b.claimed_at || '') || a.id - b.id))
/** 正在跑自动流水线（销毁/分析/质检）的题 */
const inPipeline = computed(() => liveTasks.value.filter(
  (t) => t.auto_stage && t.auto_stage !== 'done' && t.status !== 'RUNNING'))
const parallel = ref(0)

async function move(t: TaskBrief, direction: 'top' | 'up' | 'down' | 'bottom') {
  busy.value = t.id
  try {
    await api.queueMove(t.id, direction)
    await refreshTasks()
  } catch (e: any) { msg.error(e.message) } finally { busy.value = 0 }
}
async function release(t: TaskBrief) {
  if (!confirm(`把 #${t.task_no} 放回题库？排队会取消。`)) return
  busy.value = t.id
  try {
    await api.release(t.id)
    msg.success('已放回题库')
    await refreshTasks()
  } catch (e: any) { msg.error(e.message) } finally { busy.value = 0 }
}
async function stop(t: TaskBrief) {
  if (!confirm(`停止 #${t.task_no} 的容器？已产出的轨迹会保留。`)) return
  busy.value = t.id
  try {
    const r = await api.stop(t.id)
    msg.info(r.message || '已发送停止')
    await refreshTasks()
  } catch (e: any) { msg.error(e.message) } finally { busy.value = 0 }
}
async function togglePause(v: boolean) {
  try {
    const r = await api.queuePause(v)
    msg.info(r.message)
    await refreshStatus()
  } catch (e: any) { msg.error(e.message) }
}
async function setParallel(v: number | null) {
  if (!v) return
  try {
    await api.queueParallel(v)
    await refreshStatus()
    msg.success(`并发上限已改为 ${v}`)
  } catch (e: any) { msg.error(e.message) }
}
/** 有槽位也起不来的原因：同项目有题在跑，一个项目同时只跑一道 */
function waitReason(t: TaskBrief): string {
  const w = sch.value?.repo_waiting?.find((x) => x.id === t.id)
  return w ? `等 #${w.blocked_by} 跑完（同项目）` : ''
}
function stageText(t: TaskBrief): string {
  if (t.auto_error) return t.auto_error
  return STAGE_LABEL[t.auto_stage] || '等待'
}
</script>

<template>
  <div class="page">
    <div class="flex items-start gap-3 flex-wrap">
      <div>
        <div class="h1">队列</div>
        <div class="text-fg1 text-xs mt-0.5">
          超出并发的题在这里排队，前面的一结束就自动补位；一个项目同时只跑一道题；
          结束后自动销毁容器、分析、质检，不用人工点
        </div>
      </div>
      <div class="ml-auto flex items-center gap-3">
        <div class="inner px-3 h-9 flex items-center gap-2 text-xs">
          <span class="text-fg1">并发上限</span>
          <NInputNumber size="tiny" class="w-[86px]" :min="1" :max="10"
            :value="parallel || sch?.max_parallel || 1" @update:value="(v) => { parallel = v || 1; setParallel(v) }" />
        </div>
        <div class="inner px-3 h-9 flex items-center gap-2 text-xs">
          <span class="text-fg1">暂停出队</span>
          <NSwitch size="small" :value="!!sch?.paused" @update:value="togglePause" />
        </div>
      </div>
    </div>

    <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
      <div class="card p-4"><div class="text-fg1 text-xs">运行中</div>
        <div class="mono text-2xl text-fg0 nums mt-1">{{ sch?.running ?? 0 }} <span class="text-fg2 text-base">/ {{ sch?.max_parallel ?? '-' }}</span></div></div>
      <div class="card p-4"><div class="text-fg1 text-xs">排队中</div>
        <div class="mono text-2xl text-fg0 nums mt-1">{{ queued.length }}</div></div>
      <div class="card p-4"><div class="text-fg1 text-xs">流水线处理中</div>
        <div class="mono text-2xl text-fg0 nums mt-1">{{ inPipeline.length }} <span class="text-fg2 text-base">/ {{ pipe?.max_parallel ?? '-' }}</span></div></div>
      <div class="card p-4"><div class="text-fg1 text-xs">自动化</div>
        <div class="flex flex-wrap gap-1.5 mt-2">
          <span class="inner px-2 py-0.5 text-[12px]" :class="pipe?.destroy ? 'text-ok' : 'text-fg2'">销毁</span>
          <span class="inner px-2 py-0.5 text-[12px]" :class="pipe?.analyze ? 'text-ok' : 'text-fg2'">分析</span>
          <span class="inner px-2 py-0.5 text-[12px]" :class="pipe?.qc ? 'text-ok' : 'text-fg2'">质检</span>
        </div></div>
    </div>

    <div class="card">
      <div class="px-4 pt-4 pb-2 flex items-center gap-3">
        <div class="h2">运行中</div><span class="text-xs text-fg2">{{ running.length }}</span>
      </div>
      <div v-if="!running.length" class="empty">没有运行中的容器</div>
      <div v-for="t in running" :key="t.id"
        class="px-4 py-3 border-t border-line grid grid-cols-[56px_92px_1fr_120px_auto] items-center gap-3 hover:bg-bg3/40 cursor-pointer"
        @click="router.push(`/tasks/${t.id}`)">
        <span class="mono text-xs text-fg0">#{{ t.task_no }}</span>
        <StatusPill :status="t.status" small />
        <div class="min-w-0 text-xs text-fg1 truncate">{{ t.question_type }} · {{ t.languages }}</div>
        <div class="mono text-[12px] text-fg1 nums">{{ fmtDuration(t.started_at, null, nowMs) }}</div>
        <NButton size="tiny" quaternary :loading="busy === t.id" @click.stop="stop(t)">停止</NButton>
      </div>
    </div>

    <div class="card">
      <div class="px-4 pt-4 pb-2 flex items-center gap-3">
        <div class="h2">排队中</div><span class="text-xs text-fg2">{{ queued.length }}</span>
        <span v-if="sch?.paused" class="text-xs text-warn ml-2">已暂停出队，恢复后按下面的顺序启动</span>
      </div>
      <div v-if="!queued.length" class="empty">队列是空的</div>
      <div v-for="(t, i) in queued" :key="t.id"
        class="px-4 py-3 border-t border-line grid grid-cols-[28px_56px_1fr_140px_auto] items-center gap-3 hover:bg-bg3/40">
        <span class="mono text-xs text-fg2 nums">{{ i + 1 }}</span>
        <span class="mono text-xs text-fg0 cursor-pointer" @click="router.push(`/tasks/${t.id}`)">#{{ t.task_no }}</span>
        <div class="min-w-0 cursor-pointer" @click="router.push(`/tasks/${t.id}`)">
          <div class="text-xs text-fg0 truncate">{{ t.question_type }} · {{ t.languages }}</div>
          <div class="text-[12px] text-fg2 truncate">{{ t.prompt_preview }}</div>
        </div>
        <div class="text-[12px] nums" :class="waitReason(t) ? 'text-warn' : 'text-fg2 mono'">
          {{ waitReason(t) || `领取 ${fmtTime(t.claimed_at)}` }}
        </div>
        <div class="flex items-center gap-1">
          <NButton size="tiny" quaternary :disabled="i === 0" :loading="busy === t.id" @click="move(t, 'top')">置顶</NButton>
          <NButton size="tiny" quaternary :disabled="i === 0" :loading="busy === t.id" @click="move(t, 'up')">↑</NButton>
          <NButton size="tiny" quaternary :disabled="i === queued.length - 1" :loading="busy === t.id" @click="move(t, 'down')">↓</NButton>
          <NButton size="tiny" quaternary @click="release(t)">放回</NButton>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="px-4 pt-4 pb-2 flex items-center gap-3">
        <div class="h2">自动流水线</div><span class="text-xs text-fg2">{{ inPipeline.length }}</span>
        <span class="text-[12px] text-fg2 ml-2">容器销毁 → 五维分析 → 质检，全部自动</span>
      </div>
      <div v-if="!inPipeline.length" class="empty">没有正在处理的题</div>
      <div v-for="t in inPipeline" :key="t.id"
        class="px-4 py-3 border-t border-line grid grid-cols-[56px_92px_1fr_auto] items-center gap-3 hover:bg-bg3/40 cursor-pointer"
        @click="router.push(`/tasks/${t.id}`)">
        <span class="mono text-xs text-fg0">#{{ t.task_no }}</span>
        <StatusPill :status="t.status" small />
        <div class="min-w-0 text-xs truncate" :class="t.auto_error ? 'text-err' : 'text-run'">{{ stageText(t) }}</div>
        <span class="mono text-[12px] text-fg2">{{ fmtTime(t.finished_at) }}</span>
      </div>
    </div>
  </div>
</template>
