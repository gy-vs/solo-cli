<script setup lang="ts">
/** 一侧的录屏工具条：认出项目形态、把它在本机跑起来、录一段 720p。
 *
 * 启动和录屏这两件事后端在容器里都干不了（没有 macOS 的屏幕录制权限，挂载目录上执行
 * 命令用的也是容器自己的运行时），全靠宿主机代理代劳，所以代理没起来时这两个按钮要
 * 按灰。形态探测不走代理，后端自己看挂载目录就行，代理没起也能先看该录什么。
 */
import { NButton, NSelect, useMessage } from 'naive-ui'
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { api, type HostStart, type RecordPlan, type Side } from '../api'
import { refreshHost, store } from '../store'
import { HEX, SIDE_HEX } from '../status'

const props = defineProps<{ taskId: number; taskNo: string; side: Side; disabled?: boolean }>()
/** 停录后把文件路径交出去：外面那个「本机文件路径」输入框要的就是它 */
const emit = defineEmits<{ (e: 'recorded', path: string): void }>()

const msg = useMessage()
const host = computed(() => store.host)
const reachable = computed(() => !!host.value?.reachable)
const screens = computed(() => (host.value?.screens || []).map((s, i) => ({
  label: i === 0 ? '主屏' : `屏幕 ${i + 1}`, value: s.index,
})))
const screen = ref<number | null>(null)
const pickedScreen = computed(() => screen.value ?? screens.value[0]?.value ?? 0)

/** 项目形态与录制步骤 */
const plan = ref<RecordPlan | null>(null)
const showPlan = ref(false)
const KIND_COLOR: Record<string, string> = {
  fullstack: HEX.accent, frontend: HEX.info, backend: HEX.run, headless: HEX.fg1, unknown: HEX.warn,
}
const kindHex = computed(() => KIND_COLOR[plan.value?.kind || 'unknown'])

onMounted(async () => {
  refreshHost()
  try { plan.value = await api.hostPlan(props.taskId, props.side) } catch { /* 探不出来就不显示 */ }
})

const starting = ref(false)
const started = ref<HostStart | null>(null)
const urls = ref<string[]>([])

const recording = computed(() => (host.value?.recordings || []).find(
  (r) => r.side === props.side && r.alive && r.task_no === props.taskNo,
))
const recBusy = ref(false)
const elapsed = ref(0)
let timer: number | null = null

function tick(on: boolean) {
  if (on && timer === null) timer = window.setInterval(async () => {
    elapsed.value += 1
    if (elapsed.value % 5 === 0) await refreshHost()
  }, 1000)
  if (!on && timer !== null) { clearInterval(timer); timer = null }
}
onUnmounted(() => tick(false))

async function start() {
  starting.value = true
  try {
    const r = await api.hostStart(props.taskId, props.side)
    started.value = r
    msg.success(r.message)
    pollPorts()
  } catch (e: any) { msg.error(e.message, { duration: 8000 }) } finally { starting.value = false }
}

/** dev server 起来要几秒，端口不会在启动那一刻就有，隔几秒问几次 */
async function pollPorts() {
  for (let i = 0; i < 12; i++) {
    await new Promise((r) => setTimeout(r, 2500))
    try {
      const s = await api.hostStatus(props.taskId, props.side)
      if (s.urls?.length) { urls.value = s.urls; return }
    } catch { return }
  }
}

async function toggleRecord() {
  recBusy.value = true
  try {
    if (recording.value) {
      const r = await api.hostRecordStop(props.taskId, props.side)
      tick(false)
      elapsed.value = 0
      emit('recorded', r.file)
      msg.success(`${r.message}，${Math.round(r.seconds)} 秒 / ${(r.size / 1048576).toFixed(1)}MB，路径已填好`)
    } else {
      const r = await api.hostRecordStart(props.taskId, props.side, pickedScreen.value)
      elapsed.value = 0
      tick(true)
      msg.success(r.message)
    }
    await refreshHost()
  } catch (e: any) { msg.error(e.message, { duration: 10000 }) } finally { recBusy.value = false }
}

const mmss = computed(() => {
  const s = recording.value ? Math.max(elapsed.value, Math.round(recording.value.seconds)) : 0
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
})

