<script setup lang="ts">
import { NButton, NTag, useDialog, useMessage } from 'naive-ui'
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, type GateReport, type Review, type TaskDetail, type VerifyReport } from '../api'
import GateChecks from '../components/GateChecks.vue'
import QcPanel from '../components/QcPanel.vue'
import ScoreEditor from '../components/ScoreEditor.vue'
import StatusPill from '../components/StatusPill.vue'
import Timeline from '../components/Timeline.vue'
import VerifyBar from '../components/VerifyBar.vue'
import { useGlobalEvents, useRunEvents } from '../sse'
import { DIMS, fmtDuration, fmtMs, fmtTime, HEX, RUN_END } from '../status'
import { nowMs, refreshTasks } from '../store'

const route = useRoute()
const router = useRouter()
const msg = useMessage()
const dialog = useDialog()
const id = Number(route.params.id)

type Tab = 'verdict' | 'review' | 'qc' | 'upload' | 'steps' | 'prompt'
const task = ref<TaskDetail | null>(null)
const loading = ref(true)
const tab = ref<Tab>('prompt')
const tabPinned = ref(false)   // 用户手动切过 tab 后不再自动跳转
const review = ref<Review>({ scores: {}, descs: {}, evidence: {}, other_issues: '', coverage: [] })
const dirty = ref(false)
const verifyReport = ref<VerifyReport | null>(null)
const traceIndex = ref<any>(null)
const highlightStep = ref<number | null>(null)

async function load(keepReview = false) {
  const t = await api.task(id)
  task.value = t
  if (!keepReview || !dirty.value) {
    review.value = normalizeReview(t.review)
    dirty.value = false
  }
  verifyReport.value = t.verify && 'overall' in t.verify ? (t.verify as VerifyReport) : null
  loading.value = false
  const isEnded = RUN_END.includes(t.status) || ['REVIEWED', 'UPLOADED', 'DONE'].includes(t.status)
  if (isEnded && !traceIndex.value && t.artifact?.trace_found) {
    traceIndex.value = await api.traceIndex(id).catch(() => null)
  }
  // 没跑过的题先看题目信息；跑完看判定；分析完直接进评审
  if (!tabPinned.value && !dirty.value) {
    tab.value = !isEnded ? 'prompt' : (t.analysis_status === 'DONE' ? 'review' : 'verdict')
  }
}
function normalizeReview(r: any): Review {
  const scores: Record<string, number | null> = {}
  const descs: Record<string, string> = {}
  const evidence: Record<string, any[]> = {}
  for (const d of DIMS) {
    scores[d] = r?.scores?.[d] ?? null
    descs[d] = r?.descs?.[d] ?? ''
    evidence[d] = r?.evidence?.[d] ?? []
  }
  return { scores, descs, evidence, other_issues: r?.other_issues ?? '', coverage: r?.coverage ?? [], verification: r?.verification }
}
onMounted(() => load())
useGlobalEvents((p) => { if (p.type === 'task' && p.id === id) load(true) })
const { events, total: eventTotal, truncated: eventsTruncated, thinkingTokens } = useRunEvents(id, { onFinished: () => load() })

const isRunning = computed(() => task.value?.status === 'RUNNING' || task.value?.status === 'QUEUED')
const ended = computed(() => !!task.value && (RUN_END.includes(task.value.status) || ['REVIEWED', 'UPLOADED', 'DONE'].includes(task.value.status)))
const locked = computed(() => task.value?.status === 'UPLOADED' || task.value?.status === 'DONE')
const canUpload = computed(() => task.value?.status === 'REVIEWED' && verifyReport.value?.overall !== 'block' && !dirty.value)
const canComplete = computed(() => ended.value && task.value?.status !== 'DONE')
const discarded = computed(() => task.value?.status === 'DISCARDED')
const claimable = computed(() => task.value?.status === 'AVAILABLE' || task.value?.status === 'CLAIMED')
const discardable = computed(() => !!task.value && !['RUNNING', 'QUEUED', 'DISCARDED'].includes(task.value.status))
// 跑过或动过的题才有东西可退；从没碰过的待领取题没必要还原
const resettable = computed(() => !!task.value && !['AVAILABLE', 'RUNNING', 'QUEUED'].includes(task.value.status))
/** 没跑过的题只有「题目信息」，跑完才出判定/评审/质检/上传/轨迹 */
const tabs = computed<[Tab, string][]>(() => ended.value || isRunning.value
  ? [['verdict', '判定'], ['review', '五维评审'], ['qc', '质检'], ['upload', '上传'], ['steps', '轨迹步骤'], ['prompt', '题目信息']]
  : [['prompt', '题目信息']])
