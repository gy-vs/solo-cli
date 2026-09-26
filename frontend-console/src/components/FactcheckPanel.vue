<script setup lang="ts">
/** 事实核验的结果：理由里关于执行结果的话，和轨迹对不对得上。
 *
 * 和旁边那块措辞质检的分工要一眼看得出来，所以这一块只讲「说得对不对」，
 * 一句措辞的事都不提。两者判的东西不重叠，人该做的动作也完全不同：这里要他回去
 * 核对轨迹，那里要他改句子。
 *
 * 这一步的常态是「已经替你改好了」而不是「这里有问题你去改」。所以版面主角是订正
 * 留痕（notes）——哪一段哪一句、轨迹里实际是什么、改成了什么，人扫一眼就知道动过
 * 哪里，不必拿改前改后两稿逐字对。只有自动订正没成功时才会剩下要人动手的活。
 */
import { NButton, NInput, useDialog, useMessage } from 'naive-ui'
import { computed, ref } from 'vue'
import { api, type FactcheckReport, type FactcheckStatus, type TaskDetail } from '../api'
import { FACTCHECK_COLOR, FACTCHECK_LABEL, fmtTime, HEX } from '../status'
import DeliveryQc from './DeliveryQc.vue'

const props = defineProps<{
  task: TaskDetail
  report: FactcheckReport | Record<string, never>
  /** 理由编辑框里有没有未保存的改动。有的话先让人存，核验的得是落库那一稿 */
  dirty?: boolean
  readonly?: boolean
}>()
const emit = defineEmits<{
  (e: 'confirmed'): void
  (e: 'ran'): void
}>()

const msg = useMessage()
const dialog = useDialog()
const busy = ref(false)
const running = ref(false)
const note = ref('')

const r = computed(() => props.report as FactcheckReport)
const status = computed(() => props.task.factcheck_status as FactcheckStatus)
const mismatches = computed(() => r.value.mismatches || [])
const notes = computed(() => r.value.notes || [])
const hasReport = computed(() => status.value !== 'IDLE' && !!Object.keys(props.report || {}).length)
const pillColor = computed(() => HEX[FACTCHECK_COLOR[status.value] || 'fg1'])

/** 跑过核验、且此刻确实被挡着，才需要人拍板。 */
const canConfirm = computed(() => !props.readonly && !props.dirty
  && ['FAIL', 'ERROR', 'CONFIRMED'].includes(status.value))

/** 再跑一次值不值一次模型调用。口径和后端 gsb_factcheck.skip_reason 是同一套：
 *  理由一个字没改就再问一遍，报出来的还是那几处。ERROR 例外，那是没跑成。 */
const canRun = computed(() => !props.readonly && !props.dirty && status.value !== 'RUNNING'
  && (props.task.factcheck_stale || !['PASS', 'CONFIRMED', 'FAIL'].includes(status.value)))

const runHint = computed(() => {
  if (props.dirty) return '先保存理由，核验的得是落库那一稿'
  if (status.value === 'RUNNING') return '这道题的事实核验正在跑'
  if (status.value === 'FAIL') return '先按下面的出入改理由，改完这里才值得再跑一次'
  if (!canRun.value) return '已经有有效结论，理由没再改过，再跑一次答案一样'
  return '花一次模型调用，约两分钟'
})

async function run() {
  running.value = true
  try {
    const res = await api.factcheck(props.task.id)
    msg.success(res.message)
    emit('ran')
  } catch (e: any) { msg.error(e.message) } finally { running.value = false }
}

