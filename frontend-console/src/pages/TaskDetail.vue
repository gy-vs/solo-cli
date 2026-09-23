<script setup lang="ts">
import { NButton, NTag, useDialog, useMessage } from 'naive-ui'
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, SIDES, type GateReport, type Gsb, type Side, type TaskDetail, type TaskRunDetail, type VerifyReport } from '../api'
import ContainerLive from '../components/ContainerLive.vue'
import ContainerTerminal from '../components/ContainerTerminal.vue'
import FactcheckPanel from '../components/FactcheckPanel.vue'
import GateChecks from '../components/GateChecks.vue'
import GsbEditor from '../components/GsbEditor.vue'
import PrecheckPanel from '../components/PrecheckPanel.vue'
import PrecheckPill from '../components/PrecheckPill.vue'
import ScreencastPanel from '../components/ScreencastPanel.vue'
import SideStrip from '../components/SideStrip.vue'
import StatusPill from '../components/StatusPill.vue'
import Timeline from '../components/Timeline.vue'
import VerifyBar from '../components/VerifyBar.vue'
import { useGlobalEvents, useRunEvents } from '../sse'
import { fmtDuration, fmtMs, fmtTime, HEX, RUN_END, RUN_LABEL, SIDE_HEX, VERDICT_LABEL } from '../status'
import { nowMs, refreshTasks, store } from '../store'

const route = useRoute()
const router = useRouter()
const msg = useMessage()
const dialog = useDialog()
const id = Number(route.params.id)

type Tab = 'runs' | 'gsb' | 'screencast' | 'precheck' | 'upload' | 'steps' | 'prompt'
const task = ref<TaskDetail | null>(null)
const loading = ref(true)
const tab = ref<Tab>('prompt')
const tabPinned = ref(false)   // 手动切过 tab 后不再自动跳转
const gsb = ref<Gsb>(emptyGsb())
const dirty = ref(false)
const verifyReport = ref<VerifyReport | null>(null)
/** 轨迹索引按侧各存一份 */
const traceIndex = ref<Partial<Record<Side, any>>>({})
const highlightStep = ref<number | null>(null)
/** 事件流和轨迹步骤都只看一侧，省得两列挤在一起 */
const viewSide = ref<Side>('A')

function emptyGsb(): Gsb {
  const startup = { steps: [], commands: [], note: '' }
  return {
    verdict: '', reason: '', a_findings: { good: [], bad: [] }, b_findings: { good: [], bad: [] },
    a_startup: { ...startup }, b_startup: { ...startup }, evidence: [], remark: '',
  }
}
function normalizeGsb(g: any): Gsb {
  const e = emptyGsb()
  if (!g || !Object.keys(g).length) return e
  return {
    ...e, ...g,
    a_findings: { good: g.a_findings?.good || [], bad: g.a_findings?.bad || [] },
    b_findings: { good: g.b_findings?.good || [], bad: g.b_findings?.bad || [] },
    a_startup: { ...e.a_startup, ...(g.a_startup || {}) },
    b_startup: { ...e.b_startup, ...(g.b_startup || {}) },
    evidence: g.evidence || [],
  }
}

async function load(keepEdits = false) {
  const t = await api.task(id)
  task.value = t
  if (!keepEdits || !dirty.value) {
    gsb.value = normalizeGsb(t.gsb)
    dirty.value = false
  }
  verifyReport.value = t.verify && 'overall' in t.verify ? (t.verify as VerifyReport) : null
  loading.value = false
  // 落在哪一页，看这道题现在缺的是什么：还在跑就看两侧判定；等质检而质检有话说
  // 就去质检页，那是这一步唯一要人动手的地方；质检过了缺录屏就停在录屏页。
  if (!tabPinned.value && !dirty.value) {
    if (!pairEnded(t)) tab.value = t.runs?.length ? 'runs' : 'prompt'
    else if (t.status === 'ANALYZED') {
      tab.value = needsHand(t) ? 'precheck' : 'gsb'
    } else if (t.status === 'QC' || t.status === 'UPLOADED' || t.status === 'DONE') {
      tab.value = SIDES.every((s) => t.screencast?.[s]) ? 'gsb' : 'screencast'
    } else tab.value = 'runs'
  }
}

/** 两道质检里有没有等着人动手的。FAIL 是判出了问题、ERROR 是自己没跑成，
 *  两者都要人看一眼；IDLE 和 RUNNING 不算 —— 那是还没轮到或者正在跑。 */
function needsHand(t: TaskDetail): boolean {
  return ['FAIL', 'ERROR'].includes(t.factcheck_status)
    || ['FAIL', 'ERROR'].includes(t.precheck_status)
}
const pairEnded = (t: TaskDetail) => (t.runs?.length === 2) && t.runs.every((r) => RUN_END.includes(r.status))

onMounted(() => { load(); if (!store.tasks.length) refreshTasks() })
useGlobalEvents((p) => { if (p.type === 'task' && p.id === id) load(true) })
const { events, total: eventTotal, truncated: eventsTruncated, thinking } = useRunEvents(id, { onFinished: () => load(true) })
const sideEvents = computed(() => events.value.filter((e) => (e.side || 'A') === viewSide.value))

const run = (s: Side) => task.value?.runs?.find((r) => r.side === s) as TaskRunDetail | undefined
const anyRunning = computed(() => !!task.value?.runs?.some((r) => r.status === 'RUNNING' || r.status === 'QUEUED'))
const ended = computed(() => !!task.value && pairEnded(task.value))
const locked = computed(() => task.value?.status === 'UPLOADED' || task.value?.status === 'DONE')
const screencastReady = computed(() => SIDES.every((s) => !!task.value?.screencast?.[s]))
/** 能不能上传只认后端算的 precheck_block（空串表示能）：状态、提交前质检、结论有没有在
 *  质检之后被改过，三件事都在它里面判过了。前端只额外要求编辑框里没有未保存的改动 */
