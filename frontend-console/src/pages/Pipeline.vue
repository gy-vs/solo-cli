<script setup lang="ts">
/** 题目列表：按流水线状态分栏，每栏只放这一步该做的事。
 *
 * 跟题库页的分工：那边是卡片墙，面向「挑一道题来领」，一屏放得下六张卡；这边是清单，
 * 面向「这一批题现在该我做什么」—— 二三十道题横着比用时、比工具步数，挨个推进或整批推进，
 * 卡片墙干不了这个，所以另开一页而不是把 tab 塞回题库。
 *
 * 状态到栏的归并口径只在这里定义一次（TABS.statuses），别处要改也只改这一处：
 * 题级状态有十二个，人脑子里的步骤只有六个，两者对不上的地方全在这张表里。
 */
import { NButton, NCheckbox, NPagination, useDialog, useMessage } from 'naive-ui'
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api, SIDES, type BatchResult, type Side, type Status, type TaskBrief } from '../api'
import LaunchModal from '../components/LaunchModal.vue'
import PrecheckPill from '../components/PrecheckPill.vue'
import SideStats from '../components/SideStats.vue'
import StatusPill from '../components/StatusPill.vue'
import { fmtTime, RUN_END, VERDICT_LABEL } from '../status'
import { liveTasks, refreshTasks, store } from '../store'

const router = useRouter()
const msg = useMessage()
const dialog = useDialog()

type TabKey = 'running' | 'failed' | 'pending' | 'screencast' | 'qc' | 'submitted'

const TABS: {
  key: TabKey; label: string; statuses: Status[]; desc: string; empty: string
  /** 只有要批量操作的栏给勾选框。看的栏加上勾选框只是多一列噪声 */
  pick?: boolean
}[] = [
  {
    key: 'running', label: '运行中', statuses: ['RUNNING', 'QUEUED'],
    desc: '两侧容器在跑或在等槽位。用时是实时的，工具步数要等这一侧跑完导出轨迹才有',
    empty: '没有在跑的题 · 去题库领题',
  },
  {
    key: 'failed', label: '失败', statuses: ['NEEDS_ATTENTION'],
    desc: '重跑用尽、被人工停下、推产物或分析失败的题。重跑不看次数上限并把计数清零',
    empty: '没有需要人工处理的题',
    pick: true,
  },
  {
    key: 'pending', label: '待分析', statuses: ['RUN_DONE', 'ANALYZING'],
    desc: '两侧都正常跑完，等着推产物、写 GSB 结论、过质检。做完这一步题就进待录屏',
    empty: '没有等着分析的题',
    pick: true,
  },
  {
    key: 'screencast', label: '待录屏', statuses: ['ANALYZED'],
    desc: '结论已出，还差录屏。两条链接齐了这道题自己就进质检栏',
    empty: '没有等着录屏的题',
  },
  {
    key: 'qc', label: '质检', statuses: ['QC'],
    desc: '录屏齐了，等提交前质检。质检看的是理由读起来像不像人写的，'
      + '发起只能在对话里（app.cli precheck），这里只看结果；判了「待人工改」的题去详情页改完再确认',
    empty: '没有在质检这一步的题',
    pick: true,
  },
  {
    key: 'submitted', label: '已提交', statuses: ['UPLOADED', 'DONE'],
    desc: '已交到 solo2 平台。这里留着备查，退回重做请先在平台上撤回',
    empty: '还没有提交过的题',
  },
]

const tab = ref<TabKey>('running')
const current = computed(() => TABS.find((t) => t.key === tab.value)!)

const PAGE_SIZE = 20
const page = ref(1)

function sorted(key: TabKey, list: TaskBrief[]): TaskBrief[] {
  const by = (v: string | null | undefined) => v || ''
  if (key === 'running') return [...list].sort((a, b) => by(a.claimed_at).localeCompare(by(b.claimed_at)))
  if (key === 'submitted') return [...list].sort((a, b) => by(b.uploaded_at).localeCompare(by(a.uploaded_at)))
  return [...list].sort((a, b) => by(b.finished_at).localeCompare(by(a.finished_at)))
}

const inTab = (key: TabKey) => liveTasks.value.filter(
  (t) => TABS.find((x) => x.key === key)!.statuses.includes(t.status))
const counts = computed(() => Object.fromEntries(
  TABS.map((t) => [t.key, inTab(t.key).length])) as Record<TabKey, number>)

