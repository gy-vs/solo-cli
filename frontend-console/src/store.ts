/** 轻量全局状态：系统状态 + 任务列表，供各页面共享并由 SSE 驱动刷新。 */
import { computed, reactive, ref } from 'vue'
import { api, SIDES, type HostHealth, type SystemStatus, type TaskBrief } from './api'

export const store = reactive({
  status: null as SystemStatus | null,
  tasks: [] as TaskBrief[],
  loadingTasks: false,
  lastRefresh: 0,
  /** 宿主机代理。null 表示还没问过 */
  host: null as HostHealth | null,
})

let pending: number | null = null

export async function refreshStatus() {
  try { store.status = await api.status() } catch { /* 顶栏会显示断连 */ }
}

/** 宿主机代理的近况。录屏按钮要靠它判断能不能点，正在录的是哪几侧也从这儿来 */
export async function refreshHost() {
  try { store.host = await api.hostHealth() } catch {
    store.host = { ok: false, reachable: false, message: '问不到宿主机代理', screens: [], recordings: [] }
  }
}

/** 上一轮每道题的原样内容，用来认出「这题其实没变」 */
const sigs = new Map<number, string>()

/** 没变的题继续用原来那个对象。
 *
 * 整个数组换新的话，每道题都是一个新对象，卡片和列表行即使内容一字未改也要全部重画一遍。
 * 而这个刷新是 SSE 一有动静就触发的，跑着的时候相当密集 —— 题一多，光是这一下就够卡。
 * 保住没变那些的引用，Vue 才能整块跳过它们。
 */
function mergeTasks(items: TaskBrief[]) {
  const prev = new Map(store.tasks.map((t) => [t.id, t]))
  const next = items.map((n) => {
    const sig = JSON.stringify(n)
    const kept = sigs.get(n.id) === sig ? prev.get(n.id) : undefined
    sigs.set(n.id, sig)
    return kept || n
  })
  for (const id of sigs.keys()) if (!prev.has(id) && !items.some((n) => n.id === id)) sigs.delete(id)
  // 一道都没变（顺序也一样）就连数组都不换，这一轮刷新对界面来说等于没发生
  if (next.length === store.tasks.length && next.every((t, i) => t === store.tasks[i])) return
  store.tasks = next
}

export async function refreshTasks() {
  store.loadingTasks = true
  try {
    // 一次取全（含已废弃），各页面按需过滤，避免切 tab 再发请求
    const r = await api.tasks({ include_discarded: true })
    mergeTasks(r.items)
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

/** 质检放行了、等录屏链接的题。质检排在录屏前面，所以这一批的理由不会再动了 */
export const waitingScreencast = computed(() => store.tasks.filter(
  (t) => t.status === 'QC' && SIDES.some((s) => !t.screencast?.[s]),
))

/** 结论已出、停在提交前质检这一步的题 */
export const inQc = computed(() => store.tasks.filter((t) => t.status === 'ANALYZED'))
/** 其中等着人动手的：两道里任意一道判了待人工，或者自己没跑成。
 *  不看 precheck_block —— 待质检的题那句话永远非空（说的是「质检还没过」），
 *  拿它数等于把整栏都算成要人处理。 */
export const qcPending = computed(() => inQc.value.filter(
  (t) => ['FAIL', 'ERROR'].includes(t.factcheck_status)
    || ['FAIL', 'ERROR'].includes(t.precheck_status),
))

/** 合并 SSE 高频事件，250ms 内只刷一次 */
export function scheduleRefresh() {
  if (pending) return
  pending = window.setTimeout(async () => {
    pending = null
    await Promise.all([refreshTasks(), refreshStatus()])
  }, 250)
}

/** 界面上所有「已经跑了多久」共用的这一秒。
 *
 * 它每跳一下，凡是显示时长的列表行、卡片都要跟着重画一遍，所以标签页在后台时就停下来 ——
 * 那时画给谁看都没有，白占着主线程，回到前台第一件事是把时间对上。
 */
export const nowMs = ref(Date.now())
let clock: number | null = null

function startClock() {
  if (clock === null) clock = window.setInterval(() => { nowMs.value = Date.now() }, 1000)
}
function stopClock() {
  if (clock !== null) { clearInterval(clock); clock = null }
}
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible') {
    nowMs.value = Date.now()
    startClock()
  } else stopClock()
})
startClock()