const canUpload = computed(() => !!task.value && !task.value.precheck_block
  && verifyReport.value?.overall !== 'block' && !dirty.value)
const canComplete = computed(() => ended.value && task.value?.status !== 'DONE')
const discarded = computed(() => task.value?.status === 'DISCARDED')
const claimable = computed(() => task.value?.status === 'AVAILABLE' || task.value?.status === 'CLAIMED')
const discardable = computed(() => !!task.value && !['RUNNING', 'QUEUED', 'ANALYZING', 'DISCARDED'].includes(task.value.status))
const containersLeft = computed(() => task.value?.runs?.filter((r) => r.container_exists).length || 0)
/** 哪几侧需要重跑：结束状态不是 FINISHED，或者看护判过异常 */
const badSides = computed(() => SIDES.filter((s) => {
  const r = run(s)
  if (!r || !RUN_END.includes(r.status)) return false
  return r.status !== 'FINISHED' || !!r.abnormal?.reason
}))

const tabs = computed<[Tab, string][]>(() => (task.value?.runs?.length
  ? [['runs', '两侧运行'], ['gsb', 'GSB 结论'], ['screencast', '录屏'], ['precheck', '提交前质检'],
    ['upload', '上传'], ['steps', '轨迹步骤'], ['prompt', '题目信息']]
  : [['prompt', '题目信息']]))
/** 分析状态和录屏缺口在标签上点个色，不用翻页找 */
const gsbDot = computed(() => {
  const t = task.value
  if (!t) return ''
  if (t.analysis_status === 'RUNNING') return 'bg-run animate-breathe'
  if (t.analysis_status === 'FAILED') return 'bg-err'
  if (t.gsb_verdict) return 'bg-ok'
  return ''
})
/** 质检那个 tab 上的小点：跑着的时候呼吸，挑出问题等人改的时候亮起来。
 *
 * 两道一起点，事实那一道优先——它判的是说错了，比措辞生硬严重，颜色也更重。
 * 没跑过的不点：那不是「有事要做」，只是还没轮到。
 *
 * 不看 precheck_block：待质检的题那句话永远非空（说的是「质检还没过」），
 * 拿它点灯会让每一道待质检的题都亮着橙点，等于没点。 */
const precheckDot = computed(() => {
  const t = task.value
  if (!t || (t.status !== 'QC' && t.status !== 'ANALYZED')) return ''
  if (t.factcheck_status === 'RUNNING' || t.precheck_status === 'RUNNING') return 'bg-run animate-breathe'
  if (t.factcheck_status === 'FAIL' || t.factcheck_status === 'ERROR') return 'bg-err'
  if (t.precheck_status === 'ERROR') return 'bg-err'
  if (t.precheck_status === 'FAIL' || t.precheck_stale || t.factcheck_stale) return 'bg-warn'
  if (t.factcheck_status === 'IDLE' && t.precheck_status === 'IDLE') return ''
  return 'bg-ok'
})

/** 容器终端。事件流断掉时，只有容器自己的 stdout 还能说明它在不在动 */
const termShow = ref(false)
const termSide = ref<Side>('A')
function openTerminal(s?: Side) {
  // 不指定就先看哪一侧还在跑：要看的十有八九是它
  const running = task.value?.runs?.find((r) => r.status === 'RUNNING')
  termSide.value = s || (running?.side as Side) || 'A'
  termShow.value = true
}

const gateReport = ref<GateReport | null>(null)
const gateChecking = ref(false)
async function runGate() {
  gateChecking.value = true
  try { gateReport.value = await api.gate(id) } catch (e: any) { msg.error(e.message) } finally { gateChecking.value = false }
}

const busy = ref('')
async function act(name: string, fn: () => Promise<any>, ok?: string) {
  busy.value = name
  try {
    const r = await fn()
    if (ok) msg.success(ok)
    await load()
    await refreshTasks()
    return r
  } catch (e: any) {
    const d = e.detail
    if (d?.fields && Object.keys(d.fields).length) {
      msg.error(`${d.message}：${Object.entries(d.fields).map(([k, v]) => `${k} ${v}`).join('；')}`, { duration: 8000 })
    } else msg.error(e.message, { duration: 6000 })
    await load(true)
  } finally { busy.value = '' }
}
const stop = (side?: Side) => act('stop' + (side || ''), () => api.stop(id, side), '已发送停止')

/** 人工重跑。次数上限归零，用在看护已经放弃、但环境修好了的时候 */
function rerun(sides: Side[]) {
  const label = sides.length ? sides.join(' 和 ') + ' 侧' : '两侧'
  dialog.warning({
    title: `重跑 ${label}`,
    content: `会销毁${label}容器、把工作目录重置回初始快照、归档已有轨迹，然后重新排队跑一遍。`
      + '重跑次数会清零，之前的轨迹归档在 traces 目录下可以找回。',
    positiveText: '确认重跑',
    negativeText: '取消',
    onPositiveClick: () => act('rerun', () => api.rerun(id, sides), '已排队重跑'),
  })
}

