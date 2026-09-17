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
/** 题级状态：只描述这道题走到哪一步，单侧容器跑得怎样看 TaskRun.status */
export type Status =
  | 'AVAILABLE' | 'CLAIMED' | 'QUEUED' | 'RUNNING' | 'RUN_DONE' | 'ANALYZING'
  | 'ANALYZED' | 'UPLOADED' | 'DONE' | 'NEEDS_ATTENTION' | 'DISCARDED'

/** 单侧运行状态。取值与题级有同名的，比较时别混用 */
export type RunStatus = 'PENDING' | 'QUEUED' | 'RUNNING' | 'FINISHED' | 'FAILED' | 'TIMEOUT' | 'INTERRUPTED'

export type Side = 'A' | 'B'
export const SIDES: Side[] = ['A', 'B']

/** GSB 结论。库里存短值，上传时才换成平台的中文标签 */
export type Verdict = 'A' | 'B' | 'Same'

export interface TaskRunBrief {
  id: number
  side: Side
  status: RunStatus
  /** 第几次跑。重跑加一，超过上限就转人工 */
  attempt: number
  container_name: string
  container_exists: boolean
  image_tag: string
  exit_code: number | null
  session_id: string
  turn_id: string
  trace_file: string
  artifact_sha: string
  artifact_url: string
  protocol: { subtype?: string; num_turns?: number; duration_ms?: number; cost_usd?: number; usage?: any; thinking_tokens?: number | null }
  artifact: { trace_found?: boolean; trace_count?: number; tool_calls?: number; tool_errors?: number; human_turns?: number; changed_files?: number }
  /** 网关 5xx / 429。按平台规则不作为 GSB 判断依据，只触发重跑 */
  gateway_errors: string[]
  notes: string[]
  abnormal: { reason?: string; at?: string; attempt?: number; gave_up?: boolean }
  error: string
  started_at: string | null
  finished_at: string | null
}

export interface TaskRunDetail extends TaskRunBrief {
  result: any
  verdict: any
  trace_summary: any
  git_diff_stat: string
}

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
  repo_url: string
  repo_slug: string
  branch_check: { ok?: boolean; message?: string; at?: string }
  prompt_preview: string
  prompt_chars: number
  meta: Record<string, string>
  gsb_verdict: Verdict | ''
  gsb_reason_chars: number
  screencast: Partial<Record<Side, string>>
  verify_overall: 'ok' | 'warn' | 'block' | null
  verify_blocked: number
  upload_ok: boolean | null
  submission_id: number | null
  priority: number
  origin: 'bank' | 'designed'
  design_run_id: number
  auto_stage: string
  auto_error: string
  dedup_verdict: '' | 'pass' | 'discard' | 'unknown'
  dedup_reason: string
  created_at: string | null
  claimed_at: string | null
  finished_at: string | null
  uploaded_at: string | null
  done_at: string | null
  discarded_at: string | null
  discarded_from: string
  runs: TaskRunBrief[]
}

/** GSB 对比结论。分析产出，每一项都可人工改 */
export interface Gsb {
  verdict: Verdict | ''
  reason: string
  a_findings: { good: string[]; bad: string[] }
  b_findings: { good: string[]; bad: string[] }
  a_startup: Startup
  b_startup: Startup
  evidence: { side?: string; step?: number; file?: string; quote?: string }[]
  remark: string
  validity?: string
}

/** 启动说明。录屏要照着这个把项目跑起来 */
export interface Startup {
  steps: string[]
  commands: string[]
  note: string
}

export interface VerifyItem { name: string; level: 'ok' | 'warn' | 'block'; message: string }
export interface VerifyReport {
  overall: 'ok' | 'warn' | 'block'
  blocked: number
  warnings: number
  items: VerifyItem[]
}

export interface TaskDetail extends TaskBrief {
  user_prompt: string
  gsb: Gsb | Record<string, never>
  analysis: any
  verify: VerifyReport | Record<string, never>
  upload: any
  dedup: any
  runs: TaskRunDetail[]
}

export interface GateCheck { name: string; level: 'ok' | 'warn' | 'block'; message: string; fix: string }
export interface GateReport { passed: boolean; blocked: number; warnings: number; checks: GateCheck[] }

