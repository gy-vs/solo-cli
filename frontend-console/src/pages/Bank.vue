<script setup lang="ts">
import { NButton, NInput, useDialog, useMessage } from 'naive-ui'
import { computed, h, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, type GateReport, type Status, type TaskBrief } from '../api'
import GateModal from '../components/GateModal.vue'
import TaskCard from '../components/TaskCard.vue'
import { RUN_END } from '../status'
import { discardedTasks, liveTasks, refreshTasks, repoGroups, repoMates, store } from '../store'

const router = useRouter()
const msg = useMessage()
const dialog = useDialog()
const q = ref('')

// 每个状态一个 tab：点过领取但没跑的题以前会从默认视图里消失，现在各归各位
const TABS = [
  { key: 'all', label: '全部', match: (s: Status) => s !== 'DISCARDED' },
  { key: 'available', label: '待领取', match: (s: Status) => s === 'AVAILABLE' },
  { key: 'claimed', label: '已领取未跑', match: (s: Status) => s === 'CLAIMED' },
  { key: 'active', label: '排队/运行中', match: (s: Status) => s === 'QUEUED' || s === 'RUNNING' },
  { key: 'ended', label: '待评审', match: (s: Status) => RUN_END.includes(s) },
  { key: 'reviewed', label: '已评审', match: (s: Status) => s === 'REVIEWED' },
  { key: 'delivered', label: '已上传/已完成', match: (s: Status) => s === 'UPLOADED' || s === 'DONE' },
  { key: 'discarded', label: '已废弃', match: (s: Status) => s === 'DISCARDED' },
] as const

const tab = ref<(typeof TABS)[number]['key']>('all')
const matcher = computed(() => TABS.find((t) => t.key === tab.value)!.match)

const items = computed(() => {
  let list = (tab.value === 'discarded' ? discardedTasks.value : liveTasks.value).filter((t) => matcher.value(t.status))
  const k = q.value.trim().toLowerCase()
  if (k) list = list.filter((t) => `${t.task_no} ${t.question_type} ${t.languages} ${t.prompt_preview}`.toLowerCase().includes(k))
  return list
})
const counts = computed(() => Object.fromEntries(
  TABS.map((t) => [t.key, (t.key === 'discarded' ? discardedTasks.value : liveTasks.value).filter((x) => t.match(x.status)).length]),
) as Record<(typeof TABS)[number]['key'], number>)

// 一个仓库被多道题共用时列出来，方便错开时间跑
const sharedRepos = computed(() => [...repoGroups.value.entries()]
  .filter(([, arr]) => arr.length > 1)
  .map(([repo, arr]) => ({
    repo,
    nos: arr.map((t) => t.task_no).sort(),
    busy: arr.filter((t) => t.status === 'RUNNING' || t.status === 'QUEUED').length,
  })))

const runningMate = (t: TaskBrief) => repoMates(t).find((m) => m.status === 'RUNNING')

const gateShow = ref(false)
const gateTask = ref<TaskBrief | null>(null)
const gateReport = ref<GateReport | null>(null)
const busyId = ref<number | null>(null)

async function claim(t: TaskBrief) {
  busyId.value = t.id
  try {
    const r = await api.claim(t.id)
    if (r.queued) {
      const blocker = runningMate(t)
      if (r.waits_repo && blocker) msg.info(`题 ${t.task_no} 已进入队列，等 #${blocker.task_no} 跑完再启动（同一个项目）`, { duration: 6000 })
      else msg.success(`题 ${t.task_no} 已进入队列`)
      await refreshTasks()
      router.push(r.waits_repo ? '/queue' : '/runs')
    } else {
      gateTask.value = t
      gateReport.value = r.gate
      gateShow.value = true
      await refreshTasks()
    }
  } catch (e: any) { msg.error(e.message) } finally { busyId.value = null }
}
async function recheck() {
  if (!gateTask.value) return
  gateReport.value = null
  gateReport.value = await api.gate(gateTask.value.id)
  if (gateReport.value.passed) {
    const r = await api.claim(gateTask.value.id)
    if (r.queued) { msg.success('门禁通过，已进入队列'); gateShow.value = false; await refreshTasks() }
  }
}
async function release(t: TaskBrief) {
  try { await api.release(t.id); msg.success('已放回题库'); await refreshTasks() } catch (e: any) { msg.error(e.message) }
}
function discard(t: TaskBrief) {
  dialog.warning({
    title: `废弃题 ${t.task_no}`,
    content: '废弃后该题不再出现在题库与运行舱，残留容器会一并销毁。轨迹与工作目录仍保留在磁盘上，之后可在「已废弃」里恢复。',
    positiveText: '确认废弃',
    negativeText: '取消',
    onPositiveClick: async () => {
      busyId.value = t.id
      try {
        const r = await api.discard(t.id)
        msg.success(r.message)
        await refreshTasks()
      } catch (e: any) { msg.error(e.message) } finally { busyId.value = null }
    },
  })
}
async function restore(t: TaskBrief) {
  busyId.value = t.id
  try {
    const r = await api.restore(t.id)
    msg.success(r.message)
    await refreshTasks()
  } catch (e: any) { msg.error(e.message) } finally { busyId.value = null }
}