/** 质检结论在标签上直接给个色点，不用点进去看 */
const qcDot = computed(() => {
  const t = task.value
  if (!t) return ''
  if (t.qc_status === 'RUNNING') return 'bg-run animate-breathe'
  if (t.qc_conclusion === 'PASS') return 'bg-ok'
  if (t.qc_conclusion) return 'bg-err'
  if (t.qc_status === 'FAILED') return 'bg-warn'
  return ''
})

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
const stop = () => act('stop', () => api.stop(id), '已发送停止')
async function claim() {
  busy.value = 'claim'
  try {
    const r = await api.claim(id)
    if (r.queued) {
      msg.success('已进入队列，等待空闲槽位')
      await load()
      await refreshTasks()
    } else {
      gateReport.value = r.gate
      msg.warning(`门禁 ${r.gate.blocked} 项阻断，处理后再启动`)
      await load()
    }
  } catch (e: any) { msg.error(e.message) } finally { busy.value = '' }
}
function discard() {
  dialog.warning({
    title: `废弃题 ${task.value?.task_no}`,
    content: '废弃后该题不再出现在题库与运行舱，残留容器会一并销毁。轨迹与工作目录仍保留在磁盘上，之后可在题库「已废弃」里恢复。',
    positiveText: '确认废弃',
    negativeText: '取消',
    onPositiveClick: () => act('discard', () => api.discard(id), '已废弃'),
  })
}
const restore = () => act('restore', () => api.restore(id), '已恢复')
function resetTask() {
  dialog.warning({
    title: `还原题 ${task.value?.task_no} 到做题前`,
    content: '销毁残留容器；工作区 git clean 并回到初始快照 commit；轨迹目录归档；删除导出的轨迹副本与分析中间产物；'
      + 'prompt.md 里回填过的 SessionID 与 TurnID 改回占位；清空运行、分析、评审、质检记录。'
      + '做完这道题回到「待领取」，可以重新跑。工作区里未提交的改动会被清掉。',
    positiveText: '确认还原',
    negativeText: '取消',
    onPositiveClick: () => act('reset', async () => {
      const r = await api.resetTask(id)
      const bad = r.steps.filter((s) => !s.ok)
      if (bad.length) throw new Error(bad.map((s) => `${s.step}（${s.message}）`).join('；'))
      return r
    }, '已还原到做题前'),
  })
}
const analyze = () => { tab.value = 'review'; return act('analyze', () => api.analyze(id), 'Cursor 分析已启动，完成后自动填入') }
const save = () => act('save', async () => {
  const r = await api.saveReview(id, { scores: review.value.scores, descs: review.value.descs, other_issues: review.value.other_issues })
  dirty.value = false
  verifyReport.value = r.verify
  return r
}, '评审已保存并完成核验')
const upload = () => act('upload', () => api.upload(id), '上传成功')
function complete() {
  const t = task.value!
  const force = t.status !== 'UPLOADED'
  dialog.warning({
    title: '完成并销毁容器',
    content: force
      ? `该题状态为「${t.status}」，尚未上传。销毁后容器内环境不可恢复（轨迹与工作目录仍在宿主机保留）。确认放弃并销毁？`
      : `将删除容器 ${t.container_name} 并把该题标记为完成。`,
    positiveText: force ? '仍然销毁' : '确认',
    negativeText: '取消',
    onPositiveClick: () => act('complete', () => api.complete(id, force), '容器已销毁，题目已完成'),
  })
}
const destroyOnly = () => act('destroy', () => api.destroyContainer(id), '容器已销毁')

