<script setup lang="ts">
import { NButton } from 'naive-ui'
import type { TaskBrief } from '../api'
import StatusPill from './StatusPill.vue'
import { fmtTime, HEX } from '../status'

const props = defineProps<{ task: TaskBrief; busy?: boolean }>()
const emit = defineEmits<{
  (e: 'claim'): void; (e: 'release'): void; (e: 'open'): void
  (e: 'discard'): void; (e: 'restore'): void; (e: 'reset'): void
}>()
const diffColor = (d: string) => (d.includes('困难') ? HEX.warn : d.includes('中') ? HEX.run : HEX.fg1)
const claimable = () => props.task.status === 'AVAILABLE' || props.task.status === 'CLAIMED'
const discardable = () => !['RUNNING', 'QUEUED', 'DISCARDED'].includes(props.task.status)
// 跑过或动过的题才需要还原；从没碰过的待领取题没什么可退的
const resettable = () => !['AVAILABLE', 'RUNNING', 'QUEUED'].includes(props.task.status)
</script>

<template>
  <div class="card card-hover p-4 flex flex-col gap-3" :class="task.status === 'DISCARDED' ? 'opacity-70' : ''">
    <div class="flex items-start justify-between gap-2">
      <span class="mono text-xs px-2 h-6 inline-flex items-center rounded-md bg-bg3 text-fg0 border border-line">#{{ task.task_no }}</span>
      <div class="flex items-center gap-2">
        <span class="pill h-6 text-[12px]" :style="{ color: diffColor(task.difficulty), borderColor: diffColor(task.difficulty) + '66' }">{{ task.difficulty || '未标难度' }}</span>
        <StatusPill v-if="task.status !== 'AVAILABLE'" :status="task.status" small />
      </div>
    </div>
    <div>
      <div class="text-fg0 font-medium">{{ task.question_type || '未标任务类型' }} <span class="text-fg2">·</span> <span class="text-fg1">{{ task.languages || '—' }}</span></div>
      <p class="text-fg1 text-xs mt-1 line-clamp-2 leading-5">{{ task.prompt_preview }}</p>
    </div>
    <div class="flex items-center gap-3 text-[12px] text-fg2 mono">
      <span>{{ task.prompt_chars }} 字</span>
      <span>·</span>
      <span class="truncate" :title="task.env_snapshot">{{ task.env_snapshot.split('/commit/')[1]?.slice(0, 12) || '无快照 SHA' }}</span>
      <span class="ml-auto">{{ task.harness }} {{ task.harness_version }}</span>
    </div>
    <div v-if="task.status === 'DISCARDED'" class="text-[12px] text-fg2">
      废弃于 {{ fmtTime(task.discarded_at) }}<span v-if="task.discarded_from">，废弃前为 {{ task.discarded_from }}</span>
      <div v-if="task.dedup_verdict === 'discard'" class="text-err mt-0.5 line-clamp-2" :title="task.dedup_reason">
        查重命中：{{ task.dedup_reason }}
      </div>
    </div>
    <div v-else-if="task.origin === 'designed'" class="text-[12px] flex items-center gap-1.5"
      :class="task.dedup_verdict === 'pass' ? 'text-ok' : 'text-warn'">
      <span class="dot" :class="task.dedup_verdict === 'pass' ? 'bg-ok' : 'bg-warn'" />
      {{ task.dedup_verdict === 'pass' ? '设计产出 · 查重通过' : `设计产出 · ${task.dedup_reason || '未查重'}` }}
    </div>
    <div class="flex gap-2 mt-auto">
      <NButton v-if="claimable()" size="small" type="primary" class="flex-1" :loading="busy" @click="emit('claim')">领取并启动</NButton>
      <NButton v-if="task.status === 'DISCARDED'" size="small" type="primary" secondary class="flex-1" :loading="busy" @click="emit('restore')">恢复</NButton>
      <NButton v-if="task.status === 'CLAIMED' || task.status === 'QUEUED'" size="small" tertiary @click="emit('release')">放回</NButton>
      <NButton size="small" tertiary @click="emit('open')">详情</NButton>
      <NButton v-if="resettable()" size="small" quaternary :loading="busy" title="工作区、轨迹、回填、评审记录全部退回做题前"
        @click="emit('reset')">还原</NButton>
      <NButton v-if="discardable()" size="small" quaternary type="error" :loading="busy" @click="emit('discard')">废弃</NButton>
    </div>
  </div>
</template>
