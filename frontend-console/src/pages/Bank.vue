<script setup lang="ts">
import { NButton, NInput, NInputNumber, useDialog, useMessage } from 'naive-ui'
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, ApiError, type GateReport, type Status, type TaskBrief } from '../api'
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

const pool = computed(() => store.status?.pool)

/** 这道题在别的设备上先被领走了。后端已经把它从本机题库里撤掉，这里只负责说一声并刷新 */
function takenBy(e: unknown): string {
  return e instanceof ApiError && e.detail?.code === 'POOL_TAKEN' ? e.detail.message : ''
}

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
  } catch (e: any) {
    const taken = takenBy(e)
    if (taken) msg.warning(`${taken}，已从本机题库移除`, { duration: 6000 })
    else msg.error(e.message)
    // 被抢走时列表必须重拉：那道题的卡片还留在页面上，不刷新就会让人反复点同一张
    await refreshTasks()
  } finally { busyId.value = null }
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

const syncing = ref(false)
async function doSync() {
  syncing.value = true
  try {
    const r = await api.syncBank()
    msg.success(r.message)
    await refreshTasks()
  } catch (e: any) { msg.error(e.message) } finally { syncing.value = false }
}
const batching = ref(false)
/** 待领取的题，按题号排（列表也是这个序），所以「前几道」指的就是看到的前几道 */
const availableIds = computed(() => liveTasks.value.filter((t) => t.status === 'AVAILABLE').map((t) => t.id))
const claimN = ref(5)
/** 想领的道数不能超过现有的，否则按钮上写着 5 道、实际只领到 2 道 */
const claimCount = computed(() => Math.min(claimN.value || 1, counts.value.available))

function claimSome() {
  batchClaim(availableIds.value.slice(0, claimCount.value), `领取前 ${claimCount.value} 道并启动`)
}
function claimAll() {
  batchClaim(availableIds.value, '全部领取并启动')
}

function batchClaim(ids: number[], title: string) {
  if (!ids.length) return
  dialog.info({
    title,
    content: `将对 ${ids.length} 道题逐个在远端登记领取，再拉取 A、B 分支并执行门禁，通过的进队列。`
      + '一道题占两个容器槽位，排不下的会在队列里等。门禁不通过的保持「已领取」，需单独处理。',
    positiveText: '开始',
    negativeText: '取消',
    onPositiveClick: async () => {
      batching.value = true
      try {
        const r = await api.batchClaim(ids)
        const ok = r.results.filter((x) => x.queued).length
        const taken = r.results.filter((x) => x.code === 'POOL_TAKEN').length
        // 被其他设备领走的单独报一句：混在「门禁未过」里会让人以为是本机环境有问题
        msg.info(`${ok} 题入队`
          + (taken ? `，${taken} 题已被其他设备领走` : '')
          + (ids.length - ok - taken ? `，${ids.length - ok - taken} 题门禁未过` : ''))
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
        <div v-if="pool?.enabled" class="text-fg1 text-xs mt-0.5">
          来自远端 <span class="mono">{{ pool.repo || '未配置仓库' }}</span>，本机标识
          <span class="mono">{{ pool.device }}</span>，共 {{ pool.total }} 道
          <span v-if="pool.claimed_by_others">，其他设备已领走 {{ pool.claimed_by_others }} 道</span>
          。领取会先在远端占位，再拉取 A、B 分支并各起一个容器
        </div>
        <div v-else class="text-fg1 text-xs mt-0.5">
          来自 <span class="mono">{{ store.status?.paths.prompt_file }}</span>，领取后拉取 A、B 分支并各起一个容器
        </div>
      </div>
      <div class="ml-auto flex gap-2 items-center">
        <NButton size="small" secondary :loading="syncing" @click="doSync">
          {{ pool?.enabled ? '同步远端题库' : '重新扫描' }}
        </NButton>
        <NInputNumber v-model:value="claimN" size="small" :min="1" :max="counts.available || 1"
          :disabled="!counts.available" class="!w-24" />
        <NButton size="small" type="primary" secondary :loading="batching" :disabled="!counts.available" @click="claimSome">
          领取 {{ claimCount }} 道
        </NButton>
        <NButton size="small" type="primary" secondary :loading="batching" :disabled="!counts.available" @click="claimAll">
          全部（{{ counts.available }}）
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

    <div v-if="pool?.enabled && pool.draftless" class="card px-4 py-3 text-xs text-fg1">
      <span class="text-warn">远端有 {{ pool.draftless }} 道题只存了 prompt 正文</span>，
      缺仓库地址与初始快照，暂时领不了。出这些题的设备同步一次就会自动补齐。
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
      <TaskCard v-for="t in items" :key="t.id" :task="t" :busy="busyId === t.id" :device="pool?.device"
        @claim="claim(t)" @release="release(t)" @open="router.push(`/tasks/${t.id}`)"
        @discard="discard(t)" @restore="restore(t)" />
    </div>
    <div v-else class="card empty">
      <template v-if="tab === 'discarded'">没有废弃的题</template>
      <template v-else-if="store.tasks.length">没有匹配的题</template>
      <template v-else-if="pool?.enabled">远端题库里没有可领的题，点右上角同步一次，或先去出一批</template>
      <template v-else>题面文件里没有可解析的题，请检查格式后重新扫描</template>
    </div>

    <GateModal v-model:show="gateShow" :task="gateTask" :report="gateReport" @recheck="recheck" @queued="refreshTasks" />
  </div>
</template>
