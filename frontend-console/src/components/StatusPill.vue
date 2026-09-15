<script setup lang="ts">
import { computed } from 'vue'
import type { Status } from '../api'
import { HEX, STATUS_COLOR, STATUS_LABEL } from '../status'

const props = defineProps<{ status: Status; small?: boolean }>()
const color = computed(() => HEX[STATUS_COLOR[props.status]] || HEX.fg1)
const live = computed(() => props.status === 'RUNNING' || props.status === 'QUEUED')
</script>

<template>
  <span class="pill" :class="small ? 'h-5 text-[12px]' : ''"
    :style="{ color, borderColor: color + '55', background: color + '14' }">
    <span class="dot" :class="live ? 'animate-breathe' : ''" :style="{ background: color }" />
    {{ STATUS_LABEL[status] }}
  </span>
</template>
