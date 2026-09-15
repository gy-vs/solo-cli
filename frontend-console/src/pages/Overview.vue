<script setup lang="ts">
import { NButton, useMessage } from 'naive-ui'
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import Metric from '../components/Metric.vue'
import RunCard from '../components/RunCard.vue'
import StatusPill from '../components/StatusPill.vue'
import { fmtTime, HEX, QC_LABEL, STAGE_LABEL, STATUS_COLOR, STATUS_LABEL } from '../status'
import { liveTasks, refreshStatus, refreshTasks, store } from '../store'
import type { Status } from '../api'

const router = useRouter()
const msg = useMessage()
const s = computed(() => store.status)
const counts = computed(() => s.value?.counts)
const running = computed(() => liveTasks.value.filter((t) => t.status === 'RUNNING' || t.status === 'QUEUED'))
const attention = computed(() => liveTasks.value.filter((t) =>
  ['FINISHED', 'FAILED', 'TIMEOUT', 'INTERRUPTED', 'REVIEWED'].includes(t.status)))
const recent = computed(() => [...liveTasks.value]
  .filter((t) => t.status !== 'AVAILABLE')
  .sort((a, b) => (b.finished_at || b.started_at || '').localeCompare(a.finished_at || a.started_at || ''))
  .slice(0, 8))

const importing = ref(false)
async function doImport() {
  importing.value = true
  try {
    const r = await api.importBank()
    msg.success(`解析 ${r.parsed} 题，新增 ${r.added.length} 题${r.added.length ? '：' + r.added.join(', ') : ''}`)
    await Promise.all([refreshTasks(), refreshStatus()])
  } catch (e: any) { msg.error(e.message) } finally { importing.value = false }
}
const pipeline: Status[] = ['AVAILABLE', 'QUEUED', 'RUNNING', 'FINISHED', 'REVIEWED', 'UPLOADED', 'DONE']
</script>