/** 当前栏的全部题（跨页），批量操作的「一键全选」就是选它 */
const all = computed(() => sorted(tab.value, inTab(tab.value)))
const rows = computed(() => all.value.slice((page.value - 1) * PAGE_SIZE, page.value * PAGE_SIZE))

// ---------------- 勾选 ----------------
// 整个集合换新的而不是就地 add/delete：Set 的就地改动要靠深响应才能被 computed 看见，
// 换引用是这个项目里其他地方一致的做法，也更好推断哪一次刷新动了选择。
const picked = ref(new Set<number>())
const pickedCount = computed(() => picked.value.size)
const pageAllPicked = computed(() => rows.value.length > 0 && rows.value.every((t) => picked.value.has(t.id)))

function toggle(id: number, on: boolean) {
  const next = new Set(picked.value)
  on ? next.add(id) : next.delete(id)
  picked.value = next
}
function togglePage(on: boolean) {
  const next = new Set(picked.value)
  for (const t of rows.value) on ? next.add(t.id) : next.delete(t.id)
  picked.value = next
}
function pickAll() {
  picked.value = new Set(all.value.map((t) => t.id))
}
function clearPick() {
  picked.value = new Set()
}

// 翻页保留勾选（跨页批量才有意义），切栏一律清空：两栏能做的动作不一样，
// 勾选带过去只会让人对着「批量重跑」按钮按下去，而选中的其实是上一栏的题。
watch(tab, () => { page.value = 1; clearPick() })
// SSE 一刷新，题会从这一栏流到下一栏。勾选里已经不在栏里的要删掉，否则批量动作会带着
// 一批刚流走的题发出去，后端逐个回绝，界面上报一串「状态不能推进」。
watch(all, (list) => {
  const ids = new Set(list.map((t) => t.id))
  const keep = [...picked.value].filter((id) => ids.has(id))
  if (keep.length !== picked.value.size) picked.value = new Set(keep)
  const max = Math.max(1, Math.ceil(list.length / PAGE_SIZE))
  if (page.value > max) page.value = max
})

// ---------------- 行内信息 ----------------
/** 这道题现在卡在哪。一行小字，说不清就直接把后端那句原话显出来 */
function stage(t: TaskBrief): { text: string; cls: string } {
  if (t.status === 'QUEUED') return { text: '等容器槽位', cls: 'text-fg1' }
  if (t.status === 'RUNNING') {
    const live = liveSides(t)
    if (live.length) {
      const waiting = t.runs.filter((r) => !RUN_END.includes(r.status) && r.status !== 'RUNNING')
      return { text: `${live.join('、')} 侧在跑` + (waiting.length ? `，${waiting.map((r) => r.side).join('、')} 侧在等槽位` : ''), cls: 'text-run' }
    }
    // 题级还是运行中而两侧都不在跑：容器被 prune 掉或人刚把它们停了，收尾的账还没记。
    // 这种题会由巡检转成需人工，说清楚人才不会对着一行「运行中」等下去。
    const waiting = t.runs.filter((r) => !RUN_END.includes(r.status)).map((r) => r.side)
    return waiting.length
      ? { text: `${waiting.join('、')} 侧在等槽位`, cls: 'text-fg1' }
      : { text: '两侧都已停下，等巡检收尾转人工', cls: 'text-warn' }
  }
  // 转人工的原因不止「重跑用尽」一种（被人停掉、推产物失败、分析失败都会到这儿），
  // 写死一句会把人往错的方向引
  if (t.status === 'NEEDS_ATTENTION') return { text: t.auto_error || '需人工介入', cls: 'text-err' }
  if (t.status === 'ANALYZING' || t.analysis_status === 'RUNNING') return { text: '对比分析中', cls: 'text-run' }
  if (t.analysis_status === 'FAILED') return { text: t.auto_error || '分析失败', cls: 'text-err' }
  if (t.status === 'RUN_DONE') return { text: t.auto_error || '等提交产物与分析', cls: 'text-fg1' }
  if (t.status === 'ANALYZED') {
    const missing = SIDES.filter((s) => !t.screencast?.[s])
    if (missing.length) return { text: `等 ${missing.join('、')} 侧录屏`, cls: 'text-warn' }
    return { text: `${VERDICT_LABEL[t.gsb_verdict as 'A'] || '结论已出'} · 等进质检`, cls: 'text-fg1' }
  }
  if (t.status === 'QC') {
    if (t.verify_overall === 'block') return { text: t.auto_error || '自检有红项，改完才能提交', cls: 'text-err' }
    // precheck_block 是后端算的同一句话，提交按钮灰不灰也照它。这里直接把原话显出来，
    // 别在前端翻译一遍 —— 翻译的版本和点下去被回绝的理由对不上，人会以为是两个问题
    if (t.precheck_block) return { text: t.precheck_block, cls: 'text-warn' }
    return { text: `${VERDICT_LABEL[t.gsb_verdict as 'A'] || '结论已出'} · 质检已过，可提交`, cls: 'text-ok' }
  }
  if (t.status === 'UPLOADED') return { text: `已提交 #${t.submission_id ?? ''}`, cls: 'text-info' }
  if (t.status === 'DONE') return { text: '已完成并清理', cls: 'text-fg2' }
  return { text: '', cls: 'text-fg1' }
}

