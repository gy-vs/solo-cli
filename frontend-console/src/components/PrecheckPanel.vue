<script setup lang="ts">
/** 提交前质检的结果。挑出来的每一处都给原句和改法，人照着改完点确认才能提交。
 *
 * 三件事：发起质检、把模型挑出的问题摊开、让人拍板放行。发起会真的花一次模型调用，
 * 所以已经有有效结论、理由又没改过的题，按钮是灰的。
 */
import { NButton, NInput, useDialog, useMessage } from 'naive-ui'
import { computed, ref } from 'vue'
import { api, type PrecheckReport, type PrecheckStatus, type TaskDetail } from '../api'
import { fmtTime, HEX } from '../status'
import PrecheckPill from './PrecheckPill.vue'

const props = defineProps<{
  task: TaskDetail
  report: PrecheckReport | Record<string, never>
  /** 理由编辑框里有没有未保存的改动。有的话先让人存，确认的得是落库那一稿 */
  dirty?: boolean
  readonly?: boolean
}>()
const emit = defineEmits<{
  (e: 'confirmed'): void
  /** 质检刚跑完，报告变了，让详情页重新拉一次 */
  (e: 'ran'): void
  /** 把整段改写稿填进理由编辑框，存不存由人决定 */
  (e: 'apply', text: string): void
}>()

const msg = useMessage()
const dialog = useDialog()
const busy = ref(false)
const running = ref(false)
const note = ref('')

const r = computed(() => props.report as PrecheckReport)
const issues = computed(() => r.value.issues || [])
const status = computed(() => props.task.precheck_status as PrecheckStatus)
const hasReport = computed(() => status.value !== 'IDLE' && !!Object.keys(props.report || {}).length)
/** 跑过质检、且此刻确实被挡着，才需要人拍板。已经放行又没过期的题按这个按钮什么都不变。 */
const canConfirm = computed(() => !props.readonly && !props.dirty
  && !['IDLE', 'RUNNING'].includes(status.value) && !!props.task.precheck_block)

/** 再跑一次值不值一次模型调用。理由一个字没改就再问一遍，答案一样，钱白花 —— 判了
 *  待改的也一样，得先按意见改完。没跑成（ERROR）不在此列，重跑正是该做的事。
 *  编辑框里有没存的改动也不让跑：跑的得是落库那一稿，不然指纹一对就是「已过期」。 */
const canRun = computed(() => !props.readonly && !props.dirty && status.value !== 'RUNNING'
  && (props.task.precheck_stale || !['PASS', 'CONFIRMED', 'FAIL'].includes(status.value)))

const runHint = computed(() => {
  if (props.dirty) return '先保存理由，质检的得是落库那一稿'
  if (status.value === 'RUNNING') return '这道题的质检正在跑'
  if (status.value === 'FAIL') return '先按上面的意见改理由，改完这里才值得再跑一次'
  if (!canRun.value) return '已经有有效结论，理由没再改过，再跑一次答案一样'
  return '花一次模型调用，约一分半'
})

async function run() {
  running.value = true
  try {
    const res = await api.precheck(props.task.id)
    msg.success(res.message)
    emit('ran')
  } catch (e: any) { msg.error(e.message) } finally { running.value = false }
}

function confirm() {
  dialog.info({
    title: '确认放行这道题的质检',
    content: status.value === 'FAIL'
      ? '确认后这道题可以提交，质检挑出的问题按已处理记账。'
        + '模型挑出来的十条里总有两三条是它自己读偏了，你看一眼直接放行是正常操作，'
        + '但确认之后再改理由，结论会重新变成「已过期」。'
      : '确认后这道题可以提交。之后再改理由，结论会重新变成「已过期」，要再确认一次。',
    positiveText: '确认放行',
    negativeText: '取消',
    onPositiveClick: async () => {
      busy.value = true
      try {
        const res = await api.confirmPrecheck(props.task.id, note.value)
        msg.success(res.message)
        note.value = ''
        emit('confirmed')
      } catch (e: any) { msg.error(e.message) } finally { busy.value = false }
    },
  })
}
</script>

