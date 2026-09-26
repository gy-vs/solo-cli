<script setup lang="ts">
/** 录屏录制处理：待录屏之后那一段的全部动作都在这一页。
 *
 * 两种角色看同一页的不同分栏：
 * - 出题端：文档生成进度 → 已发布等人录 → 视频已回传 → 可上传（勾选后整批提交）；
 *   另外也能像录屏端一样认领自己的题来录。
 * - 录屏端（设置里打开「本机只做录屏」）：只看录制队列——认领、看文档、回传视频。
 *
 * 数据全部来自 /api/rec 一个接口，十秒拉一次。录屏仓库是两端共用的，别的设备的动作
 * 不会走本机的事件总线，靠轮询才看得见。
 */
import { NButton, NCheckbox, NDrawer, NDrawerContent, NTooltip, useDialog, useMessage } from 'naive-ui'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api, ApiError, type RecEntry, type RecLocal, type RecOverview, type RecQueueItem } from '../api'
import ReportMarkdown from '../components/ReportMarkdown.vue'
import StatusPill from '../components/StatusPill.vue'
import { fmtTime, VERDICT_LABEL } from '../status'
import { refreshTasks } from '../store'

const router = useRouter()
const msg = useMessage()
const dialog = useDialog()

const data = ref<RecOverview | null>(null)
const loading = ref(false)
const syncing = ref(false)
const busy = ref('')

async function load(quiet = true) {
  if (!quiet) loading.value = true
  try {
    data.value = await api.rec()
  } catch (e) {
    if (!quiet) msg.error((e as Error).message)
  } finally {
    loading.value = false
  }
}
let timer: number | undefined
onMounted(() => { load(false); timer = window.setInterval(load, 10000) })
onBeforeUnmount(() => window.clearInterval(timer))

async function syncNow() {
  syncing.value = true
  try {
    const r = await api.recSync()
    const s = r.stats
    msg.success(s ? `已同步：起生成 ${s.generated ?? 0}，收视频 ${s.collected ?? 0}，撤回 ${s.withdrawn ?? 0}` : '已同步')
    await load()
  } catch (e) {
    msg.error((e as Error).message)
  } finally {
    syncing.value = false
  }
}

// ---------------- 分栏 ----------------
type TabKey = 'docs' | 'waiting' | 'returned' | 'ready' | 'queue' | 'mine' | 'done'

const isRecorder = computed(() => data.value?.role === 'recorder')
const local = computed(() => data.value?.local ?? [])
const queue = computed(() => data.value?.queue ?? [])

const docState = (t: RecLocal) => t.recording.state
const entryState = (t: RecLocal) => t.entry?.state
const lists = computed(() => ({
  docs: local.value.filter((t) => t.status === 'QC'
    && (t.generating || !['published', 'collected'].includes(docState(t) || '') || !t.entry || t.entry.state === 'withdrawn')
    && !['open', 'claimed', 'recorded'].includes(entryState(t) || '')),
  waiting: local.value.filter((t) => t.status === 'QC' && ['open', 'claimed'].includes(entryState(t) || '')),
  returned: local.value.filter((t) => t.status === 'QC' && entryState(t) === 'recorded'),
  ready: local.value.filter((t) => t.status === 'READY'),
  queue: queue.value.filter((e) => e.state === 'open'),
  mine: queue.value.filter((e) => e.state === 'claimed' && e.claimed_by_me),
  done: queue.value.filter((e) => ['recorded', 'collected'].includes(e.state) && e.recorded_by_me),
}))

