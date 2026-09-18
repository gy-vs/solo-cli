<script setup lang="ts">
/** 队列管理台：容器视角看谁在跑、谁在等第几个，顺带盯调度与看护的心跳。 */
import { NButton, NInputNumber, NSwitch, useMessage } from 'naive-ui'
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, type TaskBrief } from '../api'
import { fmtTime, SIDE_HEX } from '../status'
import { liveTasks, nowMs, refreshStatus, refreshTasks, store } from '../store'

const router = useRouter()
const msg = useMessage()
const busy = ref(0)

const sch = computed(() => store.status?.scheduler)
const wd = computed(() => store.status?.watchdog)
/** 在跑的容器，后端已按开始时间排好 */
const running = computed(() => sch.value?.running_runs ?? [])
/** 排队的容器，第 n 项就是第 n 个拿到槽位的 */
const queue = computed(() => sch.value?.queue ?? [])
const byTaskNo = computed(() => {
  const m: Record<string, TaskBrief> = {}
  for (const t of liveTasks.value) m[t.task_no] = t
  return m
})
/** 被看护重跑过、已经放弃、或判了异常但被挂着没动的侧 */
const retried = computed(() => liveTasks.value
  .flatMap((t) => t.runs.map((r) => ({ t, r })))
  .filter((x) => x.r.attempt > 1 || x.r.timeouts > 0 || x.r.abnormal?.gave_up || x.r.abnormal?.held))
/** 异常处理暂停期间攒下的侧：等开关一关就会被重跑 */
const held = computed(() => retried.value.filter((x) => x.r.abnormal?.held))
const parallel = ref(0)

/** 循环停了要第一时间喊出来：队列停摆时界面看上去和「正好没题」一模一样 */
const stalled = computed(() => {
  const bad: string[] = []
  if (sch.value && !sch.value.alive) bad.push('调度循环已停止')
  if (wd.value && !wd.value.alive) bad.push('巡检循环已停止')
  if (sch.value?.last_error) bad.push(`调度报错：${sch.value.last_error}`)
  if (wd.value?.last_error) bad.push(`巡检报错：${wd.value.last_error}`)
  return bad
})
/** 心跳距今多少秒。调度两秒一轮，超过半分钟就不正常了 */
const beatAge = (iso?: string | null) =>
  iso ? Math.max(0, Math.round((nowMs.value - new Date(iso).getTime()) / 1000)) : null

const waitReason = computed(() => {
  if (sch.value?.paused) return '出队已暂停'
  return sch.value?.free ? '' : '等一个容器腾出来'
})

