/** 轻量全局状态：系统状态 + 任务列表，供各页面共享并由 SSE 驱动刷新。 */
import { computed, reactive, ref } from 'vue'
import { api, type SystemStatus, type TaskBrief } from './api'

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

/** repo_id → 共用这个仓库的题（废弃的不算，它们不会再跑） */
export const repoGroups = computed(() => {
  const m = new Map<string, TaskBrief[]>()
  for (const t of liveTasks.value) {
    if (!t.repo_id) continue
    const arr = m.get(t.repo_id)
    if (arr) arr.push(t)
    else m.set(t.repo_id, [t])
  }
  return m
})

/** 和这道题共用同一个项目的其他题。同时跑会互相盖改动，列表里要标出来。 */
export function repoMates(t: TaskBrief): TaskBrief[] {
  return (repoGroups.value.get(t.repo_id) || []).filter((x) => x.id !== t.id)
}

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