async function copy(text: string) {
  try { await navigator.clipboard.writeText(text); msg.success('命令已复制') } catch { msg.error('复制不了，手抄一下') }
}
</script>

<template>
  <div class="space-y-1.5">
    <div class="flex items-center gap-1.5 flex-wrap">
      <NButton size="tiny" secondary :loading="starting" :disabled="!reachable || disabled" @click="start">
        启动项目
      </NButton>
      <NButton size="tiny" :type="recording ? 'error' : 'primary'" :secondary="!recording"
        :loading="recBusy" :disabled="!reachable || !host?.ffmpeg" @click="toggleRecord">
        <span v-if="recording" class="flex items-center gap-1">
          <span class="dot bg-white animate-breathe" />停止录屏 {{ mmss }}
        </span>
        <span v-else>录屏 720p</span>
      </NButton>
      <NSelect v-if="screens.length > 1 && !recording" :value="pickedScreen" :options="screens"
        size="tiny" class="!w-24" :disabled="!reachable" @update:value="(v: number) => (screen = v)" />
    </div>

    <!-- 形态：决定了这一侧到底该录什么 -->
    <div v-if="plan" class="flex items-center gap-1.5 flex-wrap text-[11px]">
      <span class="pill h-5 !px-1.5" :style="{ color: kindHex, borderColor: kindHex + '55' }">
        {{ plan.kind_label }}
      </span>
      <span v-if="plan.stack.length" class="mono text-fg2">{{ plan.stack.join(' · ') }}</span>
      <button class="text-accent hover:underline ml-auto" @click="showPlan = !showPlan">
        {{ showPlan ? '收起' : '怎么录' }}
      </button>
    </div>

    <div v-if="plan && showPlan" class="inner p-2 space-y-2 text-[11px] leading-4">
      <div v-if="plan.evidence.length" class="text-fg2">
        <span v-for="(e, i) in plan.evidence" :key="i" class="block">· {{ e }}</span>
      </div>
      <div v-if="plan.serve" class="text-fg1">
        起服务 <code class="mono text-fg0">{{ plan.serve }}</code>
        <template v-if="plan.port">，访问 <span class="mono text-accent">http://localhost:{{ plan.port }}</span></template>
      </div>
      <ol class="space-y-1.5">
        <li v-for="(s, i) in plan.steps" :key="i">
          <div class="text-fg0 font-medium">{{ i + 1 }}. {{ s.title }}</div>
          <div class="text-fg2">{{ s.why }}</div>
          <div v-for="(c, j) in s.cmds" :key="j"
            class="mono text-[10px] text-fg1 bg-white border border-line rounded px-1.5 py-1 mt-1 flex items-start gap-1">
            <span class="flex-1 break-all">{{ c }}</span>
            <button v-if="!c.startsWith('（')" class="text-accent shrink-0 hover:underline" @click="copy(c)">复制</button>
          </div>
        </li>
      </ol>
      <div v-if="plan.note" class="text-warn">{{ plan.note }}</div>
    </div>

    <div v-if="!reachable" class="text-[11px] text-warn leading-4">
      宿主机代理没在跑，启动与录屏要靠它。到 <span class="mono">host-agent/</span> 双击
      <span class="mono">启动宿主机代理.command</span>，窗口留着别关。
    </div>
    <div v-else-if="!host?.ffmpeg" class="text-[11px] text-warn">
      宿主机上没找到 ffmpeg，录屏用不了：<span class="mono">brew install ffmpeg</span>
    </div>

    <div v-if="started" class="text-[11px] text-fg1 leading-4 space-y-0.5">
      <div>
        终端已开在 <span class="mono text-fg2">{{ started.tty }}</span>，
        <template v-if="started.auto.length">自动跑了 {{ started.auto.length }} 条装依赖命令</template>
        <template v-else>没有需要自动跑的装依赖命令</template>
        <template v-if="started.manual.length">，另有 {{ started.manual.length }} 条已放进历史，按 ↑ 依次调出</template>
      </div>
      <div v-if="urls.length" class="flex items-center gap-1.5 flex-wrap">
        <span class="dot bg-ok" />访问地址
        <a v-for="u in urls" :key="u" :href="u" target="_blank"
          class="mono hover:underline" :style="{ color: SIDE_HEX[side] }">{{ u }}</a>
      </div>
    </div>
  </div>
</template>
