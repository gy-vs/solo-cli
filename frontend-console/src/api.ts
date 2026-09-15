/** 后端 API 封装。所有错误统一抛 ApiError，携带后端 detail。 */

export class ApiError extends Error {
  status: number
  detail: any
  constructor(status: number, detail: any) {
    super(typeof detail === 'string' ? detail : detail?.message || detail?.detail || `HTTP ${status}`)
    this.status = status
    this.detail = detail
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
  })
  const text = await res.text()
  let body: any = null
  try { body = text ? JSON.parse(text) : null } catch { body = text }
  if (!res.ok) throw new ApiError(res.status, body?.detail ?? body)
  return body as T
}

const get = <T>(p: string) => request<T>(p)
const post = <T>(p: string, body?: any) => request<T>(p, { method: 'POST', body: body ? JSON.stringify(body) : undefined })
const put = <T>(p: string, body?: any) => request<T>(p, { method: 'PUT', body: JSON.stringify(body) })

// ---------- 类型 ----------
export type Status =
  | 'AVAILABLE' | 'CLAIMED' | 'QUEUED' | 'RUNNING' | 'FINISHED' | 'FAILED'
  | 'TIMEOUT' | 'INTERRUPTED' | 'REVIEWED' | 'UPLOADED' | 'DONE' | 'DISCARDED'

export interface TaskBrief {
  id: number
  task_no: string
  status: Status
  analysis_status: 'IDLE' | 'RUNNING' | 'DONE' | 'FAILED'
  question_type: string
  difficulty: string
  languages: string
  harness: string
  harness_version: string
  os_platform: string
  repro_level: string
  env_snapshot: string
  prompt_preview: string
  prompt_chars: number
  session_id: string
  turn_id: string
  container_name: string
  container_exists: boolean
  image_tag: string
  exit_code: number | null
  meta: Record<string, string>
  verdict_notes: string[]
  protocol: { subtype?: string; num_turns?: number; duration_ms?: number; cost_usd?: number; usage?: any }
  artifact: { trace_found?: boolean; trace_count?: number; tool_calls?: number; tool_errors?: number; changed_files?: number }
  verify_overall: 'pass' | 'warn' | 'block' | null
  upload_ok: boolean | null
  submission_id: number | null
  error: string
  created_at: string | null
  claimed_at: string | null
  started_at: string | null
  finished_at: string | null
  uploaded_at: string | null
  done_at: string | null
  discarded_at: string | null
  discarded_from: string
  qc_status: QcStatus
  qc_conclusion: string
  qc_summary: string
  qc_failed_count: number
  qc_at: string | null
  priority: number
  origin: 'bank' | 'designed'
  design_run_id: number
  auto_stage: '' | 'destroy' | 'analyze' | 'qc' | 'done'
  auto_error: string
  dedup_verdict: '' | 'pass' | 'discard' | 'unknown'
  dedup_reason: string
}

export type QcStatus = 'IDLE' | 'RUNNING' | 'DONE' | 'FAILED'

export interface ResetStep {
  step: string
  ok: boolean
  message: string
}

export interface QcCheck {
  name: string
  passed: boolean
  summary: string
  detail: string
  rule?: string
}
export interface QcResult {
  ok: boolean
  error?: string
  conclusion?: 'PASS' | 'REJECT' | 'DISCARD' | 'INCOMPLETE'
  hit_rule?: string
  summary?: string
  confidence?: number
  needs_review?: boolean
  checks?: QcCheck[]
  failed_checks?: QcCheck[]
  llm_ms?: number
  elapsed_ms?: number
}

export interface DesignRun {
  id: number
  count: number
  status: 'QUEUED' | 'RUNNING' | 'DEDUP' | 'DONE' | 'FAILED' | 'CANCELLED'
  model: string
  note: string
  error: string
  stats: {
    agent_s?: number
    new_files?: string[]
    parsed?: number
    imported?: number
    task_nos?: string[]
    passed?: number
    discarded?: number
    dedup_error?: string
  }
  task_ids: number[]
  log_tail: string
  created_at: string | null
  started_at: string | null
  finished_at: string | null
}