/** 这一栏的时间列该看哪个时刻。
 *
 * 题级 finished_at 是推进那一步才写的，而待分析栏的题正是还没推进的那些 —— 直接读它
 * 整列都是「—」。两侧 run 各自的结束时刻一直都有，取晚的那个就是这道题跑完的时刻。
 */
function stamp(t: TaskBrief): string | null {
  if (tab.value === 'running') return t.claimed_at
  if (tab.value === 'submitted') return t.uploaded_at
  return t.finished_at || t.runs.map((r) => r.finished_at).filter(Boolean).sort().pop() || null
}

/** 哪几侧要重跑：结束状态不是正常结束，或者看护判过异常 */
function badSides(t: TaskBrief): Side[] {
  return SIDES.filter((s) => {
    const r = t.runs.find((x) => x.side === s)
    if (!r || !RUN_END.includes(r.status)) return false
    return r.status !== 'FINISHED' || !!r.abnormal?.reason
  })
}
const liveSides = (t: TaskBrief) => t.runs.filter((r) => r.status === 'RUNNING').map((r) => r.side)
/** 分析中的题按钮要按灰：那一步已经在后台跑着，再点一次只会被后端挡回来 */
const analyzable = (t: TaskBrief) => t.status !== 'ANALYZING' && t.analysis_status !== 'RUNNING'
/** 能不能提交只认后端那一句 precheck_block（空串表示能）。状态、质检结论、结论有没有
 *  过期都在它里面算过了，前端再凑一套条件只会让按钮和回绝的理由对不上。 */
const uploadable = (t: TaskBrief) => !t.precheck_block && t.verify_overall !== 'block'

// ---------------- 单题动作 ----------------
/** 正在忙的那个按钮，key 是「题 id:动作」，同一行的几个按钮各转各的圈 */
const busy = ref('')
const batching = ref(false)

async function act(key: string, run: () => Promise<string>) {
  busy.value = key
  try { msg.success(await run()) } catch (e: any) { msg.error(e.message) } finally {
    busy.value = ''
    await refreshTasks()
  }
}

const stop = (t: TaskBrief) => act(`${t.id}:stop`, async () => {
  // 停止接口对「已经没有在跑的容器」是返回 ok=false 而不是报错的，照成功提示会让人
  // 以为刚刚停掉了什么。那一刻容器其实是自己跑完的，两回事。
  const r = await api.stop(t.id)
  if (!r.ok) throw new Error(r.message)
  return r.message || `#${t.task_no} 两侧容器已停止`
})

function rerun(t: TaskBrief, sides: Side[]) {
  const what = sides.length === 1 ? `${sides[0]} 侧` : '两侧'
  dialog.warning({
    title: `重跑 #${t.task_no} 的 ${what}`,
    content: `会销毁${what}容器、把工作目录重置回初始快照、归档已有轨迹，然后重新排队跑一遍。`
      + '这一侧已有的结果不再保留，重跑次数从头算。',
    positiveText: '确认重跑',
    negativeText: '取消',
    onPositiveClick: () => act(`${t.id}:rerun`, async () =>
      (await api.rerun(t.id, sides)).message || `#${t.task_no} ${what}已排队重跑`),
  })
}

/** 提交产物并分析：推两侧产物到各自分支，再跑 GSB 对比与质检，跑完题就进待录屏 */
const analyze = (t: TaskBrief) => act(`${t.id}:analyze`, async () => {
  const r = (await api.queueAnalysis([t.id])).results[0]
  if (r?.ok === false) throw new Error(r.message || '发起失败')
  return `#${t.task_no}：${r?.message || '已排入分析'}`
})

const upload = (t: TaskBrief) => act(`${t.id}:upload`, async () =>
  (await api.upload(t.id)).message || `#${t.task_no} 已提交`)

