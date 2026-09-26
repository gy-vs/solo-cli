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
  | 'ANALYZED' | 'QC' | 'READY' | 'UPLOADED' | 'DONE' | 'NEEDS_ATTENTION' | 'DISCARDED'

/** 提交前质检走到哪一档。ERROR 是质检自己没跑成，和 FAIL 不是一回事 */
export type PrecheckStatus = 'IDLE' | 'RUNNING' | 'PASS' | 'FAIL' | 'CONFIRMED' | 'ERROR'

/** 事实核验走到哪一档。取值与措辞质检同形，两者是提交前并列的两道 */
export type FactcheckStatus = PrecheckStatus

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

/** 难度筛选结论。两侧都跑得太轻的题在开 GSB 分析之前就废弃掉，省下那次额度。
 *
 *  四个数的口径和列表行里显示的完全一致：steps 是工具调用步数，minutes 是容器用时。
 *  读不到的留 null，这时 verdict 是 unknown，题照常往下走 —— 「一步没调」和「还不知道」
 *  是两件事。skipped 是筛选被关掉，或者人按过恢复、已经替这道题拍过板了。 */
export interface DifficultyScreen {
  verdict?: 'pass' | 'discard' | 'unknown' | 'skipped'
  reason?: string
  steps?: Partial<Record<Side, number | null>>
  minutes?: Partial<Record<Side, number | null>>
  thresholds?: Record<string, number>
  checked_at?: string
  /** 人工放行过：恢复废弃题时打上，之后不再按阈值筛它 */
  override?: boolean
  override_at?: string
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
  /** 不能提交的原因。两道质检、录屏、状态全在后端判完，空串表示能提交。
   *  按钮灰不灰照这个字段，别在前端另凑一套条件 */
  precheck_block: string
  precheck_at: string
  /** 事实核验：理由里关于执行结果的话和轨迹对不对得上 */
  factcheck_status: FactcheckStatus
  factcheck_mismatches: number
  /** 核验发现不符并自动订正过。改前那一稿在 factcheck.reason_before */
  factcheck_applied: boolean
  /** 订正留痕，一处一句：哪一段哪一句、轨迹里其实是什么、改成了什么 */
  factcheck_notes: string[]
  factcheck_summary: string
  /** 事实核验没放行时给人看的原话，放行了是空串 */
  factcheck_block: string
  /** 看门狗已经自动重跑过几次（上限 2 次，用完才真正留给人） */
  factcheck_auto_retries: number
  factcheck_stale: boolean
  /** 难度筛选：跑完之后按两侧步数与用时判这道题值不值得花一次分析额度 */
  difficulty_screen: DifficultyScreen
  /** 改动面体检：开跑前按题面判这道题要动几个模块。空串表示还没体检过 */
  scope_verdict: '' | 'pass' | 'narrow' | 'unknown' | 'skipped'
  /** 门禁会不会因为改动面太窄拦下它。人工放行过、结论过期的都是 false */
  scope_blocked: boolean
  scope_summary: string
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
  a_delivery?: Delivery
  b_delivery?: Delivery
  evidence: { side?: string; step?: number; file?: string; quote?: string }[]
  remark: string
  validity?: string
}

/** 一侧的交付完整性。评分 1 到 5，老题分析时还没有这对字段 */
export interface Delivery {
  score: number | null
  desc: string
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

/** 批量质检时被剔掉的题。剔除发生在发出去之前，所以这些题一次模型调用都没花 */
export interface PrecheckSkip {
  id: number
  task_no: string
  message: string
}

/** 后台批量质检的进度。running 为假时其余字段是上一批跑完留下的账 */
export interface PrecheckJob {
  running: boolean
  total: number
  done: number
  passed: number
  revise: number
  failed: number
  /** 手上正在跑的那道题号 */
  current: string
  started_at: string
  finished_at: string
  /** 已经叫停，跑完手上这道就收工 */
  stopping: boolean
}

/** 提交前质检报告 */
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
  delivery?: DeliveryQc
}

/** 两道质检里交付完整性那一段的结论。事实核验按 problems 报，措辞质检按 issues 报 */
export interface DeliveryQcSide {
  status: 'ok' | 'fixed' | 'fail'
  score?: number | null
  problems?: { quote: string; type?: string; claim?: string; fact?: string }[]
  issues?: PrecheckIssue[]
  local_defects?: string[]
  notes?: string[]
  rewrite_dropped?: string
  desc_before?: string
  desc_after?: string
}
export interface DeliveryQc {
  status: 'ok' | 'fixed' | 'fail'
  sides: Partial<Record<Side, DeliveryQcSide>>
  notes?: string[]
  model?: string
}

/** 事实核验报告。一处不符记四样：原文、轨迹里其实是什么、改成了什么、归哪一侧 */
export interface FactMismatch {
  quote: string
  side?: Side | ''
  claim?: string
  fact?: string
  fix?: string
}

