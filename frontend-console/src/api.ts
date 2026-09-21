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
  | 'ANALYZED' | 'QC' | 'UPLOADED' | 'DONE' | 'NEEDS_ATTENTION' | 'DISCARDED'

/** 提交前质检走到哪一档。ERROR 是质检自己没跑成，和 FAIL 不是一回事 */
export type PrecheckStatus = 'IDLE' | 'RUNNING' | 'PASS' | 'FAIL' | 'CONFIRMED' | 'ERROR'

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
  /** 第几次跑。重跑加一，用尽后整道题自动废弃 */
  attempt: number
  /** 其中超时了几次。上限比普通重跑低，先撞到哪个算哪个 */
  timeouts: number
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
  /** held 是「判了异常但异常处理被暂停」，只记一笔，没有重跑也没有废弃 */
  abnormal: { reason?: string; at?: string; attempt?: number; gave_up?: boolean; held?: boolean }
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
  precheck_status: PrecheckStatus
  precheck_issues: number
  precheck_summary: string
  /** 质检之后理由又改过，这份结论不再代表现在这一稿 */
  precheck_stale: boolean
  /** 不能提交的原因。空串表示能提交，按钮灰不灰照这个字段，别在前端另凑一套条件 */
  precheck_block: string
  precheck_at: string
  upload_ok: boolean | null
  submission_id: number | null
  priority: number
  /** pool 是从远端题库同步来的，可能出自别的设备 */
  origin: 'bank' | 'designed' | 'pool'
  /** 出这道题的设备标识。与本机不同就是别的设备出的，题号带设备后缀 */
  pool_device: string
  /** 远端登记的领取者。非空且不是本机，说明这道题已经被别人领走 */
  claimed_by: string
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

/** 质检挑出的一处机械化表达。quote 一定是理由正文里的原文，能拿去对位置 */
export interface PrecheckIssue {
  quote: string
  kind: string
  why: string
  suggest: string
}

/** 提交前质检报告。发起只能在对话里（见后端 app/cli.py），界面只读它 */
export interface PrecheckReport {
  passed?: boolean
  summary?: string
  issues?: PrecheckIssue[]
  /** 整段改写稿。缩水太多或引入核验红项的稿子后端已经丢掉，这里拿到的都是可用的 */
  rewrite?: string
  rewrite_dropped?: string
  model?: string
  duration_s?: number
  finished_at?: string
  confirmed_at?: string
  confirmed_from?: string
  confirmed_note?: string
  error?: string
}

export interface TaskDetail extends TaskBrief {
  user_prompt: string
  gsb: Gsb | Record<string, never>
  analysis: any
  verify: VerifyReport | Record<string, never>
  precheck: PrecheckReport | Record<string, never>
  upload: any
  dedup: any
  runs: TaskRunDetail[]
}

/** 批量动作里一道题的结果。逐题带原因回来，界面要按原因分类报数 */
export interface BatchResult {
  id: number
  ok?: boolean
  message?: string
  /** 批量分析专用：假表示排在队列里等分析并发额度，不是失败 */
  started?: boolean
}

export interface GateCheck { name: string; level: 'ok' | 'warn' | 'block'; message: string; fix: string; hard: boolean }
/** hard_blocked 里的项强制启动也绕不过去，得先修好 */
export interface GateReport {
  passed: boolean
  blocked: number
  hard_blocked: string[]
  hard_messages: string[]
  warnings: number
  checks: GateCheck[]
}

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

/** 排队中的一个容器。队列的单位是容器不是题，A 与 B 各排各的 */
export interface QueueItem {
  run_id: number; task_id: number; task_no: string; side: Side
  attempt: number
  /** 被看护退回来重跑的，跟第一次排队的区分开 */
  requeued: boolean
}

export interface RunningItem {
  run_id: number; task_no: string; side: Side; attempt: number; minutes: number
}