function discard(t: TaskBrief) {
  const submitted = t.status === 'UPLOADED' || t.status === 'DONE'
  dialog.warning({
    title: `废弃题 #${t.task_no}`,
    content: submitted
      // 平台那份不会跟着消失，这句必须说清楚：不然人以为点完就撤回了，回头发现平台上还在
      ? '本机不再跟踪这道题，两侧残留容器会一并销毁。已经交到平台的那份不受影响，'
        + '要撤回请去 solo2 上操作。轨迹与工作目录仍留在磁盘上，之后可在题库的「已废弃」里恢复。'
      : '废弃后该题不再出现在这里，在跑的容器会被停掉并销毁。'
        + '轨迹与工作目录仍留在磁盘上，之后可在题库的「已废弃」里恢复。',
    positiveText: '确认废弃',
    negativeText: '取消',
    onPositiveClick: () => act(`${t.id}:discard`, async () =>
      (await api.discard(t.id)).message || `#${t.task_no} 已废弃`),
  })
}

const launchShow = ref(false)
const launchTask = ref<TaskBrief | null>(null)
function launch(t: TaskBrief) {
  launchTask.value = t
  launchShow.value = true
}

// ---------------- 批量动作 ----------------
/** 把逐题结果折成一句话。失败的按原因归并 —— 十道题各报一句会把消息条堆满，
 *  而同一个原因往往一次修完就全好了。 */
function summarize(results: BatchResult[], okWord: string): string {
  const ok = results.filter((r) => r.ok !== false)
  const bad = results.filter((r) => r.ok === false)
  let text = `${ok.length} 道${okWord}`
  if (bad.length) {
    const groups = new Map<string, number>()
    for (const r of bad) groups.set(r.message || '未知原因', (groups.get(r.message || '未知原因') || 0) + 1)
    text += `，${bad.length} 道没成：` + [...groups].map(([m, n]) => `${m}（${n} 道）`).join('；')
  }
  return text
}

function runBatch(title: string, content: string, job: () => Promise<string>) {
  dialog.info({
    title,
    content,
    positiveText: '开始',
    negativeText: '取消',
    onPositiveClick: async () => {
      batching.value = true
      try { msg.info(await job(), { duration: 8000 }) } catch (e: any) { msg.error(e.message) } finally {
        batching.value = false
        clearPick()
        await refreshTasks()
      }
    },
  })
}

function batchRerun() {
  const ids = [...picked.value]
  runBatch(`批量重跑 ${ids.length} 道题`,
    '每道题的 A、B 两侧都会重来：销毁容器、把工作目录重置回初始快照、归档已有轨迹，再排队。'
    + '已有结果不再保留。还有容器在跑的题会被跳过，先去停它。',
    async () => summarize((await api.batchRerun(ids)).results, '已排队重跑'))
}

function batchAnalyze() {
  const ids = [...picked.value]
  runBatch(`批量分析 ${ids.length} 道题`,
    '每道题依次推两侧产物到各自分支，再跑 GSB 对比与质检，跑完自动进待录屏。'
    + '这一步在调模型，一道题十几分钟是常态，同时开几道由设置里的「分析并发」决定，'
    + '超出的排队等额度，不必守着这个页面。',
    async () => {
      const results = (await api.queueAnalysis(ids)).results
      const started = results.filter((r) => r.started).length
      const waiting = results.filter((r) => r.ok !== false && !r.started).length
      const base = summarize(results, '已受理')
      return base + (waiting ? `（其中 ${started} 道已开跑，${waiting} 道在队列里等额度）` : '')
    })
}

/** 批量提交。只发质检放行的那些，挡下的照原话说清为什么没发。
 *
 * 不做「先帮你跳过、回头再说」：一批二十道里挡下三道，人必须当场知道是哪三道、
 * 因为什么，否则他会以为整批都交了，而那三道要等到对账时才发现还躺在质检栏里。
 */
const taskNos = (list: TaskBrief[], cap = 6) =>
  list.slice(0, cap).map((t) => '#' + t.task_no).join('、') + (list.length > cap ? ' 等' : '')

