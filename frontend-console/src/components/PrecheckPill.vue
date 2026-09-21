<script setup lang="ts">
/** 提交前质检的一枚状态标。列表和详情页共用，免得两处各写一套口径。 */
import { computed } from 'vue'
import type { PrecheckStatus } from '../api'
import { HEX, PRECHECK_COLOR, PRECHECK_LABEL } from '../status'

const props = defineProps<{
  status: PrecheckStatus
  issues?: number
  /** 质检之后理由又改过：结论还在，但已经不代表现在这一稿 */
  stale?: boolean
  small?: boolean
}>()

// 认不出来的取值当成「待质检」：库里升级前的行拿到的是空串，直接显出来就是一枚
// 没有文字的空标，人分不清是没质检过还是界面坏了
const key = computed<PrecheckStatus>(() => (PRECHECK_LABEL[props.status] ? props.status : 'IDLE'))
const color = computed(() => HEX[PRECHECK_COLOR[key.value]] || HEX.fg1)
const text = computed(() => {
  const base = PRECHECK_LABEL[key.value]
  return props.issues ? `${base} ${props.issues} 处` : base
})
</script>

<template>
  <span class="inline-flex items-center gap-1.5">
    <span class="pill" :class="small ? 'h-5 text-[12px]' : ''"
      :style="{ color, borderColor: color + '55', background: color + '14' }">
      <span class="dot" :class="key === 'RUNNING' ? 'animate-breathe' : ''" :style="{ background: color }" />
      {{ text }}
    </span>
    <!-- 结论过期单独标出来，不混进状态文字里：那是两件事，一件是质检怎么判的，
         另一件是这个判断还算不算数 -->
    <span v-if="stale" class="mono text-[11px] text-warn" title="质检之后理由又改过，这份结论已经过期">
      已过期
    </span>
  </span>
</template>