<template>
  <div class="card p-4 space-y-3">
    <div class="flex items-center gap-3 flex-wrap">
      <div class="h2">提交前质检</div>
      <PrecheckPill :status="status" :issues="task.precheck_issues" :stale="task.precheck_stale" />
      <span v-if="r.model" class="mono text-[12px] text-fg2">{{ r.model }}</span>
      <span v-if="r.duration_s" class="mono text-[12px] text-fg2 nums">{{ r.duration_s }}s</span>
      <span class="mono text-[12px] text-fg2 nums ml-auto">{{ fmtTime(r.confirmed_at || r.finished_at) }}</span>
      <NButton size="tiny" :type="canRun ? 'primary' : 'default'" :secondary="canRun" :tertiary="!canRun"
        :disabled="!canRun" :loading="running" :title="runHint" @click="run">
        {{ hasReport ? '重跑质检' : '跑质检' }}
      </NButton>
    </div>

    <!-- 还没跑过：说清这一步在判什么、要花什么，人才知道这个按钮该不该点 -->
    <div v-if="!hasReport" class="inner p-3 text-xs text-fg1 leading-6">
      这道题还没做提交前质检。质检看的是理由读起来像不像一个人写的——那类毛病正则查不出来，
      得让模型逐句读一遍，所以要花一次模型调用，一道一分半左右。
      <div class="mt-1.5 text-fg2">
        录屏之前跑最划算：措辞要改的话这时候改还来得及，录完再改就得重录。
        整批发起去「题目列表 · 待录屏」勾选，或者在对话里
        <span class="mono text-accent break-all">app.cli precheck {{ task.task_no }}</span>。
      </div>
    </div>

    <template v-else>
      <div v-if="r.summary" class="text-xs leading-6"
        :style="{ color: r.passed ? HEX.ok : HEX.fg0 }">{{ r.summary }}</div>
      <div v-if="r.error" class="inner p-3 text-xs text-err leading-6">
        质检没跑完：{{ r.error }}。重跑一次就行，这不是理由本身的问题。
      </div>

      <div v-if="issues.length" class="space-y-2">
        <div v-for="(it, i) in issues" :key="i" class="inner p-3 space-y-1.5">
          <div class="flex items-start gap-2">
            <!-- 类别标签不能被旁边那句说明挤到折行：四个字的标签折成两行会把整块行高顶开 -->
            <span class="pill h-5 text-[12px] text-warn border-warn/40 shrink-0 whitespace-nowrap">
              {{ it.kind }}
            </span>
            <span class="text-[12px] text-fg1 leading-5 min-w-0">{{ it.why }}</span>
          </div>
          <!-- 原句逐字照抄自正文，能直接拿去编辑框里搜 -->
          <div class="text-xs text-fg0 leading-6 bg-warn/5 border-l-2 border-warn/50 pl-2.5 py-1 break-all">
            {{ it.quote }}
          </div>
          <div v-if="it.suggest" class="text-xs text-ok leading-6 border-l-2 border-ok/50 pl-2.5 py-1 break-all">
            改成：{{ it.suggest }}
          </div>
        </div>
      </div>
      <div v-else-if="r.passed" class="text-xs text-ok">整段读下来没有机械化的地方，可以提交。</div>

      <!-- 整段改写稿。后端已经量过字数、也确认它不会引入核验红项，但要不要用还是人定 -->
      <div v-if="r.rewrite" class="space-y-2 pt-1 border-t border-line">
        <div class="flex items-center gap-3">
          <div class="label">整段改写建议</div>
          <span class="mono text-[12px] text-fg2">只改被点出来的那几句，其余原样</span>
          <NButton size="tiny" type="primary" secondary class="ml-auto" :disabled="readonly"
            @click="emit('apply', r.rewrite!)">
            填进理由
          </NButton>
        </div>
        <pre class="text-xs text-fg0 whitespace-pre-wrap inner p-3 leading-6 max-h-72 overflow-auto">{{ r.rewrite }}</pre>
        <div class="text-[12px] text-fg2">填进去只是改了编辑框，还要点上面的「保存结论并自检」才落库。</div>
      </div>
      <div v-else-if="r.rewrite_dropped" class="text-[12px] text-fg2">
        模型给的整段改写稿被丢掉了（{{ r.rewrite_dropped }}），照上面的逐条改法自己改。
      </div>

      <!-- 放行 -->
      <div v-if="!readonly" class="pt-2 border-t border-line space-y-2">
        <div class="flex items-center gap-3">
          <div class="label">人工确认</div>
          <span class="text-[12px] text-fg2">
            {{ task.precheck_block || '这道题已经放行，可以提交' }}
          </span>
        </div>
        <div class="flex items-start gap-2">
          <NInput v-model:value="note" size="small" placeholder="放行说明，可不填，只给自己看"
            class="flex-1" :disabled="!canConfirm" />
          <NButton size="small" type="primary" :secondary="status !== 'FAIL'" :disabled="!canConfirm"
            :loading="busy"
            :title="dirty ? '先保存理由，确认的得是落库那一稿' : ''"
            @click="confirm">
            {{ status === 'CONFIRMED' ? '重新确认' : '确认放行' }}
          </NButton>
        </div>
        <div v-if="dirty" class="text-[12px] text-warn">
          理由有未保存的改动。先点上面的「保存结论并自检」，再确认——不然记下来的指纹是旧那一稿的。
        </div>
      </div>
    </template>
  </div>
</template>