function batchUpload() {
  const chosen = all.value.filter((t) => picked.value.has(t.id))
  const ready = chosen.filter((t) => uploadable(t))
  const blocked = chosen.filter((t) => !uploadable(t))
  if (!ready.length) {
    msg.warning(`选中的 ${chosen.length} 道都不能提交：`
      + blocked.slice(0, 3).map((t) => `#${t.task_no} ${t.precheck_block || '自检有红项'}`).join('；'),
      { duration: 8000 })
    return
  }
  runBatch(`批量提交 ${ready.length} 道题`,
    `这 ${ready.length} 道已经质检放行：${taskNos(ready)}。`
    + '提交会把两份轨迹传到平台并落一条 GSB 记录，成功之后本机不再允许改结论。'
    + (blocked.length
      ? `\n\n另外 ${blocked.length} 道（${taskNos(blocked, 5)}）不会提交，要先在详情页按质检意见改完再确认。`
      : ''),
    async () => summarize((await api.batchUpload(ready.map((t) => t.id))).results, '已提交'))
}

// 时间列给足 112px：「09-20 23:07:59」在等宽字体下正好放不进 96px，会折成两行，
// 于是整张表的行高被这一列撑高一截。
const cols = computed(() => (current.value.pick
  ? '30px 58px 96px minmax(0,1fr) 150px 112px auto'
  : '58px 96px minmax(0,1fr) 150px 112px auto'))
</script>

