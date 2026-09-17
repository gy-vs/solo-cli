<script setup lang="ts">
/** 队列管理台：看排队与在跑、调顺序与容器额度、盯看护的自动重跑。 */
import { NButton, NInputNumber, NSwitch, useMessage } from 'naive-ui'
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, type TaskBrief } from '../api'
import SideStrip from '../components/SideStrip.vue'
import { fmtTime, RUN_LABEL, SIDE_HEX } from '../status'
import { liveTasks, refreshStatus, refreshTasks, store } from '../store'

const router = useRouter()
const msg = useMessage()
const busy = ref(0)

const sch = computed(() => store.status?.scheduler)
const wd = computed(() => store.status?.watchdog)
const running = computed(() => liveTasks.value.filter((t) => t.status === 'RUNNING'))
const queued = computed(() => liveTasks.value
  .filter((t) => t.status === 'QUEUED')
  .sort((a, b) => a.priority - b.priority || (a.claimed_at || '').localeCompare(b.claimed_at || '') || a.id - b.id))
/** 被看护重跑过、或已经放弃的侧，集中列出来 */
const retried = computed(() => liveTasks.value
  .flatMap((t) => t.runs.map((r) => ({ t, r })))
  .filter((x) => x.r.attempt > 1 || x.r.abnormal?.gave_up))
const parallel = ref(0)

async function move(t: TaskBrief, direction: 'top' | 'up' | 'down' | 'bottom') {
  busy.value = t.id
  try {
    await api.queueMove(t.id, direction)
    await refreshTasks()
  } catch (e: any) { msg.error(e.message) } finally { busy.value = 0 }
}
async function release(t: TaskBrief) {
  if (!confirm(`把 #${t.task_no} 放回题库？两侧排队都会取消。`)) return
  busy.value = t.id
  try {
    await api.release(t.id)
    msg.success('已放回题库')
    await refreshTasks()
  } catch (e: any) { msg.error(e.message) } finally { busy.value = 0 }
}
async function stop(t: TaskBrief) {
  if (!confirm(`停止 #${t.task_no} 的两个容器？已产出的轨迹会保留。`)) return
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
    msg.success(`容器上限已改为 ${v}`)
  } catch (e: any) { msg.error(e.message) }
}
/** 一道题要两个空槽才起得来，卡住的原因基本都是额度不够 */
const waitReason = computed(() => {
  if (sch.value?.paused) return '出队已暂停'
  const free = (sch.value?.max_parallel ?? 0) - (sch.value?.running ?? 0)
  return free < 2 ? `等 ${2 - Math.max(0, free)} 个容器槽位` : ''
})
</script>