export interface SystemStatus {
  docker: { ok: boolean; message: string }
  image: { name: string; present: boolean }
  /** 额度与排队的单位都是容器：一个空槽放一个容器 */
  scheduler: {
    running: number; max_parallel: number; free: number; running_ids: number[]
    running_runs: RunningItem[]
    /** 在等的容器数；queued_tasks 才是题数 */
    queued: number; queued_tasks: number; queue: QueueItem[]
    paused: boolean
    /** 调度循环的近况。alive 为假说明它停了，界面要喊出来 */
    alive: boolean; last_tick_at: string | null; last_error: string
  }
  watchdog: {
    interval_seconds: number; max_retries: number; max_timeouts: number
    /** 开着就是只记异常不动手：不自动重跑、不自动废弃。模型停机时用 */
    paused: boolean
    alive: boolean; last_tick_at: string | null; last_error: string
    last_stats: {
      adopted?: number; requeued?: number; discarded?: number; held?: number
      run_done?: number; settled?: number; advanced?: number
    }
  }
  dedup: { ok: boolean; message: string; image: string }
  /** 远端题库。enabled 为假就是单设备模式，题目来自本机题面文件 */
  pool: {
    enabled: boolean; ok: boolean; message: string
    repo: string; device: string
    total: number; mine: number
    /** 领取是跨设备口径：unclaimed 才是这台机器还能领的 */
    claimed: number; claimed_by_me: number; claimed_by_others: number; unclaimed: number
    /** 缺题面全文、暂时领不了的老条目数 */
    draftless: number
  }
  design: { running: number[] }
  counts: Record<Status, number>
  running_sides: number
  totals: { finished: number; uploaded: number; date: string }
  containers: { name: string; status: string; task_no: string }[]
  configured: Record<string, boolean>
  paths: { coder_root_host: string; coder_root_mount: string; prompt_file: string; prompt_exists: boolean }
}

/** 宿主机代理的近况。不可达时 reachable 为假，界面把按钮按灰并教人怎么起它 */
export interface HostHealth {
  ok: boolean
  reachable: boolean
  message?: string
  version?: string
  coder_root?: string
  ffmpeg?: boolean
  /** index 是 avfoundation 的设备号，和「Capture screen 0」里的编号不是一回事，别自己算 */
  screens: { index: number; label: string }[]
  height?: number
  recordings: { id: string; task_no: string; side: Side; file: string; seconds: number; alive: boolean }[]
}

export interface HostStart {
  ok: boolean
  tty: string
  cwd: string
  /** 代理替你跑掉的装依赖命令 */
  auto: string[]
  /** 留在终端历史里等你按 ↑ 调出来的命令 */
  manual: string[]
  message: string
  note: string
  steps: string[]
}

/** 这一侧是个什么项目、录屏该怎么录。认不出形态时 kind 是 unknown，不瞎猜 */
export interface RecordPlan {
  kind: 'fullstack' | 'frontend' | 'backend' | 'headless' | 'unknown'
  kind_label: string
  stack: string[]
  /** 判成这个形态的依据，人要能复核 */
  evidence: string[]
  serve: string
  test: string
  install: string
  port: number | null
  root: string
  steps: { title: string; why: string; cmds: string[] }[]
  /** GSB 启动命令里除去装依赖的那些，无界面项目全靠它们撑起内容 */
  demo_commands: string[]
  note: string
}

export interface HostProjectStatus {
  ok: boolean
  reachable?: boolean
  running: boolean
  tty?: string
  cwd?: string
  ports: number[]
  urls?: string[]
}

export interface RunEvent { seq: number; side?: Side; kind: string; summary: string; ts: string | null; payload: any }

