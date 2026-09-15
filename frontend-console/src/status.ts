import type { Status } from './api'

export const STATUS_LABEL: Record<Status, string> = {
  AVAILABLE: '待领取',
  CLAIMED: '已领取',
  QUEUED: '排队中',
  RUNNING: '运行中',
  FINISHED: '正常结束',
  FAILED: '异常结束',
  TIMEOUT: '超时',
  INTERRUPTED: '中断',
  REVIEWED: '已评审',
  UPLOADED: '已上传',
  DONE: '已完成',
  DISCARDED: '已废弃',
}

/** 状态 → 主题色 token（对应 tailwind 颜色名） */
export const STATUS_COLOR: Record<Status, string> = {
  AVAILABLE: 'fg1',
  CLAIMED: 'fg1',
  QUEUED: 'run',
  RUNNING: 'run',
  FINISHED: 'ok',
  FAILED: 'err',
  TIMEOUT: 'warn',
  INTERRUPTED: 'err',
  REVIEWED: 'ok',
  UPLOADED: 'info',
  DONE: 'fg2',
  DISCARDED: 'fg2',
}

/** 浅色主题调色板（与 tailwind.config.js 保持一致） */
export const HEX: Record<string, string> = {
  fg0: '#0F172A', fg1: '#475569', fg2: '#94A3B8',
  run: '#D97706', ok: '#059669', err: '#E11D48', warn: '#EA580C', info: '#0284C7', accent: '#4F6BED',
}

/** 核验/门禁等级 → 颜色 */
export const LEVEL_HEX: Record<string, string> = { ok: HEX.ok, pass: HEX.ok, warn: HEX.warn, block: HEX.err }

export const RUN_END: Status[] = ['FINISHED', 'FAILED', 'TIMEOUT', 'INTERRUPTED']

/** 质检结论（solo-qa 的口径） */
export const QC_LABEL: Record<string, string> = {
  PASS: '质检通过',
  REJECT: '质检打回',
  DISCARD: '建议废弃',
  INCOMPLETE: '信息不全',
}
export const QC_COLOR: Record<string, string> = {
  PASS: 'ok', REJECT: 'err', DISCARD: 'err', INCOMPLETE: 'warn',
}

/** 自动流水线阶段 */
export const STAGE_LABEL: Record<string, string> = {
  destroy: '销毁容器',
  analyze: '五维分析',
  qc: '质检中',
  done: '流水线完成',
}

export const DESIGN_LABEL: Record<string, string> = {
  QUEUED: '等待开始',
  RUNNING: '设计中',
  DEDUP: '查重中',
  DONE: '已完成',
  FAILED: '失败',
  CANCELLED: '已取消',
}
export const DESIGN_COLOR: Record<string, string> = {
  QUEUED: 'fg1', RUNNING: 'run', DEDUP: 'run', DONE: 'ok', FAILED: 'err', CANCELLED: 'fg2',
}

export const DIMS = ['delivery', 'instruction', 'planning', 'reasoning', 'execution'] as const
export const DIM_LABEL: Record<string, string> = {
  delivery: '交付完整性',
  instruction: '指令遵循',
  planning: '任务规划',
  reasoning: '推理能力',
  execution: '执行能力',
}

export function fmtTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

export function fmtDuration(startIso?: string | null, endIso?: string | null, nowMs?: number): string {
  if (!startIso) return '—'
  const s = new Date(startIso).getTime()
  const e = endIso ? new Date(endIso).getTime() : (nowMs ?? Date.now())
  const sec = Math.max(0, Math.round((e - s) / 1000))
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), r = sec % 60
  return h ? `${h}h ${m}m` : m ? `${m}m ${r}s` : `${r}s`
}

export function fmtMs(ms?: number | null): string {
  if (!ms && ms !== 0) return '—'
  return fmtDuration(new Date(0).toISOString(), new Date(ms).toISOString())
}

export function shortId(s?: string, n = 8): string {
  return s ? s.slice(0, n) : '—'
}
