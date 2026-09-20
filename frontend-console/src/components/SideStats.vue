<script setup lang="ts">
/** 列表行里的 A、B 两侧用时与工具调用步数。
 *
 * 跑完的题要拿这两个数横着比：一侧三十步一侧三步，或者一侧跑了两小时另一侧十分钟，
 * 那份对比结论就得先当它可疑。所以这四个数要在列表上直接看到，不能等人点进详情页。
 */
import { computed } from 'vue'
import { SIDES, type Side, type TaskRunBrief } from '../api'
import { fmtDuration, HEX, RUN_COLOR, RUN_LABEL } from '../status'
import { nowMs } from '../store'

const props = defineProps<{ runs: TaskRunBrief[] }>()

const bySide = computed(() => {
  const m = {} as Partial<Record<Side, TaskRunBrief>>
  for (const r of props.runs) m[r.side] = r
  return m
})

/** 只有还在跑的时候才去读那个每秒跳的钟。
 *
 * 跑完的题时长是个定数，而读一下 nowMs 就等于订阅它，整张表会跟着每秒重画一遍 ——
 * 列表上二三十行、每行四个数，这一下就够卡。computed 的依赖是按次收集的，
 * 没有在跑的侧时这里根本不碰 nowMs，也就不会被它唤醒。
 */
const tick = computed(() => (props.runs.some((r) => !r.finished_at) ? nowMs.value : 0))

const color = (r?: TaskRunBrief) => (r ? HEX[RUN_COLOR[r.status]] : HEX.fg2)
const dur = (r?: TaskRunBrief) => (r?.started_at ? fmtDuration(r.started_at, r.finished_at, tick.value) : '—')
/** 工具调用步数。轨迹还没导出时 artifact 是空的，这时写「—」而不是 0：
 *  「一步没调」和「还不知道」是两回事，前者恰恰是要去看一眼的信号。 */
const steps = (r?: TaskRunBrief) => r?.artifact?.tool_calls
const hint = (s: Side) => {
  const r = bySide.value[s]
  if (!r) return `${s} 侧还没有运行记录`
  const errs = r.artifact?.tool_errors
  return `${s} 侧 ${RUN_LABEL[r.status]}：容器用时 ${dur(r)}，工具调用 ${steps(r) ?? '未知'} 步`
    + (errs ? `，其中 ${errs} 次报错` : '')
    + (r.attempt > 1 ? `（第 ${r.attempt} 次跑）` : '')
}
</script>

<template>
  <div class="space-y-0.5">
    <div v-for="s in SIDES" :key="s" class="flex items-center gap-1.5 mono text-[12px] leading-4"
      :title="hint(s)">
      <span class="text-[11px] font-semibold w-3 text-center shrink-0" :style="{ color: color(bySide[s]) }">{{ s }}</span>
      <span class="nums w-[52px] shrink-0" :style="{ color: color(bySide[s]) }">{{ dur(bySide[s]) }}</span>
      <span class="text-fg2">·</span>
      <span class="nums text-fg1 whitespace-nowrap">
        {{ steps(bySide[s]) ?? '—' }} <span class="text-fg2">步</span>
      </span>
    </div>
  </div>
</template>
