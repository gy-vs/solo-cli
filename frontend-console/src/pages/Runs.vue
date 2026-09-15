<script setup lang="ts">
import { NButton, useMessage } from 'naive-ui'
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, type TaskBrief } from '../api'
import RunCard from '../components/RunCard.vue'
import StatusPill from '../components/StatusPill.vue'
import { fmtDuration, fmtTime } from '../status'
import { liveTasks, nowMs, refreshTasks, store } from '../store'

const router = useRouter()
const msg = useMessage()
const active = computed(() => liveTasks.value.filter((t) => t.status === 'RUNNING' || t.status === 'QUEUED'))
const ended = computed(() => liveTasks.value
  .filter((t) => ['FINISHED', 'FAILED', 'TIMEOUT', 'INTERRUPTED', 'REVIEWED', 'UPLOADED'].includes(t.status))
  .sort((a, b) => (b.finished_at || '').localeCompare(a.finished_at || '')))
const uploadable = computed(() => ended.value.filter((t) => t.status === 'REVIEWED' && t.verify_overall !== 'block'))

const batching = ref(false)
async function uploadAll() {
  const ids = uploadable.value.map((t) => t.id)
  if (!ids.length) return
  if (!confirm(`将上传 ${ids.length} 道已评审的题到 solo-qa，继续？`)) return
  batching.value = true
  try {
    const r = await api.batchUpload(ids)
    const ok = r.results.filter((x) => x.ok).length
    ok === ids.length ? msg.success(`${ok} 题全部上传成功`) : msg.warning(`${ok} 题成功，${ids.length - ok} 题失败，详见各题上传页`)
    await refreshTasks()
  } catch (e: any) { msg.error(e.message) } finally { batching.value = false }
}
function stage(t: TaskBrief): { text: string; cls: string } {
  if (t.status === 'UPLOADED') return { text: `已上传 #${t.submission_id ?? ''}`, cls: 'text-info' }
  if (t.status === 'REVIEWED') return { text: t.verify_overall === 'warn' ? '已评审 · 有提醒' : '已评审 · 可上传', cls: 'text-ok' }
  if (t.analysis_status === 'RUNNING') return { text: 'Cursor 分析中', cls: 'text-run' }
  if (t.analysis_status === 'DONE') return { text: t.verify_overall === 'block' ? '核验有红项' : '待人工评审', cls: t.verify_overall === 'block' ? 'text-err' : 'text-warn' }
  if (t.analysis_status === 'FAILED') return { text: '分析失败', cls: 'text-err' }
  return { text: '待分析', cls: 'text-fg1' }
}
</script>

<template>
  <div class="page">
    <div class="flex items-center gap-3">
      <div>
        <div class="h1">运行舱</div>
        <div class="text-fg1 text-xs mt-0.5">每题一个容器，结束后在此进入分析、评审、上传，最后手动点「完成」销毁</div>
      </div>
      <div class="ml-auto inner px-3 h-8 flex items-center gap-2 text-xs">
        <span class="text-fg1">槽位</span>
        <span class="mono nums text-fg0">{{ store.status?.scheduler.running ?? 0 }} / {{ store.status?.scheduler.max_parallel ?? '-' }}</span>
      </div>
    </div>

    <div>
      <div class="flex items-center gap-3 mb-3"><div class="h2">进行中</div><span class="text-xs text-fg2">{{ active.length }}</span></div>
      <div v-if="active.length" class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        <RunCard v-for="t in active" :key="t.id" :task="t" @stop="refreshTasks" />
      </div>
      <div v-else class="card empty">没有运行中的容器 · 去题库领题</div>
    </div>

    <div class="card">
      <div class="px-4 pt-4 pb-2 flex items-center gap-3">
        <div class="h2">已结束</div>
        <span class="text-xs text-fg2">{{ ended.length }}</span>
        <NButton size="tiny" type="primary" secondary class="ml-auto" :disabled="!uploadable.length" :loading="batching" @click="uploadAll">
          批量上传（{{ uploadable.length }}）
        </NButton>
      </div>
      <div v-if="!ended.length" class="empty">暂无</div>
      <div v-for="t in ended" :key="t.id"
        class="px-4 py-3 border-t border-line grid grid-cols-[56px_120px_1fr_150px_90px_130px_auto] items-center gap-3 hover:bg-bg3/40 cursor-pointer"
        @click="router.push(`/tasks/${t.id}`)">
        <span class="mono text-xs text-fg0">#{{ t.task_no }}</span>
        <StatusPill :status="t.status" small />
        <div class="min-w-0">
          <div class="text-xs text-fg0 truncate">{{ t.question_type }} · {{ t.languages }}</div>
          <div class="text-[12px] truncate" :class="stage(t).cls">{{ stage(t).text }}</div>
        </div>
        <div class="mono text-[12px] text-fg1 nums">
          <div>{{ fmtDuration(t.started_at, t.finished_at, nowMs) }} · {{ t.protocol?.num_turns ?? '—' }} 轮</div>
          <div class="text-fg2">exit {{ t.exit_code ?? '—' }} · 改动 {{ t.artifact?.changed_files ?? '—' }}</div>
        </div>
        <div class="mono text-[12px] text-fg2 truncate" :title="t.session_id">{{ t.session_id ? t.session_id.slice(0, 8) : '无轨迹' }}</div>
        <div class="mono text-[12px] text-fg2 nums">{{ fmtTime(t.finished_at) }}</div>
        <span class="dot" :class="t.container_exists ? 'bg-run' : 'bg-fg2'" :title="t.container_exists ? '容器保留中' : '容器已销毁'" />
      </div>
    </div>
  </div>
</template>