<template>
  <div class="page">
    <div class="flex items-start gap-3 flex-wrap">
      <div>
        <div class="h1">队列</div>
        <div class="text-fg1 text-xs mt-0.5">
          一道题占两个容器槽位，A、B 同时启动；额度不够的在这里排队。
          跑完自动提交产物并开始对比分析，中途异常由看护重跑，不用人工点
        </div>
      </div>
      <div class="ml-auto flex items-center gap-3">
        <div class="inner px-3 h-9 flex items-center gap-2 text-xs">
          <span class="text-fg1">容器上限</span>
          <NInputNumber size="tiny" class="w-[86px]" :min="2" :max="20"
            :value="parallel || sch?.max_parallel || 2" @update:value="(v) => { parallel = v || 2; setParallel(v) }" />
        </div>
        <div class="inner px-3 h-9 flex items-center gap-2 text-xs">
          <span class="text-fg1">暂停出队</span>
          <NSwitch size="small" :value="!!sch?.paused" @update:value="togglePause" />
        </div>
      </div>
    </div>

    <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
      <div class="card p-4"><div class="text-fg1 text-xs">容器占用</div>
        <div class="mono text-2xl text-fg0 nums mt-1">{{ sch?.running ?? 0 }} <span class="text-fg2 text-base">/ {{ sch?.max_parallel ?? '-' }}</span></div>
        <div class="text-[12px] text-fg2 mt-0.5">能再开 {{ Math.max(0, Math.floor(((sch?.max_parallel ?? 0) - (sch?.running ?? 0)) / 2)) }} 道题</div></div>
      <div class="card p-4"><div class="text-fg1 text-xs">排队中</div>
        <div class="mono text-2xl text-fg0 nums mt-1">{{ queued.length }}</div>
        <div class="text-[12px] text-fg2 mt-0.5">题（{{ queued.length * 2 }} 侧）</div></div>
      <div class="card p-4"><div class="text-fg1 text-xs">重跑过的侧</div>
        <div class="mono text-2xl nums mt-1" :class="retried.length ? 'text-warn' : 'text-fg0'">{{ retried.length }}</div>
        <div class="text-[12px] text-fg2 mt-0.5">上限 {{ wd?.max_retries ?? '-' }} 次</div></div>
      <div class="card p-4"><div class="text-fg1 text-xs">看护</div>
        <div class="mono text-2xl text-fg0 nums mt-1">{{ wd?.interval_seconds ?? '-' }}<span class="text-fg2 text-base">s</span></div>
        <div class="text-[12px] text-fg2 mt-0.5">巡检异常与配对完成</div></div>
    </div>

    <div class="card">
      <div class="px-4 pt-4 pb-2 flex items-center gap-3">
        <div class="h2">运行中</div><span class="text-xs text-fg2">{{ running.length }} 题 · {{ store.status?.running_sides ?? 0 }} 侧</span>
      </div>
      <div v-if="!running.length" class="empty">没有运行中的容器</div>
      <div v-for="t in running" :key="t.id"
        class="px-4 py-3 border-t border-line grid grid-cols-[56px_1fr_280px_auto] items-center gap-3 hover:bg-bg3/40 cursor-pointer"
        @click="router.push(`/tasks/${t.id}`)">
        <span class="mono text-xs text-fg0">#{{ t.task_no }}</span>
        <div class="min-w-0 text-xs text-fg1 truncate">{{ t.question_type }} · {{ t.languages }}</div>
        <SideStrip :runs="t.runs" compact />
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
        <div class="text-[12px] nums" :class="waitReason ? 'text-warn' : 'text-fg2 mono'">
          {{ waitReason || `领取 ${fmtTime(t.claimed_at)}` }}
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
        <div class="h2">看护记录</div><span class="text-xs text-fg2">{{ retried.length }}</span>
        <span class="text-[12px] text-fg2 ml-2">网关 5xx、容器消失、超时、没产出就结束，都会自动重跑</span>
      </div>
      <div v-if="!retried.length" class="empty">没有异常重跑</div>
      <div v-for="x in retried" :key="x.r.id"
        class="px-4 py-3 border-t border-line grid grid-cols-[56px_60px_92px_1fr_120px] items-center gap-3 hover:bg-bg3/40 cursor-pointer"
        @click="router.push(`/tasks/${x.t.id}`)">
        <span class="mono text-xs text-fg0">#{{ x.t.task_no }}</span>
        <span class="mono text-[12px] font-semibold" :style="{ color: SIDE_HEX[x.r.side] }">{{ x.r.side }} 侧</span>
        <span class="mono text-[12px]" :class="x.r.abnormal?.gave_up ? 'text-err' : 'text-warn'">
          第 {{ x.r.attempt }} / {{ wd?.max_retries ?? '-' }} 次
        </span>
        <div class="min-w-0 text-[12px] truncate" :class="x.r.abnormal?.gave_up ? 'text-err' : 'text-fg1'"
          :title="x.r.abnormal?.reason">
          {{ x.r.abnormal?.reason || RUN_LABEL[x.r.status] }}{{ x.r.abnormal?.gave_up ? ' · 已放弃，等人工' : '' }}
        </div>
        <span class="mono text-[12px] text-fg2 nums">{{ fmtTime(x.r.abnormal?.at) }}</span>
      </div>
    </div>
  </div>
</template>
