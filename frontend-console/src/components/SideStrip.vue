<script setup lang="ts">
/** 两侧运行状态的横条。列表页靠它一眼看出 A、B 各跑到哪一步。 */
import { computed } from 'vue'
import { SIDES, type Side, type TaskRunBrief } from '../api'
import { fmtDuration, HEX, RUN_COLOR, RUN_LABEL, SIDE_HEX } from '../status'
import { nowMs } from '../store'

const props = defineProps<{ runs: TaskRunBrief[]; compact?: boolean }>()

const bySide = computed(() => {
  const m = {} as Partial<Record<Side, TaskRunBrief>>
  for (const r of props.runs) m[r.side] = r
  return m
})
const color = (r?: TaskRunBrief) => (r ? HEX[RUN_COLOR[r.status]] : HEX.fg2)
const live = (r?: TaskRunBrief) => r?.status === 'RUNNING'
/** 重跑过、或有网关报错的侧要点出来：这两种情况的结果不能直接拿去比 */
const flag = (r?: TaskRunBrief) => {
  if (!r) return ''
  if (r.abnormal?.gave_up) return '已放弃'
  if (r.gateway_errors?.length) return `网关 ${r.gateway_errors.join('/')}`
  if (r.attempt > 1) return `第 ${r.attempt} 次`
  return ''
}
</script>

<template>
  <div class="grid grid-cols-2 gap-2">
    <div v-for="s in SIDES" :key="s" class="inner px-2.5 py-2 min-w-0">
      <div class="flex items-center gap-1.5">
        <span class="mono text-[11px] font-semibold w-4 h-4 inline-flex items-center justify-center rounded"
          :style="{ color: SIDE_HEX[s], background: SIDE_HEX[s] + '1f' }">{{ s }}</span>
        <span class="dot shrink-0" :class="live(bySide[s]) ? 'animate-breathe' : ''"
          :style="{ background: color(bySide[s]) }" />
        <span class="text-[12px] truncate" :style="{ color: color(bySide[s]) }">
          {{ bySide[s] ? RUN_LABEL[bySide[s]!.status] : '未建' }}
        </span>
      </div>
      <div v-if="!compact" class="mono text-[11px] text-fg2 mt-1 flex items-center gap-1.5">
        <span class="nums">{{ fmtDuration(bySide[s]?.started_at, bySide[s]?.finished_at, nowMs) }}</span>
        <span v-if="bySide[s]?.artifact?.changed_files" class="nums">· 改 {{ bySide[s]!.artifact.changed_files }}</span>
        <span v-if="flag(bySide[s])" class="ml-auto text-warn truncate">{{ flag(bySide[s]) }}</span>
      </div>
    </div>
  </div>
</template>