async function move(t: TaskBrief, direction: 'top' | 'up' | 'down' | 'bottom') {
  busy.value = t.id
  try {
    await api.queueMove(t.id, direction)
    await Promise.all([refreshTasks(), refreshStatus()])
  } catch (e: any) { msg.error(e.message) } finally { busy.value = 0 }
}
async function stop(taskNo: string) {
  const t = byTaskNo.value[taskNo]
  if (!t || !confirm(`停止 #${taskNo} 的容器？已产出的轨迹会保留。`)) return
  busy.value = t.id
  try {
    const r = await api.stop(t.id)
    msg.info(r.message || '已发送停止')
    await Promise.all([refreshTasks(), refreshStatus()])
  } catch (e: any) { msg.error(e.message) } finally { busy.value = 0 }
}
async function discard(taskNo: string) {
  const t = byTaskNo.value[taskNo]
  if (!t || !confirm(`废弃 #${taskNo}？在跑的容器会一并停掉，槽位立刻让给下一道。`)) return
  busy.value = t.id
  try {
    await api.discard(t.id)
    msg.success(`#${taskNo} 已废弃`)
    await Promise.all([refreshTasks(), refreshStatus()])
  } catch (e: any) { msg.error(e.message) } finally { busy.value = 0 }
}
async function togglePause(v: boolean) {
  try {
    const r = await api.queuePause(v)
    msg.info(r.message)
    await refreshStatus()
  } catch (e: any) { msg.error(e.message) }
}
async function toggleWatchdog(v: boolean) {
  try {
    const r = await api.watchdogPause(v)
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
</script>

<template>
  <div class="page">
    <div class="flex items-start gap-3 flex-wrap">
      <div>
        <div class="h1">队列</div>
        <div class="text-fg1 text-xs mt-0.5">
          排队和额度的单位都是容器：一个空槽放一个，A、B 各排各的队，谁排到谁先跑。
          两侧都跑完自动提交产物并开始对比分析，中途异常由看护重跑，次数用尽整题废弃
        </div>
      </div>
      <div class="ml-auto flex items-center gap-3">
        <div class="inner px-3 h-9 flex items-center gap-2 text-xs">
          <span class="text-fg1">容器上限</span>
          <NInputNumber size="tiny" class="w-[86px]" :min="1" :max="12"
            :value="parallel || sch?.max_parallel || 1" @update:value="(v) => { parallel = v || 1; setParallel(v) }" />
        </div>
        <div class="inner px-3 h-9 flex items-center gap-2 text-xs">
          <span class="text-fg1">暂停出队</span>
          <NSwitch size="small" :value="!!sch?.paused" @update:value="togglePause" />
        </div>
        <div class="inner px-3 h-9 flex items-center gap-2 text-xs" :class="wd?.paused ? 'border-warn/50' : ''">
          <span class="text-fg1" title="模型或网关停机时打开：跑挂的只记一笔，不重跑也不废弃">暂停异常处理</span>
          <NSwitch size="small" :value="!!wd?.paused" @update:value="toggleWatchdog" />
        </div>
      </div>
    </div>

    <div v-if="wd?.paused" class="card p-4 border-warn/50">
      <div class="text-warn text-xs font-semibold">异常处理已暂停，跑挂的题停在原地</div>
      <div class="text-[12px] text-fg1 mt-1">
        判定照做，但不自动重跑、也不因次数用尽自动废弃，工作区与轨迹原样留着。
        模型或网关停机期间就该这样：重跑会把那一侧连 .git 一起删掉重建。
        {{ held.length ? `目前挂着 ${held.length} 侧，关掉开关后会照常重跑` : '目前还没有挂起的侧' }}
      </div>
    </div>

    <div v-if="stalled.length" class="card p-4 border-err/50">
      <div class="text-err text-xs font-semibold">后台循环异常，队列可能不再前进</div>
      <div v-for="m in stalled" :key="m" class="text-[12px] text-err mt-1">{{ m }}</div>
    </div>

    <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
      <div class="card p-4"><div class="text-fg1 text-xs">容器占用</div>
        <div class="mono text-2xl nums mt-1" :class="sch?.free ? 'text-fg0' : 'text-ok'">
          {{ sch?.running ?? 0 }} <span class="text-fg2 text-base">/ {{ sch?.max_parallel ?? '-' }}</span>
        </div>
        <div class="text-[12px] mt-0.5" :class="sch?.free && queue.length ? 'text-warn' : 'text-fg2'">
          {{ sch?.free ? `空 ${sch.free} 个槽` : '已跑满' }}
        </div></div>
      <div class="card p-4"><div class="text-fg1 text-xs">排队中</div>
        <div class="mono text-2xl text-fg0 nums mt-1">{{ queue.length }}</div>
        <div class="text-[12px] text-fg2 mt-0.5">个容器 · 来自 {{ sch?.queued_tasks ?? 0 }} 道题</div></div>
      <div class="card p-4"><div class="text-fg1 text-xs">重跑过的侧</div>
        <div class="mono text-2xl nums mt-1" :class="retried.length ? 'text-warn' : 'text-fg0'">{{ retried.length }}</div>
        <div class="text-[12px] text-fg2 mt-0.5">上限 {{ wd?.max_retries ?? '-' }} 次 / 超时 {{ wd?.max_timeouts ?? '-' }} 次</div></div>
      <div class="card p-4"><div class="text-fg1 text-xs">心跳</div>
        <div class="mono text-2xl nums mt-1" :class="stalled.length ? 'text-err' : 'text-fg0'">
          {{ beatAge(sch?.last_tick_at) ?? '-' }}<span class="text-fg2 text-base">s</span>
        </div>
        <div class="text-[12px] text-fg2 mt-0.5">
          巡检 {{ beatAge(wd?.last_tick_at) ?? '-' }}s 前 · 每 {{ wd?.interval_seconds ?? '-' }}s 一轮
        </div></div>
    </div>

    <div class="card">
      <div class="px-4 pt-4 pb-2 flex items-center gap-3">
        <div class="h2">在跑的容器</div>
        <span class="text-xs text-fg2">{{ running.length }} / {{ sch?.max_parallel ?? '-' }}</span>
      </div>
      <div v-if="!running.length" class="empty">没有运行中的容器</div>
      <div v-for="r in running" :key="r.run_id"
        class="px-4 py-3 border-t border-line grid grid-cols-[56px_60px_1fr_90px_auto] items-center gap-3 hover:bg-bg3/40 cursor-pointer"
        @click="byTaskNo[r.task_no] && router.push(`/tasks/${byTaskNo[r.task_no].id}`)">
        <span class="mono text-xs text-fg0">#{{ r.task_no }}</span>
        <span class="mono text-[12px] font-semibold" :style="{ color: SIDE_HEX[r.side] }">{{ r.side }} 侧</span>
        <div class="min-w-0 text-xs text-fg1 truncate">
          {{ byTaskNo[r.task_no]?.question_type }} · {{ byTaskNo[r.task_no]?.languages }}
          <span v-if="r.attempt > 1" class="text-warn ml-1">第 {{ r.attempt }} 次</span>
        </div>
        <span class="mono text-[12px] text-fg2 nums">{{ r.minutes }} 分钟</span>
        <div class="flex items-center gap-1">
          <NButton size="tiny" quaternary @click.stop="stop(r.task_no)">停止</NButton>
          <NButton size="tiny" quaternary @click.stop="discard(r.task_no)">废弃</NButton>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="px-4 pt-4 pb-2 flex items-center gap-3">
        <div class="h2">排队的容器</div><span class="text-xs text-fg2">{{ queue.length }}</span>
        <span v-if="sch?.paused" class="text-xs text-warn ml-2">已暂停出队，恢复后按下面的次序启动</span>
        <span v-else-if="waitReason" class="text-xs text-fg2 ml-2">{{ waitReason }}</span>
      </div>
      <div v-if="!queue.length" class="empty">队列是空的</div>
      <div v-for="(q, i) in queue" :key="q.run_id"
        class="px-4 py-3 border-t border-line grid grid-cols-[28px_56px_60px_1fr_110px_auto] items-center gap-3 hover:bg-bg3/40">
        <span class="mono text-xs nums" :class="i < (sch?.free ?? 0) ? 'text-ok' : 'text-fg2'">{{ i + 1 }}</span>
        <span class="mono text-xs text-fg0 cursor-pointer" @click="router.push(`/tasks/${q.task_id}`)">#{{ q.task_no }}</span>
        <span class="mono text-[12px] font-semibold" :style="{ color: SIDE_HEX[q.side] }">{{ q.side }} 侧</span>
        <div class="min-w-0 cursor-pointer" @click="router.push(`/tasks/${q.task_id}`)">
          <div class="text-xs text-fg0 truncate">
            {{ byTaskNo[q.task_no]?.question_type }} · {{ byTaskNo[q.task_no]?.languages }}
          </div>
          <div class="text-[12px] text-fg2 truncate">{{ byTaskNo[q.task_no]?.prompt_preview }}</div>
        </div>
        <span class="text-[12px] nums" :class="q.requeued ? 'text-warn' : 'text-fg2 mono'">
          {{ q.requeued ? `重跑 · 第 ${q.attempt} 次` : `领取 ${fmtTime(byTaskNo[q.task_no]?.claimed_at)}` }}
        </span>
        <div class="flex items-center gap-1">
          <NButton size="tiny" quaternary :disabled="i === 0" :loading="busy === q.task_id"
            @click="byTaskNo[q.task_no] && move(byTaskNo[q.task_no], 'top')">置顶</NButton>
          <NButton size="tiny" quaternary :loading="busy === q.task_id"
            @click="byTaskNo[q.task_no] && move(byTaskNo[q.task_no], 'up')">↑</NButton>
          <NButton size="tiny" quaternary :loading="busy === q.task_id"
            @click="byTaskNo[q.task_no] && move(byTaskNo[q.task_no], 'down')">↓</NButton>
          <NButton size="tiny" quaternary @click="discard(q.task_no)">废弃</NButton>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="px-4 pt-4 pb-2 flex items-center gap-3">
        <div class="h2">看护记录</div><span class="text-xs text-fg2">{{ retried.length }}</span>
        <span v-if="wd?.paused" class="text-[12px] text-warn ml-2">
          异常处理已暂停：下面这些只是记了一笔，没有重跑也没有废弃
        </span>
        <span v-else class="text-[12px] text-fg2 ml-2">
          网关重试用尽、容器消失、超时、没产出就结束，都会自动重跑；跑满 {{ wd?.max_retries ?? '-' }} 次或超时
          {{ wd?.max_timeouts ?? '-' }} 次就整题废弃，可在题库里恢复
        </span>
      </div>
      <div v-if="!retried.length" class="empty">没有异常重跑</div>
      <div v-for="x in retried" :key="x.r.id"
        class="px-4 py-3 border-t border-line grid grid-cols-[56px_60px_112px_1fr_120px] items-center gap-3 hover:bg-bg3/40 cursor-pointer"
        @click="router.push(`/tasks/${x.t.id}`)">
        <span class="mono text-xs text-fg0">#{{ x.t.task_no }}</span>
        <span class="mono text-[12px] font-semibold" :style="{ color: SIDE_HEX[x.r.side] }">{{ x.r.side }} 侧</span>
        <span class="mono text-[12px]" :class="x.r.abnormal?.gave_up ? 'text-err' : 'text-warn'">
          <template v-if="x.r.abnormal?.held">挂起 · 未重跑</template>
          <template v-else>第 {{ x.r.attempt }} / {{ wd?.max_retries ?? '-' }} 次<span v-if="x.r.timeouts"> · 超时 {{ x.r.timeouts }}</span></template>
        </span>
        <div class="min-w-0 text-[12px] truncate" :class="x.r.abnormal?.gave_up ? 'text-err' : 'text-fg1'"
          :title="x.r.abnormal?.reason">
          {{ x.r.abnormal?.reason || x.t.auto_error }}{{ x.r.abnormal?.gave_up ? ' · 已废弃整题' : '' }}
        </div>
        <span class="mono text-[12px] text-fg2 nums">{{ fmtTime(x.r.abnormal?.at) }}</span>
      </div>
    </div>
  </div>
</template>
