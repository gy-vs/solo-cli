<script setup lang="ts">
import { NButton, useMessage } from 'naive-ui'
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, SIDES, type Side, type TaskBrief } from '../api'
import RunCard from '../components/RunCard.vue'
import StatusPill from '../components/StatusPill.vue'
import { fmtDuration, fmtTime, RUN_END, SIDE_HEX, VERDICT_LABEL } from '../status'
import { liveTasks, refreshTasks, store } from '../store'

const router = useRouter()
const msg = useMessage()
const active = computed(() => liveTasks.value.filter((t) => t.status === 'RUNNING' || t.status === 'QUEUED'))
const ended = computed(() => liveTasks.value
  .filter((t) => ['RUN_DONE', 'ANALYZING', 'ANALYZED', 'UPLOADED', 'NEEDS_ATTENTION'].includes(t.status))
  .sort((a, b) => (b.finished_at || '').localeCompare(a.finished_at || '')))
const uploadable = computed(() => ended.value.filter((t) => t.status === 'ANALYZED'
  && t.verify_overall !== 'block' && SIDES.every((s) => t.screencast?.[s])))

const batching = ref(false)
async function uploadAll() {
  const ids = uploadable.value.map((t) => t.id)
  if (!ids.length) return
  if (!confirm(`将上传 ${ids.length} 道题的 GSB 结论，继续？`)) return
  batching.value = true
  try {
    const r = await api.batchUpload(ids)
    const ok = r.results.filter((x) => x.ok).length
    ok === ids.length ? msg.success(`${ok} 题全部上传成功`) : msg.warning(`${ok} 题成功，${ids.length - ok} 题失败，详见各题上传页`)
    await refreshTasks()
  } catch (e: any) { msg.error(e.message) } finally { batching.value = false }
}
/** 列表右侧那行小字：这题现在到底卡在哪 */
function stage(t: TaskBrief): { text: string; cls: string } {
  // 转人工的原因不止「重跑用尽」一种（推产物失败、分析失败都会到这儿），
  // 写死一句会把人往错的方向引，有 auto_error 就直接把它显出来
  if (t.status === 'NEEDS_ATTENTION') return { text: t.auto_error || '需人工介入', cls: 'text-err' }
  if (t.status === 'UPLOADED') return { text: `已上传 #${t.submission_id ?? ''}`, cls: 'text-info' }
  if (t.status === 'ANALYZED') {
    const missing = SIDES.filter((s) => !t.screencast?.[s])
    if (missing.length) return { text: `等 ${missing.join('、')} 侧录屏`, cls: 'text-warn' }
    if (t.verify_overall === 'block') return { text: '自检有红项', cls: 'text-err' }
    return { text: `${VERDICT_LABEL[t.gsb_verdict as 'A'] || '结论已出'} · 可上传`, cls: 'text-ok' }
  }
  if (t.analysis_status === 'RUNNING') return { text: '对比分析中', cls: 'text-run' }
  if (t.analysis_status === 'FAILED') return { text: '分析失败', cls: 'text-err' }
  return { text: '待提交产物与分析', cls: 'text-fg1' }
}
const doneRuns = (t: TaskBrief) => t.runs.filter((r) => RUN_END.includes(r.status)).length
const containers = (t: TaskBrief) => t.runs.filter((r) => r.container_exists).length
const changed = (t: TaskBrief, s: Side) => t.runs.find((r) => r.side === s)?.artifact?.changed_files ?? '—'

/** 哪几侧需要重跑：结束状态不是 FINISHED，或者看护判过异常 */
function badSides(t: TaskBrief): Side[] {
  return SIDES.filter((s) => {
    const r = t.runs.find((x) => x.side === s)
    if (!r || !RUN_END.includes(r.status)) return false
    return r.status !== 'FINISHED' || !!r.abnormal?.reason
  })
}