export interface FactcheckReport {
  mismatches?: FactMismatch[]
  /** 订正留痕，一处一句，直接可读 */
  notes?: string[]
  summary?: string
  applied?: boolean
  applied_at?: string
  /** 订正之前那一稿。自动改写不留这一份就成了不可追溯的覆盖 */
  reason_before?: string
  chars_before?: number
  /** 本地那把确定性的尺子先摘出来的可疑断言，模型未必都认 */
  local_suspects?: { quote: string; side: string; why: string }[]
  /** 改写稿没被采用的原因。非空说明这次只报了问题没能自动订正 */
  rewrite_dropped?: string
  model?: string
  rounds?: number
  duration_s?: number
  finished_at?: string
  confirmed_at?: string
  confirmed_from?: string
  confirmed_note?: string
  /** 措辞质检改写之后，事实结论过继到新一稿的时间 */
  resealed_at?: string
  error?: string
  delivery?: DeliveryQc
}

export interface TaskDetail extends TaskBrief {
  user_prompt: string
  gsb: Gsb | Record<string, never>
  analysis: any
  verify: VerifyReport | Record<string, never>
  precheck: PrecheckReport | Record<string, never>
  factcheck: FactcheckReport | Record<string, never>
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
  /** 探路把它降到了队尾：这道题的另一侧还没出结论，先让别的题的首侧走。
   *  不是被拦住，队列排空了它照样出闸 */
  deferred: boolean
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
  rec?: { enabled: boolean; recorder_only: boolean }
  /** 后台批量质检的进度。整批要跑几个小时，进度搭状态接口这趟车 */
  precheck: PrecheckJob
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
  fix: (id: number, action: 'clone_sides' | 'reset_sides' | 'archive_traces' | 'remove_containers'
    | 'scope_check' | 'scope_override') =>
    post<{ ok: boolean; message: string }>(`/api/tasks/${id}/fix/${action}`),
  /** ids 给空数组就是「把所有还没体检过改动面的待领题都跑一遍」 */
  batchScope: (ids: number[]) =>
    post<{ ok: boolean; checked: number; cached: number; narrow: number; message: string }>(
      '/api/tasks/batch/scope', { ids }),

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
  saveGsb: (id: number, body: { verdict?: string; reason: string; a_startup?: Startup; b_startup?: Startup;
    a_delivery?: Delivery; b_delivery?: Delivery; validity?: string; remark?: string }) =>
    put<{ verify: VerifyReport; task: TaskBrief }>(`/api/tasks/${id}/gsb`, body),
  backfillDelivery: (id: number) =>
    post<{ ok: boolean; message?: string; task: TaskBrief }>(`/api/tasks/${id}/delivery`),
  verify: (id: number) => post<VerifyReport>(`/api/tasks/${id}/verify`),

  // ---- 录屏 ----
  saveScreencast: (id: number, body: Partial<Record<Side, string>>) =>
    put<{ verify: VerifyReport; task: TaskBrief }>(`/api/tasks/${id}/screencast`, body),
  uploadScreencast: (id: number, side: Side, path: string) =>
    post<{ ok: boolean; url: string; path: string; message: string }>(`/api/tasks/${id}/screencast/upload?side=${side}&path=${encodeURIComponent(path)}`),
  /** 交付录屏：给两侧的本地文件路径，后端收进题目目录、代传、顺手提交。
   *  submit 传 false 就只收下不提交。这是整条流水线上最后一个人工动作。 */
  deliverScreencast: (id: number, body: { A?: string; B?: string; submit?: boolean }) =>
    post<{ ok: boolean; message: string; submitted: { ok: boolean; message: string } | null; task: TaskBrief }>(
      `/api/tasks/${id}/screencast/deliver`, body),

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

  // ---- 提交前质检：事实核验（说得对不对）与措辞质检（说得像不像人话）两道 ----
  /** 事实核验单道。拿轨迹里的执行记录去对理由，不符的地方后端直接订正并留痕，
   *  订正明细在返回的 notes 里，也落进 task.factcheck.notes */
  factcheck: (id: number) =>
    post<{ ok: boolean; passed: boolean; applied: boolean; mismatches: number
      notes: string[]; summary: string; message: string }>(`/api/tasks/${id}/factcheck`),
  confirmFactcheck: (id: number, note = '') =>
    post<{ ok: boolean; message: string; task: TaskBrief }>(
      `/api/tasks/${id}/factcheck/confirm`, { note }),
  batchFactcheck: (ids: number[]) =>
    post<{ results: BatchResult[] }>('/api/tasks/batch/factcheck', { ids }),
  /** 整条闸门走一遍：事实核验 → 措辞质检 → 本地核验 → 平台质检。
   *  顺序和巡检自动跑的完全一致，不另起一套 */
  qualityGate: (id: number) => post<any>(`/api/tasks/${id}/quality-gate`),
  startBatchQualityGate: (ids: number[]) =>
    post<{ results: BatchResult[] }>('/api/tasks/batch/quality-gate', { ids }),