const TABS: { key: TabKey; label: string; desc: string; empty: string; recorder: boolean; producer: boolean }[] = [
  { key: 'docs', label: '文档生成', producer: true, recorder: false,
    desc: '题一进待录屏就按 solo-report 自动生成录屏文档：后端收集素材，模型写片段，PowerShell 四层校验不过就带着报错重写，最多三稿',
    empty: '没有等着生成文档的题' },
  { key: 'waiting', label: '待录制', producer: true, recorder: false,
    desc: '文档已发布到录屏仓库，等录屏端认领、录制。理由一改文档自动撤回并重写',
    empty: '没有在等录制的题' },
  { key: 'returned', label: '已回传', producer: true, recorder: false,
    desc: '录屏端已把两侧视频推回来，巡检会拉回本机、代传平台，题随即进「可上传」',
    empty: '没有等着收回的视频' },
  { key: 'ready', label: '可上传', producer: true, recorder: false,
    desc: '质检放行、两侧录屏到位，只差提交。勾选后可以整批提交',
    empty: '没有可以提交的题' },
  { key: 'queue', label: '录制队列', producer: true, recorder: true,
    desc: '所有出题设备发布的、还没人认领的题。认领之后文档归你，别的录屏端看不到',
    empty: '队列是空的，出题端还没有发布新的录屏文档' },
  { key: 'mine', label: '我在录', producer: true, recorder: true,
    desc: '已认领的题。打开文档照着录，录完把 A、B 两段视频传回来',
    empty: '你手上没有在录的题' },
  { key: 'done', label: '我已回传', producer: false, recorder: true,
    desc: '已回传的视频。出题端收回后状态变成「已收回」',
    empty: '还没有回传过视频' },
]
const tabs = computed(() => TABS.filter((t) => (isRecorder.value ? t.recorder : t.producer)))
const tab = ref<TabKey>('docs')
watch(isRecorder, (r) => { if (r && !tabs.value.some((t) => t.key === tab.value)) tab.value = 'queue' }, { immediate: true })
const current = computed(() => tabs.value.find((t) => t.key === tab.value) ?? tabs.value[0])
const count = (k: TabKey) => lists.value[k].length

// ---------------- 出题端动作 ----------------
function docLine(t: RecLocal): { text: string; cls: string } {
  const r = t.recording
  if (t.generating || r.state === 'generating') return { text: r.note || '生成中', cls: 'text-run' }
  if (r.state === 'failed') {
    const auto = (r.fails ?? 0) <= 2 && r.error !== '后端重启，生成中断' ? '，巡检稍后自动重试' : ''
    return { text: `生成失败（第 ${r.fails ?? 1} 次）：${r.error || '原因不明'}${auto}`, cls: 'text-err' }
  }
  if (r.state === 'withdrawn') return { text: `文档已撤回：${r.note || ''}，等重新生成`, cls: 'text-warn' }
  if (!data.value?.auto_generate) return { text: '自动生成已关闭，手动点「生成」', cls: 'text-fg1' }
  return { text: t.need || '排队等生成额度', cls: 'text-fg1' }
}

async function generate(t: RecLocal) {
  busy.value = `${t.id}:gen`
  try {
    const r = await api.recGenerate(t.id)
    msg.success(r.message)
    await load()
  } catch (e) {
    msg.error((e as Error).message)
  } finally {
    busy.value = ''
  }
}

function withdraw(t: RecLocal) {
  dialog.warning({
    title: `撤回 #${t.task_no} 的录屏文档？`,
    content: '录屏端手上的这份文档会作废（已经在录的也一样）。理由改完、题回到待录屏后会自动重新生成。',
    positiveText: '撤回', negativeText: '取消',
    onPositiveClick: async () => {
      try {
        const r = await api.recWithdraw(t.id)
        msg.success(r.message)
        await load()
      } catch (e) {
        msg.error((e as Error).message)
      }
    },
  })
}

// 可上传栏的勾选与提交
const picked = ref(new Set<number>())
const readyIds = computed(() => lists.value.ready.map((t) => t.id))
watch(readyIds, (ids) => {
  const keep = [...picked.value].filter((id) => ids.includes(id))
  if (keep.length !== picked.value.size) picked.value = new Set(keep)
})
function toggle(id: number, on: boolean) {
  const next = new Set(picked.value)
  on ? next.add(id) : next.delete(id)
  picked.value = next
}
const allPicked = computed(() => readyIds.value.length > 0 && readyIds.value.every((id) => picked.value.has(id)))
function toggleAll(on: boolean) { picked.value = new Set(on ? readyIds.value : []) }

