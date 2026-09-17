/** SSE 订阅：全局任务变更 + 单题事件流。自动重连。 */
import { onBeforeUnmount, ref, type Ref } from 'vue'
import type { RunEvent, Side } from './api'

export function useGlobalEvents(onTask: (payload: any) => void) {
  let es: EventSource | null = null
  let timer: number | null = null
  const connected = ref(false)

  const open = () => {
    es = new EventSource('/api/events')
    es.onopen = () => { connected.value = true }
    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        if (data.type === 'task' || data.type === 'bank') onTask(data)
      } catch { /* ignore */ }
    }
    es.onerror = () => {
      connected.value = false
      es?.close()
      timer = window.setTimeout(open, 3000)
    }
  }
  open()
  onBeforeUnmount(() => { es?.close(); if (timer) clearTimeout(timer) })
  return { connected }
}

export function useRunEvents(taskId: number, opts?: { onFinished?: (status: string, side?: Side) => void; max?: number; side?: Side }) {
  const events: Ref<RunEvent[]> = ref([])
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

  const open = () => {
    events.value = []
    es = new EventSource(`/api/tasks/${taskId}/events${opts?.side ? '?side=' + opts.side : ''}`)
    es.onopen = () => { connected.value = true }
    es.onmessage = (e) => {
      let data: any
      try { data = JSON.parse(e.data) } catch { return }
      // 带 seq 的就是事件；不认死 type，后端少发这个字段时整段事件流不该消失
      if (data.type === 'event' || (data.seq != null && data.kind)) {
        events.value.push({ seq: data.seq, side: data.side, kind: data.kind, summary: data.summary, ts: data.ts, payload: data.payload })
        if (events.value.length > max) events.value.splice(0, events.value.length - max)
      } else if (data.type === 'thinking') {
        // 两侧各自计数：A、B 同时在跑时共用一个数字会互相跳
        thinking.value = { ...thinking.value, [data.side || 'A']: data.tokens || 0 }
      } else if (data.type === 'truncated') {
        truncated.value = true
        total.value = data.total || 0
      } else if (data.type === 'replay_done') {
        replayDone.value = true
        total.value = data.total || data.count || 0
      } else if (data.type === 'finished') {
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
  const close = () => { es?.close(); if (timer) clearTimeout(timer) }
  onBeforeUnmount(close)
  return { events, replayDone, connected, close, total, truncated, thinking }
}