async function claim() {
  busy.value = 'claim'
  try {
    const r = await api.claim(id)
    if (r.queued) {
      msg.success('两侧已进入队列，等待空闲槽位')
    } else {
      gateReport.value = r.gate
      const bad = Object.entries(r.prepare?.sides || {}).filter(([, v]) => !v.ok)
      if (bad.length) msg.error(`${bad.map(([s, v]) => `${s} 侧：${v.message}`).join('；')}`, { duration: 8000 })
      else msg.warning(`门禁 ${r.gate?.blocked} 项阻断，处理后再启动`)
    }
    await load()
    await refreshTasks()
  } catch (e: any) { msg.error(e.message) } finally { busy.value = '' }
}
function discard() {
  dialog.warning({
    title: `废弃题 ${task.value?.task_no}`,
    content: '废弃后该题不再出现在题库与运行舱，两侧残留容器会一并销毁。轨迹与工作目录仍保留在磁盘上，之后可在题库「已废弃」里恢复。',
    positiveText: '确认废弃',
    negativeText: '取消',
    onPositiveClick: () => act('discard', () => api.discard(id), '已废弃'),
  })
}
const restore = () => act('restore', () => api.restore(id), '已恢复')
const advance = () => act('advance', async () => {
  const r = await api.advance(id)
  if (!r.ok) throw new Error(r.error || r.message || '推进失败')
  return r
}, '已提交两侧产物并启动对比分析')
const analyze = () => { tab.value = 'gsb'; return act('analyze', () => api.analyze(id), '对比分析已启动，完成后自动填入') }
const save = () => act('save', async () => {
  const r = await api.saveGsb(id, {
    verdict: gsb.value.verdict, reason: gsb.value.reason,
    a_startup: gsb.value.a_startup, b_startup: gsb.value.b_startup, remark: gsb.value.remark,
  })
  dirty.value = false
  verifyReport.value = r.verify
  return r
}, '结论已保存并完成自检')
const upload = () => act('upload', () => api.upload(id), '已提交到 GSB 平台')
function complete() {
  const t = task.value!
  const force = t.status !== 'UPLOADED'
  dialog.warning({
    title: '完成并销毁容器',
    content: force
      ? `该题状态为「${t.status}」，尚未上传。销毁后容器内环境不可恢复（轨迹与工作目录仍在宿主机保留）。确认放弃并销毁？`
      : '将删除两侧容器并把该题标记为完成。',
    positiveText: force ? '仍然销毁' : '确认',
    negativeText: '取消',
    onPositiveClick: () => act('complete', () => api.complete(id, force), '容器已销毁，题目已完成'),
  })
}
const destroyOnly = () => act('destroy', () => api.destroyContainer(id), '容器已销毁')

function onGsb(g: Gsb) { gsb.value = g; dirty.value = true }
/** 把质检给的整段改写稿填进理由编辑框。只改编辑框，存不存由人点「保存结论并自检」定 —— 
 *  一段五六百字的话被自动换掉，人下次打开看到的已经不是自己确认过的那份，而差异翻不出来 */
function applyRewrite(text: string) {
  gsb.value = { ...gsb.value, reason: text }
  dirty.value = true
  tab.value = 'gsb'
  tabPinned.value = true
  msg.info('已填进 GSB 结论的理由框，核对后点「保存结论并自检」')
}
async function jump(p: { side?: string; step: number }) {
  if (p.side === 'A' || p.side === 'B') viewSide.value = p.side
  tab.value = 'steps'
  tabPinned.value = true
  highlightStep.value = p.step
  await ensureIndex(viewSide.value)
  await nextTick()
  document.getElementById(`step-${p.step}`)?.scrollIntoView({ block: 'center', behavior: 'smooth' })
}
async function ensureIndex(s: Side) {
  if (traceIndex.value[s] || !run(s)?.artifact?.trace_found) return
  const r = await api.traceIndex(id, s).catch(() => null)
  traceIndex.value = { ...traceIndex.value, [s]: r }
}
watch(tab, (v) => {
  if (v !== 'steps') highlightStep.value = null
  else ensureIndex(viewSide.value)
})
watch(viewSide, (s) => { if (tab.value === 'steps') ensureIndex(s) })
function pickTab(v: Tab) { tab.value = v; tabPinned.value = true }
const steps = computed(() => traceIndex.value[viewSide.value]?.steps || [])

function copy(text: string) { navigator.clipboard?.writeText(text); msg.success('已复制') }

const paramRows = computed<[string, string][]>(() => {
  const t = task.value
  if (!t) return []
  return [
    ['任务类型', t.question_type], ['任务难度', t.difficulty], ['语言/框架', t.languages],
    ['Harness', t.harness], ['Harness 版本', t.harness_version], ['操作系统', t.os_platform],
    ['复现等级', t.repro_level], ['仓库', t.repo_url], ['初始快照', t.env_snapshot],
  ]
})
const timeRows = computed<[string, string][]>(() => {
  const t = task.value
  if (!t) return []
  return [
    ['导入', fmtTime(t.created_at)], ['领取', fmtTime(t.claimed_at)], ['两侧跑完', fmtTime(t.finished_at)],
    ['上传', fmtTime(t.uploaded_at)], ['完成', fmtTime(t.done_at)], ['废弃', fmtTime(t.discarded_at)],
  ]
})
/** 上传字段预览。除了录屏链接，其余都是自动带出来的 */
const payloadPreview = computed<[string, string][]>(() => {
  const t = task.value
  if (!t) return []
  const a = run('A'), b = run('B')
  return [
    ['question_type', t.question_type], ['difficulty', t.difficulty], ['languages', t.languages],
    ['harness', t.harness || 'Claude Code'], ['harness_version', `${t.harness_version}（上传时以镜像实测为准）`],
    ['os_platform', t.os_platform], ['repro_level', t.repro_level], ['env_snapshot', t.env_snapshot],
    ['a_session_id', a?.session_id || ''], ['b_session_id', b?.session_id || ''],
    ['a_artifact_snapshot', a?.artifact_url || ''], ['b_artifact_snapshot', b?.artifact_url || ''],
    ['a_trace_file', a?.trace_file ? a.trace_file.split('/').pop() || '' : ''],
    ['b_trace_file', b?.trace_file ? b.trace_file.split('/').pop() || '' : ''],
    ['a_screencast', t.screencast?.A || ''], ['b_screencast', t.screencast?.B || ''],
    ['gsb_verdict', t.gsb_verdict ? VERDICT_LABEL[t.gsb_verdict] : ''],
    ['gsb_reason', t.gsb_reason_chars ? `${t.gsb_reason_chars} 字` : ''],
    ['validity', (task.value?.gsb as any)?.validity || '有效'],
    ['user_prompt', `${t.user_prompt.length} 字`],
  ]
})
</script>