async function submit(ids: number[]) {
  const chosen = lists.value.ready.filter((t) => ids.includes(t.id))
  const ok = chosen.filter((t) => !t.submit_block)
  const blocked = chosen.filter((t) => t.submit_block)
  if (!ok.length) {
    msg.warning(blocked.slice(0, 3).map((t) => `#${t.task_no} ${t.submit_block}`).join('；'))
    return
  }
  dialog.info({
    title: `提交 ${ok.length} 道到 solo2？`,
    content: ok.map((t) => `#${t.task_no}`).join('、')
      + (blocked.length ? `\n另有 ${blocked.length} 道被挡下：${blocked.map((t) => `#${t.task_no}`).join('、')}` : ''),
    positiveText: '提交', negativeText: '取消',
    onPositiveClick: async () => {
      busy.value = 'submit'
      try {
        const r = await api.batchUpload(ok.map((t) => t.id))
        const failed = r.results.filter((x) => !x.ok)
        if (failed.length) msg.warning(`提交 ${r.results.length - failed.length} 道成功，${failed.length} 道失败：${failed[0].message}`)
        else msg.success(`已提交 ${r.results.length} 道`)
        picked.value = new Set()
        await Promise.all([load(), refreshTasks()])
      } catch (e) {
        msg.error((e as Error).message)
      } finally {
        busy.value = ''
      }
    },
  })
}

// ---------------- 文档抽屉 ----------------
const drawer = ref(false)
const drawerTitle = ref('')
const markdown = ref('')
const drawerEntry = ref<RecEntry | null>(null)
const drawerMode = ref<'view' | 'record'>('view')
const drawerLoading = ref(false)

async function viewLocal(t: RecLocal) {
  drawerMode.value = 'view'
  drawerEntry.value = t.entry
  drawerTitle.value = `#${t.task_no} 录屏文档`
  markdown.value = ''
  drawer.value = true
  drawerLoading.value = true
  try {
    markdown.value = await api.recLocalReport(t.id)
  } catch (e) {
    markdown.value = ''
    msg.error((e as Error).message)
    drawer.value = false
  } finally {
    drawerLoading.value = false
  }
}

async function openEntry(e: RecEntry, claim: boolean) {
  busy.value = `${e.key}:open`
  try {
    const r = claim ? await api.recClaim(e.key) : await api.recReport(e.key)
    drawerEntry.value = r.entry
    markdown.value = r.markdown
    drawerTitle.value = `#${e.task_no} 录屏文档`
    drawerMode.value = r.entry.state === 'claimed' ? 'record' : 'view'
    files.value = { A: null, B: null }
    drawer.value = true
    if (claim) {
      msg.success('已认领，文档归你了')
      tab.value = 'mine'
      await load()
    }
  } catch (err) {
    msg.error((err as Error).message)
    if (err instanceof ApiError && err.status === 409) await load()
  } finally {
    busy.value = ''
  }
}

function release(e: RecEntry) {
  dialog.warning({
    title: `放回 #${e.task_no}？`,
    content: '放回后别的录屏端可以认领。已经录了一半的视频不会被传上去。',
    positiveText: '放回', negativeText: '取消',
    onPositiveClick: async () => {
      try {
        const r = await api.recRelease(e.key)
        msg.success(r.message)
        drawer.value = false
        await load()
      } catch (err) {
        msg.error((err as Error).message)
      }
    },
  })
}

function download() {
  const name = `screencast-${drawerEntry.value?.task_no ?? 'report'}.md`
  const url = URL.createObjectURL(new Blob([markdown.value], { type: 'text/markdown;charset=utf-8' }))
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  URL.revokeObjectURL(url)
}

// ---------------- 回传视频 ----------------
const files = ref<{ A: File | null; B: File | null }>({ A: null, B: null })
const uploading = ref(false)
const MAX_MB = 95

function pick(side: 'A' | 'B', ev: Event) {
  const f = (ev.target as HTMLInputElement).files?.[0] ?? null
  if (f && f.size > MAX_MB * 1024 * 1024) {
    msg.error(`${f.name} 有 ${(f.size / 1024 / 1024).toFixed(0)} MB，超过 GitHub 单文件上限，请按 720p 重新导出`)
    ;(ev.target as HTMLInputElement).value = ''
    return
  }
  files.value = { ...files.value, [side]: f }
}
const sizeOf = (f: File | null) => (f ? `${(f.size / 1024 / 1024).toFixed(1)} MB` : '')

async function sendVideos() {
  const e = drawerEntry.value
  if (!e || !files.value.A || !files.value.B) return
  uploading.value = true
  try {
    const r = await api.recVideos(e.key, files.value)
    msg.success(r.message)
    drawer.value = false
    tab.value = isRecorder.value ? 'done' : 'mine'
    await load()
  } catch (err) {
    msg.error((err as Error).message)
  } finally {
    uploading.value = false
  }
}

const ENTRY_LABEL: Record<string, { text: string; cls: string }> = {
  open: { text: '待认领', cls: 'text-fg1 border-line' },
  claimed: { text: '录制中', cls: 'text-run border-run/40' },
  recorded: { text: '已回传', cls: 'text-info border-info/40' },
  collected: { text: '已收回', cls: 'text-ok border-ok/40' },
  withdrawn: { text: '已撤回', cls: 'text-fg2 border-line' },
}
const verdict = (v: string) => VERDICT_LABEL[v as 'A'] || v || '—'
const queueRows = computed<RecQueueItem[]>(() => (['queue', 'mine', 'done'].includes(tab.value)
  ? lists.value[tab.value as 'queue' | 'mine' | 'done'] : []))
const localRows = computed<RecLocal[]>(() => (['docs', 'waiting', 'returned', 'ready'].includes(tab.value)
  ? lists.value[tab.value as 'docs' | 'waiting' | 'returned' | 'ready'] : []))
const scanNote = computed(() => {
  const s = data.value?.last_scan
  if (!s?.at) return ''
  return s.error ? `上次巡检失败：${s.error}` : `上次巡检 ${fmtTime(s.at)}`
})
</script>

<template>
  <div class="page">
    <div class="flex items-end gap-3 flex-wrap">
      <div class="min-w-0">
        <div class="h1">录屏录制处理</div>
        <div class="text-fg1 text-xs mt-0.5">{{ current?.desc }}</div>
      </div>
      <div class="ml-auto flex items-center gap-2 shrink-0">
        <div v-if="data?.available" class="inner px-3 h-8 flex items-center gap-2 text-xs">
          <span class="dot" :class="isRecorder ? 'bg-info' : 'bg-accent'" />
          <span class="text-fg0">{{ isRecorder ? '录屏端' : '出题端' }}</span>
          <span class="text-fg2">·</span>
          <span class="mono text-fg1">{{ data.device }}</span>
        </div>
        <NTooltip v-if="data?.repo">
          <template #trigger>
            <div class="inner px-3 h-8 flex items-center gap-2 text-xs max-w-[240px]">
              <span class="text-fg1 shrink-0">仓库</span>
              <span class="mono text-fg0 truncate">{{ data.repo }}</span>
            </div>
          </template>
          两端共用的私有录屏仓库：main 放事件流，每题一个 rec/设备/题号 分支
        </NTooltip>
        <NButton size="small" type="primary" secondary :loading="syncing" :disabled="!data?.available" @click="syncNow">
          立即同步
        </NButton>
      </div>
    </div>

    <!-- 没启用：说清楚缺什么、去哪儿配，而不是给一张空表 -->
    <div v-if="data && !data.available" class="card p-6 flex items-start gap-4">
      <div class="w-10 h-10 rounded-inner bg-accent/10 border border-accent/30 grid place-items-center shrink-0">
        <span class="text-accent text-lg">⏺</span>
      </div>
      <div class="flex-1 min-w-0 space-y-2">
        <div class="text-fg0 font-medium">录屏协作还没准备好</div>
        <div class="text-xs text-fg1">{{ data.message }}</div>
        <div class="text-xs text-fg2 leading-5">
          出题端与录屏端各部署一份控制台，填同一个私有「录屏仓库」。出题端的题一进待录屏就自动生成录屏文档并发布；
          录屏端在这一页认领、照文档录制、回传 A/B 两段视频；出题端自动收回，题进「可上传」，最后一步由你确认提交。
        </div>
        <NButton size="small" type="primary" @click="router.push('/settings')">去设置 → 录屏协作</NButton>
      </div>
    </div>

    <template v-else-if="data">
      <div v-if="!isRecorder && data.skill_missing.length" class="card px-4 py-2.5 text-xs text-err border-err/40">
        生成录屏文档要用 solo-report skill：{{ data.skill_missing.join('；') }}
      </div>

      <!-- 流程总览：四个数字对应出题端的四栏，一眼看出卡在哪一步 -->
      <div v-if="!isRecorder" class="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <button v-for="k in (['docs', 'waiting', 'returned', 'ready'] as TabKey[])" :key="k"
          class="card card-hover px-4 py-3 text-left transition-all"
          :class="tab === k ? 'ring-2 ring-accent/40' : ''" @click="tab = k">
          <div class="text-[12px] text-fg2">{{ TABS.find((t) => t.key === k)!.label }}</div>
          <div class="mt-1 flex items-baseline gap-2">
            <span class="text-xl font-semibold nums mono"
              :class="k === 'ready' ? 'text-ok' : k === 'returned' ? 'text-info' : k === 'docs' ? 'text-accent' : 'text-run'">
              {{ count(k) }}
            </span>
            <span v-if="k === 'docs' && data.generating" class="text-[12px] text-run flex items-center gap-1">
              <span class="dot bg-run animate-breathe" />{{ data.generating }} 道生成中
            </span>
            <span v-else-if="k === 'waiting'" class="text-[12px] text-fg2">
              {{ lists.waiting.filter((t) => t.entry?.state === 'claimed').length }} 道已有人认领
            </span>
          </div>
        </button>
      </div>

      <div class="flex items-center gap-2 flex-wrap">
        <button v-for="t in tabs" :key="t.key"
          class="px-3 h-9 rounded-inner text-xs transition-colors"
          :class="tab === t.key ? 'bg-accent/15 text-accent' : (count(t.key) ? 'text-fg1 hover:text-fg0 hover:bg-bg3/60' : 'text-fg2 hover:bg-bg3/60')"
          @click="tab = t.key">
          {{ t.label }}<span class="mono text-[12px] ml-1.5 opacity-70 nums">{{ count(t.key) }}</span>
        </button>
        <span class="ml-auto text-[12px] text-fg2" :class="data.last_scan?.error ? '!text-err' : ''">{{ scanNote }}</span>
      </div>

      <div v-if="tab === 'ready' && picked.size" class="card px-4 py-2.5 flex items-center gap-3 text-xs border-accent/40">
        <span class="text-fg0">已选 <span class="mono nums font-semibold">{{ picked.size }}</span> 道</span>
        <NButton size="small" type="info" :loading="busy === 'submit'" @click="submit([...picked])">
          批量提交（{{ picked.size }}）
        </NButton>
        <NButton size="small" quaternary class="ml-auto" @click="picked = new Set()">清空选择</NButton>
      </div>

      <!-- 本机题目（出题端四栏） -->
      <div v-if="localRows.length || ['docs', 'waiting', 'returned', 'ready'].includes(tab)" class="card">
        <template v-if="['docs', 'waiting', 'returned', 'ready'].includes(tab)">
          <div class="px-4 h-10 grid items-center gap-3 border-b border-line text-[12px] text-fg2 rec-local-cols">
            <NCheckbox v-if="tab === 'ready'" :checked="allPicked" :disabled="!lists.ready.length" @update:checked="toggleAll" />
            <span v-else />
            <span>题号</span>
            <span>状态</span>
            <span>题目 · 进度</span>
            <span>{{ tab === 'waiting' ? '录屏端' : tab === 'returned' ? '录制人' : '结论' }}</span>
            <span class="text-right">操作</span>
          </div>
          <div v-if="!localRows.length" class="empty">{{ current?.empty }}</div>
          <div v-for="t in localRows" :key="t.id"
            class="px-4 py-2.5 border-b border-line last:border-0 grid items-center gap-3 hover:bg-bg3/40 rec-local-cols">
            <NCheckbox v-if="tab === 'ready'" :checked="picked.has(t.id)" @update:checked="(v: boolean) => toggle(t.id, v)" />
            <span v-else />
            <button class="mono text-xs text-fg0 text-left hover:text-accent" @click="router.push(`/tasks/${t.id}`)">
              #{{ t.task_no }}
            </button>
            <StatusPill :status="t.status" small />
            <div class="min-w-0">
              <div class="text-xs text-fg0 truncate">
                {{ t.question_type || '未标任务类型' }}<span class="text-fg2"> · </span><span class="text-fg1">{{ t.difficulty || '—' }}</span>
                <span v-if="t.recording.kind_label" class="ml-1.5 pill text-[11px] text-fg1 border-line">{{ t.recording.kind_label }}</span>
              </div>
              <div v-if="tab === 'docs'" class="text-[12px] truncate" :class="docLine(t).cls" :title="docLine(t).text">
                <span v-if="t.generating" class="dot bg-run animate-breathe mr-1" />{{ docLine(t).text }}
              </div>
              <div v-else-if="tab === 'waiting'" class="text-[12px] text-fg1 truncate">
                {{ t.recording.rounds ? `${t.recording.rounds} 稿通过校验 · ` : '' }}发布于 {{ fmtTime(t.entry?.published_at) }}
              </div>
              <div v-else-if="tab === 'returned'" class="text-[12px] truncate"
                :class="t.recording.collect_error ? 'text-err' : 'text-info'" :title="t.recording.collect_error">
                <template v-if="t.collecting"><span class="dot bg-run animate-breathe mr-1" />正在拉回视频并代传平台</template>
                <template v-else-if="t.recording.collect_error">收回失败：{{ t.recording.collect_error }}，巡检稍后重试</template>
                <template v-else>{{ fmtTime(t.entry?.recorded_at) }} 回传，等巡检收回</template>
              </div>
              <div v-else class="text-[12px] truncate" :class="t.submit_block ? 'text-warn' : 'text-ok'" :title="t.submit_block">
                {{ t.submit_block || `录屏已到位${t.recording.recorded_by ? `（${t.recording.recorded_by} 录制）` : ''}，可提交` }}
              </div>
            </div>
            <div class="text-xs min-w-0 truncate">
              <template v-if="tab === 'waiting'">
                <span v-if="t.entry?.state === 'claimed'" class="text-run">{{ t.entry.claimed_by }} 在录</span>
                <span v-else class="text-fg2">等人认领</span>
              </template>
              <span v-else-if="tab === 'returned'" class="mono text-fg1">{{ t.entry?.recorded_by }}</span>
              <span v-else class="text-fg1">{{ verdict(t.verdict) }}</span>
            </div>
            <div class="flex items-center justify-end gap-1.5">
              <template v-if="tab === 'docs'">
                <NButton size="tiny" type="primary" secondary :loading="busy === `${t.id}:gen`"
                  :disabled="t.generating || !!data.skill_missing.length" @click="generate(t)">
                  {{ t.recording.state === 'failed' ? '重试' : '生成' }}
                </NButton>
              </template>
              <template v-if="tab === 'waiting'">
                <NButton size="tiny" tertiary @click="viewLocal(t)">文档</NButton>
                <NButton v-if="t.entry?.state === 'open'" size="tiny" type="primary" secondary
                  :loading="busy === `${t.entry.key}:open`" @click="openEntry(t.entry!, true)">
                  我来录
                </NButton>
                <NButton size="tiny" quaternary type="warning" @click="withdraw(t)">撤回</NButton>
              </template>
              <NButton v-if="tab === 'returned'" size="tiny" tertiary @click="viewLocal(t)">文档</NButton>
              <template v-if="tab === 'ready'">
                <NButton size="tiny" tertiary @click="router.push(`/tasks/${t.id}`)">详情</NButton>
                <NButton size="tiny" :type="t.submit_block ? 'default' : 'info'" :disabled="!!t.submit_block"
                  :loading="busy === 'submit'" :title="t.submit_block || '提交到 solo2'" @click="submit([t.id])">
                  提交
                </NButton>
              </template>
            </div>
          </div>
        </template>
      </div>

      <!-- 录制队列（两种角色共用） -->
      <div v-if="['queue', 'mine', 'done'].includes(tab)" class="grid gap-3 grid-cols-1 lg:grid-cols-2 2xl:grid-cols-3">
        <div v-if="!queueRows.length" class="card empty lg:col-span-2 2xl:col-span-3">{{ current?.empty }}</div>
        <div v-for="e in queueRows" :key="e.key" class="card card-hover p-4 flex flex-col gap-3 transition-all">
          <div class="flex items-start gap-3">
            <div class="w-10 h-10 rounded-inner grid place-items-center shrink-0 border"
              :class="e.state === 'claimed' ? 'bg-run/10 border-run/30 text-run' : e.state === 'open' ? 'bg-accent/10 border-accent/30 text-accent' : 'bg-ok/10 border-ok/30 text-ok'">
              <span class="mono text-xs font-semibold">{{ e.task_no.slice(0, 4) }}</span>
            </div>
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2">
                <span class="mono text-sm text-fg0 font-medium">#{{ e.task_no }}</span>
                <span class="pill text-[11px]" :class="ENTRY_LABEL[e.state].cls">{{ ENTRY_LABEL[e.state].text }}</span>
                <span v-if="e.mine" class="pill text-[11px] text-accent border-accent/30">本机出题</span>
              </div>
              <div class="text-xs text-fg1 mt-0.5 truncate">{{ e.title || '未标任务类型' }}</div>
            </div>
          </div>
          <div class="grid grid-cols-3 gap-2 text-[12px]">
            <div class="inner px-2.5 py-1.5 min-w-0">
              <div class="text-fg2">形态</div>
              <div class="text-fg0 truncate">{{ e.kind_label || '—' }}</div>
            </div>
            <div class="inner px-2.5 py-1.5 min-w-0">
              <div class="text-fg2">结论</div>
              <div class="text-fg0 truncate">{{ verdict(e.verdict) }}</div>
            </div>
            <div class="inner px-2.5 py-1.5 min-w-0">
              <div class="text-fg2">出题设备</div>
              <div class="mono text-fg0 truncate">{{ e.owner }}</div>
            </div>
          </div>
          <div class="text-[12px] text-fg2 flex items-center gap-2">
            <span v-if="e.state === 'open'">发布于 {{ fmtTime(e.published_at) }}</span>
            <span v-else-if="e.state === 'claimed'">{{ fmtTime(e.claimed_at) }} 认领</span>
            <span v-else-if="e.state === 'recorded'">{{ fmtTime(e.recorded_at) }} 回传，等出题端收回</span>
            <span v-else>{{ fmtTime(e.collected_at) }} 出题端已收回</span>
          </div>
          <div class="flex items-center gap-2 mt-auto">
            <NButton v-if="e.state === 'open'" size="small" type="primary" class="flex-1"
              :loading="busy === `${e.key}:open`" @click="openEntry(e, true)">
              认领并打开文档
            </NButton>
            <template v-else-if="e.state === 'claimed'">
              <NButton size="small" type="primary" class="flex-1" :loading="busy === `${e.key}:open`" @click="openEntry(e, false)">
                打开文档 · 回传视频
              </NButton>
              <NButton size="small" quaternary @click="release(e)">放回</NButton>
            </template>
            <NButton v-else size="small" tertiary class="flex-1" :loading="busy === `${e.key}:open`" @click="openEntry(e, false)">
              查看文档
            </NButton>
          </div>
        </div>
      </div>
    </template>

    <div v-else class="card empty">{{ loading ? '加载中…' : '读取失败' }}</div>

    <NDrawer v-model:show="drawer" :width="820" placement="right">
      <NDrawerContent :title="drawerTitle" closable :native-scrollbar="false">
        <template #header>
          <div class="flex items-center gap-3 w-full">
            <span>{{ drawerTitle }}</span>
            <span v-if="drawerEntry" class="pill text-[11px]" :class="ENTRY_LABEL[drawerEntry.state].cls">
              {{ ENTRY_LABEL[drawerEntry.state].text }}
            </span>
          </div>
        </template>
        <div v-if="drawerLoading" class="empty">加载中…</div>
        <template v-else>
          <div class="flex items-center gap-2 mb-4">
            <NButton size="small" tertiary :disabled="!markdown" @click="download">下载 MD</NButton>
            <a v-if="drawerEntry?.repo_url" :href="drawerEntry.repo_url" target="_blank"
              class="text-xs text-accent hover:underline">打开作答仓库 ↗</a>
            <NButton v-if="drawerMode === 'record' && drawerEntry" size="small" quaternary class="ml-auto"
              @click="release(drawerEntry)">
              放回队列
            </NButton>
          </div>

          <!-- 回传区放在文档上面：录完回到这页，第一眼就是它，不用翻到几百行命令后面去找 -->
          <div v-if="drawerMode === 'record'" class="card p-4 mb-5 border-accent/30 space-y-3">
            <div class="flex items-center gap-2">
              <span class="text-sm text-fg0 font-medium">回传视频</span>
              <span class="text-[12px] text-fg2">两侧都要传，720p 导出一般几 MB，单个不超过 {{ MAX_MB }} MB</span>
            </div>
            <div class="grid grid-cols-2 gap-3">
              <label v-for="s in (['A', 'B'] as const)" :key="s"
                class="inner px-3 py-3 flex items-center gap-3 cursor-pointer border border-dashed transition-colors"
                :class="files[s] ? 'border-ok/50 bg-ok/5' : 'border-line hover:border-accent/50'">
                <span class="w-8 h-8 rounded-inner grid place-items-center mono text-xs font-semibold shrink-0"
                  :class="s === 'A' ? 'bg-accent/15 text-accent' : 'bg-info/15 text-info'">{{ s }}</span>
                <span class="min-w-0 flex-1">
                  <span class="block text-xs text-fg0 truncate">{{ files[s]?.name || `选择 ${s} 侧视频` }}</span>
                  <span class="block text-[11px] text-fg2">{{ files[s] ? sizeOf(files[s]) : 'mp4 / mov / webm' }}</span>
                </span>
                <input type="file" accept="video/*" class="hidden" @change="(ev) => pick(s, ev)">
              </label>
            </div>
            <NButton type="primary" block :disabled="!files.A || !files.B" :loading="uploading" @click="sendVideos">
              {{ files.A && files.B ? '回传到录屏仓库' : '两侧视频都选好才能回传' }}
            </NButton>
          </div>

          <ReportMarkdown v-if="markdown" :source="markdown" />
        </template>
      </NDrawerContent>
    </NDrawer>
  </div>
</template>

<style scoped>
.rec-local-cols {
  grid-template-columns: 30px 64px 96px minmax(0, 1fr) 120px auto;
}
</style>
