/** 轻量全局状态：系统状态 + 任务列表，供各页面共享并由 SSE 驱动刷新。 */
import { computed, reactive, ref } from 'vue'
import { api, SIDES, type SystemStatus, type TaskBrief } from './api'

export const store = reactive({
  status: null as SystemStatus | null,
  tasks: [] as TaskBrief[],
  loadingTasks: false,
  lastRefresh: 0,
})

let pending: number | null = null

export async function refreshStatus() {
  try { store.status = await api.status() } catch { /* 顶栏会显示断连 */ }
}

export async function refreshTasks() {
  store.loadingTasks = true
  try {
    // 一次取全（含已废弃），各页面按需过滤，避免切 tab 再发请求
    const r = await api.tasks({ include_discarded: true })
    store.tasks = r.items
    store.lastRefresh = Date.now()
  } finally {
    store.loadingTasks = false
  }
}

/** 未废弃的题，列表页默认口径 */
export const liveTasks = computed(() => store.tasks.filter((t) => t.status !== 'DISCARDED'))
export const discardedTasks = computed(() => store.tasks.filter((t) => t.status === 'DISCARDED'))

/** 需要人工处理的题：重跑用尽或推产物失败，首页要能一眼看到 */
export const stuckTasks = computed(() => store.tasks.filter((t) => t.status === 'NEEDS_ATTENTION'))

/** 分析完、等录屏链接的题。这是流程里唯一卡人工的环节 */
export const waitingScreencast = computed(() => store.tasks.filter(
  (t) => t.status === 'ANALYZED' && SIDES.some((s) => !t.screencast?.[s]),
))

/** 合并 SSE 高频事件，250ms 内只刷一次 */
export function scheduleRefresh() {
  if (pending) return
  pending = window.setTimeout(async () => {
    pending = null
    await Promise.all([refreshTasks(), refreshStatus()])
  }, 250)
}

export const nowMs = ref(Date.now())
setInterval(() => { nowMs.value = Date.now() }, 1000)
