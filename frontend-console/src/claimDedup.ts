import type { useDialog } from 'naive-ui'
import { h } from 'vue'
import { api, type ClaimDedup, type ClaimMode, type ClaimResult } from './api'

type DialogApiInjection = ReturnType<typeof useDialog>

/** 人对查重提示的回答。skip 带着要记进题里的理由 */
export type DedupAnswer = { action: 'skip'; reason: string } | { action: 'discard' } | { action: 'cancel' }

/** solo2 没起或查重没跑成：说一声，确认了就照常领，不拦 */
export function askUnavailable(dialog: DialogApiInjection, why: string, what: string): Promise<boolean> {
  return new Promise((resolve) => {
    let done = false
    const finish = (v: boolean) => { if (!done) { done = true; resolve(v) } }
    dialog.warning({
      title: '领取前查重没有跑成',
      content: `${why}。这次没法确认${what}有没有和已有的题重复，仍要照常领取吗？`,
      positiveText: '照常领取',
      negativeText: '取消',
      onPositiveClick: () => finish(true),
      onNegativeClick: () => finish(false),
      onClose: () => finish(false),
      onMaskClick: () => finish(false),
    })
  })
}

/** 领一道题，查重拦下来时问人，按回答重发、废弃或作罢。
 *  返回最终那次领取的结果；废弃了或人取消了返回 null，discarded 标出是哪一种 */
export async function claimWithDedup(
  dialog: DialogApiInjection, id: number, taskNo: string, mode: ClaimMode,
): Promise<{ result: ClaimResult | null; discarded: boolean }> {
  const r = await api.claim(id, false, mode)
  if (!r.dedup) return { result: r, discarded: false }
  if (r.dedup.state === 'unavailable') {
    if (!await askUnavailable(dialog, r.dedup.reason, `题 ${taskNo} `)) return { result: null, discarded: false }
    return { result: await api.claim(id, false, mode, { reason: `未查重，人工确认后照常领取（${r.dedup.reason}）` }), discarded: false }
  }
  const a = await askHit(dialog, taskNo, r.dedup)
  if (a.action === 'discard') {
    await api.discard(id, r.dedup.reason)
    return { result: null, discarded: true }
  }
  if (a.action === 'cancel') return { result: null, discarded: false }
  return { result: await api.claim(id, false, mode, { reason: a.reason }), discarded: false }
}

/** 撞了：列出撞了谁，由人决定废弃、略过还是先不领 */
export function askHit(dialog: DialogApiInjection, taskNo: string, d: ClaimDedup): Promise<DedupAnswer> {
  return new Promise((resolve) => {
    let done = false
    const finish = (v: DedupAnswer) => { if (!done) { done = true; resolve(v) } }
    const hits = d.hits || []
    dialog.error({
      title: `题 ${taskNo} 查重命中`,
      content: () => h('div', { class: 'flex flex-col gap-2 text-[13px] leading-6' }, [
        h('div', d.reason),
        hits.length
          ? h('ul', { class: 'flex flex-col gap-1 text-fg1' }, hits.map((x) =>
            h('li', { class: 'flex gap-2' }, [
              h('span', { class: 'mono nums text-err shrink-0' }, `${(x.similarity * 100).toFixed(1)}%`),
              h('span', `${x.peer} · ${x.rule}`),
            ])))
          : null,
        h('div', { class: 'text-fg2 text-xs' }, '规则 A 按字面比，模板相近但做的事不同的题也会报；确认不是重复可以略过照领。'),
      ]),
      positiveText: '废弃这道题',
      negativeText: '略过查重，照常领取',
      onPositiveClick: () => finish({ action: 'discard' }),
      onNegativeClick: () => finish({ action: 'skip', reason: `查重命中后人工略过：${d.reason}` }),
      onClose: () => finish({ action: 'cancel' }),
      onMaskClick: () => finish({ action: 'cancel' }),
    })
  })
}