function onReview(r: Review) { review.value = r; dirty.value = true }
async function jump(step: number) {
  tab.value = 'steps'
  highlightStep.value = step
  if (!traceIndex.value) traceIndex.value = await api.traceIndex(id).catch(() => null)
  await nextTick()
  document.getElementById(`step-${step}`)?.scrollIntoView({ block: 'center', behavior: 'smooth' })
}
watch(tab, (v) => { if (v !== 'steps') highlightStep.value = null })
function pickTab(v: Tab) { tab.value = v; tabPinned.value = true }

const verdict = computed(() => task.value?.verdict || {})
const ts = computed(() => task.value?.trace_summary || {})
const covColor = (s: string) => (s === 'done' ? HEX.ok : s === 'partial' ? HEX.warn : HEX.err)
const covLabel = (s: string) => ({ done: '已实现', partial: '部分', missing: '未实现' } as Record<string, string>)[s] || s
function copy(text: string) { navigator.clipboard?.writeText(text); msg.success('已复制') }

const paramRows = computed<[string, string][]>(() => {
  const t = task.value
  if (!t) return []
  return [
    ['任务类型', t.question_type], ['任务难度', t.difficulty], ['语言/框架', t.languages],
    ['Harness', t.harness], ['Harness 版本', t.harness_version], ['操作系统', t.os_platform],
    ['复现等级', t.repro_level], ['初始快照', t.env_snapshot],
    ['SessionID', t.session_id], ['TurnID/PromptID', t.turn_id],
    ['容器名', t.container_name], ['镜像', t.image_tag],
  ]
})
const timeRows = computed<[string, string][]>(() => {
  const t = task.value
  if (!t) return []
  return [
    ['导入', fmtTime(t.created_at)], ['领取', fmtTime(t.claimed_at)], ['开始运行', fmtTime(t.started_at)],
    ['结束', fmtTime(t.finished_at)], ['上传', fmtTime(t.uploaded_at)], ['完成', fmtTime(t.done_at)],
    ['废弃', fmtTime(t.discarded_at)],
  ]
})