<template>
  <div v-if="loading" class="page"><div class="card empty">加载中…</div></div>
  <div v-else-if="task" class="page !space-y-4">
    <!-- 头部 -->
    <div class="card p-4">
      <div class="flex items-center gap-3 flex-wrap">
        <span class="mono text-sm px-2.5 h-7 inline-flex items-center rounded-md bg-bg3 text-fg0 border border-line">#{{ task.task_no }}</span>
        <StatusPill :status="task.status" />
        <span v-if="task.analysis_status === 'RUNNING'" class="pill text-run border-run/50"><span class="dot bg-run animate-breathe" />对比分析中</span>
        <span v-else-if="task.analysis_status === 'FAILED'" class="pill text-err border-err/50">分析失败</span>
        <PrecheckPill v-if="task.status === 'QC' || task.status === 'ANALYZED'"
          :status="task.precheck_status" :issues="task.precheck_issues"
          :stale="task.precheck_stale" small />
        <span v-if="task.gsb_verdict" class="pill" :style="{ color: SIDE_HEX[task.gsb_verdict as Side] || HEX.fg1, borderColor: (SIDE_HEX[task.gsb_verdict as Side] || HEX.fg1) + '55' }">
          {{ VERDICT_LABEL[task.gsb_verdict] }}
        </span>
        <span class="text-fg1 text-xs">{{ task.question_type }} · {{ task.difficulty }} · {{ task.languages }}</span>
        <a v-if="task.repo_url" :href="task.repo_url" target="_blank"
          class="mono text-[12px] text-accent underline decoration-dotted">{{ task.repo_slug }}</a>
        <span class="ml-auto mono text-[12px] text-fg2">容器保留 {{ containersLeft }} / 2</span>
      </div>
      <div class="mt-3 flex items-center gap-2 flex-wrap">
        <NButton size="small" quaternary @click="router.back()">← 返回</NButton>
        <NButton v-if="claimable" size="small" type="primary" :loading="busy === 'claim'" @click="claim">领取并启动两侧</NButton>
        <NButton v-if="claimable" size="small" secondary :loading="gateChecking" @click="runGate">门禁检查</NButton>
        <NButton v-if="discarded" size="small" type="primary" secondary :loading="busy === 'restore'" @click="restore">恢复该题</NButton>
        <NButton v-if="task.runs.length" size="small" secondary
          title="接上容器的 stdout，实时看这一侧的 Claude Code 在干什么" @click="openTerminal()">打开终端</NButton>
        <NButton v-if="anyRunning" size="small" type="error" secondary :loading="busy === 'stop'" @click="stop()">停止两侧</NButton>
        <NButton v-if="task.runs.length && !locked" size="small" tertiary :loading="busy === 'rerun'" @click="rerun([])">重跑两侧</NButton>
        <NButton v-if="ended && !locked && !task.gsb_verdict" size="small" type="primary" :loading="busy === 'advance'"
          title="提交两侧产物到 A / B 分支，然后开始对比分析" @click="advance">提交产物并分析</NButton>
        <NButton v-if="ended && !locked && task.gsb_verdict" size="small" secondary :loading="busy === 'analyze'"
          :disabled="task.analysis_status === 'RUNNING'" @click="analyze">重新分析</NButton>
        <NButton v-if="ended && !locked" size="small" :type="dirty ? 'primary' : 'default'" :secondary="!dirty"
          :loading="busy === 'save'" :disabled="!dirty && !!verifyReport" @click="save">
          {{ dirty ? '保存结论并自检' : '重新自检' }}
        </NButton>
        <NButton v-if="ended && !locked" size="small" type="info" :secondary="!canUpload" :disabled="!canUpload"
          :loading="busy === 'upload'"
          :title="canUpload ? '提交到 solo2' : (dirty ? '先保存结论' : task.precheck_block || '自检有红项')"
          @click="upload">上传 GSB</NButton>
        <span class="ml-auto" />
        <NButton v-if="containersLeft && ended && task.status !== 'DONE'" size="small" tertiary :loading="busy === 'destroy'" @click="destroyOnly">仅销毁容器</NButton>
        <NButton v-if="canComplete" size="small" :type="task.status === 'UPLOADED' ? 'success' : 'warning'"
          :secondary="task.status !== 'UPLOADED'" :loading="busy === 'complete'" @click="complete">完成并销毁</NButton>
        <NButton v-if="discardable" size="small" quaternary type="error" :loading="busy === 'discard'" @click="discard">废弃</NButton>
      </div>
      <div v-if="task.branch_check?.ok === false" class="mt-3 text-xs text-err flex items-start gap-1.5">
        <span class="dot mt-1.5 shrink-0 bg-err" />
        <span>{{ task.branch_check.message }}。仓库要恰好是 main/master 加 A、B 三个分支，A、B 从初始快照切出来。</span>
      </div>
      <div v-if="task.status === 'NEEDS_ATTENTION'" class="mt-3 inner p-3 text-xs text-err leading-5">
        <!-- 转人工的原因不止「重跑用尽」一种，推产物失败、分析失败都会到这儿，所以按 auto_error 如实说 -->
        <div>需人工介入{{ task.auto_error ? `：${task.auto_error}` : '' }}。整侧重跑会把工作目录重置回初始快照、归档已有轨迹，重跑次数清零。</div>
        <div v-if="!locked" class="mt-2 flex items-center gap-2">
          <NButton v-for="s in badSides" :key="s" size="tiny" secondary type="error"
            :loading="busy === 'rerun'" @click="rerun([s])">重跑 {{ s }} 侧</NButton>
          <NButton size="tiny" quaternary :loading="busy === 'rerun'" @click="rerun([])">重跑两侧</NButton>
        </div>
      </div>
      <div v-if="ended && !task.gsb_verdict && task.analysis_status !== 'RUNNING'" class="mt-3 text-xs text-fg1">
        两侧都跑完了。看护会自动提交产物并开始对比分析，也可以点「提交产物并分析」立刻走一遍。
      </div>
      <div v-if="task.status === 'QC' && !screencastReady" class="mt-3 text-xs text-warn flex items-start gap-1.5">
        <span class="dot mt-1.5 shrink-0 bg-warn" />
        <span>
          两道质检都放行了，理由不会再动，照着它录就行。按录屏页给的步骤把两侧项目分别跑起来录完，
          把视频路径贴回录屏页，系统会收下、代传并直接提交。
        </span>
      </div>
      <div v-if="task.status === 'QC' && screencastReady && task.precheck_block"
        class="mt-3 text-xs text-warn flex items-start gap-1.5">
        <span class="dot mt-1.5 shrink-0 bg-warn" />
        <span>{{ task.precheck_block }}</span>
      </div>
      <!-- 事实那一道排在措辞前面，提示也照这个顺序给：说错了比说得生硬严重，
           而两者该做的动作完全不同 —— 一个是回去核对轨迹，一个是改句子 -->
      <div v-if="task.status === 'ANALYZED' && task.factcheck_status === 'FAIL'"
        class="mt-3 text-xs text-err flex items-start gap-1.5">
        <span class="dot mt-1.5 shrink-0 bg-err" />
        <span>
          事实核验发现 {{ task.factcheck_mismatches }} 处描述和轨迹对不上，自动订正没成功。
          去「提交前质检」页看是哪几处——报告里写了轨迹里实际是什么，照着改完确认就行。
        </span>
      </div>
      <div v-else-if="task.status === 'ANALYZED' && task.precheck_status === 'FAIL'"
        class="mt-3 text-xs text-warn flex items-start gap-1.5">
        <span class="dot mt-1.5 shrink-0 bg-warn" />
        <span>
          质检挑出 {{ task.precheck_issues }} 处机械化表达。趁还没录屏，去「提交前质检」页逐条改完再录，
          录完再改理由就得重录一遍。
        </span>
      </div>
      <div v-else-if="task.status === 'ANALYZED' && task.factcheck_applied"
        class="mt-3 text-xs text-fg1 flex items-start gap-1.5">
        <span class="dot mt-1.5 shrink-0 bg-ok" />
        <span>
          事实核验对着轨迹订正了 {{ task.factcheck_mismatches }} 处描述，改了哪几处在「提交前质检」页写着。
        </span>
      </div>
      <div v-if="discarded" class="mt-3 text-xs text-fg1">
        该题已于 {{ fmtTime(task.discarded_at) }} 废弃，不再出现在题库与运行舱列表中。
      </div>
      <!-- 难度筛选是在开分析之前做的，废弃的题一次分析额度都没花。恢复之后不再按阈值筛它，
           所以这句话要连「按恢复会发生什么」一起说清楚 -->
      <div v-if="task.difficulty_screen?.verdict === 'discard'" class="mt-3 inner p-3 text-xs text-warn leading-5">
        难度筛选未通过：{{ task.difficulty_screen.reason }}。这一步在 GSB 分析之前，所以还没有花掉分析额度。
        按「恢复」就能把它捞回来接着分析，恢复之后不再按阈值筛这道题。
      </div>
      <div v-if="!canUpload && task.status === 'QC' && verifyReport?.overall === 'block'" class="mt-3 text-xs text-err">
        自检存在红项，上传按钮已禁用。
      </div>
    </div>

    <div class="grid grid-cols-1 xl:grid-cols-12 gap-4">
      <!-- 左：跑过的题看事件流，没跑过的看运行前检查 -->
      <div class="xl:col-span-5 card p-4 flex flex-col"
        :class="task.runs.length ? 'h-[calc(100vh-300px)] min-h-[520px]' : ''">
        <template v-if="task.runs.length">
          <div class="flex items-center gap-2 mb-2">
            <div class="h2">事件流</div>
            <div class="flex gap-1">
              <button v-for="s in SIDES" :key="s" class="w-7 h-6 rounded-md mono text-[12px] border transition-colors"
                :class="viewSide === s ? 'text-white font-semibold border-transparent' : 'border-line text-fg1 hover:text-fg0'"
                :style="viewSide === s ? { background: SIDE_HEX[s] } : {}" @click="viewSide = s">{{ s }}</button>
            </div>
            <span class="mono text-[12px] text-fg2">{{ fmtDuration(run(viewSide)?.started_at, run(viewSide)?.finished_at, nowMs) }}</span>
            <span v-if="run(viewSide)?.status === 'RUNNING'" class="ml-auto pill h-6 text-[12px] text-run border-run/50"><span class="dot bg-run animate-breathe" />实时</span>
          </div>
          <div v-if="eventsTruncated" class="inner px-3 py-1.5 mb-2 text-[12px] text-fg2 leading-5">
            两侧共 {{ eventTotal }} 条事件，这里只留了最后 {{ events.length }} 条。完整过程看轨迹 jsonl。
          </div>
          <div v-if="thinking[viewSide]" class="inner px-3 py-1.5 mb-2 text-[12px] text-run flex items-center gap-2">
            <span class="dot bg-run animate-breathe" />{{ viewSide }} 侧思考中 · 约 {{ thinking[viewSide] }} tokens
          </div>
          <Timeline :events="sideEvents" :follow="run(viewSide)?.status === 'RUNNING'" class="flex-1 min-h-0" />
        </template>
        <template v-else>
          <div class="flex items-center gap-3 mb-3">
            <div class="h2">运行前检查</div>
            <span class="text-xs text-fg2">启动容器前会自动执行同样的检查</span>
          </div>
          <GateChecks :task="task" :report="gateReport" :checking="gateChecking" @recheck="runGate" />
          <div v-if="!gateReport && !gateChecking" class="mt-1">
            <NButton size="small" secondary block @click="runGate">执行门禁检查</NButton>
          </div>
        </template>
      </div>

      <!-- 右：Tab -->
      <div class="xl:col-span-7 space-y-4">
        <div class="flex items-center gap-1">
          <button v-for="t in tabs" :key="t[0]"
            class="px-3 h-9 rounded-inner text-xs transition-colors flex items-center gap-1.5"
            :class="tab === t[0] ? 'bg-accent/15 text-accent' : 'text-fg1 hover:text-fg0 hover:bg-bg3/60'"
            @click="pickTab(t[0])">
            {{ t[1] }}
            <span v-if="t[0] === 'gsb' && gsbDot" class="dot" :class="gsbDot" />
            <span v-else-if="t[0] === 'screencast' && task.status === 'ANALYZED' && !screencastReady" class="dot bg-warn animate-breathe" />
            <span v-else-if="t[0] === 'precheck' && precheckDot" class="dot" :class="precheckDot" />
          </button>
        </div>

        <!-- 两侧运行 -->
        <template v-if="tab === 'runs'">
          <SideStrip :runs="task.runs" />
          <!-- 下面那两张卡是收尾时记下来的账，跑着的时候还没有；这一张是现问 docker 的实况 -->
          <ContainerLive :task-id="id" @terminal="openTerminal" />
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div v-for="s in SIDES" :key="s" class="card p-4 space-y-2">
              <div class="flex items-center gap-2">
                <span class="mono text-[12px] font-semibold w-5 h-5 inline-flex items-center justify-center rounded"
                  :style="{ color: SIDE_HEX[s], background: SIDE_HEX[s] + '1f' }">{{ s }}</span>
                <span class="text-fg0 font-medium text-sm">{{ run(s) ? RUN_LABEL[run(s)!.status] : '未建' }}</span>
                <span v-if="run(s)?.attempt && run(s)!.attempt > 1" class="pill h-5 text-[12px] text-warn border-warn/40">第 {{ run(s)!.attempt }} 次</span>
                <NButton v-if="run(s)" size="tiny" quaternary class="ml-auto" @click="openTerminal(s)">终端</NButton>
                <NButton v-if="run(s) && !locked" size="tiny" quaternary :loading="busy === 'rerun'" @click="rerun([s])">重跑</NButton>
              </div>
              <template v-if="run(s)">
                <div class="text-xs flex justify-between"><span class="text-fg1">退出码</span><span class="mono" :class="run(s)!.exit_code === 0 ? 'text-ok' : 'text-err'">{{ run(s)!.exit_code ?? '—' }}</span></div>
                <div class="text-xs flex justify-between"><span class="text-fg1">subtype</span><span class="mono" :class="run(s)!.protocol?.subtype === 'success' ? 'text-ok' : 'text-err'">{{ run(s)!.protocol?.subtype || '无 result' }}</span></div>
                <div class="text-xs flex justify-between"><span class="text-fg1">轮次 / 人类回合</span><span class="mono nums">{{ run(s)!.protocol?.num_turns ?? '—' }} / {{ run(s)!.artifact?.human_turns ?? '—' }}</span></div>
                <div class="text-xs flex justify-between"><span class="text-fg1">模型耗时</span><span class="mono nums">{{ fmtMs(run(s)!.protocol?.duration_ms) }}</span></div>
                <div class="text-xs flex justify-between"><span class="text-fg1">轨迹</span><span class="mono" :class="run(s)!.artifact?.trace_found ? 'text-ok' : 'text-err'">{{ run(s)!.artifact?.trace_found ? `${run(s)!.artifact.trace_count} 份` : '缺失' }}</span></div>
                <div class="text-xs flex justify-between"><span class="text-fg1">工具调用 / 报错</span><span class="mono nums">{{ run(s)!.artifact?.tool_calls ?? '—' }} / <span class="text-warn">{{ run(s)!.artifact?.tool_errors ?? '—' }}</span></span></div>
                <div class="text-xs flex justify-between"><span class="text-fg1">改动文件</span><span class="mono nums" :class="run(s)!.artifact?.changed_files ? 'text-ok' : 'text-warn'">{{ run(s)!.artifact?.changed_files ?? '—' }}</span></div>
                <div class="text-xs flex justify-between gap-2"><span class="text-fg1 shrink-0">容器</span><span class="mono text-fg2 truncate" :title="run(s)!.container_name">{{ run(s)!.container_name }} {{ run(s)!.container_exists ? '保留中' : '已销毁' }}</span></div>
                <div class="inner px-2.5 py-2 cursor-pointer" @click="run(s)!.session_id && copy(run(s)!.session_id)">
                  <div class="label">SessionID（轨迹文件名）</div>
                  <div class="mono text-[12px] break-all" :class="run(s)!.session_id ? 'text-fg0' : 'text-err'">{{ run(s)!.session_id || '未获取' }}</div>
                </div>
                <div class="inner px-2.5 py-2">
                  <div class="label">产物提交</div>
                  <a v-if="run(s)!.artifact_url" :href="run(s)!.artifact_url" target="_blank"
                    class="mono text-[12px] text-accent break-all underline decoration-dotted">{{ run(s)!.artifact_url }}</a>
                  <div v-else class="mono text-[12px] text-warn">未提交</div>
                </div>
                <div v-if="run(s)!.gateway_errors?.length" class="text-[12px] text-warn">
                  网关报错 {{ run(s)!.gateway_errors.join('、') }}（不作为 GSB 判断依据，只触发重跑）
                </div>
                <div v-if="run(s)!.abnormal?.reason" class="text-[12px] text-warn break-all">
                  异常：{{ run(s)!.abnormal.reason }}{{ run(s)!.abnormal.gave_up ? '（已放弃自动重跑）' : '' }}
                </div>
                <div v-for="n in run(s)!.notes" :key="n" class="text-[12px] text-warn break-all">{{ n }}</div>
                <div v-if="run(s)!.error" class="inner p-2 text-[12px] text-err mono whitespace-pre-wrap">{{ run(s)!.error }}</div>
                <div class="pt-1">
                  <div class="label mb-1">git diff --stat</div>
                  <pre class="mono text-[11px] text-fg1 whitespace-pre-wrap max-h-40 overflow-auto inner p-2">{{ run(s)!.git_diff_stat || '（无改动）' }}</pre>
                </div>
                <a v-if="run(s)!.trace_file" :href="api.traceUrl(id, s)" class="inline-flex"><NButton size="tiny" tertiary>下载 {{ s }} 侧轨迹</NButton></a>
              </template>
              <div v-else class="empty">尚未创建</div>
            </div>
          </div>
        </template>

        <!-- GSB 结论 -->
        <template v-if="tab === 'gsb'">
          <div v-if="!ended" class="card empty">两侧都跑完后才能对比</div>
          <template v-else>
            <div class="card p-4 flex items-center gap-4 flex-wrap">
              <div><div class="label">分析模型</div><div class="mono text-xs text-fg0">{{ task.analysis?.model || '—' }}</div></div>
              <div><div class="label">分析耗时</div><div class="mono text-xs text-fg0 nums">{{ task.analysis?.duration_s ? task.analysis.duration_s + 's' : '—' }}</div></div>
              <div><div class="label">完成时间</div><div class="mono text-xs text-fg0 nums">{{ fmtTime(task.analysis?.finished_at) }}</div></div>
              <div v-if="gsb.validity" class="min-w-0 flex-1">
                <div class="label">有效性</div>
                <div class="text-xs text-warn truncate" :title="gsb.validity">{{ gsb.validity }}</div>
              </div>
              <NTag v-if="dirty" size="small" type="warning" :bordered="false">有未保存修改</NTag>
              <NTag v-else-if="locked" size="small" :bordered="false">已上传 · 只读</NTag>
            </div>
            <div v-if="task.analysis_status === 'RUNNING'" class="card p-4 text-xs text-run flex items-center gap-2">
              <span class="dot bg-run animate-breathe" />正在读两侧轨迹和改动做对比，通常 5–20 分钟，完成后自动填入下方。
            </div>
            <div v-else-if="task.analysis_status === 'FAILED'" class="card p-4 space-y-1">
              <div class="text-err text-sm font-medium">分析没跑完</div>
              <div class="text-fg1 text-xs leading-5">{{ task.analysis?.error || task.auto_error || '未知原因' }}</div>
            </div>
            <GsbEditor :gsb="gsb" :readonly="locked" @update="onGsb" @jump="jump" />
            <VerifyBar :report="verifyReport" />
          </template>
        </template>

        <!-- 录屏 -->
        <template v-if="tab === 'screencast'">
          <div v-if="!task.gsb_verdict" class="card empty">分析出结论后再录屏，那时才知道两侧各自怎么启动</div>
          <ScreencastPanel v-else :task="task" :gsb="gsb" @saved="load(true)" />
        </template>

        <!-- 提交前质检：事实核验在前、措辞在后，摆放顺序照流水线的顺序来。
             先把话说对，再把话说顺——反过来打磨的是一段事实还错着的话 -->
        <template v-if="tab === 'precheck'">
          <div v-if="!task.gsb_verdict" class="card empty">还没有理由正文，质检没有可读的东西</div>
          <template v-else>
            <FactcheckPanel :task="task" :report="task.factcheck" :dirty="dirty" :readonly="locked"
              @confirmed="load()" @ran="load()" />
            <PrecheckPanel :task="task" :report="task.precheck" :dirty="dirty" :readonly="locked"
              @confirmed="load()" @ran="load()" @apply="applyRewrite" />
          </template>
        </template>

        <!-- 上传 -->
        <template v-if="tab === 'upload'">
          <div class="card p-4">
            <div class="flex items-center gap-3 mb-3">
              <div class="h2">提交字段预览</div>
              <span class="mono text-[12px] text-fg2">POST /api/v1/gsb/submissions</span>
              <NButton size="tiny" type="info" class="ml-auto" :disabled="!canUpload" :loading="busy === 'upload'" @click="upload">上传</NButton>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-1.5">
              <div v-for="[k, v] in payloadPreview" :key="k" class="inner px-3 py-1.5 flex items-center gap-3 text-xs">
                <span class="mono text-fg2 w-[168px] shrink-0">{{ k }}</span>
                <span class="mono truncate" :class="v ? 'text-fg0' : 'text-err'" :title="v">{{ v || '缺失' }}</span>
              </div>
            </div>
            <div class="text-[12px] text-fg2 mt-3">
              除了两条录屏链接，其余字段都是自动带出来的。还要过两道门：自检无红项，提交前质检放行。
            </div>
          </div>
          <div v-if="task.upload && Object.keys(task.upload).length" class="card p-4 space-y-2">
            <div class="flex items-center gap-3">
              <div class="h2">上次上传</div>
              <span class="pill h-5 text-[12px]" :class="task.upload.ok ? 'text-ok border-ok/50' : 'text-err border-err/50'">
                {{ task.upload.ok ? `成功 · #${task.upload.submission_id}` : '失败' }}
              </span>
              <span class="mono text-[12px] text-fg2 ml-auto">{{ fmtTime(task.upload.started_at) }}</span>
            </div>
            <div v-if="task.upload.message" class="text-xs" :class="task.upload.ok ? 'text-fg1' : 'text-err'">{{ task.upload.message }}</div>
            <div v-if="task.upload.fields" class="space-y-1">
              <div v-for="(m, f) in task.upload.fields" :key="f" class="inner px-3 py-1.5 text-xs flex gap-3">
                <span class="mono text-warn w-[168px] shrink-0">{{ f }}</span><span class="text-fg0">{{ m }}</span>
              </div>
            </div>
            <pre v-if="task.upload.steps?.length" class="mono text-[12px] text-fg2 inner p-2 whitespace-pre-wrap">{{ task.upload.steps.join('\n') }}</pre>
          </div>
        </template>

        <!-- 轨迹步骤 -->
        <template v-if="tab === 'steps'">
          <div class="card p-4">
            <div class="flex items-center gap-2 mb-3">
              <div class="h2">轨迹步骤索引</div>
              <div class="flex gap-1">
                <button v-for="s in SIDES" :key="s" class="w-7 h-6 rounded-md mono text-[12px] border transition-colors"
                  :class="viewSide === s ? 'text-white font-semibold border-transparent' : 'border-line text-fg1 hover:text-fg0'"
                  :style="viewSide === s ? { background: SIDE_HEX[s] } : {}" @click="viewSide = s">{{ s }}</button>
              </div>
              <span class="mono text-[12px] text-fg2">{{ steps.length }} 步 · 供结论证据引用</span>
            </div>
            <div v-if="!steps.length" class="empty">无轨迹或尚未解析</div>
            <div v-else class="space-y-1 max-h-[calc(100vh-360px)] overflow-auto pr-1">
              <div v-for="s in steps" :key="s.step" :id="`step-${s.step}`"
                class="inner px-3 py-2 text-xs border transition-colors"
                :class="highlightStep === s.step ? 'border-accent bg-accent/10' : 'border-transparent'">
                <div class="flex items-center gap-2 mono text-[12px]">
                  <span class="text-fg2">#{{ s.step }}</span>
                  <span :class="s.kind === 'tool' ? (s.is_error ? 'text-err' : 'text-run') : 'text-accent'">{{ s.kind === 'tool' ? s.tool : 'text' }}</span>
                  <span class="ml-auto text-fg2">{{ fmtTime(s.ts) }}</span>
                </div>
                <div class="text-fg0 mt-0.5 break-all">{{ s.summary }}</div>
                <div v-if="s.result" class="text-fg2 mt-0.5 break-all mono text-[12px]">→ {{ s.result }}</div>
                <div v-if="s.files?.length" class="mt-1 flex flex-wrap gap-1">
                  <span v-for="f in s.files" :key="f" class="mono text-[11px] px-1.5 rounded bg-white border border-line text-fg1">{{ f }}</span>
                </div>
              </div>
            </div>
          </div>
        </template>

        <!-- 题目信息 -->
        <template v-if="tab === 'prompt'">
          <div class="card p-4">
            <div class="h2 mb-3">提交参数</div>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-2">
              <div v-for="[k, v] in paramRows" :key="k" class="inner px-3 py-2 text-xs flex gap-3">
                <span class="text-fg1 w-[104px] shrink-0">{{ k }}</span>
                <span class="mono break-all" :class="v ? 'text-fg0' : 'text-fg2'">{{ v || '待运行后回填' }}</span>
              </div>
            </div>
          </div>
          <div class="card p-4">
            <div class="flex items-center gap-3 mb-3">
              <div class="h2">发送给模型的 prompt</div>
              <span class="mono text-[12px] text-fg2">{{ task.user_prompt.length }} 字 · 两侧发的是同一段</span>
              <NButton size="tiny" tertiary class="ml-auto" @click="copy(task.user_prompt)">复制</NButton>
            </div>
            <pre class="text-xs text-fg0 whitespace-pre-wrap inner p-4 leading-6 max-h-[520px] overflow-auto">{{ task.user_prompt }}</pre>
          </div>
          <div v-if="Object.keys(task.meta).length" class="card p-4">
            <div class="h2 mb-3">项目与路径</div>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-2">
              <div v-for="(v, k) in task.meta" :key="k" class="inner px-3 py-2 text-xs">
                <div class="label">{{ k }}</div>
                <div class="mono text-fg0 break-all">{{ v }}</div>
              </div>
            </div>
          </div>
          <div class="card p-4">
            <div class="h2 mb-3">时间线</div>
            <div class="grid grid-cols-2 md:grid-cols-4 gap-2">
              <div v-for="[k, v] in timeRows" :key="k" class="inner px-3 py-2 text-xs">
                <div class="label">{{ k }}</div>
                <div class="mono nums" :class="v === '—' ? 'text-fg2' : 'text-fg0'">{{ v }}</div>
              </div>
            </div>
          </div>
        </template>
      </div>
    </div>

    <ContainerTerminal v-model:show="termShow" v-model:side="termSide" :task-id="id" :task-no="task.task_no" />
  </div>
  <div v-else class="page"><div class="card empty">任务不存在 <NButton size="tiny" tertiary @click="router.push('/runs')">返回</NButton></div></div>
</template>