function confirm() {
  dialog.info({
    title: '确认放行这道题的事实核验',
    content: status.value === 'FAIL'
      ? '确认后这道题可以往下走。模型报的出入里总有它自己读偏的，'
        + '你对着轨迹看一眼直接放行是正常操作，但确认之后再改理由，结论会重新变成「已过期」。'
      : '确认后这道题可以往下走。之后再改理由，结论会重新变成「已过期」，要再确认一次。',
    positiveText: '确认放行',
    negativeText: '取消',
    onPositiveClick: async () => {
      busy.value = true
      try {
        const res = await api.confirmFactcheck(props.task.id, note.value)
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
      <div class="h2">事实核验</div>
      <span class="pill h-5 text-[12px] whitespace-nowrap"
        :style="{ color: pillColor, borderColor: `${pillColor}66` }">
        {{ FACTCHECK_LABEL[status] || FACTCHECK_LABEL.IDLE }}
        <template v-if="task.factcheck_mismatches"> · {{ task.factcheck_mismatches }} 处</template>
      </span>
      <span v-if="task.factcheck_stale" class="pill h-5 text-[12px] text-warn border-warn/40">已过期</span>
      <span v-if="r.model" class="mono text-[12px] text-fg2">{{ r.model }}</span>
      <span v-if="r.duration_s" class="mono text-[12px] text-fg2 nums">{{ r.duration_s }}s</span>
      <span class="mono text-[12px] text-fg2 nums ml-auto">{{ fmtTime(r.confirmed_at || r.finished_at) }}</span>
      <NButton size="tiny" :type="canRun ? 'primary' : 'default'" :secondary="canRun" :tertiary="!canRun"
        :disabled="!canRun" :loading="running" :title="runHint" @click="run">
        {{ hasReport ? '重跑核验' : '跑核验' }}
      </NButton>
    </div>
    <div v-if="status === 'FAIL' && task.factcheck_block" class="text-xs text-err">{{ task.factcheck_block }}</div>

    <!-- 还没跑过：说清这一步在判什么。它和措辞质检最容易被当成一回事 -->
    <div v-if="!hasReport" class="inner p-3 text-xs text-fg1 leading-6">
      这道题还没做事实核验。核验拿两侧轨迹里的实际执行记录去对理由：哪条命令跑过、
      跑出了什么、报没报错。写「没跑过测试」而轨迹里改完之后跑通了，这类话正则查不出来、
      读起来也完全像人话，只能让模型对着记录逐句核一遍。
      <div class="mt-1.5 text-fg2">
        对不上的地方会直接改掉，不是只报给你。改了哪几处会在这里逐条列出来。
      </div>
    </div>

    <template v-else>
      <div v-if="r.summary" class="text-xs leading-6"
        :style="{ color: mismatches.length ? HEX.fg0 : HEX.ok }">{{ r.summary }}</div>
      <div v-if="r.error" class="inner p-3 text-xs text-err leading-6">
        核验没跑完：{{ r.error }}。重跑一次就行，这不是理由本身的问题。
      </div>

      <!-- 订正留痕。这是这一步的主要交付物：只给一段改好的正文，人没法知道动过哪里 -->
      <div v-if="r.applied && notes.length" class="space-y-2">
        <div class="label">已按轨迹订正 {{ notes.length }} 处</div>
        <div v-for="(n, i) in notes" :key="i"
          class="text-xs text-fg0 leading-6 bg-ok/5 border-l-2 border-ok/50 pl-2.5 py-1 break-all">
          {{ n }}
        </div>
        <div class="text-[12px] text-fg2">
          理由正文已经是订正之后的那一稿（{{ r.chars_before }} 字 → {{ task.gsb_reason_chars }} 字），
          改前那一稿存在核验报告里，需要对照的话看下面的原文。
        </div>
      </div>

      <!-- 报了出入但没能自动订正：这才是要人动手的那种 -->
      <div v-else-if="mismatches.length" class="space-y-2">
        <div class="text-xs text-err leading-6">
          下面这些地方和轨迹对不上，自动订正没成功{{ r.rewrite_dropped ? `（${r.rewrite_dropped}）` : '' }}。
          照着「轨迹里实际是」那一行改，改完点下面的确认。
        </div>
        <div v-for="(it, i) in mismatches" :key="i" class="inner p-3 space-y-1.5">
          <div class="flex items-start gap-2">
            <span v-if="it.side" class="pill h-5 text-[12px] text-err border-err/40 shrink-0 whitespace-nowrap">
              {{ it.side }} 侧
            </span>
            <span class="text-[12px] text-fg1 leading-5 min-w-0">{{ it.claim }}</span>
          </div>
          <div class="text-xs text-fg0 leading-6 bg-err/5 border-l-2 border-err/50 pl-2.5 py-1 break-all">
            {{ it.quote }}
          </div>
          <div v-if="it.fact" class="text-xs text-ok leading-6 border-l-2 border-ok/50 pl-2.5 py-1 break-all">
            轨迹里实际是：{{ it.fact }}
          </div>
          <div v-if="it.fix" class="text-[12px] text-fg2 leading-5 break-all">建议改成：{{ it.fix }}</div>
        </div>
      </div>

      <div v-else class="text-xs text-ok">
        理由里关于执行结果的说法都能在轨迹里对上。
        <span v-if="r.resealed_at" class="text-fg2">（措辞质检改写之后复查过一遍，结论沿用。）</span>
      </div>

      <!-- 本地先摘出来的可疑句。模型未必都认，摆出来是为了让人能复核它的判断 -->
      <div v-if="r.local_suspects?.length" class="pt-1 border-t border-line space-y-1">
        <div class="label">本地规则摘出的可疑句（供复核，模型未必都认）</div>
        <div v-for="(s, i) in r.local_suspects" :key="i" class="text-[12px] text-fg2 leading-5 break-all">
          [{{ s.side }}] {{ s.quote }} —— {{ s.why }}
        </div>
      </div>

      <DeliveryQc :report="r.delivery" />

      <div v-if="r.reason_before" class="pt-1 border-t border-line space-y-1">
        <div class="label">订正之前的原文</div>
        <pre class="text-xs text-fg1 whitespace-pre-wrap inner p-3 leading-6 max-h-56 overflow-auto">{{ r.reason_before }}</pre>
      </div>

      <!-- 放行 -->
      <div v-if="!readonly && canConfirm" class="pt-2 border-t border-line space-y-2">
        <div class="flex items-center gap-3">
          <div class="label">人工确认</div>
          <span class="text-[12px] text-fg2">对着轨迹看过，确认这段话没问题</span>
        </div>
        <div class="flex items-start gap-2">
          <NInput v-model:value="note" size="small" placeholder="放行说明，可不填，只给自己看"
            class="flex-1" />
          <NButton size="small" type="primary" :secondary="status !== 'FAIL'" :loading="busy" @click="confirm">
            {{ status === 'CONFIRMED' ? '重新确认' : '确认放行' }}
          </NButton>
        </div>
      </div>
      <div v-if="dirty" class="text-[12px] text-warn">
        理由有未保存的改动。先点上面的「保存结论并自检」，再跑核验或确认。
      </div>
    </template>
  </div>
</template>