const importing = ref(false)
async function doImport() {
  importing.value = true
  try {
    const r = await api.importBank()
    msg.success(`解析 ${r.parsed} 题，新增 ${r.added.length}，已存在 ${r.skipped}`)
    await refreshTasks()
  } catch (e: any) { msg.error(e.message) } finally { importing.value = false }
}
const batching = ref(false)
async function claimAll() {
  const ids = liveTasks.value.filter((t) => t.status === 'AVAILABLE').map((t) => t.id)
  if (!ids.length) return
  dialog.info({
    title: '全部领取并启动',
    content: `将对 ${ids.length} 道题逐个执行门禁并进入队列，门禁不通过的保持「已领取」，需单独处理。`,
    positiveText: '开始',
    negativeText: '取消',
    onPositiveClick: async () => {
      batching.value = true
      try {
        const r = await api.batchClaim(ids)
        const ok = r.results.filter((x) => x.queued).length
        msg.info(`${ok} 题入队，${ids.length - ok} 题门禁未过`)
        await refreshTasks()
      } catch (e: any) { msg.error(e.message) } finally { batching.value = false }
    },
  })
}

function resetTask(t: TaskBrief) {
  dialog.warning({
    title: `还原题 ${t.task_no} 到做题前`,
    content: () => h('div', { class: 'text-xs leading-6' }, [
      h('div', '会依次做这几件事，做完这道题回到「待领取」，可以重新跑：'),
      h('div', { class: 'text-fg1 mt-1' }, '销毁各轮残留容器；工作区 git clean 并回到初始快照 commit；删除各轮轨迹目录、导出的轨迹副本、分析中间产物，以及以前还原时归档下来的目录；prompt.md 里回填过的 SessionID 与 TurnID 改回占位；清空运行、续跑、分析、评审、质检记录。'),
      h('div', { class: 'text-err mt-1' }, '工作区里未提交的改动会被清掉，轨迹与分析产物是直接删除、不留归档的。'),
    ]),
    positiveText: '确认还原',
    negativeText: '取消',
    onPositiveClick: async () => {
      busyId.value = t.id
      try {
        const r = await api.resetTask(t.id)
        const bad = r.steps.filter((s) => !s.ok)
        if (r.ok) msg.success(`题 ${t.task_no} 已还原到做题前`)
        else msg.warning(`部分步骤未完成：${bad.map((s) => `${s.step}（${s.message}）`).join('；')}`)
        await refreshTasks()
      } catch (e: any) { msg.error(e.message) } finally { busyId.value = null }
    },
  })
}
</script>

<template>
  <div class="page">
    <div class="flex items-center gap-3">
      <div>
        <div class="h1">题库</div>
        <div class="text-fg1 text-xs mt-0.5">来自 <span class="mono">{{ store.status?.paths.prompt_file }}</span>，领取后进行门禁检查再启动容器</div>
      </div>
      <div class="ml-auto flex gap-2">
        <NButton size="small" secondary :loading="importing" @click="doImport">重新扫描</NButton>
        <NButton size="small" type="primary" secondary :loading="batching" :disabled="!counts.available" @click="claimAll">
          全部领取并启动（{{ counts.available }}）
        </NButton>
      </div>
    </div>

    <div class="flex items-center gap-2">
      <button v-for="t in TABS" :key="t.key"
        class="px-3 h-9 rounded-inner text-xs transition-colors"
        :class="tab === t.key ? 'bg-accent/15 text-accent' : (counts[t.key] ? 'text-fg1 hover:text-fg0 hover:bg-bg3/60' : 'text-fg2 hover:bg-bg3/60')"
        @click="tab = t.key">
        {{ t.label }}<span class="mono text-[12px] ml-1.5 opacity-70 nums">{{ counts[t.key] }}</span>
      </button>
      <NInput v-model:value="q" size="small" placeholder="搜索题号 / 类型 / 语言 / 正文" clearable class="!w-72 ml-auto" />
    </div>

    <div v-if="sharedRepos.length" class="card px-4 py-3 flex flex-wrap items-center gap-x-5 gap-y-1.5 text-xs">
      <span class="text-fg2">共用同一个项目的题，错开时间跑：</span>
      <span v-for="g in sharedRepos" :key="g.repo" class="flex items-center gap-1.5"
        :class="g.busy ? 'text-warn' : 'text-fg1'" :title="g.repo">
        <span class="dot" :class="g.busy ? 'bg-warn' : 'bg-fg2'" />
        <span class="mono">{{ g.repo.split('/')[1] }}</span>
        <span class="mono text-fg2">{{ g.nos.map((n) => `#${n}`).join(' ') }}</span>
      </span>
    </div>

    <div v-if="items.length" class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
      <TaskCard v-for="t in items" :key="t.id" :task="t" :busy="busyId === t.id" :mates="repoMates(t)"
        @claim="claim(t)" @release="release(t)" @open="router.push(`/tasks/${t.id}`)"
        @discard="discard(t)" @restore="restore(t)" @reset="resetTask(t)" />
    </div>
    <div v-else class="card empty">
      <template v-if="tab === 'discarded'">没有废弃的题</template>
      <template v-else-if="store.tasks.length">没有匹配的题</template>
      <template v-else>prompt.md 中没有可解析的题，请检查格式后重新扫描</template>
    </div>

    <GateModal v-model:show="gateShow" :task="gateTask" :report="gateReport" @recheck="recheck" @queued="refreshTasks" />
  </div>
</template>