<template>
  <div class="page">
    <div class="flex items-end gap-3">
      <div>
        <div class="h1">题目列表</div>
        <div class="text-fg1 text-xs mt-0.5">{{ current.desc }}</div>
      </div>
      <div class="ml-auto inner px-3 h-8 flex items-center gap-2 text-xs shrink-0">
        <span class="text-fg1">容器槽位</span>
        <span class="mono nums text-fg0">
          {{ store.status?.scheduler.running ?? 0 }} / {{ store.status?.scheduler.max_parallel ?? '-' }}
        </span>
      </div>
    </div>

    <div class="flex items-center gap-2 flex-wrap">
      <button v-for="t in TABS" :key="t.key"
        class="px-3 h-9 rounded-inner text-xs transition-colors"
        :class="tab === t.key ? 'bg-accent/15 text-accent' : (counts[t.key] ? 'text-fg1 hover:text-fg0 hover:bg-bg3/60' : 'text-fg2 hover:bg-bg3/60')"
        @click="tab = t.key">
        {{ t.label }}<span class="mono text-[12px] ml-1.5 opacity-70 nums">{{ counts[t.key] }}</span>
      </button>
    </div>

    <!-- 批量条只在能勾的栏出现，且勾了才亮起来：空着占一条高度会让人以为按钮坏了 -->
    <div v-if="current.pick && pickedCount"
      class="card px-4 py-2.5 flex items-center gap-3 text-xs border-accent/40">
      <span class="text-fg0">已选 <span class="mono nums font-semibold">{{ pickedCount }}</span> 道</span>
      <NButton v-if="tab === 'failed'" size="small" type="primary" :loading="batching" @click="batchRerun">
        批量重跑（{{ pickedCount }}）
      </NButton>
      <NButton v-if="tab === 'pending'" size="small" type="primary" :loading="batching" @click="batchAnalyze">
        批量分析并提交产物（{{ pickedCount }}）
      </NButton>
      <NButton v-if="tab === 'qc'" size="small" type="info" :loading="batching" @click="batchUpload">
        批量提交（{{ pickedCount }}）
      </NButton>
      <NButton v-if="pickedCount < counts[tab]" size="small" tertiary @click="pickAll">
        选中全部 {{ counts[tab] }} 道
      </NButton>
      <NButton size="small" quaternary class="ml-auto" @click="clearPick">清空选择</NButton>
    </div>

    <div class="card">
      <div class="px-4 h-10 grid items-center gap-3 border-b border-line text-[12px] text-fg2"
        :style="{ gridTemplateColumns: cols }">
        <NCheckbox v-if="current.pick" :checked="pageAllPicked" :disabled="!rows.length"
          :title="`选中本页 ${rows.length} 道`" @update:checked="togglePage" />
        <span>题号</span>
        <span>状态</span>
        <span>题目 · 当前卡在哪</span>
        <!-- 这一列是拿来横着比的：两侧用时和步数差得远，那份对比结论就得先当它可疑。
             到了质检这一栏，对比结论早就写完了，该横着比的换成质检结果 -->
        <span>{{ tab === 'qc' ? '提交前质检' : 'A / B 用时 · 工具步数' }}</span>
        <span>{{ tab === 'running' ? '领取时间' : tab === 'submitted' ? '提交时间' : '结束时间' }}</span>
        <span class="text-right">操作</span>
      </div>

      <div v-if="!rows.length" class="empty">{{ current.empty }}</div>

      <div v-for="t in rows" :key="t.id"
        class="px-4 py-2.5 border-b border-line last:border-0 grid items-center gap-3 hover:bg-bg3/40"
        :style="{ gridTemplateColumns: cols }">
        <NCheckbox v-if="current.pick" :checked="picked.has(t.id)" @update:checked="(v) => toggle(t.id, v)" />

        <button class="mono text-xs text-fg0 text-left hover:text-accent transition-colors"
          title="打开题目详情" @click="router.push(`/tasks/${t.id}`)">
          #{{ t.task_no }}
        </button>

        <StatusPill :status="t.status" small />

        <div class="min-w-0">
          <div class="text-xs text-fg0 truncate">
            {{ t.question_type || '未标任务类型' }}
            <span class="text-fg2">·</span>
            <span class="text-fg1">{{ t.languages || '—' }}</span>
          </div>
          <div class="text-[12px] truncate" :class="stage(t).cls" :title="stage(t).text">{{ stage(t).text }}</div>
        </div>

        <PrecheckPill v-if="tab === 'qc'" :status="t.precheck_status" :issues="t.precheck_issues"
          :stale="t.precheck_stale" small />
        <SideStats v-else :runs="t.runs" />

        <span class="mono text-[12px] text-fg2 nums whitespace-nowrap">{{ fmtTime(stamp(t)) }}</span>

        <div class="flex items-center justify-end gap-1.5">
          <NButton v-if="liveSides(t).length" size="tiny" tertiary :loading="busy === `${t.id}:stop`"
            @click="stop(t)">
            停止
          </NButton>

          <template v-if="tab === 'failed'">
            <NButton v-for="s in badSides(t)" :key="s" size="tiny" type="primary" secondary
              :loading="busy === `${t.id}:rerun`" @click="rerun(t, [s])">
              重跑 {{ s }}
            </NButton>
            <!-- 两侧都正常跑完却还转了人工，卡的是推产物或分析这一步，该给的出路是再推一次 -->
            <NButton v-if="!badSides(t).length" size="tiny" type="primary" secondary
              :loading="busy === `${t.id}:analyze`" :disabled="!analyzable(t)" @click="analyze(t)">
              重试推进
            </NButton>
            <NButton v-if="badSides(t).length === 2" size="tiny" tertiary
              :loading="busy === `${t.id}:rerun`" @click="rerun(t, [])">
              重跑两侧
            </NButton>
          </template>

          <NButton v-if="tab === 'pending'" size="tiny" type="primary" secondary
            :loading="busy === `${t.id}:analyze`" :disabled="!analyzable(t)" @click="analyze(t)">
            {{ analyzable(t) ? '分析产物并提交' : '分析中' }}
          </NButton>

          <NButton v-if="tab === 'screencast'" size="tiny" type="primary" secondary @click="launch(t)">
            启动 / 录屏
          </NButton>

          <template v-if="tab === 'qc'">
            <!-- 判了「待人工改」的题要逐条看 issues 才知道改哪句，所以给的动作是进详情页，
                 不是在这一行里塞一个编辑框 -->
            <NButton v-if="t.precheck_block" size="tiny" type="primary" secondary
              @click="router.push(`/tasks/${t.id}`)">
              去处理
            </NButton>
            <NButton size="tiny" :type="uploadable(t) ? 'info' : 'default'" :tertiary="!uploadable(t)"
              :disabled="!uploadable(t)" :loading="busy === `${t.id}:upload`"
              :title="uploadable(t) ? '提交到 solo2' : t.precheck_block || '自检有红项，改完才能提交'"
              @click="upload(t)">
              提交
            </NButton>
          </template>

          <NButton size="tiny" quaternary type="error" :loading="busy === `${t.id}:discard`" @click="discard(t)">
            废弃
          </NButton>
        </div>
      </div>

      <div v-if="all.length > PAGE_SIZE" class="px-4 py-3 flex items-center gap-3 border-t border-line">
        <span class="text-[12px] text-fg2 mono nums">
          第 {{ (page - 1) * PAGE_SIZE + 1 }}–{{ Math.min(page * PAGE_SIZE, all.length) }} 道，共 {{ all.length }} 道
        </span>
        <NPagination v-model:page="page" :item-count="all.length" :page-size="PAGE_SIZE" class="ml-auto" />
      </div>
    </div>

    <LaunchModal v-model:show="launchShow" :task="launchTask" />
  </div>
</template>