<template>
  <div class="page">
    <div class="flex items-center gap-3">
      <div>
        <div class="h1">总览</div>
        <div class="text-fg1 text-xs mt-0.5">设计题目 → 题库 → 排队运行 → 自动销毁容器 → 自动分析 → 自动质检 → 上传</div>
      </div>
      <div class="ml-auto flex gap-2">
        <NButton size="small" secondary :loading="importing" @click="doImport">重新扫描 prompt.md</NButton>
        <NButton size="small" secondary @click="router.push('/design')">设计题目</NButton>
        <NButton size="small" type="primary" @click="router.push('/bank')">去题库领题</NButton>
      </div>
    </div>

    <div class="grid grid-cols-2 lg:grid-cols-4 xl:grid-cols-6 gap-4">
      <Metric label="待领取" :value="counts?.AVAILABLE ?? '—'" />
      <Metric label="运行 / 槽位" :value="`${s?.scheduler.running ?? 0}/${s?.scheduler.max_parallel ?? '-'}`" :tone="HEX.run" />
      <Metric label="待处理" :value="attention.length" :tone="HEX.ok" sub="运行结束、待评审或待上传" />
      <Metric label="今日上传" :value="s?.totals.uploaded ?? '—'" :tone="HEX.info" :sub="s?.totals.date" />
      <Metric label="异常" :value="(counts?.FAILED ?? 0) + (counts?.TIMEOUT ?? 0) + (counts?.INTERRUPTED ?? 0)" :tone="HEX.err" />
      <Metric label="已完成" :value="counts?.DONE ?? '—'" :tone="HEX.fg2"
        :sub="counts?.DISCARDED ? `另有 ${counts.DISCARDED} 题已废弃` : ''" />
    </div>

    <div class="grid grid-cols-1 xl:grid-cols-3 gap-4">
      <div class="card p-4 xl:col-span-2">
        <div class="flex items-center gap-3 mb-3">
          <div class="h2">流水线</div>
          <span class="text-xs text-fg2">各阶段题数</span>
        </div>
        <div class="flex items-stretch gap-1">
          <div v-for="(st, i) in pipeline" :key="st" class="flex-1 flex items-center gap-1 min-w-0">
            <div class="inner flex-1 p-3 min-w-0">
              <div class="text-[12px] text-fg1 truncate">{{ STATUS_LABEL[st] }}</div>
              <div class="mono nums text-xl font-semibold" :style="{ color: HEX[STATUS_COLOR[st]] }">{{ counts?.[st] ?? 0 }}</div>
            </div>
            <span v-if="i < pipeline.length - 1" class="text-fg2 text-xs shrink-0">›</span>
          </div>
        </div>
      </div>
      <div class="card p-4 space-y-3">
        <div class="flex items-center gap-2">
          <div class="h2">环境</div>
          <span v-if="s?.scheduler.paused" class="pill h-5 text-[12px] text-warn border-warn/50 ml-auto">出队已暂停</span>
        </div>
        <div class="inner px-3 py-2 space-y-1.5">
          <div class="flex items-center gap-2 text-xs">
            <span class="text-fg1">自动流水线</span>
            <span class="ml-auto flex gap-1.5">
              <span class="text-[12px]" :class="s?.pipeline.destroy ? 'text-ok' : 'text-fg2'">销毁</span>
              <span class="text-[12px]" :class="s?.pipeline.analyze ? 'text-ok' : 'text-fg2'">分析</span>
              <span class="text-[12px]" :class="s?.pipeline.qc ? 'text-ok' : 'text-fg2'">质检</span>
            </span>
          </div>
          <div class="flex items-center gap-2 text-xs">
            <span class="dot" :class="s?.qc.ok ? 'bg-ok' : 'bg-err'" />
            <span class="text-fg1">质检通道</span>
            <span class="ml-auto mono text-[12px] text-fg2 truncate max-w-[180px]" :title="s?.qc.message">{{ s?.qc.message || '—' }}</span>
          </div>
        </div>
        <div class="space-y-2 text-xs">
          <div class="flex items-center gap-2"><span class="dot" :class="s?.docker.ok ? 'bg-ok' : 'bg-err'" /><span class="text-fg1">Docker</span><span class="ml-auto mono text-fg0">{{ s?.docker.message || '—' }}</span></div>
          <div class="flex items-center gap-2"><span class="dot" :class="s?.image.present ? 'bg-ok' : 'bg-err'" /><span class="text-fg1">镜像</span><span class="ml-auto mono text-fg0 truncate max-w-[220px]" :title="s?.image.name">{{ s?.image.name?.split('/').pop() || '—' }}</span></div>
          <div class="flex items-center gap-2"><span class="dot" :class="s?.paths.prompt_exists ? 'bg-ok' : 'bg-err'" /><span class="text-fg1">prompt.md</span><span class="ml-auto mono text-fg0 truncate max-w-[220px]" :title="s?.paths.prompt_file">{{ s?.paths.coder_root_host || '—' }}</span></div>
          <div class="flex items-center gap-2"><span class="dot" :class="s?.configured['cc.api_key'] ? 'bg-ok' : 'bg-err'" /><span class="text-fg1">网关 Key</span><span class="ml-auto mono text-fg2">{{ s?.configured['cc.api_key'] ? '已配置' : '未配置' }}</span></div>
          <div class="flex items-center gap-2"><span class="dot" :class="s?.configured['qa.session_cookie'] && s?.configured['qa.csrf_token'] ? 'bg-ok' : 'bg-err'" /><span class="text-fg1">solo-qa 身份</span><span class="ml-auto mono text-fg2">{{ s?.configured['qa.session_cookie'] ? '已配置' : '未配置' }}</span></div>
          <div class="flex items-center gap-2"><span class="dot" :class="s?.configured['cursor.api_key'] ? 'bg-ok' : 'bg-err'" /><span class="text-fg1">Cursor Key</span><span class="ml-auto mono text-fg2">{{ s?.configured['cursor.api_key'] ? '已配置' : '未配置' }}</span></div>
        </div>
        <div v-if="s?.containers.length" class="pt-2 border-t border-line">
          <div class="label mb-1">残留容器 {{ s.containers.length }}</div>
          <div v-for="c in s.containers" :key="c.name" class="mono text-[12px] text-fg1 flex gap-2"><span>{{ c.name }}</span><span class="text-fg2 truncate">{{ c.status }}</span></div>
        </div>
        <NButton size="tiny" tertiary class="w-full" @click="router.push('/settings')">前往设置</NButton>
      </div>
    </div>

    <div>
      <div class="flex items-center gap-3 mb-3">
        <div class="h2">运行舱</div>
        <span class="text-xs text-fg2">{{ running.length }} 个进行中</span>
        <NButton size="tiny" tertiary class="ml-auto" @click="router.push('/runs')">全部</NButton>
      </div>
      <div v-if="running.length" class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        <RunCard v-for="t in running" :key="t.id" :task="t" />
      </div>
      <div v-else class="card empty">没有正在运行的题</div>
    </div>

    <div class="card">
      <div class="px-4 pt-4 pb-2 flex items-center gap-3"><div class="h2">最近活动</div></div>
      <div v-if="!recent.length" class="empty">暂无</div>
      <div v-for="t in recent" :key="t.id" class="px-4 py-2.5 border-t border-line flex items-center gap-3 hover:bg-bg3/40 cursor-pointer" @click="router.push(`/tasks/${t.id}`)">
        <span class="mono text-xs text-fg0 w-10">#{{ t.task_no }}</span>
        <StatusPill :status="t.status" small />
        <span class="text-xs text-fg1 truncate flex-1">{{ t.question_type }} · {{ t.languages }}</span>
        <span v-if="t.auto_stage && t.auto_stage !== 'done'" class="text-[12px] text-run">{{ STAGE_LABEL[t.auto_stage] }}</span>
        <span v-else-if="t.analysis_status === 'RUNNING'" class="text-[12px] text-run">分析中</span>
        <span v-if="t.qc_conclusion" class="text-[12px]" :class="t.qc_conclusion === 'PASS' ? 'text-ok' : 'text-err'">{{ QC_LABEL[t.qc_conclusion] }}</span>
        <span v-else-if="t.verify_overall" class="text-[12px]" :class="t.verify_overall === 'block' ? 'text-err' : t.verify_overall === 'warn' ? 'text-warn' : 'text-ok'">核验 {{ t.verify_overall }}</span>
        <span class="mono text-[12px] text-fg2 nums">{{ fmtTime(t.finished_at || t.started_at || t.claimed_at) }}</span>
      </div>
    </div>
  </div>
</template>