export interface DesignCheck { name: string; ok: boolean; message: string }

export interface Evidence { step?: number; file?: string; quote?: string }
export interface Review {
  scores: Record<string, number | null>
  descs: Record<string, string>
  evidence: Record<string, Evidence[]>
  other_issues: string
  coverage: { point: string; status: string; evidence?: string }[]
  verification?: { commands?: string[]; summary?: string }
}
export interface VerifyItem { dim?: string; level: 'ok' | 'warn' | 'block'; code: string; message: string; words?: string[] }
export interface VerifyReport {
  overall: 'pass' | 'warn' | 'block'
  blocks: number
  warns: number
  evidence_total: number
  evidence_hit: number
  evidence_hit_rate: number | null
  items: VerifyItem[]
}

export interface TaskDetail extends TaskBrief {
  user_prompt: string
  result: any
  verdict: any
  trace_summary: any
  trace_file: string
  git_diff_stat: string
  analysis: any
  review: Review
  verify: VerifyReport | Record<string, never>
  upload: any
  qc: QcResult | Record<string, never>
  dedup: any
}

export interface GateCheck { name: string; level: 'ok' | 'warn' | 'block'; message: string; fix: string }
export interface GateReport { passed: boolean; blocked: number; warnings: number; checks: GateCheck[] }

export interface SettingItem {
  key: string; label: string; group: string; secret: boolean; kind: string; help: string
  default: string; configured: boolean; value: string
}

export interface SystemStatus {
  docker: { ok: boolean; message: string }
  image: { name: string; present: boolean }
  scheduler: { running: number; max_parallel: number; running_ids: number[]; queued: number; paused: boolean }
  pipeline: { running: number[]; max_parallel: number; destroy: boolean; analyze: boolean; qc: boolean }
  qc: { ok: boolean; message: string; image: string }
  design: { running: number[] }
  counts: Record<Status, number>
  totals: { finished: number; uploaded: number; date: string }
  containers: { name: string; status: string; task_no: string }[]
  configured: Record<string, boolean>
  paths: { coder_root_host: string; coder_root_mount: string; prompt_file: string; prompt_exists: boolean }
}

export interface RunEvent { seq: number; kind: string; summary: string; ts: string | null; payload: any }

