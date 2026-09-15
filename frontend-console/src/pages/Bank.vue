<script setup lang="ts">
import { NButton, NInput, useDialog, useMessage } from 'naive-ui'
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, type GateReport, type TaskBrief } from '../api'
import GateModal from '../components/GateModal.vue'
import TaskCard from '../components/TaskCard.vue'
import { discardedTasks, liveTasks, refreshTasks, store } from '../store'

const router = useRouter()
const msg = useMessage()
const dialog = useDialog()
const q = ref('')
const tab = ref<'available' | 'claimed' | 'all' | 'discarded'>('available')

const items = computed(() => {
  let list = tab.value === 'discarded' ? discardedTasks.value : liveTasks.value
  if (tab.value === 'available') list = list.filter((t) => t.status === 'AVAILABLE')
  if (tab.value === 'claimed') list = list.filter((t) => t.status === 'CLAIMED' || t.status === 'QUEUED')
  const k = q.value.trim().toLowerCase()
  if (k) list = list.filter((t) => `${t.task_no} ${t.question_type} ${t.languages} ${t.prompt_preview}`.toLowerCase().includes(k))
  return list
})
const counts = computed(() => ({
  available: liveTasks.value.filter((t) => t.status === 'AVAILABLE').length,
  claimed: liveTasks.value.filter((t) => t.status === 'CLAIMED' || t.status === 'QUEUED').length,
  all: liveTasks.value.length,
  discarded: discardedTasks.value.length,
}))

const gateShow = ref(false)
const gateTask = ref<TaskBrief | null>(null)
const gateReport = ref<GateReport | null>(null)
const busyId = ref<number | null>(null)

async function claim(t: TaskBrief) {
  busyId.value = t.id
  try {
    const r = await api.claim(t.id)
    if (r.queued) {
      msg.success(`题 ${t.task_no} 已进入队列`)
      await refreshTasks()
      router.push('/runs')
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

const TABS = [
  ['available', '待领取'], ['claimed', '已领取/排队'], ['all', '全部'], ['discarded', '已废弃'],
] as const
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
      <button v-for="t in TABS" :key="t[0]"
        class="px-3 h-9 rounded-inner text-xs transition-colors" :class="tab === t[0] ? 'bg-accent/15 text-accent' : 'text-fg1 hover:text-fg0 hover:bg-bg3/60'"
        @click="tab = t[0]">
        {{ t[1] }}<span class="mono text-[12px] ml-1.5 opacity-70 nums">{{ counts[t[0]] }}</span>
      </button>
      <NInput v-model:value="q" size="small" placeholder="搜索题号 / 类型 / 语言 / 正文" clearable class="!w-72 ml-auto" />
    </div>

    <div v-if="items.length" class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
      <TaskCard v-for="t in items" :key="t.id" :task="t" :busy="busyId === t.id"
        @claim="claim(t)" @release="release(t)" @open="router.push(`/tasks/${t.id}`)"
        @discard="discard(t)" @restore="restore(t)" />
    </div>
    <div v-else class="card empty">
      <template v-if="tab === 'discarded'">没有废弃的题</template>
      <template v-else-if="store.tasks.length">没有匹配的题</template>
      <template v-else>prompt.md 中没有可解析的题，请检查格式后重新扫描</template>
    </div>

    <GateModal v-model:show="gateShow" :task="gateTask" :report="gateReport" @recheck="recheck" @queued="refreshTasks" />
  </div>
</template>