  /** 措辞质检单道，跑完才回（一道一分半，按钮转着圈等）。状态不对时后端回 409 */
  precheck: (id: number) =>
    post<{ ok: boolean; passed: boolean; issues: number; summary: string; message: string }>(
      `/api/tasks/${id}/precheck`),
  /** 整批，立刻返回。一百多道要跑几个小时，浏览器挂不住这么长的连接，所以后端起后台
   *  任务：每道题跑完发 SSE 刷新那一行，整批进度看 status().precheck。
   *  skipped 是被剔掉的题（已有有效结论、正在跑、没有理由正文），要原样说给人听。 */
  startBatchPrecheck: (ids: number[]) =>
    post<{ ok: boolean; started: number; message: string; skipped: PrecheckSkip[] }>(
      '/api/tasks/batch/precheck/start', { ids }),
  stopBatchPrecheck: () => post<{ ok: boolean; message: string }>('/api/tasks/batch/precheck/stop'),
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

  // ---- 录屏录制处理 ----
  rec: () => get<RecOverview>('/api/rec'),
  recSync: () => post<{ ok: boolean; message?: string; stats?: Record<string, any> }>('/api/rec/sync'),
  recGenerate: (taskId: number) => post<{ ok: boolean; message: string }>(`/api/rec/tasks/${taskId}/generate`),
  recBatchGenerate: (ids: number[]) => post<{ results: RecBatchResult[] }>('/api/rec/batch/generate', { ids }),
  recBatchWithdraw: (ids: number[]) => post<{ results: RecBatchResult[] }>('/api/rec/batch/withdraw', { ids }),
  recBatchClaim: (keys: string[]) => post<{ results: RecBatchResult[] }>('/api/rec/batch/claim', { keys }),
  recBatchRelease: (keys: string[]) => post<{ results: RecBatchResult[] }>('/api/rec/batch/release', { keys }),
  recWithdraw: (taskId: number) => post<{ ok: boolean; message: string }>(`/api/rec/tasks/${taskId}/withdraw`),
  recLocalReport: async (taskId: number) => {
    const res = await fetch(`/api/rec/tasks/${taskId}/report`)
    const text = await res.text()
    if (!res.ok) {
      let detail: any = text
      try { detail = JSON.parse(text)?.detail ?? text } catch { /* 纯文本 */ }
      throw new ApiError(res.status, detail)
    }
    return text
  },
  recClaim: (key: string) => post<RecReport>('/api/rec/claim', { key }),
  recReport: (key: string) => get<RecReport>(`/api/rec/report?key=${encodeURIComponent(key)}`),
  recRelease: (key: string) => post<{ ok: boolean; message: string }>('/api/rec/release', { key }),
  recVideos: async (key: string, files: { A?: File | null; B?: File | null }, paths: { A?: string; B?: string } = {}) => {
    const form = new FormData()
    form.append('key', key)
    if (files.A) form.append('a', files.A)
    if (files.B) form.append('b', files.B)
    if (paths.A) form.append('a_path', paths.A)
    if (paths.B) form.append('b_path', paths.B)
    const res = await fetch('/api/rec/videos', { method: 'POST', body: form })
    const text = await res.text()
    let body: any = null
    try { body = text ? JSON.parse(text) : null } catch { body = text }
    if (!res.ok) throw new ApiError(res.status, body?.detail ?? body)
    return body as { ok: boolean; message: string }
  },
}

// ---------- 录屏协作 ----------
/** 录屏仓库里一道题此刻的状态（按事件流折叠出来） */
export type RecEntryState = 'open' | 'claimed' | 'recorded' | 'collected' | 'withdrawn'

export interface RecEntry {
  key: string
  owner: string
  task_no: string
  state: RecEntryState
  digest: string
  title: string
  kind_label: string
  verdict: string
  repo_url: string
  branch: string
  published_at: string
  claimed_by: string
  claimed_at: string
  recorded_by: string
  recorded_at: string
  collected_at: string
}

export interface RecQueueItem extends RecEntry {
  mine: boolean
  claimed_by_me: boolean
  recorded_by_me: boolean
}

/** 本机题目的录屏进度（题上的 recording 字段） */
export interface RecLocal {
  id: number
  task_no: string
  status: Status
  question_type: string
  difficulty: string
  verdict: string
  recording: {
    state?: 'generating' | 'failed' | 'published' | 'collected' | 'withdrawn'
    stage?: string
    note?: string
    error?: string
    fails?: number
    rounds?: number
    model?: string
    kind_label?: string
    started_at?: string
    published_at?: string
    collected_at?: string
    collect_error?: string
    recorded_by?: string
    wanted?: boolean
  }
  generating: boolean
  collecting: boolean
  screencast: Record<string, string>
  submit_block: string
  entry: RecEntry | null
  need: string
}

export interface RecOverview {
  available: boolean
  message: string
  device: string
  role: 'producer' | 'recorder'
  repo: string
  auto_generate: boolean
  max_parallel: number
  generating: number
  skill_missing: string[]
  last_scan: { at?: string; error?: string; generated?: number; collected?: number; withdrawn?: number }
  local: RecLocal[]
  queue: RecQueueItem[]
}

export interface RecBatchResult {
  id?: number
  key?: string | number
  task_no?: string
  ok: boolean
  message: string
}

export interface RecReport {
  ok: boolean
  entry: RecEntry
  markdown: string
}
