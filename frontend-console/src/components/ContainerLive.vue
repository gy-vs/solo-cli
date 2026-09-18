<script setup lang="ts">
/** 两侧容器此刻的样子。数字全部现问 docker，三秒一轮。
 *
 * 跟旁边那张「两侧运行」卡片不是一回事：那张显示的是收尾时记下来的账，跑着的时候
 * 那份账还不存在（退出码、轮次、用量都要等结束才有）。这里回答的是另一个问题 ——
 * 这一刻容器到底在不在干活。最要紧的是「最后输出」：事件采集一断，界面上就再没有
 * 别的东西能区分「模型还在想」和「容器早就卡死了」。
 */
import { NButton, NSwitch } from 'naive-ui'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { api, SIDES, type ContainerLive, type Side } from '../api'
import { fmtDuration, fmtTime, HEX, RUN_LABEL, SIDE_HEX } from '../status'
import { nowMs } from '../store'

const props = defineProps<{ taskId: number }>()
const emit = defineEmits<{ (e: 'terminal', side: Side): void }>()

const items = ref<ContainerLive[]>([])
const at = ref('')
const err = ref('')
const auto = ref(true)
const loading = ref(false)
let timer: number | null = null

async function pull() {
  if (loading.value) return
  loading.value = true
  try {
    const r = await api.containers(props.taskId)
    items.value = r.items
    at.value = r.at
    err.value = ''
  } catch (e: any) {
    err.value = e.message || '取容器状态失败'
  } finally {
    loading.value = false
  }
}
/** 页面切到后台就别刷了：docker stats 每次都要采样一两秒，白烧宿主机的 CPU */
function tick() {
  if (auto.value && document.visibilityState === 'visible') pull()
}
onMounted(() => { pull(); timer = window.setInterval(tick, 3000) })
onBeforeUnmount(() => { if (timer) clearInterval(timer) })

const bySide = computed(() => {
  const m = {} as Partial<Record<Side, ContainerLive>>
  for (const c of items.value) m[c.side] = c
  return m
})

/** 容器这一刻处于什么状态，一句话说清 */
function stateText(c?: ContainerLive): string {
  if (!c) return '读取中'
  if (!c.exists) return '容器不在了'
  if (c.running) return '容器运行中'
  if (c.status === 'created') return '已创建，未启动'
  return `已退出 · exit=${c.exit_code ?? '未知'}`
}
function stateColor(c?: ContainerLive): string {
  if (!c || !c.exists) return HEX.fg2
  if (c.running) return HEX.run
  return c.exit_code === 0 ? HEX.ok : HEX.err
}
/** 多久没出声。跑着的容器超过一分钟不吭声就值得看一眼，五分钟基本是出事了 */
function silence(c?: ContainerLive): { text: string; color: string } {
  if (!c || !c.exists) return { text: '—', color: HEX.fg2 }
  if (c.silent_seconds == null) return { text: '无日志', color: HEX.err }
  const s = c.silent_seconds
  const text = s < 60 ? `${s}s 前` : s < 3600 ? `${Math.floor(s / 60)}m 前` : `${Math.floor(s / 3600)}h 前`
  if (!c.running) return { text, color: HEX.fg1 }
  return { text, color: s < 60 ? HEX.ok : s < 300 ? HEX.warn : HEX.err }
}
const claudeProc = (c?: ContainerLive) => c?.processes?.find((p) => p.cmd.includes('claude'))
/** 库里给这一侧记的账。跟容器的实况并排放，对不上的时候一眼能看出来 */
function accounted(c?: ContainerLive): string {
  const s = c?.run_status
  return s ? RUN_LABEL[s] : ''
}
</script>

<template>
  <div class="card p-4 space-y-3">
    <div class="flex items-center gap-2 flex-wrap">
      <div class="h2">容器实时</div>
      <span class="mono text-[12px] text-fg2">现问 docker · 每 3 秒一轮</span>
      <div class="ml-auto flex items-center gap-2">
        <span class="mono text-[12px] text-fg2">{{ at ? fmtTime(at) : '—' }}</span>
        <NSwitch v-model:value="auto" size="small" />
        <span class="text-[12px] text-fg1">自动刷新</span>
        <NButton size="tiny" tertiary :loading="loading" @click="pull">刷新</NButton>
      </div>
    </div>
    <div v-if="err" class="inner px-3 py-2 text-[12px] text-err">{{ err }}</div>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
      <div v-for="s in SIDES" :key="s" class="inner p-3 space-y-2">
        <div class="flex items-center gap-2">
          <span class="mono text-[11px] font-semibold w-4 h-4 inline-flex items-center justify-center rounded"
            :style="{ color: SIDE_HEX[s], background: SIDE_HEX[s] + '1f' }">{{ s }}</span>
          <span class="dot shrink-0" :class="bySide[s]?.running ? 'animate-breathe' : ''"
            :style="{ background: stateColor(bySide[s]) }" />
          <span class="text-[12px]" :style="{ color: stateColor(bySide[s]) }">{{ stateText(bySide[s]) }}</span>
          <span v-if="accounted(bySide[s])" class="mono text-[11px] text-fg2">记账 {{ accounted(bySide[s]) }}</span>
          <NButton v-if="bySide[s]?.exists" size="tiny" secondary class="ml-auto" @click="emit('terminal', s)">终端</NButton>
        </div>
        <div class="grid grid-cols-4 gap-1 mono text-[11px] nums">
          <div><div class="label">CPU</div><div class="text-fg0">{{ bySide[s]?.cpu || '—' }}</div></div>
          <div><div class="label">内存</div><div class="text-fg0" :title="bySide[s]?.mem">{{ bySide[s]?.mem_perc || '—' }}</div></div>
          <div><div class="label">已运行</div><div class="text-fg0">{{ fmtDuration(bySide[s]?.started_at, bySide[s]?.running ? null : bySide[s]?.finished_at, nowMs) }}</div></div>
          <div>
            <div class="label">最后输出</div>
            <div :style="{ color: silence(bySide[s]).color }">{{ silence(bySide[s]).text }}</div>
          </div>
        </div>
        <div v-if="bySide[s]?.running" class="text-[11px] flex items-center gap-1.5">
          <span class="dot" :style="{ background: bySide[s]!.claude_alive ? HEX.ok : HEX.err }" />
          <span :style="{ color: bySide[s]!.claude_alive ? HEX.fg1 : HEX.err }">
            {{ bySide[s]!.claude_alive ? `claude 进程在跑 · CPU 时间 ${claudeProc(bySide[s])?.time || '—'}` : 'claude 进程已经没了，容器还没退出' }}
          </span>
          <span class="mono text-fg2 ml-auto">{{ bySide[s]!.processes.length }} 个进程</span>
        </div>
        <div v-if="bySide[s]?.oom_killed" class="text-[11px] text-err">容器被 OOM 杀过，内存额度可能不够</div>
        <div v-if="bySide[s]?.error" class="text-[11px] text-err break-all">{{ bySide[s]!.error }}</div>
        <div class="mono text-[11px] text-fg2 truncate" :title="bySide[s]?.last_log">
          {{ bySide[s]?.last_log || (bySide[s]?.exists ? '暂无日志' : '—') }}
        </div>
      </div>
    </div>
  </div>
</template>
