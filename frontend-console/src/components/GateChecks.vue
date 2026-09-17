<script setup lang="ts">
import { NButton, useDialog, useMessage } from 'naive-ui'
import { ref } from 'vue'
import { api, type GateReport, type TaskBrief } from '../api'
import { LEVEL_HEX } from '../status'

const props = defineProps<{ task: TaskBrief | null; report: GateReport | null; checking?: boolean }>()
const emit = defineEmits<{ (e: 'recheck'): void }>()
const msg = useMessage()
const dialog = useDialog()
const busy = ref('')

const FIX_LABEL: Record<string, string> = {
  reset_snapshot: '重置到初始快照',
  archive_traces: '归档现有轨迹',
  remove_container: '删除残留容器',
  switch_branch: '切到题目分支',
}
const color = (l: string) => LEVEL_HEX[l] || LEVEL_HEX.block

async function run(action: string) {
  if (!props.task) return
  busy.value = action
  try {
    const r = await api.fix(props.task.id, action)
    r.ok ? msg.success(r.message || '已处理') : msg.error(r.message)
    emit('recheck')
  } catch (e: any) { msg.error(e.message) } finally { busy.value = '' }
}
function fix(action: string) {
  if (action !== 'reset_snapshot') return run(action)
  dialog.warning({
    title: '重置到初始快照',
    content: '在题目分支上执行 git reset --hard 与 git clean -fdx，清空工作目录里所有未提交改动与被忽略的文件。'
      + '分支上已有的交付提交会先备份到 refs/solo-backup/*，之后能用 git log 找回。',
    positiveText: '确认重置',
    negativeText: '取消',
    onPositiveClick: () => run(action),
  })
}
</script>

<template>
  <div v-if="report" class="space-y-2">
    <div class="flex items-center gap-3">
      <span class="pill" :style="{ color: color(report.passed ? 'ok' : 'block'), borderColor: color(report.passed ? 'ok' : 'block') + '55' }">
        {{ report.passed ? '全部通过' : `${report.blocked} 项阻断` }}
      </span>
      <span v-if="report.warnings" class="text-xs text-warn">{{ report.warnings }} 项提醒</span>
      <NButton size="tiny" tertiary class="ml-auto" :loading="checking" @click="emit('recheck')">重新检查</NButton>
    </div>
    <div v-for="c in report.checks" :key="c.name" class="inner p-3 flex items-start gap-3 animate-slidein">
      <span class="dot mt-1.5 shrink-0" :style="{ background: color(c.level) }" />
      <div class="min-w-0 flex-1">
        <div class="mono text-[12px] text-fg2">{{ c.name }}</div>
        <div class="text-fg0 text-xs break-all">{{ c.message }}</div>
      </div>
      <NButton v-if="c.fix" size="tiny" secondary :type="c.fix === 'reset_snapshot' ? 'warning' : 'default'"
        :loading="busy === c.fix" @click="fix(c.fix)">{{ FIX_LABEL[c.fix] || c.fix }}</NButton>
    </div>
  </div>
  <div v-else-if="checking" class="empty">检查中…</div>
  <div v-else class="empty">尚未检查</div>
</template>
