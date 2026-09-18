<script setup lang="ts">
import { NButton, NInput, useDialog, useMessage } from 'naive-ui'
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, type GateReport, type Status, type TaskBrief } from '../api'
import GateModal from '../components/GateModal.vue'
import TaskCard from '../components/TaskCard.vue'
import { discardedTasks, liveTasks, refreshTasks, store } from '../store'

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
  { key: 'ended', label: '待分析', match: (s: Status) => s === 'RUN_DONE' || s === 'ANALYZING' },
  { key: 'analyzed', label: '待录屏上传', match: (s: Status) => s === 'ANALYZED' },
  { key: 'delivered', label: '已上传/已完成', match: (s: Status) => s === 'UPLOADED' || s === 'DONE' },
  { key: 'attention', label: '需人工', match: (s: Status) => s === 'NEEDS_ATTENTION' },
  { key: 'discarded', label: '已废弃', match: (s: Status) => s === 'DISCARDED' },
] as const

const tab = ref<(typeof TABS)[number]['key']>('all')
const matcher = computed(() => TABS.find((t) => t.key === tab.value)!.match)

const items = computed(() => {
  let list = (tab.value === 'discarded' ? discardedTasks.value : liveTasks.value).filter((t) => matcher.value(t.status))
  const k = q.value.trim().toLowerCase()
  if (k) list = list.filter((t) => `${t.task_no} ${t.question_type} ${t.languages} ${t.repo_slug} ${t.prompt_preview}`.toLowerCase().includes(k))
  return list
})
const counts = computed(() => Object.fromEntries(
  TABS.map((t) => [t.key, (t.key === 'discarded' ? discardedTasks.value : liveTasks.value).filter((x) => t.match(x.status)).length]),
) as Record<(typeof TABS)[number]['key'], number>)

/** 分支不合规的题领不了，先在列表顶上点出来 */
const badBranch = computed(() => liveTasks.value.filter((t) => t.branch_check?.ok === false))

const gateShow = ref(false)
const gateTask = ref<TaskBrief | null>(null)
const gateReport = ref<GateReport | null>(null)
const busyId = ref<number | null>(null)

async function claim(t: TaskBrief) {
  busyId.value = t.id
  try {
    const r = await api.claim(t.id)
    if (r.queued) {
      msg.success(`题 ${t.task_no} 的 A、B 两侧已进入队列`)
      await refreshTasks()
      router.push('/runs')
    } else {
      const bad = Object.entries(r.prepare?.sides || {}).filter(([, v]) => !v.ok)
      if (bad.length) msg.error(bad.map(([s, v]) => `${s} 侧：${v.message}`).join('；'), { duration: 8000 })
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
    if (r.queued) { msg.success('门禁通过，两侧已进入队列'); gateShow.value = false; await refreshTasks() }
  }
}
async function release(t: TaskBrief) {
  try { await api.release(t.id); msg.success('已放回题库'); await refreshTasks() } catch (e: any) { msg.error(e.message) }
}
function discard(t: TaskBrief) {
  dialog.warning({
    title: `废弃题 ${t.task_no}`,
    content: '废弃后该题不再出现在题库与运行舱，两侧残留容器会一并销毁。轨迹与工作目录仍保留在磁盘上，之后可在「已废弃」里恢复。',
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
    content: `将对 ${ids.length} 道题逐个拉取 A、B 分支并执行门禁，通过的进队列。一道题占两个容器槽位，`
      + '排不下的会在队列里等。门禁不通过的保持「已领取」，需单独处理。',
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
</script>

<template>
  <div class="page">
    <div class="flex items-center gap-3">
      <div>
        <div class="h1">题库</div>
        <div class="text-fg1 text-xs mt-0.5">来自 <span class="mono">{{ store.status?.paths.prompt_file }}</span>，领取后拉取 A、B 分支并各起一个容器</div>
      </div>
      <div class="ml-auto flex gap-2">
        <NButton size="small" secondary :loading="importing" @click="doImport">重新扫描</NButton>
        <NButton size="small" type="primary" secondary :loading="batching" :disabled="!counts.available" @click="claimAll">
          全部领取并启动（{{ counts.available }}）
        </NButton>
      </div>
    </div>

    <div class="flex items-center gap-2 flex-wrap">
      <button v-for="t in TABS" :key="t.key"
        class="px-3 h-9 rounded-inner text-xs transition-colors"
        :class="tab === t.key ? 'bg-accent/15 text-accent' : (counts[t.key] ? 'text-fg1 hover:text-fg0 hover:bg-bg3/60' : 'text-fg2 hover:bg-bg3/60')"
        @click="tab = t.key">
        {{ t.label }}<span class="mono text-[12px] ml-1.5 opacity-70 nums">{{ counts[t.key] }}</span>
      </button>
      <NInput v-model:value="q" size="small" placeholder="搜索题号 / 类型 / 语言 / 仓库 / 正文" clearable class="!w-72 ml-auto" />
    </div>

    <div v-if="badBranch.length" class="card px-4 py-3 flex flex-wrap items-center gap-x-5 gap-y-1.5 text-xs">
      <span class="text-err">分支结构不合规，领不了：</span>
      <span v-for="t in badBranch" :key="t.id" class="flex items-center gap-1.5 text-fg1"
        :title="t.branch_check?.message">
        <span class="dot bg-err" />
        <span class="mono">#{{ t.task_no }}</span>
        <span class="mono text-fg2">{{ t.repo_slug }}</span>
      </span>
      <span class="text-fg2">仓库要恰好是 main/master 加 A、B</span>
    </div>

    <div v-if="items.length" class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
      <TaskCard v-for="t in items" :key="t.id" :task="t" :busy="busyId === t.id"
        @claim="claim(t)" @release="release(t)" @open="router.push(`/tasks/${t.id}`)"
        @discard="discard(t)" @restore="restore(t)" />
    </div>
    <div v-else class="card empty">
      <template v-if="tab === 'discarded'">没有废弃的题</template>
      <template v-else-if="store.tasks.length">没有匹配的题</template>
      <template v-else>题面文件里没有可解析的题，请检查格式后重新扫描</template>
    </div>

    <GateModal v-model:show="gateShow" :task="gateTask" :report="gateReport" @recheck="recheck" @queued="refreshTasks" />
  </div>
</template>