const rerunning = ref('')
/** 列表里直接重跑某一侧。整侧推倒重来，所以要问一句 */
async function rerunSide(t: TaskBrief, s: Side) {
  if (!confirm(`重跑 #${t.task_no} 的 ${s} 侧？\n\n会销毁该侧容器、把工作目录重置回初始快照、归档已有轨迹，然后重新排队跑一遍。`)) return
  rerunning.value = `${t.id}${s}`
  try {
    await api.rerun(t.id, [s])
    msg.success(`#${t.task_no} ${s} 侧已排队重跑`)
    await refreshTasks()
  } catch (e: any) { msg.error(e.message) } finally { rerunning.value = '' }
}
</script>

<template>
  <div class="page">
    <div class="flex items-center gap-3">
      <div>
        <div class="h1">运行舱</div>
        <div class="text-fg1 text-xs mt-0.5">一题两个容器，A、B 同时跑；两侧跑完自动对比，出结论后补录屏链接再上传</div>
      </div>
      <div class="ml-auto inner px-3 h-8 flex items-center gap-2 text-xs">
        <span class="text-fg1">容器槽位</span>
        <span class="mono nums text-fg0">{{ store.status?.scheduler.running ?? 0 }} / {{ store.status?.scheduler.max_parallel ?? '-' }}</span>
      </div>
    </div>

    <div>
      <div class="flex items-center gap-3 mb-3">
        <div class="h2">进行中</div><span class="text-xs text-fg2">{{ active.length }} 题 · {{ store.status?.running_sides ?? 0 }} 侧在跑</span>
      </div>
      <div v-if="active.length" class="grid grid-cols-1 xl:grid-cols-2 gap-4">
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
        class="px-4 py-3 border-t border-line grid grid-cols-[56px_120px_1fr_130px_120px_130px_auto] items-center gap-3 hover:bg-bg3/40 cursor-pointer"
        @click="router.push(`/tasks/${t.id}`)">
        <span class="mono text-xs text-fg0">#{{ t.task_no }}</span>
        <StatusPill :status="t.status" small />
        <div class="min-w-0">
          <div class="text-xs text-fg0 truncate">{{ t.question_type }} · {{ t.languages }}</div>
          <div class="text-[12px] truncate" :class="stage(t).cls">{{ stage(t).text }}</div>
        </div>
        <div class="mono text-[12px] text-fg1 nums">
          <!-- 这些题都跑完了，时长是个定数。这里不读那个每秒跳的钟，否则整张表跟着每秒重画 -->
          <div>{{ fmtDuration(t.claimed_at, t.finished_at) }} · {{ doneRuns(t) }}/2 侧</div>
          <div class="text-fg2">改动 A {{ changed(t, 'A') }} · B {{ changed(t, 'B') }}</div>
        </div>
        <div class="flex items-center gap-1.5 mono text-[12px]">
          <span v-if="t.gsb_verdict" class="pill h-5 text-[12px]"
            :style="{ color: SIDE_HEX[t.gsb_verdict as Side] || '#475569', borderColor: (SIDE_HEX[t.gsb_verdict as Side] || '#475569') + '55' }">
            {{ VERDICT_LABEL[t.gsb_verdict] }}
          </span>
          <span v-else class="text-fg2">无结论</span>
        </div>
        <div class="mono text-[12px] text-fg2 nums">{{ fmtTime(t.finished_at) }}</div>
        <div class="flex items-center gap-2">
          <NButton v-for="s in badSides(t)" :key="s" size="tiny" quaternary
            :loading="rerunning === `${t.id}${s}`" @click.stop="rerunSide(t, s)">
            重跑 {{ s }}
          </NButton>
          <span class="mono text-[12px] text-fg2" :title="`${containers(t)} 个容器保留中`">
            <span class="dot mr-1" :class="containers(t) ? 'bg-run' : 'bg-fg2'" />{{ containers(t) }}/2
          </span>
        </div>
      </div>
    </div>
  </div>
</template>
