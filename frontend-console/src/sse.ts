/** SSE 订阅：全局公共流 + 单题详细事件流。自动重连。
 *
 * 浏览器对同一个域只给六个并发连接，SSE 是长连接、开着就不还。所以这里的规矩是：
 * 公共流全应用共用一条（不管几个组件、几个页面在听），单题详细流只有详情页开一条，
 * 容器日志再一条 —— 加起来最多三条，剩下的额度留给普通请求。
 *
 * 从前列表页每张运行卡各开一条自己的流，三道题在跑就吃掉一半额度，再点开详情和终端
 * 就没有连接留给 XHR 了：状态、任务列表、容器实时全在排队，界面看着就是「越点越卡」。
 */
import { onBeforeUnmount, ref, shallowRef, type Ref } from 'vue'
import type { RunEvent, Side } from './api'

/** 公共流里的运行事件摘要。列表页只显示几行字，后端就不发 payload 了 */
export interface RunEventLite { task_id: number; seq: number; side: Side; kind: string; summary: string; ts: string }

type Handler = (payload: any) => void

// ---------------- 公共流（全应用一条） ----------------

const taskHandlers = new Set<Handler>()
const runHandlers = new Set<(e: RunEventLite) => void>()
/** 连接状态是共享的：顶栏那个「实时连接」指示灯读的就是它 */
const globalConnected = ref(false)
let globalEs: EventSource | null = null
let globalTimer: number | null = null

function openGlobal() {
  globalEs = new EventSource('/api/events')
  globalEs.onopen = () => { globalConnected.value = true }
  globalEs.onmessage = (e) => {
    let data: any
    try { data = JSON.parse(e.data) } catch { return }
    if (data.type === 'run_event') {
      for (const h of runHandlers) h(data as RunEventLite)
    } else if (data.type === 'task' || data.type === 'bank') {
      for (const h of taskHandlers) h(data)
    }
  }
  globalEs.onerror = () => {
    globalConnected.value = false
    globalEs?.close()
    globalEs = null
    globalTimer = window.setTimeout(openGlobal, 3000)
  }
}

/** 最后一个听众走了才真的断开：页面间跳转时连接不该跟着断一次再连一次 */
function releaseGlobal() {
  if (taskHandlers.size || runHandlers.size) return
  globalEs?.close()
  globalEs = null
  if (globalTimer) { clearTimeout(globalTimer); globalTimer = null }
  globalConnected.value = false
}

function ensureGlobal() {
  if (!globalEs && !globalTimer) openGlobal()
}

/** 听任务状态变化。多处调用只共用一条连接 */
export function useGlobalEvents(onTask: Handler) {
  taskHandlers.add(onTask)
  ensureGlobal()
  onBeforeUnmount(() => { taskHandlers.delete(onTask); releaseGlobal() })
  return { connected: globalConnected }
}

/** 某题两侧的最近几条动静，从公共流里筛，不额外占连接。
 *
 * active 为假时不再累积：卡片跑完了就该显示收尾那份账，实时行留着只会让人以为还在跑。
 */
export function useRunFeed(taskId: () => number, active: () => boolean, keep = 3) {
  const recent = shallowRef<Record<Side, RunEventLite[]>>({ A: [], B: [] })
  const onRun = (e: RunEventLite) => {
    if (e.task_id !== taskId() || !active()) return
    if (!['assistant', 'user', 'system', 'stderr'].includes(e.kind)) return
    const s: Side = e.side === 'B' ? 'B' : 'A'
    const next = { ...recent.value }
    next[s] = [...next[s], e].slice(-keep)
    recent.value = next
  }
  runHandlers.add(onRun)
  ensureGlobal()
  onBeforeUnmount(() => { runHandlers.delete(onRun); releaseGlobal() })
  const clear = () => { recent.value = { A: [], B: [] } }
  return { recent, clear }
}

// ---------------- 单题详细流（只有详情页开） ----------------

export function useRunEvents(taskId: number, opts?: { onFinished?: (status: string, side?: Side) => void; max?: number; side?: Side }) {
  /** shallow 是有意的：payload 是嵌套很深的原始 JSON，深响应式会把每条事件整棵树都
   *  包一层代理，几百条下来光建代理就够卡一下。这里只整体替换数组，不改单条内容。 */
  const events: Ref<RunEvent[]> = shallowRef([])
  const replayDone = ref(false)
  const connected = ref(false)
  /** 事件总数与已展示条数：一次运行可能几万条，后端只回放尾部 */
  const total = ref(0)
  const truncated = ref(false)
  /** 思考 token 是按秒节流推来的进度，单独显示，不塞进事件列表 */
  const thinking = ref<Partial<Record<Side, number>>>({})
  let es: EventSource | null = null
  let timer: number | null = null
  const max = opts?.max ?? 800

  /** 事件攒一小会儿再一起进列表。
   *
   * 一条一条推的话，每条都要走一遍响应式失效、过滤、重排 —— 模型手快的时候一秒几十条，
   * 时间线就一直在重画，滚动和点击全跟着卡。攒到一帧再合并，人眼看不出差别。 */
  let buffer: RunEvent[] = []
  let flushTimer: number | null = null
  const flush = () => {
    flushTimer = null
    if (!buffer.length) return
    const next = events.value.concat(buffer)
    buffer = []
    events.value = next.length > max ? next.slice(next.length - max) : next
  }
  const scheduleFlush = () => {
    if (flushTimer === null) flushTimer = window.setTimeout(flush, 120)
  }

  const open = () => {
    events.value = []
    buffer = []
    es = new EventSource(`/api/tasks/${taskId}/events${opts?.side ? '?side=' + opts.side : ''}`)
    es.onopen = () => { connected.value = true }
    es.onmessage = (e) => {
      let data: any
      try { data = JSON.parse(e.data) } catch { return }
      // 带 seq 的就是事件；不认死 type，后端少发这个字段时整段事件流不该消失
      if (data.type === 'event' || (data.seq != null && data.kind)) {
        buffer.push({ seq: data.seq, side: data.side, kind: data.kind, summary: data.summary, ts: data.ts, payload: data.payload })
        scheduleFlush()
      } else if (data.type === 'thinking') {
        // 两侧各自计数：A、B 同时在跑时共用一个数字会互相跳
        thinking.value = { ...thinking.value, [data.side || 'A']: data.tokens || 0 }
      } else if (data.type === 'truncated') {
        truncated.value = true
        total.value = data.total || 0
      } else if (data.type === 'reload') {
        // 后端重新接管了容器并按容器日志重建了这一侧的时间线，手里这份已经过时
        close()
        open()
      } else if (data.type === 'replay_done') {
        // 回放的几百条一次进来，别等下一个合并窗口
        flush()
        replayDone.value = true
        total.value = data.total || data.count || 0
      } else if (data.type === 'finished') {
        flush()
        opts?.onFinished?.(data.status, data.side)
      }
    }
    es.onerror = () => {
      connected.value = false
      es?.close()
      timer = window.setTimeout(open, 3000)
    }
  }
  open()
  const close = () => {
    es?.close()
    es = null
    if (timer) { clearTimeout(timer); timer = null }
    if (flushTimer) { clearTimeout(flushTimer); flushTimer = null }
  }
  onBeforeUnmount(close)
  return { events, replayDone, connected, close, total, truncated, thinking }
}