/** 领题时先 clone 两侧，分支不合规就不往下走 */
export interface PrepareResult {
  ok: boolean
  message: string
  sides: Partial<Record<Side, { ok: boolean; reused: boolean; message: string }>>
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

export interface SettingItem {
  key: string; label: string; group: string; secret: boolean; kind: string; help: string
  default: string; configured: boolean; value: string
}

export interface SystemStatus {
  docker: { ok: boolean; message: string }
  image: { name: string; present: boolean }
  /** 额度单位是容器：一道题占两个 */
  scheduler: { running: number; max_parallel: number; running_ids: number[]; queued: number; paused: boolean }
  watchdog: { interval_seconds: number; max_retries: number }
  dedup: { ok: boolean; message: string; image: string }
  design: { running: number[] }
  counts: Record<Status, number>
  running_sides: number
  totals: { finished: number; uploaded: number; date: string }
  containers: { name: string; status: string; task_no: string }[]
  configured: Record<string, boolean>
  paths: { coder_root_host: string; coder_root_mount: string; prompt_file: string; prompt_exists: boolean }
}

export interface RunEvent { seq: number; side?: Side; kind: string; summary: string; ts: string | null; payload: any }

// ---------- 接口 ----------
export const api = {
  health: () => get<{ ok: boolean }>('/api/health'),
  status: () => get<SystemStatus>('/api/system/status'),
  probe: (target: 'gsb' | 'gateway' | 'cursor' | 'docker' | 'dedup') =>
    post<{ ok: boolean; message: string }>(`/api/system/probe/${target}`),

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

  // ---- 领取与门禁 ----
  gate: (id: number) => post<GateReport>(`/api/tasks/${id}/gate`),
  claim: (id: number, force = false) =>
    post<{ queued: boolean; prepare: PrepareResult; gate: GateReport | null }>(`/api/tasks/${id}/claim${force ? '?force=true' : ''}`),
  release: (id: number) => post<{ ok: boolean }>(`/api/tasks/${id}/release`),
  discard: (id: number) => post<{ ok: boolean; message: string }>(`/api/tasks/${id}/discard`),
  restore: (id: number) => post<{ ok: boolean; status: Status; message: string }>(`/api/tasks/${id}/restore`),
  fix: (id: number, action: 'clone_sides' | 'reset_sides' | 'archive_traces' | 'remove_containers') =>
    post<{ ok: boolean; message: string }>(`/api/tasks/${id}/fix/${action}`),

  // ---- 运行 ----
  /** 不给 side 就把两侧都停了 */
  stop: (id: number, side?: Side) => post<{ ok: boolean; message: string }>(`/api/tasks/${id}/stop${side ? '?side=' + side : ''}`),
  /** 人工重跑。留空 sides 表示两侧都重跑；不看次数上限并把计数清零 */
  rerun: (id: number, sides: Side[] = []) =>
    post<{ ok: boolean; message: string }>(`/api/tasks/${id}/rerun`, { sides }),
  events: (id: number, side?: Side) =>
    get<{ items: RunEvent[]; total: number; truncated: boolean }>(`/api/tasks/${id}/events/list${side ? '?side=' + side : ''}`),
  traceIndex: (id: number, side: Side) => get<any>(`/api/tasks/${id}/trace-index?side=${side}`),
  traceUrl: (id: number, side: Side) => `/api/tasks/${id}/trace?side=${side}`,

  // ---- GSB 分析与结论 ----
  analyze: (id: number) => post<{ ok: boolean; message: string }>(`/api/tasks/${id}/analyze`),
  /** 手动走一遍推产物加开分析，给推送失败后重试用 */
  advance: (id: number) => post<{ ok: boolean; message?: string; error?: string }>(`/api/tasks/${id}/advance`),
  saveGsb: (id: number, body: { verdict?: string; reason: string; a_startup?: Startup; b_startup?: Startup; validity?: string; remark?: string }) =>
    put<{ verify: VerifyReport; task: TaskBrief }>(`/api/tasks/${id}/gsb`, body),
  verify: (id: number) => post<VerifyReport>(`/api/tasks/${id}/verify`),

  // ---- 录屏 ----
  saveScreencast: (id: number, body: Partial<Record<Side, string>>) =>
    put<{ verify: VerifyReport; task: TaskBrief }>(`/api/tasks/${id}/screencast`, body),
  uploadScreencast: (id: number, side: Side, path: string) =>
    post<{ ok: boolean; url: string; message: string }>(`/api/tasks/${id}/screencast/upload?side=${side}&path=${encodeURIComponent(path)}`),

  // ---- 上传与收尾 ----
  upload: (id: number) => post<{ ok: boolean; message: string; submission_id?: number }>(`/api/tasks/${id}/upload`),
  batchUpload: (ids: number[]) => post<{ results: any[] }>('/api/tasks/batch/upload', { ids }),
  batchClaim: (ids: number[]) => post<{ results: any[] }>('/api/tasks/batch/claim', { ids }),
  complete: (id: number, force = false) => post<{ ok: boolean; message: string }>(`/api/tasks/${id}/complete${force ? '?force=true' : ''}`),
  destroyContainer: (id: number) => post<{ ok: boolean; message: string }>(`/api/tasks/${id}/destroy-container`),

  // ---- 队列 ----
  queue: () => get<{ items: TaskBrief[]; scheduler: SystemStatus['scheduler'] }>('/api/tasks/queue/list'),
  queueMove: (id: number, direction: 'top' | 'up' | 'down' | 'bottom') =>
    post<{ ok: boolean; priority: number }>(`/api/tasks/${id}/queue/move`, { direction }),
  queuePause: (paused: boolean) => post<{ ok: boolean; paused: boolean; message: string }>(`/api/tasks/queue/pause?paused=${paused}`),
  queueParallel: (value: number) => post<{ ok: boolean; max_parallel: number; message: string }>(`/api/tasks/queue/parallel?value=${value}`),

  // ---- 题目设计 ----
  designPreflight: () => get<{ checks: DesignCheck[]; ready: boolean; default_count: number; auto_dedup: boolean }>('/api/design/preflight'),
  designStart: (count: number, note = '') => post<{ ok: boolean; id: number }>('/api/design/start', { count, note }),
  designRuns: () => get<{ items: DesignRun[]; running: number[] }>('/api/design'),
  designRun: (id: number) => get<DesignRun & { tasks: TaskBrief[] }>(`/api/design/${id}`),
  designCancel: (id: number) => post<{ ok: boolean }>(`/api/design/${id}/cancel`),
  designDedup: (ids: number[]) => post<{ ok: boolean; passed: number; discarded: number }>('/api/design/dedup', { ids }),
}