/** 一侧容器此刻的样子。全部现问 docker，跟收尾时记下的那份账无关 */
export interface ContainerLive {
  side: Side
  name: string
  run_status: RunStatus | ''
  exists: boolean
  status: string
  running: boolean
  exit_code: number | null
  started_at: string | null
  finished_at: string | null
  oom_killed: boolean
  error: string
  image: string
  cpu: string
  mem: string
  mem_perc: string
  processes: { pid: string; time: string; cmd: string }[]
  /** 容器里那个 claude 进程还在不在。事件流不动时，只有它能说明模型是否还在干活 */
  claude_alive: boolean
  last_log_at: string | null
  /** 离最后一行日志过了多久。判「还在动」还是「卡住了」就看这个数 */
  silent_seconds: number | null
  last_log: string
}

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
  /** 拉远端题库。池没启用时后端会自动退回本地题面文件的导入 */
  syncBank: () => post<{ ok: boolean; message: string; added?: string[]; removed?: string[]; skipped?: string[] }>('/api/tasks/sync'),

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

  // ---- 容器实时 ----
  containers: (id: number) => get<{ items: ContainerLive[]; at: string }>(`/api/tasks/${id}/containers`),
  /** 容器原始 stdout 的实时流，给终端面板用（EventSource 直连） */
  containerLogUrl: (id: number, side: Side, tail = 300) =>
    `/api/tasks/${id}/container/logs?side=${side}&tail=${tail}`,

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

  // ---- 宿主机动作（启动项目、录屏）----
  /** 这两件事后端在容器里干不了，统一转给宿主机上的 host-agent */
  hostHealth: () => get<HostHealth>('/api/host/health'),
  /** 项目形态与录制步骤。后端自己看挂载目录，不经过宿主机代理，代理没起也能看 */
  hostPlan: (id: number, side: Side) => get<RecordPlan>(`/api/host/tasks/${id}/plan?side=${side}`),
  hostStart: (id: number, side: Side) => post<HostStart>(`/api/host/tasks/${id}/start?side=${side}`),
  hostStatus: (id: number, side: Side) => get<HostProjectStatus>(`/api/host/tasks/${id}/status?side=${side}`),
  hostRecordStart: (id: number, side: Side, screen: number) =>
    post<{ ok: boolean; id: string; file: string; message: string }>(`/api/host/tasks/${id}/record/start?side=${side}&screen=${screen}`),
  /** 停录返回的 file 是后端可见路径，直接能喂给 uploadScreencast */
  hostRecordStop: (id: number, side: Side) =>
    post<{ ok: boolean; file: string; host_file: string; size: number; seconds: number; message: string }>(`/api/host/tasks/${id}/record/stop?side=${side}`),

  // ---- 提交前质检 ----
  /** 这里只有「人工确认放行」。发起质检故意没有封装：它只能由对话里的
   *  `docker compose exec backend python -m app.cli precheck` 发起，nginx 也把那两条
   *  路由挡在外面。为什么这么关，见 backend/app/services/gsb_precheck.py 的说明。 */
  confirmPrecheck: (id: number, note = '') =>
    post<{ ok: boolean; message: string; submittable: boolean; task: TaskBrief }>(
      `/api/tasks/${id}/precheck/confirm`, { note }),

  // ---- 上传与收尾 ----
  upload: (id: number) => post<{ ok: boolean; message: string; submission_id?: number }>(`/api/tasks/${id}/upload`),
  batchUpload: (ids: number[]) => post<{ results: BatchResult[] }>('/api/tasks/batch/upload', { ids }),
  batchClaim: (ids: number[]) => post<{ results: any[] }>('/api/tasks/batch/claim', { ids }),
  /** 批量重跑。sides 留空表示每道题两侧都重跑 */
  batchRerun: (ids: number[], sides: Side[] = []) =>
    post<{ results: BatchResult[] }>('/api/tasks/batch/rerun', { ids, sides }),
  /** 提交产物并分析。单题也走批量口：那一步要推 git 再调两轮模型，十几二十分钟，
   *  只能排进后台队列，同步等的话请求先超时而动作还在后台跑，界面上看到的是一个假失败。
   *  started 为假不是失败，是在队列里等分析并发额度，照原话说给人听。 */
  queueAnalysis: (ids: number[]) => post<{ results: BatchResult[] }>('/api/tasks/batch/advance', { ids }),
  complete: (id: number, force = false) => post<{ ok: boolean; message: string }>(`/api/tasks/${id}/complete${force ? '?force=true' : ''}`),
  destroyContainer: (id: number) => post<{ ok: boolean; message: string }>(`/api/tasks/${id}/destroy-container`),

  // ---- 队列 ----
  queue: () => get<{ items: TaskBrief[]; scheduler: SystemStatus['scheduler'] }>('/api/tasks/queue/list'),
  queueMove: (id: number, direction: 'top' | 'up' | 'down' | 'bottom') =>
    post<{ ok: boolean; priority: number }>(`/api/tasks/${id}/queue/move`, { direction }),
  queuePause: (paused: boolean) => post<{ ok: boolean; paused: boolean; message: string }>(`/api/tasks/queue/pause?paused=${paused}`),
  watchdogPause: (paused: boolean) => post<{ ok: boolean; paused: boolean; message: string }>(`/api/tasks/watchdog/pause?paused=${paused}`),
  queueParallel: (value: number) => post<{ ok: boolean; max_parallel: number; message: string }>(`/api/tasks/queue/parallel?value=${value}`),

  // ---- 题目设计 ----
  designPreflight: () => get<{ checks: DesignCheck[]; ready: boolean; default_count: number; auto_dedup: boolean }>('/api/design/preflight'),
  designStart: (count: number, note = '') => post<{ ok: boolean; id: number }>('/api/design/start', { count, note }),
  designRuns: () => get<{ items: DesignRun[]; running: number[] }>('/api/design'),
  designRun: (id: number) => get<DesignRun & { tasks: TaskBrief[] }>(`/api/design/${id}`),
  designCancel: (id: number) => post<{ ok: boolean }>(`/api/design/${id}/cancel`),
  designDedup: (ids: number[]) => post<{ ok: boolean; passed: number; discarded: number }>('/api/design/dedup', { ids }),
}
