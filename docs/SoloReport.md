# 众测题目验证命令

每题给出仓库地址和 A、B 两侧按顺序执行的命令，命令后的 `#` 注释是预期看到的结果。全部命令在 Windows PowerShell 中逐行执行即可（每行一条，不含 `&&`）。开新窗口先执行一次：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

题目按形态分四类，验证方式不同：**无界面**（库 / CLI）全靠终端里的一行式脚本与测试；**纯后端**起服务后用 `Invoke-RestMethod` 打接口看响应；**纯前端** / **全栈**起服务后开浏览器，按「界面操作」小节逐步点，命令块里同时给出可直接打的接口。凡是起了服务的题，命令块末尾都有 `taskkill` 收尾，两侧之间不会抢端口。

<!-- solo-report:index:start -->
## 总览

| 题号 | 题型 | 难度 | 形态 | A | B | 生成日期 |
| --- | --- | --- | --- | --- | --- | --- |
| [03](#第-03-题Feature-迭代困难无界面) | Feature 迭代 | 困难 | 无界面 | [A](https://github.com/gy-vs/css-syntax-core/tree/A) | [B](https://github.com/gy-vs/css-syntax-core/tree/B) | 2026-09-20 |
| [82](#第-82-题Feature-迭代困难无界面) | Feature 迭代 | 困难 | 无界面 | [A](https://github.com/gy-vs/httpx-multipart-header-core/tree/A) | [B](https://github.com/gy-vs/httpx-multipart-header-core/tree/B) | 2026-09-20 |
| [83](#第-83-题Feature-迭代困难无界面) | Feature 迭代 | 困难 | 无界面 | [A](https://github.com/gy-vs/httpx-h2-tunnel-core/tree/A) | [B](https://github.com/gy-vs/httpx-h2-tunnel-core/tree/B) | 2026-09-20 |
| [84](#第-84-题Feature-迭代困难无界面) | Feature 迭代 | 困难 | 无界面 | [A](https://github.com/gy-vs/jinja-namespace-assign-core/tree/A) | [B](https://github.com/gy-vs/jinja-namespace-assign-core/tree/B) | 2026-09-20 |
| [111](#第-111-题Bug-修复困难无界面) | Bug 修复 | 困难 | 无界面 | [A](https://github.com/gy-vs/markdown-raw-link-core/tree/A) | [B](https://github.com/gy-vs/markdown-raw-link-core/tree/B) | 2026-09-22 |
| [115](#第-115-题Feature-迭代困难无界面) | Feature 迭代 | 困难 | 无界面 | [A](https://github.com/gy-vs/httpx-netrc-auth-core/tree/A) | [B](https://github.com/gy-vs/httpx-netrc-auth-core/tree/B) | 2026-09-22 |
| [116](#第-116-题Feature-迭代困难无界面) | Feature 迭代 | 困难 | 无界面 | [A](https://github.com/gy-vs/httpx-auth-flow-core/tree/A) | [B](https://github.com/gy-vs/httpx-auth-flow-core/tree/B) | 2026-09-22 |
| [121](#第-121-题Feature-迭代困难无界面) | Feature 迭代 | 困难 | 无界面 | [A](https://github.com/gy-vs/attrs-pattern-match-core/tree/A) | [B](https://github.com/gy-vs/attrs-pattern-match-core/tree/B) | 2026-09-22 |
| [122](#第-122-题Feature-迭代困难无界面) | Feature 迭代 | 困难 | 无界面 | [A](https://github.com/gy-vs/async-queue-rate-state-core/tree/A) | [B](https://github.com/gy-vs/async-queue-rate-state-core/tree/B) | 2026-09-22 |
| [123](#第-123-题Feature-迭代困难无界面) | Feature 迭代 | 困难 | 无界面 | [A](https://github.com/gy-vs/async-queue-task-timeout-core/tree/A) | [B](https://github.com/gy-vs/async-queue-task-timeout-core/tree/B) | 2026-09-22 |
| [124](#第-124-题Feature-迭代困难无界面) | Feature 迭代 | 困难 | 无界面 | [A](https://github.com/gy-vs/markdown-definition-token-core/tree/A) | [B](https://github.com/gy-vs/markdown-definition-token-core/tree/B) | 2026-09-22 |
| [125](#第-125-题Feature-迭代困难无界面) | Feature 迭代 | 困难 | 无界面 | [A](https://github.com/gy-vs/httpx-response-stream-core/tree/A) | [B](https://github.com/gy-vs/httpx-response-stream-core/tree/B) | 2026-09-22 |
| [137](#第-137-题Feature-迭代困难全栈) | Feature 迭代 | 困难 | 全栈 | [A](https://github.com/gy-vs/webhook-replay-queue-web/tree/A) | [B](https://github.com/gy-vs/webhook-replay-queue-web/tree/B) | 2026-09-22 |
| [138](#第-138-题0-1-代码生成困难全栈) | 0-1 代码生成 | 困难 | 全栈 | [A](https://github.com/gy-vs/structured-merge-review-web/tree/A) | [B](https://github.com/gy-vs/structured-merge-review-web/tree/B) | 2026-09-22 |
| [140](#第-140-题0-1-代码生成困难全栈) | 0-1 代码生成 | 困难 | 全栈 | [A](https://github.com/gy-vs/unicode-collation-workbench-web/tree/A) | [B](https://github.com/gy-vs/unicode-collation-workbench-web/tree/B) | 2026-09-22 |
| [141](#第-141-题0-1-代码生成困难全栈) | 0-1 代码生成 | 困难 | 全栈 | [A](https://github.com/gy-vs/state-machine-scenario-web/tree/A) | [B](https://github.com/gy-vs/state-machine-scenario-web/tree/B) | 2026-09-22 |
| [142](#第-142-题0-1-代码生成困难全栈) | 0-1 代码生成 | 困难 | 全栈 | [A](https://github.com/gy-vs/content-provenance-review-web/tree/A) | [B](https://github.com/gy-vs/content-provenance-review-web/tree/B) | 2026-09-22 |
| [143](#第-143-题0-1-代码生成困难无界面) | 0-1 代码生成 | 困难 | 无界面 | [A](https://github.com/gy-vs/canonical-cbor-core/tree/A) | [B](https://github.com/gy-vs/canonical-cbor-core/tree/B) | 2026-09-22 |
| [144](#第-144-题0-1-代码生成困难无界面) | 0-1 代码生成 | 困难 | 无界面 | [A](https://github.com/gy-vs/persistent-range-map-core/tree/A) | [B](https://github.com/gy-vs/persistent-range-map-core/tree/B) | 2026-09-22 |
| [145](#第-145-题0-1-代码生成困难无界面) | 0-1 代码生成 | 困难 | 无界面 | [A](https://github.com/gy-vs/hpack-dynamic-table-core/tree/A) | [B](https://github.com/gy-vs/hpack-dynamic-table-core/tree/B) | 2026-09-22 |
| [146](#第-146-题0-1-代码生成困难无界面) | 0-1 代码生成 | 困难 | 无界面 | [A](https://github.com/gy-vs/merkle-consistency-core/tree/A) | [B](https://github.com/gy-vs/merkle-consistency-core/tree/B) | 2026-09-22 |
| [147](#第-147-题0-1-代码生成困难无界面) | 0-1 代码生成 | 困难 | 无界面 | [A](https://github.com/gy-vs/incremental-lexer-core/tree/A) | [B](https://github.com/gy-vs/incremental-lexer-core/tree/B) | 2026-09-22 |
| [148](#第-148-题Bug-修复困难全栈) | Bug 修复 | 困难 | 全栈 | [A](https://github.com/gy-vs/api-header-sequence-web/tree/A) | [B](https://github.com/gy-vs/api-header-sequence-web/tree/B) | 2026-09-22 |
| [149](#第-149-题Feature-迭代困难全栈) | Feature 迭代 | 困难 | 全栈 | [A](https://github.com/gy-vs/api-sequence-binding-web/tree/A) | [B](https://github.com/gy-vs/api-sequence-binding-web/tree/B) | 2026-09-22 |
| [150](#第-150-题Bug-修复困难全栈) | Bug 修复 | 困难 | 全栈 | [A](https://github.com/gy-vs/api-multipart-preview-web/tree/A) | [B](https://github.com/gy-vs/api-multipart-preview-web/tree/B) | 2026-09-22 |
| [151](#第-151-题Feature-迭代困难全栈) | Feature 迭代 | 困难 | 全栈 | [A](https://github.com/gy-vs/api-fault-profile-web/tree/A) | [B](https://github.com/gy-vs/api-fault-profile-web/tree/B) | 2026-09-22 |
| [153](#第-153-题Feature-迭代困难全栈) | Feature 迭代 | 困难 | 全栈 | [A](https://github.com/gy-vs/search-experiment-compare-web/tree/A) | [B](https://github.com/gy-vs/search-experiment-compare-web/tree/B) | 2026-09-22 |
| [154](#第-154-题Bug-修复困难全栈) | Bug 修复 | 困难 | 全栈 | [A](https://github.com/gy-vs/search-highlight-offset-web/tree/A) | [B](https://github.com/gy-vs/search-highlight-offset-web/tree/B) | 2026-09-22 |
| [156](#第-156-题Bug-修复困难全栈) | Bug 修复 | 困难 | 全栈 | [A](https://github.com/gy-vs/search-stable-page-web/tree/A) | [B](https://github.com/gy-vs/search-stable-page-web/tree/B) | 2026-09-22 |
| [157](#第-157-题Feature-迭代困难全栈) | Feature 迭代 | 困难 | 全栈 | [A](https://github.com/gy-vs/search-rule-sandbox-web/tree/A) | [B](https://github.com/gy-vs/search-rule-sandbox-web/tree/B) | 2026-09-22 |
| [159](#第-159-题Feature-迭代困难全栈) | Feature 迭代 | 困难 | 全栈 | [A](https://github.com/gy-vs/subtitle-ripple-group-web/tree/A) | [B](https://github.com/gy-vs/subtitle-ripple-group-web/tree/B) | 2026-09-22 |
| [160](#第-160-题Bug-修复困难全栈) | Bug 修复 | 困难 | 全栈 | [A](https://github.com/gy-vs/subtitle-grapheme-split-web/tree/A) | [B](https://github.com/gy-vs/subtitle-grapheme-split-web/tree/B) | 2026-09-22 |
| [161](#第-161-题Feature-迭代困难全栈) | Feature 迭代 | 困难 | 全栈 | [A](https://github.com/gy-vs/subtitle-alignment-session-web/tree/A) | [B](https://github.com/gy-vs/subtitle-alignment-session-web/tree/B) | 2026-09-22 |
| [162](#第-162-题Bug-修复困难全栈) | Bug 修复 | 困难 | 全栈 | [A](https://github.com/gy-vs/subtitle-webvtt-roundtrip-web/tree/A) | [B](https://github.com/gy-vs/subtitle-webvtt-roundtrip-web/tree/B) | 2026-09-22 |
| [163](#第-163-题Feature-迭代困难全栈) | Feature 迭代 | 困难 | 全栈 | [A](https://github.com/gy-vs/email-mime-preview-web/tree/A) | [B](https://github.com/gy-vs/email-mime-preview-web/tree/B) | 2026-09-22 |
| [164](#第-164-题Bug-修复困难全栈) | Bug 修复 | 困难 | 全栈 | [A](https://github.com/gy-vs/email-css-cache-web/tree/A) | [B](https://github.com/gy-vs/email-css-cache-web/tree/B) | 2026-09-22 |
| [165](#第-165-题Feature-迭代困难全栈) | Feature 迭代 | 困难 | 全栈 | [A](https://github.com/gy-vs/email-capability-profile-web/tree/A) | [B](https://github.com/gy-vs/email-capability-profile-web/tree/B) | 2026-09-22 |
| [167](#第-167-题Feature-迭代困难全栈) | Feature 迭代 | 困难 | 全栈 | [A](https://github.com/gy-vs/email-snapshot-share-web/tree/A) | [B](https://github.com/gy-vs/email-snapshot-share-web/tree/B) | 2026-09-22 |
| [168](#第-168-题Bug-修复困难全栈) | Bug 修复 | 困难 | 全栈 | [A](https://github.com/gy-vs/recurrence-dst-gap-web/tree/A) | [B](https://github.com/gy-vs/recurrence-dst-gap-web/tree/B) | 2026-09-22 |
| [169](#第-169-题Feature-迭代困难全栈) | Feature 迭代 | 困难 | 全栈 | [A](https://github.com/gy-vs/recurrence-exception-edit-web/tree/A) | [B](https://github.com/gy-vs/recurrence-exception-edit-web/tree/B) | 2026-09-22 |
| [171](#第-171-题Feature-迭代困难全栈) | Feature 迭代 | 困难 | 全栈 | [A](https://github.com/gy-vs/recurrence-revision-compare-web/tree/A) | [B](https://github.com/gy-vs/recurrence-revision-compare-web/tree/B) | 2026-09-22 |
| [172](#第-172-题Bug-修复困难全栈) | Bug 修复 | 困难 | 全栈 | [A](https://github.com/gy-vs/recurrence-weekstart-web/tree/A) | [B](https://github.com/gy-vs/recurrence-weekstart-web/tree/B) | 2026-09-22 |
| [173](#第-173-题Feature-迭代困难全栈) | Feature 迭代 | 困难 | 全栈 | [A](https://github.com/gy-vs/payload-transform-pipeline-web/tree/A) | [B](https://github.com/gy-vs/payload-transform-pipeline-web/tree/B) | 2026-09-22 |
| [174](#第-174-题Bug-修复困难全栈) | Bug 修复 | 困难 | 全栈 | [A](https://github.com/gy-vs/payload-falsy-coercion-web/tree/A) | [B](https://github.com/gy-vs/payload-falsy-coercion-web/tree/B) | 2026-09-22 |
| [175](#第-175-题Feature-迭代困难全栈) | Feature 迭代 | 困难 | 全栈 | [A](https://github.com/gy-vs/payload-dryrun-diff-web/tree/A) | [B](https://github.com/gy-vs/payload-dryrun-diff-web/tree/B) | 2026-09-22 |
| [176](#第-176-题Bug-修复困难全栈) | Bug 修复 | 困难 | 全栈 | [A](https://github.com/gy-vs/payload-source-row-web/tree/A) | [B](https://github.com/gy-vs/payload-source-row-web/tree/B) | 2026-09-22 |
| [177](#第-177-题Feature-迭代困难全栈) | Feature 迭代 | 困难 | 全栈 | [A](https://github.com/gy-vs/payload-contract-gate-web/tree/A) | [B](https://github.com/gy-vs/payload-contract-gate-web/tree/B) | 2026-09-22 |
| [178](#第-178-题Bug-修复困难全栈) | Bug 修复 | 困难 | 全栈 | [A](https://github.com/gy-vs/a11y-node-identity-web/tree/A) | [B](https://github.com/gy-vs/a11y-node-identity-web/tree/B) | 2026-09-22 |
| [179](#第-179-题Feature-迭代困难全栈) | Feature 迭代 | 困难 | 全栈 | [A](https://github.com/gy-vs/a11y-focus-order-web/tree/A) | [B](https://github.com/gy-vs/a11y-focus-order-web/tree/B) | 2026-09-22 |
| [180](#第-180-题Bug-修复困难全栈) | Bug 修复 | 困难 | 全栈 | [A](https://github.com/gy-vs/a11y-idref-scope-web/tree/A) | [B](https://github.com/gy-vs/a11y-idref-scope-web/tree/B) | 2026-09-22 |
| [181](#第-181-题Feature-迭代困难全栈) | Feature 迭代 | 困难 | 全栈 | [A](https://github.com/gy-vs/a11y-suppression-policy-web/tree/A) | [B](https://github.com/gy-vs/a11y-suppression-policy-web/tree/B) | 2026-09-22 |
| [182](#第-182-题Bug-修复困难全栈) | Bug 修复 | 困难 | 全栈 | [A](https://github.com/gy-vs/a11y-alpha-contrast-web/tree/A) | [B](https://github.com/gy-vs/a11y-alpha-contrast-web/tree/B) | 2026-09-22 |
| [183](#第-183-题Feature-迭代困难全栈) | Feature 迭代 | 困难 | 全栈 | [A](https://github.com/gy-vs/release-impact-plan-web/tree/A) | [B](https://github.com/gy-vs/release-impact-plan-web/tree/B) | 2026-09-22 |
| [184](#第-184-题Bug-修复困难全栈) | Bug 修复 | 困难 | 全栈 | [A](https://github.com/gy-vs/release-prerelease-range-web/tree/A) | [B](https://github.com/gy-vs/release-prerelease-range-web/tree/B) | 2026-09-22 |
| [185](#第-185-题Feature-迭代困难全栈) | Feature 迭代 | 困难 | 全栈 | [A](https://github.com/gy-vs/release-provenance-chain-web/tree/A) | [B](https://github.com/gy-vs/release-provenance-chain-web/tree/B) | 2026-09-22 |
| [186](#第-186-题Bug-修复困难全栈) | Bug 修复 | 困难 | 全栈 | [A](https://github.com/gy-vs/release-cycle-collapse-web/tree/A) | [B](https://github.com/gy-vs/release-cycle-collapse-web/tree/B) | 2026-09-22 |
| [187](#第-187-题Feature-迭代困难全栈) | Feature 迭代 | 困难 | 全栈 | [A](https://github.com/gy-vs/release-wave-simulator-web/tree/A) | [B](https://github.com/gy-vs/release-wave-simulator-web/tree/B) | 2026-09-22 |
| [189](#第-189-题Feature-迭代困难全栈) | Feature 迭代 | 困难 | 全栈 | [A](https://github.com/gy-vs/redaction-review-state-web/tree/A) | [B](https://github.com/gy-vs/redaction-review-state-web/tree/B) | 2026-09-22 |
| [190](#第-190-题Bug-修复困难全栈) | Bug 修复 | 困难 | 全栈 | [A](https://github.com/gy-vs/redaction-overlap-merge-web/tree/A) | [B](https://github.com/gy-vs/redaction-overlap-merge-web/tree/B) | 2026-09-22 |
| [191](#第-191-题Feature-迭代困难全栈) | Feature 迭代 | 困难 | 全栈 | [A](https://github.com/gy-vs/redaction-policy-sim-web/tree/A) | [B](https://github.com/gy-vs/redaction-policy-sim-web/tree/B) | 2026-09-22 |
| [193](#第-193-题Feature-迭代困难无界面) | Feature 迭代 | 困难 | 无界面 | [A](https://github.com/gy-vs/mime-alternative-stream-core/tree/A) | [B](https://github.com/gy-vs/mime-alternative-stream-core/tree/B) | 2026-09-22 |
| [194](#第-194-题Bug-修复困难无界面) | Bug 修复 | 困难 | 无界面 | [A](https://github.com/gy-vs/mime-folded-header-core/tree/A) | [B](https://github.com/gy-vs/mime-folded-header-core/tree/B) | 2026-09-22 |
| [195](#第-195-题Feature-迭代困难无界面) | Feature 迭代 | 困难 | 无界面 | [A](https://github.com/gy-vs/mime-rfc2231-params-core/tree/A) | [B](https://github.com/gy-vs/mime-rfc2231-params-core/tree/B) | 2026-09-22 |
| [198](#第-198-题Bug-修复困难无界面) | Bug 修复 | 困难 | 无界面 | [A](https://github.com/gy-vs/tar-pax-path-core/tree/A) | [B](https://github.com/gy-vs/tar-pax-path-core/tree/B) | 2026-09-22 |
| [200](#第-200-题Bug-修复困难无界面) | Bug 修复 | 困难 | 无界面 | [A](https://github.com/gy-vs/tar-checksum-compat-core/tree/A) | [B](https://github.com/gy-vs/tar-checksum-compat-core/tree/B) | 2026-09-22 |
| [201](#第-201-题Feature-迭代困难无界面) | Feature 迭代 | 困难 | 无界面 | [A](https://github.com/gy-vs/tar-unknown-size-writer-core/tree/A) | [B](https://github.com/gy-vs/tar-unknown-size-writer-core/tree/B) | 2026-09-22 |
| [202](#第-202-题Bug-修复困难无界面) | Bug 修复 | 困难 | 无界面 | [A](https://github.com/gy-vs/tar-longname-scope-core/tree/A) | [B](https://github.com/gy-vs/tar-longname-scope-core/tree/B) | 2026-09-22 |
| [208](#第-208-题Bug-修复困难无界面) | Bug 修复 | 困难 | 无界面 | [A](https://github.com/gy-vs/unicode-normalized-offset-core/tree/A) | [B](https://github.com/gy-vs/unicode-normalized-offset-core/tree/B) | 2026-09-22 |
| [209](#第-209-题Feature-迭代困难无界面) | Feature 迭代 | 困难 | 无界面 | [A](https://github.com/gy-vs/unicode-grapheme-fuzzy-core/tree/A) | [B](https://github.com/gy-vs/unicode-grapheme-fuzzy-core/tree/B) | 2026-09-22 |
| [211](#第-211-题Feature-迭代困难无界面) | Feature 迭代 | 困难 | 无界面 | [A](https://github.com/gy-vs/unicode-stream-matcher-core/tree/A) | [B](https://github.com/gy-vs/unicode-stream-matcher-core/tree/B) | 2026-09-22 |
| [212](#第-212-题Bug-修复困难无界面) | Bug 修复 | 困难 | 无界面 | [A](https://github.com/gy-vs/unicode-mark-highlight-core/tree/A) | [B](https://github.com/gy-vs/unicode-mark-highlight-core/tree/B) | 2026-09-22 |
| [214](#第-214-题Bug-修复困难无界面) | Bug 修复 | 困难 | 无界面 | [A](https://github.com/gy-vs/eventlog-partial-tail-core/tree/A) | [B](https://github.com/gy-vs/eventlog-partial-tail-core/tree/B) | 2026-09-22 |
| [215](#第-215-题Feature-迭代困难无界面) | Feature 迭代 | 困难 | 无界面 | [A](https://github.com/gy-vs/eventlog-idempotency-core/tree/A) | [B](https://github.com/gy-vs/eventlog-idempotency-core/tree/B) | 2026-09-22 |
| [216](#第-216-题Bug-修复困难无界面) | Bug 修复 | 困难 | 无界面 | [A](https://github.com/gy-vs/eventlog-watermark-race-core/tree/A) | [B](https://github.com/gy-vs/eventlog-watermark-race-core/tree/B) | 2026-09-22 |
| [263](#第-263-题Feature-迭代困难全栈) | Feature 迭代 | 困难 | 全栈 | [A](https://github.com/gy-vs/cert-path-build-web/tree/A) | [B](https://github.com/gy-vs/cert-path-build-web/tree/B) | 2026-09-22 |
| [265](#第-265-题Feature-迭代困难全栈) | Feature 迭代 | 困难 | 全栈 | [A](https://github.com/gy-vs/cert-revocation-sim-web/tree/A) | [B](https://github.com/gy-vs/cert-revocation-sim-web/tree/B) | 2026-09-22 |
| [267](#第-267-题Feature-迭代困难全栈) | Feature 迭代 | 困难 | 全栈 | [A](https://github.com/gy-vs/cert-algorithm-policy-web/tree/A) | [B](https://github.com/gy-vs/cert-algorithm-policy-web/tree/B) | 2026-09-22 |
| [268](#第-268-题Bug-修复困难全栈) | Bug 修复 | 困难 | 全栈 | [A](https://github.com/gy-vs/message-dedup-window-web/tree/A) | [B](https://github.com/gy-vs/message-dedup-window-web/tree/B) | 2026-09-22 |
| [270](#第-270-题Bug-修复困难全栈) | Bug 修复 | 困难 | 全栈 | [A](https://github.com/gy-vs/message-ack-gap-web/tree/A) | [B](https://github.com/gy-vs/message-ack-gap-web/tree/B) | 2026-09-22 |
| [271](#第-271-题Feature-迭代困难全栈) | Feature 迭代 | 困难 | 全栈 | [A](https://github.com/gy-vs/message-deadletter-replay-web/tree/A) | [B](https://github.com/gy-vs/message-deadletter-replay-web/tree/B) | 2026-09-22 |
| [275](#第-275-题Feature-迭代困难全栈) | Feature 迭代 | 困难 | 全栈 | [A](https://github.com/gy-vs/plan-regression-gate-web/tree/A) | [B](https://github.com/gy-vs/plan-regression-gate-web/tree/B) | 2026-09-22 |
| [279](#第-279-题Feature-迭代困难全栈) | Feature 迭代 | 困难 | 全栈 | [A](https://github.com/gy-vs/patch-threeway-review-web/tree/A) | [B](https://github.com/gy-vs/patch-threeway-review-web/tree/B) | 2026-09-22 |
| [284](#第-284-题Bug-修复困难全栈) | Bug 修复 | 困难 | 全栈 | [A](https://github.com/gy-vs/flag-percent-rollout-web/tree/A) | [B](https://github.com/gy-vs/flag-percent-rollout-web/tree/B) | 2026-09-22 |
| [285](#第-285-题Feature-迭代困难全栈) | Feature 迭代 | 困难 | 全栈 | [A](https://github.com/gy-vs/flag-config-publish-web/tree/A) | [B](https://github.com/gy-vs/flag-config-publish-web/tree/B) | 2026-09-22 |
| [286](#第-286-题Bug-修复困难全栈) | Bug 修复 | 困难 | 全栈 | [A](https://github.com/gy-vs/flag-segment-cache-web/tree/A) | [B](https://github.com/gy-vs/flag-segment-cache-web/tree/B) | 2026-09-22 |
| [287](#第-287-题Feature-迭代困难全栈) | Feature 迭代 | 困难 | 全栈 | [A](https://github.com/gy-vs/flag-offline-snapshot-web/tree/A) | [B](https://github.com/gy-vs/flag-offline-snapshot-web/tree/B) | 2026-09-22 |
| [289](#第-289-题Feature-迭代困难全栈) | Feature 迭代 | 困难 | 全栈 | [A](https://github.com/gy-vs/tz-bundle-diff-web/tree/A) | [B](https://github.com/gy-vs/tz-bundle-diff-web/tree/B) | 2026-09-22 |
| [290](#第-290-题Bug-修复困难全栈) | Bug 修复 | 困难 | 全栈 | [A](https://github.com/gy-vs/tz-local-gap-web/tree/A) | [B](https://github.com/gy-vs/tz-local-gap-web/tree/B) | 2026-09-22 |
| [291](#第-291-题Feature-迭代困难全栈) | Feature 迭代 | 困难 | 全栈 | [A](https://github.com/gy-vs/tz-patch-publish-web/tree/A) | [B](https://github.com/gy-vs/tz-patch-publish-web/tree/B) | 2026-09-22 |
| [292](#第-292-题Bug-修复困难全栈) | Bug 修复 | 困难 | 全栈 | [A](https://github.com/gy-vs/tz-posix-rule-web/tree/A) | [B](https://github.com/gy-vs/tz-posix-rule-web/tree/B) | 2026-09-22 |
| [295](#第-295-题Feature-迭代困难无界面) | Feature 迭代 | 困难 | 无界面 | [A](https://github.com/gy-vs/ws-extension-negotiate-core/tree/A) | [B](https://github.com/gy-vs/ws-extension-negotiate-core/tree/B) | 2026-09-22 |
| [299](#第-299-题Feature-迭代困难无界面) | Feature 迭代 | 困难 | 无界面 | [A](https://github.com/gy-vs/zip-stream-descriptor-core/tree/A) | [B](https://github.com/gy-vs/zip-stream-descriptor-core/tree/B) | 2026-09-22 |
| [301](#第-301-题Feature-迭代困难无界面) | Feature 迭代 | 困难 | 无界面 | [A](https://github.com/gy-vs/zip-encrypted-entry-core/tree/A) | [B](https://github.com/gy-vs/zip-encrypted-entry-core/tree/B) | 2026-09-22 |
| [307](#第-307-题Feature-迭代困难无界面) | Feature 迭代 | 困难 | 无界面 | [A](https://github.com/gy-vs/jsonschema-output-format-core/tree/A) | [B](https://github.com/gy-vs/jsonschema-output-format-core/tree/B) | 2026-09-22 |
| [315](#第-315-题Feature-迭代困难无界面) | Feature 迭代 | 困难 | 无界面 | [A](https://github.com/gy-vs/h2-priority-tree-core/tree/A) | [B](https://github.com/gy-vs/h2-priority-tree-core/tree/B) | 2026-09-22 |
| [322](#第-322-题Bug-修复困难无界面) | Bug 修复 | 困难 | 无界面 | [A](https://github.com/gy-vs/regex-step-budget-core/tree/A) | [B](https://github.com/gy-vs/regex-step-budget-core/tree/B) | 2026-09-22 |
| [327](#第-327-题Feature-迭代困难无界面) | Feature 迭代 | 困难 | 无界面 | [A](https://github.com/gy-vs/protobuf-json-mapping-core/tree/A) | [B](https://github.com/gy-vs/protobuf-json-mapping-core/tree/B) | 2026-09-22 |
| [328](#第-328-题Bug-修复困难无界面) | Bug 修复 | 困难 | 无界面 | [A](https://github.com/gy-vs/bytecode-cfg-verify-core/tree/A) | [B](https://github.com/gy-vs/bytecode-cfg-verify-core/tree/B) | 2026-09-22 |
| [329](#第-329-题Feature-迭代困难无界面) | Feature 迭代 | 困难 | 无界面 | [A](https://github.com/gy-vs/bytecode-stack-types-core/tree/A) | [B](https://github.com/gy-vs/bytecode-stack-types-core/tree/B) | 2026-09-22 |
| [330](#第-330-题Bug-修复困难无界面) | Bug 修复 | 困难 | 无界面 | [A](https://github.com/gy-vs/bytecode-constant-index-core/tree/A) | [B](https://github.com/gy-vs/bytecode-constant-index-core/tree/B) | 2026-09-22 |
| [333](#第-333-题Feature-迭代困难无界面) | Feature 迭代 | 困难 | 无界面 | [A](https://github.com/gy-vs/hamt-transient-core/tree/A) | [B](https://github.com/gy-vs/hamt-transient-core/tree/B) | 2026-09-22 |
| [335](#第-335-题Feature-迭代困难无界面) | Feature 迭代 | 困难 | 无界面 | [A](https://github.com/gy-vs/hamt-structural-diff-core/tree/A) | [B](https://github.com/gy-vs/hamt-structural-diff-core/tree/B) | 2026-09-22 |
| [336](#第-336-题Bug-修复困难无界面) | Bug 修复 | 困难 | 无界面 | [A](https://github.com/gy-vs/hamt-bitmap-boundary-core/tree/A) | [B](https://github.com/gy-vs/hamt-bitmap-boundary-core/tree/B) | 2026-09-22 |
| [339](#第-339-题0-1-代码生成困难全栈) | 0-1 代码生成 | 困难 | 全栈 | [A](https://github.com/gy-vs/otel-baggage-inspector-web/tree/A) | [B](https://github.com/gy-vs/otel-baggage-inspector-web/tree/B) | 2026-09-22 |
| [342](#第-342-题0-1-代码生成困难全栈) | 0-1 代码生成 | 困难 | 全栈 | [A](https://github.com/gy-vs/binary-layout-studio-web/tree/A) | [B](https://github.com/gy-vs/binary-layout-studio-web/tree/B) | 2026-09-22 |
<!-- solo-report:index:end -->

---

## 第 03 题　Feature 迭代　·　困难　·　无界面
<!-- solo-report:task=03 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/css-syntax-core　A 分支：https://github.com/gy-vs/css-syntax-core/tree/A　B 分支：https://github.com/gy-vs/css-syntax-core/tree/B

存为 `verify_property_syntax.mjs`（放在仓库根目录）

```javascript
async function loadParse() {
  try {
    const m = await import('./lib/property-syntax/index.js')
    return s => m.parse(s)
  } catch (err) {
    const m = await import('./lib/lexer/property-syntax.js')
    return s => m.parsePropertySyntax(s)
  }
}
const parseSyntax = await loadParse()
for (const s of ['<length> <color>', '<length># | auto']) {
  try {
    const ast = parseSyntax(s)
    console.log(JSON.stringify(s), ast && ast.type, ast && ast.combinator, ast && ast.terms && ast.terms.length)
  } catch (e) {
    console.log(JSON.stringify(s), e.name, e.rawMessage || e.message)
  }
}
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/css-syntax-core.git css-syntax-core-A
cd css-syntax-core-A
npm ci
npx mocha lib/__tests/property-syntax-parse.js lib/__tests/lexer-check-property-rule.js lib/__tests/lexer-check-custom-properties.js --require lib/__tests/helpers/setup.js --reporter spec   # 预期：99 passing
node --input-type=module -e "import { parse, lexer } from './lib/index.js'; const e = lexer.checkPropertyRule(parse('@property --x { syntax: \'<length>\'; inherits: false; initial-value: 0; }').children.first); console.log(e == null ? 'ok' : ((e.descriptor || '') + ' ' + String(e.message || e).split('\n')[0]));"   # 预期：ok
node --input-type=module -e "import { parse, lexer } from './lib/index.js'; const e = lexer.checkPropertyRule(parse('@property --x { syntax: \'<length>\'; inherits: false; initial-value: 0px; foo: bar; }').children.first); console.log(e == null ? 'ok' : ((e.descriptor || '') + ' ' + String(e.message || e).split('\n')[0]));"   # 预期：foo Unknown @property descriptor `foo`
node --input-type=module -e "import { parse, lexer } from './lib/index.js'; console.log(JSON.stringify(lexer.checkCustomProperties(parse('a { color: red; }'))));"   # 预期：[]
node --input-type=module -e "import { parse, lexer } from './lib/index.js'; const r = lexer.checkCustomProperties(parse('@property --x { syntax: \'<length>\'; inherits: false; initial-value: 0px; } .a { --x: red; } .b { --x: var(--y); }')); console.log(Array.isArray(r) ? r.length : r);"   # 预期：1
node verify_property_syntax.mjs   # 预期："<length> <color>" SyntaxError Unexpected input ；"<length># | auto" Group | 2
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/css-syntax-core.git css-syntax-core-B
cd css-syntax-core-B
npm ci
npx mocha lib/__tests/lexer-property-syntax.js lib/__tests/lexer-check-property-rule.js lib/__tests/lexer-check-custom-properties.js --require lib/__tests/helpers/setup.js --reporter spec   # 预期：80 passing
node --input-type=module -e "import { parse, lexer } from './lib/index.js'; const e = lexer.checkPropertyRule(parse('@property --x { syntax: \'<length>\'; inherits: false; initial-value: 0; }').children.first); console.log(e == null ? 'ok' : ((e.descriptor || '') + ' ' + String(e.message || e).split('\n')[0]));"   # 预期：initial-value `initial-value` descriptor value doesn't match the syntax "<length>"
node --input-type=module -e "import { parse, lexer } from './lib/index.js'; const e = lexer.checkPropertyRule(parse('@property --x { syntax: \'<length>\'; inherits: false; initial-value: 0px; foo: bar; }').children.first); console.log(e == null ? 'ok' : ((e.descriptor || '') + ' ' + String(e.message || e).split('\n')[0]));"   # 预期：ok
node --input-type=module -e "import { parse, lexer } from './lib/index.js'; console.log(JSON.stringify(lexer.checkCustomProperties(parse('a { color: red; }'))));"   # 预期：false
node --input-type=module -e "import { parse, lexer } from './lib/index.js'; const r = lexer.checkCustomProperties(parse('@property --x { syntax: \'<length>\'; inherits: false; initial-value: 0px; } .a { --x: red; } .b { --x: var(--y); }')); console.log(Array.isArray(r) ? r.length : r);"   # 预期：1
node verify_property_syntax.mjs   # 预期："<length> <color>" Group   2 ；"<length># | auto" Group | 2
cd ..
```

---

## 第 82 题　Feature 迭代　·　困难　·　无界面
<!-- solo-report:task=82 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/httpx-multipart-header-core　A 分支：https://github.com/gy-vs/httpx-multipart-header-core/tree/A　B 分支：https://github.com/gy-vs/httpx-multipart-header-core/tree/B

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/httpx-multipart-header-core.git httpx-multipart-header-core-A
cd httpx-multipart-header-core-A
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e . "pytest<8"
python -m pytest tests/test_multipart.py -q -o filterwarnings=ignore   # 预期：观察 passed
python -c "from httpx._content import encode_request; custom={'Content-ID':'id-1','Expires':'0'}; h,s=encode_request(files={'file':('name.txt', b'<file content>', 'text/plain', custom)}, boundary=b'+++'); body=b''.join(s); print(custom); print(b'Content-ID: id-1' in body, b'Expires: 0' in body, b'Content-Type: text/plain' in body); print(h.get('Content-Length'))"   # 预期：{'Content-ID': 'id-1', 'Expires': '0'} / True True True / 156
python -c "from httpx._content import encode_request; h,s=encode_request(files={'file':('test.txt', b'abc', None, {'Content-ID':'x'})}, boundary=b'+++'); body=b''.join(s); print(b'Content-Type:' in body, b'text/plain' in body, b'Content-ID: x' in body)"   # 预期：True True True
python -c "from httpx._content import encode_request; h,s=encode_request(files={'file':('name.txt', b'abc', 'text/plain', {'content-type':'image/png'})}, boundary=b'+++'); body=b''.join(s); print(b'image/png' in body, b'text/plain' in body)"   # 预期：True False
python -c "from httpx._content import encode_request; h,s=encode_request(files={'file':('name.txt', b'abc')}, boundary=b'+++'); body=b''.join(s); print(b'name.txt' in body, b'Content-Disposition' in body)"   # 预期：True True
deactivate
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/httpx-multipart-header-core.git httpx-multipart-header-core-B
cd httpx-multipart-header-core-B
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e . "pytest<8"
python -m pytest tests/test_multipart.py -q -o filterwarnings=ignore   # 预期：观察 passed
python -c "from httpx._content import encode_request; custom={'Content-ID':'id-1','Expires':'0'}; h,s=encode_request(files={'file':('name.txt', b'<file content>', 'text/plain', custom)}, boundary=b'+++'); body=b''.join(s); print(custom); print(b'Content-ID: id-1' in body, b'Expires: 0' in body, b'Content-Type: text/plain' in body); print(h.get('Content-Length'))"   # 预期：{'Content-ID': 'id-1', 'Expires': '0'} / True True True / 156
python -c "from httpx._content import encode_request; h,s=encode_request(files={'file':('test.txt', b'abc', None, {'Content-ID':'x'})}, boundary=b'+++'); body=b''.join(s); print(b'Content-Type:' in body, b'text/plain' in body, b'Content-ID: x' in body)"   # 预期：False False True
python -c "from httpx._content import encode_request; h,s=encode_request(files={'file':('name.txt', b'abc', 'text/plain', {'content-type':'image/png'})}, boundary=b'+++'); body=b''.join(s); print(b'image/png' in body, b'text/plain' in body)"   # 预期：True False
python -c "from httpx._content import encode_request; h,s=encode_request(files={'file':('name.txt', b'abc')}, boundary=b'+++'); body=b''.join(s); print(b'name.txt' in body, b'Content-Disposition' in body)"   # 预期：True True
deactivate
cd ..
```

---

## 第 83 题　Feature 迭代　·　困难　·　无界面
<!-- solo-report:task=83 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/httpx-h2-tunnel-core　A 分支：https://github.com/gy-vs/httpx-h2-tunnel-core/tree/A　B 分支：https://github.com/gy-vs/httpx-h2-tunnel-core/tree/B

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/httpx-h2-tunnel-core.git httpx-h2-tunnel-core-A
cd httpx-h2-tunnel-core-A
python -c "import os; print(os.path.isdir('.venv'))"   # 预期：True
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e ".[http2]" "pytest<8"
python -m pytest tests/client/test_proxies.py -q -o filterwarnings=ignore   # 预期：观察 passed
python -c "import httpx._transports.default as d; print(hasattr(d, '_proxy_http_version_kwargs'))"   # 预期：False
python -c "import httpx; t=httpx.HTTPTransport(http2=True, proxy=httpx.Proxy('http://127.0.0.1:8080')); print(type(t._pool).__name__, getattr(t._pool, '_http1', None), getattr(t._pool, '_http2', None))"   # 预期：HTTPProxy True True
python -c "import inspect, httpx; src=inspect.getsource(httpx.HTTPTransport.__init__); print(('except TypeError' in src), ('_proxy_http_version_kwargs' in src))"   # 预期：True False
deactivate
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/httpx-h2-tunnel-core.git httpx-h2-tunnel-core-B
cd httpx-h2-tunnel-core-B
python -c "import os; print(os.path.isdir('.venv'))"   # 预期：False
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e ".[http2]" "pytest<8"
python -m pytest tests/client/test_proxies.py -q -o filterwarnings=ignore   # 预期：观察 passed
python -c "import httpx._transports.default as d; print(hasattr(d, '_proxy_http_version_kwargs'))"   # 预期：True
python -c "import httpx; t=httpx.HTTPTransport(http2=True, proxy=httpx.Proxy('http://127.0.0.1:8080')); print(type(t._pool).__name__, getattr(t._pool, '_http1', None), getattr(t._pool, '_http2', None))"   # 预期：HTTPProxy True True
python -c "import inspect, httpx; src=inspect.getsource(httpx.HTTPTransport.__init__); print(('except TypeError' in src), ('_proxy_http_version_kwargs' in src))"   # 预期：False True
deactivate
cd ..
```

---

## 第 84 题　Feature 迭代　·　困难　·　无界面
<!-- solo-report:task=84 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/jinja-namespace-assign-core　A 分支：https://github.com/gy-vs/jinja-namespace-assign-core/tree/A　B 分支：https://github.com/gy-vs/jinja-namespace-assign-core/tree/B

存为 `verify_ns_assign.py`（放在仓库根目录）

```python
from jinja2 import Environment, TemplateRuntimeError
from jinja2 import compiler

print('has_write_guards', hasattr(compiler.CodeGenerator, '_write_nsref_guards'))
print('has_flag', '_nsref_guards_emitted' in open('src/jinja2/compiler.py', encoding='utf-8').read())

e = Environment()
print('swap', e.from_string('{% set ns = namespace(a=1, b=2) %}{% set ns.a, ns.b = ns.b, ns.a %}{{ ns.a }}-{{ ns.b }}').render())
print('mixed', e.from_string('{% set ns = namespace(b=0) %}{% set a, ns.b = 1, 2 %}{{ a }}-{{ ns.b }}').render())
print('nested', e.from_string('{% set ns = namespace(b=0) %}{% set a, (ns.b, c) = 1, (2, 3) %}{{ a }}-{{ ns.b }}-{{ c }}').render())
print('single', e.from_string('{% set ns = namespace(a=1) %}{% set ns.a = 2 %}{{ ns.a }}').render())
print('block', e.from_string('{% set ns = namespace() %}{% set ns.a %}42{% endset %}{{ ns.a }}').render())

t = e.from_string('{% set ns.a, ns.b = 1, 2 %}')
try:
    t.render(ns=dict())
    print('reject', 'no error')
except TemplateRuntimeError as err:
    print('reject', err)

t = e.from_string('{% set ns = namespace() %}{% set ns.a, ns.b = 1, 2, 3 %}')
try:
    t.render()
    print('mismatch', 'no error')
except ValueError as err:
    print('mismatch', type(err).__name__, err)

calls = [0]

def f():
    calls[0] += 1
    return (1, 2)

print('rhs', e.from_string('{% set ns = namespace() %}{% set ns.a, ns.b = f() %}{{ ns.a }}-{{ ns.b }}').render(f=f), 'calls', calls[0])
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/jinja-namespace-assign-core.git jinja-namespace-assign-core-A
cd jinja-namespace-assign-core-A
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e . "pytest<8" "markupsafe<2.1"
python -m pytest tests/test_core_tags.py -q -k namespace              # 预期：观察 passed
python verify_ns_assign.py                                          # 预期：has_write_guards True；has_flag False；swap 2-1；mixed 1-2；nested 1-2-3；single 2；block 42；reject cannot assign attribute on non-namespace object；mismatch ValueError too many values to unpack (expected 2)；rhs 1-2 calls 1
deactivate
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/jinja-namespace-assign-core.git jinja-namespace-assign-core-B
cd jinja-namespace-assign-core-B
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e . "pytest<8" "markupsafe<2.1"
python -m pytest tests/test_core_tags.py -q -k namespace              # 预期：观察 passed
python verify_ns_assign.py                                          # 预期：has_write_guards False；has_flag True；其余渲染与 A 相同
deactivate
cd ..
```

---

## 第 111 题　Bug 修复　·　困难　·　无界面
<!-- solo-report:task=111 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/markdown-raw-link-core　A 分支：https://github.com/gy-vs/markdown-raw-link-core/tree/A　B 分支：https://github.com/gy-vs/markdown-raw-link-core/tree/B

存为 `verify_raw_link.mjs`（放在仓库根目录）

```javascript
import {marked, Marked, lexer} from './lib/marked.esm.js';

function findLinks(tokens) {
  const out = [];
  const walk = (list) => {
    if (!list) {
      return;
    }
    for (const token of list) {
      if (token.type === 'link' || token.type === 'image') {
        out.push(token.type + ':' + JSON.stringify(token.raw));
      }
      walk(token.tokens);
      walk(token.items);
    }
  };
  walk(tokens);
  return out.join('|') || 'none';
}

const md1 = '[`x``y]z`](url)';
console.log('codespan-html', JSON.stringify(marked.parse(md1)).replace(/\n/g, ''));
console.log('codespan-raw', findLinks(lexer(md1)));

const inst = new Marked();
inst.use({
  extensions: [{
    name: 'mark',
    level: 'inline',
    start(src) {
      return src.indexOf('%%');
    },
    tokenizer(src) {
      const match = /^%%([\s\S]*?)%%/.exec(src);
      if (match) {
        return {type: 'mark', raw: match[0], text: match[1]};
      }
    },
    renderer(token) {
      return '<mark>' + token.text + '</mark>';
    },
  }],
});

const md2 = '[a %%]%% b](url)';
console.log('ext-html', JSON.stringify(inst.parse(md2)).replace(/\n/g, ''));
console.log('ext-raw', findLinks(inst.lexer(md2)));

const md3 = '[a %%](x)%% b](url)';
console.log('false-html', JSON.stringify(inst.parse(md3)).replace(/\n/g, ''));
console.log('false-raw', findLinks(inst.lexer(md3)));

const md4 = '[`x``y]z`][nope]';
console.log('fail-html', JSON.stringify(marked.parse(md4)).replace(/\n/g, ''));
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/markdown-raw-link-core.git markdown-raw-link-core-A
cd markdown-raw-link-core-A
npm ci
npm run build:esbuild
node --test --test-reporter=spec test/unit/Lexer.test.js   # 预期：含链接标签 raw token 用例，观察 pass
node verify_raw_link.mjs   # 预期：codespan-html 为带 <a href="url"> 的代码跨度链接；codespan-raw 为原文 [`x``y]z`](url)；ext-raw 为原文 [a %%]%% b](url)；false-html 误收短标签 <a href="x">a %%</a>%% b](url)；fail-html 回退为普通文本
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/markdown-raw-link-core.git markdown-raw-link-core-B
cd markdown-raw-link-core-B
npm ci
npm run build:esbuild
node --test --test-reporter=spec test/unit/Lexer.test.js   # 预期：观察 pass；无 A 侧那组 Lexer 标签用例
node verify_raw_link.mjs   # 预期：codespan-html 不成链接，为 [<code>x``y]z</code>](url)；codespan-raw none；ext-raw 被掩码污染为 [a aaaaa b](url)；false-html 收下完整链接 a <mark>](x)</mark> b；fail-html 与 A 相同回退
cd ..
```

---

## 第 115 题　Feature 迭代　·　困难　·　无界面
<!-- solo-report:task=115 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/httpx-netrc-auth-core　A 分支：https://github.com/gy-vs/httpx-netrc-auth-core/tree/A　B 分支：https://github.com/gy-vs/httpx-netrc-auth-core/tree/B

存为 `verify_netrc.py`（放在仓库根目录）

```python
import os
import stat
import httpx


def write_netrc(path, body):
    with open(path, 'w') as f:
        f.write(body)
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)


def echo_app(request):
    return httpx.Response(200, json={'auth': request.headers.get('Authorization')})


write_netrc('demo.netrc', 'machine example.org\nlogin alice\npassword s3cret\n')
transport = httpx.MockTransport(echo_app)
client = httpx.Client(transport=transport, auth=httpx.NetRCAuth('demo.netrc'))
print('match', client.get('https://example.org').json())
print('nomatch', client.get('https://other.org').json())
print('repr-default', repr(httpx.NetRCAuth()))
print('repr-file', repr(httpx.NetRCAuth('demo.netrc')))

try:
    missing = httpx.NetRCAuth('missing.netrc')
    print('construct', 'ok')
    c2 = httpx.Client(transport=transport, auth=missing)
    try:
        print('first', c2.get('https://example.org').json())
    except FileNotFoundError:
        print('first', 'FileNotFoundError')
    print('second', c2.get('https://example.org').json())
except FileNotFoundError:
    print('construct', 'FileNotFoundError')

c4 = httpx.Client(transport=transport, auth=httpx.NetRCAuth(), trust_env=False)
print('url-fallback', c4.get('https://alice:secret@example.org/').json())
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/httpx-netrc-auth-core.git httpx-netrc-auth-core-A
cd httpx-netrc-auth-core-A
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e . "pytest<8" trio trustme uvicorn
python -m pytest tests/test_auth.py tests/client/test_auth.py -q   # 预期：127 passed, 1 failed（空密码 netrc 在部分 CPython 上 NetrcParseError）
python -c "import httpx; print(repr(httpx.NetRCAuth()))"   # 预期：NetRCAuth(file='<default>')
python verify_netrc.py   # 预期：match 带 Basic YWxpY2U6czNjcmV0；nomatch auth None；construct FileNotFoundError；url-fallback auth None
deactivate
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/httpx-netrc-auth-core.git httpx-netrc-auth-core-B
cd httpx-netrc-auth-core-B
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e . "pytest<8" trio trustme uvicorn
python -m pytest tests/test_auth.py tests/client/test_auth.py -q   # 预期：119 passed
python -c "import httpx; print(repr(httpx.NetRCAuth()))"   # 预期：NetRCAuth()
python verify_netrc.py   # 预期：match 同 A；construct ok；first FileNotFoundError；second auth None；url-fallback Basic YWxpY2U6c2VjcmV0
deactivate
cd ..
```

---

## 第 116 题　Feature 迭代　·　困难　·　无界面
<!-- solo-report:task=116 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/httpx-auth-flow-core　A 分支：https://github.com/gy-vs/httpx-auth-flow-core/tree/A　B 分支：https://github.com/gy-vs/httpx-auth-flow-core/tree/B

存为 `verify_auth_flow.py`（放在仓库根目录）

```python
import httpx


req = httpx.Request('GET', 'https://example.org')
got = next(httpx.BasicAuth('u', 'p').auth_flow(req))
print('basic-header', 'Authorization' in got.headers)
print('basic-own-auth-flow', 'auth_flow' in vars(httpx.BasicAuth))
print('digest-own-auth-flow', 'auth_flow' in vars(httpx.DigestAuth))


class OnlyAsync(httpx.Auth):
    async def async_auth_flow(self, request):
        request.headers['X-Auth'] = 'async'
        yield request


try:
    next(OnlyAsync().sync_auth_flow(req))
    print('only-async-on-sync', 'ok')
except RuntimeError:
    print('only-async-on-sync', 'RuntimeError')


class Both(httpx.Auth):
    def sync_auth_flow(self, request):
        request.headers['X-Auth'] = 'sync'
        yield request

    async def async_auth_flow(self, request):
        request.headers['X-Auth'] = 'async'
        yield request


got2 = next(Both().sync_auth_flow(httpx.Request('GET', 'https://example.org')))
print('both-on-sync', got2.headers.get('x-auth'))
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/httpx-auth-flow-core.git httpx-auth-flow-core-A
cd httpx-auth-flow-core-A
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e . "pytest<8"
python -m pytest tests/client/test_auth.py -q   # 预期：观察 passed（含双 flow 用例）
python -c "import httpx; r=httpx.Request('GET','https://example.org'); print('Authorization' in next(httpx.BasicAuth('u','p').auth_flow(r)).headers)"   # 预期：True
python verify_auth_flow.py   # 预期：basic-header True；basic-own-auth-flow True；digest-own-auth-flow True；only-async-on-sync RuntimeError；both-on-sync sync
deactivate
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/httpx-auth-flow-core.git httpx-auth-flow-core-B
cd httpx-auth-flow-core-B
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e . "pytest<8"
python -m pytest tests/client/test_auth.py -q   # 预期：观察 passed（含双 flow 用例）
python -c "import httpx; r=httpx.Request('GET','https://example.org'); print('Authorization' in next(httpx.BasicAuth('u','p').auth_flow(r)).headers)"   # 预期：False
python verify_auth_flow.py   # 预期：basic-header False；basic-own-auth-flow False；digest-own-auth-flow False；only-async-on-sync RuntimeError；both-on-sync sync
deactivate
cd ..
```

---

## 第 121 题　Feature 迭代　·　困难　·　无界面
<!-- solo-report:task=121 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/attrs-pattern-match-core　A 分支：https://github.com/gy-vs/attrs-pattern-match-core/tree/A　B 分支：https://github.com/gy-vs/attrs-pattern-match-core/tree/B

存为 `verify_match_args.py`（放在仓库根目录）

```python
import ast
import os
import sys

import attr

C = attr.make_class("C", ["a", "b"])
print("make", getattr(C, "__match_args__", None))

@attr.s
class Classic:
    x = attr.ib()
    y = attr.ib(kw_only=True)
print("kwonly", getattr(Classic, "__match_args__", None))

@attr.define
class Excluded:
    positional = attr.ib()
    keyword_only = attr.ib(kw_only=True)
    excluded = attr.ib(init=False, default=3)
print("excluded", getattr(Excluded, "__match_args__", None))

@attr.s(match_args=False)
class Off:
    x = attr.ib()
print("off", hasattr(Off, "__match_args__"), getattr(Off, "__match_args__", None))

@attr.s(slots=True)
class Slotted:
    x = attr.ib()
print("slots", getattr(Slotted, "__match_args__", None), "__match_args__" in Slotted.__dict__)

try:
    @attr.s(match_args=True)
    class Custom:
        x = attr.ib()
        __match_args__ = ("custom",)
    print("custom", Custom.__match_args__)
except Exception as e:
    print("custom", type(e).__name__, str(e)[:80].replace("\n", " "))

try:
    @attr.s
    class AliasClash:
        x = attr.ib()
        _x = attr.ib(init=False, default=1)
    print("alias-clash", "ok", AliasClash(0)._x)
except Exception as e:
    print("alias-clash", type(e).__name__, str(e)[:90].replace("\n", " "))

print("syntax-helper", os.path.exists("tests/match_args_syntax.py"))
src = open("tests/test_match_args.py", encoding="utf-8").read()
print("bare-match-in-test", "match D(" in src)
try:
    ast.parse(src)
    print("ast-test", "ok")
except SyntaxError as e:
    print("ast-test", "SyntaxError", e.lineno)

if sys.version_info >= (3, 10):
    ns = {}
    exec(
        "def go(o, c):\n"
        "    match o:\n"
        "        case c(a, b):\n"
        "            return (a, b)\n"
        "        case _:\n"
        "            return None\n",
        ns,
    )
    print("real-match", ns["go"](C(1, 2), C))
else:
    print("real-match", "skipped")
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/attrs-pattern-match-core.git attrs-pattern-match-core-A
cd attrs-pattern-match-core-A
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e . "pytest<8" hypothesis six
$env:PYTHONPATH = "src"
python -m pytest tests/test_match_args.py -q   # 预期：观察 passed（3.10+；match 语句在 tests/match_args_syntax.py）
python verify_match_args.py   # 预期：make ('a', 'b')；kwonly ('x',)；excluded ('positional',)；off False None；slots ('x',) True；custom ('custom',)；alias-clash ok 1；syntax-helper True；bare-match-in-test False；real-match (1, 2)
deactivate
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/attrs-pattern-match-core.git attrs-pattern-match-core-B
cd attrs-pattern-match-core-B
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e . "pytest<8" hypothesis six
$env:PYTHONPATH = "src"
python -m pytest tests/test_match_args.py -q   # 预期：3.10+ 观察 passed；3.9 收集阶段 SyntaxError（正文含 match D(1, 2, 3, 4)）
python verify_match_args.py   # 预期：make / kwonly / excluded / off / slots / real-match 与 A 相同；custom ValueError __match_args__ is explicitly set；alias-clash ValueError Attributes 'x' and '_x' have the same __init__ argument name 'x'.；syntax-helper False；bare-match-in-test True
deactivate
cd ..
```

---

## 第 122 题　Feature 迭代　·　困难　·　无界面
<!-- solo-report:task=122 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/async-queue-rate-state-core　A 分支：https://github.com/gy-vs/async-queue-rate-state-core/tree/A　B 分支：https://github.com/gy-vs/async-queue-rate-state-core/tree/B

存为 `verify_rate.mjs`（放在仓库根目录）

```javascript
import PQueue from './source/index.js';

const q1 = new PQueue({concurrency: 2, interval: 5000, intervalCap: 1});
await q1.add(() => 'a');
console.log('empty-after-cap', q1.isRateLimited, q1.size);

const events = [];
const q2 = new PQueue({concurrency: 1, interval: 5000, intervalCap: 1});
q2.on('rateLimit', () => events.push('rl:' + q2.isRateLimited));
q2.on('rateLimitCleared', () => events.push('clr:' + q2.isRateLimited));
let release;
q2.add(() => new Promise((resolve) => {
  release = resolve;
}));
q2.add(() => 'b');
console.log('sat-wait', q2.isRateLimited, q2.size);
release('x');
await q2.onIdle();
console.log('events', events.join(',') || 'none');

const q3 = new PQueue({concurrency: 2, interval: 40, intervalCap: 1});
const ev3 = [];
q3.on('rateLimit', () => ev3.push('rl'));
q3.on('rateLimitCleared', () => ev3.push('clr'));
q3.add(() => 'a');
q3.add(() => 'b');
await q3.onIdle();
console.log('two-wait-events', ev3.join(',') || 'none', 'final', q3.isRateLimited);
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/async-queue-rate-state-core.git async-queue-rate-state-core-A
cd async-queue-rate-state-core-A
npm install
node --import=tsx/esm --test test/rate-limit.ts   # 预期：观察 pass；含额度耗尽即使 concurrency 也饱和仍限流
node --import=tsx/esm verify_rate.mjs   # 预期：empty-after-cap false 0；sat-wait true 1；events rl:true,clr:false；two-wait-events rl,clr final false
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/async-queue-rate-state-core.git async-queue-rate-state-core-B
cd async-queue-rate-state-core-B
npm install
node --import=tsx/esm --test test/rate-limit.ts   # 预期：观察 pass；concurrency 饱和不误报限流
node --import=tsx/esm verify_rate.mjs   # 预期：empty-after-cap false 0；sat-wait false 1；events rl:true,clr:false；two-wait-events rl,clr final false
cd ..
```

---

## 第 123 题　Feature 迭代　·　困难　·　无界面
<!-- solo-report:task=123 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/async-queue-task-timeout-core　A 分支：https://github.com/gy-vs/async-queue-task-timeout-core/tree/A　B 分支：https://github.com/gy-vs/async-queue-task-timeout-core/tree/B

存为 `verify_timeout.cjs`（放在仓库根目录）

```javascript
const mod = require('./dist');
const PQueue = mod.default || mod;
const TimeoutError = mod.TimeoutError;

function delay(ms, value) {
  return new Promise((resolve) => setTimeout(() => resolve(value), ms));
}

(async () => {
  const proto = Object.getPrototypeOf(new PQueue());
  const desc = Object.getOwnPropertyDescriptor(proto, 'concurrency');
  console.log('conc-setter', Boolean(desc && desc.set));

  const q0 = new PQueue({concurrency: 1});
  try {
    const v = await q0.add(() => delay(30, 'late'), {timeout: 0});
    console.log('timeout0', v);
  } catch (error) {
    console.log('timeout0', error.name);
  }

  const q1 = new PQueue({concurrency: 1});
  q1.add(() => delay(40, 'a'));
  try {
    const v = await q1.add(() => delay(10, 'b'), {timeout: 30});
    console.log('queue-wait', v);
  } catch (error) {
    console.log('queue-wait', error.name);
  }

  const q2 = new PQueue({concurrency: 1});
  try {
    await q2.add(() => delay(20, 'x'), {timeout: -1});
    console.log('neg', 'ok');
  } catch (error) {
    console.log('neg', error.name);
  }

  console.log('TimeoutError-export', typeof TimeoutError);
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/async-queue-task-timeout-core.git async-queue-task-timeout-core-A
cd async-queue-task-timeout-core-A
npm install
npm run build
npx ava test/timeout.ts   # 预期：观察 passed；不要跑 npm test，nyc 在较新 Node 上会崩
node verify_timeout.cjs   # 预期：conc-setter false；timeout0 late；queue-wait b；neg TypeError；TimeoutError-export function
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/async-queue-task-timeout-core.git async-queue-task-timeout-core-B
cd async-queue-task-timeout-core-B
npm install
npm run build
npx ava test/timeout.ts   # 预期：观察 passed，含动态 concurrency
node verify_timeout.cjs   # 预期：conc-setter true；timeout0 TimeoutError；queue-wait b；neg TimeoutError（并可能打出 TimeoutNegativeWarning）；TimeoutError-export function
cd ..
```

---

## 第 124 题　Feature 迭代　·　困难　·　无界面
<!-- solo-report:task=124 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/markdown-definition-token-core　A 分支：https://github.com/gy-vs/markdown-definition-token-core/tree/A　B 分支：https://github.com/gy-vs/markdown-definition-token-core/tree/B

存为 `verify_def.mjs`（放在仓库根目录）

```javascript
import fs from 'node:fs';
import {marked, lexer, Marked, Parser, Lexer} from './lib/marked.esm.js';

const src = '[link]: https://example.com "title"\n\n[link]';
const tokens = lexer(src);
const defs = tokens.filter((t) => t.type === 'def');
console.log('def-count', defs.length);
if (defs[0]) {
  console.log('def-fields', [defs[0].raw, defs[0].tag, defs[0].href, defs[0].title].join('|'));
}
console.log('html', JSON.stringify(marked.parse(src)).replace(/\n/g, ''));

const seen = [];
const walked = new Marked({
  walkTokens(token) {
    if (token.type === 'def') {
      seen.push(token.tag + ':' + token.href);
      token.href = '/changed';
    }
  },
});
console.log('walk-html', JSON.stringify(walked.parse(src)).replace(/\n/g, ''));
console.log('walk-seen', seen.join(','));

console.log('inline', JSON.stringify(marked.parseInline('[link]: https://example.com')));

const custom = new Marked({
  renderer: {
    def(token) {
      return '<!-- def ' + token.tag + ' -->';
    },
  },
});
console.log('custom', JSON.stringify(custom.parse('[x]: /u\n\n')).replace(/\n/g, ''));

const inst = new Marked();
inst.use({
  renderer: {
    paragraph() {
      return 'custom-p';
    },
  },
});
const pipeTokens = Lexer.lex('hello', inst.defaults);
const pipeHtml = Parser.parse(pipeTokens, inst.defaults);
console.log('manual-pipe', JSON.stringify(pipeHtml).replace(/\n/g, ''));

const instanceSrc = fs.readFileSync('test/unit/instance.test.js', 'utf8');
console.log('old-defaults-test', instanceSrc.includes('should pass defaults to lexer and parser'));
const typesSrc = fs.readFileSync('test/types/marked.ts', 'utf8');
console.log('types-walk-def', typesSrc.includes("token.type === 'def'"));
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/markdown-definition-token-core.git markdown-definition-token-core-A
cd markdown-definition-token-core-A
npm ci
npm run build:esbuild
node --test --test-reporter=spec test/unit/Lexer.test.js test/unit/Parser.test.js test/unit/marked.test.js   # 预期：观察 pass，含 def token / walkTokens / parseInline
node verify_def.mjs   # 预期：def-count 1；tag=link href=https://example.com title=title；html 仍是带 title 的 <a>；walk-html 仍指向原地址；walk-seen link:https://example.com；inline 不产生块级 def；custom <!-- def x -->；manual-pipe custom-p；old-defaults-test true；types-walk-def true
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/markdown-definition-token-core.git markdown-definition-token-core-B
cd markdown-definition-token-core-B
npm ci
npm run build:esbuild
node --test --test-reporter=spec test/unit/Lexer.test.js test/unit/Parser.test.js test/unit/marked.test.js   # 预期：观察 pass；折行定义与嵌套 def 覆盖更细
node verify_def.mjs   # 预期：def / html / walk / inline / custom / manual-pipe / types-walk-def 与 A 相同；old-defaults-test false（原 should pass defaults to lexer and parser 被顶替）
cd ..
```

---

## 第 125 题　Feature 迭代　·　困难　·　无界面
<!-- solo-report:task=125 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/httpx-response-stream-core　A 分支：https://github.com/gy-vs/httpx-response-stream-core/tree/A　B 分支：https://github.com/gy-vs/httpx-response-stream-core/tree/B

存为 `verify_stream.py`（放在仓库根目录）

```python
import httpx


r = httpx.Response(200, content=b'Hello, world!')
print('bytes', dict(r.headers), r.content)

g = (c for c in [b'Hello, ', b'world!'])
s = httpx.Response(200, content=g)
print('iter-headers', dict(s.headers), 'closed', s.is_closed)
print('iter-read', s.read(), 'closed', s.is_closed)


def boom():
    yield b'a'
    raise ValueError('boom')


t = httpx.Response(200, content=boom())
try:
    list(t.iter_raw())
except ValueError:
    print('boom', 'ValueError', 'closed', t.is_closed)

u = httpx.Response(200, content=(c for c in [b'x']))
u.close()
try:
    u.read()
    print('after-close', 'ok')
except Exception as exc:
    print('after-close', type(exc).__name__)

from httpx._content_streams import encode_response
stream = encode_response((c for c in [b'ab']))
print('encode-headers', dict(stream.get_headers()), 'replay', stream.can_replay() if callable(getattr(stream, 'can_replay', None)) else stream.can_replay)
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/httpx-response-stream-core.git httpx-response-stream-core-A
cd httpx-response-stream-core-A
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e . "pytest<8"
python -m pytest tests/models/test_responses.py tests/test_content_streams.py -q   # 预期：观察 passed
python -c "import httpx; r=httpx.Response(200, content=b'Hello, world!'); print(dict(r.headers), r.content)"   # 预期：{'content-length': '13'} b'Hello, world!'
python verify_stream.py   # 预期：iter-headers transfer-encoding chunked；boom ValueError closed False；after-close ResponseClosed
deactivate
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/httpx-response-stream-core.git httpx-response-stream-core-B
cd httpx-response-stream-core-B
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e . "pytest<8"
python -m pytest tests/models/test_responses.py tests/test_content_streams.py -q   # 预期：观察 passed
python -c "import httpx; r=httpx.Response(200, content=b'Hello, world!'); print(dict(r.headers), r.content)"   # 预期：{'content-length': '13'} b'Hello, world!'
python verify_stream.py   # 预期：iter-headers 同 A；boom ValueError closed True；after-close ResponseClosed
deactivate
cd ..
```

---

## 第 137 题　Feature 迭代　·　困难　·　全栈
<!-- solo-report:task=137 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/webhook-replay-queue-web　A 分支：https://github.com/gy-vs/webhook-replay-queue-web/tree/A　B 分支：https://github.com/gy-vs/webhook-replay-queue-web/tree/B

服务：`npm run dev` 同时起后端 4174 与前端 4173；浏览器开 http://localhost:4173。被占用会自动 +1，以新窗口打出的 Local: 地址为准。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/webhook-replay-queue-web.git webhook-replay-queue-web-A
cd webhook-replay-queue-web-A
npm ci
npm test                                                       # 预期：17 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                              # 浏览器打开后按下面「界面操作」走
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/capture/hook -ContentType "application/json" -Headers @{ 'x-signature' = 't' } -Body '{"order":1}' | ConvertTo-Json -Compress   # 预期：{"id":1}，状态码 202
Invoke-RestMethod http://127.0.0.1:4174/api/events | ConvertTo-Json -Compress   # 预期：一条事件，path 含 /api/capture/hook，verification.reason 为 valid
try { Invoke-RestMethod http://127.0.0.1:4174/api/batches | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：{"batches":[]}；界面建批后 batches 里有任务
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:4173，顶栏看到「Webhook Lab」，左栏标题「Events」，空列表时显示「等待 webhook 事件…」。终端打完 capture 后左栏出现 `POST /api/capture/hook`，小字 `event 1 · valid`。
2. 勾选该事件，在「并发数」填 `1`、在「间隔 (ms)」填 `200`，点击「重放 1 个事件」。状态栏先显示「创建批次…」，随后「批次 … 已创建」；右栏「重放批次」出现卡片，计数含「排队 / 运行 / 成功」。
3. 点击标题「展开/收起」打开任务，在仍显示 `running` 时立刻点「取消」。A：任务马上变成 `cancelled`，适配器监听 abort 当场结束；B：按钮文案是「取消任务」，默认回环要等约 25ms 定时器走完才变成「已取消」，期间仍可能停在「运行中」。
4. 在批次卡片的「并发」框里连续改数字。A：失焦才 PATCH，输入用 defaultValue 重挂载；B：`onChange` 每个按键都 PATCH 到服务端，「间隔 ms」同样逐键写入。
5. 再勾选同一事件建第二批。A：左栏事件数不变（测试适配器不回写捕获日志）；B：回环适配器把重放再写入捕获日志，左栏事件数随重放自增，勾选集会跟着变。
6. 刷新页面。A：`/api/events` 与 `/api/batches` 一并重拉，选择/展开不跟着批次刷新跳动；B：捕获事件只在挂载时拉一次，重连只补重放流，中间丢掉的捕获帧补不齐。
7. 回到终端执行剩下的接口命令并 `taskkill`。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/webhook-replay-queue-web.git webhook-replay-queue-web-B
cd webhook-replay-queue-web-B
npm ci
npm test                                                       # 预期：17 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                              # 浏览器打开后按下面「界面操作」走
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/capture/hook -ContentType "application/json" -Headers @{ 'x-signature' = 't' } -Body '{"order":1}' | ConvertTo-Json -Compress   # 预期：{"id":1}，状态码 202
Invoke-RestMethod http://127.0.0.1:4174/api/events | ConvertTo-Json -Compress   # 预期：一条事件；随后重放会再往该列表追加 loopback 捕获
try { Invoke-RestMethod http://127.0.0.1:4174/api/batches | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404（B 的快照在 GET /api/replay/state）
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 3、4、5、6 步。B 顶栏另有「实时已连接」/「重连中…」，批次上有「暂停批次」/「继续批次」（A 没有批次级暂停）。

---

## 第 138 题　0-1 代码生成　·　困难　·　全栈
<!-- solo-report:task=138 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/structured-merge-review-web　A 分支：https://github.com/gy-vs/structured-merge-review-web/tree/A　B 分支：https://github.com/gy-vs/structured-merge-review-web/tree/B

服务：`npm run dev` 同时起后端 3001 与前端 5173；浏览器开 http://localhost:5173。被占用会自动 +1，以新窗口打出的 Local: 地址为准。B 的 package.json 没有 `dev` 脚本，新窗口会报 Missing script: dev，需改跑 `npm run start`（3001）并另开 `npm run dev:client`（5173）。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/structured-merge-review-web.git structured-merge-review-web-A
cd structured-merge-review-web-A
npm ci
npm test                                                       # 预期：23 passed（merge + server）
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 merge-workbench server listening on http://localhost:3001 与 Local: http://localhost:5173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:3001/api/sessions | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:5173                              # 浏览器打开后按下面「界面操作」走
Invoke-RestMethod http://127.0.0.1:3001/api/sessions | ConvertTo-Json -Compress   # 预期：[]；创建会话后出现摘要项
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:3001/api/sessions -ContentType "application/json" -Body '{"name":"demo","base":{"a":1},"local":{"a":2},"remote":{"a":1,"b":3}}' | ConvertTo-Json -Compress   # 预期：201，带 id/revision/conflicts，字段 a 为值冲突
try { Invoke-RestMethod -Method Put -Uri http://127.0.0.1:3001/api/sessions/nope -ContentType "application/json" -Body '{"revision":0,"decisions":{}}' } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404，error 为 会话不存在
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:5173，看到标题「三方合并工作台」，「会话名称」占位符，按钮「填入演示数据」和「开始合并」，三栏标签「基线 base / 本地 local / 远端 remote」。
2. 点击「填入演示数据」，名称变成「演示：产品清单」，三栏填入产品清单 JSON。再点「开始合并」，进入审阅页，顶栏「← 返回」，状态「保存中…」随后「已保存 rev 1」。
3. 左栏看到「冲突（N）」路径列表（没有可展开折叠的结构树）。点某一冲突，中间三栏对照基线/本地/远端，右侧「最终结果」。A：树形审阅靠路径文本和三栏；B：有「结构树」按钮，冲突节点高亮，数组顺序冲突挂在数组节点上。
4. 点「↩ 撤销」再点「↪ 重做」，进度「已裁决 x/N」回退/前进。未裁决项 A 会提示「还有 N 个冲突未裁决（暂按本地计入）」；B 用独立结构树承载，不靠这条默认本地策略文案。
5. 再开一个标签页打开同一会话，两边各改一项冲突后等自动保存。A：一侧出现「检测到另一页面的修改，已合并双方决策」，revision 递增且不是最后写入覆盖；B：保存态会走到 `conflict-merge` / `saved`。
6. 刷新页面，未完成决策仍在，撤销栈以外的已保存选择恢复。点「复制 JSON」观察输出。
7. 回到终端执行剩下的接口命令并 `taskkill`。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/structured-merge-review-web.git structured-merge-review-web-B
cd structured-merge-review-web-B
npm ci
npm test                                                       # 预期：无测试文件，vitest 找不到用例而失败；且无 package-lock.json 时 npm ci 会先失败，需改用 npm install
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 预期：Missing script: dev；改跑 npm run start 后打出 merge-workbench server listening on http://localhost:3001
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:3001/api/sessions | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:5173                              # 浏览器打开后按下面「界面操作」走
Invoke-RestMethod http://127.0.0.1:3001/api/sessions | ConvertTo-Json -Compress   # 预期：[]；创建后有会话摘要
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:3001/api/sessions -ContentType "application/json" -Body '{"name":"demo","base":{"a":1},"local":{"a":2},"remote":{"a":1,"b":3}}' | ConvertTo-Json -Compress   # 预期：201，toDTO 会话
try { Invoke-RestMethod -Method Put -Uri http://127.0.0.1:3001/api/sessions/nope -ContentType "application/json" -Body '{"revision":0,"decisions":{}}' } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404，error 为 会话不存在
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 1、3、4 步。B 首页按钮是「载入示例」和「开始合并审阅」，非法 JSON 提示「存在无法解析的 JSON，请检查输入。」；审阅页有「结构树」「复制」「导出」。

---

## 第 140 题　0-1 代码生成　·　困难　·　全栈
<!-- solo-report:task=140 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/unicode-collation-workbench-web　A 分支：https://github.com/gy-vs/unicode-collation-workbench-web/tree/A　B 分支：https://github.com/gy-vs/unicode-collation-workbench-web/tree/B

服务：`npm run dev` 同时起后端 3001 与前端 5173；浏览器开 http://localhost:5173。被占用会自动 +1，以新窗口打出的 Local: 地址为准。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/unicode-collation-workbench-web.git unicode-collation-workbench-web-A
cd unicode-collation-workbench-web-A
npm ci
npm test                                                       # 预期：测试通过（sort/match/api）
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 API 3001 与 Local: http://localhost:5173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:3001/api/experiments | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:5173                              # 浏览器打开后按下面「界面操作」走
Invoke-RestMethod http://127.0.0.1:3001/api/experiments | ConvertTo-Json -Compress   # 预期：启动时 {"experiments":[]}；首页会自动新建一条「未命名实验」
try { Invoke-RestMethod http://127.0.0.1:3001/api/experiments/demo | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404，error 为 not_found（A 无 demo 种子 id）
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:3001/api/experiments -ContentType "application/json" -Body '{}' | ConvertTo-Json -Compress   # 预期：201，experiment.name 为 未命名实验，含组合字符/土耳其/数字种子样本
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:5173，标题「Unicode 排序与检索工作台」，自动出现一条实验。点「新建实验」，状态闪「已创建实验 r1」。名称框占位「实验名称」。
2. 在「样本」区看种子行（含 café / 土耳其 İ / file10）。点「+ 添加一行」再点某行「✕」（title「删除此行」）。切到「结果」，检索高亮应落在原字符串范围内。
3. 在「排序结果」点「全选」再「清空选择」，再手动点几行后拖动/改排序配置。A、B 重排后选中项都应还在；A 没有组件测试覆盖这条。
4. 复制当前页 URL，另开标签页改「实验名称」并点「保存」。回到第一页再保存。A：弹出「保存冲突」，差异把另一标签页新增的行标成「本地已删」；点「自动合并并保存」会用服务端列表做骨架，本地删掉的行可能被服务端版本复活，名称与配置取本地、对方改过的配置被丢掉。B：对话框「检测到并发修改（revision …）」，三路合并，按钮「合并并保存」「取消（继续保留本地更改）」。
5. 冲突框里对比 A 的「保留我的（覆盖服务端）」「放弃本地，采用服务端」「继续编辑（暂不保存）」与 B 的「取消（继续保留本地更改）」。窄屏下 A 只是三栏堆成单列；B 用「面板切换」在「编辑区」/「结果区」间切换且不重置选中。
6. 回到终端执行剩下的接口命令并 `taskkill`。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/unicode-collation-workbench-web.git unicode-collation-workbench-web-B
cd unicode-collation-workbench-web-B
npm ci
npm test                                                       # 预期：测试通过（含 merge 三路与组件用例）
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 API 3001 与 Local: http://localhost:5173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:3001/api/experiments | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:5173                              # 浏览器打开后按下面「界面操作」走
Invoke-RestMethod http://127.0.0.1:3001/api/experiments | ConvertTo-Json -Compress   # 预期：已有 id 为 demo 的种子实验
try { Invoke-RestMethod http://127.0.0.1:3001/api/experiments/demo | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：200，带 experiment 与 results（前端实时求值同一套引擎）
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:3001/api/experiments -ContentType "application/json" -Body '{}' | ConvertTo-Json -Compress   # 预期：201，新建实验（name 可为空字符串）
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 1、4、5 步。B 标题是「Unicode 工作台」，按钮「新建」，查询占位「输入子串，结果区按原字符串范围高亮…」；并列排序时 title 为「排序键相等，已按样本 id 决胜」。

---

## 第 141 题　0-1 代码生成　·　困难　·　全栈
<!-- solo-report:task=141 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/state-machine-scenario-web　A 分支：https://github.com/gy-vs/state-machine-scenario-web/tree/A　B 分支：https://github.com/gy-vs/state-machine-scenario-web/tree/B

服务：`npm run dev` 同时起后端 3001 与前端 5173；浏览器开 http://localhost:5173。被占用会自动 +1，以新窗口打出的 Local: 地址为准。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/state-machine-scenario-web.git state-machine-scenario-web-A
cd state-machine-scenario-web-A
npm ci
npm test                                                       # 预期：13 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 state machine workbench server on http://localhost:3001 与 Local: http://localhost:5173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:3001/api/sessions -ContentType "application/json" -Body '{"machine":{"initial":"idle","states":{"idle":{"on":{}}}},"scenario":{"steps":[]}}' | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:5173                              # 浏览器打开后按下面「界面操作」走
try { Invoke-RestMethod http://127.0.0.1:3001/api/health | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404（A 无 /api/health）
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:3001/api/sessions -ContentType "application/json" -Body '{"machine":{"initial":"idle","states":{"idle":{"on":{}}}},"scenario":{"name":"demo","onError":"rollback","steps":[{"at":0,"send":[{"type":"PING"}]}]}}' | ConvertTo-Json -Compress   # 预期：{sessionId, snapshot}，当前状态 idle
try { Invoke-RestMethod http://127.0.0.1:3001/api/sessions/nope } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404，error 为 SESSION_EXPIRED
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:5173，标题「状态机情景验证工作台」，左栏「状态机定义」「情景编排」已填默认 JSON。展开「可用守卫 / 动作（服务端注册表）」，看到「守卫: always, never, progressDone, payloadFlag, explodingGuard」。
2. 点击「创建会话」，连接状态经 `connecting` 变为 `online`。右栏「当前状态」显示 idle，「事件队列」与「步骤日志（单步差异）」出现。A：守卫/动作只能从这份固定清单挑；B：守卫可用 `ctx.count + 1` 这类表达式，按钮是「创建会话并开始」。
3. 点「运行」，再点「暂停」「继续」「单步」「步进 ×10」。页面暂停/单步不应打乱服务端虚拟时钟顺序。点「模拟断线重连」：A：持久化 lastAck，重连按序号续传，缓冲截断时横幅「事件缓冲已截断，已以服务端快照重新同步」；B：无「模拟断线重连」按钮，靠 SSE 重连，过期文案是「会话已过期（TTL 到期），请新建会话。」
4. 在「事件类型」填 `PAUSE`，「延迟」填 `0`，点「注入事件」，观察队列插入位置：动作派发的新事件不能插到当前批次之前。
5. 点「销毁会话」，横幅可为「会话已过期或被销毁，请重新创建」。B 对应按钮是「重置情景」，另有「跳到序号」+「跳转」。
6. 回到终端执行剩下的接口命令并 `taskkill`。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/state-machine-scenario-web.git state-machine-scenario-web-B
cd state-machine-scenario-web-B
npm ci
npm test                                                       # 预期：观察仍有失败（README 写全绿，GSB 记录最后一次运行未全绿）
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 [fsm-workbench] listening on http://localhost:3001 与 Local: http://localhost:5173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:3001/api/sessions -ContentType "application/json" -Body '{"machine":{"initial":"idle","states":{"idle":{"on":{}}}},"scenario":{"steps":[]}}' | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:5173                              # 浏览器打开后按下面「界面操作」走
try { Invoke-RestMethod http://127.0.0.1:3001/api/health | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：{"ok":true,"sessions":...,"registryActions":[...]}
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:3001/api/sessions -ContentType "application/json" -Body '{"machine":{"initial":"idle","states":{"idle":{"on":{}}}},"scenario":{"name":"demo","onError":"rollback","steps":[{"at":0,"send":[{"type":"PING"}]}]}}' | ConvertTo-Json -Compress   # 预期：201，{sessionId,status,expiresAt}
try { Invoke-RestMethod http://127.0.0.1:3001/api/sessions/nope } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404，code 为 SESSION_NOT_FOUND
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 2、3、5 步。B 控制条是「▶ 继续播放」「⏸ 暂停」「⏭ 单步」「跳转」「注入」；标题区有「当前状态 / 上下文」「待处理事件队列（按确定性排序键）」。

---

## 第 142 题　0-1 代码生成　·　困难　·　全栈
<!-- solo-report:task=142 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/content-provenance-review-web　A 分支：https://github.com/gy-vs/content-provenance-review-web/tree/A　B 分支：https://github.com/gy-vs/content-provenance-review-web/tree/B

服务：`npm run dev` 同时起后端与前端。A：API 4000、前端 5173；B：API 8787、前端 5173。浏览器开 http://localhost:5173。被占用会自动 +1，以新窗口打出的 Local: 地址为准。下列命令按 A 的 4000 与 `/api/declarations` 来写；B 把端口换成 8787、列表接口换成 `/api/chain`。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/content-provenance-review-web.git content-provenance-review-web-A
cd content-provenance-review-web-A
npm ci
npm test                                                       # 预期：17 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 来源声明链审阅工作台 API 已启动: http://localhost:4000 与 Local: http://localhost:5173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4000/api/declarations | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:5173                              # 浏览器打开后按下面「界面操作」走
Invoke-RestMethod http://127.0.0.1:4000/api/declarations | ConvertTo-Json -Compress   # 预期：{"items":[]}；提交后 items 带 state/review
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4000/api/declarations -ContentType "application/json" -Body '{}' } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：400，error 为 invalid-declaration
try { Invoke-RestMethod http://127.0.0.1:4000/api/declarations/nope } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404，error 为 not-found
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:5173，标题「来源声明链审阅工作台」，点「刷新」。左栏「提交声明」，可切「表单」/「导入 JSON」，占位「如 article-1」「如 root-a, root-b」「样例内容」。
2. 用表单填内容 id、点「派生并提交」或「提交原始 JSON」。卡片边框区分未验证 / 有效 / 无效 / 被上游阻塞。详情「挂起原因」与「阻塞来源」分开。A：签名是 HMAC，公钥字段里带着共享密钥，未知密钥无法单列；B：Ed25519 可注入，未知密钥是一类失败，「签名密钥」写在卡片 title 上。
3. 点开一条声明，在「审阅人（本地标识）」「审阅意见」填写后保存，看到「已保存 v1」。A 另有「载入最新版本」。
4. 再开一个标签页改同一条的审阅备注并保存。回到第一页等约 8 秒轮询。A：草稿被轮询回填成服务端值，正在编辑的标签和备注静默消失；B：提示冲突，按钮「采用对方版本，放弃我的草稿」与「仍以我的草稿覆盖」，不会静默覆盖。
5. 提交一条父 id 尚不存在的声明。A：状态未验证/挂起，补齐父节点后自动验证；B：树视图 title「一个或多个声明引用了尚不存在的父声明」，可切「派生关系树」/「时间线」。
6. 回到终端执行剩下的接口命令并 `taskkill`。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/content-provenance-review-web.git content-provenance-review-web-B
cd content-provenance-review-web-B
npm ci
npm test                                                       # 预期：13 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 [provenance-bench] API listening on http://localhost:8787 与 Local: http://localhost:5173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:8787/api/chain | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:5173                              # 浏览器打开后按下面「界面操作」走
Invoke-RestMethod http://127.0.0.1:8787/api/chain | ConvertTo-Json -Compress   # 预期：链路快照（nodes/reviews）；A 同路径在 4000 上 404
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8787/api/claims -ContentType "application/json" -Body '{}' } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：400
try { Invoke-RestMethod http://127.0.0.1:8787/api/claims/nope } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404 或观察错误体
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 2、4、5 步。B 审阅区占位「输入昵称」「记录核查依据……」，标记 aria-label「审阅标记」。

---

## 第 143 题　0-1 代码生成　·　困难　·　无界面
<!-- solo-report:task=143 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/canonical-cbor-core　A 分支：https://github.com/gy-vs/canonical-cbor-core/tree/A　B 分支：https://github.com/gy-vs/canonical-cbor-core/tree/B

存为 `verify_cbor.mjs`（放在仓库根目录）

```javascript
const api = await import('./dist/index.js');
const {encode, decode} = api;

function hex(bytes) {
  return Buffer.from(bytes).toString('hex');
}

const canon = encode({b: 1, a: 2}, {canonical: true});
console.log('canon-hex', hex(canon));

const one = encode(1);
const decoded = decode(one);
const value = decoded && Object.prototype.hasOwnProperty.call(decoded, 'value') ? decoded.value : decoded;
console.log('small-int', typeof value, String(value));

console.log('nan-hex', hex(encode(Number.NaN, {canonical: true})));
console.log('neg0-hex', hex(encode(-0, {canonical: true})));

const indef = Uint8Array.from([0x7f, 0x62, 0x61, 0x62, 0xff]);
const first = indef.slice(0, 2);
const rest = indef.slice(2);

if (api.CborDecoder) {
  const decoder = new api.CborDecoder();
  const parts = [];
  decoder.push(first);
  const a = decoder.next();
  parts.push(a.done ? JSON.stringify(a.value) : 'need-more');
  decoder.push(rest);
  try {
    const b = decoder.next();
    parts.push(b.done ? JSON.stringify(b.value) : 'need-more');
  } catch (error) {
    parts.push(error.name + ':' + (error.code || error.message).toString().slice(0, 40));
  }
  console.log('indef-split', parts.join('|'));
} else {
  const decoder = new api.Decoder();
  const parts = [];
  decoder.write(first);
  try {
    parts.push(JSON.stringify(decoder.decode().value));
  } catch (error) {
    parts.push(error.name);
  }
  decoder.write(rest);
  try {
    parts.push(JSON.stringify(decoder.decode().value));
  } catch (error) {
    parts.push(error.name + ':' + (error.message || '').toString().slice(0, 40));
  }
  console.log('indef-split', parts.join('|'));
}
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/canonical-cbor-core.git canonical-cbor-core-A
cd canonical-cbor-core-A
npm ci
npm run build
npm test   # 预期：观察 pass
node verify_cbor.mjs   # 预期：canon-hex a2616102616201；small-int number 1；nan-hex f97e00；neg0-hex f98000；indef-split need-more|"b"
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/canonical-cbor-core.git canonical-cbor-core-B
cd canonical-cbor-core-B
npm ci
npm run build
npm test   # 预期：观察 pass；差分套件 test/property.ts 不在默认命令里
node verify_cbor.mjs   # 预期：canon-hex / nan-hex / neg0-hex 与 A 相同；small-int bigint 1；indef-split NeedMoreDataError|"ab"
cd ..
```

---

## 第 144 题　0-1 代码生成　·　困难　·　无界面
<!-- solo-report:task=144 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/persistent-range-map-core　A 分支：https://github.com/gy-vs/persistent-range-map-core/tree/A　B 分支：https://github.com/gy-vs/persistent-range-map-core/tree/B

存为 `verify_rangemap.mjs`（放在仓库根目录）

```javascript
let api;
try {
  api = await import('./dist/index.js');
} catch {
  api = await import('./dist/src/range-map.js');
}
const {RangeMap} = api;

function dump(map) {
  if (typeof map.toArray === 'function') {
    return JSON.stringify(map.toArray());
  }
  return JSON.stringify([...map.entries()].map((entry) => ({
    start: entry.start,
    end: entry.end,
    value: entry.value,
  })));
}

function getValue(map, pos) {
  const hit = map.get(pos);
  if (hit && typeof hit === 'object' && Object.prototype.hasOwnProperty.call(hit, 'value')) {
    return hit.value;
  }
  return hit;
}

function applyEdit(map, start, end, insert) {
  if (typeof map.transform === 'function') {
    return map.transform([{start, end, newLength: insert}], {affinity: {start: 'left', end: 'right'}});
  }
  return map.applyEdits([{start, end, insertLength: insert}]);
}

let map = RangeMap.empty();
map = map.set(0, 10, 'a').set(3, 7, 'b');
console.log('overwrite', dump(map));
console.log('get5', getValue(map, 5));

const v0 = map;
const v1 = map.set(20, 30, 'c');
console.log('old-still', dump(v0));
if (typeof v0.sharedNodes === 'function') {
  console.log('shared', v0.sharedNodes(v1));
} else if (api.countSharedNodes) {
  console.log('shared', api.countSharedNodes(v0, v1));
} else {
  console.log('shared', 'n/a');
}

const tiled = RangeMap.empty().set(0, 20, 'L').set(20, 30, 'M').set(30, 50, 'R');
console.log('edit-inner', dump(applyEdit(tiled, 20, 30, 4)));

const wrap = RangeMap.empty().set(0, 50, 'X');
console.log('edit-wrap', dump(applyEdit(wrap, 20, 30, 4)));

const cover = RangeMap.empty().set(0, 50, 'X');
console.log('edit-cover', dump(applyEdit(cover, 0, 50, 4)));
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/persistent-range-map-core.git persistent-range-map-core-A
cd persistent-range-map-core-A
npm ci
npm run build
node --import tsx --test test/overwrite.test.ts test/persistence.test.ts   # 预期：观察 pass；完整 npm test 会因 fuzz 里 affinity 对照失败退出
node verify_rangemap.mjs   # 预期：overwrite 切成 a[0,3) b[3,7) a[7,10)；get5 b；old-still 仍是旧三段；shared 2；edit-inner L[0,24)+R[24,44)（中段 M 被丢掉）；edit-wrap X[0,44)；edit-cover X[0,4)
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/persistent-range-map-core.git persistent-range-map-core-B
cd persistent-range-map-core-B
npm ci
npm run build
npm test   # 预期：观察 pass
node verify_rangemap.mjs   # 预期：overwrite / get5 / old-still / edit-wrap 与 A 相同；shared 1；edit-inner L[0,20)+R[20,44)；edit-cover []
cd ..
```

---

## 第 145 题　0-1 代码生成　·　困难　·　无界面
<!-- solo-report:task=145 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/hpack-dynamic-table-core　A 分支：https://github.com/gy-vs/hpack-dynamic-table-core/tree/A　B 分支：https://github.com/gy-vs/hpack-dynamic-table-core/tree/B

存为 `verify_hpack.mjs`（放在仓库根目录）

```javascript
let api;
try {
  api = await import('./dist/index.js');
} catch {
  api = await import('./dist/src/index.js');
}

const {HpackEncoder, HpackDecoder, DynamicTable, encodeInteger} = api;

function tryCall(fn, args) {
  try {
    const out = fn(...args);
    return Buffer.from(out).toString('hex');
  } catch (error) {
    return error.name;
  }
}

console.log('enc-0-5-1337', tryCall(encodeInteger, [0, 5, 1337]));
console.log('enc-1337-5-0', tryCall(encodeInteger, [1337, 5, 0]));

const encoder = new HpackEncoder();
const decoder = new HpackDecoder();
const block = encoder.encode([
  {name: ':method', value: 'GET'},
  {name: 'authorization', value: 'Bearer x', indexing: 'never'},
]);
console.log('block-hex', Buffer.from(block).toString('hex'));
console.log('decoded', JSON.stringify(decoder.decode(Buffer.from(block))));
const snap = decoder.snapshot();
const entries = snap.entries || snap;
console.log('dec-snap', JSON.stringify(entries));
const encSnap = encoder.snapshot();
console.log('enc-snap', JSON.stringify(encSnap.entries || encSnap));

try {
  decoder.decode(Buffer.from('ff01', 'hex'));
  console.log('bad-idx', 'ok');
} catch (error) {
  console.log('bad-idx', error.name, error.code || '');
}
const after = decoder.snapshot();
console.log('snap-after-fail', JSON.stringify(after.entries || after));

try {
  const frozen = decoder.snapshot();
  frozen.entries.push({name: 'x', value: 'y'});
  console.log('snap-mut', 'pushed', frozen.entries.length);
} catch (error) {
  console.log('snap-mut', error.name);
}

try {
  new DynamicTable(-1);
  console.log('bad-size', 'ok');
} catch (error) {
  console.log('bad-size', error.name, error.code || '');
}
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/hpack-dynamic-table-core.git hpack-dynamic-table-core-A
cd hpack-dynamic-table-core-A
npm ci
npm run build
npm test   # 预期：观察 pass
node verify_hpack.mjs   # 预期：enc-0-5-1337 1f9a0a；enc-1337-5-0 20；block-hex 821f08084265617265722078；decoded 含 indexing indexed/never；bad-idx HpackDecodingError INDEX_OUT_OF_RANGE；snap-after-fail []；snap-mut TypeError；bad-size HpackDecodingError DYNAMIC_TABLE_SIZE
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/hpack-dynamic-table-core.git hpack-dynamic-table-core-B
cd hpack-dynamic-table-core-B
npm ci
npm run build
npm test   # 预期：观察 pass
node verify_hpack.mjs   # 预期：enc-0-5-1337 20；enc-1337-5-0 1f9a0a；block-hex 与 A 相同；decoded 含 sensitive false/true；bad-idx HpackDecodingError（无 code）；snap-after-fail []；snap-mut pushed 1；bad-size RangeError
cd ..
```

---

## 第 146 题　0-1 代码生成　·　困难　·　无界面
<!-- solo-report:task=146 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/merkle-consistency-core　A 分支：https://github.com/gy-vs/merkle-consistency-core/tree/A　B 分支：https://github.com/gy-vs/merkle-consistency-core/tree/B

存为 `verify_146.mjs`（放在仓库根目录）

```javascript
import { createHash } from 'node:crypto';
import * as api from './dist/index.js';

const hashFn = (b) => createHash('sha256').update(b).digest();
const hex = (u) => Buffer.from(u).toString('hex').slice(0, 16);

console.log(
  'exports',
  ['MerkleLog', 'AppendOnlyMerkleLog', 'verifyInclusion', 'verifyInclusionProof', 'verifyConsistency', 'verifyConsistencyProof']
    .filter((k) => typeof api[k] === 'function')
    .join(','),
);

const scratch = new api.InMemoryNodeStore();
const digest = new Uint8Array(32);
try {
  if (typeof scratch.putNode === 'function') {
    await scratch.putNode(0, 0, digest);
    await scratch.putNode(0, 0, digest);
    console.log('dup-write', 'accepted');
  } else {
    scratch.setNode(0, 0, digest);
    scratch.setNode(0, 0, digest);
    console.log('dup-write', 'accepted');
  }
} catch (e) {
  console.log('dup-write', String(e.message).split('\n')[0]);
}

const inner = new api.InMemoryNodeStore();
const counted = new api.CountingNodeStore(inner);
const isA = typeof api.MerkleLog === 'function';
const hasher = isA ? api.createHasher(hashFn) : null;
const log = isA ? new api.MerkleLog(hasher, counted) : new api.AppendOnlyMerkleLog(hashFn, counted);

console.log('empty-root', hex(isA ? log.root() : log.root()));

const leaves = [Buffer.from('a'), Buffer.from('b'), Buffer.from('c'), Buffer.from('d')];
for (const leaf of leaves) {
  if (isA) await log.append(leaf);
  else log.append(leaf);
}
const root = log.root();
console.log('size4-root', hex(root));

if (isA) {
  const p = await log.inclusionProof(1);
  console.log('incl-ok', api.verifyInclusion(hasher, root, leaves[1], p));
  const extra = { ...p, proof: [...p.proof, new Uint8Array(hasher.hashSize)] };
  console.log('incl-extra', api.verifyInclusion(hasher, root, leaves[1], extra));
  const oldRoot = await log.rootAt(2);
  const c = await log.consistencyProof(2, 4);
  console.log('cons-ok', api.verifyConsistency(hasher, oldRoot, root, c));
} else {
  const p = log.inclusionProof(1);
  try {
    api.verifyInclusion(hashFn, p, root);
    console.log('incl-ok', true);
  } catch (e) {
    console.log('incl-ok', e.name);
  }
  const extra = { ...p, nodes: [...p.nodes, { side: 'L', hash: new Uint8Array(32) }] };
  try {
    api.verifyInclusion(hashFn, extra, root);
    console.log('incl-extra', true);
  } catch (e) {
    console.log('incl-extra', e.name + ': ' + String(e.message).split('\n')[0]);
  }
}

if (typeof api.AppendOnlyMerkleLog === 'function' && typeof api.AppendOnlyMerkleLog.open === 'function') {
  try {
    const reopened = api.AppendOnlyMerkleLog.open(hashFn, inner, 2);
    reopened.append(Buffer.from('z'));
    console.log('open-prefix', 'ok size=' + reopened.size);
  } catch (e) {
    console.log('open-prefix', String(e.message).split('\n')[0]);
  }
} else {
  console.log('open-prefix', 'no-open-api');
}
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/merkle-consistency-core.git merkle-consistency-core-A
cd merkle-consistency-core-A
npm ci
npm run build
npm test                                                          # 预期：32 passed
node verify_146.mjs                                                     # 预期：exports 含 MerkleLog,verifyInclusion,verifyInclusionProof,verifyConsistency,verifyConsistencyProof；dup-write 为 node (level=0, index=0) already stored；empty-root dbc1b4c900ffe48d；size4-root 33376a3bd63e9993；incl-ok true；incl-extra false；cons-ok true；open-prefix no-open-api
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/merkle-consistency-core.git merkle-consistency-core-B
cd merkle-consistency-core-B
npm ci
npm run build
npm test                                                          # 预期：35 passed
node verify_146.mjs                                                     # 预期：exports 含 AppendOnlyMerkleLog,verifyInclusion,verifyConsistency；dup-write accepted；empty-root 与 size4-root 与 A 相同；incl-ok true；incl-extra 为 ProofVerificationError: proof has 1 extraneous node(s)；open-prefix ok size=3
cd ..
```

---

## 第 147 题　0-1 代码生成　·　困难　·　无界面
<!-- solo-report:task=147 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/incremental-lexer-core　A 分支：https://github.com/gy-vs/incremental-lexer-core/tree/A　B 分支：https://github.com/gy-vs/incremental-lexer-core/tree/B

存为 `verify_147.mjs`（放在仓库根目录）

```javascript
import { existsSync } from 'node:fs';
import { createRequire } from 'node:module';

async function load(rel) {
  try {
    const mod = await import(rel);
    if (mod.IncrementalLexer || mod.createLexer || mod.createLexer === undefined) {
      if (mod.IncrementalLexer || mod.createLexer) return mod;
      if (mod.default && (mod.default.IncrementalLexer || mod.default.createLexer)) {
        return { ...mod.default, ...mod };
      }
    }
    return mod;
  } catch {
    return createRequire(import.meta.url)(rel);
  }
}

const api = await load('./dist/src/index.js');

function makeLexer() {
  if (typeof api.IncrementalLexer === 'function') {
    return new api.IncrementalLexer({
      rules: [
        { type: 'num', pattern: /\d+(?:\.\d+)?/, priority: 2 },
        { type: 'word', pattern: /[A-Za-z_]\w*/ },
        { type: 'dot', pattern: /\./ },
        { type: 'space', pattern: /[ \t]+/, skip: true },
        { type: 'string', pattern: /"(?:\\.|[^"\\])*"/ },
      ],
    });
  }
  return api.createLexer({
    states: {
      $: {
        name: '$',
        rules: [
          { type: 'num', pattern: /\d+(?:\.\d+)?/, priority: 2 },
          { type: 'word', pattern: /[A-Za-z_]\w*/ },
          { type: 'dot', pattern: /\./ },
          { type: 'space', pattern: /[ \t]+/, ignore: true },
          { type: 'string', pattern: /"(?:\\.|[^"\\])*"/ },
        ],
      },
    },
  });
}

const lexer = makeLexer();
const sideA = typeof lexer.setText === 'function';
const first = sideA ? lexer.setText('hello world') : lexer.tokenize('hello world');
console.log('init', first.map((t) => t.type + ':' + t.value).join('|'));
const t0 = first[0];

const upd = sideA
  ? lexer.applyEdits([{ start: 6, end: 11, text: 'there' }])
  : lexer.update([{ start: 6, end: 11, text: 'there' }]);
console.log('edit', upd.tokens.map((t) => t.type + ':' + t.value).join('|'));
console.log('identity', upd.tokens[0] === t0);
console.log('rescannedChars', upd.rescannedChars);
console.log('fellBack', upd.fellBack === undefined ? 'absent' : upd.fellBack);
console.log('reusedTokens', upd.reusedTokens === undefined ? 'absent' : upd.reusedTokens);

try {
  if (sideA) lexer.applyEdits([{ start: 0, end: 2, text: 'x' }, { start: 1, end: 3, text: 'y' }]);
  else lexer.update([{ start: 0, end: 2, text: 'x' }, { start: 1, end: 3, text: 'y' }]);
  console.log('overlap', 'accepted');
} catch (e) {
  console.log('overlap', String(e.message).split('\n')[0]);
}

const lex2 = makeLexer();
if (sideA) lex2.setText('n 1');
else lex2.tokenize('n 1');
const r2 = sideA ? lex2.applyEdits([{ start: 3, end: 3, text: '.2' }]) : lex2.update([{ start: 3, end: 3, text: '.2' }]);
console.log('merge-num', r2.tokens.map((t) => t.type + ':' + t.value).join('|'));

console.log('fuzz-file', existsSync('test/fuzz.test.ts'));

try {
  const types = await load('./dist/src/types.js');
  if (typeof types.createLexer === 'function') {
    try {
      types.createLexer({ states: {} });
      console.log('types-createLexer', 'ok');
    } catch (e) {
      console.log('types-createLexer', String(e.message).split('\n')[0]);
    }
  } else {
    console.log('types-createLexer', 'absent');
  }
} catch {
  console.log('types-createLexer', 'no-module');
}
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/incremental-lexer-core.git incremental-lexer-core-A
cd incremental-lexer-core-A
npm ci
npm run build
node --test (Get-ChildItem dist/test/*.test.js).FullName                                                          # 预期：37 passed
node verify_147.mjs                                                     # 预期：init word:hello|word:world；edit word:hello|word:there；identity true；rescannedChars 5；fellBack absent；reusedTokens absent；overlap Overlapping edits: [0, 2) and [1, 3)；merge-num word:n|num:1.2；fuzz-file true；types-createLexer absent
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/incremental-lexer-core.git incremental-lexer-core-B
cd incremental-lexer-core-B
npm ci
npm run build
npm test                                                          # 预期：22 passed
node verify_147.mjs                                                     # 预期：init 与 edit 与 identity 与 A 相同；rescannedChars 6；fellBack false；reusedTokens 1；overlap 批量编辑不得重叠（相邻/首尾相接允许）；merge-num 与 A 相同；fuzz-file false；types-createLexer createLexer 由 ./incremental-lexer 提供，请从包入口导入
cd ..
```

---

## 第 148 题　Bug 修复　·　困难　·　全栈
<!-- solo-report:task=148 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/api-header-sequence-web　A 分支：https://github.com/gy-vs/api-header-sequence-web/tree/A　B 分支：https://github.com/gy-vs/api-header-sequence-web/tree/B

服务：`npm run dev` 同时起后端 4174 与前端 4173；浏览器开 http://localhost:4173。被占用会自动 +1，以新窗口打出的 Local: 地址为准。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/api-header-sequence-web.git api-header-sequence-web-A
cd api-header-sequence-web-A
npm ci
npm test                                                       # 预期：测试通过（headers + api）
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                              # 浏览器打开后按下面「界面操作」走
Invoke-RestMethod http://127.0.0.1:4174/api/scenarios/alpha | ConvertTo-Json -Compress   # 预期：revision 3，headers 含两行 Set-Cookie 且保留 h-seed-* 行 id
Invoke-RestMethod http://127.0.0.1:4174/api/scenarios/alpha/replay | ConvertTo-Json -Compress   # 预期：线级重放正文 {"ok":true}（不是预览 JSON）
try { Invoke-RestMethod http://127.0.0.1:4174/api/scenarios/alpha/replay/step-alpha-1 } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404（A 没有按 stepId 的重放路由）
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:4173，左栏「Items」有 Primary / Secondary request sequences。状态从 Loading 到 Loaded。中间工具栏「Save」「Replay」。
2. 打开 alpha，看到两行「Set-Cookie」（sid=alpha 与 theme=dark）以及 X-Trace。点「Add header」新增一行，占位「Set-Cookie」。右栏「Preview」默认可切「Wire lines」/「Merged view」；Merged 下提示 Set-Cookie 保持独立行。
3. 点「Replay」，状态「Replaying」再「Replayed」，「Replayed response」显示 HTTP/1.1 200 与正文。A：writeHead 按原始行写出，重复 Set-Cookie 与大小写都保留；B：GET `/replay` 只给 JSON 预览，线级 `res.append` 会把同名不同大小写折成一个键。
4. 用「Drag to reorder」或「Move up / Move down」把 X-Trace 拖到两行 Set-Cookie 中间，点「Save」，状态「Saved」。刷新后再打开，行序与行 id 不变。打开 beta（仍是旧对象格式）观察迁移后的多值 Set-Cookie；A：首次重存前行 id 不跨请求稳定。
5. 复制页面，两个标签页都改一行后先后保存。后保存的一侧状态「Revision conflict」。A：可点「Reload theirs」或「Overwrite with mine」；B：只有「Reload newest」，没有保留本地后覆盖的路径。
6. 拖动过程中观察行样式。A：dragId 在 ref 上，拖动时不会出现 dragging 高亮；B：有「Duplicate field name (case-insensitive)」提示。
7. 回到终端执行剩下的接口命令并 `taskkill`。可用 `(Invoke-WebRequest -UseBasicParsing http://127.0.0.1:4174/api/scenarios/alpha/replay).Headers` 核对 A 的重复 Set-Cookie。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/api-header-sequence-web.git api-header-sequence-web-B
cd api-header-sequence-web-B
npm ci
npm test                                                       # 预期：测试通过
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                              # 浏览器打开后按下面「界面操作」走
Invoke-RestMethod http://127.0.0.1:4174/api/scenarios/alpha | ConvertTo-Json -Compress   # 预期：revision 3，steps 含 step-alpha-1，响应头已从旧对象迁成有序行
Invoke-RestMethod http://127.0.0.1:4174/api/scenarios/alpha/replay | ConvertTo-Json -Compress   # 预期：JSON {id,revision,steps}，raw/merged 预览，不是线级 HTTP 响应
try { Invoke-RestMethod http://127.0.0.1:4174/api/scenarios/alpha/replay/step-alpha-1 } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：200，正文 {"ok":true}；同名头被 Node 折成单键
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 3、5、6 步。B 有「Add step」「Add row」，分区「Request headers / Response headers」，右栏「Replay preview」主要是 merged 视图。

---

## 第 149 题　Feature 迭代　·　困难　·　全栈
<!-- solo-report:task=149 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/api-sequence-binding-web　A 分支：https://github.com/gy-vs/api-sequence-binding-web/tree/A　B 分支：https://github.com/gy-vs/api-sequence-binding-web/tree/B

服务：`npm run dev` 同时起后端 4174 与前端 4173；浏览器开 http://localhost:4173。被占用会自动 +1，以新窗口打出的 Local: 地址为准。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/api-sequence-binding-web.git api-sequence-binding-web-A
cd api-sequence-binding-web-A
npm ci
npm test                                                       # 预期：取消与完成竞争的用例会超时，整次测试不能全绿
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                              # 浏览器打开后按下面「界面操作」走
Invoke-RestMethod http://127.0.0.1:4174/api/scenarios/alpha/runs | ConvertTo-Json -Compress   # 预期：{"runs":[]}；跑过场景后 runs 数组有记录（服务端有按场景列运行接口）
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/scenarios/alpha/runs -ContentType "application/json" -Body '{"revision":1}' } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：409，message 含 场景已被修改（当前 revision 3）
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/scenarios/alpha/runs -ContentType "application/json" -Body '{}' | ConvertTo-Json -Compress   # 预期：201，status 为 running，pinned revision 3
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:4173，左栏场景「Primary request sequences」，状态「加载中」后「已加载」。工具栏「保存」「分析」「运行场景」。
2. 查看步骤「登录并取 token」等，头名称/URL 里有 `{{baseUrl}}`、`{{token}}`。右侧「编辑期实时检查」列出未定义引用。点「分析」，状态「分析中」再「分析完成」。
3. 点「运行场景」，切到「运行」页。A：RunView 把每步引用的原始值与转换结果列成表，有「取消运行」；运行标识只记在 localStorage，没有运行列表，清存储或换浏览器就看不到已完成运行。B：按钮是「Run」「Cancel」，右侧「Runs」列表可刷新后再看完结步骤。
4. 运行中点「取消运行」。终态只能是取消或完成之一。A：取消与最后一步竞争的测试闸门未修通，界面上观察是否卡在「已请求取消…」；B：终态由带守卫的迁移独占，取消与完成相撞只落一个终态。
5. 点「添加步骤」后「上移」「下移」。B：点两次「Header」会插入两个空键，对象存储把它们合并成一个，同名请求头无法表达。A：请求头是数组，可并存两行。
6. 不保存就点运行。A：提示「有未保存修改：运行使用已保存的 revision，请先保存」。改场景后用旧 revision 再运行会「场景已被修改，请重新加载后再运行」。
7. 回到终端执行剩下的接口命令并 `taskkill`。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/api-sequence-binding-web.git api-sequence-binding-web-B
cd api-sequence-binding-web-B
npm ci
npm test                                                       # 预期：测试通过
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                              # 浏览器打开后按下面「界面操作」走
Invoke-RestMethod http://127.0.0.1:4174/api/scenarios/alpha/runs | ConvertTo-Json -Compress   # 预期：[]（数组而不是 {runs:…}）
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/scenarios/alpha/runs -ContentType "application/json" -Body '{"revision":1}' } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：201（B 认 expectedRevision，忽略 revision 字段）
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/scenarios/alpha/runs -ContentType "application/json" -Body '{}' | ConvertTo-Json -Compress   # 预期：201，status 为 running，definition 已按当前 revision 快照
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 3、4、5 步。B 文案是 Save / Analyze / Run / Add step / Move up / Move down / Delete step。

---

## 第 150 题　Bug 修复　·　困难　·　全栈
<!-- solo-report:task=150 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/api-multipart-preview-web　A 分支：https://github.com/gy-vs/api-multipart-preview-web/tree/A　B 分支：https://github.com/gy-vs/api-multipart-preview-web/tree/B

服务：`npm run dev` 同时起后端 4174 与前端 4173；浏览器开 http://localhost:4173。被占用会自动 +1，以新窗口打出的 Local: 地址为准。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/api-multipart-preview-web.git api-multipart-preview-web-A
cd api-multipart-preview-web-A
npm ci
npm test                                                       # 预期：测试通过（multipart + api）
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                              # 浏览器打开后按下面「界面操作」走
(Invoke-WebRequest -UseBasicParsing http://127.0.0.1:4174/api/scenarios/alpha/request.bin).Headers['Content-Type']   # 预期：application/octet-stream（无 boundary，也无 Content-Disposition）
try { Invoke-RestMethod http://127.0.0.1:4174/api/scenarios/alpha/request } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404（A 的下载路径是 request.bin）
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/scenarios/alpha/analyze -ContentType "application/json" -Body '{}' | ConvertTo-Json -Compress   # 预期：{id:alpha,revision:3,lines:…}；界面上没有 Analyze 按钮
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:4173，顶栏「API Scenario Studio」，左栏「Items」选中 Primary request sequences，状态 Loaded。中间「Save」「Text field」「Binary part」「Download & verify」。工具栏没有「Analyze」。
2. 看到文本 part `note` 与二进制 `payload`，文件名含「固件-β.bin」，摘要是字节数 + fnv1a，而不是把二进制当字符串整段显示。右栏「Summary」列出 Boundary / Parts / Serialized。
3. 点「Save」，状态「Saved revision 4」。再点「Download & verify」。A：只出现一行 `Verified: N bytes from the server are identical to the editor draft.`（或 Mismatch），浏览器不会下载文件；B：状态 Verifying，然后「Bytes identical」并排 local/server 散列，再出现「Download」把服务端字节存成附件。
4. 点「Analyze」。A：没有该按钮，服务端 `/analyze` 仍在但界面触达不到；B：按钮「Analyze」，状态 Analyzing 后 Ready，右栏「Analysis」还在。
5. 切到 beta（无 multipart），再点「Download & verify」。A：`Nothing saved to download yet`；B：`No stored multipart body`。回到 alpha，手工改 Boundary 与 payload 冲突后点 Save，A：校验失败写在 problem 区；B：非法 boundary 会禁用保存。
6. 点「Binary part」再选文件，确认预览仍是摘要而非完整二进制字符串。回到终端执行剩下的接口命令并 `taskkill`。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/api-multipart-preview-web.git api-multipart-preview-web-B
cd api-multipart-preview-web-B
npm ci
npm test                                                       # 预期：测试通过
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                              # 浏览器打开后按下面「界面操作」走
try { Invoke-WebRequest -UseBasicParsing http://127.0.0.1:4174/api/scenarios/alpha/request.bin | Out-Null } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404（B 的下载路径是 /request）
(Invoke-WebRequest -UseBasicParsing http://127.0.0.1:4174/api/scenarios/alpha/request).Headers['Content-Type']   # 预期：multipart/form-data; boundary=…，并带 Content-Disposition 附件名
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/scenarios/alpha/analyze -ContentType "application/json" -Body '{}' | ConvertTo-Json -Compress   # 预期：{id:alpha,revision:3,lines:…}；lines 统计的是摘要行（保存时 content 被 summarizePart 覆盖）
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 1、3、4 步。B 另有 Boundary 的 auto/manual 切换；保存成功文案「Saved revision N」。

---

## 第 151 题　Feature 迭代　·　困难　·　全栈
<!-- solo-report:task=151 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/api-fault-profile-web　A 分支：https://github.com/gy-vs/api-fault-profile-web/tree/A　B 分支：https://github.com/gy-vs/api-fault-profile-web/tree/B

服务：`npm run dev` 同时起后端 4174 与前端 4173；浏览器开 http://localhost:4173。前端端口被占用会自动 +1，以新窗口打出的 Local: 地址为准。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/api-fault-profile-web.git api-fault-profile-web-A
cd api-fault-profile-web-A
npm ci
npm test                                                                 # 预期：30 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                                      # 浏览器打开后按下面「界面操作」走
Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | ConvertTo-Json -Compress   # 预期：{"family":"api-scenario","count":2}
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/scenarios/alpha/faults/preview -ContentType "application/json" -Body '{"config":{"seed":7,"fixedDelayMs":100}}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：200，body 含 plan.events 与稳定 id
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/scenarios/alpha/runs -ContentType "application/json" -Body '{"freeze":"draft","config":{"seed":7,"fixedDelayMs":100}}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：201，config.seed 为 7 且 configRevision 升到 2
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:4173，左栏 Items 看到 Primary request sequences，中间栏标题为 API Scenario Studio。
2. 确认已选中 alpha。中间面板文本域下方看到 Fault injection 表单，字段包括 Seed、Fixed delay ms、Jitter ±ms。
3. 不要点「Save config (rev 1)」。把 Seed 改成 `7`，点击「Preview plan」。右侧 Inspection 出现 Plan preview，事件带稳定 id。A：预览按种子 7；B：点「Preview plan」同样可预览草稿，状态行类似 Plan ready — deterministic for seed 7。
4. 仍不保存，直接点「Start run」。A：状态栏显示 Run started，表单变灰并出现 frozen while run is active，本次按种子 7 冻结且 revision 提升；B：无「Start run」，点「Run」只提交已保存 revision，草稿种子被丢掉，提示 Save the config first 或仍按 seed 1 开跑。
5. 运行中点「Cancel run」（在 fieldset 外）。A：按钮可用，轨迹里已发分块保留、未触发项停止；B：对应按钮文案是「Cancel」，Cancel 在按钮行内，运行中可用。
6. 回到终端执行剩下的接口命令并关服务。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/api-fault-profile-web.git api-fault-profile-web-B
cd api-fault-profile-web-B
npm ci
npm test                                                                 # 预期：12 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                                      # 浏览器打开后按下面「界面操作」走
Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | ConvertTo-Json -Compress   # 预期：{"family":"api-scenario","count":2}
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/scenarios/alpha/faults/preview -ContentType "application/json" -Body '{"config":{"seed":7,"fixedDelayMs":100}}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/scenarios/alpha/runs -ContentType "application/json" -Body '{"freeze":"draft","config":{"seed":7,"fixedDelayMs":100}}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：400，error 为 invalid_revision
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 3、4、5 步。B 侧故障区按钮是「Save」「Preview plan」「Run」「Cancel」，另有 title 为 Randomize seed 的骰子按钮；未先 Save 就 Run 不会冻结草稿。

---

## 第 153 题　Feature 迭代　·　困难　·　全栈
<!-- solo-report:task=153 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/search-experiment-compare-web　A 分支：https://github.com/gy-vs/search-experiment-compare-web/tree/A　B 分支：https://github.com/gy-vs/search-experiment-compare-web/tree/B

服务：`npm run dev` 同时起后端 4174 与前端 4173；浏览器开 http://localhost:4173。前端端口被占用会自动 +1，以新窗口打出的 Local: 地址为准。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/search-experiment-compare-web.git search-experiment-compare-web-A
cd search-experiment-compare-web-A
npm ci
npm test                                                                 # 预期：27 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/experiments | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                                      # 浏览器打开后按下面「界面操作」走
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/experiments -ContentType "application/json" -Body '{"querySet":["alpha","faq"],"a":{"name":"A","weights":{"title":3,"body":1,"tags":2}},"b":{"name":"B","weights":{"title":0,"body":0,"tags":0}},"topK":5}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：201，body 含 id、snapshotId、corpusRevision
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/corpus/reindex -ContentType "application/json" -Body '{}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：200，索引 revision 前进，已创建实验仍钉在旧快照
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/snapshots/missing/reclaim -ContentType "application/json" -Body '{}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：200 或空 reclaimed 列表（接口存在）
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:4173，左侧看到 New experiment 与查询集合输入（「Queries, one per line」），默认可含 `alpha !fail:b`。
2. 保留或填入两行查询，调整 A / B 的 title/body/tags 权重，点击「run both sides」。结果行按查询原顺序落位，统计条出现 comparable queries 与 totalQueries 分母。
3. 展开任意一行看 rank Δ。A：可用 `!fail:a` / `!fail:b` 人为制造单侧失败；B：查询集合写死，单侧失败只能靠预设的 flaky parser 行，无自定义查询框。
4. 点顶栏「advance index」。A：运行中实验仍绑定创建时的快照 revision；B：无此按钮，对应的是左下「Simulate index update」，提示 pinned snapshot 仍用于本次运行。
5. 实验终止后点「reclaim snapshot」。A：横幅 Snapshot reclaimed: results stay viewable, replay is unavailable，「replay」按钮禁用；B：没有可点的回收入口，只能等 TTL，按钮是「Re-run」。
6. 回到终端执行剩下的接口命令并关服务。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/search-experiment-compare-web.git search-experiment-compare-web-B
cd search-experiment-compare-web-B
npm ci
npm test                                                                 # 预期：26 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/experiments | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                                      # 浏览器打开后按下面「界面操作」走
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/experiments -ContentType "application/json" -Body '{"querySet":["alpha","faq"],"a":{"name":"A","weights":{"title":3,"body":1,"tags":2}},"b":{"name":"B","weights":{"title":0,"body":0,"tags":0}},"topK":5}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404（对比实验挂在 /api/compare/experiments）
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/corpus/reindex -ContentType "application/json" -Body '{}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/snapshots/missing/reclaim -ContentType "application/json" -Body '{}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 3、4、5 步。B 侧主按钮是「Run comparison」「Simulate index update」「Cancel」「Re-run」；开始对比前在左侧选 Side A / Side B 预设配置，不能编辑查询集合。

---

## 第 154 题　Bug 修复　·　困难　·　全栈
<!-- solo-report:task=154 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/search-highlight-offset-web　A 分支：https://github.com/gy-vs/search-highlight-offset-web/tree/A　B 分支：https://github.com/gy-vs/search-highlight-offset-web/tree/B

服务：`npm run dev` 同时起后端 4174 与前端 4173；浏览器开 http://localhost:4173。前端端口被占用会自动 +1，以新窗口打出的 Local: 地址为准。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/search-highlight-offset-web.git search-highlight-offset-web-A
cd search-highlight-offset-web-A
npm ci
npm test                                                                 # 预期：观察 Tests 行（GSB 称 textMapping.test.ts 曾 Transform failed；若套件能跑则核对 ß/café/emoji 用例）
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                                      # 浏览器打开后按下面「界面操作」走
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/search -ContentType "application/json" -Body '{"query":"cafe","caseFold":true,"stripMarks":true}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：200，results 含 cafe，snippet 高亮覆盖 NFC/NFD 的 cafe
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/search -ContentType "application/json" -Body '{"query":"irmak","caseFold":true,"turkish":true}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：200，results 含 takim（土耳其开关存在）
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/experiments/gamma/search -ContentType "application/json" -Body '{"query":"strasse"}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:4173，标题 Search Relevance Lab，右侧面板标题 Search workbench。
2. 在 aria-label「Search query」的输入框里输入 `grösse`。A：防抖自动搜索，无需点按钮，结果行 mark 完整覆盖 Größe；B：无 Search workbench 跨记录面板，需先选中 gamma 再点「Search」。
3. 勾选「Case fold (ß→ss)」「Strip diacritics」，再勾上「Turkish I」，输入 `irmak`。A：出现 Turkish I 开关，结果随 turkish 变化（GSB 指出四种 I 会塌缩到同一点）；B：没有 Turkish I 复选框。
4. 输入家庭 emoji 或 `cafe`，滚动结果列表。A：虚拟列表复用行时高亮来自当前 props，不沿用上一行；B：高亮在当前记录的 Highlight preview 与右侧片段列表里看。
5. 切到左栏另一条记录再搜。A：跨记录检索仍列出多条；B：搜索只针对当前记录，空查询点 Search 返回 400。
6. 回到终端执行剩下的接口命令并关服务。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/search-highlight-offset-web.git search-highlight-offset-web-B
cd search-highlight-offset-web-B
npm ci
npm test                                                                 # 预期：43 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                                      # 浏览器打开后按下面「界面操作」走
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/search -ContentType "application/json" -Body '{"query":"cafe","caseFold":true,"stripMarks":true}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/search -ContentType "application/json" -Body '{"query":"irmak","caseFold":true,"turkish":true}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/experiments/gamma/search -ContentType "application/json" -Body '{"query":"strasse"}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：200，hits 为 [{start:0,end:6},{start:11,end:18}]，原文切片 Straße 与 STRASSE
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 2、3、5 步。B 侧先在左栏点 I18N folding fixtures（gamma），工具条输入框 placeholder 为 Search (case/diacritic folding)，回车或点「Search」；编辑区下方有 Highlight preview。

---

## 第 156 题　Bug 修复　·　困难　·　全栈
<!-- solo-report:task=156 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/search-stable-page-web　A 分支：https://github.com/gy-vs/search-stable-page-web/tree/A　B 分支：https://github.com/gy-vs/search-stable-page-web/tree/B

服务：`npm run dev` 同时起后端 4174 与前端 4173；浏览器开 http://localhost:4173。前端端口被占用会自动 +1，以新窗口打出的 Local: 地址为准。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/search-stable-page-web.git search-stable-page-web-A
cd search-stable-page-web-A
npm ci
npm test                                                                 # 预期：15 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                                      # 浏览器打开后按下面「界面操作」走
Invoke-RestMethod 'http://127.0.0.1:4174/api/search?pageSize=5' | ConvertTo-Json -Compress   # 预期：200，items 长度 5 且带 nextCursor、revision
try { Invoke-RestMethod 'http://127.0.0.1:4174/api/search?pageSize=5&cursor=nope' } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：409，error.code 为 invalid_cursor
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/docs -ContentType "application/json" -Body '{"id":"doc-verify","title":"ranking","content":"ranking","tags":[]}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：201，revision 前进
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:4173，标题 Search Relevance Lab，副标题 稳定游标分页工作台。A：没有 Judgments 页签，原实验编辑界面被去掉；B：顶栏有「搜索工作台」和「Judgments」两个页签，默认停在搜索工作台。
2. 直接点「加载更多」连续翻页。同分区间内文档不重复、不漏；快速连点时按钮在 loading 时禁用。
3. 在「新文档 id」留空或填 `doc-verify`，点「新增文档」。出现提示 索引已变更，revision=…。再点「加载更多」。A：横幅 结果已失效，并保留当前条数，点「刷新重检」才重查；B：横幅 索引已更新，当前列表已过期，点「刷新并重新开始」。
4. 加载尚未结束时改「查询词」再立刻点「重新检索」。A：pager 无世代号，飞在路上的旧响应可能写回旧结果与旧游标；B：#gen 丢弃迟到响应，界面不会拼两套结果。
5. 切分数升降序或改「标签筛选」后再检索，旧游标被拒。A：按钮文案是「分数降序（切换）」/「重新检索」；B：是「分数高→低」「分数低→高」和「搜索」。
6. 回到终端执行剩下的接口命令并关服务。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/search-stable-page-web.git search-stable-page-web-B
cd search-stable-page-web-B
npm ci
npm test                                                                 # 预期：21 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                                      # 浏览器打开后按下面「界面操作」走
Invoke-RestMethod 'http://127.0.0.1:4174/api/search?pageSize=5' | ConvertTo-Json -Compress   # 预期：200，ok 为 true，items 长度 5 且带 nextCursor
try { Invoke-RestMethod 'http://127.0.0.1:4174/api/search?pageSize=5&cursor=nope' } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：400，error 为 malformed_cursor
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/docs -ContentType "application/json" -Body '{"id":"doc-verify","title":"ranking","content":"ranking","tags":[]}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404（增删在 /api/search/docs）
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 1、3、4、5 步。B 侧新增文档需走接口或后续操作推进 revision；界面主按钮是「搜索」「加载更多」「刷新」「刷新并重新开始」。

---

## 第 157 题　Feature 迭代　·　困难　·　全栈
<!-- solo-report:task=157 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/search-rule-sandbox-web　A 分支：https://github.com/gy-vs/search-rule-sandbox-web/tree/A　B 分支：https://github.com/gy-vs/search-rule-sandbox-web/tree/B

服务：`npm run dev` 同时起后端 4174 与前端 4173；浏览器开 http://localhost:4173。前端端口被占用会自动 +1，以新窗口打出的 Local: 地址为准。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/search-rule-sandbox-web.git search-rule-sandbox-web-A
cd search-rule-sandbox-web-A
npm ci
npm test                                                                 # 预期：29 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                                      # 浏览器打开后按下面「界面操作」走
Invoke-RestMethod http://127.0.0.1:4174/api/experiments/alpha | ConvertTo-Json -Compress   # 预期：200，含 rules、samples、revision
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/experiments/alpha/simulate -ContentType "application/json" -Body '{"rules":[],"samples":[],"draftHash":"0"}' } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：409，error 为 draft_hash_mismatch
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/experiments/alpha/simulate-saved -ContentType "application/json" -Body '{}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:4173，左栏实验列表默认选中 alpha，侧栏显示草稿哈希以及 Matches saved revision 或 Unsaved changes。
2. 在规则区用 title 为「Add rule」的按钮新增规则，匹配类型可选 exact / prefix / regex。点 title「Move up」「Move down」重排。A：列表按 priority 降序显示，上下移动靠改 priority 数值，可能与编译序（窄作用域、exact>prefix>regex）不一致；B：无 prefix，按列表顺序编译，右侧有编译顺序徽章。
3. 点击「Simulate」。右侧出现诊断与每个样例的决策链，点击链上规则会滚到对应卡片。
4. 模拟完成后改任意字段。A：旧结果变灰，提示 Draft changed since this run — these results belong to an older draft and will not be applied. Simulate again；B：草稿一变就把模拟态清回 idle，点「模拟」时若哈希尚未回填会看到 Simulation rejected / draft_hash_mismatch，需再点一次。
5. 点击「Diff vs saved」。A：只列出 added / removed / changed 与一句 sample queries changed，看不出位次移动；B：切到「对比 revN」，能看到新增、删除、字段级修改和「样例重排」/规则 moved。
6. 回到终端执行剩下的接口命令并关服务。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/search-rule-sandbox-web.git search-rule-sandbox-web-B
cd search-rule-sandbox-web-B
npm ci
npm test                                                                 # 预期：观察 passed 数
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                                      # 浏览器打开后按下面「界面操作」走
Invoke-RestMethod http://127.0.0.1:4174/api/experiments/alpha | ConvertTo-Json -Compress   # 预期：200，含 rules、samples、revision
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/experiments/alpha/simulate -ContentType "application/json" -Body '{"rules":[],"samples":[],"draftHash":"0"}' } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：409，error 为 draft_hash_mismatch
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/experiments/alpha/simulate-saved -ContentType "application/json" -Body '{}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：200，按已保存 revision 模拟，含 compiledOrder
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 2、4、5 步。B 侧工具条是「保存」「模拟」，规则页签有「重写」「固定」「降权/过滤」，排序按钮 aria-label 为「上移」「下移」，右侧页签为「模拟」「对比 revN」「诊断」。

---

## 第 159 题　Feature 迭代　·　困难　·　全栈
<!-- solo-report:task=159 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/subtitle-ripple-group-web　A 分支：https://github.com/gy-vs/subtitle-ripple-group-web/tree/A　B 分支：https://github.com/gy-vs/subtitle-ripple-group-web/tree/B

服务：`npm run dev` 同时起后端 4174 与前端 4173；浏览器开 http://localhost:4173。前端端口被占用会自动 +1，以新窗口打出的 Local: 地址为准。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/subtitle-ripple-group-web.git subtitle-ripple-group-web-A
cd subtitle-ripple-group-web-A
npm ci
npm test                                                                 # 预期：25 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                                      # 浏览器打开后按下面「界面操作」走
Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | ConvertTo-Json -Compress   # 预期：含 family 与 count
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/tracks/alpha/debug/external-touch -ContentType "application/json" -Body '{"offset":100}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：200，track.revision 前进，changed 列出被推开的 cue
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/tracks/alpha/operations -ContentType "application/json" -Body '{}' } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：400 或 422（接口存在，缺 intent）
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:4173，左栏选择一条 track，时间轴出现若干 cue。
2. 点选 cue，Shift 点选构造多个区间；拖动 cue 主体做 ripple，拖左右 handle 做 trim。点 cue 上的 locked 图标设屏障后再拖，传播停在锁定项前。
3. 点工具栏「Simulate other page edit」推进 revision，再拖相关 cue。A：出现最小冲突集合横幅，点「Replay on rev N」基于新版本重放，或丢弃意图；B：没有该按钮，需另开标签页制造冲突，横幅按钮是「Refresh & replay intent」和「Dismiss」。
4. 点「Undo」。A：提交成功后才弹栈，冲突时历史仍在，也有「Redo」；B：先切掉栈顶再提交，若这次逆意图返回 409，被撤销条目已丢而轨道未变，且没有 Redo。
5. 再拖一次被夹到零位移的手势。A：不产生撤销记录、revision 不增加；B：观察状态栏本地预测位移量是否为 0。
6. 回到终端执行剩下的接口命令并关服务。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/subtitle-ripple-group-web.git subtitle-ripple-group-web-B
cd subtitle-ripple-group-web-B
npm ci
npm test                                                                 # 预期：观察 passed 数
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                                      # 浏览器打开后按下面「界面操作」走
Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | ConvertTo-Json -Compress   # 预期：含 family 与 count
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/tracks/alpha/debug/external-touch -ContentType "application/json" -Body '{"offset":100}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/tracks/alpha/operations -ContentType "application/json" -Body '{}' } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404（提交走 /api/tracks/:id/intent）
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 3、4 步。B 侧工具栏主要是「Undo」；并发冲突用两个标签页，第二个标签移动 cue 后回到第一个再拖。

---

## 第 160 题　Bug 修复　·　困难　·　全栈
<!-- solo-report:task=160 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/subtitle-grapheme-split-web　A 分支：https://github.com/gy-vs/subtitle-grapheme-split-web/tree/A　B 分支：https://github.com/gy-vs/subtitle-grapheme-split-web/tree/B

服务：`npm run dev` 同时起后端 4174 与前端 4173；浏览器开 http://localhost:4173。前端端口被占用会自动 +1，以新窗口打出的 Local: 地址为准。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/subtitle-grapheme-split-web.git subtitle-grapheme-split-web-A
cd subtitle-grapheme-split-web-A
npm ci
npm test                                                                 # 预期：49 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                                      # 浏览器打开后按下面「界面操作」走
Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | ConvertTo-Json -Compress   # 预期：family 为 subtitle-timing，count 为轨道条数（cue 模型）
try { Invoke-RestMethod http://127.0.0.1:4174/api/cues | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/tracks/gamma/split -ContentType "application/json" -Body '{"cueId":"missing","position":0,"revision":1}' } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：409 或 404/400，error 为 revision_conflict / cue_not_found / empty_cue / invalid_position（拆分接口存在，拒绝空 cue 与首尾）
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:4173，左侧 Items 列出 alpha、beta、gamma。
2. 选 gamma。A：状态栏出现 migrated from utf16 coordinates，旧 UTF-16 标注已折算；B：左栏是 cue-family、cue-flags、cue-nfd、cue-bidi、cue-empty、cue-legacy，选 cue-legacy 才出迁移横幅。
3. 在某条 cue 文本里把光标点进 emoji / 旗帜 / 组合字符内部。A：下方提示 Caret: grapheme x/y — snapped from UTF-16 offset …；B：显示 utf16 → grapheme 以及 mid-cluster 吸附。
4. 光标在首尾时看拆分按钮。A：按钮文案「Split at grapheme N」，首尾禁用，不会产出空 cue；B：按钮是「Split at cursor」，首尾算合法拆分位，可得到空 cue，空 cue 还能再拆。
5. 点拆分，再点「Undo」，然后「Save」，刷新页面。A：Undo 只在当前会话快照里，刷新后不能再撤；B：Undo 打 POST /api/undo，刷新后仍可撤。两边保存后再载入，文本与标注应与撤销后一致。
6. 回到终端执行剩下的接口命令并关服务。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/subtitle-grapheme-split-web.git subtitle-grapheme-split-web-B
cd subtitle-grapheme-split-web-B
npm ci
npm test                                                                 # 预期：观察 passed 数
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                                      # 浏览器打开后按下面「界面操作」走
Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | ConvertTo-Json -Compress   # 预期：family 为 subtitle-timing，count 仍按旧 rows.length 报数，与 cue 列表条数不一致
try { Invoke-RestMethod http://127.0.0.1:4174/api/cues | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：200，列表含 cue-family、cue-empty、cue-legacy
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/tracks/gamma/split -ContentType "application/json" -Body '{"cueId":"missing","position":0,"revision":1}' } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404（拆分在 /api/cues/:id/split）
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 2、4、5 步。B 侧工具条是「Save」「Split at cursor」「Undo」；拆分后中栏出现拆分报告。

---

## 第 161 题　Feature 迭代　·　困难　·　全栈
<!-- solo-report:task=161 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/subtitle-alignment-session-web　A 分支：https://github.com/gy-vs/subtitle-alignment-session-web/tree/A　B 分支：https://github.com/gy-vs/subtitle-alignment-session-web/tree/B

服务：`npm run dev` 同时起后端 4174 与前端 4173；浏览器开 http://localhost:4173。前端端口被占用会自动 +1，以新窗口打出的 Local: 地址为准。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/subtitle-alignment-session-web.git subtitle-alignment-session-web-A
cd subtitle-alignment-session-web-A
npm ci
npm test                                                                 # 预期：23 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                                      # 浏览器打开后按下面「界面操作」走
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/tracks/alpha/alignment-sessions -ContentType "application/json" -Body '{"aligner":"default"}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：201，body 含 id 与钉住的 revision
try { Invoke-RestMethod -Method Delete -Uri http://127.0.0.1:4174/api/tracks/beta | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：无输出（204）
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:4173，副标题 Aligner review workbench，左栏默认加载 alpha。A：工具条有「Align」「Cancel session」「Save cues」；B：仍是原编辑器，只有「Save」「Analyze」，看不到对齐复核。
2. 点击「Align」。cue 表格按轨道顺序出现 Suggestion 列，基线仍匹配的建议被自动应用，其余落到 Conflict，显示置信度。B：无 Align 按钮，点了也不会发会话。
3. 在冲突行的 tweak 输入框改起止时间，点「Accept」；对另一条点「Reject」。A：接受带微调，拒绝回滚基线；B：表格里没有 Accept / Reject。
4. 切换 Review queue 下的状态页签。A：筛选只改变可见行，不丢未保存微调；B：没有 Review queue。
5. 点「Cancel session」。迟到建议以 Ignored 出现。A：取消为终态；B：没有该按钮。若要看轨道删除，终端 DELETE 后会话事件变 410。
6. 回到终端执行剩下的接口命令并关服务。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/subtitle-alignment-session-web.git subtitle-alignment-session-web-B
cd subtitle-alignment-session-web-B
npm ci
npm test                                                                 # 预期：观察 passed 数（含 review-session 单测，无真实会话端点）
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                                      # 浏览器打开后按下面「界面操作」走
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/tracks/alpha/alignment-sessions -ContentType "application/json" -Body '{"aligner":"default"}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
try { Invoke-RestMethod -Method Delete -Uri http://127.0.0.1:4174/api/tracks/beta | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 1、2、3、4、5 步。B 侧页面仍是 Subtitle Timing Studio 的 Items / Save / Analyze / Content，useReviewItems 未被任何组件引用。

---

## 第 162 题　Bug 修复　·　困难　·　全栈
<!-- solo-report:task=162 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/subtitle-webvtt-roundtrip-web　A 分支：https://github.com/gy-vs/subtitle-webvtt-roundtrip-web/tree/A　B 分支：https://github.com/gy-vs/subtitle-webvtt-roundtrip-web/tree/B

服务：`npm run dev` 同时起后端 4174 与前端 4173；浏览器开 http://localhost:4173。被占用会自动 +1，以新窗口打出的 Local: 地址为准。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/subtitle-webvtt-roundtrip-web.git subtitle-webvtt-roundtrip-web-A
cd subtitle-webvtt-roundtrip-web-A
npm ci
npm test                                                                 # 预期：38 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/tracks | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                                      # 浏览器打开后按下面「界面操作」走
Invoke-RestMethod http://127.0.0.1:4174/api/tracks | ConvertTo-Json -Compress   # 预期：含 id=alpha name=Primary timed cues
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/vtt/parse -ContentType "application/json" -Body '{"content":"WEBVTT\n\n00:00:01.000 --> 00:00:04.000 vertical:rl line:10\nhi"}' | ConvertTo-Json -Compress   # 预期：解析出 cue，vertical/line 在结构化字段里
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/vtt/patch -ContentType "application/json" -Body '{"content":"WEBVTT\n\n00:00:01.000 --> 00:00:04.000 vertical:rl line:10\nhi","cueIndex":0,"patch":{"start":"00:00:02.000"}}' | ConvertTo-Json -Compress   # 预期：ops 为空，content 仍以 00:00:01.000 开头，vertical:rl line:10 仍在
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/vtt/serialize -ContentType "application/json" -Body '{"content":"WEBVTT\n\n00:00:01.000 --> 00:00:04.000 vertical:rl line:10\nhi"}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：200，content 含 vertical:rl line:10
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/vtt/patch -ContentType "application/json" -Body '{"content":"WEBVTT\n\n00:00:01.000 --> 00:00:04.000 vertical:rl line:10\nhi","cueIndex":0,"patch":{"start":"nope"}}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：200，未改时间（没有 ops）
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:4173，看到标题 Subtitle Timing Studio 与小字 WebVTT fidelity editing，左侧 Items 有「Primary timed cues」。
2. 点击「Primary timed cues」，工具栏有「Save」「Analyze」，状态栏显示 Loaded。中间同时有原文 textarea（aria-label Content）和按块渲染的表单。
3. 在第一条 cue 的「start」输入框里逐位改时间（插入或删掉一位）。A：onChange 只在合法时间戳时写回，中间态被丢掉，输入立刻被模型值覆盖，逐位编辑走不通；B：本地缓冲可逐位输入，失焦或回车后状态栏显示 Updated cue #1。
4. 查看 REGION 块。A：badge 为 region #N，有可编辑字段（width 等）；B：REGION 只读，block-tag 为 REGION，没有字段输入框。
5. 点「Analyze」，右侧 Inspection 出现 JSON。A：无「Import .vtt」「Structured」「Source」按钮；B：工具栏有「Import .vtt」，并可在 Structured / Source 之间切换看导出文本。
6. 回到终端执行剩下的接口命令并关服务。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/subtitle-webvtt-roundtrip-web.git subtitle-webvtt-roundtrip-web-B
cd subtitle-webvtt-roundtrip-web-B
npm ci
npm test                                                                 # 预期：18 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/tracks | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                                      # 浏览器打开后按下面「界面操作」走
Invoke-RestMethod http://127.0.0.1:4174/api/tracks | ConvertTo-Json -Compress   # 预期：含 id=alpha name=Primary timed cues
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/vtt/parse -ContentType "application/json" -Body '{"content":"WEBVTT\n\n00:00:01.000 --> 00:00:04.000 vertical:rl line:10\nhi"}' | ConvertTo-Json -Compress   # 预期：tokens 里 cue 的 start/end 与 known settings
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/vtt/patch -ContentType "application/json" -Body '{"content":"WEBVTT\n\n00:00:01.000 --> 00:00:04.000 vertical:rl line:10\nhi","cueIndex":0,"patch":{"start":"00:00:02.000"}}' | ConvertTo-Json -Compress   # 预期：content 时间变为 00:00:02.000，vertical:rl line:10 仍在原位
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/vtt/serialize -ContentType "application/json" -Body '{"content":"WEBVTT\n\n00:00:01.000 --> 00:00:04.000 vertical:rl line:10\nhi"}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404，没有 serialize 端点
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/vtt/patch -ContentType "application/json" -Body '{"content":"WEBVTT\n\n00:00:01.000 --> 00:00:04.000 vertical:rl line:10\nhi","cueIndex":0,"patch":{"start":"nope"}}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：400
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 3、4、5 步。

---

## 第 163 题　Feature 迭代　·　困难　·　全栈
<!-- solo-report:task=163 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/email-mime-preview-web　A 分支：https://github.com/gy-vs/email-mime-preview-web/tree/A　B 分支：https://github.com/gy-vs/email-mime-preview-web/tree/B

服务：`npm run dev` 同时起后端 4174 与前端 4173；浏览器开 http://localhost:4173。被占用会自动 +1，以新窗口打出的 Local: 地址为准。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/email-mime-preview-web.git email-mime-preview-web-A
cd email-mime-preview-web-A
npm ci
npm test                                                                 # 预期：观察 passed（含 mime/htmlView/requestToken/api）
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/messages | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                                      # 浏览器打开后按下面「界面操作」走
Invoke-RestMethod http://127.0.0.1:4174/api/messages | ConvertTo-Json -Compress   # 预期：含 id=newsletter 的 Newsletter (nested alt/related + remote + missing CID)
try { Invoke-RestMethod http://127.0.0.1:4174/api/health | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：{"ok":true}
try { Invoke-RestMethod "http://127.0.0.1:4174/api/messages/newsletter/selection?profile=html_prefer_related" | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：200，含 resources/attachments/nodes
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/messages/seed-newsletter/render -ContentType "application/json" -Body '{"client":"desktop"}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404，没有 POST render
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:4173，看到标题 Email Rendering Lab，顶栏有「Import MIME」和 title 为 Reload message list 的刷新按钮。
2. 在「Message」下拉里选 Newsletter (nested alt/related + remote + missing CID)，「Simulated client」选 Modern webmail。看到 flag：HTML、related CID、inline images。
3. 预览区 iframe 的 title 为 Sanitized HTML preview。点击正文旁 title 为 Show source MIME part 的链接 `part ... ↩`，左侧 MIME 树跳到对应 part。A：解析错误只出现在对应分支，整封不会空白；B：预览区按钮 title 为 Re-render，iframe title 为 preview，点 chip `body: ... part ...` 跳树。
4. 把 Simulated client / Client profile 切到会放行脚本的桌面配置。A：选 Strict desktop client，脚本是否进入 srcDoc 观察隔离 iframe；B：点「Desktop mail」，脚本原样进入 srcDoc（sanitize 关闭），再点「Webmail」应剥掉 script。
5. 点「Import MIME」，在「Message name (optional)」可留空，点「Parse & import」且 textarea 为空。A：提示 Paste a raw MIME message first.，有「Cancel」；B：按钮原文是「Import」和「Parse & import」，placeholder 为 Name (optional) / Paste raw MIME source…，无 Cancel。
6. 回到终端执行剩下的接口命令并关服务。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/email-mime-preview-web.git email-mime-preview-web-B
cd email-mime-preview-web-B
npm ci
npm test                                                                 # 预期：15 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/messages | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                                      # 浏览器打开后按下面「界面操作」走
Invoke-RestMethod http://127.0.0.1:4174/api/messages | ConvertTo-Json -Compress   # 预期：含 id=seed-newsletter 的 Newsletter (nested alternative/related)
try { Invoke-RestMethod http://127.0.0.1:4174/api/health | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404，没有 /api/health
try { Invoke-RestMethod "http://127.0.0.1:4174/api/messages/newsletter/selection?profile=html_prefer_related" | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404，没有 selection 路由且 id 不是 newsletter
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/messages/seed-newsletter/render -ContentType "application/json" -Body '{"client":"desktop"}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：200，body.html 含 script，带 renderToken
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 1、3、4、5 步。

---

## 第 164 题　Bug 修复　·　困难　·　全栈
<!-- solo-report:task=164 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/email-css-cache-web　A 分支：https://github.com/gy-vs/email-css-cache-web/tree/A　B 分支：https://github.com/gy-vs/email-css-cache-web/tree/B

服务：`npm run dev` 同时起后端 4174 与前端 4173；浏览器开 http://localhost:4173。被占用会自动 +1，以新窗口打出的 Local: 地址为准。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/email-css-cache-web.git email-css-cache-web-A
cd email-css-cache-web-A
npm ci
npm test                                                                 # 预期：观察 passed（含 coordinator/inline/api）
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/templates | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                                      # 浏览器打开后按下面「界面操作」走
Invoke-RestMethod http://127.0.0.1:4174/api/templates/alpha | ConvertTo-Json -Compress   # 预期：revision=3，content 含 class=promo，响应里没有 css 字段
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/templates/alpha/preview -ContentType "application/json" -Body '{"revision":3,"html":"<p class=\"promo\">hello</p>","css":".promo{color:red}","content":"<p class=\"promo\">hello</p>"}' | ConvertTo-Json -Compress   # 预期：200，html 内联后含 style，revision=3
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/templates/alpha/preview -ContentType "application/json" -Body '{"revision":999,"html":"<p>x</p>","css":"","content":"<p>x</p>"}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：409 revision_conflict
try { Invoke-RestMethod -Method Put -Uri http://127.0.0.1:4174/api/templates/nope -ContentType "application/json" -Body '{"content":"x","revision":1}' } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:4173，看到标题 Email Rendering Lab，左侧 Items 有「Primary render previews」。
2. 点击「Primary render previews」，工具栏有「Save」「Analyze」「Preview」，状态栏 Loaded。中间两个 textarea：aria-label 为 Content 与 CSS。
3. 点「Preview」。A：状态栏依次 Rendering → Rendered，右侧 Preview 出现 iframe（title Preview），Inspection JSON 仍在下方；B：状态栏 Previewing 后回到 Ready，有预览时 iframe 顶掉 Inspection JSON 面板。
4. 连点两次「Preview」（同一模板同一 revision）。A：请求带自增令牌和 AbortController，旧响应不能盖住新预览，状态栏仍是 Rendered；B：只比 id+revision，两发都算当前，先发后到可能盖住后一次结果。
5. 立刻点「Secondary render previews」再点「Preview」，确认第二份不会带上第一份的内联样式。A：切模板会 invalidate 令牌并 abort 上一发；B：跨模板的陈旧响应会被挡住，但同 revision 连发仍可能乱序。
6. 回到终端执行剩下的接口命令并关服务。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/email-css-cache-web.git email-css-cache-web-B
cd email-css-cache-web-B
npm ci
npm test                                                                 # 预期：观察 passed（含 previewOwnership/inline/api）
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/templates | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                                      # 浏览器打开后按下面「界面操作」走
Invoke-RestMethod http://127.0.0.1:4174/api/templates/alpha | ConvertTo-Json -Compress   # 预期：revision=3，content 含 class=title，带 css 字段
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/templates/alpha/preview -ContentType "application/json" -Body '{"revision":3,"html":"<p class=\"promo\">hello</p>","css":".promo{color:red}","content":"<p class=\"promo\">hello</p>"}' | ConvertTo-Json -Compress   # 预期：200，html 内联，baseRevision=3，服务端不校验 revision
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/templates/alpha/preview -ContentType "application/json" -Body '{"revision":999,"html":"<p>x</p>","css":"","content":"<p>x</p>"}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：200，陈旧 revision 仍渲染成功，baseRevision=999
try { Invoke-RestMethod -Method Put -Uri http://127.0.0.1:4174/api/templates/nope -ContentType "application/json" -Body '{"content":"x","revision":1}' } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 3、4、5 步。

---

## 第 165 题　Feature 迭代　·　困难　·　全栈
<!-- solo-report:task=165 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/email-capability-profile-web　A 分支：https://github.com/gy-vs/email-capability-profile-web/tree/A　B 分支：https://github.com/gy-vs/email-capability-profile-web/tree/B

服务：`npm run dev` 同时起后端 4174 与前端 4173；浏览器开 http://localhost:4173。被占用会自动 +1，以新窗口打出的 Local: 地址为准。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/email-capability-profile-web.git email-capability-profile-web-A
cd email-capability-profile-web-A
npm ci
npm test                                                                 # 预期：观察 passed（engine + api）
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/profiles | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                                      # 浏览器打开后按下面「界面操作」走
Invoke-RestMethod http://127.0.0.1:4174/api/profiles | ConvertTo-Json -Compress   # 预期：含 id=gmail-android
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/templates/alpha/preview -ContentType "application/json" -Body '{"profileId":"gmail-android","profileRevision":1}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：200，original 与 transformed 并排，带 explanations
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/transform -ContentType "application/json" -Body '{"templateId":"alpha","profileId":"gmail"}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404，没有 /api/transform
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/templates/alpha/preview -ContentType "application/json" -Body '{"profileId":"gmail-android"}' } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：400，缺 profileRevision
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:4173。A：标题为「邮件渲染实验室」，左侧「模板」与「客户端能力配置」（默认 gmail-android）；B：标题 Email Rendering Lab，顶栏「Templates」「Clients」。
2. 等自动预览完成。A：状态栏「预览绑定 rev.1」，中间「原始模板」与「转换结果」各有「代码」「渲染」；B：需点「Transform preview」，状态栏 Transform done: N drops...，Original / Transformed 用「Code」「Rendered」切换。
3. 在右侧「降级解释」里点一条解释。A：原始侧与转换侧同时高亮对应节点，节点只在一侧存在时出现「该节点已被降级移除，转换结果中不存在」或「该节点在原始模板中无对应位置」；B：只有转换侧 CodeView 接收高亮，原始侧固定无高亮，没有缺失提示。
4. 点「配置与历史」（A）或切到「Clients」（B）。A：表单按 CSS 属性/媒体/图片/dark mode 分域，有「保存为新 revision」和 title「删除配置（历史快照保留）」；B：是「Capability config JSON」文本框，有「New profile」「Save (new revision)」「Delete」。
5. 点「保存模板」（A）或「Save template」（B）前先改源码。A：summary「编辑模板源码」，按钮「保存模板」「预览」；B：textarea aria-label 为 Template HTML。
6. 回到终端执行剩下的接口命令并关服务。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/email-capability-profile-web.git email-capability-profile-web-B
cd email-capability-profile-web-B
npm ci
npm test                                                                 # 预期：14 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/profiles | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                                      # 浏览器打开后按下面「界面操作」走
Invoke-RestMethod http://127.0.0.1:4174/api/profiles | ConvertTo-Json -Compress   # 预期：含 id=gmail
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/templates/alpha/preview -ContentType "application/json" -Body '{"profileId":"gmail-android","profileRevision":1}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404，预览走 /api/transform
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/transform -ContentType "application/json" -Body '{"templateId":"alpha","profileId":"gmail"}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：200，带 result.outputHtml 与 explanations
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/templates/alpha/preview -ContentType "application/json" -Body '{"profileId":"gmail-android"}' } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 1、2、3、4 步。

---

## 第 167 题　Feature 迭代　·　困难　·　全栈
<!-- solo-report:task=167 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/email-snapshot-share-web　A 分支：https://github.com/gy-vs/email-snapshot-share-web/tree/A　B 分支：https://github.com/gy-vs/email-snapshot-share-web/tree/B

服务：`npm run dev` 同时起后端 4174 与前端 4173；浏览器开 http://localhost:4173。被占用会自动 +1，以新窗口打出的 Local: 地址为准。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/email-snapshot-share-web.git email-snapshot-share-web-A
cd email-snapshot-share-web-A
npm ci
npm test                                                                 # 预期：观察 passed（snapshots + api）
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/templates | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                                      # 浏览器打开后按下面「界面操作」走
Invoke-RestMethod http://127.0.0.1:4174/api/templates/alpha | ConvertTo-Json -Compress   # 预期：revision=3 name=Primary render previews
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/snapshots -ContentType "application/json" -Body '{"templateId":"alpha","revision":3,"capabilities":{"images":true,"css":true,"viewportWidth":800},"resources":[{"cid":"logo","contentType":"image/png","contentBase64":"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M8AAAMBAQDJ/pLvAAAAAElFTkSuQmCC"}]}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：201，shortLink 形如 #/s/<id>，manifest 含资源摘要
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/snapshots -ContentType "application/json" -Body '{"templateId":"alpha","revision":3,"clientProfileId":"webmail","resources":[{"name":"hero.webp","content":"hello"}]}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：观察 4xx（B 形态字段，A 可能缺 capabilities）
try { Invoke-RestMethod http://127.0.0.1:4174/api/snapshots/nope | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：4xx，快照不存在
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:4173，看到标题 Email Rendering Lab，左侧「Primary render previews」，工具栏「Save」「Analyze」。
2. 找到生成快照区域。A：标题「生成只读快照」，可勾选「渲染内嵌图片」「支持 CSS」，文件选择器可加 png，按钮「固定并生成短链接」；B：点「Add resource」出现 aria-label「Resource name」「Resource content」两个文本框，再点「Create snapshot」。
3. 生成快照。A：成功后出现「快照已生成（内容相同资源自动去重）」和本地短链接；B：状态栏 Snapshot created，出现 Read-only snapshot 与 local short link。
4. 打开短链接进入只读页。A：标题区可看固定模板（aria-label Pinned template content 只读）和「降级解释」，按钮「返回可编辑工作台」；B：标题 Read-only snapshot，链接「返回编辑器」，资源按位置反推 part，内嵌图片场景演示不出。
5. 回到工作台改 Content 并「Save」，再打开刚才的快照。两侧都应仍显示生成时的 revision 内容，不受当前草稿影响。
6. 回到终端执行剩下的接口命令并关服务。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/email-snapshot-share-web.git email-snapshot-share-web-B
cd email-snapshot-share-web-B
npm ci
npm test                                                                 # 预期：观察 passed（snapshots + api）
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/templates | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                                      # 浏览器打开后按下面「界面操作」走
Invoke-RestMethod http://127.0.0.1:4174/api/templates/alpha | ConvertTo-Json -Compress   # 预期：revision=3，content 为带 cid:hero.webp 的 HTML
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/snapshots -ContentType "application/json" -Body '{"templateId":"alpha","revision":3,"capabilities":{"images":true,"css":true,"viewportWidth":800},"resources":[{"cid":"logo","contentType":"image/png","contentBase64":"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M8AAAMBAQDJ/pLvAAAAAElFTkSuQmCC"}]}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：观察 4xx 或 201（B 认 clientProfileId 与 name/content，不一定认 cid/base64）
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/snapshots -ContentType "application/json" -Body '{"templateId":"alpha","revision":3,"clientProfileId":"webmail","resources":[{"name":"hero.webp","content":"hello"}]}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：201，url 形如 /#/s/<id>
try { Invoke-RestMethod http://127.0.0.1:4174/api/snapshots/nope | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：4xx
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 2、3、4 步。

---

## 第 168 题　Bug 修复　·　困难　·　全栈
<!-- solo-report:task=168 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/recurrence-dst-gap-web　A 分支：https://github.com/gy-vs/recurrence-dst-gap-web/tree/A　B 分支：https://github.com/gy-vs/recurrence-dst-gap-web/tree/B

服务：`npm run dev` 同时起后端 4174 与前端 4173；浏览器开 http://localhost:4173。被占用会自动 +1，以新窗口打出的 Local: 地址为准。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/recurrence-dst-gap-web.git recurrence-dst-gap-web-A
cd recurrence-dst-gap-web-A
npm ci
npm test                                                                 # 预期：观察 passed（recurrence/timezone/api）
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/schedules | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                                      # 浏览器打开后按下面「界面操作」走
Invoke-RestMethod http://127.0.0.1:4174/api/schedules | ConvertTo-Json -Compress   # 预期：alpha=Daily 02:30 (New York)，beta=Half-hour zone (Adelaide)
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/schedules/alpha/occurrences -ContentType "application/json" -Body '{"window":{"fromLocal":"2024-03-08T00:00:00","toLocal":"2024-03-12T00:00:00"},"pageSize":20}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：200，occurrence 带本地字段、offset 与 id，春季 gap 按 later 策略处理
try { Invoke-RestMethod "http://127.0.0.1:4174/api/recurrences/nyc-daily/occurrences/preview?from=0&to=4102444800000" | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404，没有 /api/recurrences
try { Invoke-RestMethod http://127.0.0.1:4174/api/zones | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404，时区走 IANA 自由文本而非下拉清单
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:4173，看到 Recurrence Rule Studio。A：左侧「Daily 02:30 (New York)」「Half-hour zone (Adelaide)」；B：左侧 Rules 为「New York 02:30 daily (gap/fold showcase)」等。
2. 选纽约那条规则。A：IANA timezone 输入框 placeholder America/New_York，Start (local wall time) 为 02:30，有「Save」「Analyze」；B：Zone 是下拉（仅内置七个时区），窗口是 Window from (UTC) / Window to (UTC, exclusive)，没有 Analyze。
3. 看春季 gap 策略。A：fieldset「Spring gap (missing wall time)」单选「跳过该天」「较早偏移（时钟显示后移）」「较晚偏移（时钟显示前移）」；B：title「Spring gap (local time does not exist)」下拉 Earlier offset / Later offset / Skip。
4. 切到 Adelaide / 半小时偏移规则（A 点「Half-hour zone (Adelaide)」；B 若下拉里没有 Australia/Adelaide 则无法表达该时区）。A：任意 IANA 时区可填；B：只能选表内时区。
5. 改 gap 策略后「Save」，再翻页预览。A：点「Load next page」，occurrence 由服务端返回，浏览器 Date 不重算；B：点 Next，状态栏 Saved · N cached expansion(s) invalidated，过期游标会失败。
6. 回到终端执行剩下的接口命令并关服务。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/recurrence-dst-gap-web.git recurrence-dst-gap-web-B
cd recurrence-dst-gap-web-B
npm ci
npm test                                                                 # 预期：观察 passed（engine/recurrence/api）
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/schedules | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                                      # 浏览器打开后按下面「界面操作」走
Invoke-RestMethod http://127.0.0.1:4174/api/schedules | ConvertTo-Json -Compress   # 预期：仍有脚手架 alpha/beta（Primary/Secondary occurrence sets），真正规则在 /api/recurrences
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/schedules/alpha/occurrences -ContentType "application/json" -Body '{"window":{"fromLocal":"2024-03-08T00:00:00","toLocal":"2024-03-12T00:00:00"},"pageSize":20}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404，展开走 /api/recurrences/:id/occurrences
try { Invoke-RestMethod "http://127.0.0.1:4174/api/recurrences/nyc-daily/occurrences/preview?from=0&to=4102444800000" | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：200，含 gap/fold 计数
try { Invoke-RestMethod http://127.0.0.1:4174/api/zones | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：200，zones 只有内置七个时区
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 1、2、3、4 步。

---

## 第 169 题　Feature 迭代　·　困难　·　全栈
<!-- solo-report:task=169 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/recurrence-exception-edit-web　A 分支：https://github.com/gy-vs/recurrence-exception-edit-web/tree/A　B 分支：https://github.com/gy-vs/recurrence-exception-edit-web/tree/B

服务：`npm run dev` 同时起后端 4174 与前端 4173；浏览器开 http://localhost:4173。被占用会自动 +1，以新窗口打出的 Local: 地址为准。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/recurrence-exception-edit-web.git recurrence-exception-edit-web-A
cd recurrence-exception-edit-web-A
npm ci
npm test                                                                 # 预期：观察 passed（recurrence + api）
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { try { Invoke-RestMethod http://127.0.0.1:4174/api/series | Out-Null; break } catch { Start-Sleep -Seconds 1 } } }
Start-Process http://localhost:4173                                      # 浏览器打开后按下面「界面操作」走
try { Invoke-RestMethod http://127.0.0.1:4174/api/rules | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：200，含 standup / monthly-report 等规则
try { Invoke-RestMethod http://127.0.0.1:4174/api/series | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/series/standup/touch -ContentType "application/json" -Body '{}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404，没有 simulate conflict 端点
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/undo -ContentType "application/json" -Body '{}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：观察 200 或业务错误 JSON（全局撤销栈，不校验 revision）
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:4173，看到 Recurrence Rule Studio 时间轴。A：有「‹ 前 4 周」「后 4 周 ›」「撤销」；B：列表是 Daily stand-up、Month-end payroll (31st) 等，顶栏有「simulate conflict」。
2. 把某次 occurrence 拖到另一天。A：弹出「移动 occurrence」对话框，单选「仅本次（记录一条修改例外）」「从本次起（截断原规则并生成新规则，迁移后半段例外）」，按钮「预览」「保存（revision N）」；B：工具栏出现「Only this one」「This and all following」「Save (rev N)」「Discard」。
3. 选「从本次起」/「This and all following」，先预览再保存。A：右侧「预测结果」展示截断与新规则、迁移例外计数，界面与变更说明里看不到 gap/overlap 判定；B：时间轴上 DST 标记来自 gap/overlap 检测，按月 31 日无效日期会跳过（看 Month-end payroll）。
4. 再拖一次做连续从此修改。A：只能看到 migratedExceptions 计数；B：后半段例外会迁到新规则。然后点「撤销」（A）或 undo 条目（B）。A：全局单栈且不校验 revision；B：冲突时状态栏 Revision conflict — drag intent kept，可点「Discard drag」。
5. 点 title 为 Simulate a concurrent revision bump 的「simulate conflict」（仅 B 有）。A：按钮不存在；B：revision 被抬高，未保存拖动会提示冲突并保留意图。
6. 回到终端执行剩下的接口命令并关服务。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/recurrence-exception-edit-web.git recurrence-exception-edit-web-B
cd recurrence-exception-edit-web-B
npm ci
npm test                                                                 # 预期：观察 passed（model/dst/operations/api）
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { try { Invoke-RestMethod http://127.0.0.1:4174/api/series | Out-Null; break } catch { Start-Sleep -Seconds 1 } } }
Start-Process http://localhost:4173                                      # 浏览器打开后按下面「界面操作」走
try { Invoke-RestMethod http://127.0.0.1:4174/api/rules | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
try { Invoke-RestMethod http://127.0.0.1:4174/api/series | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：200，含 standup、payday
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/series/standup/touch -ContentType "application/json" -Body '{}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：200，revision +1，用来模拟并发
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/undo -ContentType "application/json" -Body '{}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404，撤销挂在 series 变更上
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 1、2、3、4、5 步。

---

## 第 171 题　Feature 迭代　·　困难　·　全栈
<!-- solo-report:task=171 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/recurrence-revision-compare-web　A 分支：https://github.com/gy-vs/recurrence-revision-compare-web/tree/A　B 分支：https://github.com/gy-vs/recurrence-revision-compare-web/tree/B

服务：`npm run dev` 同时起后端 4174 与前端 4173；浏览器开 http://localhost:4173。被占用会自动 +1，以新窗口打出的 Local: 地址为准。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/recurrence-revision-compare-web.git recurrence-revision-compare-web-A
cd recurrence-revision-compare-web-A
npm ci
npm test                                                                 # 预期：脚手架 1 passed（比较会话未接到服务端）
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/schedules | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                                      # 浏览器打开后按下面「界面操作」走
Invoke-RestMethod http://127.0.0.1:4174/api/schedules | ConvertTo-Json -Compress   # 预期：alpha/beta 脚手架记录
try { Invoke-RestMethod http://127.0.0.1:4174/api/schedules/alpha/revisions | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/schedules/alpha/compare -ContentType "application/json" -Body '{"oldRevision":1,"newRevision":2,"from":"2026-01-01","to":"2026-03-31"}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404，没有比较会话
try { Invoke-RestMethod -Method Put -Uri http://127.0.0.1:4174/api/schedules/nope -ContentType "application/json" -Body '{"content":"x","revision":1}' } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:4173，看到 Recurrence Rule Studio。A：仍是原脚手架，工具栏只有「Save」「Analyze」，textarea aria-label 为 Content，没有比较区；B：有「Save as new revision」「Validate」，以及 Compare revisions 面板。
2. 找「Compare」按钮。A：按钮不存在；B：选择 Old / New revision（默认 1 与 2）、From / To 后点「Compare」。
3. 比较进行中看统计。A：无流式结果；B：徽标先是 streaming · partial，文案 Counts partial until stream completes，完成后 complete / Final counts，筛选项「Added」「Removed」「Time changed」「Unchanged」。
4. 点一条 occurrence 的 Jump to producing rule field or exception。A：无此入口；B：应跳到规则 JSON 对应字段（aria-label Rule document JSON），但配平括号查找可能落在 id 上。
5. 点「Analyze」（A）或「Validate」（B）。A：状态栏 Ready，Inspection 为脚手架分析；B：校验规则文档 JSON。
6. 回到终端执行剩下的接口命令并关服务。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/recurrence-revision-compare-web.git recurrence-revision-compare-web-B
cd recurrence-revision-compare-web-B
npm ci
npm test                                                                 # 预期：16 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/schedules | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                                      # 浏览器打开后按下面「界面操作」走
Invoke-RestMethod http://127.0.0.1:4174/api/schedules | ConvertTo-Json -Compress   # 预期：含 standup 系列，revision 为当前头
try { Invoke-RestMethod http://127.0.0.1:4174/api/schedules/alpha/revisions | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：200，revision 1 到 4，note 含 Move team to Chicago time
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/schedules/alpha/compare -ContentType "application/json" -Body '{"oldRevision":1,"newRevision":2,"from":"2026-01-01","to":"2026-03-31"}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：201，sessionId 与 streamUrl
try { Invoke-RestMethod -Method Put -Uri http://127.0.0.1:4174/api/schedules/nope -ContentType "application/json" -Body '{"content":"x","revision":1}' } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 1、2、3、4 步。

---

## 第 172 题　Bug 修复　·　困难　·　全栈
<!-- solo-report:task=172 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/recurrence-weekstart-web　A 分支：https://github.com/gy-vs/recurrence-weekstart-web/tree/A　B 分支：https://github.com/gy-vs/recurrence-weekstart-web/tree/B

服务：`npm run dev` 同时起后端 4174 与前端 4173；浏览器开 http://localhost:4173。被占用会自动 +1，以新窗口打出的 Local: 地址为准。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/recurrence-weekstart-web.git recurrence-weekstart-web-A
cd recurrence-weekstart-web-A
npm ci
npm test                                                                 # 预期：观察 passed（core/selection/api）
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/schedules | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                                      # 浏览器打开后按下面「界面操作」走
Invoke-RestMethod http://127.0.0.1:4174/api/schedules/alpha | ConvertTo-Json -Compress   # 预期：200，content 为 RRULE/DTSTART
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/preview -ContentType "application/json" -Body '{"content":"RRULE:FREQ=WEEKLY;INTERVAL=2;BYDAY=MO,WE,FR;WKST=MO\nDTSTART:20251229T090000\nTZID:UTC\n"}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：200，calendar.wkst=MO，occurrence 带 periodKey
try { Invoke-RestMethod "http://127.0.0.1:4174/api/recurrence/calendar?wkst=MO" | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404，周历挂在 /api/preview
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/preview -ContentType "application/json" -Body '{"content":"RRULE:FREQ=WEEKLY;WKST=XX\nDTSTART:20260105T090000\n"}' } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：422
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:4173，看到 Recurrence Rule Studio。A：工具栏「Save」「Analyze」，右侧 Occurrence grid，pill 显示 WKST / interval / zone，locale 仅影响标签；B：仍是纯文本框 CRUD，没有网格、没有 WKST 控件。
2. 看 WKST 控件。A：legend「WKST — week starts on (server-authoritative)」，radiogroup aria-label WKST，按钮 MO/TU/…；B：该控件不存在，周起始仍按浏览器地区。
3. 在网格上拖选一个周区间，或用方向键/PageUp/PageDown。A：键鼠落到同一套服务端周期键，点「Reset selection to rule」可回到规则选择；B：没有网格，拖选与跳周都不存在。
4. 把 WKST 从 MO 切到 SU（点 SU 段按钮）。A：出现提示 WKST changed MO → SU. Picked days are unchanged, but their week ranges were re-interpreted under the new week start.，可能列出 period 迁移；B：无法切换 WKST，calendar.ts 里的 reinterpretSelection 没有调用方。
5. 改 Locale (labels only) 下拉，确认列标题语言变了但周起始不变。A：pill 写 locale xx (labels only)；B：无此下拉。
6. 回到终端执行剩下的接口命令并关服务。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/recurrence-weekstart-web.git recurrence-weekstart-web-B
cd recurrence-weekstart-web-B
npm ci
npm test                                                                 # 预期：脚手架 1 passed（界面未改，网格相关测试缺失）
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/schedules | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                                      # 浏览器打开后按下面「界面操作」走
Invoke-RestMethod http://127.0.0.1:4174/api/schedules/alpha | ConvertTo-Json -Compress   # 预期：200，种子 content 已换成 DTSTART/RRULE
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/preview -ContentType "application/json" -Body '{"content":"RRULE:FREQ=WEEKLY;INTERVAL=2;BYDAY=MO,WE,FR;WKST=MO\nDTSTART:20251229T090000\nTZID:UTC\n"}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404，预览在 /api/recurrence/preview
try { Invoke-RestMethod "http://127.0.0.1:4174/api/recurrence/calendar?wkst=MO" | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：200，source=rule localeAgnostic=true
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/preview -ContentType "application/json" -Body '{"content":"RRULE:FREQ=WEEKLY;WKST=XX\nDTSTART:20260105T090000\n"}' } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 1、2、3、4 步。

---

## 第 173 题　Feature 迭代　·　困难　·　全栈
<!-- solo-report:task=173 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/payload-transform-pipeline-web　A 分支：https://github.com/gy-vs/payload-transform-pipeline-web/tree/A　B 分支：https://github.com/gy-vs/payload-transform-pipeline-web/tree/B

服务：`npm run dev` 同时起后端 4174 与前端 4173；浏览器开 http://localhost:4173。被占用会自动 +1，以新窗口打出的 Local: 地址为准。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/payload-transform-pipeline-web.git payload-transform-pipeline-web-A
cd payload-transform-pipeline-web-A
npm ci
npm test                                                         # 预期：观察 vitest 结果（材料里 A 侧没有一次成功跑通记录）
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { if ($_.Exception.Response) { break } else { Start-Sleep -Seconds 1 } } }
Start-Process http://localhost:4173                              # 浏览器打开后按下面「界面操作」走
try { Invoke-RestMethod http://127.0.0.1:4174/api/pipelines | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：A 返回列表，含 name=Legacy /v1/users -> UserV2；B 为 404
try { Invoke-RestMethod http://127.0.0.1:4174/api/pipeline | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：A 为 404；B 返回 name=Legacy order payload v1 -> v2、revision=1
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/run -ContentType "application/json" -Body '{"steps":[{"id":"s1","op":"rename","source":"$.no_such_field","target":"$.x"}]}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：A 为 404；B 为 409，body 有 ok=false、code、sourcePath，没有 output 字段
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:4173。A：顶栏附近看到「转换流水线」，左栏有种子流水线 `Legacy /v1/users -> UserV2`；B：顶栏 `Payload Migration Workbench`，流水线名 `Legacy order payload v1 -> v2`，右侧 `rev 1`。
2. 点进种子流水线。A：中栏底部有「重命名 / 移动 / 拆分 / 合并 / 表达式」追加按钮，步骤行有 title「上移」「下移」「编辑」「删除」；B：点「Add step」挑选 rename / move / split / merge / expression，行上 title 为「Move up」「Move down」「Delete」。
3. 点开某一步编辑器。A：「目标已存在」下拉可见「覆盖」「跳过」「报错中止」；B：勾选项为「overwrite target」，表达式提示 Inputs that are absent bind to null。A：三档冲突策略；B：缺失直接绑成 null。
4. 开两个标签载入同一条流水线。在标签 1 改名称后点「保存」（B 侧按钮原文为 `Save`），再回标签 2 点保存。A：冲突横幅「并发冲突：」，按钮「载入服务器版本（放弃本地）」「基于服务器版本重试保存」；B：横幅 Concurrent save detected，按钮「Load server version & re-apply later」。
5. 在冲突横幅上点重试/载入。A：点「基于服务器版本重试保存」仍会再撞冲突（闭包读到旧 revision）；B：点「Load server version & re-apply later」只覆盖本地 steps/name 并清 dirty，本地修改不会被重放。
6. 右栏选一样例。A：点「运行预览」，时间线逐步出现，点「展开完整节点（按需拉取）」才拉子树；B：自动或点「Re-run」，失败步只给失败前摘要，结果类型没有最终 output。
7. 回到终端执行剩下的接口命令并 `taskkill`。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/payload-transform-pipeline-web.git payload-transform-pipeline-web-B
cd payload-transform-pipeline-web-B
npm ci
npm test                                                         # 预期：观察 vitest 结果
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { if ($_.Exception.Response) { break } else { Start-Sleep -Seconds 1 } } }
Start-Process http://localhost:4173                              # 浏览器打开后按下面「界面操作」走
try { Invoke-RestMethod http://127.0.0.1:4174/api/pipelines | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
try { Invoke-RestMethod http://127.0.0.1:4174/api/pipeline | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：name=Legacy order payload v1 -> v2、revision=1
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/run -ContentType "application/json" -Body '{"steps":[{"id":"s1","op":"rename","source":"$.no_such_field","target":"$.x"}]}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：409，ok=false，无 output 字段
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 1、3、4、5、6 步。

---

## 第 174 题　Bug 修复　·　困难　·　全栈
<!-- solo-report:task=174 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/payload-falsy-coercion-web　A 分支：https://github.com/gy-vs/payload-falsy-coercion-web/tree/A　B 分支：https://github.com/gy-vs/payload-falsy-coercion-web/tree/B

服务：`npm run dev` 同时起后端 4174 与前端 4173；浏览器开 http://localhost:4173。被占用会自动 +1，以新窗口打出的 Local: 地址为准。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/payload-falsy-coercion-web.git payload-falsy-coercion-web-A
cd payload-falsy-coercion-web-A
npm ci
npm test                                                         # 预期：观察 vitest 结果
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { if ($_.Exception.Response) { break } else { Start-Sleep -Seconds 1 } } }
Start-Process http://localhost:4173                              # 浏览器打开后按下面「界面操作」走
Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | ConvertTo-Json -Compress   # 预期：family=migration-mapping、count=2
try { Invoke-RestMethod http://127.0.0.1:4174/api/specs | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：A 返回 specs 与 Presence 枚举（含 defaulted）；B 为 404
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/batch-convert -ContentType "application/json" -Body '{"strictSerialization":true}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：A 为 422，error=unserializable_payload；B 为 404
try { Invoke-RestMethod http://127.0.0.1:4174/api/convert/enums | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：A 为 404；B 返回 sourceStatuses=present/missing/undefined/null
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:4173。A：顶栏 `Payload Migration Workbench`，左栏 Field specs 列出 name、meta.revision 等；B：顶栏默认停在「Payload 转换工作台」，可切「记录编辑」。
2. 点「空位/undefined 样本」（B 侧为「载入示例对象（含 undefined/空位）」），再点「单条预览」（B 侧为「单条预览（前端）」）。看到字段行带状态徽标。A：空串/0/false 标「存在」；B：标 present（含 '' / 0 / false）。
3. 点筛选条。A：芯片「存在」「null」「缺失」「undefined」「默认值填充」「转换失败」；B：来源轴 present / missing / undefined / null，结果轴 kept / coerced / defaulted / failed / omitted。A：填过默认值后只剩 Defaulted，分不清原来是缺键还是显式 null；B：byStatus 与 byOutcome 两列仍能分开看。
4. 点「服务端批量」（B 侧为「服务端批量执行」）。A：批量摘要写「有效 = 存在 + 默认值填充」；B：有效口径只计 status=present，defaultedFields 单列。
5. A：勾选「严格序列化（undefined / 空位报错）」再点「服务端批量」，界面出现序列化被拒绝；B：没有该勾选，接口在 `/api/convert/batch`。再点「服务端迁移」（B 侧为「加载旧保存数据」）。A：迁移后 Presence 由结构推断；B：只补状态、输出值未改。
6. 回到终端执行剩下的接口命令并 `taskkill`。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/payload-falsy-coercion-web.git payload-falsy-coercion-web-B
cd payload-falsy-coercion-web-B
npm ci
npm test                                                         # 预期：观察 vitest 结果
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { if ($_.Exception.Response) { break } else { Start-Sleep -Seconds 1 } } }
Start-Process http://localhost:4173                              # 浏览器打开后按下面「界面操作」走
Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | ConvertTo-Json -Compress   # 预期：family=migration-mapping、count=2
try { Invoke-RestMethod http://127.0.0.1:4174/api/specs | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/batch-convert -ContentType "application/json" -Body '{"strictSerialization":true}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
try { Invoke-RestMethod http://127.0.0.1:4174/api/convert/enums | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：sourceStatuses 含 present、missing、undefined、null
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 1、3、4、5 步。

---

## 第 175 题　Feature 迭代　·　困难　·　全栈
<!-- solo-report:task=175 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/payload-dryrun-diff-web　A 分支：https://github.com/gy-vs/payload-dryrun-diff-web/tree/A　B 分支：https://github.com/gy-vs/payload-dryrun-diff-web/tree/B

服务：`npm run dev` 同时起后端 4174 与前端 4173；浏览器开 http://localhost:4173。被占用会自动 +1，以新窗口打出的 Local: 地址为准。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/payload-dryrun-diff-web.git payload-dryrun-diff-web-A
cd payload-dryrun-diff-web-A
npm ci
npm test                                                         # 预期：观察 vitest 结果（A 侧前端没有测试）
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { if ($_.Exception.Response) { break } else { Start-Sleep -Seconds 1 } } }
Start-Process http://localhost:4173                              # 浏览器打开后按下面「界面操作」走
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/dryrun/sessions -ContentType "application/json" -Body '{"fromRevision":"rev-1","toRevision":"rev-2","sampleSetId":"orders"}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：A 返回 session id 与 status；B 为 404
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/runs -ContentType "application/json" -Body '{"leftRevisionId":"rev-legacy","rightRevisionId":"rev-current"}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：A 为 404；B 返回 run id 与 running
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/testing/sample-set -ContentType "application/json" -Body '{"generation":2}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：A 为 404；B 把样例集合切到第二代
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:4173。A：顶栏 `Payload Migration Workbench`，控件 From / To /「样例集合」；B：标题「Payload 迁移 Dry-run 审阅台」，左栏「流水线 Revision」默认 rev-legacy 与 rev-current。
2. 点「开始 dry-run」（B 侧为「Dry-run 全部样例」）。中栏「按路径汇总」开始增量填充。A：运行中出现徽标「部分统计 PARTIAL」；B：文案「部分统计：」与「（运行中，统计为部分结果，完成后自动收敛）」。
3. 点击汇总表任意一行路径，右侧出现样例详情。保持运行，后续样例到达后选中路径仍不变。
4. 运行中点「取消」。A：徽标「已取消（迟到结果已丢弃）」；B：运行状态切到「已取消」，迟到事件不再写入。
5. 看重复稳定键。A：多余元素仍复用同一个选择器路径，详情只能靠下标区分、无对齐诊断；B：左栏「数组对齐配置」列出稳定键，多余元素路径带出现序后缀，并有 title「对齐诊断」。
6. 点 title「刷新配置」（B 侧 title「刷新目录」）。若集合版本已变，A：提示「样例集合已更新到 vN，本次运行基于 vM 快照」；B：出现集合已更新横幅。
7. 回到终端执行剩下的接口命令并 `taskkill`。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/payload-dryrun-diff-web.git payload-dryrun-diff-web-B
cd payload-dryrun-diff-web-B
npm ci
npm test                                                         # 预期：观察 vitest 结果
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { if ($_.Exception.Response) { break } else { Start-Sleep -Seconds 1 } } }
Start-Process http://localhost:4173                              # 浏览器打开后按下面「界面操作」走
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/dryrun/sessions -ContentType "application/json" -Body '{"fromRevision":"rev-1","toRevision":"rev-2","sampleSetId":"orders"}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/runs -ContentType "application/json" -Body '{"leftRevisionId":"rev-legacy","rightRevisionId":"rev-current"}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：返回 run id，status=running
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/testing/sample-set -ContentType "application/json" -Body '{"generation":2}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：样例集合切到 generation 2
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 1、2、4、5、6 步。

---

## 第 176 题　Bug 修复　·　困难　·　全栈
<!-- solo-report:task=176 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/payload-source-row-web　A 分支：https://github.com/gy-vs/payload-source-row-web/tree/A　B 分支：https://github.com/gy-vs/payload-source-row-web/tree/B

服务：`npm run dev` 同时起后端 4174 与前端 4173；浏览器开 http://localhost:4173。被占用会自动 +1，以新窗口打出的 Local: 地址为准。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/payload-source-row-web.git payload-source-row-web-A
cd payload-source-row-web-A
npm ci
npm test                                                         # 预期：观察 vitest 结果
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { if ($_.Exception.Response) { break } else { Start-Sleep -Seconds 1 } } }
Start-Process http://localhost:4173                              # 浏览器打开后按下面「界面操作」走
Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | ConvertTo-Json -Compress   # 预期：family=migration-mapping、count=2
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/batches -ContentType "application/json" -Body '{"records":[{"mappingId":"nope"},{"content":"ok payload"}]}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：A 仍 200，未知引用记入 errors 并继续跑其余记录；B 整批 400，error=unknown_mapping
try { Invoke-RestMethod -Method Delete -Uri http://127.0.0.1:4174/api/batches/batch-1/snapshot | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：A 为 404（无 Drop snapshot 接口）；B 对不存在批次也是 404，有批次时返回 ok=true
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:4173，顶栏 `Migration Mapping Studio`。A：点顶部「Batch runs」切到批量面板；B：批量面板挂在三栏工作区下方，向下滚动即可看到。
2. A：点「Load sample」载入自带 JSON，再点「Run batch」；B：文本框已有样例，直接点「Run batch」。状态栏 A 显示 Idle→Running→Done；B 显示 `Batch … ok/failed/filtered`。
3. 看结果行。A：每行带来源 id→派生 id，步骤路径是常量 `STEP_PATH`，不含展开下标；B：步骤路径含过滤段与带下标的展开段。A：被过滤行与入库错误在列表尾部；B：被过滤记录以标签显示在列表上方。
4. 在「Filter rows」（B 侧 aria-label 为「Filter results」）里输入来源 id 片段。筛选后每行来源链仍完整。A：placeholder `Filter by id, path, message…`；B：`Filter by name, id, step…`。
5. 点「Retry failed」（A 侧按钮带失败计数 `Retry failed (N)`）。A：按派生 id 合并，列表不会因重试出现重复行；B：接口 `completionOrder` 会再次追加同一 id，响应里该行重复，界面因 `mergeItemsById` 去重看不出来。
6. 点「Drop snapshot」（仅 B 有此按钮）。A：界面没有该按钮，快照默认不过期；B：点完再点「Retry failed」，状态变为 `Snapshot expired — retry refused; start a new batch`，接口 410 `snapshot_expired`。
7. 回到终端执行剩下的接口命令并 `taskkill`。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/payload-source-row-web.git payload-source-row-web-B
cd payload-source-row-web-B
npm ci
npm test                                                         # 预期：观察 vitest 结果
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { if ($_.Exception.Response) { break } else { Start-Sleep -Seconds 1 } } }
Start-Process http://localhost:4173                              # 浏览器打开后按下面「界面操作」走
Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | ConvertTo-Json -Compress   # 预期：family=migration-mapping、count=2
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/batches -ContentType "application/json" -Body '{"records":[{"mappingId":"nope"},{"content":"ok payload"}]}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：400，error=unknown_mapping，其余记录一并丢失
try { Invoke-RestMethod -Method Delete -Uri http://127.0.0.1:4174/api/batches/batch-1/snapshot | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：若尚未创建 batch-1 则为 404；刚跑过的批次可改为实际 batchId，成功时 ok=true
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 1、3、5、6 步。

---

## 第 177 题　Feature 迭代　·　困难　·　全栈
<!-- solo-report:task=177 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/payload-contract-gate-web　A 分支：https://github.com/gy-vs/payload-contract-gate-web/tree/A　B 分支：https://github.com/gy-vs/payload-contract-gate-web/tree/B

服务：`npm run dev` 同时起后端 4174 与前端 4173；浏览器开 http://localhost:4173。被占用会自动 +1，以新窗口打出的 Local: 地址为准。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/payload-contract-gate-web.git payload-contract-gate-web-A
cd payload-contract-gate-web-A
npm ci
npm test                                                         # 预期：观察 vitest 结果
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { if ($_.Exception.Response) { break } else { Start-Sleep -Seconds 1 } } }
Start-Process http://localhost:4173                              # 浏览器打开后按下面「界面操作」走
try { Invoke-RestMethod http://127.0.0.1:4174/api/pipelines/payload-migration | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：A 返回 id=payload-migration 与 steps；B 为 404
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/pipelines/payload-migration/validate -ContentType "application/json" -Body '{}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：A 返回各样例 errors 与 attribution（primary / candidates / certain）；B 为 404
try { Invoke-RestMethod http://127.0.0.1:4174/api/workbench | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：A 为 404；B 返回 pipeline、schema、samples
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:4173。A：顶栏 `Payload Migration Workbench`，pill 显示 `pipeline rN · schema rM`，主按钮「Run gate」；B：标题「转换流水线」，主按钮「全部校验」，默认样例 `sample-happy`。
2. 等自动校验结束，点一个失败样例。A：右侧「Gate errors」列出路径与 message；B：错误卡片带 keyword 与「最近可能写入步骤」。
3. 点错误条目跳转。A：点错误路径按钮后左侧对应步骤被选中，当前样例不变，编辑器下方出现该路径上的实际取值；B：主跳转按钮「最近可能写入步骤：…」可用，但候选步骤按钮全部绑定同一个 `onJump`，点具体候选仍跳到 primary / candidates[0]。
4. 改一步的写路径后保存。A：步骤区是「Step JSON」文本框，点「Apply step」；B：map 文本为「目标路径 <= 源路径」，点「保存步骤」。A：顶部出现 stale 横幅 `Pipeline or schema changed — displayed verdicts are stale until the gate re-runs`；B：状态栏给出重验了多少个受影响样例。
5. 看数组元素样例。A：同组通配 `items[].sku` / `items[].qty` 能写出叶子，归因可指向最近静态写入者；B：同组通配里 qty 走不到 writeLeaf，转换输出本身就不对，后续门禁归因不可信。
6. A：在「Schema JSON」里改 schema 后点「Save schema」，旧结论失效；B：点「保存并重验此样例」只动 sampleRevision。
7. 回到终端执行剩下的接口命令并 `taskkill`。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/payload-contract-gate-web.git payload-contract-gate-web-B
cd payload-contract-gate-web-B
npm ci
npm test                                                         # 预期：观察 vitest 结果（材料里最后可见 gate 测试仍可能失败）
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { if ($_.Exception.Response) { break } else { Start-Sleep -Seconds 1 } } }
Start-Process http://localhost:4173                              # 浏览器打开后按下面「界面操作」走
try { Invoke-RestMethod http://127.0.0.1:4174/api/pipelines/payload-migration | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/pipelines/payload-migration/validate -ContentType "application/json" -Body '{}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
try { Invoke-RestMethod http://127.0.0.1:4174/api/workbench | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：返回 pipeline、schema、samples
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 1、3、4、5、6 步。

---

## 第 178 题　Bug 修复　·　困难　·　全栈
<!-- solo-report:task=178 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/a11y-node-identity-web　A 分支：https://github.com/gy-vs/a11y-node-identity-web/tree/A　B 分支：https://github.com/gy-vs/a11y-node-identity-web/tree/B

服务：`npm run dev` 同时起后端 4174 与前端 4173；浏览器开 http://localhost:4173。被占用会自动 +1，以新窗口打出的 Local: 地址为准。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/a11y-node-identity-web.git a11y-node-identity-web-A
cd a11y-node-identity-web-A
npm ci
npm test                                                         # 预期：观察 vitest 结果（A 侧收尾有类型检查、测试、构建一起通过的记录）
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { if ($_.Exception.Response) { break } else { Start-Sleep -Seconds 1 } } }
Start-Process http://localhost:4173                              # 浏览器打开后按下面「界面操作」走
Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | ConvertTo-Json -Compress   # 预期：两侧都能返回 family 与 count
try { Invoke-RestMethod http://127.0.0.1:4174/api/audits | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：观察是否仍保留脚手架 audits 列表
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:4173。A：看到「实时页面（含 iframe）」与「可忽略的问题」；B：顶部切到「Node identity」（另一页签为「Text audits」）。
2. A：点「扫描并建立快照」，对某条问题点「忽略」，生成基线 finding；B：在「Remap scenarios」里选一个场景，点「Load scenario」，它会重置审计、上传 before、播种 ignored finding、再上传 after。A：走真实 DOM 采集；B：`runSide` 直接取 fixture.before / fixture.after，采集模块没有接到界面。
3. 选一种重排（兄弟插入、节点移动、文本变化、重复组件、节点删除、跨 iframe）。A：点「重排并对账」，对账输入会重新扫描预览 DOM；B：点「3. Match identities」，全程跑在硬编码夹具上。
4. 观察自动迁移与待确认。A：「待确认的映射」可点「确认映射并迁移」或「节点已删除，丢弃」；B：「Pending confirmation」里点「This is the same node」或「Accept deletion (close finding)」。状态栏会显示自动迁移数量与待确认数量。
5. 看跨 iframe。A：匹配器有跨 iframe 场景用例，帧身份不靠子节点下标；B：帧 id 仅由 iframe src 派生，同 src 多帧会撞 frameId，最后一次自测仍写着跨 frame 无稳定键。
6. 点「清理旧快照」（B 侧为「Prune old」），再打开映射审计。A：已确认映射仍在；B：点「Audit trail」，被清理的快照引用带已清理标记而映射记录仍保留。B 改 finding 状态会 `location.reload` 整页刷新。
7. 回到终端执行剩下的接口命令并 `taskkill`。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/a11y-node-identity-web.git a11y-node-identity-web-B
cd a11y-node-identity-web-B
npm ci
npm test                                                         # 预期：观察 vitest 结果（材料里匹配器仍有未解场景）
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { if ($_.Exception.Response) { break } else { Start-Sleep -Seconds 1 } } }
Start-Process http://localhost:4173                              # 浏览器打开后按下面「界面操作」走
Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | ConvertTo-Json -Compress   # 预期：family 与 count
try { Invoke-RestMethod http://127.0.0.1:4174/api/audits | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：观察 audits 列表
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 1、2、3、5、6 步。

---

## 第 179 题　Feature 迭代　·　困难　·　全栈
<!-- solo-report:task=179 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/a11y-focus-order-web　A 分支：https://github.com/gy-vs/a11y-focus-order-web/tree/A　B 分支：https://github.com/gy-vs/a11y-focus-order-web/tree/B

服务：`npm run dev` 同时起后端 4174 与前端 4173；浏览器开 http://localhost:4173。被占用会自动 +1，以新窗口打出的 Local: 地址为准。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/a11y-focus-order-web.git a11y-focus-order-web-A
cd a11y-focus-order-web-A
npm ci
npm test                                                         # 预期：观察 vitest 结果
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { if ($_.Exception.Response) { break } else { Start-Sleep -Seconds 1 } } }
Start-Process http://localhost:4173                              # 浏览器打开后按下面「界面操作」走
try { Invoke-RestMethod http://127.0.0.1:4174/api/snapshots | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：A 返回含 id=checkout 的快照列表；B 为 404
try { Invoke-RestMethod http://127.0.0.1:4174/api/snapshot | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：A 为 404；B 返回演示快照节点
try { Invoke-RestMethod -Method Delete -Uri http://127.0.0.1:4174/api/snapshots/checkout/nodes/search | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：A 删除 search 并 pruneEdges，其余约束链保留；B 为 404
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:4173。A：默认载入 checkout 快照，左栏「快照结构」，中栏「计算顺序（基线）」，右栏「建议顺序」；B：左栏按作用域分组的计算顺序基线，中栏「建议顺序（审阅）」，右栏「约束与冲突」。
2. 在建议顺序栏拖动某一行，或点选后用行内「上移（Alt+↑）」「下移（Alt+↓）」（B 侧用 Ctrl/Alt+方向键）。A：约束链面板出现 from→to，需再点「保存约束」才 PUT；B：每次移动立刻 PUT，顶栏显示保存结果。
3. 用快照结构栏 title「新增节点」添加节点（A：表单字段「节点 id」「标签」「可访问名称」「tabindex（可空）」，点「添加」；B：点顶栏「模拟新增节点」）。新节点应能落入既有约束之间。
4. 删一个被约束引用的节点。A：树节点 title「删除节点（连带子树，相关约束自动剪除）」，删完仍可继续拖动保存；B：点行右侧 title「从快照删除节点」，约束仍指向已删节点，随后任何拖动/键盘移动都会 422 并回滚，必须先点「删除约束」清掉坏边。
5. 制造循环或跨作用域约束后点「保存约束」（B 侧自动提交）。A：ConflictPanel 渲染最小冲突链，链上节点可点并自动定位第一个；B：422 分支丢掉 conflicts，只显示「约束被服务端拒绝」，最小冲突链看不到。修订号冲突时 A 把本地草稿 rebase 到服务器新版本；B 直接用 body.current.constraints 覆盖本地。
6. 滚动面板并选中节点后刷新。A：选中、三栏滚动与未保存草稿都会恢复；B：选中与两栏滚动从 sessionStorage 恢复。
7. 回到终端执行剩下的接口命令并 `taskkill`。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/a11y-focus-order-web.git a11y-focus-order-web-B
cd a11y-focus-order-web-B
npm ci
npm test                                                         # 预期：观察 vitest 结果
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { if ($_.Exception.Response) { break } else { Start-Sleep -Seconds 1 } } }
Start-Process http://localhost:4173                              # 浏览器打开后按下面「界面操作」走
try { Invoke-RestMethod http://127.0.0.1:4174/api/snapshots | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
try { Invoke-RestMethod http://127.0.0.1:4174/api/snapshot | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：返回演示快照节点
try { Invoke-RestMethod -Method Delete -Uri http://127.0.0.1:4174/api/snapshots/checkout/nodes/search | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 1、2、4、5 步。

---

## 第 180 题　Bug 修复　·　困难　·　全栈
<!-- solo-report:task=180 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/a11y-idref-scope-web　A 分支：https://github.com/gy-vs/a11y-idref-scope-web/tree/A　B 分支：https://github.com/gy-vs/a11y-idref-scope-web/tree/B

服务：`npm run dev` 同时起后端 4174 与前端 4173；浏览器开 http://localhost:4173。被占用会自动 +1，以新窗口打出的 Local: 地址为准。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/a11y-idref-scope-web.git a11y-idref-scope-web-A
cd a11y-idref-scope-web-A
npm ci
npm test                                                         # 预期：观察 vitest 结果
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { if ($_.Exception.Response) { break } else { Start-Sleep -Seconds 1 } } }
Start-Process http://localhost:4173                              # 浏览器打开后按下面「界面操作」走
try { Invoke-RestMethod http://127.0.0.1:4174/api/pages | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：A 返回 page-demo；B 为 404
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/pages/page-demo/mutate -ContentType "application/json" -Body '{"op":{"type":"set-attr","nid":"page-title","name":"class","value":null}}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：A 返回 cache.rebuilt 为空（与 id 无关的属性不重建作用域索引）；B 为 404
try { Invoke-RestMethod http://127.0.0.1:4174/api/snapshot | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：A 为 404；B 返回内置演示快照
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:4173。A：默认进入 ARIA 作用域工作台并加载 `page-demo`，随后自动分析；B：顶栏默认「ARIA scopes」，可切「Audits」做旧的 Save / Analyze。
2. 中栏看快照树（含 shadow / iframe 作用域标记），右栏看 Findings 与重复 id。A：重复 id 分组文案含 repeated token；B：Findings 按 ok / missing / duplicate / cross-scope 分色计数。
3. 点击某条 finding。A：来源节点与所有目标（含被边界阻断的候选）在树上高亮；B：点 token 前的准星，右栏按服务端路径回放定位，不走 getElementById。
4. 用右栏节点编辑做缓存对比（仅 A 有这些按钮）。nid 默认 page-title：先点 title「unrelated attr edit: no scope index rebuilt」的「drop class」，观察 rebuilt 为空、reused 覆盖全部作用域；再点 title「id edit: only owning scope rebuilt」的「rename id」，只有所属作用域重建。B：没有 mutate 面板，改 class / aria-label 仍会重建该作用域索引。
5. A：parent 填 `open-host` 后点「move」，源与目标两个作用域被作废；B：界面没有移动入口，移动只存在于测试辅助。
6. 点「Re-analyze」（B 侧为「Analyze IDREFs」）与「Reload」（B 侧为「Reload snapshot」）。A：revision 过期时状态栏提示冲突并自动重载；B：工具条显示 snapshot revision、scopes、nodes 与 rebuilt index(es)。
7. 回到终端执行剩下的接口命令并 `taskkill`。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/a11y-idref-scope-web.git a11y-idref-scope-web-B
cd a11y-idref-scope-web-B
npm ci
npm test                                                         # 预期：观察 vitest 结果
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { if ($_.Exception.Response) { break } else { Start-Sleep -Seconds 1 } } }
Start-Process http://localhost:4173                              # 浏览器打开后按下面「界面操作」走
try { Invoke-RestMethod http://127.0.0.1:4174/api/pages | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/pages/page-demo/mutate -ContentType "application/json" -Body '{"op":{"type":"set-attr","nid":"page-title","name":"class","value":null}}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
try { Invoke-RestMethod http://127.0.0.1:4174/api/snapshot | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：返回内置演示快照
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 1、3、4、5、6 步。

---

## 第 181 题　Feature 迭代　·　困难　·　全栈
<!-- solo-report:task=181 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/a11y-suppression-policy-web　A 分支：https://github.com/gy-vs/a11y-suppression-policy-web/tree/A　B 分支：https://github.com/gy-vs/a11y-suppression-policy-web/tree/B

服务：`npm run dev` 同时起后端 4174 与前端 4173；浏览器开 http://localhost:4173。被占用会自动 +1，以新窗口打出的 Local: 地址为准。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/a11y-suppression-policy-web.git a11y-suppression-policy-web-A
cd a11y-suppression-policy-web-A
npm ci
npm test                                                         # 预期：观察 vitest 结果
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { if ($_.Exception.Response) { break } else { Start-Sleep -Seconds 1 } } }
Start-Process http://localhost:4173                              # 浏览器打开后按下面「界面操作」走
try { Invoke-RestMethod http://127.0.0.1:4174/api/audits | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：A 仍返回脚手架 audits 列表；B 为 404（原路由被删）
try { Invoke-RestMethod http://127.0.0.1:4174/api/suppression/snapshots | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：A 返回样例快照；B 为 404
try { Invoke-RestMethod http://127.0.0.1:4174/api/snapshots | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：A 为 404；B 返回快照列表
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:4173。A：顶栏「无障碍问题抑制规则」，样例快照标签可切换，中栏是样例预览；B：仍是脚手架「Accessibility Review」，fetch `/api/audits` 失败，Items 为空，只有「Save」「Analyze」。
2. A：中栏 SnapshotPreview 逐条展示 candidates 的 won / shadowed / expired / invalid / disabled，被覆盖一支打出 coveredBy.why；B：没有预览、没有命中节点、没有覆盖原因。
3. A：点「+ 新建规则」，填写「留空=全部路径」「留空=全部组件」「如 color-contrast」「为什么抑制？用于审计与解释」后保存，看见 toast「规则已创建」；B：没有新建规则入口。
4. A：在规则卡片点「禁用」或「启用」，预览结论从已抑制切到「规则已禁用，未抑制」；B：按钮不存在。
5. A：右栏点「开始批量（N 个样例）」，观察进度；运行中点「取消（不写部分统计）」，确认不写入最终统计；完成后在「历史报告（固定 revision，可回放）」点「回放」。B：只能走接口 `/api/batch-jobs`，界面无批量面板。
6. 回到终端执行剩下的接口命令并 `taskkill`。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/a11y-suppression-policy-web.git a11y-suppression-policy-web-B
cd a11y-suppression-policy-web-B
npm ci
npm test                                                         # 预期：观察 vitest 结果
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { if ($_.Exception.Response) { break } else { Start-Sleep -Seconds 1 } } }
Start-Process http://localhost:4173                              # 浏览器打开后按下面「界面操作」走
try { Invoke-RestMethod http://127.0.0.1:4174/api/audits | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404，首屏旧界面指向不存在的端点
try { Invoke-RestMethod http://127.0.0.1:4174/api/suppression/snapshots | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
try { Invoke-RestMethod http://127.0.0.1:4174/api/snapshots | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：返回快照列表
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 1、2、3、4、5 步。

---

## 第 182 题　Bug 修复　·　困难　·　全栈
<!-- solo-report:task=182 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/a11y-alpha-contrast-web　A 分支：https://github.com/gy-vs/a11y-alpha-contrast-web/tree/A　B 分支：https://github.com/gy-vs/a11y-alpha-contrast-web/tree/B

服务：`npm run dev` 同时起后端 4174 与前端 4173；浏览器开 http://localhost:4173。被占用会自动 +1，以新窗口打出的 Local: 地址为准。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/a11y-alpha-contrast-web.git a11y-alpha-contrast-web-A
cd a11y-alpha-contrast-web-A
npm ci
npm test                                                         # 预期：观察 vitest 结果（A 侧收尾没有留下通过记录）
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { if ($_.Exception.Response) { break } else { Start-Sleep -Seconds 1 } } }
Start-Process http://localhost:4173                              # 浏览器打开后按下面「界面操作」走
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/contrast -ContentType "application/json" -Body '{"foreground":{"color":"rgb(255,255,255)","alpha":0.5},"background":[{"color":null}],"threshold":4.5}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：A 为 400（请求体是 B 的字段）；B 为 verdict=undetermined，ratio 下界=1
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/contrast -ContentType "application/json" -Body '{"foreground":{"kind":"paint","color":{"rgb":[1,1,1],"alpha":0.5}},"backgrounds":[{"kind":"unknown"}],"threshold":4.5}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：A 返回对比度区间，下界来自压黑/压白两端点、高于 1；B 为 400
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:4173。A：点「对比度解释」打开右侧面板「对比度解释视图」；B：Inspection 面板下方就是 Contrast 区域，字段「Text color」「Text alpha」「Background layers (top → bottom,」「Threshold」。
2. A：用「场景」下拉切换预置向量，查看判定、最终亮度、「每层颜色来源」与「逐层合成（线性 sRGB）」；B：填入文字颜色与 alpha，背景层每行一层，行尾可跟 alpha，问号或 unknown 表示未知底色。
3. 切到未知底色场景。A：点「纯黑」「纯白」切换两条管线，区间只由这两个端点取 min/max，半透明文字压未知底色时下界偏高，可能把应判不确定的配色判成通过；B：即时给出 pass / fail / undetermined，穿越时下界落到 1。
4. A：点「请求服务端核对」，页面显示服务端结果、cacheKey、cacheHit；B：点「Evaluate」，显示服务端结论、缓存命中、是否与本地模块一致。
5. 再核对一次相同输入。A：cache 键含色彩空间、分量、alpha、层 kind 与 id，不同来源不会串缓存；B：cache 键只归一化到 sRGB 分量与 alpha，钳制后相同的广色域层会命中同一条缓存，来源和降级告警可能对不上当前层。
6. 回到终端执行剩下的接口命令并 `taskkill`。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/a11y-alpha-contrast-web.git a11y-alpha-contrast-web-B
cd a11y-alpha-contrast-web-B
npm ci
npm test                                                         # 预期：观察 vitest 结果
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { if ($_.Exception.Response) { break } else { Start-Sleep -Seconds 1 } } }
Start-Process http://localhost:4173                              # 浏览器打开后按下面「界面操作」走
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/contrast -ContentType "application/json" -Body '{"foreground":{"color":"rgb(255,255,255)","alpha":0.5},"background":[{"color":null}],"threshold":4.5}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：verdict=undetermined，ratio 下界=1
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/contrast -ContentType "application/json" -Body '{"foreground":{"kind":"paint","color":{"rgb":[1,1,1],"alpha":0.5}},"backgrounds":[{"kind":"unknown"}],"threshold":4.5}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：400
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 1、3、4、5 步。

---

## 第 183 题　Feature 迭代　·　困难　·　全栈
<!-- solo-report:task=183 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/release-impact-plan-web　A 分支：https://github.com/gy-vs/release-impact-plan-web/tree/A　B 分支：https://github.com/gy-vs/release-impact-plan-web/tree/B

服务：`npm run dev` 同时起 Express API 4174 与 Vite 前端 4173；浏览器开 http://localhost:4173。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/release-impact-plan-web.git release-impact-plan-web-A
cd release-impact-plan-web-A
npm ci
npm test   # 预期：53 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/graph | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                              # 被占用会自动 +1，以新窗口打出的 Local: 地址为准
(Invoke-RestMethod http://127.0.0.1:4174/api/graph).revision   # 预期：1（16 个节点 / 23 条边）
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/plan/compute -ContentType "application/json" -Body '{"revision":1,"changes":[{"id":"core","to":"2.0.0"}]}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：ok true，candidates 含 core@2.0.0(major)、utils@3.0.0(major)、app@5.0.0(major)
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/plan/compute -ContentType "application/json" -Body '{"revision":1,"changes":[{"id":"peer-lib","to":"2.0.0"}]}' } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：422（peer 互斥，无法满足）
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/plan/compute -ContentType "application/json" -Body '{"revision":99,"changes":[]}' } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：409
try { Invoke-RestMethod http://127.0.0.1:4174/api/health | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:4173，看到顶栏「Release Dependency Studio」。A：中栏有「2. 选择包变更」和按钮「计算候选版本计划」，左栏有「依赖（出边）」「被依赖（入边）」；B：顶栏有「Full recompute」「Edit graph」，中间是「Dependency graph」SVG。
2. 勾选 `core`，升级级别选 `major`（或指定版本输入 `2.0.0`），点击「计算候选版本计划」。A：候选表出现 core@2.0.0(major) 以及沿图传播的 utils / app 等；B：无此按钮，左侧改种子后页面会自动算计划，图上种子节点带光环。
3. 在候选行里改某个版本，点击该行「增量重算」。A：受影响行更新，未受影响行标「沿用上轮」；B：无「增量重算」按钮，改版本后点候选面板的重算子图，状态栏出现 affected / reused 计数。
4. 打开冲突或原因链，点一条原因边。A：只把起点包选中，提示「已在左栏定位原因边」；B：图上对应边高亮，无关边变暗。
5. 左栏并发区点击「旧 revision 提交」。A：状态提示 409；再点「提交修改」成功。B：无这两个按钮，点「Edit graph」提交后按新 revision 重算。
6. 回到终端执行剩下的接口命令并关服务。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/release-impact-plan-web.git release-impact-plan-web-B
cd release-impact-plan-web-B
npm ci
npm test   # 预期：33 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/graph | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                              # 被占用会自动 +1，以新窗口打出的 Local: 地址为准
(Invoke-RestMethod http://127.0.0.1:4174/api/graph).revision   # 预期：1（13 个节点）
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/plan/compute -ContentType "application/json" -Body '{"revision":1,"changes":[{"id":"core","to":"2.0.0"}]}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404 Cannot POST /api/plan/compute
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/plan/compute -ContentType "application/json" -Body '{"revision":1,"changes":[{"id":"peer-lib","to":"2.0.0"}]}' } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/plan/compute -ContentType "application/json" -Body '{"revision":99,"changes":[]}' } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
try { Invoke-RestMethod http://127.0.0.1:4174/api/health | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：{"ok":true,"mode":"local-simulation"}
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 1、2、3、4、5 步。

---

## 第 184 题　Bug 修复　·　困难　·　全栈
<!-- solo-report:task=184 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/release-prerelease-range-web　A 分支：https://github.com/gy-vs/release-prerelease-range-web/tree/A　B 分支：https://github.com/gy-vs/release-prerelease-range-web/tree/B

服务：`npm run dev` 同时起 Express API 4174 与 Vite 前端 4173；浏览器开 http://localhost:4173。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/release-prerelease-range-web.git release-prerelease-range-web-A
cd release-prerelease-range-web-A
npm ci
npm test   # 预期：57 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/plans | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                              # 被占用会自动 +1，以新窗口打出的 Local: 地址为准
Invoke-RestMethod http://127.0.0.1:4174/api/plans | ConvertTo-Json -Compress   # 预期：alpha Primary package graphs revision 3；beta Secondary package graphs revision 5
try { $c = Invoke-RestMethod http://127.0.0.1:4174/api/plans/alpha/candidates; ($c.candidates | ForEach-Object { $_.raw }) -join ' ' } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：顺序含 2.0.0-rc.2 在 2.0.0-rc.10 之前，其后是 2.0.0；invalid 含 2.0.0-rc..2、v2.0.2、latest
try { (Invoke-RestMethod http://127.0.0.1:4174/api/plans/beta/candidates).candidates | Where-Object { $_.raw -like '*rc*' } | ForEach-Object { $_.raw + '/' + $_.included } } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：2.0.0-rc.2/False 与 2.0.0-rc.10/False（稳定范围排除预发布）
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/plans/alpha/resolve -ContentType "application/json" -Body '{}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404 Cannot POST /api/plans/alpha/resolve
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:4173，左栏点「Primary package graphs」。A：中栏有「Range」「Include prereleases」「Preview」「Save」「Analyze」；右栏标题「Candidates」。B：中栏是「Range expression」和「Save plan」，无 Preview / Analyze，右侧是「Inspection」。
2. 看候选列表。A：`2.0.0-rc.2` 排在 `2.0.0-rc.10` 之前，末尾红色块「Unparseable versions — kept as received」列出 `2.0.0-rc..2` / `v2.0.2` / `latest`；B：Inspection 里同样 rc.2 在 rc.10 前，无效条目在「Invalid input」分组，不混进有序列表。
3. 勾选「Include prereleases」后点「Preview」。A：面板 pill 变为 `prereleases included`，并出现 `cache miss` / 再点一次变 `cache hit`；B：无 Preview 按钮，勾选「Include prereleases even when the range does not mention them」后自动重算，工具栏可能出现 `resolved from cache`。
4. 切到「Secondary package graphs」。A：稳定范围 `>=1.0.0 <3.0.0` 下 rc 版本标 `excluded`；B：点筛选「In range」，预发布不在命中集合里。
5. 点「Save」（B 为「Save plan」），刷新页面再打开同一计划。两侧候选集合与保存前所见一致。
6. 回到终端执行剩下的接口命令并关服务。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/release-prerelease-range-web.git release-prerelease-range-web-B
cd release-prerelease-range-web-B
npm ci
npm test   # 预期：观察 passed 数（收尾改动后未再复跑）
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/plans | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                              # 被占用会自动 +1，以新窗口打出的 Local: 地址为准
Invoke-RestMethod http://127.0.0.1:4174/api/plans | ConvertTo-Json -Compress   # 预期：alpha / beta 两条，无 range 字段
try { $c = Invoke-RestMethod http://127.0.0.1:4174/api/plans/alpha/candidates; ($c.candidates | ForEach-Object { $_.raw }) -join ' ' } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404 Cannot GET /api/plans/alpha/candidates
try { (Invoke-RestMethod http://127.0.0.1:4174/api/plans/beta/candidates).candidates | Where-Object { $_.raw -like '*rc*' } | ForEach-Object { $_.raw + '/' + $_.included } } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/plans/alpha/resolve -ContentType "application/json" -Body '{}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：candidates 顺序 2.0.0-rc.2 在 2.0.0-rc.10 之前，2.0.0 included true，invalidCandidates 单独列出
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 1、3 步。

---

## 第 185 题　Feature 迭代　·　困难　·　全栈
<!-- solo-report:task=185 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/release-provenance-chain-web　A 分支：https://github.com/gy-vs/release-provenance-chain-web/tree/A　B 分支：https://github.com/gy-vs/release-provenance-chain-web/tree/B

服务：`npm run dev` 同时起 Express API 4174 与 Vite 前端 4173；浏览器开 http://localhost:4173。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/release-provenance-chain-web.git release-provenance-chain-web-A
cd release-provenance-chain-web-A
npm ci
npm test   # 预期：34 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/packages | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                              # 被占用会自动 +1，以新窗口打出的 Local: 地址为准
try { Invoke-RestMethod http://127.0.0.1:4174/api/health | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：{"ok":true,"keyId":"ed25519:e7935333ecb57c0b"}
(Invoke-RestMethod http://127.0.0.1:4174/api/packages).packages | ForEach-Object { $_.packageId }   # 预期：pkg-pending pkg-valid pkg-digest-bad pkg-sig-bad pkg-big
try { Invoke-RestMethod http://127.0.0.1:4174/api/info | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
try { (Invoke-RestMethod 'http://127.0.0.1:4174/api/nodes/pkg-pending-build/parent').edge.state } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：missing_parent
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:4173。A：顶栏「发布依赖工作台 · 构建来源声明链」和「重置样例」，左栏已列出 pkg-pending / pkg-valid / pkg-digest-bad / pkg-sig-bad / pkg-big；B：左栏是 pkg-good 等样例，初始多数包还没有附加声明，主按钮是「附加声明（本地样例）」。
2. 点 `pkg-digest-bad`（B 点 `pkg-digest`），看产物追溯。A：中栏「产物追溯入口」自动沿主脊展开到源码，边上徽标点开后对照「子声明的父摘要 vs 实际父声明摘要」，节点徽标为「摘要不符」；B：需先点「附加声明（本地样例）」，再点节点左侧展开箭头逐边加载，边上并排「链接边 parentDigest」和「摘要边 claimedDigest」，断裂处 claimed ≠ expected。
3. 点 `pkg-pending`（B 点 `pkg-orphan`）。A：详情里点「补投缺失的父声明（测试乱序到达）」，节点从「等待父声明」转为已验证；B：先附加声明看到挂起，再点「补发缺失父声明」，操作日志出现 pending_parent 然后释放。
4. 点 `pkg-big`（B 点 `pkg-large`）。A：入口多时点「加载更多产物」，分叉处点「展开 N 条分叉」才加载；主脊会一次走满。B：每次只请求一条父边，未展开分支不传输；点「替换声明 revision（局部重算）」后日志列出 recomputed 槽位。
5. 在节点上选审阅状态并点「保存标记（携带 revision …）」。A：替换 revision 后旧标记保留并标过期；B：审阅挂在槽位上，点「确认异常」或「忽略」，重复保存可看到 409 提示。
6. 回到终端执行剩下的接口命令并关服务。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/release-provenance-chain-web.git release-provenance-chain-web-B
cd release-provenance-chain-web-B
npm ci
npm test   # 预期：23 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/packages | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                              # 被占用会自动 +1，以新窗口打出的 Local: 地址为准
try { Invoke-RestMethod http://127.0.0.1:4174/api/health | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
(Invoke-RestMethod http://127.0.0.1:4174/api/packages).packages | ForEach-Object { $_.packageId }   # 预期：pkg-digest pkg-dup pkg-fork pkg-good pkg-large pkg-orphan pkg-sigfail
try { Invoke-RestMethod http://127.0.0.1:4174/api/info | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：family release-provenance-chain，trustedKeyIds 含 test-key-1
try { (Invoke-RestMethod 'http://127.0.0.1:4174/api/nodes/pkg-pending-build/parent').edge.state } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 1、2、3、4、5 步。

---

## 第 186 题　Bug 修复　·　困难　·　全栈
<!-- solo-report:task=186 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/release-cycle-collapse-web　A 分支：https://github.com/gy-vs/release-cycle-collapse-web/tree/A　B 分支：https://github.com/gy-vs/release-cycle-collapse-web/tree/B

服务：`npm run dev` 同时起 Express API 4174 与 Vite 前端 4173；浏览器开 http://localhost:4173。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/release-cycle-collapse-web.git release-cycle-collapse-web-A
cd release-cycle-collapse-web-A
npm ci
npm test   # 预期：22 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/plans | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                              # 被占用会自动 +1，以新窗口打出的 Local: 地址为准
Invoke-RestMethod http://127.0.0.1:4174/api/plans | ConvertTo-Json -Compress   # 预期：含 alpha、beta
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/plans/alpha/analyze -ContentType "application/json" -Body '{"root":"web","rootVersion":"1.0.0"}' | ConvertTo-Json -Compress   # 预期：body.analysis.components 含 scc[core,web] cyclic true、scc[util] 自环；折叠不在请求里
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/plans/beta/analyze -ContentType "application/json" -Body '{"root":"app","rootVersion":"2.0.0"}' | ConvertTo-Json -Compress   # 预期：analysis.conflicts 含 app / lib 的 conflicting_range，原因链经 app->lib
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/plans/alpha/analyze -ContentType "application/json" -Body '{"root":"web","rootVersion":"1.0.0","knownRevision":1}' } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：409 revision_conflict
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/plans/alpha/analyze -ContentType "application/json" -Body '{"root":"web","rootVersion":"1.0.0","revision":99}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：200（A 只认 knownRevision，忽略 revision）
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:4173，左栏选 alpha。A：工具栏有「Save」「Analyze impact」、root 下拉和「Root version」；右栏标题「Impact」。B：工具栏是「Save」「Analyze」，右栏「Inspection」。
2. root 选 `web`，version 填 `1.0.0`，点「Analyze impact」。A：出现「Cycle group」分组（core/web）、util 自环，以及每个包的协商区间与 required 版本；B：无 root 下拉，点「Analyze」后 Components 列出 alpha/beta 环（带 cycle 徽标），环外 gamma、delta 也在影响集，delta 经 optional 边为 patch。
3. 点分组标题反复折叠与展开。两侧右栏影响数字不随折叠变化（折叠只影响显示，不发给服务端）。
4. 左栏切到 beta 再分析。A：出现「Blocking range conflicts」，原因链穿过环指到具体边；B：若默认图无冲突，需在 Content 里写两条无法同时满足的边再点 Analyze，看 Diagnostics。
5. 在 Content 改一行后点「Save」抬升 revision，再分析。A：状态栏出现图已变更 / `(draft newer than analysis)`，遇 409 会重新拉取；B：界面不发送 revision，状态栏仍是 Ready，409 只能靠接口带旧 revision 看到。
6. 回到终端执行剩下的接口命令并关服务。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/release-cycle-collapse-web.git release-cycle-collapse-web-B
cd release-cycle-collapse-web-B
npm ci
npm test   # 预期：21 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/plans | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                              # 被占用会自动 +1，以新窗口打出的 Local: 地址为准
Invoke-RestMethod http://127.0.0.1:4174/api/plans | ConvertTo-Json -Compress   # 预期：含 alpha、beta
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/plans/alpha/analyze -ContentType "application/json" -Body '{"root":"web","rootVersion":"1.0.0"}' | ConvertTo-Json -Compress   # 预期：顶层 components 含 c0 cycle members alpha,beta；impacts 含 alpha/major、gamma/major、delta/patch
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/plans/beta/analyze -ContentType "application/json" -Body '{"root":"app","rootVersion":"2.0.0"}' | ConvertTo-Json -Compress   # 预期：观察 impacts / diagnostics（B 的 beta 图不一定有 A 那种 ^1/^2 冲突）
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/plans/alpha/analyze -ContentType "application/json" -Body '{"root":"web","rootVersion":"1.0.0","knownRevision":1}' } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：200（B 不读 knownRevision）
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/plans/alpha/analyze -ContentType "application/json" -Body '{"root":"web","rootVersion":"1.0.0","revision":99}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：409 revision_conflict
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 1、2、4、5 步。

---

## 第 187 题　Feature 迭代　·　困难　·　全栈
<!-- solo-report:task=187 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/release-wave-simulator-web　A 分支：https://github.com/gy-vs/release-wave-simulator-web/tree/A　B 分支：https://github.com/gy-vs/release-wave-simulator-web/tree/B

服务：`npm run dev` 同时起 Express API 4174 与 Vite 前端 4173；浏览器开 http://localhost:4173。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/release-wave-simulator-web.git release-wave-simulator-web-A
cd release-wave-simulator-web-A
npm ci
npm test   # 预期：15 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/plans | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                              # 被占用会自动 +1，以新窗口打出的 Local: 地址为准
Invoke-RestMethod http://127.0.0.1:4174/api/plans | ConvertTo-Json -Compress   # 预期：[{id:release-1,revision:1,waves:4}]
try { Invoke-RestMethod http://127.0.0.1:4174/api/registry | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：含 core、plugin-a、plugin-b、api 等包定义
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/plans/release-1/simulate -ContentType "application/json" -Body '{"failedWaves":["w1"]}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：ok false，w1 rolledBack，api 与 web 被级联 blocked
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/plans/release-1/moves -ContentType "application/json" -Body '{"baseRevision":1,"moves":[{"packageId":"plugin-a","toWave":"w3"}]}' } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：422 validation_failed（环被拆波，计划不变）
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/plans/alpha/touch } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:4173。A：顶栏「Release Dependency Studio」，看板四波 Foundations / Connectors / Services / Apps，卡片 core、utils、docs、plugin-a、plugin-b、api、web，顶栏按钮「Undo」；B：顶栏「发布依赖工作台」，波次 1–4 放 core-a / core-b / lib-x 等，另有「撤销」「模拟并发编辑」和「双版本兼容窗口」。
2. 把 plugin-a（B 把 core-a）拖到别的波次。两侧本地预测立刻拒绝并给出最短原因链（环必须同波）。
3. 勾选某波标题上的 fail（B 为「失败」）。A：右栏出现回滚模拟，web 经 api→core 三跳被阻塞；B：时间线出现「波次失败，原子回滚」。
4. 点顶栏「Undo」（B 为「撤销」）。A：按逆移动重新走校验，历史不存整份旧计划；B：本地是快照回退（history 带 before），服务端提交才用逆移动。
5. 并发。A：界面没有制造 revision 前进的按钮，需用接口打 moves 才能看到 409 重放；B：先点「模拟并发编辑」再拖一个合法包，提示保留移动意图并在新计划上重放。B 另可改「双版本兼容窗口」数值；A 的 window 只读显示在 Registry 的 `window closes at wave`。
6. 回到终端执行剩下的接口命令并关服务。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/release-wave-simulator-web.git release-wave-simulator-web-B
cd release-wave-simulator-web-B
npm ci
npm test   # 预期：观察 passed 数
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/plans | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                              # 被占用会自动 +1，以新窗口打出的 Local: 地址为准
Invoke-RestMethod http://127.0.0.1:4174/api/plans | ConvertTo-Json -Compress   # 预期：[{id:alpha,name:Demo release train,revision:1,waves:4,window:3}]
try { Invoke-RestMethod http://127.0.0.1:4174/api/registry | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/plans/release-1/simulate -ContentType "application/json" -Body '{"failedWaves":["w1"]}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/plans/release-1/moves -ContentType "application/json" -Body '{"baseRevision":1,"moves":[{"packageId":"plugin-a","toWave":"w3"}]}' } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/plans/alpha/touch } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：200，revision 变为 2
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 1、4、5 步。

---

## 第 189 题　Feature 迭代　·　困难　·　全栈
<!-- solo-report:task=189 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/redaction-review-state-web　A 分支：https://github.com/gy-vs/redaction-review-state-web/tree/A　B 分支：https://github.com/gy-vs/redaction-review-state-web/tree/B

服务：`npm run dev` 同时起 Express API 4174 与 Vite 前端 4173；浏览器开 http://localhost:4173。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/redaction-review-state-web.git redaction-review-state-web-A
cd redaction-review-state-web-A
npm ci
npm test   # 预期：16 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/documents | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                              # 被占用会自动 +1，以新窗口打出的 Local: 地址为准
Invoke-RestMethod http://127.0.0.1:4174/api/detectors | ConvertTo-Json -Compress   # 预期：versions 1.0.0 与 2.0.0
Invoke-RestMethod http://127.0.0.1:4174/api/documents | ConvertTo-Json -Compress   # 预期：alpha 客户联络单 revision 3；beta 外发公告草稿
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/documents/alpha/analyze -ContentType "application/json" -Body '{"detectorVersion":"2.0.0","expectedRev":3}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：findings 含 email/phone origin unchanged，以及 id_card presence new
try { Invoke-RestMethod http://127.0.0.1:4174/api/audit | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：events 含 analyze
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:4173，左栏选 alpha。A：文档名「客户联络单」，按钮「保存编辑」「运行 / 重复检测」，右栏四泳道「待审 / 接受 / 拒绝 / 已应用」；B：文档名「Primary redaction findings」，按钮「保存」「检测」，阶段 Tab 同样四态。
2. 检测器选低版本后点「运行 / 重复检测」（B 选 detector-1 后点「检测」）。A：待审泳道出现邮箱与手机；B：同样出现 email#1 与 phone#1。B 需先点一下右栏 Tab，否则热键不生效。
3. 键盘批量。A：窗口级按键，不勾选时按 A 接受整条待审泳道，也可点「全部接受」；B：热键只作用于光标那一条，批量要点「全部接受待审」。
4. 把检测器切到高版本再检测一次。A：email/phone 标沿用（unchanged），身份证标「新出现」，消失项进「已消失（保留追溯，不参与生成）」；B：按 ruleId#occurrence 复用，文档中部若插入新命中，旧决策可能落到别的值上。
5. 待审清零后点「生成最终脱敏文本」（B 为「冻结并生成最终文本」）。冻结后再改决策。A：被拒，文案「该批次已冻结并生成最终文本，决策不可再修改」；B：卡片操作区消失。再改文档并「保存编辑」后点生成。A：文档 revision 冲突；B：出现「检测已过期」，冻结按钮禁用。
6. 回到终端执行剩下的接口命令并关服务。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/redaction-review-state-web.git redaction-review-state-web-B
cd redaction-review-state-web-B
npm ci
npm test   # 预期：观察 passed 数
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/documents | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                              # 被占用会自动 +1，以新窗口打出的 Local: 地址为准
Invoke-RestMethod http://127.0.0.1:4174/api/detectors | ConvertTo-Json -Compress   # 预期：versions detector-1、detector-2，latest detector-2
Invoke-RestMethod http://127.0.0.1:4174/api/documents | ConvertTo-Json -Compress   # 预期：alpha Primary redaction findings revision 3
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/documents/alpha/analyze -ContentType "application/json" -Body '{"detectorVersion":"2.0.0","expectedRev":3}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：观察 4xx 或空（B 的版本名是 detector-2 不是 2.0.0）
try { Invoke-RestMethod http://127.0.0.1:4174/api/audit | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 1、2、3、4、5 步。

---

## 第 190 题　Bug 修复　·　困难　·　全栈
<!-- solo-report:task=190 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/redaction-overlap-merge-web　A 分支：https://github.com/gy-vs/redaction-overlap-merge-web/tree/A　B 分支：https://github.com/gy-vs/redaction-overlap-merge-web/tree/B

服务：`npm run dev` 同时起 Express API 4174 与 Vite 前端 4173；浏览器开 http://localhost:4173。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/redaction-overlap-merge-web.git redaction-overlap-merge-web-A
cd redaction-overlap-merge-web-A
npm ci
npm test   # 预期：32 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/documents | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                              # 被占用会自动 +1，以新窗口打出的 Local: 地址为准
(Invoke-RestMethod http://127.0.0.1:4174/api/documents/alpha).content   # 预期：含 北京市海淀区中关村大街1号 与 🎉
try { Invoke-RestMethod http://127.0.0.1:4174/api/documents/alpha/suggestions | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：revision 3，ranges 含 addr-1 吞 name-1、conflict-a/conflict-b 部分相交、zero-tail 零长度
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/documents/alpha/redaction/plan -ContentType "application/json" -Body '{"revision":3,"ranges":[]}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：ready true，preview 仍是原文（空 ranges）
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/documents/alpha/redactions/plan -ContentType "application/json" -Body '{"revision":3,"ranges":[]}' } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/documents/alpha/redaction/plan -ContentType "application/json" -Body '{"revision":2,"ranges":[]}' } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：409 revision_conflict
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:4173，左栏选 alpha。A：下方「脱敏审阅」面板，正文已是带地址/姓名/表情的中文样例；B：正文仍是 `redaction findings: alpha`，工具栏「Save」「Analyze」「Build plan」「Apply redactions」。
2. A：点「接受全部非零建议」再点「构建规范集合」。右侧列出规范范围，外层吞内层处写「外层策略主导，内层仅保留审计引用」，并提示「部分相交，策略冲突」。B：若要复现包含/相交需先改正文点「Save」（未保存时 Build plan 禁用），再「Analyze」后「Build plan」。
3. 解决冲突。A：在冲突卡片点某个范围 id（如 conflict-b），选完立即重算，预览变为 `收件地址：████…` / `备用地址：` / `备注：张三同时负责[地点] 完成。`，「张三」等原文不再出现；B：在「Winning strategy」下拉选策略后，冲突区块连同「Rebuild plan」一起卸掉，必须回工具栏再点「Build plan」。
4. 点「预览（不落库）」再点「应用并保存」。A：服务端若检出泄露会拒绝（文案「服务端检测到原文泄露，已拒绝输出」），成功则提示「输出不含任何已接受范围原文」；B：点「Apply redactions」，泄露只进 leaks 列表仍返回 output，可再点「Use as draft」。
5. 相邻范围：A 规范集合里同策略带「相邻同策略已合并」，不同策略保持两条；B 在 Canonical spans 的 audit refs 里观察合并或拆分。
6. 回到终端执行剩下的接口命令并关服务。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/redaction-overlap-merge-web.git redaction-overlap-merge-web-B
cd redaction-overlap-merge-web-B
npm ci
npm test   # 预期：观察 passed 数
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/documents | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                              # 被占用会自动 +1，以新窗口打出的 Local: 地址为准
(Invoke-RestMethod http://127.0.0.1:4174/api/documents/alpha).content   # 预期：redaction findings: alpha\nstate: active
try { Invoke-RestMethod http://127.0.0.1:4174/api/documents/alpha/suggestions | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/documents/alpha/redaction/plan -ContentType "application/json" -Body '{"revision":3,"ranges":[]}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/documents/alpha/redactions/plan -ContentType "application/json" -Body '{"revision":3,"ranges":[]}' } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：200 {"revision":3,"status":"ok","spans":[]}
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/documents/alpha/redaction/plan -ContentType "application/json" -Body '{"revision":2,"ranges":[]}' } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 1、2、3、4 步。

---

## 第 191 题　Feature 迭代　·　困难　·　全栈
<!-- solo-report:task=191 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/redaction-policy-sim-web　A 分支：https://github.com/gy-vs/redaction-policy-sim-web/tree/A　B 分支：https://github.com/gy-vs/redaction-policy-sim-web/tree/B

服务：`npm run dev` 同时起 Express API 4174 与 Vite 前端 4173；浏览器开 http://localhost:4173。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/redaction-policy-sim-web.git redaction-policy-sim-web-A
cd redaction-policy-sim-web-A
npm ci
npm test   # 预期：15 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/policy | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                              # 被占用会自动 +1，以新窗口打出的 Local: 地址为准
Invoke-RestMethod http://127.0.0.1:4174/api/policy | ConvertTo-Json -Compress   # 预期：revision 1，hash 09a0cae4b12edfd9，rules 含 r-id-card / r-phone / r-email / r-bank-card
Invoke-RestMethod http://127.0.0.1:4174/api/samples | ConvertTo-Json -Compress   # 预期：basic / overlap / threshold / broken 四条
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/policy/compile -ContentType "application/json" -Body '{}' } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：400 malformed_policy
try { Invoke-RestMethod http://127.0.0.1:4174/api/documents | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:4173。A：顶栏「文本脱敏审阅工作台」，显示服务端策略 revision 与草稿哈希，按钮「保存策略」「运行模拟」；左栏「添加规则」和规则名称。B：顶栏「已保存 rev」，按钮「保存策略」「对全部样例模拟」「刷新样例」，左栏「+ 新建派生」「+ 新建规则」。
2. 改一条规则的名称或阈值，或点「上移」调整优先级。A：顶栏哈希立刻变，旧模拟（若有）标「已过期：草稿或样例已变更，结果仅用于对照」；B：诊断面板草稿哈希变化，结果区「⚠ 结果已过期（保留用于对照）」。B 的规则可以勾选并集/交集检测器组合；A 每条规则只能单选一个检测器。
3. 点「运行模拟」（B 为「对全部样例模拟」）。A：中栏按样例列出范围归因与被覆盖原因，右栏先「部分统计（进行中）」再转「最终统计」；B：右栏先出逐样例部分统计卡片，结束后「最终统计」。
4. 模拟进行中点「取消模拟」。A：真正中断流，右栏转为「已取消（部分结果）」；B：按钮只把本地标成已取消，服务端仍跑完，界面可能同时显示已取消与完整最终结果。
5. 并发保存：两个标签都点「保存策略」。后保存一方。A：横幅「保存冲突」并出现「加载最新策略」；B：提示冲突并出现「加载服务端版本（rev …）」。
6. 回到终端执行剩下的接口命令并关服务。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/redaction-policy-sim-web.git redaction-policy-sim-web-B
cd redaction-policy-sim-web-B
npm ci
npm test   # 预期：观察 passed 数
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/policy | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                              # 被占用会自动 +1，以新窗口打出的 Local: 地址为准
Invoke-RestMethod http://127.0.0.1:4174/api/policy | ConvertTo-Json -Compress   # 预期：name 默认脱敏策略，detectors 含 contact（union）与 contact_secret（intersect）
Invoke-RestMethod http://127.0.0.1:4174/api/samples | ConvertTo-Json -Compress   # 预期：alpha / beta / gamma / delta
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/policy/compile -ContentType "application/json" -Body '{}' } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：400 invalid_draft 草稿必须包含 rules 与 detectors 数组
try { Invoke-RestMethod http://127.0.0.1:4174/api/documents | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：200 文档列表（基线 CRUD 仍在）
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 1、2、4、5 步。

---

## 第 193 题　Feature 迭代　·　困难　·　无界面
<!-- solo-report:task=193 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/mime-alternative-stream-core　A 分支：https://github.com/gy-vs/mime-alternative-stream-core/tree/A　B 分支：https://github.com/gy-vs/mime-alternative-stream-core/tree/B

存为 `verify_193.mjs`（放在仓库根目录）

```javascript
import * as api from './dist/index.js';

const enc = new TextEncoder();
const dec = new TextDecoder();

function timeout(ms) {
  return new Promise((_, rej) => setTimeout(() => rej(new Error('timeout')), ms));
}

async function collect(iter) {
  const chunks = [];
  if (!iter) return '';
  for await (const c of iter) chunks.push(c);
  return dec.decode(chunks.length ? Buffer.concat(chunks.map((c) => Buffer.from(c))) : Buffer.alloc(0));
}

const mixed =
  'Content-Type: multipart/mixed; boundary=outer\r\n\r\n' +
  '--outer\r\nContent-Type: text/plain\r\n\r\nAAA\r\n' +
  '--outer\r\nContent-Type: text/plain\r\n\r\nBBB\r\n' +
  '--outer--\r\n';

const nestedMissing =
  'Content-Type: multipart/mixed; boundary=outer\r\n\r\n' +
  '--outer\r\nContent-Type: multipart/alternative; boundary=inner\r\n\r\n' +
  '--inner\r\nContent-Type: text/plain\r\n\r\nplain\r\n' +
  '--outer\r\nContent-Type: text/plain\r\n\r\nsibling\r\n' +
  '--outer--\r\n';

const badHeader =
  'Content-Type: multipart/mixed; boundary=x\r\n\r\n' +
  '--x\r\nBad Header Without Colon\r\nContent-Type: text/plain\r\n\r\nok\r\n' +
  '--x--\r\n';

async function parseA(bytes, onBody) {
  const events = [];
  const parser = new api.MimeParser({
    onEvent: (ev) => {
      events.push(ev.type);
      if (ev.type === 'part-start' && ev.node && ev.node.body && onBody) onBody(ev.node.body);
      if (ev.type === 'diagnostic') events.push('diag:' + ev.diagnostic.code + '@' + ev.diagnostic.offset);
    },
  });
  for (let i = 0; i < bytes.length; i++) await parser.feed(bytes.subarray(i, i + 1));
  await parser.end();
  return events;
}

async function parseB(bytes, onBody) {
  const events = [];
  const parser = new api.MimeParser();
  const consumer = (async () => {
    for await (const ev of parser.events()) {
      events.push(ev.type);
      if (ev.type === 'part-start' && ev.part && ev.part.body && onBody) await onBody(ev.part.body);
      if (ev.type === 'error') events.push('diag:' + (ev.error && ev.error.code) + '@' + (ev.error && ev.error.offset));
      if (ev.type === 'done') events.push('diag-count:' + (ev.errors ? ev.errors.length : 0));
    }
  })();
  for (let i = 0; i < bytes.length; i++) await parser.feed(bytes.subarray(i, i + 1));
  await parser.end();
  await consumer;
  return events;
}

const isA = typeof new api.MimeParser().events !== 'function';

async function runNormal() {
  const bytes = enc.encode(mixed);
  const bodies = [];
  const events = isA
    ? await parseA(bytes, (body) => { bodies.push(collect(body)); })
    : await parseB(bytes, async (body) => { bodies.push(await collect(body)); });
  if (isA) await Promise.all(bodies);
  const texts = isA ? await Promise.all(bodies) : bodies;
  console.log('events', events.join(','));
  console.log('bodies', JSON.stringify(texts));
}

await runNormal();

async function runNested() {
  const bytes = enc.encode(nestedMissing);
  try {
    if (isA) {
      const texts = [];
      const events = await parseA(bytes, (body) => { texts.push(collect(body)); });
      const bodies = await Promise.all(texts);
      console.log('nested-events', events.filter((e) => e === 'part-start' || e.startsWith('diag:')).join(','));
      console.log('nested-bodies', JSON.stringify(bodies));
    } else {
      const bodies = [];
      const events = await parseB(bytes, async (body) => { bodies.push(await collect(body)); });
      console.log('nested-events', events.filter((e) => e === 'part-start' || String(e).startsWith('diag')).join(','));
      console.log('nested-bodies', JSON.stringify(bodies));
    }
  } catch (e) {
    console.log('nested-events', e.name + ':' + (e.code || '') + '@' + (e.offset || ''));
    console.log('nested-bodies', 'threw');
  }
}

await runNested();

async function runBad() {
  const bytes = enc.encode(badHeader);
  if (isA) {
    const events = await parseA(bytes);
    console.log('bad-header', events.filter((e) => String(e).startsWith('diag') || e === 'part-start').join(','));
  } else {
    const events = await parseB(bytes);
    console.log('bad-header', events.filter((e) => String(e).startsWith('diag') || e === 'part-start').join(','));
  }
}

await runBad();

let abortedHung = false;
{
  const big =
    'Content-Type: multipart/mixed; boundary=x\r\n\r\n--x\r\nContent-Type: application/octet-stream\r\n\r\n' +
    'Z'.repeat(200000) +
    '\r\n--x\r\nContent-Type: text/plain\r\n\r\nsecond\r\n--x--\r\n';
  const bytes = enc.encode(big);
  if (isA) {
    let aborted = false;
    const parser = new api.MimeParser({
      onEvent: (ev) => {
        if (ev.type === 'part-start' && ev.node && ev.node.body && !aborted) {
          aborted = true;
          void (async () => {
            for await (const chunk of ev.node.body) {
              void chunk;
              break;
            }
          })();
        }
      },
    });
    const work = (async () => {
      for (let i = 0; i < bytes.length; i += 16384) await parser.feed(bytes.subarray(i, i + 16384));
      await parser.end();
    })();
    try {
      await Promise.race([work, timeout(1500)]);
      console.log('abort-feed', 'resolved');
    } catch (e) {
      abortedHung = true;
      console.log('abort-feed', e.message);
    }
  } else {
    const parser = new api.MimeParser();
    let aborted = false;
    const consumer = (async () => {
      for await (const ev of parser.events()) {
        if (ev.type === 'part-start' && ev.part && ev.part.body && !aborted) {
          aborted = true;
          for await (const chunk of ev.part.body) {
            void chunk;
            break;
          }
        }
      }
    })();
    const work = (async () => {
      for (let i = 0; i < bytes.length; i += 16384) await parser.feed(bytes.subarray(i, i + 16384));
      await parser.end();
      await consumer;
    })();
    try {
      await Promise.race([work, timeout(1500)]);
      console.log('abort-feed', 'resolved');
    } catch (e) {
      abortedHung = true;
      console.log('abort-feed', e.message);
    }
  }
}
if (abortedHung) process.exit(0);
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/mime-alternative-stream-core.git mime-alternative-stream-core-A
cd mime-alternative-stream-core-A
npm ci
npm run build
npm test                                                          # 预期：21 passed
node verify_193.mjs                                                     # 预期：events message-start,part-start,part-end,part-start,part-end,message-end；bodies ["AAA","BBB"]；nested-events part-start,part-start,diag:unexpected-eof@155,part-start；nested-bodies ["plain","sibling"]；bad-header diagnostic,diag:malformed-header-line@50,part-start；abort-feed resolved
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/mime-alternative-stream-core.git mime-alternative-stream-core-B
cd mime-alternative-stream-core-B
npm ci
npm run build
npm test                                                          # 预期：34 passed
node verify_193.mjs                                                     # 预期：events part-start,part-start,part-end,part-start,part-end,part-end,done,diag-count:0；bodies 与 A 相同；nested-events MimeParseError:unexpected-eof@214；nested-bodies threw；bad-header part-start,diag:bad-header@50,diag-count:1；abort-feed timeout
cd ..
```

---

## 第 194 题　Bug 修复　·　困难　·　无界面
<!-- solo-report:task=194 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/mime-folded-header-core　A 分支：https://github.com/gy-vs/mime-folded-header-core/tree/A　B 分支：https://github.com/gy-vs/mime-folded-header-core/tree/B

存为 `verify_194.mjs`（放在仓库根目录）

```javascript
import * as api from './dist/index.js';

const folded =
  'Content-Disposition: attachment;\r\n \tfilename="a b.txt";\r\n\tsize=1\r\n' +
  'Received: one\r\nX-Ext: a\r\nReceived: two\r\nX-Ext: b\r\n';

function namesOf(block) {
  if (block.fields) return block.fields.map((f) => f.name).join(',');
  return block.map((f) => f.name).join(',');
}

function getAll(block, name) {
  if (typeof block.getAll === 'function') return block.getAll(name).map((x) => (typeof x === 'string' ? x : x.value));
  return block.filter((f) => f.name === name).map((f) => f.value);
}

function unfoldedCd(block) {
  if (typeof block.get === 'function') {
    const f = block.get('content-disposition');
    return f && (f.value || f);
  }
  const f = block.find((h) => h.name === 'content-disposition');
  return f && f.value;
}

const block = api.parseHeaderBlock ? api.parseHeaderBlock(folded) : api.parseHeaders(folded);
console.log('order', namesOf(block));
console.log('received', getAll(block, 'received').join('|'));
const cdValue = typeof unfoldedCd(block) === 'string' ? unfoldedCd(block) : String(unfoldedCd(block));
console.log('cd-value', JSON.stringify(cdValue));

if (typeof api.parseContentDisposition === 'function') {
  const p = api.parseContentDisposition(cdValue);
  console.log('cd-filename', p.get('filename'));
  console.log('cd-size', p.get('size'));
  const dup = api.parseContentDisposition('attachment; x=1; x=2');
  console.log('dup-param', dup.getAll('x').join('|'));
} else {
  const p = api.parseParameters(cdValue);
  console.log('cd-filename', p.parameters.filename);
  console.log('cd-size', p.parameters.size);
  const dup = api.parseParameters('attachment; x=1; x=2');
  console.log('dup-param', dup.parameters.x);
}

const cafe = 'X: café\nY: 1\n';
const cafeBlock = api.parseHeaderBlock ? api.parseHeaderBlock(cafe) : api.parseHeaders(cafe);
let raw;
if (typeof cafeBlock.rawBytes === 'function') raw = cafeBlock.rawBytes();
else if (cafeBlock.rawBlock instanceof Uint8Array) raw = cafeBlock.rawBlock;
else if (typeof cafeBlock.rawBlock === 'string') raw = Buffer.from(cafeBlock.rawBlock);
else if (typeof cafeBlock.raw === 'string') raw = Buffer.from(cafeBlock.raw);
else raw = Buffer.from(String(cafeBlock));
console.log('cafe-bytes', Array.from(raw).map((b) => b.toString(16)).join(' '));

const malformed = 'Good: 1\r\nGARBAGE LINE\r\n \tcontinued\r\nX: ok\r\n';
const m = api.parseHeaderBlock ? api.parseHeaderBlock(malformed) : api.parseHeaders(malformed);
if (m.fields) {
  const good = m.fields.find((f) => String(f.name).toLowerCase() === 'good' || String(f.lowerName) === 'good');
  console.log('malformed-fields', m.fields.map((f) => f.name).join(','));
  console.log('good-raw', JSON.stringify(good && String(good.raw)));
  const issues = (m.issues || m.errors || []).map((i) => i.code).join(',');
  console.log('issues', issues);
} else {
  console.log('malformed-fields', m.map((f) => f.name).join(','));
  console.log('good-raw', 'n/a');
  console.log('issues', 'n/a');
}

const mixed = 'A: 1\r\nB: folded\r\n\there\r\n\r\nfirst body\r\nline2';
if (typeof api.MimeStream === 'function') {
  const s = new api.MimeStream();
  const events = s.feed(mixed);
  if (Array.isArray(events) && events[0] && events[0].type === 'headers') {
    const h = events[0].headers;
    const body = events.filter((e) => e.type === 'data').map((e) => e.chunk).join('');
    console.log('reconstruct', h.raw + h.separator + body === mixed);
    console.log('separator', JSON.stringify(h.separator));
    console.log('body-first', JSON.stringify(body.slice(0, 10)));
  } else if (Array.isArray(events) && events[0] && events[0].headers && events[0].body !== undefined) {
    console.log('reconstruct', 'no-separator');
    console.log('separator', 'absent');
    console.log('body-first', JSON.stringify(String(events[0].body).slice(0, 10)));
  } else {
    console.log('reconstruct', 'empty-feed');
    console.log('separator', 'n/a');
    console.log('body-first', 'n/a');
  }
}
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/mime-folded-header-core.git mime-folded-header-core-A
cd mime-folded-header-core-A
npm ci
npm run build
npm test                                                          # 预期：38 passed
node verify_194.mjs                                                     # 预期：order Content-Disposition,Received,X-Ext,Received,X-Ext；received one|two；cd-value 折叠 tab 已变成空格、filename 不含 tab；cd-filename a b.txt；cd-size 1；dup-param 1|2；cafe-bytes 含 c3 a9；malformed-fields Good,X；good-raw 仅 Good: 1；issues missing-colon,orphan-continuation；reconstruct no-separator；separator absent；body-first first body
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/mime-folded-header-core.git mime-folded-header-core-B
cd mime-folded-header-core-B
npm ci
npm run build
npm test                                                          # 预期：31 passed
node verify_194.mjs                                                     # 预期：order 小写 content-disposition,received,x-ext,received,x-ext；received 与 cd-filename/size 与 A 相同；dup-param 2；cafe-bytes 含 e9 而非 c3 a9；malformed-fields good,x；good-raw 把续行并进 Good: 1\r\n \tcontinued\r\n；issues MALFORMED_LINE；reconstruct true；separator \r\n；body-first first body
cd ..
```

---

## 第 195 题　Feature 迭代　·　困难　·　无界面
<!-- solo-report:task=195 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/mime-rfc2231-params-core　A 分支：https://github.com/gy-vs/mime-rfc2231-params-core/tree/A　B 分支：https://github.com/gy-vs/mime-rfc2231-params-core/tree/B

存为 `verify_195.mjs`（放在仓库根目录）

```javascript
import * as api from './dist/index.js';

const parse = api.parseMimeParameters || api.parseMimeParams;
const serializeAll = api.serializeMimeParameters;
const serializeOne = api.parseMimeParams ? api.serializeMimeParam : null;

function show(r) {
  if (Array.isArray(r.params)) {
    return r.params.map((p) => p.name + '=' + p.value).join('|');
  }
  return Object.entries(r.params || {})
    .map(([k, v]) => k + '=' + v)
    .join('|');
}

function diags(r) {
  return (r.diagnostics || []).map((d) => d.code).join(',');
}

const colon = parse('attachment; filename="x:y.txt"; size=1');
console.log('colon-params', show(colon) || '(empty)');
console.log('colon-value', colon.value);

const ordered = parse("attachment; filename*1*=%20txt; filename*0*=utf-8''hello%20world");
console.log('ordered', show(ordered));
console.log('ordered-diags', diags(ordered));

const mixed = parse('attachment; filename*0*=utf-8\'\'hello; filename*1=" world"; filename=fb.txt');
console.log('mixed', show(mixed));
console.log('mixed-diags', diags(mixed));

const bad = parse("x/y; filename*=UTF-8''100%GG.txt; filename=ok.txt");
console.log('bad-fallback', show(bad));
console.log('bad-diags', diags(bad));

if (serializeAll) {
  const wire = serializeAll('attachment', { filename: '100% cafe' });
  console.log('ser', wire);
  const back = parse(wire);
  console.log('roundtrip', show(back));
} else {
  const wire = serializeOne('filename', '100% cafe');
  console.log('ser', wire);
  const back = parse('attachment; ' + wire);
  console.log('roundtrip', show(back));
}

const utf = parse("x/y; filename*1*=%82%ACb.txt; filename*0*=UTF-8''a%E2");
console.log('utf-span', show(utf));
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/mime-rfc2231-params-core.git mime-rfc2231-params-core-A
cd mime-rfc2231-params-core-A
npm ci
npm run build
npm test                                                          # 预期：20 passed
node verify_195.mjs                                                     # 预期：colon-params size=1（filename 丢失）；colon-value y.txt"；ordered filename=hello world txt；mixed filename=hello world 且无诊断；bad-fallback filename=ok.txt；bad-diags INVALID_PERCENT_SEQUENCE；ser attachment; filename*=utf-8''100%25%20cafe；roundtrip filename=100% cafe；utf-span filename=a€b.txt
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/mime-rfc2231-params-core.git mime-rfc2231-params-core-B
cd mime-rfc2231-params-core-B
npm ci
npm run build
npm test                                                          # 预期：33 passed
node verify_195.mjs                                                     # 预期：colon-params filename=x:y.txt|size=1；colon-value attachment；ordered 与 utf-span 与 roundtrip 与 A 相同；mixed filename=fb.txt；mixed-diags continuation-mixed；bad-diags bad-percent-escape；ser filename="100% cafe"
cd ..
```

---

## 第 198 题　Bug 修复　·　困难　·　无界面
<!-- solo-report:task=198 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/tar-pax-path-core　A 分支：https://github.com/gy-vs/tar-pax-path-core/tree/A　B 分支：https://github.com/gy-vs/tar-pax-path-core/tree/B

存为 `verify_198.mjs`（放在仓库根目录）

```javascript
import * as api from './dist/index.js';

function writeOctal(block, offset, width, value) {
  const digits = value.toString(8).padStart(width - 1, '0');
  for (let i = 0; i < width - 1; i++) block[offset + i] = digits.charCodeAt(i);
  block[offset + width - 1] = 0;
}

function checksum(block) {
  let s = 0;
  for (let i = 0; i < 512; i++) s += block[i];
  return s;
}

function header({ name, size, typeflag = '0', linkname = '', prefix = '' }) {
  const b = new Uint8Array(512);
  Buffer.from(name).copy(b, 0);
  writeOctal(b, 100, 8, 0o644);
  writeOctal(b, 108, 8, 0);
  writeOctal(b, 116, 8, 0);
  writeOctal(b, 124, 12, size);
  writeOctal(b, 136, 12, 0);
  b.fill(0x20, 148, 156);
  b[156] = typeflag.charCodeAt(0);
  if (linkname) Buffer.from(linkname).copy(b, 157);
  Buffer.from('ustar\0').copy(b, 257);
  Buffer.from('00').copy(b, 263);
  if (prefix) Buffer.from(prefix).copy(b, 345);
  const sum = checksum(b);
  const oct = sum.toString(8).padStart(6, '0');
  Buffer.from(oct).copy(b, 148);
  b[154] = 0;
  b[155] = 0x20;
  return b;
}

function pad(payload) {
  const n = Math.ceil(payload.length / 512) * 512;
  const out = new Uint8Array(n);
  out.set(payload);
  return out;
}

function paxRecords(map) {
  const chunks = [];
  for (const [k, v] of Object.entries(map)) {
    const make = (n) => Buffer.from(n + ' ' + k + '=' + v + '\n');
    let rec = make(1);
    rec = make(rec.length);
    rec = make(rec.length);
    chunks.push(rec);
  }
  return Buffer.concat(chunks);
}

function fileEntry(name, body) {
  const data = Buffer.from(body);
  return Buffer.concat([header({ name, size: data.length }), pad(data)]);
}

function special(typeflag, payload, name = './PaxHeader') {
  const buf = Buffer.from(payload);
  return Buffer.concat([header({ name, size: buf.length, typeflag }), pad(buf)]);
}

const eoa = Buffer.alloc(1024);

const merged = api.mergeMetadata(
  { path: 'ustar.txt', size: 1, type: 'file' },
  { path: 'global.txt' },
  { path: 'local.txt' },
  'gnu.txt',
);
console.log('merge-path', merged.path);

const emptyLocal = api.mergeMetadata(
  { path: 'ustar.txt', size: 1, type: 'file' },
  { path: 'global.txt' },
  { path: '' },
  'gnu.txt',
);
console.log('empty-local', JSON.stringify(emptyLocal.path));

const archive = Buffer.concat([
  special('g', paxRecords({ path: 'from-global.txt' }), './PaxGlobal'),
  special('L', 'gnu-long.txt\0', '././@LongLink'),
  special('x', paxRecords({ path: 'from-local.txt' })),
  fileEntry('ustar.txt', 'hi\n'),
  eoa,
]);

function list(parsed) {
  const entries = parsed.entries || parsed;
  return (Array.isArray(entries) ? entries : []).map((e) => {
    const meta = e.meta || e;
    const src = meta.sources && meta.sources.path;
    const layer = (src && (src.layer || src.origin)) || '?';
    const deleted = meta.pathDeleted ? ' deleted' : '';
    return meta.path + '@' + layer + deleted;
  });
}

if (typeof api.parseTar === 'function') {
  const r = api.parseTar(new Uint8Array(archive));
  console.log('paths', list(r).join(','));
  const first = r.entries[0];
  if (first && first.pathProvenance) {
    console.log(
      'provenance',
      first.pathProvenance.map((p) => p.layer + ':' + JSON.stringify(p.value) + (p.maskedBy ? '>' + p.maskedBy : '')).join('|'),
    );
  } else {
    console.log('provenance', 'absent');
  }
  console.log('warnings', (r.warnings || []).map((w) => w.code).join(','));
} else {
  const r = api.parseArchive(new Uint8Array(archive));
  console.log('paths', list(r).join(','));
  const first = r.entries[0] && (r.entries[0].meta || r.entries[0]);
  console.log('provenance', first && first.sources && first.sources.path ? JSON.stringify(first.sources.path) : 'absent');
  console.log('warnings', (r.diagnostics || []).map((d) => d.code).join(','));
}

const emptyPax = Buffer.concat([
  special('x', paxRecords({ path: '' })),
  fileEntry('ustar.txt', 'hi\n'),
  eoa,
]);
if (typeof api.parseTar === 'function') {
  const r = api.parseTar(new Uint8Array(emptyPax));
  console.log('empty-pax-path', JSON.stringify((r.entries[0] && r.entries[0].path) || ''));
} else {
  const r = api.parseArchive(new Uint8Array(emptyPax));
  const meta = r.entries[0] && (r.entries[0].meta || r.entries[0]);
  console.log('empty-pax-path', JSON.stringify((meta && meta.path) || '') + (meta && meta.pathDeleted ? ' deleted' : ''));
}

const leak = Buffer.concat([
  special('L', 'should-not-leak.txt\0', '././@LongLink'),
  Buffer.concat([
    (() => {
      const bad = header({ name: 'bad.txt', size: 0 });
      bad[148] ^= 1;
      return bad;
    })(),
  ]),
  fileEntry('ok.txt', 'z'),
  eoa,
]);

if (typeof api.parseTar === 'function') {
  const r = api.parseTar(new Uint8Array(leak));
  console.log('leak-paths', list(r).join(','));
  console.log('leak-warn', (r.warnings || []).map((w) => w.code).join(','));
} else {
  const r = api.parseArchive(new Uint8Array(leak));
  console.log('leak-paths', list(r).join(','));
  console.log('leak-warn', (r.diagnostics || []).map((d) => d.code).join(','));
}
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/tar-pax-path-core.git tar-pax-path-core-A
cd tar-pax-path-core-A
npm ci
npm run build
npm test                                                          # 预期：29 passed
node verify_198.mjs                                                     # 预期：merge-path local.txt；empty-local 空串；paths from-local.txt@localPax；provenance 含四层链与 maskedBy；empty-pax-path "ustar.txt"；leak-paths ok.txt@ustar；leak-warn bad-header-checksum,orphan-one-shot
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/tar-pax-path-core.git tar-pax-path-core-B
cd tar-pax-path-core-B
npm ci
npm run build
npm test                                                          # 预期：38 passed
node verify_198.mjs                                                     # 预期：merge-path 与 empty-local 与 paths 与 leak-paths 与 A 相同；provenance 只有获胜者 origin/keyword/blockIndex/occurrence；empty-pax-path "" deleted；leak-warn bad-checksum
cd ..
```

---

## 第 200 题　Bug 修复　·　困难　·　无界面
<!-- solo-report:task=200 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/tar-checksum-compat-core　A 分支：https://github.com/gy-vs/tar-checksum-compat-core/tree/A　B 分支：https://github.com/gy-vs/tar-checksum-compat-core/tree/B

存为 `verify_200.mjs`（放在仓库根目录）

```javascript
import * as api from './dist/index.js';

function writeOctal(block, offset, width, value) {
  const digits = value.toString(8).padStart(width - 1, '0');
  for (let i = 0; i < width - 1; i++) block[offset + i] = digits.charCodeAt(i);
  block[offset + width - 1] = 0;
}

function sums(block) {
  let unsigned = 0;
  let signed = 0;
  for (let i = 0; i < 512; i++) {
    const v = i >= 148 && i < 156 ? 0x20 : block[i];
    unsigned += v;
    signed += v > 0x7f ? v - 0x100 : v;
  }
  return { unsigned, signed };
}

function putChecksum(block, value) {
  const oct = value.toString(8).padStart(6, '0');
  for (let i = 0; i < 6; i++) block[148 + i] = oct.charCodeAt(i);
  block[154] = 0;
  block[155] = 0x20;
}

function makeHeader(nameBytes, size = 0) {
  const b = new Uint8Array(512);
  b.set(nameBytes.subarray(0, Math.min(100, nameBytes.length)), 0);
  writeOctal(b, 100, 8, 0o644);
  writeOctal(b, 108, 8, 0);
  writeOctal(b, 116, 8, 0);
  writeOctal(b, 124, 12, size);
  writeOctal(b, 136, 12, 0);
  b.fill(0x20, 148, 156);
  b[156] = 0x30;
  Buffer.from('ustar\0').copy(b, 257);
  Buffer.from('00').copy(b, 263);
  const { unsigned } = sums(b);
  putChecksum(b, unsigned);
  return b;
}

function showVerify(label, block, extra) {
  const r = extra === undefined ? api.verifyChecksum(block) : api.verifyChecksum(block, extra);
  const ok = r.valid !== undefined ? r.valid : r.ok;
  const algo = r.algorithm;
  const kind = (r.field && (r.field.kind || r.field.style)) || '?';
  console.log(label, ok, algo, kind);
}

const plain = makeHeader(Buffer.from('hello.txt'));
showVerify('plain', plain);

const hi = new Uint8Array(16);
hi.set(Buffer.from('cafe'));
hi[4] = 0xff;
hi[5] = 0x80;
const high = makeHeader(hi);
const s = sums(high);
console.log('high-sums', s.unsigned, s.signed, s.unsigned - s.signed);
putChecksum(high, s.signed);
showVerify('high-signed-compat', high);
showVerify('high-signed-strict', high, { signedChecksumCompat: false });

const flipped = Uint8Array.from(plain);
flipped[0] ^= 1;
showVerify('flipped', flipped);

try {
  api.verifyChecksum(plain.subarray(0, 511));
  console.log('trunc', 'accepted');
} catch (e) {
  console.log('trunc', (e.code || e.name) + ': ' + String(e.message).split('\n')[0]);
}

const archive = Buffer.concat([plain, Buffer.alloc(1024)]);
try {
  const r = api.readArchive(archive);
  const entries = Array.isArray(r) ? r : r.entries;
  const first = entries[0];
  const path = first.path || (first.header && first.header.path);
  const algo = (first.checksum && first.checksum.algorithm) || first.checksumAlgorithm;
  console.log('read', path, algo, entries.length);
  const idx = new api.ArchiveIndex();
  try {
    idx.add(first.header || first);
    console.log('index-add', 'ok');
  } catch (e) {
    console.log('index-add', String(e.message).split('\n')[0]);
  }
} catch (e) {
  console.log('read', (e.code || e.name) + ': ' + String(e.message).split('\n')[0]);
}

const other = { path: 'x', size: 0, type: 'other' };
const idx2 = new api.ArchiveIndex();
try {
  idx2.add(other);
  console.log('index-other', idx2.find('x') ? 'found' : 'missing');
} catch (e) {
  console.log('index-other', String(e.message).split('\n')[0]);
}
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/tar-checksum-compat-core.git tar-checksum-compat-core-A
cd tar-checksum-compat-core-A
npm ci
npm run build
npm test                                                          # 预期：38 passed
node verify_200.mjs                                                     # 预期：plain true unsigned posix；high-sums 3819 3307 512；high-signed-compat true signed posix；high-signed-strict false null posix；flipped false；trunc TRUNCATED_HEADER: header block is 511 bytes, need 512；read hello.txt unsigned 1；index-add ok；index-other found
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/tar-checksum-compat-core.git tar-checksum-compat-core-B
cd tar-checksum-compat-core-B
npm ci
npm run build
npm test                                                          # 预期：41 passed
node verify_200.mjs                                                     # 预期：plain true unsigned canonical；high-sums 与 signed 接受/拒绝 与 A 相同，字段 kind 为 canonical；trunc truncated-header: checksum verification requires exactly 512 header bytes, got 511；read 与 index-add/index-other 与 A 相同
cd ..
```

---

## 第 201 题　Feature 迭代　·　困难　·　无界面
<!-- solo-report:task=201 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/tar-unknown-size-writer-core　A 分支：https://github.com/gy-vs/tar-unknown-size-writer-core/tree/A　B 分支：https://github.com/gy-vs/tar-unknown-size-writer-core/tree/B

存为 `verify_201.mjs`（放在仓库根目录）

```javascript
import * as api from './dist/index.js';

async function* chunks(data, n) {
  for (let i = 0; i < data.length; i += n) yield Buffer.from(data.subarray(i, i + n));
}

async function* failAfter(n) {
  yield Buffer.from('abc');
  if (n) throw new Error('source-boom');
}

function collectSink() {
  const parts = [];
  const sink = (c) => {
    parts.push(Buffer.from(c));
  };
  sink.parts = parts;
  sink.buf = () => Buffer.concat(parts);
  return sink;
}

async function writeStandard(path, source, extra) {
  const sink = collectSink();
  if (typeof api.TarUnknownSizeWriter === 'function') {
    const w = new api.TarUnknownSizeWriter({ sink });
    try {
      const r = await w.addUnknownSize(
        { path },
        source,
        extra || { strategy: 'standard', memoryThreshold: 8, diskBudget: 1024 * 1024 },
      );
      const end = await w.close();
      return { ok: true, size: r.size, bytes: end.bytesWritten, buf: sink.buf(), spilled: r.spilled, err: null };
    } catch (e) {
      return { ok: false, size: 0, bytes: w.bytesWritten, buf: sink.buf(), spilled: false, err: e.name + ':' + e.bytesWritten };
    }
  }
  const opts = extra && extra.strategy === 'chunked'
    ? { strategy: 'chunked', sink }
    : {
        strategy: 'standard',
        sink,
        memoryBudget: (extra && extra.memoryThreshold) || 8,
        tempBudget: extra && extra.diskBudget !== undefined ? extra.diskBudget : 1024 * 1024,
        compatibility: extra && extra.compatibility ? extra.compatibility : 'pax',
      };
  const w = new api.TarWriter(opts);
  const r = await w.addFile({ path, source });
  if (!r.ok) return { ok: false, size: 0, bytes: r.boundary, buf: sink.buf(), spilled: false, err: r.error.name + ':' + r.boundary };
  const end = await w.end();
  return { ok: true, size: r.size, bytes: end.ok ? end.size : w.bytesWritten, buf: sink.buf(), spilled: false, err: null };
}

const empty = await writeStandard('empty.txt', chunks(Buffer.alloc(0), 1));
console.log('empty', empty.ok, empty.size, empty.bytes, empty.buf.subarray(empty.buf.length - 1024).every((b) => b === 0));

const body = Buffer.from('hello-unknown-size-payload');
const std = await writeStandard('hello.txt', chunks(body, 5));
console.log('std', std.ok, std.size, JSON.stringify(std.buf.subarray(0, 10).toString()));
console.log('ustar-ver', std.buf[263], std.buf[264]);

const longName = 'dir/' + 'n'.repeat(120) + '.txt';
const long = await writeStandard(longName, chunks(Buffer.from('x'), 1));
console.log('long-ok', long.ok, long.size);
console.log('long-typeflag', String.fromCharCode(long.buf[156]), JSON.stringify(long.buf.subarray(257, 265).toString()));
console.log('long-name100', JSON.stringify(long.buf.subarray(0, 100).toString().replace(/\0+$/g, '')));

const boom = await writeStandard('boom.txt', failAfter(1));
console.log('source-fail', boom.ok, boom.err, boom.bytes, boom.buf.length);
const tail = boom.buf.subarray(Math.max(0, boom.buf.length - 1024));
console.log('source-fail-eoa', boom.buf.length >= 1024 && tail.every((b) => b === 0));

const over = await writeStandard(
  'over.bin',
  chunks(Buffer.alloc(64), 8),
  { strategy: 'standard', memoryThreshold: 4, diskBudget: 8, memoryBudget: 4, tempBudget: 8, compatibility: 'pax' },
);
console.log('budget', over.ok, over.err, over.bytes);

const chk = await writeStandard('c.bin', chunks(Buffer.from('zz'), 1), { strategy: 'chunked' });
console.log('chunked-ok', chk.ok, chk.size);
console.log('chunked-magic', JSON.stringify(chk.buf.subarray(0, 8).toString()));
console.log('chunked-typeflag', String.fromCharCode(chk.buf[156] || 0));
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/tar-unknown-size-writer-core.git tar-unknown-size-writer-core-A
cd tar-unknown-size-writer-core-A
npm ci
npm run build
npm test                                                          # 预期：34 passed
node verify_201.mjs                                                     # 预期：empty true 0 1536 true；std true 26 hello.txt；ustar-ver 48 48（ASCII 00）；long-typeflag x 且 magic ustar\0 00；source-fail SourceFailedError:0 且无结束零块；budget DiskBudgetExceededError:0；chunked-magic TARCHNK1
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/tar-unknown-size-writer-core.git tar-unknown-size-writer-core-B
cd tar-unknown-size-writer-core-B
npm ci
npm run build
npm test                                                          # 预期：21 passed
node verify_201.mjs                                                     # 预期：empty 与 std 与 A 相同；ustar-ver 0 0（两个 NUL）；long-typeflag x 且 magic ustar 后两个 NUL；source-fail SourceError:0 且无结束零块；budget TempBudgetExceededError:0；chunked-magic 以 @ux/ 开头、typeflag C
cd ..
```

---

## 第 202 题　Bug 修复　·　困难　·　无界面
<!-- solo-report:task=202 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/tar-longname-scope-core　A 分支：https://github.com/gy-vs/tar-longname-scope-core/tree/A　B 分支：https://github.com/gy-vs/tar-longname-scope-core/tree/B

存为 `verify_202.mjs`（放在仓库根目录）

```javascript
import { existsSync, readFileSync } from 'node:fs';

let mod;
if (existsSync('./dist/index.js')) mod = await import('./dist/index.js');
else if (existsSync('./dist/src/index.js')) mod = await import('./dist/src/index.js');
else mod = await import('./src/index.js');
const pkg = JSON.parse(readFileSync('package.json', 'utf8'));
console.log('test-script', pkg.scripts.test);
console.log('has-vitest', Boolean(pkg.devDependencies && pkg.devDependencies.vitest));
console.log(
  'exports',
  Object.keys(mod)
    .filter((k) => typeof mod[k] !== 'undefined')
    .sort()
    .join(','),
);

const BLOCK = 512;
const enc = new TextEncoder();

function octal(value, length) {
  const out = new Uint8Array(length);
  const padded = value.toString(8).padStart(length - 1, '0');
  out.set(enc.encode(padded).subarray(0, length - 1), 0);
  out[length - 1] = 0x20;
  return out;
}

function putString(block, text, offset, length) {
  block.set(enc.encode(text).subarray(0, length), offset);
}

function makeHeader(spec) {
  const block = new Uint8Array(BLOCK);
  putString(block, spec.name, 0, 100);
  block.set(octal(0o644, 7), 100);
  block.set(octal(0, 7), 108);
  block.set(octal(0, 7), 116);
  block.set(octal(spec.size, 12), 124);
  block.set(octal(0, 12), 136);
  block.fill(0x20, 148, 156);
  block[156] = spec.typeflag;
  putString(block, spec.linkName ?? '', 157, 100);
  putString(block, 'ustar', 257, 5);
  block[263] = 0x30;
  block[264] = 0x30;
  let sum = 0;
  for (let i = 0; i < BLOCK; i++) sum += block[i];
  putString(block, sum.toString(8).padStart(6, '0'), 148, 6);
  block[154] = 0;
  block[155] = 0x20;
  return block;
}

function padded(data) {
  const blocks = Math.max(1, Math.ceil(data.length / BLOCK));
  const out = new Uint8Array(blocks * BLOCK);
  out.set(data);
  return out;
}

function concat(parts) {
  const out = new Uint8Array(parts.reduce((s, p) => s + p.length, 0));
  let o = 0;
  for (const p of parts) {
    out.set(p, o);
    o += p.length;
  }
  return out;
}

function longRecord(kind, payload) {
  const body = enc.encode(payload + '\0');
  return [
    makeHeader({ name: '././@LongLink', size: body.length, typeflag: kind.charCodeAt(0) }),
    padded(body),
  ];
}

function fileRecord(name, content) {
  const body = enc.encode(content);
  return [makeHeader({ name, size: body.length, typeflag: 0x30 }), padded(body)];
}

async function collect(source, filter) {
  const paths = [];
  const kinds = [];
  let frozen = null;
  const iter = mod.TarReader
    ? new mod.TarReader(source, { filter }).entries()
    : mod.parseTar(source, { filter });
  for await (const e of iter) {
    paths.push(JSON.stringify(e.path));
    kinds.push(typeof e.body);
    if (frozen === null) frozen = Object.isFrozen(e);
  }
  return { paths: paths.join('|'), kinds: kinds.join('|'), frozen };
}

function keepFilter(h) {
  const p = h.path;
  return p !== 'skip-me.txt' && p !== 'very-long-name-should-not-leak';
}

const skipArc = concat([
  ...longRecord('L', 'very-long-name-should-not-leak'),
  ...fileRecord('skip-me.txt', 'x'),
  ...fileRecord('keep.txt', 'y'),
  new Uint8Array(1024),
]);
const skip = await collect(skipArc, keepFilter);
console.log('filter-skip', skip.paths, skip.kinds, skip.frozen);

const bad = new Uint8Array(BLOCK);
bad.fill(0x41);
const corruptArc = concat([
  ...longRecord('L', 'orphan-long-name'),
  bad,
  ...fileRecord('after-bad.txt', 'z'),
  new Uint8Array(1024),
]);
try {
  const r = await collect(corruptArc);
  console.log('after-corrupt', r.paths);
} catch (e) {
  console.log('after-corrupt-err', e.name);
}

const emptyArc = concat([
  ...longRecord('L', ''),
  ...fileRecord('short.txt', 'q'),
  new Uint8Array(1024),
]);
const empty = await collect(emptyArc);
console.log('empty-longname', empty.paths);
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/tar-longname-scope-core.git tar-longname-scope-core-A
cd tar-longname-scope-core-A
npm install
npm run build
npm test                                                                 # 预期：29 passed
node verify_202.mjs                                                      # 预期：test-script vitest run；has-vitest true；exports ArchiveIndex,TarReader,mergeMetadata；filter-skip "keep.txt" object true；after-corrupt "after-bad.txt"；empty-longname ""
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/tar-longname-scope-core.git tar-longname-scope-core-B
cd tar-longname-scope-core-B
npm install
npm run build
npm test                                                                 # 预期：Node 20 上 20 passed；Node 24 会把 dist/test/ 当模块报 MODULE_NOT_FOUND
node verify_202.mjs                                                      # 预期：test-script tsc -p tsconfig.test.json && node --test dist/test/；has-vitest false；exports ArchiveIndex,TarParseError,mergeMetadata,parseTar；filter-skip "keep.txt" function false；after-corrupt "after-bad.txt"；empty-longname ""
cd ..
```

---

## 第 208 题　Bug 修复　·　困难　·　无界面
<!-- solo-report:task=208 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/unicode-normalized-offset-core　A 分支：https://github.com/gy-vs/unicode-normalized-offset-core/tree/A　B 分支：https://github.com/gy-vs/unicode-normalized-offset-core/tree/B

存为 `verify_208.mjs`（放在仓库根目录）

```javascript
import { findMatches } from './dist/index.js';

function show(label, hits, text) {
  const parts = hits.map((h) => {
    const slice = text ? JSON.stringify(text.slice(h.start, h.end)) : '';
    const g =
      h.graphemeStart === undefined ? '-' : h.graphemeStart + ':' + h.graphemeEnd;
    return h.start + '-' + h.end + '/' + g + '/' + slice;
  });
  console.log(label, hits.length, parts.join(';') || '(none)');
}

const math = '𝔽 is bold';
show('math-f', findMatches(math, 'f'), math);

const nfd = 'Cafe\u0301';
show('nfd-cafe', findMatches(nfd, 'cafe'), nfd);

const sharp = 'Straße';
show('sharp-ss', findMatches(sharp, 'ss'), sharp);
show('sharp-strasse', findMatches(sharp, 'strasse'), sharp);

const full = 'ＨＥＬＬＯ';
show('fullwidth', findMatches(full, 'hello'), full);

const tr = findMatches('İstanbul', 'istanbul', { locale: 'tr' });
show('turkish', tr, 'İstanbul');

const circled = 'Ⓐbc';
show('circled', findMatches(circled, 'a'), circled);
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/unicode-normalized-offset-core.git unicode-normalized-offset-core-A
cd unicode-normalized-offset-core-A
npm ci
npm run build
npm test                                                                 # 预期：28 passed
node verify_208.mjs                                                      # 预期：math-f 1 0-2/-/"𝔽"；nfd-cafe 1 0-5/-/"Café"；sharp-ss 1 4-5/-/"ß"；sharp-strasse 1 0-6/-/"Straße"；fullwidth 1 0-5/-/"ＨＥＬＬＯ"；turkish 1 0-8/-/"İstanbul"；circled 1 0-1/-/"Ⓐ"
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/unicode-normalized-offset-core.git unicode-normalized-offset-core-B
cd unicode-normalized-offset-core-B
npm ci
npm run build
npm test                                                                 # 预期：44 passed
node verify_208.mjs                                                      # 预期：math-f 0 (none)；nfd-cafe 1 0-5/0:4/"Café"；sharp-ss 1 4-5/4:5/"ß"；sharp-strasse 1 0-6/0:6/"Straße"；fullwidth 1 0-5/0:5/"ＨＥＬＬＯ"；turkish 1 0-8/0:8/"İstanbul"；circled 1 0-1/0:1/"Ⓐ"
cd ..
```

---

## 第 209 题　Feature 迭代　·　困难　·　无界面
<!-- solo-report:task=209 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/unicode-grapheme-fuzzy-core　A 分支：https://github.com/gy-vs/unicode-grapheme-fuzzy-core/tree/A　B 分支：https://github.com/gy-vs/unicode-grapheme-fuzzy-core/tree/B

存为 `verify_209.mjs`（放在仓库根目录）

```javascript
import * as m from './dist/index.js';

const fuzzy = m.fuzzyFind || m.fuzzySearch;

const empty = fuzzy('abc', '');
console.log('empty', empty.status, empty.matches.length);

const trans = fuzzy('wolrd cafe', 'world', { maxCost: 2 });
const hit = trans.matches[0];
const step = hit && hit.script && hit.script[0];
console.log(
  'transpose',
  trans.status,
  hit && hit.cost,
  hit && hit.start + '-' + hit.end,
  step && Object.keys(step).sort().join(','),
  step && (Array.isArray(step.text) ? 'ids' : step.target ? 'ref' : typeof step.text),
);

const zwj = fuzzy('see 👨‍👩‍👧 here', '👨‍👩‍👧', { maxCost: 0 });
console.log(
  'zwj',
  zwj.status,
  zwj.matches.length,
  zwj.matches[0] && zwj.matches[0].cost,
  zwj.matches[0] && zwj.matches[0].start + '-' + zwj.matches[0].end,
);

const cancelled = fuzzy('hello world', 'hello', {
  maxCost: 2,
  shouldCancel: () => true,
  shouldContinue: () => false,
});
console.log('cancel', cancelled.status);

const budget = fuzzy('hello world this is a long text for the budget path', 'zzzzzzzzzz', {
  maxCost: 10,
  maxWork: 1,
  maxCells: 1,
});
console.log('budget', budget.status);
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/unicode-grapheme-fuzzy-core.git unicode-grapheme-fuzzy-core-A
cd unicode-grapheme-fuzzy-core-A
npm ci
npm run build
npm test                                                                 # 预期：36 passed
node verify_209.mjs                                                      # 预期：empty ok 4；transpose ok 1 0-5 cost,op,query,text ids；zwj ok 1 0 4-12；cancel cancelled；budget budget-exceeded
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/unicode-grapheme-fuzzy-core.git unicode-grapheme-fuzzy-core-B
cd unicode-grapheme-fuzzy-core-B
npm ci
npm run build
npm test                                                                 # 预期：38 passed
node verify_209.mjs                                                      # 预期：empty empty-query 0；transpose matched 1 0-5 cost,op,query,target ref；zwj matched 1 0 4-12；cancel cancelled；budget matched
cd ..
```

---

## 第 211 题　Feature 迭代　·　困难　·　无界面
<!-- solo-report:task=211 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/unicode-stream-matcher-core　A 分支：https://github.com/gy-vs/unicode-stream-matcher-core/tree/A　B 分支：https://github.com/gy-vs/unicode-stream-matcher-core/tree/B

存为 `verify_211.mjs`（放在仓库根目录）

```javascript
import * as m from './dist/index.js';

function fmt(hits) {
  return hits
    .map((h) => {
      if ('byteStart' in h) {
        return [h.patternIndex, h.pattern, h.byteStart, h.byteEnd, h.u16Start, h.u16End].join(':');
      }
      return [h.pattern, h.start.byte, h.end.byte, h.start.utf16, h.end.utf16].join(':');
    })
    .join('|') || '(none)';
}

const enc = new TextEncoder();
const family = '👨‍👩‍👧';
const famHits = m.searchBytes(enc.encode(family), ['👨', '👩', '👧']);
console.log('family', famHits.length, fmt(famHits));

const nfd = 'Cafe\u0301';
const nfdBytes = enc.encode(nfd);
const nfdHits = m.searchBytes(nfdBytes, ['cafe']);
console.log('nfd-cafe', nfdHits.length, fmt(nfdHits));

const chunks = [];
for (const b of nfdBytes) chunks.push(Uint8Array.of(b));
const streamHits = [];
for await (const h of m.searchStream(chunks, ['cafe'])) streamHits.push(h);
console.log('nfd-stream', streamHits.length, fmt(streamHits));

const overlap = m.searchBytes(enc.encode('abcabc'), ['ab', 'bc', 'abc']);
console.log('overlap', overlap.length, fmt(overlap));

try {
  m.searchBytes(Uint8Array.of(0xff), ['a'], { mode: 'strict', onInvalid: 'strict' });
  console.log('strict-ff', 'ok');
} catch (e) {
  console.log('strict-ff', e.name);
}
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/unicode-stream-matcher-core.git unicode-stream-matcher-core-A
cd unicode-stream-matcher-core-A
npm ci
npm run build
npm test                                                                 # 预期：51 passed
node verify_211.mjs                                                      # 预期：family 3 0:👨:0:18:0:2|1:👩:7:18:3:5|2:👧:14:18:6:8；nfd-cafe 与 nfd-stream 各 1 条且切块一致；overlap 6；strict-ff Utf8DecodeError
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/unicode-stream-matcher-core.git unicode-stream-matcher-core-B
cd unicode-stream-matcher-core-B
npm ci
npm run build
npm test                                                                 # 预期：1 failed / 57 passed
node verify_211.mjs                                                      # 预期：family 1 2:14:18:6:8（簇内只留下最后一个码点）；nfd-cafe 与 nfd-stream 各 1 条；overlap 6；strict-ff UTF8DecodeError
cd ..
```

---

## 第 212 题　Bug 修复　·　困难　·　无界面
<!-- solo-report:task=212 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/unicode-mark-highlight-core　A 分支：https://github.com/gy-vs/unicode-mark-highlight-core/tree/A　B 分支：https://github.com/gy-vs/unicode-mark-highlight-core/tree/B

存为 `verify_212.mjs`（放在仓库根目录）

```javascript
import * as m from './dist/index.js';

function show(label, hits, text) {
  const parts = hits.map((h) => {
    const id = h.queryId !== undefined ? h.queryId : h.queryIndex;
    const slice = text ? JSON.stringify(text.slice(h.start, h.end)) : '';
    return (id === undefined ? '' : id + '@') + h.start + '-' + h.end + '/' + slice;
  });
  console.log(label, hits.length, parts.join(';') || '(none)');
}

const nfd = 'Cafe\u0301';
show('nfd', m.findMatches(nfd, 'cafe'), nfd);

const zwj = 'ab\u200Dcd';
show('zwj-word', m.findMatches(zwj, 'abcd'), zwj);

const prep = '\u0600cafe';
show('prepend', m.findMatches(prep, 'cafe'), prep);

show('aaa', m.findMatches('aaa', 'aa'), 'aaa');

const multi = m.searchHits
  ? m.searchHits('cafe cafe', [
      { id: 'x', text: 'cafe' },
      { id: 'y', text: 'cafe' },
    ])
  : m.search('cafe cafe', ['cafe', 'cafe']);
show('multi', multi, 'cafe cafe');

const hits = m.findMatches('xx cafe yy', 'cafe');
if (m.clipExcerpt) {
  const ex = m.clipExcerpt('xx cafe yy', hits.map((h) => ({ ...h, queryId: 'q' })), 3, 9);
  console.log('clip', JSON.stringify(ex.text), JSON.stringify(ex.hits));
} else {
  const ex = m.cropSnippet('xx cafe yy', hits, { maxLength: 6, context: 0 });
  console.log('clip', JSON.stringify(ex.text), JSON.stringify(ex.matches));
}
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/unicode-mark-highlight-core.git unicode-mark-highlight-core-A
cd unicode-mark-highlight-core-A
npm ci
npm run build
npm test                                                                 # 预期：29 passed
node verify_212.mjs                                                      # 预期：nfd 1 0-5；zwj-word 1 0-5；prepend 1 0-5；aaa 2 段重叠命中；multi 4 条带 x/y 身份；clip "cafe y" 相对范围 start 0 end 4
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/unicode-mark-highlight-core.git unicode-mark-highlight-core-B
cd unicode-mark-highlight-core-B
npm ci
npm run build
npm test                                                                 # 预期：21 passed
node verify_212.mjs                                                      # 预期：nfd 1 0-5；zwj-word 0 (none)；prepend 1 0-5；aaa 1 段；multi 4 条带 0/1 序号；clip "cafe" 相对范围 start 0 end 4
cd ..
```

---

## 第 214 题　Bug 修复　·　困难　·　无界面
<!-- solo-report:task=214 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/eventlog-partial-tail-core　A 分支：https://github.com/gy-vs/eventlog-partial-tail-core/tree/A　B 分支：https://github.com/gy-vs/eventlog-partial-tail-core/tree/B

存为 `verify_214.mjs`（放在仓库根目录）

```javascript
import { existsSync, mkdtempSync, writeFileSync, readFileSync, readdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const mod = existsSync('./dist/index.js')
  ? await import('./dist/index.js')
  : await import('./src/index.js');

console.log('has-EventLog', typeof mod.EventLog);
console.log('has-ts-entry', existsSync('src/index.ts'));
console.log('has-tsconfig', existsSync('tsconfig.json'));

async function openLog(dir) {
  return Promise.resolve(mod.DurableEventLog.open(dir));
}

function segmentPath(dir) {
  const name = readdirSync(dir).find((f) => f.startsWith('segment'));
  return join(dir, name);
}

const dir = mkdtempSync(join(tmpdir(), 'elog-'));
const log = await openLog(dir);
await Promise.resolve(log.append('s', { n: 1 }));
await Promise.resolve(log.append('s', { n: 2 }));
await Promise.resolve(log.append('s', { n: 3 }));
if (log.close) await Promise.resolve(log.close());

const before = readFileSync(segmentPath(dir));
writeFileSync(segmentPath(dir), before.subarray(0, before.length - 5));

const log2 = await openLog(dir);
console.log('after-trunc-wm', log2.watermark());
const rec = await Promise.resolve(log2.append('s', { n: 'new' }));
console.log('append-seq', rec.sequence);
if (log2.close) await Promise.resolve(log2.close());

const log3 = await openLog(dir);
console.log('reopen-wm', log3.watermark(), log3.read().map((r) => r.sequence).join(','));
if (log3.close) await Promise.resolve(log3.close());

const dir2 = mkdtempSync(join(tmpdir(), 'elog2-'));
const log4 = await openLog(dir2);
await Promise.resolve(log4.append('s', { n: 1 }));
if (log4.close) await Promise.resolve(log4.close());
const good = readFileSync(segmentPath(dir2));
let extra;
if (existsSync('src/index.ts')) {
  extra = Buffer.alloc(8);
  extra.write('EVL1');
  extra.writeUInt32LE(0x7fffffff, 4);
} else {
  extra = Buffer.alloc(16);
  extra.writeUInt32BE(0x454c4731, 0);
  extra.writeUInt32BE(2, 4);
  extra.writeUInt32BE(0x7fffffff, 8);
  extra.writeUInt32BE(0, 12);
}
writeFileSync(segmentPath(dir2), Buffer.concat([good, extra]));
try {
  const log5 = await openLog(dir2);
  console.log('huge-len', 'opened', log5.watermark());
  if (log5.close) await Promise.resolve(log5.close());
} catch (e) {
  console.log('huge-len', e.name);
}

const dir3 = mkdtempSync(join(tmpdir(), 'elog3-'));
const log6 = await openLog(dir3);
await Promise.resolve(log6.append('s', { n: 1 }));
if (log6.close) await Promise.resolve(log6.close());
const size1 = readFileSync(segmentPath(dir3)).length;
await openLog(dir3).then(async (l) => {
  if (l.close) await Promise.resolve(l.close());
});
await openLog(dir3).then(async (l) => {
  if (l.close) await Promise.resolve(l.close());
});
const size2 = readFileSync(segmentPath(dir3)).length;
console.log('idempotent', size1, size2, size1 === size2);
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/eventlog-partial-tail-core.git eventlog-partial-tail-core-A
cd eventlog-partial-tail-core-A
npm install
npm run build
npm test                                                                 # 预期：26 passed
node verify_214.mjs                                                      # 预期：has-EventLog function；has-ts-entry true；has-tsconfig true；after-trunc-wm 2；append-seq 3；reopen-wm 3 1,2,3；huge-len LogCorruptionError；idempotent 57 57 true
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/eventlog-partial-tail-core.git eventlog-partial-tail-core-B
cd eventlog-partial-tail-core-B
npm install
npm run build                                                            # 预期：missing script: build
npm test                                                                 # 预期：Node 20 上 57 passed；Node 24 会把 test/ 当模块报 MODULE_NOT_FOUND
node verify_214.mjs                                                      # 预期：has-EventLog undefined；has-ts-entry false；has-tsconfig false；after-trunc-wm 2；append-seq 3；reopen-wm 3 1,2,3；huge-len opened 1；idempotent 28 28 true
cd ..
```

---

## 第 215 题　Feature 迭代　·　困难　·　无界面
<!-- solo-report:task=215 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/eventlog-idempotency-core　A 分支：https://github.com/gy-vs/eventlog-idempotency-core/tree/A　B 分支：https://github.com/gy-vs/eventlog-idempotency-core/tree/B

存为 `verify_215.mjs`（放在仓库根目录）

```javascript
import * as m from './dist/index.js';

async function openFresh() {
  if (m.MemoryVolume) {
    return m.EventLog.open({
      volume: new m.MemoryVolume(),
      namespaces: { default: 86400000 },
      autoVisible: true,
    });
  }
  return m.EventLog.open(new m.MemoryStorage());
}

const log = await openFresh();
const a = await log.append('s', { x: 1, y: 2 }, { key: 'k1' });
const b = await log.append('s', { y: 2, x: 1 }, { key: 'k1' });
console.log('replay', a.sequence, b.sequence, a.sequence === b.sequence, b.replay);

try {
  await log.append('s', { x: 9 }, { key: 'k1' });
  console.log('conflict', 'none');
} catch (e) {
  const diag = log.getConflict ? log.getConflict(undefined, 'k1') : log.conflicts()[0];
  console.log('conflict', e.name, diag && Object.keys(diag).sort().join(','));
}

let recovered;
if (m.MemoryVolume) {
  const vol = new m.MemoryVolume();
  const first = await m.EventLog.open({
    volume: vol,
    namespaces: { default: 86400000 },
    autoVisible: true,
  });
  await first.append('s', { n: 1 }, { key: 'r' });
  const bytes = vol.snapshotBytes();
  const damaged = bytes.slice();
  damaged[0] ^= 0xff;
  const bad = new m.MemoryVolume(damaged);
  try {
    const second = await m.EventLog.open({
      volume: bad,
      namespaces: { default: 86400000 },
    });
    recovered = 'opened:' + second.watermark();
  } catch (e) {
    recovered = e.name;
  }
} else {
  const store = new m.MemoryStorage();
  const first = await m.EventLog.open(store);
  await first.append('s', { n: 1 }, { key: 'r' });
  const bytes = store.snapshot();
  bytes[0] ^= 0xff;
  try {
    const second = await m.EventLog.open(store);
    recovered = 'opened:' + second.watermark();
  } catch (e) {
    recovered = e.name;
  }
}
console.log('bad-magic', recovered);

console.log('api', ['getConflict', 'conflicts', 'FileVolume', 'FileStorage', 'reportReplicaWatermark', 'advanceVisibilityWatermark'].filter((k) => typeof log[k] === 'function' || typeof m[k] === 'function').join(','));
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/eventlog-idempotency-core.git eventlog-idempotency-core-A
cd eventlog-idempotency-core-A
npm ci
npm run build
npm test                                                                 # 预期：35 passed
node verify_215.mjs                                                      # 预期：replay 1 1 true true；conflict IdempotencyConflictError at,existingDigest,existingSequence,expiresAt,incomingDigest；bad-magic opened:0；api getConflict,FileVolume,advanceVisibilityWatermark
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/eventlog-idempotency-core.git eventlog-idempotency-core-B
cd eventlog-idempotency-core-B
npm ci
npm run build
npm test                                                                 # 预期：34 passed
node verify_215.mjs                                                      # 预期：replay 1 1 true undefined；conflict IdempotencyConflictError canonical,detectedAt,digest,expiresAt,key,ns,otherCanonical,otherDigest,reason,seq；bad-magic FrameCorruptionError；api conflicts,FileStorage,reportReplicaWatermark
cd ..
```

---

## 第 216 题　Bug 修复　·　困难　·　无界面
<!-- solo-report:task=216 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/eventlog-watermark-race-core　A 分支：https://github.com/gy-vs/eventlog-watermark-race-core/tree/A　B 分支：https://github.com/gy-vs/eventlog-watermark-race-core/tree/B

存为 `verify_216.mjs`（放在仓库根目录）

```javascript
import * as m from './dist/index.js';

async function drainAll(log) {
  if (m.Follower) {
    const f = new m.Follower(log);
    const it = f[Symbol.asyncIterator]();
    const got = [];
    for (let i = 0; i < 3; i++) got.push((await it.next()).value.sequence);
    const pos = f.position;
    f.close();
    const done = await it.next();
    return { got: got.join(','), extra: 'pos=' + pos + ' done=' + done.done };
  }
  const got = [];
  const p = log.follow((e) => got.push(e.sequence));
  log.close();
  const n = await p;
  return { got: got.join(','), extra: 'ret=' + n };
}

async function failOnSecond(log) {
  const got = [];
  try {
    if (m.Follower) {
      const f = new m.Follower(log);
      for await (const e of f) {
        got.push(e.sequence);
        if (e.sequence === 2) throw new Error('boom');
      }
    } else {
      await log.follow((e) => {
        got.push(e.sequence);
        if (e.sequence === 2) throw new Error('boom');
      });
    }
    return { got: got.join(','), extra: 'no-throw' };
  } catch (e) {
    const extra =
      e.lastDeliveredSequence !== undefined ? 'last=' + e.lastDeliveredSequence : 'no-last';
    return { got: got.join(','), extra, err: e.message };
  }
}

const log = new m.EventLog();
log.append('s', 'a');
log.append('s', 'b');
log.append('s', 'c');
const d = await drainAll(log);
console.log('drain', d.got, d.extra);

const log2 = new m.EventLog();
log2.append('s', 'a');
log2.append('s', 'b');
log2.append('s', 'c');
const f = await failOnSecond(log2);
console.log('fail', f.got, f.extra, f.err);

const batch = new m.EventLog();
if (batch.appendMany) batch.appendMany('s', [1, 2, 3]);
else batch.appendAll('s', [1, 2, 3]);
console.log('batch-wm', batch.watermark());

const sample = new m.EventLog();
console.log(
  'api',
  ['Follower', 'WakeBus', 'ChangeSignal', 'SegmentedEventLog']
    .filter((k) => typeof m[k] === 'function')
    .concat(typeof sample.follow === 'function' ? ['follow'] : [])
    .join(','),
);
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/eventlog-watermark-race-core.git eventlog-watermark-race-core-A
cd eventlog-watermark-race-core-A
npm ci
npm run build
npm test                                                                 # 预期：30 passed
node verify_216.mjs                                                      # 预期：drain 1,2,3 ret=3；fail 1,2 last=1 boom；batch-wm 3；api WakeBus,follow
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/eventlog-watermark-race-core.git eventlog-watermark-race-core-B
cd eventlog-watermark-race-core-B
npm ci
npm run build
npm test                                                                 # 预期：38 passed
node verify_216.mjs                                                      # 预期：drain 1,2,3 pos=2 done=true；fail 1,2 no-last boom；batch-wm 3；api Follower,ChangeSignal,SegmentedEventLog
cd ..
```

---

## 第 263 题　Feature 迭代　·　困难　·　全栈
<!-- solo-report:task=263 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/cert-path-build-web　A 分支：https://github.com/gy-vs/cert-path-build-web/tree/A　B 分支：https://github.com/gy-vs/cert-path-build-web/tree/B

服务：`npm run dev` 同时起后端 4174 与前端 4173；浏览器开 http://localhost:4173。B 侧已拆掉 React/Vite，同一条 `npm run dev` 只起原生 http 在 4174，4173 起不来。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/cert-path-build-web.git cert-path-build-web-A
cd cert-path-build-web-A
npm install
npm test                                                                                          # 预期：14 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"         # 新窗口打出 cert path workbench http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/health | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                                                              # 浏览器打开后按下面「界面操作」走；被占用会自动 +1，以新窗口打出的 Local: 地址为准
Invoke-RestMethod http://127.0.0.1:4174/api/health | ConvertTo-Json -Compress                      # 预期：{"ok":true,"offline":true}
Invoke-RestMethod http://127.0.0.1:4174/api/fixtures | ConvertTo-Json -Compress                    # 预期：含 certsPem、anchorsPem、files（约 12 份，如 leaf.pem / root-a.pem）
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/validate -ContentType "application/json" -Body '{}' } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：400，error=empty_input
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/build -ContentType "application/json" -Body '{}' } catch { $_.Exception.Response.StatusCode.value__ }       # 预期：404，Cannot POST /api/build
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:4173，看到标题「证书路径工作台」和按钮「载入内置场景夹具」。A：按钮在顶栏；B：4173 连不上（Vite 已删除），即便改开 http://localhost:4174 也没有该按钮。
2. 点击「载入内置场景夹具」，左栏出现 leaf.example 等证书，盾牌图标可把证书「提升为信任锚」。A：列表出现；B：按钮不存在。
3. 点击「构建路径」，右栏出现路径卡片，逐边显示名称匹配 / AKI↔SKI / 签名验证。A：共枚举多条路径，含交叉签名双路径；B：按钮不存在，页面是「构建并枚举路径」。
4. 勾选「允许 SHA-1」或改「验证逻辑时间」，出现过期横幅「已标记为过期——点击"重新验证"」，主按钮变成「重新验证」。A：策略 revision 由前端自增；B：过期丝带来自服务端 binding.policyRevision，主按钮是「重新构建」。
5. 回到终端执行剩下的接口命令和 `taskkill`。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/cert-path-build-web.git cert-path-build-web-B
cd cert-path-build-web-B
npm install
npm test                                                                                          # 预期：35 passed（node --test test/）
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"         # 新窗口只打出 certificate chain workbench http://127.0.0.1:4174，没有 Vite Local: 4173
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/health | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                                                              # 预期：4173 连不上，Vite/React 栈已删除
Invoke-RestMethod http://127.0.0.1:4174/api/health | ConvertTo-Json -Compress                      # 预期：{"ok":true,"offline":true}
Invoke-RestMethod http://127.0.0.1:4174/api/fixtures | ConvertTo-Json -Compress                    # 预期：含 certificates、scenarios（约 10 个场景），没有 files/certsPem
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/validate -ContentType "application/json" -Body '{}' } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404，error=not_found
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/build -ContentType "application/json" -Body '{}' } catch { $_.Exception.Response.StatusCode.value__ }       # 预期：400，error=no_certificates
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 1、2、3、4 步。

---

## 第 265 题　Feature 迭代　·　困难　·　全栈
<!-- solo-report:task=265 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/cert-revocation-sim-web　A 分支：https://github.com/gy-vs/cert-revocation-sim-web/tree/A　B 分支：https://github.com/gy-vs/cert-revocation-sim-web/tree/B

服务：`npm run dev` 同时起后端 4174 与前端 4173；浏览器开 http://localhost:4173。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/cert-revocation-sim-web.git cert-revocation-sim-web-A
cd cert-revocation-sim-web-A
npm install
npm test                                                                                          # 预期：42 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"         # 新窗口打出 revocation server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/health | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                                                              # 浏览器打开后按下面「界面操作」走；被占用会自动 +1，以新窗口打出的 Local: 地址为准
Invoke-RestMethod http://127.0.0.1:4174/api/health | ConvertTo-Json -Compress                      # 预期：{"offline":true,"networkRequests":"disabled","engine":"local-crypto"}
Invoke-RestMethod http://127.0.0.1:4174/api/materials | ConvertTo-Json -Compress                   # 预期：counts.certs=12、crls=5、ocsps=3（启动已加载 demo-bundle.json）
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/demo -ContentType "application/json" -Body '{}' } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404，Cannot POST /api/demo
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/evaluate -ContentType "application/json" -Body '{"time":"2026-01-20T12:00:00Z","policy":{"conflict":"revoked-wins"}}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：200，policy.conflict=revoked-wins；leaf-revoked/leaf-delta/leaf-indirect=revoked，leaf-good=good
Invoke-RestMethod http://127.0.0.1:4174/api/policy | ConvertTo-Json -Compress                      # 预期：policies 含 ocsp-first、crl-first、revoked-wins、fresh-wins、reject-conflict
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:4173，看到标题「证书链吊销工作台」和左栏「材料库」。A：启动已自动加载 12 证书 / 5 CRL / 3 OCSP，没有「载入演示场景」；B：材料库为空，顶栏有「载入演示场景」。
2. 点击「评估」，中栏时间轴与各证书状态刷新。A：冲突策略下拉里有 revoked-wins / fresh-wins / reject-conflict；B：策略只有 strict / crl_first / ocsp_first / latest，没有 revoked-wins。
3. 点击「冻结模拟会话」。A：出现「已冻结会话」和「正在使用冻结会话」，之后仍可改时间再评估（代次守卫丢掉旧响应）；B：按钮原文是「冻结模拟」，冻结后时间/策略/nonce 整体禁用，需先点「退出冻结，使用新时间」。
4. 点击时间轴上某个状态变化点。A：可定位到带秒的逻辑时间；B：fromLocalInput 按整分构造 ISO，非整分变化点会落到变化前一刻，界面仍显示旧状态。
5. 尝试点「导入 JSON」喂真实 .crl。A：只接受自定义 JSON 信封，真实 DER/CRL 进不去；B：材料区可贴 PEM 或 hex DER，点导入后走 /api/materials。
6. 回到终端执行剩下的接口命令和 `taskkill`。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/cert-revocation-sim-web.git cert-revocation-sim-web-B
cd cert-revocation-sim-web-B
npm install
npm test                                                                                          # 预期：36 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"         # 新窗口打出 offline server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/health | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                                                              # 浏览器打开后按下面「界面操作」走；被占用会自动 +1，以新窗口打出的 Local: 地址为准
Invoke-RestMethod http://127.0.0.1:4174/api/health | ConvertTo-Json -Compress                      # 预期：{"ok":true,"offline":true,"networkRequests":"never"}
try { Invoke-RestMethod http://127.0.0.1:4174/api/materials | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404，Cannot GET /api/materials
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/demo -ContentType "application/json" -Body '{}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：200，含 Demo Root CA 等真实 DER 材料
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/evaluate -ContentType "application/json" -Body '{"time":"2026-01-20T12:00:00Z","policy":{"conflict":"revoked-wins"}}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：400，{"error":"bad policy"}
try { Invoke-RestMethod http://127.0.0.1:4174/api/policy | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404，Cannot GET /api/policy
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 1、2、3、4、5 步。

---

## 第 267 题　Feature 迭代　·　困难　·　全栈
<!-- solo-report:task=267 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/cert-algorithm-policy-web　A 分支：https://github.com/gy-vs/cert-algorithm-policy-web/tree/A　B 分支：https://github.com/gy-vs/cert-algorithm-policy-web/tree/B

服务：`npm run dev` 同时起后端 4174 与前端 4173；浏览器开 http://localhost:4173。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/cert-algorithm-policy-web.git cert-algorithm-policy-web-A
cd cert-algorithm-policy-web-A
npm install
npm test                                                                                          # 预期：39 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"         # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                                                              # 浏览器打开后按下面「界面操作」走；被占用会自动 +1，以新窗口打出的 Local: 地址为准
Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | ConvertTo-Json -Compress                   # 预期：{"family":"cert-chain","count":2,"policies":2}
Invoke-RestMethod http://127.0.0.1:4174/api/policies | ConvertTo-Json -Compress                    # 预期：strict revision=2（Strict modern）、compatible revision=1
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/evaluate -ContentType "application/json" -Body '{"at":"2019-06-01T00:00:00Z","chainId":"alpha","a":{"policyId":"strict"},"b":{"policyId":"compatible"}}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：200，a.allowed=false rev=2；b.allowed=true rev=1
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/verify/compare -ContentType "application/json" -Body '{"chainId":"alpha","at":"2024-12-01T12:00:00Z","purpose":"serverAuth","left":{"policyId":"modern"},"right":{"policyId":"baseline"}}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404，Cannot POST /api/verify/compare
try { Invoke-RestMethod -Method Put -Uri http://127.0.0.1:4174/api/policies/strict -ContentType "application/json" -Body '{"revision":99,"rules":[{"id":"x"}]}' } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：422，error=policy_invalid；随后 GET 该策略 revision 仍为 2（无部分发布）
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:4173，看到「Certificate Chain Lab」和共享区「Logical verification time」。左右栏分别是 Policy A / Policy B。A：默认策略 strict 与 compatible；B：标题多了 Algorithm Policy Workbench，左右是 modern 与 baseline。
2. 左右选定策略后点击「Compare policies」。A：状态栏出现 Compared at … verdict difference(s)，strict 拒链、compatible 放行；B：按钮原文是「Compare both policies on this chain」，走 /api/verify/compare。
3. 点击对照矩阵里某个失败格，对应规则卡片滚动并闪烁。两侧编辑器都还在。
4. 在左侧规则上点 title 为「Move earlier (higher priority)」的上移按钮，再点「Compare policies」。A：数组顺序即优先级，重排会改变判定；B：按钮 title 是「Move up」，编译器按特异度/id 重排，界面顺序不影响结果。
5. 把「Logical verification time」改成带秒的值再比较。A：atToIso 只认长度 16，否则静默落到 2019-06-01；B：按完整 ISO 解析，早于所有版本时报「当时无生效版本」。
6. 回到终端执行剩下的接口命令和 `taskkill`。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/cert-algorithm-policy-web.git cert-algorithm-policy-web-B
cd cert-algorithm-policy-web-B
npm install
npm test                                                                                          # 预期：32 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"         # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                                                              # 浏览器打开后按下面「界面操作」走；被占用会自动 +1，以新窗口打出的 Local: 地址为准
Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | ConvertTo-Json -Compress                   # 预期：family=cert-chain，policies 为 modern/baseline 对象数组
Invoke-RestMethod http://127.0.0.1:4174/api/policies | ConvertTo-Json -Compress                    # 预期：modern latestVersion=2，baseline latestVersion=1，没有 strict
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/evaluate -ContentType "application/json" -Body '{"at":"2019-06-01T00:00:00Z","chainId":"alpha","a":{"policyId":"strict"},"b":{"policyId":"compatible"}}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404，Cannot POST /api/evaluate
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/verify/compare -ContentType "application/json" -Body '{"chainId":"alpha","at":"2024-12-01T12:00:00Z","purpose":"serverAuth","left":{"policyId":"modern"},"right":{"policyId":"baseline"}}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：200，left.allowed=false resolvedVersion=1；right.allowed=true resolvedVersion=1
try { Invoke-RestMethod -Method Put -Uri http://127.0.0.1:4174/api/policies/strict -ContentType "application/json" -Body '{"revision":99,"rules":[{"id":"x"}]}' } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404，Cannot PUT /api/policies/strict（发布走 /api/policies/:id/versions）
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 1、2、4、5 步。

---

## 第 268 题　Bug 修复　·　困难　·　全栈
<!-- solo-report:task=268 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/message-dedup-window-web　A 分支：https://github.com/gy-vs/message-dedup-window-web/tree/A　B 分支：https://github.com/gy-vs/message-dedup-window-web/tree/B

服务：`npm run dev` 同时起后端 4174 与前端 4173；浏览器开 http://localhost:4173。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/message-dedup-window-web.git message-dedup-window-web-A
cd message-dedup-window-web-A
npm install
npm test                                                                                          # 预期：20 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"         # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                                                              # 浏览器打开后按下面「界面操作」走；被占用会自动 +1，以新窗口打出的 Local: 地址为准
Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | ConvertTo-Json -Compress                   # 预期：{"family":"message-delivery","count":2}
try { $att = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/dedup/attempt -ContentType "application/json" -Body '{"key":"order-1001"}'; $att | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：201，outcome=started，state=processing，attempt=1
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/dedup/attempt -ContentType "application/json" -Body '{"key":"order-1001"}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：200，outcome=suppressed，reason=in_progress
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/dedup/complete -ContentType "application/json" -Body ('{"key":"order-1001","lease":"' + $att.record.lease + '","result":{"ok":true}}') | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：200，outcome=delivered
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/dedup/complete -ContentType "application/json" -Body ('{"key":"order-1001","lease":"' + $att.record.lease + '","result":{"ok":true}}') | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：200，outcome=already_terminal，state=delivered（事件里多一条 suppressed）
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/dedup/clock/jump -ContentType "application/json" -Body '{"offsetMs":-3600000}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：200，wallOffsetMs=-3600000，logicalNow 不回退
Invoke-RestMethod http://127.0.0.1:4174/api/dedup/state | ConvertTo-Json -Compress                 # 预期：stats.attempts=1、suppressed=2、delivered=1
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:4173，看到「Message Delivery Lab」和 Simulate 面板「Idempotency key」。A：主按钮是「Attempt delivery」；B：主按钮是「Send」，没有 Attempt delivery。
2. 键里填 `order-1001`，点击「Attempt delivery」，再点「Timeout retry ×2」。A：attempts 与 suppressed 增加，delivered 不动；B：「Timeout retry ×2」按钮不存在。
3. 点击「Complete」，delivered 加一；再点一次 Complete。A：事件流出现 duplicate 的 suppressed，没有第二个成功终态；B：行内按钮是「Deliver」，重复完成返回 noop 且不发事件。
4. 点击「Wall clock −1h」，再点「Cleanup expired」。A：逻辑时钟不回退，过期终态仍可按窗口清扫；B：有「Wall clock −1h」但没有 Cleanup expired，窗口要靠「Advance +window」才能关。
5. 回到终端执行剩下的接口命令和 `taskkill`。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/message-dedup-window-web.git message-dedup-window-web-B
cd message-dedup-window-web-B
npm install
npm test                                                                                          # 预期：19 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"         # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                                                              # 浏览器打开后按下面「界面操作」走；被占用会自动 +1，以新窗口打出的 Local: 地址为准
Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | ConvertTo-Json -Compress                   # 预期：{"family":"message-delivery","count":2}
try { $att = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/dedup/attempt -ContentType "application/json" -Body '{"key":"order-1001"}'; $att | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404，Cannot POST /api/dedup/attempt
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/dedup/attempt -ContentType "application/json" -Body '{"key":"order-1001"}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/dedup/complete -ContentType "application/json" -Body '{"key":"order-1001","result":{"ok":true}}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/dedup/complete -ContentType "application/json" -Body '{"key":"order-1001","result":{"ok":true}}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/dedup/clock/jump -ContentType "application/json" -Body '{"offsetMs":-3600000}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404，时钟推进走 /api/delivery/advance，不推则 logicalNow 停在 0
try { Invoke-RestMethod http://127.0.0.1:4174/api/dedup/state | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404，状态在 /api/delivery/state
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 1、2、3、4 步。

---

## 第 270 题　Bug 修复　·　困难　·　全栈
<!-- solo-report:task=270 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/message-ack-gap-web　A 分支：https://github.com/gy-vs/message-ack-gap-web/tree/A　B 分支：https://github.com/gy-vs/message-ack-gap-web/tree/B

服务：`npm run dev` 同时起后端 4174 与前端 4173；浏览器开 http://localhost:4173。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/message-ack-gap-web.git message-ack-gap-web-A
cd message-ack-gap-web-A
npm install
npm test                                                                                          # 预期：30 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"         # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/state | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                                                              # 浏览器打开后按下面「界面操作」走；被占用会自动 +1，以新窗口打出的 Local: 地址为准
Invoke-RestMethod http://127.0.0.1:4174/api/state | ConvertTo-Json -Compress                       # 预期：committedSeq=0，ackedAhead=[]，gaps.pendingRanges=[]
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/publish -ContentType "application/json" -Body '{"count":12}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：{"published":12,"firstSeq":1,"lastSeq":12}
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/consumers -ContentType "application/json" -Body '{"consumerId":"c1","leaseMs":60000}' | ConvertTo-Json -Compress   # 预期：id=c1
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/deliver -ContentType "application/json" -Body '{"consumerId":"c1","maxMessages":12,"attemptTimeoutMs":60000}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：200，deliveries 序号 1..12，attempt=1
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/ack -ContentType "application/json" -Body '{"consumerId":"c1","seq":12,"attempt":1}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：{"advancedTo":0,"duplicated":false}，12 只进离散集合
for ($i = 1; $i -le 10; $i++) { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/ack -ContentType "application/json" -Body ('{"consumerId":"c1","seq":' + $i + ',"attempt":1}') | Out-Null }
Invoke-RestMethod http://127.0.0.1:4174/api/state | ConvertTo-Json -Compress                       # 预期：committedSeq=10，ackedAhead=[12]，inFlight 含 seq=11
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:4173，看到「消息交付工作台 · 确认水位与缺口」和水位卡「committedSeq」。A：中栏用 committedSeq / ackedAhead；B：标题没有「确认水位与缺口」，水位字段是 watermark，离散集合叫前方离散确认。
2. 填 consumerId=`c1`，点击「注册 / 重获租约」，数量填 12，点击「发布 12 条」，再点「拉取」。A：这几个按钮都在；B：「注册 / 重获租约」不存在，改为「注册消费者」（服务端发 UUID），发布是「追加发布（下一个序号）」，拉取是「拉取消息」。
3. 先确认序号 12，再确认 1..10，留下 11。A：水位停在 10，前方离散确认集合出现 12，缺口/在途露出 11；B：可用「乱序 ack：12 先于 11」一键复现，A 没有该按钮。
4. 点击「崩溃重启」。A：按钮 title 为「模拟崩溃重启:从快照恢复,在途消息重新可交付」，前缀 1..10 不再投递，11 重新可交付且 attempt 递增；B：按钮是「模拟崩溃重启」，走 /api/admin/restart。
5. 回到终端执行剩下的接口命令和 `taskkill`。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/message-ack-gap-web.git message-ack-gap-web-B
cd message-ack-gap-web-B
npm install
npm test                                                                                          # 预期：25 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"         # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/state | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                                                              # 浏览器打开后按下面「界面操作」走；被占用会自动 +1，以新窗口打出的 Local: 地址为准
Invoke-RestMethod http://127.0.0.1:4174/api/state | ConvertTo-Json -Compress                       # 预期：watermark="0"，pendingAhead=[]，gaps=[]
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/publish -ContentType "application/json" -Body '{"count":12}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404，Cannot POST /api/publish（发布走 /api/messages）
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/consumers -ContentType "application/json" -Body '{"consumerId":"c1","leaseMs":60000}' | ConvertTo-Json -Compress   # 预期：201，忽略传入的 consumerId，返回新的 consumerId UUID
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/deliver -ContentType "application/json" -Body '{"consumerId":"c1","maxMessages":12,"attemptTimeoutMs":60000}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404，Cannot POST /api/deliver（拉取走 /api/fetch 且要 x-consumer-id）
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/ack -ContentType "application/json" -Body '{"consumerId":"c1","seq":12,"attempt":1}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404 或 4xx（缺 x-consumer-id / deliveryId）
for ($i = 1; $i -le 10; $i++) { try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/ack -ContentType "application/json" -Body ('{"consumerId":"c1","seq":' + $i + ',"attempt":1}') | Out-Null } catch { $_.Exception.Response.StatusCode.value__ } }
Invoke-RestMethod http://127.0.0.1:4174/api/state | ConvertTo-Json -Compress                       # 预期：watermark 仍为 "0"（/api/publish 未写下任何消息）
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 1、2、3、4 步。

---

## 第 271 题　Feature 迭代　·　困难　·　全栈
<!-- solo-report:task=271 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/message-deadletter-replay-web　A 分支：https://github.com/gy-vs/message-deadletter-replay-web/tree/A　B 分支：https://github.com/gy-vs/message-deadletter-replay-web/tree/B

服务：`npm run dev` 同时起后端 4174 与前端 4173；浏览器开 http://localhost:4173。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/message-deadletter-replay-web.git message-deadletter-replay-web-A
cd message-deadletter-replay-web-A
npm install
npm test                                                                                          # 预期：23 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"         # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                                                              # 浏览器打开后按下面「界面操作」走；被占用会自动 +1，以新窗口打出的 Local: 地址为准
Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | ConvertTo-Json -Compress                   # 预期：{"family":"message-delivery","deadLetters":4}
$batch = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/batches -ContentType "application/json" -Body '{}'
$batch | ConvertTo-Json -Compress                                                                 # 预期：201/对象，id 如 rb-0001，status=preview，items.length=4，revision=1
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/dead-letters -ContentType "application/json" -Body '{"topic":"orders.created","headers":{"x-dlq-sim":"fail-once"},"failures":[{"reason":"timeout"}]}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：201，新死信写入池，但不进入已冻结批次
Invoke-RestMethod ('http://127.0.0.1:4174/api/batches/' + $batch.id) | ConvertTo-Json -Compress     # 预期：items 仍为 4，filter.candidateTotal=4
try { Invoke-RestMethod -Method Post -Uri ('http://127.0.0.1:4174/api/batches/' + $batch.id + '/start') -ContentType "application/json" -Body '{"revision":0}' } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：409 revision_conflict
try { Invoke-RestMethod -Method Patch -Uri ('http://127.0.0.1:4174/api/batches/' + $batch.id) -ContentType "application/json" -Body '{"revision":1,"transform":{"targetTopic":"orders.v2"}}' } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404，冻结后改配置只能另建批次
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:4173，看到「消息交付工作台 · 死信重放」和左栏筛选。A：种子 4 条（orders.created 等）；B：标题是「死信重放工作台」，种子 5 条（orders.v1 等）。
2. 点击「冻结筛选结果并生成预览」，核对预览条数等于冻结数量。A：文案「确定预览：以下 N 条为服务端冻结的集合」；B：文案「已冻结 N 条（与冻结集合一致）」。
3. 点击「模拟筛选期间新增死信」。A：新死信不进入本批次，items 仍为冻结数；B：详情以 driftAdded 计数提示，同样不入批。
4. 点击「确认并开始发送（N 条）」。A：该按钮原文如此，目标拒绝是独立 rejected 状态；B：按钮是「开始重放」，失败只有 failed 一种，目标拒绝也会被「仅重试失败项」再发。
5. 部分失败后点击「仅重试 N 条失败项」。A：只捞 failed，成功项 attempts 保持 1，rejected 不重投；B：按钮是「仅重试失败项（N）」，仍为 failed 的项（含永久拒绝）会再入队。
6. 寻找「应用左侧修改到冻结配置」。A：按钮不存在，改目标主题只能冻结前改或另建批次；B：开始前可用该按钮 PATCH 配置，冻结集合不变。
7. 回到终端执行剩下的接口命令和 `taskkill`。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/message-deadletter-replay-web.git message-deadletter-replay-web-B
cd message-deadletter-replay-web-B
npm install
npm test                                                                                          # 预期：14 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"         # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                                                              # 浏览器打开后按下面「界面操作」走；被占用会自动 +1，以新窗口打出的 Local: 地址为准
Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | ConvertTo-Json -Compress                   # 预期：{"family":"dead-letter-replay","count":5}
$batch = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/batches -ContentType "application/json" -Body '{}'
$batch | ConvertTo-Json -Compress                                                                 # 预期：status=pending，frozenIds 5 条（dl-1001..dl-1005），revision=1
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/dead-letters -ContentType "application/json" -Body '{"topic":"orders.created","headers":{"x-dlq-sim":"fail-once"},"failures":[{"reason":"timeout"}]}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404，Cannot POST /api/dead-letters（注入走 /api/dev/dead-letters）
Invoke-RestMethod ('http://127.0.0.1:4174/api/batches/' + $batch.id) | ConvertTo-Json -Compress     # 预期：frozenIds 仍为 5，driftAdded=0（上面那次注入 404，未写入）
try { Invoke-RestMethod -Method Post -Uri ('http://127.0.0.1:4174/api/batches/' + $batch.id + '/start') -ContentType "application/json" -Body '{"revision":0}' } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：409
try { Invoke-RestMethod -Method Patch -Uri ('http://127.0.0.1:4174/api/batches/' + $batch.id) -ContentType "application/json" -Body '{"revision":1,"transform":{"targetTopic":"orders.v2"}}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：200，revision 变为 2，targetTopic=orders.v2，frozenIds 不变
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 1、4、5、6 步。

---

## 第 275 题　Feature 迭代　·　困难　·　全栈
<!-- solo-report:task=275 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/plan-regression-gate-web　A 分支：https://github.com/gy-vs/plan-regression-gate-web/tree/A　B 分支：https://github.com/gy-vs/plan-regression-gate-web/tree/B

服务：`npm run dev` 同时起后端 4174 与前端 4173；浏览器开 http://localhost:4173（被占用会自动 +1，以新窗口打出的 Local: 地址为准）。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/plan-regression-gate-web.git plan-regression-gate-web-A
cd plan-regression-gate-web-A
npm ci
npm test                                                       # 预期：观察 vitest 末行 passed 数（交付材料写 26）
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/state | Out-Null; break } catch { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { Start-Sleep -Seconds 1 } } }
Start-Process http://localhost:4173                              # 浏览器打开后按下面「界面操作」走
try { Invoke-RestMethod http://127.0.0.1:4174/api/state | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：含 schemaRevision、stats.revision、parameterSets、runCapacity=2
try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/runs -ContentType "application/json" -Body '{"parameterSetId":"ps-main","concurrency":2}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：返回 runId
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:4173，看到顶栏「Plan Regression Gate」以及 schema / stats / rules revision。A：左栏标题「Parameter samples」，顶栏有「Refresh stats」；B：顶栏「查询计划回归门控」，左栏「参数集」。
2. 中栏看样例结果表。A：表格按样例原顺序，另有 Streamed 列显示到达次序；B：结果按 index 回填到原位置，状态分为通过、失败、无效、未运行。
3. 点击「Run gate」（B 侧为「运行门控」），等表格开始填入结果。
4. 运行中立刻点击「Cancel」（B 侧为「取消」）。A：未领取样例徽章为 not run 而非 failed；B：未启动样例标为未运行，与失败分色。
5. 在规则面板点击「Save rules (new revision)」（B 侧先展开「阈值规则（按标签覆盖）」再点「保存规则」），然后对刚完成的运行点「Publish」（B 侧为「发布」）。A：旧运行不能发到新规则 revision；B：提示规则已更新、旧运行不能发布。
6. 点击「Refresh stats」（B 侧展开「统计信息」后点「保存统计」）。A：顶栏 stats rev 前进；B：统计 rN 前进。
7. 回到终端执行剩下的接口命令并 `taskkill`。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/plan-regression-gate-web.git plan-regression-gate-web-B
cd plan-regression-gate-web-B
npm ci
npm test                                                       # 预期：23 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/state | Out-Null; break } catch { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { Start-Sleep -Seconds 1 } } }
Start-Process http://localhost:4173                              # 浏览器打开后按下面「界面操作」走
try { Invoke-RestMethod http://127.0.0.1:4174/api/state | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：family=query-plan-gate，含 paramSets、statsRevision、rulesRevision
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/runs -ContentType "application/json" -Body '{"parameterSetId":"ps-main","concurrency":2}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404（B 入口是 POST /api/gates）
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 1、2、4、5 步。

---

## 第 279 题　Feature 迭代　·　困难　·　全栈
<!-- solo-report:task=279 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/patch-threeway-review-web　A 分支：https://github.com/gy-vs/patch-threeway-review-web/tree/A　B 分支：https://github.com/gy-vs/patch-threeway-review-web/tree/B

服务：`npm run dev` 同时起后端 4174 与前端 4173；浏览器开 http://localhost:4173（被占用会自动 +1，以新窗口打出的 Local: 地址为准）。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/patch-threeway-review-web.git patch-threeway-review-web-A
cd patch-threeway-review-web-A
npm ci
npm test                                                       # 预期：27 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/documents | Out-Null; break } catch { try { Invoke-RestMethod http://127.0.0.1:4174/api/reviews | Out-Null; break } catch { Start-Sleep -Seconds 1 } } }
Start-Process http://localhost:4173                              # 浏览器打开后按下面「界面操作」走
try { Invoke-RestMethod http://127.0.0.1:4174/api/documents | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：含 id=doc-1、name=示例：产品说明书
try { Invoke-RestMethod http://127.0.0.1:4174/api/documents/doc-1/review | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：有 conflict 组；演示段带小标题，同块双改能成冲突
try { Invoke-RestMethod http://127.0.0.1:4174/api/reviews | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/documents -ContentType "application/json" -Body '{"name":"cn-edit","baseline":"\u652f\u6301\u4e09\u65b9\u5bf9\u6bd4","local":"\u652f\u6301\u4e09\u65b9\u5bf9\u6bd4\u4e0e\u5408\u5e76","remote":"\u652f\u6301\u4e09\u65b9\u5bf9\u6bd4\u4e0e\u534f\u4f5c"}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：201 新文档；无标点中文整段成一词，改写常被判成删除加新增
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:4173，看到顶栏「文档补丁工作台」。A：左栏有「示例：产品说明书」；B：左栏有「发布说明三方审阅」。
2. 点选种子文档，中栏看冲突组。A：冲突卡片有「采用本地」「采用远端」；B：有「采纳本地」「采纳远端」以及保留基线 / 自定义合并。
3. 只对其中一组点「采用本地」（B 侧点「采纳本地」再点「记录审阅意见」），然后点「提交已审决定」（B 侧为「提交已审 N 组」）。A：右栏「合并结果」与补丁历史更新，未选冲突保持待审；B：状态类似「已提交 N 组，M 组保持悬置」。
4. 点击「导入」（B 侧为「导入三方版本」）。在「名称」填 `cn-edit`，基线 / 本地版 / 远端版分别填无标点中文段「支持三方对比」「支持三方对比与合并」「支持三方对比与协作」，A 再点「创建三方评审」。
5. 打开刚导入的评审看冲突。A：无标点中文改写相似度常为 0，界面更像两侧各自删除再插入，同块双改不成冲突；B：汉字逐字切分，该改写能认成 edit_edit 冲突。
6. 对已决条目点「撤销决定（作为新决定提交）」（B 侧为「撤销该决定」）再提交。A：撤销作为 pending 决定；B：该组重新进入待审。
7. 回到终端执行剩下的接口命令并 `taskkill`。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/patch-threeway-review-web.git patch-threeway-review-web-B
cd patch-threeway-review-web-B
npm ci
npm test                                                       # 预期：38 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/documents | Out-Null; break } catch { try { Invoke-RestMethod http://127.0.0.1:4174/api/reviews | Out-Null; break } catch { Start-Sleep -Seconds 1 } } }
Start-Process http://localhost:4173                              # 浏览器打开后按下面「界面操作」走
try { Invoke-RestMethod http://127.0.0.1:4174/api/documents | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
try { Invoke-RestMethod http://127.0.0.1:4174/api/documents/doc-1/review | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
try { Invoke-RestMethod http://127.0.0.1:4174/api/reviews | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：列表含 id=rev-1、name=发布说明三方审阅
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/documents -ContentType "application/json" -Body '{"name":"cn-edit","baseline":"\u652f\u6301\u4e09\u65b9\u5bf9\u6bd4","local":"\u652f\u6301\u4e09\u65b9\u5bf9\u6bd4\u4e0e\u5408\u5e76","remote":"\u652f\u6301\u4e09\u65b9\u5bf9\u6bd4\u4e0e\u534f\u4f5c"}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404（B 入口是 POST /api/reviews）
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 1、2、5 步。

---

## 第 284 题　Bug 修复　·　困难　·　全栈
<!-- solo-report:task=284 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/flag-percent-rollout-web　A 分支：https://github.com/gy-vs/flag-percent-rollout-web/tree/A　B 分支：https://github.com/gy-vs/flag-percent-rollout-web/tree/B

服务：`npm run dev` 同时起后端 4174 与前端 4173；浏览器开 http://localhost:4173（被占用会自动 +1，以新窗口打出的 Local: 地址为准）。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/flag-percent-rollout-web.git flag-percent-rollout-web-A
cd flag-percent-rollout-web-A
npm ci
npm test                                                       # 预期：40 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                              # 浏览器打开后按下面「界面操作」走
Invoke-RestMethod http://127.0.0.1:4174/api/flags | ConvertTo-Json -Compress   # 预期：alpha 的 hasRollout=true，beta 的 hasRollout=false
try { Invoke-RestMethod http://127.0.0.1:4174/api/flags/beta/rollout } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404，body.error=no_rollout
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/rollout/plan -ContentType "application/json" -Body '{"variants":[{"id":"off","weight":0},{"id":"a","weight":50},{"id":"b","weight":50}]}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：半开区间覆盖 1000000 槽，off.slots=0
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/flags/alpha/assign -ContentType "application/json" -Body '{"userId":"user-42"}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:4173，看到顶栏「Feature Evaluation Lab」。A：左栏标题「Flags」，alpha 带 · rollout；B：左栏标题「Items」。
2. 选中 alpha。A：中栏是变体表，有「Save rollout」「Add variant」，预览区标题「Slot preview」显示 `[start, end)`；B：中栏是 aria-label「Content」的 JSON 文本框，下方「Variant slots」面板显示整数槽与半开区间。
3. 在「user key」（B 侧为「Test user」）里保持或输入 `user-42`，A 点「Evaluate」，看命中变体与 slot。B：输入框一改就显示 hash → slot → 变体，无需单独按钮。
4. A 点「Simulate 1,000 deterministic users」看分布；B 无此按钮，分布需回终端打 simulate 接口。
5. 左栏改点 beta。A：加载分支把 404 收成 `config: null` 仍当 data 为真去读 `data.config.variants`，控制台 `Cannot read properties of null`，界面停在 Loading，新建配置走不通；B：beta 正常打开，JSON 里是 search-ranking 的 33.33/33.33/33.34 权重。
6. 回到 alpha，点「Add variant」（B 侧无此按钮，只能在 JSON 里手写增删），观察槽位表是否仍按变体 id 而不是行序划分。
7. 回到终端执行剩下的接口命令并 `taskkill`。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/flag-percent-rollout-web.git flag-percent-rollout-web-B
cd flag-percent-rollout-web-B
npm ci
npm test                                                       # 预期：40 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                              # 浏览器打开后按下面「界面操作」走
Invoke-RestMethod http://127.0.0.1:4174/api/flags | ConvertTo-Json -Compress   # 预期：alpha 与 beta 都在，无 hasRollout 字段
try { Invoke-RestMethod http://127.0.0.1:4174/api/flags/beta/rollout } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404（B 无 rollout 子资源）
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/rollout/plan -ContentType "application/json" -Body '{"variants":[{"id":"off","weight":0},{"id":"a","weight":50},{"id":"b","weight":50}]}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404（B 入口是 /api/flags/:id/assign）
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/flags/alpha/assign -ContentType "application/json" -Body '{"userId":"user-42"}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：含 hash、slot、variant，槽位落在半开区间内
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 2、4、5、6 步。

---

## 第 285 题　Feature 迭代　·　困难　·　全栈
<!-- solo-report:task=285 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/flag-config-publish-web　A 分支：https://github.com/gy-vs/flag-config-publish-web/tree/A　B 分支：https://github.com/gy-vs/flag-config-publish-web/tree/B

服务：`npm run dev` 同时起后端 4174 与前端 4173；浏览器开 http://localhost:4173（被占用会自动 +1，以新窗口打出的 Local: 地址为准）。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/flag-config-publish-web.git flag-config-publish-web-A
cd flag-config-publish-web-A
npm ci
npm test                                                       # 预期：12 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                              # 浏览器打开后按下面「界面操作」走
try { Invoke-RestMethod http://127.0.0.1:4174/api/evaluate | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：带 releaseId 的完整旧/新 release 快照，看不到半切换
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/evaluate -ContentType "application/json" -Body '{"environment":"prod"}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404（A 是 GET /api/evaluate）
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/releases/publish -ContentType "application/json" -Body '{"flags":[{"id":"alpha"}],"flagIds":["alpha"],"environment":"prod","note":"partial"}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：成功发布；release 是全量快照，未选中的 flag 仍留在新 release 里
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:4173，看到顶栏「Feature Evaluation Lab」和 current release。A：顶栏只有「Publish all drafts as release」；B：左栏可勾选草稿组成发布集，另有「目标环境」和 placeholder「note」。
2. 中栏点「Save draft」保存当前草稿，状态类似 Saved rev N。两侧都有此按钮。
3. 尝试只发一部分 flag。A：页面上没有发布集勾选，只能点「Publish all drafts as release」，做不出只发两个 flag 的动作；B：勾选 alpha（可再勾 beta），点「原子发布所选草稿」。
4. 看发布结果。A：成功时反馈 `Published rel-xxxx (...)`，右侧「Release history」出现新卡片并带 live；B：状态 `Published rel-… — atomic switch complete`。若 B 只勾 alpha，未勾选的在线 flag 会从新 release 消失。
5. 在历史卡片上，A 点「Restore as new release」；B 点「回滚到此（创建新 release）」。两侧都是新建 release 而不是移动历史记录。
6. A 点「Analyze」看 Inspection；B 点「Evaluate」，评估区显示本次读到的 releaseId。A 无 Evaluate 按钮。
7. 回到终端执行剩下的接口命令并 `taskkill`。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/flag-config-publish-web.git flag-config-publish-web-B
cd flag-config-publish-web-B
npm ci
npm test                                                       # 预期：18 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                              # 浏览器打开后按下面「界面操作」走
try { Invoke-RestMethod http://127.0.0.1:4174/api/evaluate | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404（B 是 POST /api/evaluate）
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/evaluate -ContentType "application/json" -Body '{"environment":"prod"}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：含 releaseId，只能看到完整旧 release 或完整新 release
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/releases/publish -ContentType "application/json" -Body '{"flags":[{"id":"alpha"}],"flagIds":["alpha"],"environment":"prod","note":"partial"}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：422 validation_failed（只发 alpha 时依赖闭包缺 beta），或成员仅等于勾选集合
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 1、3、4、6 步。

---

## 第 286 题　Bug 修复　·　困难　·　全栈
<!-- solo-report:task=286 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/flag-segment-cache-web　A 分支：https://github.com/gy-vs/flag-segment-cache-web/tree/A　B 分支：https://github.com/gy-vs/flag-segment-cache-web/tree/B

服务：`npm run dev` 同时起后端 4174 与前端 4173；浏览器开 http://localhost:4173（被占用会自动 +1，以新窗口打出的 Local: 地址为准）。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/flag-segment-cache-web.git flag-segment-cache-web-A
cd flag-segment-cache-web-A
npm ci
npm test                                                       # 预期：观察 vitest 末行 passed 数（材料写 10+ 集成用例）
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                              # 浏览器打开后按下面「界面操作」走
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/flags/alpha/evaluate -ContentType "application/json" -Body '{"userId":"user-1","attributes":{"country":"US","plan":"beta"}}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：value=true，cache.status 为 miss 或 hit，带 cache.version
try { Invoke-RestMethod 'http://127.0.0.1:4174/api/evaluate?segmentId=seg-canary&userId=u1' } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404（A 评估走 POST /api/flags/:id/evaluate）
try { Invoke-RestMethod -Method Put -Uri http://127.0.0.1:4174/api/segments/seg-us -ContentType "application/json" -Body '{"revision":2,"rules":[{"type":"segment","segmentId":"seg-us"}]}' } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：422，error=segment_cycle
Invoke-RestMethod http://127.0.0.1:4174/api/cache/stats | ConvertTo-Json -Compress   # 预期：含 size、hits、misses、computes；更新分群后旧条目仍占容量
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:4173。A：顶栏「Feature Evaluation Lab」，左栏「Flags」和「Segments」；B：顶栏「特性规则工作台 · 分群依赖缓存」，左栏「共享分群」和「用户」。
2. A 左栏 Flags 选 alpha，在 Evaluate 的「User」填 `user-1`，「Attributes」保持 `{"country":"US","plan":"beta"}`，点「Evaluate」。右侧 Cache 卡片显示 MISS 与 version。B：选 seg-canary 与 u1，点「评估命中」，检查面板显示来源为首次计算及「命中的缓存版本」。
3. 再点一次「Evaluate」（B 侧再点「评估命中」）。A：Cache 变成 HIT 且 version 不变；B：来源变为缓存命中，缓存版本不变。
4. A 左栏 Segments 选 seg-us，把规则 JSON 里 country 从 US 改成 CA，点「Save」；状态出现 `Saved — invalidated: …`。B：在 aria-label「Segment rule」里改 terms 后点「保存规则」，状态给出新 revision 与失效条数。
5. 回到 alpha / seg-canary 再评估。A：又是 MISS、version 不同、value 变为 false；但旧缓存条目并未真正删除，只是换键后不可达。B：缓存版本变成新身份且来源回到首次计算；切到未受影响的分群评估仍是缓存命中。
6. A 仍可点「Analyze」；B 页面没有 Analyze 入口。把 include 改成指向自身再保存：A 状态 `Rejected: segment_cycle`；B 状态 `编译拒绝：…` 并带环路径。
7. 回到终端执行剩下的接口命令并 `taskkill`。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/flag-segment-cache-web.git flag-segment-cache-web-B
cd flag-segment-cache-web-B
npm ci
npm test                                                       # 预期：11 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                              # 浏览器打开后按下面「界面操作」走
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/flags/alpha/evaluate -ContentType "application/json" -Body '{"userId":"user-1","attributes":{"country":"US","plan":"beta"}}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
try { Invoke-RestMethod 'http://127.0.0.1:4174/api/evaluate?segmentId=seg-canary&userId=u1' } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：含 match、source、cacheVersion（闭包内容身份）
try { Invoke-RestMethod -Method Put -Uri http://127.0.0.1:4174/api/segments/seg-us -ContentType "application/json" -Body '{"revision":2,"rules":[{"type":"segment","segmentId":"seg-us"}]}' } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404（B 无 seg-us；循环写入走 400 compile_rejected）
Invoke-RestMethod http://127.0.0.1:4174/api/cache/stats | ConvertTo-Json -Compress   # 预期：404（B 是 GET /api/cache）
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 1、2、5、6 步。

---

## 第 287 题　Feature 迭代　·　困难　·　全栈
<!-- solo-report:task=287 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/flag-offline-snapshot-web　A 分支：https://github.com/gy-vs/flag-offline-snapshot-web/tree/A　B 分支：https://github.com/gy-vs/flag-offline-snapshot-web/tree/B

服务：`npm run dev` 同时起后端 4174 与前端 4173；浏览器开 http://localhost:4173（被占用会自动 +1，以新窗口打出的 Local: 地址为准）。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/flag-offline-snapshot-web.git flag-offline-snapshot-web-A
cd flag-offline-snapshot-web-A
npm ci
npm test                                                       # 预期：20 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                              # 浏览器打开后按下面「界面操作」走
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/releases/rel-2026.09/exports | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：202，含 taskId
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/workbench/releases/rel-prod/snapshots -ContentType "application/json" -Body '{}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
try { Invoke-RestMethod -Method Delete -Uri http://127.0.0.1:4174/api/cohorts/beta-testers } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：409，error=cohort_in_use
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:4173，看到顶栏「Feature Evaluation Lab」。A：主界面下方就是导出面板（中文文案）；B：顶栏有「Rules」和「Offline export」，需先点「Offline export」。
2. A 在 Release 导出卡片选 `rel-2026.09`，点「导出快照」；再改一次规则内容后重复导出，得到两个快照。B：点「Export snapshot」至少两次（可先改 format v1/v2）。
3. 选基线与目标，A 点「生成增量」，界面显示全量与增量体积对比（delta / full）。B 填 Baseline seq / Target seq 后点「Generate delta」。
4. A 点「模拟应用」，看校验通过或失败提示；失败时原快照保持不变。B 点「Simulate apply」，故障注入下拉里可选手截断 / 错误基线。
5. 再点一次应用。A：第二次会被基线检查拒绝，already_applied / baseline_mismatch，首次结果不受影响。B：点「Apply again (idempotency)」仍复用 simulateApply，每次重新拉基线再应用，already_applied 分支走不到，看到的仍像首次应用。
6. 生成过程中 A 点任务行内「取消」；B 点「Cancel」。切换基线或目标后，A 用序号闸门丢掉旧任务结果；B 旧任务也可能被 superseded。
7. 回到终端执行剩下的接口命令并 `taskkill`。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/flag-offline-snapshot-web.git flag-offline-snapshot-web-B
cd flag-offline-snapshot-web-B
npm ci
npm test                                                       # 预期：观察是否全绿（轨迹称 workbench-api 未稳定通过；交付材料写 27）
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                              # 浏览器打开后按下面「界面操作」走
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/releases/rel-2026.09/exports | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/workbench/releases/rel-prod/snapshots -ContentType "application/json" -Body '{}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：201，含 envelope.sequence 与 rootDigest
try { Invoke-RestMethod -Method Delete -Uri http://127.0.0.1:4174/api/cohorts/beta-testers } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404（B 删除被引用分群走草稿 PUT，导出会 409 reference_broken）
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 1、5 步。

---

## 第 289 题　Feature 迭代　·　困难　·　全栈
<!-- solo-report:task=289 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/tz-bundle-diff-web　A 分支：https://github.com/gy-vs/tz-bundle-diff-web/tree/A　B 分支：https://github.com/gy-vs/tz-bundle-diff-web/tree/B

服务：`npm run dev` 同时起后端 4174 与前端 4173；浏览器开 http://localhost:4173。被占用会自动 +1，以新窗口打出的 Local: 地址为准。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/tz-bundle-diff-web.git tz-bundle-diff-web-A
cd tz-bundle-diff-web-A
npm ci
npm test                                                       # 预期：31 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/fixtures | Out-Null; break } catch { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { Start-Sleep -Seconds 1 } } }
Start-Process http://localhost:4173                              # 浏览器打开后按下面「界面操作」走
Invoke-RestMethod http://127.0.0.1:4174/api/fixtures | ConvertTo-Json -Compress   # 预期：{"names":["old","new"],"largeSizes":[1000,10000]}
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/diff -ContentType "application/json" -Body '{"a":{"version":"x","zones":[{"name":"Z","initialOffsetSec":0,"transitions":[]}],"links":[{"name":"L1","target":"L2"},{"name":"L2","target":"L1"}]},"b":{"version":"y","zones":[{"name":"Z","initialOffsetSec":0,"transitions":[]},{"name":"N","initialOffsetSec":0,"transitions":[]}],"links":[{"name":"L1","target":"L2"},{"name":"L2","target":"L1"}]}}' | ConvertTo-Json -Compress   # 预期：summary.zonesAdded 为 1；两侧同一 link 环不计入 aliasCycles（为 0）
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/compare -ContentType "application/json" -Body '{"leftId":"alpha","rightId":"beta","now":1790290800}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404（A 没有 /api/compare）
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:4173，顶栏看到「Timezone Data Workbench」。A：Bundle A / Bundle B 下拉会自动载入 `old` 与 `new`；B：标题是「Timezone Data Studio」，左栏是 Left / Right 选 `alpha` / `beta`。
2. 点击「Compare」。A：出现汇总卡片 zones added / aliases retargeted / alias cycles 等，默认停在 Differences 页；B：中栏出现分类 chip（Added / Link cycle / Dangling link 等）与可展开差异行，状态从 Comparing 回到 Ready。
3. 点「Zone catalog」。A：列表一直是空的（`lastVisible` 依赖尚未返回的 total，取页循环进不去）；B：没有 Zone catalog 页，差异行本身就是虚拟列表。
4. 回到 Differences，展开某个 zone 后再在筛选框输入不匹配的关键字。A：展开集合按 zone 名保存在筛选外，切回仍展开；B：在「Filter zones…」里筛，已展开行不会被收起。
5. 点「Sample conversions」（A）或查看右栏 Sample conversions（B），用默认样例再点 Compare / Convert。A：两版数据共用同一 disambiguation；B：可改 Gap / Overlap 策略后再 Compare。
6. 回到终端执行剩下的接口命令并 `taskkill`。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/tz-bundle-diff-web.git tz-bundle-diff-web-B
cd tz-bundle-diff-web-B
npm ci
npm test                                                       # 预期：21 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/fixtures | Out-Null; break } catch { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { Start-Sleep -Seconds 1 } } }
Start-Process http://localhost:4173                              # 浏览器打开后按下面「界面操作」走
try { Invoke-RestMethod http://127.0.0.1:4174/api/fixtures | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404（B 没有 /api/fixtures）
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/diff -ContentType "application/json" -Body '{"a":{"version":"x","zones":[{"name":"Z","initialOffsetSec":0,"transitions":[]}],"links":[{"name":"L1","target":"L2"},{"name":"L2","target":"L1"}]},"b":{"version":"y","zones":[{"name":"Z","initialOffsetSec":0,"transitions":[]},{"name":"N","initialOffsetSec":0,"transitions":[]}],"links":[{"name":"L1","target":"L2"},{"name":"L2","target":"L1"}]}}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404（B 走 /api/compare）
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/compare -ContentType "application/json" -Body '{"leftId":"alpha","rightId":"beta","now":1790290800}' | ConvertTo-Json -Compress   # 预期：diff.summary.alias_retargeted 为 1、cycle 为 2（两侧相同的环也计入明细）
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 1、3、4、5 步。

---

## 第 290 题　Bug 修复　·　困难　·　全栈
<!-- solo-report:task=290 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/tz-local-gap-web　A 分支：https://github.com/gy-vs/tz-local-gap-web/tree/A　B 分支：https://github.com/gy-vs/tz-local-gap-web/tree/B

服务：`npm run dev` 同时起后端 4174 与前端 4173；浏览器开 http://localhost:4173。被占用会自动 +1，以新窗口打出的 Local: 地址为准。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/tz-local-gap-web.git tz-local-gap-web-A
cd tz-local-gap-web-A
npm ci
npm test                                                       # 预期：28 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                              # 浏览器打开后按下面「界面操作」走
(Invoke-RestMethod http://127.0.0.1:4174/api/bundles/alpha/zones).zones.name   # 预期：Demo/East Demo/Half Demo/Neg Demo/Fixed
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/bundles/alpha/resolve -ContentType "application/json" -Body '{"zone":"Demo/East","local":"2024-03-10 02:30:00","policy":"compatible"}' | ConvertTo-Json -Compress   # 预期：result.kind 为 gap，resolved.instant 为 2024-03-10T07:30:00Z，candidates 2 条
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/bundles/alpha/resolve -ContentType "application/json" -Body '{"zone":"Demo/Neg","local":"2024-03-31T01:30:00","policy":"later"}' | ConvertTo-Json -Compress   # 预期：kind 为 overlap（真负 DST，春季回拨）
try { Invoke-RestMethod http://127.0.0.1:4174/api/convert?bundle=alpha"&"zone=Alpha/OneHour"&"local=2024-03-31T02:30"&"policy=compatible } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404（A 没有 GET /api/convert）
try { Invoke-RestMethod -Method Put -Uri http://127.0.0.1:4174/api/bundles/alpha -ContentType "application/json" -Body '{"revision":3,"content":"not-a-bundle"}' } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：422 invalid_bundle，revision 不变
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:4173，顶栏「时区数据工作台」。左栏选 Primary timezone bundles（alpha）。A：Zone 下拉是 Demo/East / Demo/Half / Demo/Neg / Demo/Fixed；B：标题是 Timezone Data Studio，Zone 是 Alpha/OneHour / Alpha/Fixed。
2. Zone 选 Demo/East，本地墙钟时间填 `2024-03-10T02:30:00`，策略选「兼容 compatible」，点击「解析候选」。A：徽章「间隙 gap（时间不存在）」，「前边界（旧读数最后一刻）」本地 `2024-03-10T02:00:00`，候选带依据；B：按钮是「转换」，默认本地时间是 `2024-03-31T02:30`，没有 Demo/East。
3. 本地时间改成 `2024-11-03T01:30:00`，策略改「拒绝 reject」再解析。A：重叠 overlap，两个候选 instant 升序 `2024-11-03T05:30:00Z` / `2024-11-03T06:30:00Z`，reject 不给 instant；B：用 Alpha/OneHour 的 `2024-10-27T02:30` 看 overlap。
4. Zone 换 Demo/Neg，本地 `2024-03-31T01:30:00`，策略「较晚 later」。A：春季是 overlap（夏季偏移更小的真负 DST）；B：切到 beta 的 Beta/Negative，`2024-10-06T01:30` 得到的是 gap（负偏移时区的常规夏令时，不是负 DST）。
5. 中间文本框改成非法内容，点「保存（revision 递增）」。A：状态「保存被拒：invalid_bundle」；B：按钮是「Save」，任意内容都能保存，revision 递增。
6. 回到终端执行剩下的接口命令并 `taskkill`。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/tz-local-gap-web.git tz-local-gap-web-B
cd tz-local-gap-web-B
npm ci
npm test                                                       # 预期：19 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                              # 浏览器打开后按下面「界面操作」走
(Invoke-RestMethod http://127.0.0.1:4174/api/bundles/alpha/zones).zones.name   # 预期：Alpha/OneHour Alpha/Fixed
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/bundles/alpha/resolve -ContentType "application/json" -Body '{"zone":"Demo/East","local":"2024-03-10 02:30:00","policy":"compatible"}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404（B 走 GET /api/convert）
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/bundles/alpha/resolve -ContentType "application/json" -Body '{"zone":"Demo/Neg","local":"2024-03-31T01:30:00","policy":"later"}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
Invoke-RestMethod http://127.0.0.1:4174/api/convert?bundle=alpha"&"zone=Alpha/OneHour"&"local=2024-03-31T02:30"&"policy=compatible | ConvertTo-Json -Compress   # 预期：kind 为 gap，gap.startLocal 为 2024-03-31T02:00，compatible 解析为 2024-03-31T01:30Z
Invoke-RestMethod -Method Put -Uri http://127.0.0.1:4174/api/bundles/alpha -ContentType "application/json" -Body '{"revision":3,"content":"not-a-bundle"}' | ConvertTo-Json -Compress   # 预期：200，revision 变成 4（不校验 bundle 文本）
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 1、2、4、5 步。

---

## 第 291 题　Feature 迭代　·　困难　·　全栈
<!-- solo-report:task=291 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/tz-patch-publish-web　A 分支：https://github.com/gy-vs/tz-patch-publish-web/tree/A　B 分支：https://github.com/gy-vs/tz-patch-publish-web/tree/B

服务：`npm run dev` 同时起后端 4174 与前端 4173；浏览器开 http://localhost:4173。被占用会自动 +1，以新窗口打出的 Local: 地址为准。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/tz-patch-publish-web.git tz-patch-publish-web-A
cd tz-patch-publish-web-A
npm ci
npm test                                                       # 预期：14 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { try { Invoke-RestMethod http://127.0.0.1:4174/api/head | Out-Null; break } catch { Start-Sleep -Seconds 1 } } }
Start-Process http://localhost:4173                              # 浏览器打开后按下面「界面操作」走
Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | ConvertTo-Json -Compress   # 预期：{"family":"timezone-bundle","count":2}
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/bundles/alpha/validate -ContentType "application/json" -Body '{"ops":[{"kind":"insertTransition","zone":"Alpha","transition":{"at":1500,"offsetSeconds":-9000,"abbrevIndex":9}}]}' | ConvertTo-Json -Compress   # 预期：valid 为 false，错误含缩写索引越界
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/bundles/alpha/publish -ContentType "application/json" -Body '{"baseRevision":1,"ops":[{"kind":"insertTransition","zone":"Alpha","transition":{"at":1500,"offsetSeconds":-9000,"abbrevIndex":1}}],"simulateCrash":true}' } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：500，body 含 publish_crashed 与 rolledBack true，revision 仍为 1
try { Invoke-RestMethod http://127.0.0.1:4174/api/head | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404（A 没有 /api/head）
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:4173，顶栏「Timezone Data Studio」。A：左栏 Bundles 选 Primary timezone bundles，看到 zone Alpha / Beta 与 link AlphaAlias；B：没有 bundle 列表，直接显示当前 head 快照（America/New_York 等）。
2. 在「at」填 `1500`、「offset 秒」填 `-10800`、「缩写索引」填 `1`，点击「插入过渡」，草稿出现一行。再点「验证」。A：验证报告「通过」或列出样例影响表，状态「验证完成」；B：按钮是「Stage operation」+「Validate」。
3. 把缩写索引改成 `9` 再插入并验证。A：未通过，错误含 abbrevIndex 越界，点「发布新 revision」会 422 且 revision 不变；B：abbrev index 填 `99` 后 Validate 得到 `invalid-abbrev-index`，Publish 422。
4. 用合法操作点「发布新 revision」成功一次后，再带过期基线发布一次做出 409。A：出现「重放不相交操作」，点下去仍带旧 `bundle.revision`，回来还是 revision_conflict；B：点「Replay disjoint ops onto new base」会把 baseSummary 换成 `conflict.current.id`，再 Publish 可以过。
5. A：崩溃只能靠接口 `simulateCrash`（界面无按钮），进程内存里历史在重启后消失；B：点「Crash sim」，head 不前移，重启后孤儿 revision 被清理。
6. 回到终端执行剩下的接口命令并 `taskkill`。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/tz-patch-publish-web.git tz-patch-publish-web-B
cd tz-patch-publish-web-B
npm ci
npm test                                                       # 预期：24 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 timezone workbench api http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { try { Invoke-RestMethod http://127.0.0.1:4174/api/head | Out-Null; break } catch { Start-Sleep -Seconds 1 } } }
Start-Process http://localhost:4173                              # 浏览器打开后按下面「界面操作」走
try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404（B 用 GET /api/head）
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/bundles/alpha/validate -ContentType "application/json" -Body '{"ops":[{"kind":"insertTransition","zone":"Alpha","transition":{"at":1500,"offsetSeconds":-9000,"abbrevIndex":9}}]}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/bundles/alpha/publish -ContentType "application/json" -Body '{"baseRevision":1,"ops":[{"kind":"insertTransition","zone":"Alpha","transition":{"at":1500,"offsetSeconds":-9000,"abbrevIndex":1}}],"simulateCrash":true}' } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
Invoke-RestMethod http://127.0.0.1:4174/api/head | ConvertTo-Json -Compress   # 预期：revision 为 0，含 America/New_York 与 summary 摘要
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 1、2、4、5 步。

---

## 第 292 题　Bug 修复　·　困难　·　全栈
<!-- solo-report:task=292 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/tz-posix-rule-web　A 分支：https://github.com/gy-vs/tz-posix-rule-web/tree/A　B 分支：https://github.com/gy-vs/tz-posix-rule-web/tree/B

服务：`npm run dev` 同时起后端 4174 与前端 4173；浏览器开 http://localhost:4173。被占用会自动 +1，以新窗口打出的 Local: 地址为准。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/tz-posix-rule-web.git tz-posix-rule-web-A
cd tz-posix-rule-web-A
npm ci
npm test                                                       # 预期：27 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                              # 浏览器打开后按下面「界面操作」走
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/posix/expand -ContentType "application/json" -Body '{"tz":"AEST-10AEDT,M10.1.0,M4.1.0","start":"2024-01-01T00:00:00Z","end":"2025-01-01T00:00:00Z"}' | ConvertTo-Json -Compress   # 预期：initial.dst 为 true、offsetSeconds 39600，transitions 的 utcText 为 2024-04-06T15:00:00Z 与 2024-10-05T16:00:00Z
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/posix/expand -ContentType "application/json" -Body '{"tz":"EST25","startSeconds":0,"endSeconds":10}' } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：400，error 为 invalid_tz_rule，message 含「偏移」
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/tz/explain -ContentType "application/json" -Body '{"rule":"AEST-10AEDT-11,M10.1.0,M4.1.0"}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404（A 走 /api/posix/expand）
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:4173。A：默认就在顶部「POSIX TZ 规则」标签，TZ 字符串默认 `AEST-10AEDT,M10.1.0,M4.1.0`；B：先看到原有 bundle 工作区，POSIX 区块在下方，默认预设是 `AEST-10AEDT-11,M10.1.0,M4.1.0`。
2. UTC 区间起止保持 `2024-01-01T00:00:00Z` ～ `2025-01-01T00:00:00Z`，点击「展开过渡」。A：AST 标准名 AEST，区间起点是 DST（+11），过渡表两行 4 月结束 / 10 月开始，「规则展开依据」含同一状态机；B：按钮是「Explain rule」和「Expand interval」。
3. 点预设「澳大利亚东部 AEST-10（南半球跨年）」再展开。A：名称后省略 DST 偏移，按标准+1h，结果仍跨年正确；B：默认带 `-11`，点 Explain rule 应看到 dst true、standard +10:00、daylight +11:00、2024 年 start 落在 10-06、end 落在 04-07。
4. 点「J 日 + 负时刻」或把规则改成含 `J60` 的形式再展开。A：notes 写明 Jn 不计 2 月 29 日、闰年 3 月起顺延；B：逐年表格给出各年 civilDate。
5. 把 TZ 改成非法 `EST25` 再展开。A：页面错误区出现中文诊断（偏移）；B：Explain / Expand 走 400 分支。
6. A 可切到「数据 bundles」回到原工作区；B 的 Save / Analyze 一直留在上半页。回到终端执行剩下的接口命令并 `taskkill`。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/tz-posix-rule-web.git tz-posix-rule-web-B
cd tz-posix-rule-web-B
npm ci
npm test                                                       # 预期：观察 passed 数（GSB 称交付时默认预设曾 400；当前代码 /api/tz/explain 对 AEST-10AEDT-11 返回 200）
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm run dev"   # 新窗口打出 server http://127.0.0.1:4174 与 Local: http://localhost:4173/
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:4174/api/bootstrap | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:4173                              # 浏览器打开后按下面「界面操作」走
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/posix/expand -ContentType "application/json" -Body '{"tz":"AEST-10AEDT,M10.1.0,M4.1.0","start":"2024-01-01T00:00:00Z","end":"2025-01-01T00:00:00Z"}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404（B 走 /api/tz/explain 与 /api/tz/expand）
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/posix/expand -ContentType "application/json" -Body '{"tz":"EST25","startSeconds":0,"endSeconds":10}' } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:4174/api/tz/explain -ContentType "application/json" -Body '{"rule":"AEST-10AEDT-11,M10.1.0,M4.1.0"}' | ConvertTo-Json -Compress   # 预期：200，dst true，standard.offset 为 +10:00，daylight.offset 为 +11:00
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 1、2、3 步。

---

## 第 295 题　Feature 迭代　·　困难　·　无界面
<!-- solo-report:task=295 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/ws-extension-negotiate-core　A 分支：https://github.com/gy-vs/ws-extension-negotiate-core/tree/A　B 分支：https://github.com/gy-vs/ws-extension-negotiate-core/tree/B

存为 `verify_ext.mjs`（放在仓库根目录）

```javascript
import * as m from './dist/index.js'

function catcher(label, fn) {
  return Promise.resolve()
    .then(fn)
    .then((v) => console.log(label, v))
    .catch((e) => console.log(label, e && e.name, String(e && e.message || e).split('\n')[0]))
}

const buf = new Uint8Array(5)
buf[0] = 0x81
buf[1] = 126
buf[2] = 0
buf[3] = 1
buf[4] = 65
const ext = m.decodeFrame(buf)
console.log('ext-len', ext == null ? 'null' : ext.payload.length + ':' + ext.payload[0])

const tiny = m.decodeFrame(Uint8Array.from([0x81, 0x01, 65]))
console.log('rsv1', tiny && tiny.rsv1, 'rsv2', tiny && tiny.rsv2, 'rsv3', tiny && tiny.rsv3)

const header = 'PerMessage-Deflate; server_no_context_takeover; client_max_window_bits="15", unknown-x'
await catcher('parse', () => {
  if (m.parseExtensionsHeader) {
    const els = m.parseExtensionsHeader(header)
    return els.map((e) => e.name + ':' + e.parameters.map((p) => p.name + '=' + p.value).join(';')).join(' | ')
  }
  const els = m.parseOfferHeader(header)
  return els.map((e) => e.name + ':' + e.params.map((p) => p.name + '=' + p.value).join(';')).join(' | ')
})

await catcher('dup-param', () => {
  const h = 'permessage-deflate; server_no_context_takeover; server_no_context_takeover'
  if (m.negotiateFromHeader) {
    const r = m.negotiateFromHeader(h)
    return r == null ? 'null' : (r.responseHeader || JSON.stringify(r))
  }
  const n = new m.ExtensionNegotiator()
  n.register(m.permessageDeflateDefinition)
  const r = n.negotiate(h)
  return JSON.stringify({ negotiated: r.negotiated, header: r.header })
})

await catcher('ctrl-rsv1', async () => {
  if (m.MessageReceiver) {
    const conn = new m.ConnectionState()
    const rec = new m.MessageReceiver(conn, null)
    try {
      await rec.acceptFrame({ fin: true, opcode: 9, rsv1: true, rsv2: false, rsv3: false, payload: new Uint8Array() })
      return 'accepted state=' + conn.state
    } catch (e) {
      return e.name + ' state=' + conn.state
    }
  }
  const f = { fin: true, opcode: 9, rsv1: true, payload: new Uint8Array() }
  return 'rsv1-optional=' + (f.rsv1 === true)
})
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/ws-extension-negotiate-core.git ws-extension-negotiate-core-A
cd ws-extension-negotiate-core-A
npm ci
npm run build
npx vitest run   # 预期：58 passed
node verify_ext.mjs   # 预期：ext-len null ；rsv1 false rsv2 false rsv3 false ；parse permessage-deflate:... | unknown-x: ；dup-param null ；ctrl-rsv1 WebSocketProtocolError state=closing
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/ws-extension-negotiate-core.git ws-extension-negotiate-core-B
cd ws-extension-negotiate-core-B
npm ci
npm run build
npx vitest run   # 预期：4 failed | 70 passed
node verify_ext.mjs   # 预期：ext-len 1:65 ；rsv1 false rsv2 false rsv3 false ；parse PerMessage-Deflate:... | unknown-x: ；dup-param ExtensionError parameter "server_no_context_takeover" is repeated ；ctrl-rsv1 rsv1-optional=true
cd ..
```

---

## 第 299 题　Feature 迭代　·　困难　·　无界面
<!-- solo-report:task=299 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/zip-stream-descriptor-core　A 分支：https://github.com/gy-vs/zip-stream-descriptor-core/tree/A　B 分支：https://github.com/gy-vs/zip-stream-descriptor-core/tree/B

存为 `verify_zip.mjs`（放在仓库根目录）

```javascript
import * as m from './dist/index.js'

async function* boom() {
  yield new Uint8Array([1, 2, 3])
  throw new Error('source-fail')
}

async function writeArchive(limit, body, methodStore) {
  const chunks = []
  const sink = { write(c) { chunks.push(Buffer.from(c)) } }
  let zip64
  if (m.ZipWriter) {
    const w = new m.ZipWriter(sink, { zip64Threshold: limit })
    const rec = await w.addEntry({
      name: 'a.txt',
      method: methodStore ? 'store' : 'deflate',
      source: [body],
    })
    zip64 = rec.zip64
    await w.finish()
  } else {
    const w = new m.StreamingZipWriter({ zipSink: sink, zip64SizeLimit: limit })
    const rec = await w.addEntry('a.txt', [body], { method: methodStore ? 'stored' : 'deflated' })
    zip64 = rec.zip64
    await w.finish()
  }
  const buf = Buffer.concat(chunks)
  return { zip64, len: buf.length, hasDescSig: buf.includes(Buffer.from([0x50, 0x4b, 0x07, 0x08])), hasEocd: buf.includes(Buffer.from([0x50, 0x4b, 0x05, 0x06])) }
}

const four = new Uint8Array(4).fill(65)
const r1 = await writeArchive(4n, four, true)
console.log('zip64-eq-limit', r1.zip64, 'desc', r1.hasDescSig, 'eocd', r1.hasEocd, 'len', r1.len)

const empty = new Uint8Array(0)
const r0 = await writeArchive(0xffffffffn, empty, true)
console.log('empty-store', r0.zip64, 'desc', r0.hasDescSig, 'eocd', r0.hasEocd)

const chunks = []
const sink = { write(c) { chunks.push(Buffer.from(c)) } }
try {
  if (m.ZipWriter) {
    const w = new m.ZipWriter(sink)
    try {
      await w.addEntry({ name: 'x.txt', method: 'store', source: boom() })
      console.log('src-fail', 'no-throw')
    } catch (e) {
      console.log('src-fail', e.name, String(e.message).slice(0, 60))
    }
    try {
      await w.finish()
      console.log('finish-after-fail', 'ok', Buffer.concat(chunks).includes(Buffer.from([0x50, 0x4b, 0x05, 0x06])))
    } catch (e) {
      console.log('finish-after-fail', e.name, String(e.message).slice(0, 80))
    }
  } else {
    const w = new m.StreamingZipWriter({ zipSink: sink })
    try {
      await w.addEntry('x.txt', boom(), { method: 'stored' })
      console.log('src-fail', 'no-throw')
    } catch (e) {
      console.log('src-fail', e.name, String(e.message).slice(0, 60))
    }
    try {
      await w.finish()
      console.log('finish-after-fail', 'ok', Buffer.concat(chunks).includes(Buffer.from([0x50, 0x4b, 0x05, 0x06])))
    } catch (e) {
      console.log('finish-after-fail', e.name, String(e.message).slice(0, 80))
    }
  }
} catch (e) {
  console.log('fail-flow', e.name, String(e.message).slice(0, 80))
}

const round = new TextEncoder().encode('hello zip')
const built = await writeArchive(0xffffffffn, round, true)
console.log('roundtrip-bytes', built.len, 'eocd', built.hasEocd)
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/zip-stream-descriptor-core.git zip-stream-descriptor-core-A
cd zip-stream-descriptor-core-A
npm ci
npm run build
npx vitest run   # 预期：18 passed
node verify_zip.mjs   # 预期：zip64-eq-limit true desc true eocd true len 232 ；empty-store false desc true eocd true ；src-fail Error source-fail ；finish-after-fail ZipWriterError archive cannot be finished: a previous entry failed or was cancelled; refusing t ；roundtrip-bytes 133 eocd true
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/zip-stream-descriptor-core.git zip-stream-descriptor-core-B
cd zip-stream-descriptor-core-B
npm ci
npm run build
npx vitest run   # 预期：24 passed
node verify_zip.mjs   # 预期：zip64-eq-limit false desc true eocd true len 204 ；empty-store false desc true eocd true ；src-fail ZipWriterError entry "x.txt" failed; archive cannot be completed ；finish-after-fail ZipWriterError cannot finish: archive is unfinishable after a previous failure or abort ；roundtrip-bytes 133 eocd true
cd ..
```

---

## 第 301 题　Feature 迭代　·　困难　·　无界面
<!-- solo-report:task=301 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/zip-encrypted-entry-core　A 分支：https://github.com/gy-vs/zip-encrypted-entry-core/tree/A　B 分支：https://github.com/gy-vs/zip-encrypted-entry-core/tree/B

存为 `verify_aes.mjs`（放在仓库根目录）

```javascript
import { createCipheriv, createHmac, pbkdf2Sync } from 'node:crypto'
import * as m from './dist/index.js'

function encryptWinZip(plaintext, password, { strength = 3, version = 1, iterations = 1000, salt } = {}) {
  const keyLength = { 1: 16, 2: 24, 3: 32 }[strength]
  const saltLength = { 1: 8, 2: 12, 3: 16 }[strength]
  const saltBuf = salt ?? Buffer.alloc(saltLength, 7)
  const passwordBytes = Buffer.from(password, 'utf8')
  const derived = pbkdf2Sync(passwordBytes, saltBuf, iterations, 2 * keyLength + 2, 'sha1')
  const encryptionKey = derived.subarray(0, keyLength)
  const authenticationKey = derived.subarray(keyLength, 2 * keyLength)
  const verifier = derived.subarray(2 * keyLength)
  const cipher = createCipheriv('aes-' + keyLength * 8 + '-ecb', encryptionKey, null)
  cipher.setAutoPadding(false)
  const ciphertext = Buffer.allocUnsafe(plaintext.length)
  for (let offset = 0, counter = 1n; offset < plaintext.length; offset += 16, counter++) {
    const block = Buffer.alloc(16)
    let c = counter
    for (let i = 0; i < 16; i++) {
      block[i] = Number(c & 0xffn)
      c >>= 8n
    }
    const keystream = cipher.update(block)
    const n = Math.min(16, plaintext.length - offset)
    for (let i = 0; i < n; i++) ciphertext[offset + i] = plaintext[offset + i] ^ keystream[i]
  }
  const authCode = createHmac('sha1', authenticationKey).update(ciphertext).digest().subarray(0, 10)
  const payload = Buffer.concat([saltBuf, verifier, ciphertext, authCode])
  const extra = new Uint8Array(11)
  extra[0] = 0x01
  extra[1] = 0x99
  extra[2] = 7
  extra[3] = 0
  extra[4] = version
  extra[5] = 0
  extra[6] = 0x41
  extra[7] = 0x45
  extra[8] = strength
  extra[9] = 0
  extra[10] = 0
  return { payload, extra }
}

const plain = Buffer.from('hello-aes')
const vec = encryptWinZip(plain, 'secret', { strength: 3, version: 1, salt: Buffer.alloc(16, 7) })

try {
  if (m.decryptEntryToBytes) {
    const text = Buffer.from(
      await m.decryptEntryToBytes(
        { name: 'a.txt', extra: vec.extra, encrypted: true },
        vec.payload,
        { password: () => 'secret', pbkdf2Iterations: 1000 },
      ),
    ).toString('utf8')
    console.log('good-pw', text)
  } else {
    const text = Buffer.from(
      await m.decryptEntryBytes(
        { name: 'a.txt', size: 0n, offset: 0n, extra: vec.extra, compressionMethod: 99 },
        vec.payload,
        { password: 'secret', params: { iterations: 1000 } },
      ),
    ).toString('utf8')
    console.log('good-pw', text)
  }
} catch (e) {
  console.log('good-pw', e.name, String(e.message).split('\n')[0])
}

try {
  if (m.decryptEntryToBytes) {
    await m.decryptEntryToBytes(
      { name: 'a.txt', extra: vec.extra, encrypted: true },
      vec.payload,
      { password: () => 'wrong', pbkdf2Iterations: 1000 },
    )
    console.log('bad-pw', 'no-throw')
  } else {
    await m.decryptEntryBytes(
      { name: 'a.txt', size: 0n, offset: 0n, extra: vec.extra, compressionMethod: 99 },
      vec.payload,
      { password: 'wrong', params: { iterations: 1000 } },
    )
    console.log('bad-pw', 'no-throw')
  }
} catch (e) {
  console.log('bad-pw', e.name, String(e.message).split('\n')[0], 'leaks', String(e.message).includes('wrong'))
}

try {
  if (m.decryptEntryToBytes) {
    await m.decryptEntryToBytes(
      { name: 'a.txt', extra: vec.extra, encrypted: true },
      vec.payload.subarray(0, 8),
      { password: () => 'secret', pbkdf2Iterations: 1000 },
    )
    console.log('trunc-salt', 'no-throw')
  } else {
    await m.decryptEntryBytes(
      { name: 'a.txt', size: 0n, offset: 0n, extra: vec.extra, compressionMethod: 99 },
      vec.payload.subarray(0, 8),
      { password: 'secret', params: { iterations: 1000 } },
    )
    console.log('trunc-salt', 'no-throw')
  }
} catch (e) {
  console.log('trunc-salt', e.name, String(e.message).split('\n')[0])
}

try {
  if (m.IterationLimitError || m.MAX_PBKDF2_ITERATIONS) {
    await m.decryptEntryToBytes(
      { name: 'a.txt', extra: vec.extra, encrypted: true },
      vec.payload,
      { password: () => 'secret', pbkdf2Iterations: 9e9 },
    )
    console.log('iter-cap', 'no-throw')
  } else {
    await m.decryptEntryBytes(
      { name: 'a.txt', size: 0n, offset: 0n, extra: vec.extra, compressionMethod: 99 },
      vec.payload,
      { password: 'secret', params: { iterations: 9e9, maxIterations: 1000 } },
    )
    console.log('iter-cap', 'no-throw')
  }
} catch (e) {
  console.log('iter-cap', e.name, String(e.message).split('\n')[0])
}
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/zip-encrypted-entry-core.git zip-encrypted-entry-core-A
cd zip-encrypted-entry-core-A
npm ci
npm run build
npx vitest run   # 预期：33 passed
node verify_aes.mjs   # 预期：good-pw hello-aes ；bad-pw PasswordVerificationError password verification failed leaks false ；trunc-salt MalformedEncryptedDataError truncated salt or password verifier ；iter-cap IterationLimitError PBKDF2 iteration count exceeds the limit of 1000000
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/zip-encrypted-entry-core.git zip-encrypted-entry-core-B
cd zip-encrypted-entry-core-B
npm ci
npm run build
npx vitest run   # 预期：49 passed
node verify_aes.mjs   # 预期：good-pw WrongPasswordError Password verification failed for entry "a.txt" ；bad-pw WrongPasswordError Password verification failed for entry "a.txt" leaks false ；trunc-salt ZipFormatError Encrypted entry is truncated: needed 8 more salt byte(s) ；iter-cap InvalidEncryptionOptionError PBKDF2 iteration count exceeds the configured limit of 1000
cd ..
```

---

## 第 307 题　Feature 迭代　·　困难　·　无界面
<!-- solo-report:task=307 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/jsonschema-output-format-core　A 分支：https://github.com/gy-vs/jsonschema-output-format-core/tree/A　B 分支：https://github.com/gy-vs/jsonschema-output-format-core/tree/B

存为 `verify_output.mjs`（放在仓库根目录）

```javascript
import * as m from './dist/index.js'

function out(r) {
  if (r && typeof r.toOutput === 'function') return r.toOutput.bind(r)
  return (fmt) => m.format(r, fmt)
}

const schema = { anyOf: [{ type: 'string' }, { type: 'number' }] }
const r = m.validate(schema, 'hi')
const fmt = out(r)
const flag = fmt('flag')
const basic = fmt('basic')
const detailed = fmt('detailed')
const verbose = fmt('verbose')
console.log('valids', flag.valid, basic.valid, detailed.valid, verbose.valid)

function countUnits(node) {
  if (!node || typeof node !== 'object') return 0
  let n = 1
  for (const k of ['errors', 'annotations']) {
    const arr = node[k]
    if (Array.isArray(arr)) for (const c of arr) n += countUnits(c)
  }
  return n
}
console.log('verbose-units', countUnits(verbose), 'has-ann', Array.isArray(verbose.annotations), 'has-err', Array.isArray(verbose.errors))

const frozen = Object.freeze({ a: 1 })
try {
  const fr = m.validate({ $ref: '#/$defs/n', $defs: { n: { type: 'object', properties: { a: { type: 'number' } } } } }, frozen)
  const f = out(fr)('flag')
  console.log('frozen', f.valid)
} catch (e) {
  console.log('frozen', e.name, String(e.message).split('\n')[0])
}

const ptr = m.validate({ properties: { 'a/b': { type: 'string' }, 'c~d': { type: 'number' } } }, { 'a/b': 'x', 'c~d': 1 })
const v2 = out(ptr)('verbose')
const dump = JSON.stringify(v2)
console.log('escaped', dump.includes('a~1b') || dump.includes('~1'), dump.includes('c~0d') || dump.includes('~0'))
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/jsonschema-output-format-core.git jsonschema-output-format-core-A
cd jsonschema-output-format-core-A
npm ci
npm run build
npx vitest run   # 预期：35 passed
node verify_output.mjs   # 预期：valids true true true true ；verbose-units 6 has-ann true has-err false ；frozen true ；escaped true true
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/jsonschema-output-format-core.git jsonschema-output-format-core-B
cd jsonschema-output-format-core-B
npm ci
npm run build
npx vitest run   # 预期：23 passed
node verify_output.mjs   # 预期：valids true true true true ；verbose-units 3 has-ann true has-err false ；frozen TypeError Cannot define property __visitId, object is not extensible ；escaped true true
cd ..
```

---

## 第 315 题　Feature 迭代　·　困难　·　无界面
<!-- solo-report:task=315 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/h2-priority-tree-core　A 分支：https://github.com/gy-vs/h2-priority-tree-core/tree/A　B 分支：https://github.com/gy-vs/h2-priority-tree-core/tree/B

存为 `verify_priority.mjs`（放在仓库根目录）

```javascript
import * as m from './dist/index.js'

const objectStyle = typeof m.clampWeight === 'function'
const tree = new m.PriorityTree()

function prio(id, dep, weight) {
  if (objectStyle) tree.reprioritize({ streamId: id, dependsOn: dep, weight: weight })
  else tree.reprioritize(id, dep, weight)
}

prio(1, 0, 16)
prio(3, 1, 16)
prio(5, 3, 16)
prio(1, 5, 16)
console.log('cycle-root', tree.childrenOf(0).join(','))
console.log('cycle-p1', tree.parentOf(1))
console.log('cycle-p3', tree.parentOf(3))
console.log('cycle-p5', tree.parentOf(5))

const s = new m.PriorityScheduler(0)
if (typeof s.open === 'function') s.open(1)
if (typeof s.queue === 'function') s.queue(1, 1000)
else if (typeof s.queueData === 'function') s.queueData(1, 1000)
if (objectStyle) console.log('pick-win0', s.pick())
else console.log('pick-win0', s.schedule())

const s2 = new m.PriorityScheduler()
s2.open(1)
s2.open(3)
if (objectStyle) {
  s2.setWeight(1, 1)
  s2.setWeight(3, 2)
  s2.queue(1, 100000)
  s2.queue(3, 100000)
} else {
  s2.priority(1, 0, 1)
  s2.priority(3, 0, 2)
  s2.queueData(1, 100000)
  s2.queueData(3, 100000)
}
const bytes = { 1: 0, 3: 0 }
const picks = { 1: 0, 3: 0 }
for (let i = 0; i < 60; i++) {
  let id
  let n
  if (objectStyle) {
    const p = s2.pick(1000)
    if (!p) break
    id = p.streamId
    n = id === 1 ? 10 : 100
    n = Math.min(n, p.budget)
    s2.sent(id, n)
  } else {
    const chosen = s2.schedule()
    if (chosen === null) break
    id = chosen
    n = id === 1 ? 10 : 100
    const t = s2.transmit(id, n)
    if (!t) break
    n = t.bytes
  }
  bytes[id] += n
  picks[id] += 1
}
console.log('bytes', bytes[1], bytes[3])
console.log('picks', picks[1], picks[3])
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/h2-priority-tree-core.git h2-priority-tree-core-A
cd h2-priority-tree-core-A
npm ci
npm run build
npx vitest run   # 预期：29 passed
node verify_priority.mjs   # 预期：cycle-root 3；cycle-p3 0；cycle-p5 3；pick-win0 null；bytes 490 1100；picks 49 11
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/h2-priority-tree-core.git h2-priority-tree-core-B
cd h2-priority-tree-core-B
npm ci
npm run build
npx vitest run   # 预期：35 passed
node verify_priority.mjs   # 预期：cycle-root 5；cycle-p3 1；cycle-p5 0；pick-win0 1；bytes 200 4000；picks 20 40
cd ..
```

---

## 第 322 题　Bug 修复　·　困难　·　无界面
<!-- solo-report:task=322 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/regex-step-budget-core　A 分支：https://github.com/gy-vs/regex-step-budget-core/tree/A　B 分支：https://github.com/gy-vs/regex-step-budget-core/tree/B

存为 `verify_budget.mjs`（放在仓库根目录）

```javascript
import * as m from './dist/index.js'

const Ex = m.RegexExecutor || m.RegexVM
const ex = new Ex()
const code = [
  { op: 'char', value: 'a' },
  { op: 'match' },
]

function runGlobal(limit) {
  if (typeof ex.matchAll === 'function') {
    const r = ex.matchAll({ code: code }, 'aaa', { limit: limit })
    return r.outcome + ' n=' + r.matches.length + ' steps=' + r.steps + ' live=' + ex.liveFrames
  }
  const r = ex.execResult({ code: code, global: true }, 'aaa', { limit: limit, global: true })
  const n = (r.matches || r.partialMatches || []).length
  return r.status + ' n=' + n + ' steps=' + r.used + ' depth=' + ex.frameDepth
}

console.log('global-limit2', runGlobal(2))
console.log('global-limit20', runGlobal(20))

if (typeof ex.exec === 'function') {
  const r = ex.exec({ code: [{ op: 'match' }] }, '', { limit: 1 })
  console.log('reuse', r.outcome, 'live', ex.liveFrames)
} else {
  const r = ex.execResult({ code: [{ op: 'match' }] }, '', { limit: 1 })
  console.log('reuse', r.status, 'depth', ex.frameDepth)
}

console.log('has-matchAll', typeof ex.matchAll)
console.log('has-execResult', typeof ex.execResult)
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/regex-step-budget-core.git regex-step-budget-core-A
cd regex-step-budget-core-A
npm ci
npm run build
npx vitest run   # 预期：24 passed
node verify_budget.mjs   # 预期：global-limit2 match n=3 steps=7 live=0；global-limit20 match n=3；reuse match live 0；has-matchAll function
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/regex-step-budget-core.git regex-step-budget-core-B
cd regex-step-budget-core-B
npm ci
npm run build
npx vitest run   # 预期：30 passed
node verify_budget.mjs   # 预期：global-limit2 limit n=1 steps=2 depth=0；global-limit20 match n=3 steps=7；reuse match depth 0；has-execResult function
cd ..
```

---

## 第 327 题　Feature 迭代　·　困难　·　无界面
<!-- solo-report:task=327 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/protobuf-json-mapping-core　A 分支：https://github.com/gy-vs/protobuf-json-mapping-core/tree/A　B 分支：https://github.com/gy-vs/protobuf-json-mapping-core/tree/B

存为 `verify_json.mjs`（放在仓库根目录）

```javascript
import * as m from './dist/index.js'

function dottedA() {
  const p = new m.DescriptorPool()
  p.addFile({
    name: 'w.proto',
    package: 'foo.bar',
    syntax: 'proto3',
    messages: [
      { kind: 'message', name: 'Inner', fields: [{ name: 'n', number: 1, type: 'int32' }] },
      { kind: 'message', name: 'Outer', fields: [{ name: 'inner', number: 1, type: 'Inner' }] },
    ],
  })
  const outer = p.findMessage('foo.bar.Outer')
  if (!outer) return 'missing'
  const f = outer.fields[0]
  return f.messageType ? f.messageType.fullName : ('unresolved:' + f.kind)
}

function dottedB() {
  const p = m.standardPool([{
    messages: [
      { name: '.foo.bar.Inner', fields: [{ name: 'n', number: 1, type: 'int32' }] },
      { name: '.foo.bar.Outer', fields: [{ name: 'inner', number: 1, type: 'message', typeName: '.foo.bar.Inner' }] },
    ],
  }])
  const outer = p.findMessage('.foo.bar.Outer')
  if (!outer) return 'missing'
  const f = outer.fields[0]
  return f.messageType ? f.messageType.fullName : ('unresolved:' + f.type)
}

try {
  if (typeof m.standardPool === 'function') console.log('dotted', dottedB())
  else console.log('dotted', dottedA())
} catch (e) {
  console.log('dotted', String(e.message).split('\n')[0])
}

try {
  if (typeof m.standardPool === 'function') {
    const p = m.standardPool()
    const url = 'type.googleapis.com/prefix/google.protobuf.Timestamp'
    const hit = p.resolveTypeUrl(url)
    console.log('typeurl', hit ? hit.fullName : 'undef')
  } else {
    const p = new m.DescriptorPool()
    const url = 'type.googleapis.com/prefix/google.protobuf.Timestamp'
    const hit = p.lookupType(url)
    console.log('typeurl', hit.fullName)
  }
} catch (e) {
  console.log('typeurl', String(e.message).split('\n')[0])
}

try {
  if (typeof m.standardPool === 'function') {
    const p = m.standardPool([{
      messages: [{ name: '.pkg.Wrap', fields: [{ name: 'child', number: 1, type: 'message', typeName: '.pkg.Wrap' }] }],
    }])
    const d = p.lookupMessage('.pkg.Wrap')
    const msg = new m.DynamicMessage(d, p)
    const f = d.fields[0]
    console.log('has-before', msg.has(f))
    msg.getFieldOrDefault(f)
    console.log('has-after', msg.has(f))
  } else {
    const p = new m.DescriptorPool()
    p.addFile({
      name: 'd.proto',
      package: 'pkg',
      syntax: 'proto3',
      messages: [{ kind: 'message', name: 'Wrap', fields: [{ name: 'child', number: 1, type: 'Wrap' }] }],
    })
    const d = p.findMessage('pkg.Wrap')
    const msg = new m.DynamicMessage(d)
    console.log('has-before', msg.has('child'))
    msg.get('child')
    console.log('has-after', msg.has('child'))
  }
} catch (e) {
  console.log('presence', String(e.message).split('\n')[0])
}

try {
  if (typeof m.toJson === 'function') {
    const p = new m.DescriptorPool()
    p.addFile({
      name: 'demo.proto',
      package: 'demo',
      syntax: 'proto3',
      messages: [{ kind: 'message', name: 'Msg', fields: [{ name: 'id', number: 1, type: 'int64' }] }],
    })
    const Msg = p.findMessage('demo.Msg')
    const msg = m.fromJson(Msg, '{"id":"42"}', p)
    console.log('roundtrip', m.toJson(msg))
  } else {
    const p = m.standardPool([{ messages: [{ name: '.pkg.Msg', fields: [{ name: 'user_id', number: 1, type: 'int64' }] }] }])
    const msg = new m.JsonParser(p).parse('{"userId":"42"}', p.lookupMessage('.pkg.Msg'))
    console.log('roundtrip', new m.JsonPrinter().print(msg))
  }
} catch (e) {
  console.log('roundtrip', String(e.message).split('\n')[0])
}
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/protobuf-json-mapping-core.git protobuf-json-mapping-core-A
cd protobuf-json-mapping-core-A
npm ci
npm run build
npx vitest run   # 预期：69 passed
node verify_json.mjs   # 预期：dotted unresolved:scalar；typeurl google.protobuf.Timestamp；has-before/after false；roundtrip {"id":"42"}
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/protobuf-json-mapping-core.git protobuf-json-mapping-core-B
cd protobuf-json-mapping-core-B
npm ci
npm run build
npx vitest run   # 预期：44 passed
node verify_json.mjs   # 预期：dotted .foo.bar.Inner；typeurl undef；has-before false has-after true；roundtrip {"userId":"42"}
cd ..
```

---

## 第 328 题　Bug 修复　·　困难　·　无界面
<!-- solo-report:task=328 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/bytecode-cfg-verify-core　A 分支：https://github.com/gy-vs/bytecode-cfg-verify-core/tree/A　B 分支：https://github.com/gy-vs/bytecode-cfg-verify-core/tree/B

存为 `verify_cfg.mjs`（放在仓库根目录）

```javascript
import * as m from './dist/index.js'

function run(bytes, ranges) {
  try {
    if (typeof m.verify === 'function') {
      const r = m.verify(bytes, ranges || [])
      return 'ok n=' + r.instructions.length
    }
    const r = m.buildControlFlowGraph(bytes, ranges || [])
    return 'ok n=' + r.instructions.length
  } catch (e) {
    return String(e.code || e.name) + ' off=' + String(e.offset) + ' idx=' + String(e.index) + ' tgt=' + String(e.targetOffset)
  }
}

if (typeof m.verify === 'function') {
  console.log('into-op', run(Uint8Array.from([0x01, 0x07, 0x02, 0xfd])))
  console.log('halt-bad', run(Uint8Array.from([0x05, 0xff])))
  console.log('ok-halt', run(Uint8Array.from([0x05])))
} else {
  console.log('into-op', run(Uint8Array.from([0x01, 0x07, 0x03, 0xff])))
  console.log('halt-bad', run(Uint8Array.from([0x06, 0xff])))
  console.log('ok-halt', run(Uint8Array.from([0x06])))
}

console.log('has-verify', typeof m.verify)
console.log('has-cfg', typeof m.buildControlFlowGraph)
console.log('has-OP_NOP', typeof m.OP_NOP)
console.log('has-OP', typeof m.OP)
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/bytecode-cfg-verify-core.git bytecode-cfg-verify-core-A
cd bytecode-cfg-verify-core-A
npm ci
npm run build
npx vitest run   # 预期：36 passed
node verify_cfg.mjs   # 预期：into-op JUMP_TARGET_NOT_BOUNDARY off=2 idx=1 tgt=1；halt-bad UNKNOWN_OPCODE；ok-halt n=1；has-verify function
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/bytecode-cfg-verify-core.git bytecode-cfg-verify-core-B
cd bytecode-cfg-verify-core-B
npm ci
npm run build
npx vitest run   # 预期：42 passed
node verify_cfg.mjs   # 预期：into-op JUMP_INTO_OPERAND off=2 idx=1 tgt=1；halt-bad UNKNOWN_OPCODE；ok-halt n=1；has-cfg function
cd ..
```

---

## 第 329 题　Feature 迭代　·　困难　·　无界面
<!-- solo-report:task=329 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/bytecode-stack-types-core　A 分支：https://github.com/gy-vs/bytecode-stack-types-core/tree/A　B 分支：https://github.com/gy-vs/bytecode-stack-types-core/tree/B

存为 `verify_types.mjs`（放在仓库根目录）

```javascript
import * as m from './dist/index.js'

if (typeof m.refType === 'function') {
  const named = m.refType('Foo')
  const bare = m.refType()
  console.log('join-ref', m.joinTypes(bare, named))
  console.log('assign-named-to-bare', m.isAssignable(named, bare))
  console.log('assign-bare-to-named', m.isAssignable(bare, named))
  const a = m.refType('Cat')
  const b = m.refType('Dog')
  console.log('join-two-named', m.joinTypes(a, b))
} else {
  const supers = { Foo: m.OBJECT, Cat: m.OBJECT, Dog: m.OBJECT }
  console.log('join-ref', JSON.stringify(m.joinTypes(m.cls(m.OBJECT), m.cls('Foo'), supers)))
  console.log('assign-named-to-bare', m.assignable(m.cls('Foo'), m.cls(m.OBJECT), supers))
  console.log('assign-bare-to-named', m.assignable(m.cls(m.OBJECT), m.cls('Foo'), supers))
  console.log('join-two-named', JSON.stringify(m.joinTypes(m.cls('Cat'), m.cls('Dog'), supers)))
}

console.log('has-cls', typeof m.cls)
console.log('has-refType', typeof m.refType)
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/bytecode-stack-types-core.git bytecode-stack-types-core-A
cd bytecode-stack-types-core-A
npm ci
npm run build
npx vitest run   # 预期：26 passed
node verify_types.mjs   # 预期：join-ref {"kind":"class","name":"java/lang/Object"}；assign-named-to-bare true；assign-bare-to-named false；join-two-named {"kind":"class","name":"java/lang/Object"}
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/bytecode-stack-types-core.git bytecode-stack-types-core-B
cd bytecode-stack-types-core-B
npm ci
npm run build
npx vitest run   # 预期：22 passed
node verify_types.mjs   # 预期：join-ref REF#Foo；assign-named-to-bare true；assign-bare-to-named false；join-two-named REF
cd ..
```

---

## 第 330 题　Bug 修复　·　困难　·　无界面
<!-- solo-report:task=330 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/bytecode-constant-index-core　A 分支：https://github.com/gy-vs/bytecode-constant-index-core/tree/A　B 分支：https://github.com/gy-vs/bytecode-constant-index-core/tree/B

存为 `verify_const.mjs`（放在仓库根目录）

```javascript
import * as m from './dist/index.js'

const qnan = 0x7ff8000000000000n
const snan = 0x7ff0000000000001n
const negZero = 0x8000000000000000n
const posZero = 0n

function isB() {
  return typeof m.planConstantPool === 'function'
}

function kinds(mod) {
  return mod.constants.map((c) => c.kind + ':' + String(c.value !== undefined ? c.value : c.bits)).join(',')
}

try {
  if (isB()) {
    const constants = [
      { kind: 'string', value: 'foo' },
      { kind: 'string', value: 'foo' },
      { kind: 'int', value: 1n },
      { kind: 'float', bits: posZero },
      { kind: 'float', bits: negZero },
      { kind: 'float', bits: qnan },
      { kind: 'float', bits: snan },
      { kind: 'signature', params: [], returns: [] },
    ]
    const fn = {
      signature: 7,
      code: [{ offset: 0, opcode: 1, operand: 0 }],
      nested: [],
      handlers: [{ tryStart: 0, tryEnd: 1, catchTarget: 0, typeIndex: 0 }],
    }
    const n1 = m.normalizeModule({
      constants: constants,
      functions: [fn],
      imports: [],
      exports: [],
      debug: null,
      extensions: [],
    })
    console.log('pool', kinds(n1))
    console.log('handler-type', n1.functions[0].handlers[0].typeIndex)
    console.log('handler-try', n1.functions[0].handlers[0].tryStart, n1.functions[0].handlers[0].tryEnd)
    const n2 = m.normalizeModule(n1)
    console.log('idem', kinds(n1) === kinds(n2))
    try {
      m.normalizeModule({
        constants: [
          { kind: 'string', value: 'b' },
          { kind: 'string', value: 'a' },
        ],
        functions: [],
        imports: [],
        exports: [],
        debug: null,
        extensions: [{ known: false, id: 128, body: new Uint8Array([1, 2, 3]) }],
      })
      console.log('unknown-ext', 'ok')
    } catch (e) {
      console.log('unknown-ext', e.name)
    }
  } else {
    const fn = function emptyFn(nameIndex, signatureIndex) {
      return {
        nameIndex: nameIndex,
        signatureIndex: signatureIndex,
        code: new Uint8Array(),
        locals: [],
        handlers: [],
        nested: [],
        debugFileIndex: -1,
      }
    }
    const constants = [
      { kind: 'string', value: 'foo' },
      { kind: 'string', value: 'foo' },
      { kind: 'int', value: 1n },
      { kind: 'float', bits: posZero },
      { kind: 'float', bits: negZero },
      { kind: 'float', bits: qnan },
      { kind: 'float', bits: snan },
      { kind: 'sig', value: { params: [], results: [] } },
    ]
    const n1 = m.normalizeModule({
      constants: constants,
      functions: [fn(0, 7)],
      imports: [],
      exports: [],
      extensions: [],
    })
    console.log('pool', kinds(n1))
    const n2 = m.normalizeModule(n1)
    console.log('idem', kinds(n1) === kinds(n2))
    try {
      m.normalizeModule({
        constants: [
          { kind: 'string', value: 'b' },
          { kind: 'string', value: 'a' },
          { kind: 'sig', value: { params: [], results: [] } },
        ],
        functions: [fn(0, 2)],
        imports: [],
        exports: [],
        extensions: [{ id: 128, opaque: true, data: new Uint8Array([1, 2, 3]), refs: [] }],
      })
      console.log('unknown-ext', 'ok')
    } catch (e) {
      console.log('unknown-ext', e.name)
    }
  }
} catch (e) {
  console.log('fail', e.name, String(e.message).split('\n')[0])
}
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/bytecode-constant-index-core.git bytecode-constant-index-core-A
cd bytecode-constant-index-core-A
npm ci
npm run build
npx vitest run   # 预期：14 passed
node verify_const.mjs   # 预期：pool 只留可达的 string:foo 与 sig；idem true；unknown-ext ExtensionBlockedError
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/bytecode-constant-index-core.git bytecode-constant-index-core-B
cd bytecode-constant-index-core-B
npm ci
npm run build
npx vitest run   # 预期：12 passed
node verify_const.mjs   # 预期：pool 保留 int/float/NaN/string/signature；handler-type 5；idem true；unknown-ext UnknownExtensionError
cd ..
```

---

## 第 333 题　Feature 迭代　·　困难　·　无界面
<!-- solo-report:task=333 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/hamt-transient-core　A 分支：https://github.com/gy-vs/hamt-transient-core/tree/A　B 分支：https://github.com/gy-vs/hamt-transient-core/tree/B

存为 `verify_hamt.mjs`（放在仓库根目录）

```javascript
import * as m from './dist/index.js'

const h = m.hashKey
const entries = [{ key: 'a', value: 1, hash: h('a') }]
try {
  const fromArr = new m.PersistentMap(entries)
  console.log('from-entries', fromArr.size(), String(fromArr.get('a', h('a'))))
} catch (e) {
  console.log('from-entries', e.name)
}

let base = new m.PersistentMap()
base = base.set('k', 1, h('k'))
const t = typeof base.transient === 'function' ? base.transient() : base.asTransient()
t.set('k2', 2, h('k2'))
const frozen = t.freeze()
console.log('frozen', frozen.size(), frozen.get('k2', h('k2')))
console.log('source', base.size(), String(base.get('k2', h('k2'))))
try {
  t.set('k3', 3, h('k3'))
  console.log('after-freeze', 'ok')
} catch (e) {
  console.log('after-freeze', e.message)
}
try {
  t.freeze()
  console.log('freeze-twice', 'ok')
} catch (e) {
  console.log('freeze-twice', e.message)
}

let vstat = 'no-validateMap'
try {
  if (typeof m.validateMap === 'function') vstat = String(m.validateMap(frozen))
} catch (e) {
  vstat = e.message
}
console.log('validateMap', vstat)
console.log('inspectRoot', typeof m.inspectRoot)
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/hamt-transient-core.git hamt-transient-core-A
cd hamt-transient-core-A
npm ci
npm run build
npx vitest run   # 预期：13 passed
node verify_hamt.mjs   # 预期：from-entries 1 1；frozen 2 2；source 1 undefined；after-freeze TransientMap used after freeze()；validateMap no-validateMap
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/hamt-transient-core.git hamt-transient-core-B
cd hamt-transient-core-B
npm ci
npm run build
npx vitest run   # 预期：17 passed
node verify_hamt.mjs   # 预期：from-entries TypeError；frozen 2 2；source 1 undefined；after-freeze TransientMap is no longer active (already frozen or aborted)；validateMap 2
cd ..
```

---

## 第 335 题　Feature 迭代　·　困难　·　无界面
<!-- solo-report:task=335 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/hamt-structural-diff-core　A 分支：https://github.com/gy-vs/hamt-structural-diff-core/tree/A　B 分支：https://github.com/gy-vs/hamt-structural-diff-core/tree/B

存为 `verify_diff.mjs`（放在仓库根目录）

```javascript
import * as m from './dist/index.js'

const h = m.hashKey
const dup = new m.PersistentMap([
  { key: 'a', value: 1, hash: h('a') },
  { key: 'a', value: 2, hash: h('a') },
])
console.log('dup-size', dup.size(), dup.get('a', h('a')))

let map = new m.PersistentMap()
map = map.set('u', undefined, h('u'))
console.log('undef-size', map.size(), map.get('u', h('u')) === undefined)
map = map.delete('u', h('u'))
console.log('undef-del', map.size())

let a = new m.PersistentMap()
a = a.set('x', 1, h('x'))
a = a.set('y', 2, h('y'))
const b = a.set('x', 9, h('x'))
console.log('nodes', a.nodeCount(), b.nodeCount())

async function runDiff() {
  if (typeof a.diff === 'function') {
    const stats = { nodesVisited: 0 }
    const events = []
    for await (const ev of a.diff(b, { stats: stats })) events.push(ev.type + ':' + ev.key)
    console.log('diff', events.join(','), 'visited', stats.nodesVisited)
  } else {
    const r = await m.diffMaps(a, b)
    const changed = (r.changed || []).map((e) => 'changed:' + e.key)
    console.log('diff', changed.join(','), 'visited', r.stats.nodesVisited, 'skipped', r.stats.sharedSubtreesSkipped)
  }
}

runDiff().catch((e) => {
  console.log('diff-err', e.name, String(e.message).split('\n')[0])
})
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/hamt-structural-diff-core.git hamt-structural-diff-core-A
cd hamt-structural-diff-core-A
npm ci
npm run build
npx vitest run   # 预期：16 passed
node verify_diff.mjs   # 预期：dup-size 1 2；undef-size 1；undef-del 0；diff changed:x visited 2
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/hamt-structural-diff-core.git hamt-structural-diff-core-B
cd hamt-structural-diff-core-B
npm ci
npm run build
npx vitest run   # 预期：22 passed
node verify_diff.mjs   # 预期：dup-size 2 2；undef-size 1；undef-del 1；diff changed:x visited 4 skipped 1
cd ..
```

---

## 第 336 题　Bug 修复　·　困难　·　无界面
<!-- solo-report:task=336 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/hamt-bitmap-boundary-core　A 分支：https://github.com/gy-vs/hamt-bitmap-boundary-core/tree/A　B 分支：https://github.com/gy-vs/hamt-bitmap-boundary-core/tree/B

存为 `verify_bitmap.mjs`（放在仓库根目录）

```javascript
import * as m from './dist/index.js'

console.log('bitFor31', typeof m.bitFor === 'function' ? m.bitFor(31) : 'no-bitFor')
console.log('popcount-neg1', typeof m.popcount === 'function' ? m.popcount(-1) : 'no-popcount')

function hashOf(slot) {
  if (typeof m.bitFor === 'function') return (slot << 27) >>> 0
  return slot >>> 0
}

function setSlot(map, slot, key) {
  return map.set(key, slot, hashOf(slot))
}

let map = new m.PersistentMap()
for (let s = 0; s < 16; s++) map = setSlot(map, s, 's' + s)
map = setSlot(map, 31, 's31')
console.log('has31', map.get('s31', hashOf(31)))
console.log('has0', map.get('s0', hashOf(0)))

const keys = []
if (typeof map.items === 'function') {
  for (const e of map.items()) keys.push(e.key)
}
console.log('nkeys', keys.length, 'last', keys[keys.length - 1], 'has-s31', keys.indexOf('s31') >= 0)

let neg = new m.PersistentMap()
neg = neg.set('n', 7, -1)
console.log('neg-hash', neg.get('n', -1), neg.get('n', 4294967295))

const root = typeof map.getRootNode === 'function' ? map.getRootNode() : null
if (root && root.bitmap !== undefined) console.log('root-kind', 'bitmap', (root.bitmap >>> 0).toString(16))
else if (root && root.children && root.children.length === 32) console.log('root-kind', 'array')
else console.log('root-kind', root && root.constructor ? root.constructor.name : typeof root)
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/hamt-bitmap-boundary-core.git hamt-bitmap-boundary-core-A
cd hamt-bitmap-boundary-core-A
npm ci
npm run build
npx vitest run   # 预期：33 passed
node verify_bitmap.mjs   # 预期：bitFor31 2147483648；popcount-neg1 32；has31 31；nkeys 17 last s31；neg-hash 7 7；root-kind array
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/hamt-bitmap-boundary-core.git hamt-bitmap-boundary-core-B
cd hamt-bitmap-boundary-core-B
npm ci
npm run build
npx vitest run   # 预期：19 passed
node verify_bitmap.mjs   # 预期：bitFor31 no-bitFor；popcount-neg1 no-popcount；has31 31；nkeys 17 last s31；neg-hash 7 7；root-kind object
cd ..
```

---

## 第 339 题　0-1 代码生成　·　困难　·　全栈
<!-- solo-report:task=339 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/otel-baggage-inspector-web　A 分支：https://github.com/gy-vs/otel-baggage-inspector-web/tree/A　B 分支：https://github.com/gy-vs/otel-baggage-inspector-web/tree/B

服务：`npm start` 同时托管 API 与 `public/` 静态页。两侧都设 `$env:PORT = "3000"`，浏览器开 http://localhost:3000。B 默认本是 8080，用环境变量对齐。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/otel-baggage-inspector-web.git otel-baggage-inspector-web-A
cd otel-baggage-inspector-web-A
npm install
npm test                                                       # 预期：38 passed
$env:PORT = "3000"
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm start"   # 新窗口打出 baggage workbench listening on http://localhost:3000
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:3000/api/health | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:3000                              # 浏览器打开后按下面「界面操作」走
Invoke-RestMethod http://127.0.0.1:3000/api/graphs | ConvertTo-Json -Compress   # 预期：graphs[0].name 为 demo-shop，revision 1，5 个节点
try { Invoke-RestMethod http://127.0.0.1:3000/api/configs | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404（A 的图在 /api/graphs）
$g = Invoke-RestMethod http://127.0.0.1:3000/api/graphs
Invoke-RestMethod -Method Post -Uri ("http://127.0.0.1:3000/api/graphs/" + $g.graphs[0].id + "/runs") -ContentType "application/json" -Body '{"node":"frontend","headers":{"baggage":"user_id=42,password=hunter2,env=prod,env=staging","traceparent":"00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"}}' | ConvertTo-Json -Compress   # 预期：hops 至少 6 条，password 为 dropped/sensitive-removed，重复 env 丢弃，joins 写明不合并
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:3000/api/sample/run -ContentType "application/json" -Body '{}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
taskkill /PID $svc.Id /T /F
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:3000。A：标题「OpenTelemetry Baggage 传播检查工作台」，图下拉已是 demo-shop，revision 徽章为 1；B：顶栏「🧳 Baggage 传播检查工作台」，自动载入 checkout 示例。
2. 点「运行」。A：③ 逐跳结果出现 frontend→api→auth/billing→notify，password 标丢弃（敏感键），`env=staging` 因重复键丢弃，notify 合流提示不合并；B：按钮是「▶ 运行模拟」，示例图是 edge-gateway / auth / inventory。
3. 在④ 选两跳点「比较」。A：列出键级 same / 变化；B：右侧「两跳对比」用 `=` / `≠` / `+` / `−`。
4. 点「导出 JSON（已脱敏）」或打开对应导出链接。A：敏感值被替换成 `[REDACTED]`，短值可能误伤其它字段，导出里仍能看到键名 password；B：按钮「导出脱敏记录」，所有成员值都去掉只留键和字节长度。
5. 改 JSON 后点「保存（新 revision）」两次、第二次不先点 ↻。A：第二次 409，提示「冲突：…请点 ↻ 重新加载」；B：「保存新 revision」同样要带 expectedRevision，过期 409。
6. B 独有「多入口 roots」文本框（文档写了 `input.roots`）；A 没有该字段。回到终端执行剩下的接口命令并 `taskkill`。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/otel-baggage-inspector-web.git otel-baggage-inspector-web-B
cd otel-baggage-inspector-web-B
npm install
npm test                                                       # 预期：47 passed
$env:PORT = "3000"
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm start"   # 新窗口打出 baggage workbench listening on http://localhost:3000
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:3000/api/health | Out-Null; break } catch { Start-Sleep -Seconds 1 } }
Start-Process http://localhost:3000                              # 浏览器打开后按下面「界面操作」走
try { Invoke-RestMethod http://127.0.0.1:3000/api/graphs | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404（B 的图在 /api/configs）
Invoke-RestMethod http://127.0.0.1:3000/api/configs | ConvertTo-Json -Compress   # 预期：含 id 为 sample 的 Checkout pipeline
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:3000/api/graphs/x/runs -ContentType "application/json" -Body '{"node":"frontend","headers":{"baggage":"user_id=42,password=hunter2,env=prod,env=staging","traceparent":"00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"}}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：404
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:3000/api/sample/run -ContentType "application/json" -Body '{}' | ConvertTo-Json -Compress   # 预期：201 或 200 复用，hops 含敏感删除、rename、isolate/union 合流
taskkill /PID $svc.Id /T /F
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 1、2、4、6 步。

---

## 第 342 题　0-1 代码生成　·　困难　·　全栈
<!-- solo-report:task=342 generated=2026-09-22 -->

仓库：https://github.com/gy-vs/binary-layout-studio-web　A 分支：https://github.com/gy-vs/binary-layout-studio-web/tree/A　B 分支：https://github.com/gy-vs/binary-layout-studio-web/tree/B

服务：同一套命令两侧都跑。`npm start` 在 A 听 8080（Node 静态页+API）；`uvicorn backend.app.main:app` 在 B 听 8000（Python 全栈）。缺的一侧预期为模块不存在或 404。浏览器主入口 http://localhost:8000。

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/binary-layout-studio-web.git binary-layout-studio-web-A
cd binary-layout-studio-web-A
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt                       # 预期：没有 requirements.txt，pip 报文件不存在
npm test                                                       # 预期：28 passed
python -m pytest tests/ -q                                     # 预期：No module named pytest，或 tests 目录不存在
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm start"   # 新窗口打出 binary-layout-studio 已启动: http://localhost:8080
$web = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command",".\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000"   # 预期：ModuleNotFoundError，没有 backend.app
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:8080/ | Out-Null; break } catch { try { Invoke-RestMethod http://127.0.0.1:8000/ | Out-Null; break } catch { Start-Sleep -Seconds 1 } } }
Start-Process http://localhost:8000                              # A：8000 连不上，改开 http://localhost:8080 看 Node 页
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8080/api/compile -ContentType "application/json" -Body '{"schema":"struct Node be { n: u8; kids: Node[n]; }"}' | ConvertTo-Json -Compress   # 预期：ok true，root 为 Node（经数组的递归可通过）
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/parse -ContentType "application/json" -Body '{"layout":"struct A { a: A; }","hex":"00"}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：连接失败或 404（Python 服务没起来）
try { Invoke-RestMethod http://127.0.0.1:8000/api/example | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：连接失败或 404
taskkill /PID $svc.Id /T /F
taskkill /PID $web.Id /T /F
deactivate
cd ..
```

A 侧界面操作（`Start-Process` 打开浏览器之后、`taskkill` 之前做）：

1. 进入 http://localhost:8000。A：页面起不来（没有 FastAPI 模块）；B：标题「二进制布局检查工作台」，按钮「解析 ▸」「重新编码 ⟳」「载入示例」。
2. 点击「载入示例」。A：按钮不存在；B：布局框出现 `struct Packet`，十六进制自动填入。
3. 点击「解析 ▸」。A：无此按钮（A 在 8080 上的按钮文案是「解析」）；B：字段树出现 hdr.magic / flags 等位域，字节视图高亮范围不越输入。
4. 点击字段树一行再点字节格子。A：8080 页也能双向定位（probe 标无界面，实际 public 页有「字段树」「字节网格」）；B：字段树 ↔ 字节视图双向定位。
5. 把布局改成 `struct Node { n: u8; kids: Node[n]; }` 再解析。A：8080 的 `/api/compile` 成功；B：8000 返回 ok false，error.message 含「递归无界」。
6. 回到终端执行剩下的接口命令并 `taskkill`。

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/binary-layout-studio-web.git binary-layout-studio-web-B
cd binary-layout-studio-web-B
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt                       # 预期：装上 fastapi uvicorn pytest httpx
npm test                                                       # 预期：没有 package.json，npm 报 ENOENT
python -m pytest tests/ -q                                     # 预期：101 passed
$svc = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command","npm start"   # 预期：没有 package.json，新窗口报 ENOENT
$web = Start-Process powershell -PassThru -ArgumentList "-NoExit","-Command",".\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000"   # 新窗口打出 Uvicorn running on http://127.0.0.1:8000
for ($i = 0; $i -lt 30; $i++) { try { Invoke-RestMethod http://127.0.0.1:8080/ | Out-Null; break } catch { try { Invoke-RestMethod http://127.0.0.1:8000/ | Out-Null; break } catch { Start-Sleep -Seconds 1 } } }
Start-Process http://localhost:8000                              # 浏览器打开后按下面「界面操作」走
try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8080/api/compile -ContentType "application/json" -Body '{"schema":"struct Node be { n: u8; kids: Node[n]; }"}' | ConvertTo-Json -Compress } catch { $_.Exception.Response.StatusCode.value__ }   # 预期：连接失败或 404（B 没有 Node 服务）
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/parse -ContentType "application/json" -Body '{"layout":"struct A { a: A; }","hex":"00"}' | ConvertTo-Json -Compress   # 预期：ok false，stage 为 compile，message 含「递归无界」
Invoke-RestMethod http://127.0.0.1:8000/api/example | ConvertTo-Json -Compress   # 预期：layout 含 struct Packet，并带 hex
taskkill /PID $svc.Id /T /F
taskkill /PID $web.Id /T /F
deactivate
cd ..
```

B 侧界面操作：与 A 侧相同，差异见第 1、5 步。

---