const payloadPreview = computed(() => {
  const t = task.value
  if (!t) return []
  const r = review.value
  const rows: [string, string][] = [
    ['question_type', t.question_type], ['difficulty', t.difficulty], ['languages', t.languages],
    ['harness', t.harness || 'Claude Code'], ['harness_version', `${t.harness_version}（上传时以镜像实测为准）`],
    ['os_platform', t.os_platform], ['repro_level', t.repro_level], ['env_snapshot', t.env_snapshot],
    ['session_id', t.session_id], ['turn_id', t.turn_id],
    ['trace_file', t.trace_file ? t.trace_file.split('/').pop() || '' : ''],
  ]
  for (const d of DIMS) rows.push([`score_${d}`, r.scores[d] == null ? '' : String(r.scores[d])])
  rows.push(['user_prompt', `${t.user_prompt.length} 字`], ['other_issues', r.other_issues ? `${r.other_issues.length} 字` : '（空）'])
  return rows
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
        <span v-if="task.analysis_status === 'RUNNING'" class="pill text-run border-run/50"><span class="dot bg-run animate-breathe" />Cursor 分析中</span>
        <span v-else-if="task.analysis_status === 'FAILED'" class="pill text-err border-err/50">分析失败</span>
        <span class="text-fg1 text-xs">{{ task.question_type }} · {{ task.difficulty }} · {{ task.languages }}</span>
        <span class="ml-auto mono text-[12px] text-fg2 flex items-center gap-2">
          <span class="dot" :class="task.container_exists ? 'bg-run' : 'bg-fg2'" />
          {{ task.container_name }} {{ task.container_exists ? '保留中' : (task.started_at ? '已销毁' : '未创建') }}
        </span>
      </div>
      <div class="mt-3 flex items-center gap-2 flex-wrap">
        <NButton size="small" quaternary @click="router.back()">← 返回</NButton>
        <NButton v-if="claimable" size="small" type="primary" :loading="busy === 'claim'" @click="claim">领取并启动</NButton>
        <NButton v-if="claimable" size="small" secondary :loading="gateChecking" @click="runGate">门禁检查</NButton>
        <NButton v-if="discarded" size="small" type="primary" secondary :loading="busy === 'restore'" @click="restore">恢复该题</NButton>
        <NButton v-if="isRunning" size="small" type="error" secondary :loading="busy === 'stop'" @click="stop">停止容器</NButton>
        <NButton v-if="ended && !locked" size="small" type="primary" :secondary="task.analysis_status === 'DONE'" :loading="busy === 'analyze'"
          :disabled="task.analysis_status === 'RUNNING'" @click="analyze">
          {{ task.analysis_status === 'DONE' ? '重新分析' : 'Cursor 五维分析' }}
        </NButton>
        <NButton v-if="ended && !locked" size="small" :type="dirty ? 'primary' : 'default'" :secondary="!dirty" :loading="busy === 'save'" :disabled="!dirty && !!verifyReport" @click="save">
          {{ dirty ? '保存评审并核验' : '重新核验' }}
        </NButton>
        <NButton v-if="ended && !locked" size="small" type="info" :secondary="!canUpload" :disabled="!canUpload" :loading="busy === 'upload'" @click="upload">
          上传 solo-qa
        </NButton>
        <a v-if="task.trace_file" :href="api.traceUrl(id)" class="inline-flex"><NButton size="small" tertiary>下载轨迹</NButton></a>
        <span class="ml-auto" />
        <NButton v-if="task.container_exists && ended && task.status !== 'DONE'" size="small" tertiary :loading="busy === 'destroy'" @click="destroyOnly">仅销毁容器</NButton>
        <NButton v-if="canComplete" size="small" :type="task.status === 'UPLOADED' ? 'success' : 'warning'" :secondary="task.status !== 'UPLOADED'" :loading="busy === 'complete'" @click="complete">
          完成并销毁
        </NButton>
        <NButton v-if="resettable" size="small" quaternary :loading="busy === 'reset'"
          title="工作区、轨迹、回填、评审记录全部退回做题前" @click="resetTask">还原到做题前</NButton>
        <NButton v-if="discardable" size="small" quaternary type="error" :loading="busy === 'discard'" @click="discard">废弃</NButton>
      </div>
      <div v-if="discarded" class="mt-3 text-xs text-fg1">
        该题已于 {{ fmtTime(task.discarded_at) }} 废弃，不再出现在题库与运行舱列表中。
      </div>
      <div v-if="task.error" class="mt-3 inner p-3 text-xs text-err mono whitespace-pre-wrap">{{ task.error }}</div>
      <div v-if="!canUpload && task.status === 'REVIEWED' && verifyReport?.overall === 'block'" class="mt-3 text-xs text-err">核验存在红项，上传按钮已禁用。</div>
    </div>

    <div class="grid grid-cols-1 xl:grid-cols-12 gap-4">
      <!-- 左：跑过的题看事件流，没跑过的看运行前检查 -->
      <div class="xl:col-span-5 card p-4 flex flex-col"
        :class="ended || isRunning ? 'h-[calc(100vh-300px)] min-h-[520px]' : ''">
        <template v-if="ended || isRunning">
          <div class="flex items-center gap-3 mb-2">
            <div class="h2">事件流</div>
            <span class="mono text-[12px] text-fg2">{{ fmtDuration(task.started_at, task.finished_at, nowMs) }}</span>
            <span v-if="isRunning" class="ml-auto pill h-6 text-[12px] text-run border-run/50"><span class="dot bg-run animate-breathe" />实时</span>
          </div>
          <div v-if="eventsTruncated" class="inner px-3 py-1.5 mb-2 text-[12px] text-fg2 leading-5">
            共 {{ eventTotal }} 条事件，这里只显示最后 {{ events.length }} 条。完整过程看轨迹 jsonl。
          </div>
          <div v-if="isRunning && thinkingTokens" class="inner px-3 py-1.5 mb-2 text-[12px] text-run flex items-center gap-2">
            <span class="dot bg-run animate-breathe" />模型思考中 · 约 {{ thinkingTokens }} tokens
          </div>
          <Timeline :events="events" :follow="isRunning" class="flex-1 min-h-0" />
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
            class="px-3 h-9 rounded-inner text-xs transition-colors flex items-center gap-1.5" :class="tab === t[0] ? 'bg-accent/15 text-accent' : 'text-fg1 hover:text-fg0 hover:bg-bg3/60'"
            @click="pickTab(t[0])">
            {{ t[1] }}
            <span v-if="t[0] === 'qc' && qcDot" class="dot" :class="qcDot" />
          </button>
        </div>

        <!-- 判定 -->
        <template v-if="tab === 'verdict'">
          <div v-if="!ended" class="card empty">运行结束后显示三层判定</div>
          <template v-else>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div class="card p-4 space-y-1.5">
                <div class="h2">进程层</div>
                <div class="text-xs flex justify-between"><span class="text-fg1">退出码</span><span class="mono" :class="task.exit_code === 0 ? 'text-ok' : 'text-err'">{{ task.exit_code ?? '—' }}</span></div>
                <div class="text-xs flex justify-between"><span class="text-fg1">超时</span><span class="mono">{{ verdict.process?.timed_out ? '是' : '否' }}</span></div>
                <div class="text-xs flex justify-between"><span class="text-fg1">人工停止</span><span class="mono">{{ verdict.process?.manual_stop ? '是' : '否' }}</span></div>
                <div class="text-xs flex justify-between"><span class="text-fg1">镜像</span><span class="mono text-fg2 truncate max-w-[140px]" :title="task.image_tag">{{ task.image_tag.split(':').pop() }}</span></div>
              </div>
              <div class="card p-4 space-y-1.5">
                <div class="h2">协议层</div>
                <div class="text-xs flex justify-between"><span class="text-fg1">subtype</span><span class="mono" :class="verdict.protocol?.subtype === 'success' ? 'text-ok' : 'text-err'">{{ verdict.protocol?.subtype || '无 result' }}</span></div>
                <div class="text-xs flex justify-between"><span class="text-fg1">轮次</span><span class="mono nums">{{ verdict.protocol?.num_turns ?? '—' }}</span></div>
                <div class="text-xs flex justify-between"><span class="text-fg1">模型耗时</span><span class="mono nums">{{ fmtMs(verdict.protocol?.duration_ms) }}</span></div>
                <div class="text-xs flex justify-between"><span class="text-fg1">费用</span><span class="mono nums">{{ verdict.protocol?.cost_usd != null ? '$' + Number(verdict.protocol.cost_usd).toFixed(3) : '—' }}</span></div>
              </div>
              <div class="card p-4 space-y-1.5">
                <div class="h2">产物层</div>
                <div class="text-xs flex justify-between"><span class="text-fg1">轨迹</span><span class="mono" :class="verdict.artifact?.trace_found ? 'text-ok' : 'text-err'">{{ verdict.artifact?.trace_found ? `${verdict.artifact.trace_count} 份` : '缺失' }}</span></div>
                <div class="text-xs flex justify-between"><span class="text-fg1">工具调用 / 报错</span><span class="mono nums">{{ verdict.artifact?.tool_calls ?? '—' }} / <span class="text-warn">{{ verdict.artifact?.tool_errors ?? '—' }}</span></span></div>
                <div class="text-xs flex justify-between"><span class="text-fg1">改动文件</span><span class="mono nums" :class="verdict.artifact?.changed_files ? 'text-ok' : 'text-warn'">{{ verdict.artifact?.changed_files ?? '—' }}</span></div>
                <div class="text-xs flex justify-between"><span class="text-fg1">stop_reason</span><span class="mono text-fg2">{{ ts.stop_reason || '—' }}</span></div>
              </div>
            </div>
            <div v-if="verdict.notes?.length" class="card p-4 space-y-1">
              <div class="h2 mb-1">备注</div>
              <div v-for="n in verdict.notes" :key="n" class="text-xs text-warn flex gap-2"><span class="dot bg-warn mt-1.5 shrink-0" />{{ n }}</div>
            </div>
            <div class="card p-4 space-y-2">
              <div class="h2">回填</div>
              <div class="grid grid-cols-1 md:grid-cols-2 gap-2">
                <div class="inner p-3 cursor-pointer" @click="task.session_id && copy(task.session_id)">
                  <div class="label">SessionID（轨迹文件名）</div>
                  <div class="mono text-xs break-all" :class="task.session_id ? 'text-fg0' : 'text-err'">{{ task.session_id || '未获取' }}</div>
                </div>
                <div class="inner p-3 cursor-pointer" @click="task.turn_id && copy(task.turn_id)">
                  <div class="label">TurnID / PromptID</div>
                  <div class="mono text-xs break-all" :class="task.turn_id ? 'text-fg0' : 'text-err'">{{ task.turn_id || '未获取' }}</div>
                </div>
              </div>
              <div class="text-[12px] text-fg2">两项齐全时已自动写回 prompt.md（原文件另存 .bak）。点击可复制。</div>
            </div>
            <div class="card p-4 space-y-2">
              <div class="flex items-center gap-3"><div class="h2">工作目录改动</div><span class="mono text-[12px] text-fg2">git diff --stat</span></div>
              <pre class="mono text-[12px] text-fg1 whitespace-pre-wrap max-h-64 overflow-auto inner p-3">{{ task.git_diff_stat || '（无改动）' }}</pre>
            </div>
            <div v-if="ts.last_assistant_text" class="card p-4 space-y-2">
              <div class="flex items-center gap-3"><div class="h2">模型最后一段话</div><span class="mono text-[12px] text-fg2">{{ ts.model }}</span></div>
              <pre class="text-xs text-fg1 whitespace-pre-wrap max-h-64 overflow-auto inner p-3">{{ ts.last_assistant_text }}</pre>
            </div>
          </template>
        </template>

        <!-- 评审 -->
        <template v-if="tab === 'review'">
          <div v-if="!ended" class="card empty">运行结束后可发起 Cursor 分析</div>
          <template v-else>
            <div class="card p-4 flex items-center gap-4 flex-wrap">
              <div>
                <div class="label">分析模型</div>
                <div class="mono text-xs text-fg0">{{ task.analysis?.model || '—' }}</div>
              </div>
              <div>
                <div class="label">分析耗时</div>
                <div class="mono text-xs text-fg0 nums">{{ task.analysis?.duration_s ? task.analysis.duration_s + 's' : '—' }}</div>
              </div>
              <div>
                <div class="label">完成时间</div>
                <div class="mono text-xs text-fg0 nums">{{ fmtTime(task.analysis?.finished_at) }}</div>
              </div>
              <div class="min-w-0 flex-1">
                <div class="label">agent 实际验证</div>
                <div class="text-xs text-fg1 truncate" :title="review.verification?.summary">{{ review.verification?.summary || '—' }}</div>
              </div>
              <NTag v-if="dirty" size="small" type="warning" :bordered="false">有未保存修改</NTag>
              <NTag v-else-if="locked" size="small" :bordered="false">已上传 · 只读</NTag>
            </div>
            <div v-if="task.analysis_status === 'RUNNING'" class="card p-4 text-xs text-run flex items-center gap-2">
              <span class="dot bg-run animate-breathe" />Cursor agent 正在读轨迹、跑产物验证，通常需要 5–20 分钟，完成后自动填入下方。
            </div>
            <div v-if="review.coverage?.length" class="card p-4">
              <div class="h2 mb-2">需求覆盖</div>
              <div class="space-y-1">
                <div v-for="(c, i) in review.coverage" :key="i" class="inner px-3 py-2 flex items-start gap-3 text-xs">
                  <span class="pill h-5 text-[12px] shrink-0" :style="{ color: covColor(c.status), borderColor: covColor(c.status) + '55' }">{{ covLabel(c.status) }}</span>
                  <span class="text-fg0">{{ c.point }}</span>
                  <span class="ml-auto text-fg2 mono text-[12px] truncate max-w-[40%]" :title="c.evidence">{{ c.evidence }}</span>
                </div>
              </div>
            </div>
            <ScoreEditor :review="review" :verify-items="verifyReport?.items || []" :readonly="locked" @update="onReview" @jump="jump" />
            <VerifyBar :report="verifyReport" />
            <div v-if="review.verification?.commands?.length" class="card p-4">
              <div class="h2 mb-2">agent 跑过的命令</div>
              <pre class="mono text-[12px] text-fg1 inner p-3 whitespace-pre-wrap">{{ review.verification.commands.join('\n') }}</pre>
            </div>
          </template>
        </template>

        <!-- 质检 -->
        <template v-if="tab === 'qc'">
          <QcPanel :task="task" @done="load(true)" />
        </template>

        <!-- 上传 -->
        <template v-if="tab === 'upload'">
          <div class="card p-4">
            <div class="flex items-center gap-3 mb-3">
              <div class="h2">提交字段预览</div>
              <span class="text-xs text-fg2">POST {{ '/api/v1/submissions' }}</span>
              <NButton size="tiny" type="info" class="ml-auto" :disabled="!canUpload" :loading="busy === 'upload'" @click="upload">上传</NButton>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-1.5">
              <div v-for="[k, v] in payloadPreview" :key="k" class="inner px-3 py-1.5 flex items-center gap-3 text-xs">
                <span class="mono text-fg2 w-32 shrink-0">{{ k }}</span>
                <span class="mono truncate" :class="v ? 'text-fg0' : 'text-err'" :title="v">{{ v || '缺失' }}</span>
              </div>
            </div>
            <div class="text-[12px] text-fg2 mt-3">
              状态需为「已评审」且核验无红项。五维描述以评审页保存的内容为准。
            </div>
            <div v-if="task.qc_conclusion && task.qc_conclusion !== 'PASS'"
              class="inner px-3 py-2 mt-2 text-[12px] text-err leading-5">
              质检结论是「{{ task.qc_conclusion }}」，有 {{ task.qc_failed_count }} 项没过。
              直接上传大概率会被 solo-qa 打回，建议先去质检页按未通过项改描述。
            </div>
          </div>
          <div v-if="task.upload && Object.keys(task.upload).length" class="card p-4 space-y-2">
            <div class="flex items-center gap-3">
              <div class="h2">上次上传</div>
              <span class="pill h-5 text-[12px]" :class="task.upload.ok ? 'text-ok border-ok/50' : 'text-err border-err/50'">{{ task.upload.ok ? `成功 · #${task.upload.submission_id}` : '失败' }}</span>
              <span class="mono text-[12px] text-fg2 ml-auto">{{ fmtTime(task.upload.started_at) }}</span>
            </div>
            <div v-if="task.upload.message" class="text-xs" :class="task.upload.ok ? 'text-fg1' : 'text-err'">{{ task.upload.message }}</div>
            <div v-if="task.upload.fields" class="space-y-1">
              <div v-for="(m, f) in task.upload.fields" :key="f" class="inner px-3 py-1.5 text-xs flex gap-3"><span class="mono text-warn w-32 shrink-0">{{ f }}</span><span class="text-fg0">{{ m }}</span></div>
            </div>
            <pre v-if="task.upload.steps?.length" class="mono text-[12px] text-fg2 inner p-2 whitespace-pre-wrap">{{ task.upload.steps.join('\n') }}</pre>
          </div>
        </template>

        <!-- 轨迹步骤 -->
        <template v-if="tab === 'steps'">
          <div class="card p-4">
            <div class="flex items-center gap-3 mb-3">
              <div class="h2">轨迹步骤索引</div>
              <span class="mono text-[12px] text-fg2">{{ traceIndex?.steps?.length ?? 0 }} 步 · 供评审证据引用</span>
            </div>
            <div v-if="!traceIndex?.steps?.length" class="empty">无轨迹或尚未解析</div>
            <div v-else class="space-y-1 max-h-[calc(100vh-360px)] overflow-auto pr-1">
              <div v-for="s in traceIndex.steps" :key="s.step" :id="`step-${s.step}`"
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
              <span class="mono text-[12px] text-fg2">{{ task.user_prompt.length }} 字 · 容器只接收这一段</span>
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
  </div>
  <div v-else class="page"><div class="card empty">任务不存在 <NButton size="tiny" tertiary @click="router.push('/runs')">返回</NButton></div></div>
</template>