// ---------- 接口 ----------
export const api = {
  health: () => get<{ ok: boolean }>('/api/health'),
  status: () => get<SystemStatus>('/api/system/status'),
  probe: (target: 'qa' | 'gateway' | 'cursor' | 'docker' | 'qc') => post<{ ok: boolean; message: string }>(`/api/system/probe/${target}`),

  settings: () => get<{ items: SettingItem[] }>('/api/settings'),
  saveSettings: (values: Record<string, string>) => put<{ written: string[]; items: SettingItem[] }>('/api/settings', { values }),
  models: () => get<{ models: string[]; source: string; current: string }>('/api/settings/models'),

  tasks: (params?: { status?: string; exclude_done?: boolean; include_discarded?: boolean }) => {
    const q = new URLSearchParams()
    if (params?.status) q.set('status', params.status)
    if (params?.exclude_done) q.set('exclude_done', 'true')
    if (params?.include_discarded) q.set('include_discarded', 'true')
    return get<{ items: TaskBrief[] }>(`/api/tasks${q.toString() ? '?' + q : ''}`)
  },
  task: (id: number) => get<TaskDetail>(`/api/tasks/${id}`),
  importBank: () => post<{ parsed: number; added: string[]; skipped: number }>('/api/tasks/import'),
  gate: (id: number) => post<GateReport>(`/api/tasks/${id}/gate`),
  claim: (id: number, force = false) => post<{ queued: boolean; gate: GateReport }>(`/api/tasks/${id}/claim${force ? '?force=true' : ''}`),
  release: (id: number) => post<{ ok: boolean }>(`/api/tasks/${id}/release`),
  discard: (id: number) => post<{ ok: boolean; message: string }>(`/api/tasks/${id}/discard`),
  restore: (id: number) => post<{ ok: boolean; status: Status; message: string }>(`/api/tasks/${id}/restore`),
  resetTask: (id: number, keepTraces = true) =>
    post<{ ok: boolean; steps: ResetStep[] }>(`/api/tasks/${id}/reset?keep_traces=${keepTraces}`),
  fix: (id: number, action: string) => post<{ ok: boolean; message: string }>(`/api/tasks/${id}/fix/${action}`),
  stop: (id: number) => post<{ ok: boolean; message: string }>(`/api/tasks/${id}/stop`),
  events: (id: number) => get<{ items: RunEvent[] }>(`/api/tasks/${id}/events/list`),
  traceIndex: (id: number) => get<any>(`/api/tasks/${id}/trace-index`),
  analyze: (id: number) => post<{ ok: boolean; message: string }>(`/api/tasks/${id}/analyze`),
  saveReview: (id: number, body: { scores: Record<string, number | null>; descs: Record<string, string>; other_issues: string; evidence?: any; coverage?: any }) =>
    put<{ verify: VerifyReport; task: TaskBrief }>(`/api/tasks/${id}/review`, body),
  verify: (id: number) => post<VerifyReport>(`/api/tasks/${id}/verify`),
  upload: (id: number) => post<{ ok: boolean; message: string; submission_id?: number }>(`/api/tasks/${id}/upload`),
  batchUpload: (ids: number[]) => post<{ results: any[] }>('/api/tasks/batch/upload', { ids }),
  batchClaim: (ids: number[]) => post<{ results: any[] }>('/api/tasks/batch/claim', { ids }),
  complete: (id: number, force = false) => post<{ ok: boolean; message: string }>(`/api/tasks/${id}/complete${force ? '?force=true' : ''}`),
  destroyContainer: (id: number) => post<{ ok: boolean; message: string }>(`/api/tasks/${id}/destroy-container`),
  traceUrl: (id: number) => `/api/tasks/${id}/trace`,

  // ---- 质检 ----
  qc: (id: number) => post<{ ok: boolean; message: string }>(`/api/tasks/${id}/qc`),
  batchQc: (ids: number[]) => post<{ ok: boolean; started: number }>('/api/tasks/batch/qc', { ids }),
  rerunPipeline: (id: number) => post<{ ok: boolean; message: string }>(`/api/tasks/${id}/pipeline`),

  // ---- 队列 ----
  queue: () => get<{
    items: TaskBrief[]
    scheduler: SystemStatus['scheduler']
    pipeline: { running: number[]; max_parallel: number }
  }>('/api/tasks/queue/list'),
  queueMove: (id: number, direction: 'top' | 'up' | 'down' | 'bottom') =>
    post<{ ok: boolean; priority: number }>(`/api/tasks/${id}/queue/move`, { direction }),
  queuePause: (paused: boolean) => post<{ ok: boolean; paused: boolean; message: string }>(`/api/tasks/queue/pause?paused=${paused}`),
  queueParallel: (value: number) => post<{ ok: boolean; max_parallel: number }>(`/api/tasks/queue/parallel?value=${value}`),

  // ---- 题目设计 ----
  designPreflight: () => get<{ checks: DesignCheck[]; ready: boolean; default_count: number; auto_dedup: boolean }>('/api/design/preflight'),
  designStart: (count: number, note = '') => post<{ ok: boolean; id: number }>('/api/design/start', { count, note }),
  designRuns: () => get<{ items: DesignRun[]; running: number[] }>('/api/design'),
  designRun: (id: number) => get<DesignRun & { tasks: TaskBrief[] }>(`/api/design/${id}`),
  designCancel: (id: number) => post<{ ok: boolean }>(`/api/design/${id}/cancel`),
  designDedup: (ids: number[]) => post<{ ok: boolean; passed: number; discarded: number }>('/api/design/dedup', { ids }),
}
