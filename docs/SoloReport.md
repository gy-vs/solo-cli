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
| [04](#第-04-题Bug-修复困难无界面) | Bug 修复 | 困难 | 无界面 | [A](https://github.com/gy-vs/chrono-datetime-core/tree/A) | [B](https://github.com/gy-vs/chrono-datetime-core/tree/B) | 2026-09-20 |
| [07](#第-07-题0-1-代码生成困难无界面) | 0-1 代码生成 | 困难 | 无界面 | [A](https://github.com/gy-vs/regex-engine-core/tree/A) | [B](https://github.com/gy-vs/regex-engine-core/tree/B) | 2026-09-20 |
| [08](#第-08-题0-1-代码生成困难无界面) | 0-1 代码生成 | 困难 | 无界面 | [A](https://github.com/gy-vs/type-inference-core/tree/A) | [B](https://github.com/gy-vs/type-inference-core/tree/B) | 2026-09-20 |
| [10](#第-10-题Bug-修复困难无界面) | Bug 修复 | 困难 | 无界面 | [A](https://github.com/gy-vs/css-visitor-core/tree/A) | [B](https://github.com/gy-vs/css-visitor-core/tree/B) | 2026-09-20 |
| [15](#第-15-题Feature-迭代困难无界面) | Feature 迭代 | 困难 | 无界面 | [A](https://github.com/gy-vs/query-eval-core/tree/A) | [B](https://github.com/gy-vs/query-eval-core/tree/B) | 2026-09-20 |
| [16](#第-16-题0-1-代码生成困难无界面) | 0-1 代码生成 | 困难 | 无界面 | [A](https://github.com/gy-vs/deflate-codec-core/tree/A) | [B](https://github.com/gy-vs/deflate-codec-core/tree/B) | 2026-09-20 |
| [17](#第-17-题0-1-代码生成地狱无界面) | 0-1 代码生成 | 地狱 | 无界面 | [A](https://github.com/gy-vs/consensus-replication-core/tree/A) | [B](https://github.com/gy-vs/consensus-replication-core/tree/B) | 2026-09-20 |
| [24](#第-24-题Bug-修复困难无界面) | Bug 修复 | 困难 | 无界面 | [A](https://github.com/gy-vs/css-custom-prop-core/tree/A) | [B](https://github.com/gy-vs/css-custom-prop-core/tree/B) | 2026-09-20 |
| [26](#第-26-题Bug-修复困难无界面) | Bug 修复 | 困难 | 无界面 | [A](https://github.com/gy-vs/js-module-import-core/tree/A) | [B](https://github.com/gy-vs/js-module-import-core/tree/B) | 2026-09-20 |
| [33](#第-33-题Feature-迭代困难无界面) | Feature 迭代 | 困难 | 无界面 | [A](https://github.com/gy-vs/css-calc-type-core/tree/A) | [B](https://github.com/gy-vs/css-calc-type-core/tree/B) | 2026-09-20 |
| [35](#第-35-题Bug-修复困难无界面) | Bug 修复 | 困难 | 无界面 | [A](https://github.com/gy-vs/css-input-map-core/tree/A) | [B](https://github.com/gy-vs/css-input-map-core/tree/B) | 2026-09-20 |
| [36](#第-36-题0-1-代码生成困难无界面) | 0-1 代码生成 | 困难 | 无界面 | [A](https://github.com/gy-vs/http-cache-core/tree/A) | [B](https://github.com/gy-vs/http-cache-core/tree/B) | 2026-09-20 |
| [37](#第-37-题Feature-迭代困难无界面) | Feature 迭代 | 困难 | 无界面 | [A](https://github.com/gy-vs/yaml-emit-core/tree/A) | [B](https://github.com/gy-vs/yaml-emit-core/tree/B) | 2026-09-20 |
| [38](#第-38-题Bug-修复困难无界面) | Bug 修复 | 困难 | 无界面 | [A](https://github.com/gy-vs/yaml-alias-core/tree/A) | [B](https://github.com/gy-vs/yaml-alias-core/tree/B) | 2026-09-20 |
| [39](#第-39-题Feature-迭代困难无界面) | Feature 迭代 | 困难 | 无界面 | [A](https://github.com/gy-vs/chrono-recur-core/tree/A) | [B](https://github.com/gy-vs/chrono-recur-core/tree/B) | 2026-09-20 |
| [40](#第-40-题代码重构困难无界面) | 代码重构 | 困难 | 无界面 | [A](https://github.com/gy-vs/chrono-format-core/tree/A) | [B](https://github.com/gy-vs/chrono-format-core/tree/B) | 2026-09-20 |
| [41](#第-41-题Feature-迭代困难无界面) | Feature 迭代 | 困难 | 无界面 | [A](https://github.com/gy-vs/js-using-decl-core/tree/A) | [B](https://github.com/gy-vs/js-using-decl-core/tree/B) | 2026-09-20 |
| [42](#第-42-题Bug-修复困难无界面) | Bug 修复 | 困难 | 无界面 | [A](https://github.com/gy-vs/js-token-context-core/tree/A) | [B](https://github.com/gy-vs/js-token-context-core/tree/B) | 2026-09-20 |
| [43](#第-43-题Bug-修复困难无界面) | Bug 修复 | 困难 | 无界面 | [A](https://github.com/gy-vs/css-generator-core/tree/A) | [B](https://github.com/gy-vs/css-generator-core/tree/B) | 2026-09-20 |
| [45](#第-45-题Bug-修复困难无界面) | Bug 修复 | 困难 | 无界面 | [A](https://github.com/gy-vs/query-signature-core/tree/A) | [B](https://github.com/gy-vs/query-signature-core/tree/B) | 2026-09-20 |
| [51](#第-51-题0-1-代码生成困难无界面) | 0-1 代码生成 | 困难 | 无界面 | [A](https://github.com/gy-vs/dns-resolution-cache/tree/A) | [B](https://github.com/gy-vs/dns-resolution-cache/tree/B) | 2026-09-20 |
| [52](#第-52-题0-1-代码生成困难无界面) | 0-1 代码生成 | 困难 | 无界面 | [A](https://github.com/gy-vs/range-lock-manager/tree/A) | [B](https://github.com/gy-vs/range-lock-manager/tree/B) | 2026-09-20 |
| [53](#第-53-题0-1-代码生成困难无界面) | 0-1 代码生成 | 困难 | 无界面 | [A](https://github.com/gy-vs/cookie-policy-jar/tree/A) | [B](https://github.com/gy-vs/cookie-policy-jar/tree/B) | 2026-09-20 |
| [54](#第-54-题0-1-代码生成困难无界面) | 0-1 代码生成 | 困难 | 无界面 | [A](https://github.com/gy-vs/hedged-request-coordinator/tree/A) | [B](https://github.com/gy-vs/hedged-request-coordinator/tree/B) | 2026-09-20 |
| [55](#第-55-题0-1-代码生成困难无界面) | 0-1 代码生成 | 困难 | 无界面 | [A](https://github.com/gy-vs/accept-negotiation-core/tree/A) | [B](https://github.com/gy-vs/accept-negotiation-core/tree/B) | 2026-09-20 |
| [56](#第-56-题Bug-修复困难无界面) | Bug 修复 | 困难 | 无界面 | [A](https://github.com/gy-vs/httpx-tls-client-core/tree/A) | [B](https://github.com/gy-vs/httpx-tls-client-core/tree/B) | 2026-09-20 |
| [57](#第-57-题Bug-修复困难无界面) | Bug 修复 | 困难 | 无界面 | [A](https://github.com/gy-vs/httpx-zstd-response-core/tree/A) | [B](https://github.com/gy-vs/httpx-zstd-response-core/tree/B) | 2026-09-20 |
| [58](#第-58-题Bug-修复困难无界面) | Bug 修复 | 困难 | 无界面 | [A](https://github.com/gy-vs/httpx-timeout-dispatch-core/tree/A) | [B](https://github.com/gy-vs/httpx-timeout-dispatch-core/tree/B) | 2026-09-20 |
| [59](#第-59-题Bug-修复困难无界面) | Bug 修复 | 困难 | 无界面 | [A](https://github.com/gy-vs/httpx-digest-auth-core/tree/A) | [B](https://github.com/gy-vs/httpx-digest-auth-core/tree/B) | 2026-09-20 |
| [60](#第-60-题Bug-修复困难无界面) | Bug 修复 | 困难 | 无界面 | [A](https://github.com/gy-vs/httpx-asgi-transport-core/tree/A) | [B](https://github.com/gy-vs/httpx-asgi-transport-core/tree/B) | 2026-09-20 |
| [61](#第-61-题Bug-修复困难无界面) | Bug 修复 | 困难 | 无界面 | [A](https://github.com/gy-vs/jinja-bytecode-cache-core/tree/A) | [B](https://github.com/gy-vs/jinja-bytecode-cache-core/tree/B) | 2026-09-20 |
| [62](#第-62-题Bug-修复困难无界面) | Bug 修复 | 困难 | 无界面 | [A](https://github.com/gy-vs/jinja-async-stream-core/tree/A) | [B](https://github.com/gy-vs/jinja-async-stream-core/tree/B) | 2026-09-20 |
| [63](#第-63-题Bug-修复困难无界面) | Bug 修复 | 困难 | 无界面 | [A](https://github.com/gy-vs/jinja-branch-scope-core/tree/A) | [B](https://github.com/gy-vs/jinja-branch-scope-core/tree/B) | 2026-09-20 |
| [64](#第-64-题Bug-修复困难无界面) | Bug 修复 | 困难 | 无界面 | [A](https://github.com/gy-vs/jinja-required-block-core/tree/A) | [B](https://github.com/gy-vs/jinja-required-block-core/tree/B) | 2026-09-20 |
| [65](#第-65-题Bug-修复困难无界面) | Bug 修复 | 困难 | 无界面 | [A](https://github.com/gy-vs/attrs-field-transform-core/tree/A) | [B](https://github.com/gy-vs/attrs-field-transform-core/tree/B) | 2026-09-20 |
| [66](#第-66-题Bug-修复困难无界面) | Bug 修复 | 困难 | 无界面 | [A](https://github.com/gy-vs/attrs-keyword-init-core/tree/A) | [B](https://github.com/gy-vs/attrs-keyword-init-core/tree/B) | 2026-09-20 |
| [67](#第-67-题Bug-修复困难无界面) | Bug 修复 | 困难 | 无界面 | [A](https://github.com/gy-vs/attrs-slotted-cache-core/tree/A) | [B](https://github.com/gy-vs/attrs-slotted-cache-core/tree/B) | 2026-09-20 |
| [68](#第-68-题Bug-修复困难无界面) | Bug 修复 | 困难 | 无界面 | [A](https://github.com/gy-vs/attrs-preinit-core/tree/A) | [B](https://github.com/gy-vs/attrs-preinit-core/tree/B) | 2026-09-20 |
| [69](#第-69-题Bug-修复困难无界面) | Bug 修复 | 困难 | 无界面 | [A](https://github.com/gy-vs/async-queue-window-core/tree/A) | [B](https://github.com/gy-vs/async-queue-window-core/tree/B) | 2026-09-20 |
| [70](#第-70-题Bug-修复困难无界面) | Bug 修复 | 困难 | 无界面 | [A](https://github.com/gy-vs/async-queue-backpressure-core/tree/A) | [B](https://github.com/gy-vs/async-queue-backpressure-core/tree/B) | 2026-09-20 |
| [71](#第-71-题Bug-修复困难无界面) | Bug 修复 | 困难 | 无界面 | [A](https://github.com/gy-vs/async-queue-abort-core/tree/A) | [B](https://github.com/gy-vs/async-queue-abort-core/tree/B) | 2026-09-20 |
| [72](#第-72-题Bug-修复困难无界面) | Bug 修复 | 困难 | 无界面 | [A](https://github.com/gy-vs/async-queue-drain-core/tree/A) | [B](https://github.com/gy-vs/async-queue-drain-core/tree/B) | 2026-09-20 |
| [73](#第-73-题Bug-修复困难无界面) | Bug 修复 | 困难 | 无界面 | [A](https://github.com/gy-vs/async-queue-interval-core/tree/A) | [B](https://github.com/gy-vs/async-queue-interval-core/tree/B) | 2026-09-20 |
| [74](#第-74-题Bug-修复困难无界面) | Bug 修复 | 困难 | 无界面 | [A](https://github.com/gy-vs/markdown-reference-core/tree/A) | [B](https://github.com/gy-vs/markdown-reference-core/tree/B) | 2026-09-20 |
| [76](#第-76-题Bug-修复困难无界面) | Bug 修复 | 困难 | 无界面 | [A](https://github.com/gy-vs/markdown-task-list-core/tree/A) | [B](https://github.com/gy-vs/markdown-task-list-core/tree/B) | 2026-09-20 |
| [77](#第-77-题Bug-修复困难无界面) | Bug 修复 | 困难 | 无界面 | [A](https://github.com/gy-vs/markdown-blockquote-core/tree/A) | [B](https://github.com/gy-vs/markdown-blockquote-core/tree/B) | 2026-09-20 |
| [78](#第-78-题Bug-修复困难无界面) | Bug 修复 | 困难 | 无界面 | [A](https://github.com/gy-vs/markdown-inline-link-core/tree/A) | [B](https://github.com/gy-vs/markdown-inline-link-core/tree/B) | 2026-09-20 |
| [79](#第-79-题Feature-迭代困难无界面) | Feature 迭代 | 困难 | 无界面 | [A](https://github.com/gy-vs/httpx-socket-options-core/tree/A) | [B](https://github.com/gy-vs/httpx-socket-options-core/tree/B) | 2026-09-20 |
| [80](#第-80-题Feature-迭代困难无界面) | Feature 迭代 | 困难 | 无界面 | [A](https://github.com/gy-vs/httpx-socks-resolution-core/tree/A) | [B](https://github.com/gy-vs/httpx-socks-resolution-core/tree/B) | 2026-09-20 |
| [81](#第-81-题Feature-迭代困难无界面) | Feature 迭代 | 困难 | 无界面 | [A](https://github.com/gy-vs/httpx-zstd-codec-core/tree/A) | [B](https://github.com/gy-vs/httpx-zstd-codec-core/tree/B) | 2026-09-20 |
| [82](#第-82-题Feature-迭代困难无界面) | Feature 迭代 | 困难 | 无界面 | [A](https://github.com/gy-vs/httpx-multipart-header-core/tree/A) | [B](https://github.com/gy-vs/httpx-multipart-header-core/tree/B) | 2026-09-20 |
| [83](#第-83-题Feature-迭代困难无界面) | Feature 迭代 | 困难 | 无界面 | [A](https://github.com/gy-vs/httpx-h2-tunnel-core/tree/A) | [B](https://github.com/gy-vs/httpx-h2-tunnel-core/tree/B) | 2026-09-20 |
| [84](#第-84-题Feature-迭代困难无界面) | Feature 迭代 | 困难 | 无界面 | [A](https://github.com/gy-vs/jinja-namespace-assign-core/tree/A) | [B](https://github.com/gy-vs/jinja-namespace-assign-core/tree/B) | 2026-09-20 |
| [100](#第-100-题Feature-迭代困难无界面) | Feature 迭代 | 困难 | 无界面 | [A](https://github.com/gy-vs/markdown-token-pipeline-core/tree/A) | [B](https://github.com/gy-vs/markdown-token-pipeline-core/tree/B) | 2026-09-20 |
| [101](#第-101-题0-1-代码生成困难无界面) | 0-1 代码生成 | 困难 | 无界面 | [A](https://github.com/gy-vs/json-patch-transaction-core/tree/A) | [B](https://github.com/gy-vs/json-patch-transaction-core/tree/B) | 2026-09-20 |
| [102](#第-102-题0-1-代码生成困难无界面) | 0-1 代码生成 | 困难 | 无界面 | [A](https://github.com/gy-vs/rendezvous-hash-core/tree/A) | [B](https://github.com/gy-vs/rendezvous-hash-core/tree/B) | 2026-09-20 |
| [103](#第-103-题0-1-代码生成困难无界面) | 0-1 代码生成 | 困难 | 无界面 | [A](https://github.com/gy-vs/async-phaser-core/tree/A) | [B](https://github.com/gy-vs/async-phaser-core/tree/B) | 2026-09-20 |
| [104](#第-104-题0-1-代码生成困难无界面) | 0-1 代码生成 | 困难 | 无界面 | [A](https://github.com/gy-vs/framed-stream-core/tree/A) | [B](https://github.com/gy-vs/framed-stream-core/tree/B) | 2026-09-20 |
| [105](#第-105-题0-1-代码生成困难无界面) | 0-1 代码生成 | 困难 | 无界面 | [A](https://github.com/gy-vs/text-anchor-transform-core/tree/A) | [B](https://github.com/gy-vs/text-anchor-transform-core/tree/B) | 2026-09-20 |
| [106](#第-106-题Bug-修复困难无界面) | Bug 修复 | 困难 | 无界面 | [A](https://github.com/gy-vs/httpx-url-encoding-core/tree/A) | [B](https://github.com/gy-vs/httpx-url-encoding-core/tree/B) | 2026-09-20 |
| [107](#第-107-题Bug-修复困难无界面) | Bug 修复 | 困难 | 无界面 | [A](https://github.com/gy-vs/jinja-template-globals-core/tree/A) | [B](https://github.com/gy-vs/jinja-template-globals-core/tree/B) | 2026-09-20 |
| [109](#第-109-题Bug-修复困难无界面) | Bug 修复 | 困难 | 无界面 | [A](https://github.com/gy-vs/acorn-delayed-errors-core/tree/A) | [B](https://github.com/gy-vs/acorn-delayed-errors-core/tree/B) | 2026-09-20 |
| [110](#第-110-题Bug-修复困难无界面) | Bug 修复 | 困难 | 无界面 | [A](https://github.com/gy-vs/async-queue-signal-cleanup-core/tree/A) | [B](https://github.com/gy-vs/async-queue-signal-cleanup-core/tree/B) | 2026-09-20 |
| [112](#第-112-题Bug-修复困难无界面) | Bug 修复 | 困难 | 无界面 | [A](https://github.com/gy-vs/markdown-autolink-entity-core/tree/A) | [B](https://github.com/gy-vs/markdown-autolink-entity-core/tree/B) | 2026-09-20 |
| [113](#第-113-题Bug-修复困难无界面) | Bug 修复 | 困难 | 无界面 | [A](https://github.com/gy-vs/markdown-indented-code-core/tree/A) | [B](https://github.com/gy-vs/markdown-indented-code-core/tree/B) | 2026-09-20 |
| [114](#第-114-题Bug-修复困难无界面) | Bug 修复 | 困难 | 无界面 | [A](https://github.com/gy-vs/markdown-hook-isolation-core/tree/A) | [B](https://github.com/gy-vs/markdown-hook-isolation-core/tree/B) | 2026-09-20 |
| [117](#第-117-题Feature-迭代困难无界面) | Feature 迭代 | 困难 | 无界面 | [A](https://github.com/gy-vs/jinja-native-macro-core/tree/A) | [B](https://github.com/gy-vs/jinja-native-macro-core/tree/B) | 2026-09-20 |
| [118](#第-118-题Feature-迭代困难无界面) | Feature 迭代 | 困难 | 无界面 | [A](https://github.com/gy-vs/jinja-loop-neighbor-core/tree/A) | [B](https://github.com/gy-vs/jinja-loop-neighbor-core/tree/B) | 2026-09-20 |
| [119](#第-119-题Feature-迭代困难无界面) | Feature 迭代 | 困难 | 无界面 | [A](https://github.com/gy-vs/attrs-exception-core/tree/A) | [B](https://github.com/gy-vs/attrs-exception-core/tree/B) | 2026-09-20 |
| [120](#第-120-题Feature-迭代困难无界面) | Feature 迭代 | 困难 | 无界面 | [A](https://github.com/gy-vs/attrs-pickle-state-core/tree/A) | [B](https://github.com/gy-vs/attrs-pickle-state-core/tree/B) | 2026-09-20 |
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

## 第 04 题　Bug 修复　·　困难　·　无界面
<!-- solo-report:task=04 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/chrono-datetime-core　A 分支：https://github.com/gy-vs/chrono-datetime-core/tree/A　B 分支：https://github.com/gy-vs/chrono-datetime-core/tree/B

存为 `verify_duration.js`（放在仓库根目录）

```javascript
const { Duration } = require('./src/luxon.js')
const d1 = Duration.fromObject({ years: 0, months: 12, days: 730 })
console.log('G1', JSON.stringify(d1.shiftTo('years', 'months', 'days').toObject()))
const ms = 365 * 24 * 60 * 60 * 1000
const d2 = Duration.fromMillis(ms)
console.log('G2', JSON.stringify(d2.shiftTo('years', 'months', 'days', 'hours', 'minutes', 'seconds', 'milliseconds').toObject()))
const d2c = Duration.fromMillis(-ms * 12)
console.log('G2neg', JSON.stringify(d2c.shiftTo('years', 'months', 'days').toObject()))
const d3 = Duration.fromObject({ years: 0, days: 367 })
console.log('G3norm', JSON.stringify(d3.normalize().toObject()))
console.log('G3shift', JSON.stringify(d3.shiftTo().toObject()))
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/chrono-datetime-core.git chrono-datetime-core-A
cd chrono-datetime-core-A
npm ci
$env:TZ = "America/New_York"
npx jest test/duration --coverage=false   # 预期：15 passed, 189 passed
npx babel-node verify_duration.js   # 预期：G1 {"years":3,"months":0,"days":0} ；G2 years 1 其余为 0 ；G2neg {"years":-12,"months":0,"days":0} ；G3norm 与 G3shift 均为 {"years":1,"days":2}
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/chrono-datetime-core.git chrono-datetime-core-B
cd chrono-datetime-core-B
npm ci
$env:TZ = "America/New_York"
npx jest test/duration --coverage=false   # 预期：15 failed ；TypeError: Duration.fromObject is not a function
npx babel-node verify_duration.js   # 预期：TypeError: Duration.fromObject is not a function
cd ..
```

---

## 第 07 题　0-1 代码生成　·　困难　·　无界面
<!-- solo-report:task=07 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/regex-engine-core　A 分支：https://github.com/gy-vs/regex-engine-core/tree/A　B 分支：https://github.com/gy-vs/regex-engine-core/tree/B

存为 `verify_posix_perf.py`（放在仓库根目录）

```python
import time
from posixre import compile

p = compile(r'(a|aa)*b')
for n in (20, 40, 60, 80):
    text = 'a' * n
    start = time.perf_counter()
    result = p.match(text)
    ms = round((time.perf_counter() - start) * 1000, 3)
    print(n, result, ms, 'ms')
```

存为 `verify_posix_reject.py`（放在仓库根目录）

```python
from posixre import compile

for pat in (r'(x)\1', r'a(?=b)'):
    try:
        compile(pat)
        print(pat, 'no error')
    except Exception as e:
        print(pat, type(e).__name__, getattr(e, 'pos', None))
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/regex-engine-core.git regex-engine-core-A
cd regex-engine-core-A
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e .
python -m unittest discover -s tests -q                              # 预期：Ran 73 tests，OK
python -c "from posixre import match; m = match(r'(a|ab)(c|bcd)(d*)', 'abcd'); print(m.span(), m.groups(), [m.span(g) for g in (1,2,3)])"   # 预期：(0, 4) ('ab', 'c', 'd') [(0, 2), (2, 3), (3, 4)]
python verify_posix_perf.py                                         # 预期：四行均为 None，耗时毫秒级且随长度接近线性
python -c "from posixre import scan; print([m.span() for m in scan(r'a*', 'bab')])"   # 预期：[(0, 0), (1, 2), (3, 3)]
python -c "from posixre import finditer; print([m.span() for m in finditer(r'a*', 'aba')])"   # 预期：ImportError: cannot import name 'finditer'
python verify_posix_reject.py                                       # 预期：error 3 与 error 2
python -c "import os; print(os.path.exists('tests/oracle.py'))"      # 预期：True
deactivate
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/regex-engine-core.git regex-engine-core-B
cd regex-engine-core-B
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
$env:PYTHONPATH = "."
python -m unittest discover -s tests -q                              # 预期：Ran 105 tests，OK
python -c "from posixre import match; m = match(r'(a|ab)(c|bcd)(d*)', 'abcd'); print(m.span(), m.groups(), [m.span(g) for g in (1,2,3)])"   # 预期：(0, 4) ('ab', 'c', 'd') [(0, 2), (2, 3), (3, 4)]
python verify_posix_perf.py                                         # 预期：四行均为 None，耗时毫秒级且随长度接近线性
python -c "from posixre import scan; print([m.span() for m in scan(r'a*', 'bab')])"   # 预期：ImportError: cannot import name 'scan'
python -c "from posixre import finditer; print([m.span() for m in finditer(r'a*', 'aba')])"   # 预期：[(0, 1), (1, 1), (2, 3), (3, 3)]
python verify_posix_reject.py                                       # 预期：PatternError 3 与 PatternError 1
python -c "import os; print(os.path.exists('tests/oracle.py'))"      # 预期：False
deactivate
cd ..
```

---

## 第 08 题　0-1 代码生成　·　困难　·　无界面
<!-- solo-report:task=08 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/type-inference-core　A 分支：https://github.com/gy-vs/type-inference-core/tree/A　B 分支：https://github.com/gy-vs/type-inference-core/tree/B

存为 `verify_infer.mjs`（放在仓库根目录）

```javascript
import * as lib from './dist/index.js'
const parse = lib.parseSource || lib.parse
const cases = [
  'let id = fn x => x in let a = id 1 in id "s"',
  'let id = \\x -> x in let a = id 1 in id "s"',
  'let c = ref (fn x => x) in let a = (!c) 1 in (!c) "s"',
  'let c = ref (\\x -> x) in let a = (!c) 1 in (!c) "s"',
  'fn x => x x',
  '\\f -> f f',
  '{a = 1}.b'
]
for (const src of cases) {
  try {
    const r = lib.inferProgram(parse(src))
    console.log('OK', src, r.typeName || r.typeText)
  } catch (e) {
    console.log('ERR', src, e.constructor.name, (e.message || '').split('\n')[0])
  }
}
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/type-inference-core.git type-inference-core-A
cd type-inference-core-A
npm ci
npm run build
npm run build:test
node --test (Get-ChildItem dist-test/test/*.js).FullName   # 预期：42 pass
node --input-type=module -e "import { parseSource } from './dist/index.js'; console.log(typeof parseSource);"   # 预期：function
node --input-type=module -e "import { parse } from './dist/index.js'; console.log(typeof parse);"   # 预期：SyntaxError The requested module './dist/index.js' does not provide an export named 'parse'
node verify_infer.mjs   # 预期：fn 语法 let-poly 打印 OK string ；反斜杠语法 ParseError 无法识别的字符 "\\" ；ref 逃逸 TypeInferenceError 类型不匹配 ；自作用 TypeInferenceError 类型无法构造
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/type-inference-core.git type-inference-core-B
cd type-inference-core-B
npm ci
npm run build
npm run build:test
node --test --test-reporter=spec (Get-ChildItem build-test/test/*.js).FullName   # 预期：97 pass
node --input-type=module -e "import { parseSource } from './dist/index.js'; console.log(typeof parseSource);"   # 预期：SyntaxError The requested module './dist/index.js' does not provide an export named 'parseSource'
node --input-type=module -e "import { parse } from './dist/index.js'; console.log(typeof parse);"   # 预期：function
node verify_infer.mjs   # 预期：fn 语法 ParseError 无法识别的字符 ">" ；反斜杠语法 OK str ；ref 逃逸 InferError 类型不匹配 位置 1:44 ；自作用 InferError 无法构造的无限类型
cd ..
```

---

## 第 10 题　Bug 修复　·　困难　·　无界面
<!-- solo-report:task=10 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/css-visitor-core　A 分支：https://github.com/gy-vs/css-visitor-core/tree/A　B 分支：https://github.com/gy-vs/css-visitor-core/tree/B

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/css-visitor-core.git css-visitor-core-A
cd css-visitor-core-A
corepack enable
pnpm install --frozen-lockfile
npx uvu -r ts-node/register/transpile-only test visitor.test.ts   # 预期：62 passed
node -e "const postcss=require('./lib/postcss.js'); const events=[]; const plugin={postcssPlugin:'lift', Rule(rule){ events.push('Rule '+rule.selector); if(!rule.nodes) return; for (const child of rule.nodes.slice()) { if(child.type==='rule'){ child.selector=rule.selector+' '+child.selector; rule.after(child); } } }, RootExit(){ events.push('RootExit'); }}; postcss([plugin]).process('a { b { c {} } }', {from:undefined}).css; console.log(events.join(','));"   # 预期：Rule a,Rule a b,Rule a b c,RootExit,Rule a,Rule a b,RootExit
node -e "const postcss=require('./lib/postcss.js'); const order=[]; const plugin={postcssPlugin:'ins', Rule(rule){ order.push(rule.selector); if(rule.selector==='b') rule.before(postcss.rule({selector:'a2'})); }, RootExit(){ order.push('RootExit'); }}; postcss([plugin]).process('a {} b {} c {}', {from:undefined}).css; console.log(order.join(','));"   # 预期：a,b,c,RootExit
node -e "const fs=require('fs'); console.log(fs.readFileSync('lib/lazy-result.js','utf8').includes('function popStack'));"   # 预期：true
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/css-visitor-core.git css-visitor-core-B
cd css-visitor-core-B
corepack enable
pnpm install --frozen-lockfile
npx uvu -r ts-node/register/transpile-only test visitor.test.ts   # 预期：67 passed
node -e "const postcss=require('./lib/postcss.js'); const events=[]; const plugin={postcssPlugin:'lift', Rule(rule){ events.push('Rule '+rule.selector); if(!rule.nodes) return; for (const child of rule.nodes.slice()) { if(child.type==='rule'){ child.selector=rule.selector+' '+child.selector; rule.after(child); } } }, RootExit(){ events.push('RootExit'); }}; postcss([plugin]).process('a { b { c {} } }', {from:undefined}).css; console.log(events.join(','));"   # 预期：Rule a,Rule a b,Rule a b c,RootExit,Rule a,Rule a b,RootExit
node -e "const postcss=require('./lib/postcss.js'); const order=[]; const plugin={postcssPlugin:'ins', Rule(rule){ order.push(rule.selector); if(rule.selector==='b') rule.before(postcss.rule({selector:'a2'})); }, RootExit(){ order.push('RootExit'); }}; postcss([plugin]).process('a {} b {} c {}', {from:undefined}).css; console.log(order.join(','));"   # 预期：a,b,c,RootExit
node -e "const fs=require('fs'); console.log(fs.readFileSync('lib/lazy-result.js','utf8').includes('function popStack'));"   # 预期：false
cd ..
```

---

## 第 15 题　Feature 迭代　·　困难　·　无界面
<!-- solo-report:task=15 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/query-eval-core　A 分支：https://github.com/gy-vs/query-eval-core/tree/A　B 分支：https://github.com/gy-vs/query-eval-core/tree/B

存为 `verify_budget.js`（放在仓库根目录）

```javascript
const jsonata = require('./src/jsonata')
;(async () => {
  const b1 = { steps: 50, depth: 20 }
  try {
    await jsonata('$map([1..100], function($x){$x*2})').evaluate({}, undefined, b1)
    console.log('third-arg-map NO THROW', b1.stepsUsed)
  } catch (e) {
    console.log('third-arg-map', e.code, e.budgetExceeded, e.consumed, e.value, e.limit, e.position)
  }
  const b2 = { steps: 50, depth: 20 }
  try {
    await jsonata('$map([1..100], function($x){$x*2})').evaluate({}, undefined, undefined, b2)
    console.log('fourth-arg-map NO THROW', b2.stepsUsed)
  } catch (e) {
    console.log('fourth-arg-map', e.code, e.budgetExceeded, e.consumed, e.value, e.limit, e.position)
  }
  const run = async () => {
    const b = {}
    await jsonata('$sum([1..20].($*2))').evaluate({}, undefined, b)
    return [b.stepsUsed, b.depthPeak]
  }
  const x = await run()
  const y = await run()
  console.log('det-third', JSON.stringify(x), JSON.stringify(y))
})()
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/query-eval-core.git query-eval-core-A
cd query-eval-core-A
npm install
npx mocha test/budget-tests.js   # 预期：43 passing
node verify_budget.js   # 预期：third-arg-map D1014 steps 106 50 undefined 9 ；fourth-arg-map NO THROW undefined ；det-third [107,5] [107,5]
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/query-eval-core.git query-eval-core-B
cd query-eval-core-B
npm install
npx mocha test/budget.js   # 预期：45 passing
node verify_budget.js   # 预期：third-arg-map NO THROW undefined ；fourth-arg-map D1014 undefined undefined 106 steps 9 ；det-third [null,null] [null,null]
cd ..
```

---

## 第 16 题　0-1 代码生成　·　困难　·　无界面
<!-- solo-report:task=16 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/deflate-codec-core　A 分支：https://github.com/gy-vs/deflate-codec-core/tree/A　B 分支：https://github.com/gy-vs/deflate-codec-core/tree/B

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/deflate-codec-core.git deflate-codec-core-A
cd deflate-codec-core-A
npm ci
npm run build
npm test   # 预期：观察 pass 数
node --input-type=module -e "import { gzipSyncIndexed, gunzipRangeSync } from './dist/src/index.js'; const d = Buffer.from('log line\\n'.repeat(20000)); const r = gzipSyncIndexed(d, 1 << 16); console.log(r.data.length, gunzipRangeSync(r.data, r.index, 1000, 1100).length);"   # 预期：两个数字，区间长度 100
node --input-type=module -e "import { compressSeekable, inflateRange } from './dist/index.js'; console.log(typeof compressSeekable);"   # 预期：ERR_MODULE_NOT_FOUND Cannot find module .../dist/index.js
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/deflate-codec-core.git deflate-codec-core-B
cd deflate-codec-core-B
npm ci
npm run build
npm test   # 预期：观察 pass 数
node --input-type=module -e "import { gzipSyncIndexed, gunzipRangeSync } from './dist/src/index.js'; const d = Buffer.from('log line\\n'.repeat(20000)); const r = gzipSyncIndexed(d, 1 << 16); console.log(r.data.length, gunzipRangeSync(r.data, r.index, 1000, 1100).length);"   # 预期：ERR_MODULE_NOT_FOUND Cannot find module .../dist/src/index.js
node --input-type=module -e "import { compressSeekable, inflateRange } from './dist/index.js'; console.log(typeof compressSeekable);"   # 预期：function
cd ..
```

---

## 第 17 题　0-1 代码生成　·　地狱　·　无界面
<!-- solo-report:task=17 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/consensus-replication-core　A 分支：https://github.com/gy-vs/consensus-replication-core/tree/A　B 分支：https://github.com/gy-vs/consensus-replication-core/tree/B

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/consensus-replication-core.git consensus-replication-core-A
cd consensus-replication-core-A
npm install
npm run build
npm test   # 预期：Could not find 'dist/test'
node dist/scripts/smoke.js 1   # 预期：打印 seed/ops/linearizable: false ，随后 search step budget exhausted 与 operations that could not be placed
node --input-type=module -e "import { step } from './dist/core/index.js'; console.log(typeof step);"   # 预期：function
node --input-type=module -e "import { checkLinearizable } from './dist/checker/index.js'; console.log(typeof checkLinearizable);"   # 预期：function
node --input-type=module -e "import { MemoryStorage } from './dist/src/raft/storage.js'; console.log(typeof MemoryStorage);"   # 预期：ERR_MODULE_NOT_FOUND
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/consensus-replication-core.git consensus-replication-core-B
cd consensus-replication-core-B
npm install
npm run build
npm test   # 预期：Could not find 'dist/src/tests/'
node dist/scripts/smoke.js 1   # 预期：MODULE_NOT_FOUND
node --input-type=module -e "import { step } from './dist/core/index.js'; console.log(typeof step);"   # 预期：ERR_MODULE_NOT_FOUND
node --input-type=module -e "import { checkLinearizable } from './dist/checker/index.js'; console.log(typeof checkLinearizable);"   # 预期：ERR_MODULE_NOT_FOUND
node --input-type=module -e "import { MemoryStorage } from './dist/src/raft/storage.js'; console.log(typeof MemoryStorage);"   # 预期：function
cd ..
```

---

## 第 24 题　Bug 修复　·　困难　·　无界面
<!-- solo-report:task=24 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/css-custom-prop-core　A 分支：https://github.com/gy-vs/css-custom-prop-core/tree/A　B 分支：https://github.com/gy-vs/css-custom-prop-core/tree/B

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/css-custom-prop-core.git css-custom-prop-core-A
cd css-custom-prop-core-A
corepack enable
pnpm install --frozen-lockfile
npx uvu -r ts-node/register/transpile-only test stringify.test.ts   # 预期：128 passed
node -e "const postcss=require('./lib/postcss.js'); const css='a{*--x: 1 /* c */}'; const out=postcss.parse(css).toString(); console.log(JSON.stringify(out), out===css);"   # 预期："a{*--x: 1 /* c */}" true
node -e "const postcss=require('./lib/postcss.js'); const css='a{*color: red /* c */}'; console.log(postcss.parse(css).toString()===css);"   # 预期：true
node -e "const postcss=require('./lib/postcss.js'); const root=postcss.parse('a { *--x: red /* note */ }'); console.log(root.toString()==='a { *--x: red /* note */ }'); root.first.first.value='blue'; console.log(JSON.stringify(root.toString()));"   # 预期：true 然后 "a { *--x: blue}"
node ./node_modules/uvu/bin.js -r ts-node/register/transpile-only test stringifier.test   # 预期：观察 passed 数
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/css-custom-prop-core.git css-custom-prop-core-B
cd css-custom-prop-core-B
corepack enable
pnpm install --frozen-lockfile
npx uvu -r ts-node/register/transpile-only test stringify.test.ts   # 预期：32 passed
node -e "const postcss=require('./lib/postcss.js'); const css='a{*--x: 1 /* c */}'; const out=postcss.parse(css).toString(); console.log(JSON.stringify(out), out===css);"   # 预期："a{*--x: 1 /* c */}" true
node -e "const postcss=require('./lib/postcss.js'); const css='a{*color: red /* c */}'; console.log(postcss.parse(css).toString()===css);"   # 预期：true
node -e "const postcss=require('./lib/postcss.js'); const root=postcss.parse('a { *--x: red /* note */ }'); console.log(root.toString()==='a { *--x: red /* note */ }'); root.first.first.value='blue'; console.log(JSON.stringify(root.toString()));"   # 预期：true 然后 "a { *--x: blue}"
node ./node_modules/uvu/bin.js -r ts-node/register/transpile-only test stringifier.test   # 预期：46 passed
cd ..
```

---

## 第 26 题　Bug 修复　·　困难　·　无界面
<!-- solo-report:task=26 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/js-module-import-core　A 分支：https://github.com/gy-vs/js-module-import-core/tree/A　B 分支：https://github.com/gy-vs/js-module-import-core/tree/B

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/js-module-import-core.git js-module-import-core-A
cd js-module-import-core-A
npm ci
node test/compress.js dynamic-import.js   # 预期：Passed 8 test cases
node --input-type=module -e "import {minify} from './main.js'; const r = await minify('function go(){var P=\'/routes/\';return import(P+\'home\'+\'.js\')}', {compress:true, mangle:false}); console.log(r.code);"   # 预期：function go(){return import("/routes/home.js")}
node --input-type=module -e "import {minify} from './main.js'; const r = await minify('import((sideEffect(),\'/routes/home.js\'));', {compress:true, mangle:false}); console.log(r.code);"   # 预期：import(sideEffect(),"/routes/home.js");
node --input-type=module -e "import {minify} from './main.js'; const r = await minify('function go(){return import(true?\'home.js\':\'about.js\')}', {compress:true, mangle:false}); console.log(r.code);"   # 预期：function go(){return import("home.js")}
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/js-module-import-core.git js-module-import-core-B
cd js-module-import-core-B
npm ci
node test/compress.js dynamic-import.js   # 预期：Passed 11 test cases
node --input-type=module -e "import {minify} from './main.js'; const r = await minify('function go(){var P=\'/routes/\';return import(P+\'home\'+\'.js\')}', {compress:true, mangle:false}); console.log(r.code);"   # 预期：function go(){return import("/routes/home.js")}
node --input-type=module -e "import {minify} from './main.js'; const r = await minify('import((sideEffect(),\'/routes/home.js\'));', {compress:true, mangle:false}); console.log(r.code);"   # 预期：import((sideEffect(),"/routes/home.js"));
node --input-type=module -e "import {minify} from './main.js'; const r = await minify('function go(){return import(true?\'home.js\':\'about.js\')}', {compress:true, mangle:false}); console.log(r.code);"   # 预期：function go(){return import("home.js")}
cd ..
```

---

## 第 33 题　Feature 迭代　·　困难　·　无界面
<!-- solo-report:task=33 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/css-calc-type-core　A 分支：https://github.com/gy-vs/css-calc-type-core/tree/A　B 分支：https://github.com/gy-vs/css-calc-type-core/tree/B

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/css-calc-type-core.git css-calc-type-core-A
cd css-calc-type-core-A
npm ci
npx mocha lib/__tests/lexer-math-check.js --require lib/__tests/helpers/setup.js --reporter spec   # 预期：40 passing
node --input-type=module -e "import { lexer } from './lib/index.js'; const r = lexer.matchProperty('width', 'calc(100% - 16)'); console.log(r.matched, r.error && r.error.rawMessage);"   # 预期：false Incompatible operands for `-`: `percentage` and `number` can't be combined
node --input-type=module -e "import { lexer } from './lib/index.js'; const r = lexer.matchProperty('line-height', 'calc(100% - 1px)'); console.log(r.matched, r.error && r.error.rawMessage);"   # 预期：false Incompatible operands for `-`: `percentage` and `length` can't be combined
node --input-type=module -e "import { lexer } from './lib/index.js'; const r = lexer.matchProperty('opacity', 'calc(1 + 50%)'); console.log(r.matched, r.error && r.error.rawMessage);"   # 预期：false Incompatible operands for `+`: `number` and `percentage` can't be combined
node --input-type=module -e "import { lexer } from './lib/index.js'; const r = lexer.matchProperty('width', 'calc(0 + 16px)'); console.log(r.matched, r.error && r.error.rawMessage);"   # 预期：true
node --input-type=module -e "import { lexer } from './lib/index.js'; const r = lexer.matchProperty('width', 'calc(100px / (1 - 1))'); console.log(r.matched, r.error && r.error.rawMessage);"   # 预期：false Division by zero is not allowed
node --input-type=module -e "import { lexer } from './lib/index.js'; const r = lexer.matchProperty('border-width', 'calc(100% - 16px)'); console.log(r.matched, r.error && r.error.rawMessage);"   # 预期：false Incompatible operands for `-`: `percentage` and `length` can't be combined
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/css-calc-type-core.git css-calc-type-core-B
cd css-calc-type-core-B
npm ci
npx mocha lib/__tests/lexer-match-calc.js --require lib/__tests/helpers/setup.js --reporter spec   # 预期：105 passing
node --input-type=module -e "import { lexer } from './lib/index.js'; const r = lexer.matchProperty('width', 'calc(100% - 16)'); console.log(r.matched, r.error && r.error.rawMessage);"   # 预期：false calc() evaluates to <number> which doesn't match the expected type <length>
node --input-type=module -e "import { lexer } from './lib/index.js'; const r = lexer.matchProperty('line-height', 'calc(100% - 1px)'); console.log(r.matched, r.error && r.error.rawMessage);"   # 预期：true
node --input-type=module -e "import { lexer } from './lib/index.js'; const r = lexer.matchProperty('opacity', 'calc(1 + 50%)'); console.log(r.matched, r.error && r.error.rawMessage);"   # 预期：true
node --input-type=module -e "import { lexer } from './lib/index.js'; const r = lexer.matchProperty('width', 'calc(0 + 16px)'); console.log(r.matched, r.error && r.error.rawMessage);"   # 预期：false Incompatible types for "+" operator: <number> and <length>
node --input-type=module -e "import { lexer } from './lib/index.js'; const r = lexer.matchProperty('width', 'calc(100px / (1 - 1))'); console.log(r.matched, r.error && r.error.rawMessage);"   # 预期：true
node --input-type=module -e "import { lexer } from './lib/index.js'; const r = lexer.matchProperty('border-width', 'calc(100% - 16px)'); console.log(r.matched, r.error && r.error.rawMessage);"   # 预期：false Percentage is not allowed in this context
cd ..
```

---

## 第 35 题　Bug 修复　·　困难　·　无界面
<!-- solo-report:task=35 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/css-input-map-core　A 分支：https://github.com/gy-vs/css-input-map-core/tree/A　B 分支：https://github.com/gy-vs/css-input-map-core/tree/B

存为 `verify_map.js`（放在仓库根目录）

```javascript
const fs = require('fs')
const path = require('path')
const os = require('os')
const { parse } = require('./lib/postcss.js')
const root = fs.mkdtempSync(path.join(os.tmpdir(), 'sr35-'))
const upload = path.join(root, 'upload')
const secret = path.join(root, 'secret')
fs.mkdirSync(upload)
fs.mkdirSync(secret)
fs.writeFileSync(path.join(secret, 'config.map'), JSON.stringify({ version: 3, sources: ['x'], names: [], mappings: '', sourcesContent: ['SECRET'] }))
fs.symlinkSync(path.join(secret, 'config.map'), path.join(upload, 'evil.map'))
const r1 = parse('a{}\n/*# sourceMappingURL=evil.map */', { from: path.join(upload, 'style.css') })
console.log('outside', !!r1.source.input.map)
fs.writeFileSync(path.join(upload, 'ok.map'), JSON.stringify({ version: 3, sources: [], names: [], mappings: '' }))
const r2 = parse('a{}\n/*# sourceMappingURL=ok.map */', { from: path.join(upload, 'style.css') })
console.log('legit', !!(r2.source.input.map && r2.source.input.map.text))
fs.symlinkSync(path.join(upload, 'missing.map'), path.join(upload, 'broken.map'))
let threw = false
try {
  parse('a{}\n/*# sourceMappingURL=broken.map */', { from: path.join(upload, 'style.css') })
} catch (e) {
  threw = true
}
console.log('broken-nocrash', !threw)
const b64 = Buffer.from(JSON.stringify({ version: 3, sources: [], names: [], mappings: '' })).toString('base64')
const r3 = parse('a{}\n/*# sourceMappingURL=data:application/json;base64,' + b64 + ' */')
console.log('inline', !!r3.source.input.map)
fs.rmSync(root, { recursive: true, force: true })
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/css-input-map-core.git css-input-map-core-A
cd css-input-map-core-A
corepack enable
pnpm install --frozen-lockfile
node ./node_modules/uvu/bin.js -r ts-node/register/transpile-only test "previous-map\\.test\\.ts$"   # 预期：37 passed
node verify_map.js   # 预期：outside false ；legit true ；broken-nocrash true ；inline true
node -e "const P=require('./lib/previous-map.js'); console.log(typeof P.prototype.isInsideDir);"   # 预期：function
node -e "const fs=require('fs'); console.log(fs.readFileSync('lib/previous-map.js','utf8').includes('c8 ignore start'));"   # 预期：false
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/css-input-map-core.git css-input-map-core-B
cd css-input-map-core-B
corepack enable
pnpm install --frozen-lockfile
node ./node_modules/uvu/bin.js -r ts-node/register/transpile-only test "previous-map\\.test\\.ts$"   # 预期：35 passed
node verify_map.js   # 预期：outside false ；legit true ；broken-nocrash true ；inline true
node -e "const P=require('./lib/previous-map.js'); console.log(typeof P.prototype.isInsideDir);"   # 预期：undefined
node -e "const fs=require('fs'); console.log(fs.readFileSync('lib/previous-map.js','utf8').includes('c8 ignore start'));"   # 预期：true
cd ..
```

---

## 第 36 题　0-1 代码生成　·　困难　·　无界面
<!-- solo-report:task=36 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/http-cache-core　A 分支：https://github.com/gy-vs/http-cache-core/tree/A　B 分支：https://github.com/gy-vs/http-cache-core/tree/B

存为 `verify_36.mjs`（放在仓库根目录）

```javascript
import * as k from './dist/index.js';

const t0 = Date.UTC(2026, 0, 1);

function httpDate(ms) {
  return new Date(ms).toUTCString();
}

if (k.ResponsePolicy) {
  const policy = new k.ResponsePolicy(
    { method: 'GET', url: 'https://x/', headers: {} },
    {
      status: 200,
      headers: { date: httpDate(t0), 'cache-control': 'max-age=10, must-revalidate' },
    },
    { requestTimeMs: t0, responseTimeMs: t0 },
    { now: () => t0 + 20000 },
  );
  const d = policy.evaluate({ 'cache-control': 'max-stale=9999' });
  console.log('must-revalidate+max-stale', d.state, d.reason || '');
} else {
  const variant = k.createVariant({
    request: k.normalizeRequest({ method: 'GET', target: 'https://x/a' }),
    response: k.normalizeResponse({
      status: 200,
      headers: { date: httpDate(t0), 'cache-control': 'max-age=60, must-revalidate' },
    }),
    requestTime: t0,
    responseTime: t0,
  });
  const ev = k.evaluate({
    variant,
    request: k.normalizeRequest({
      method: 'GET',
      target: 'https://x/a',
      headers: { 'cache-control': 'max-stale=100' },
    }),
    now: t0 + 70000,
  });
  console.log('must-revalidate+max-stale', ev.status, String(ev.serve));
}

const cache = new k.Cache({ now: () => t0, clock: () => t0 });
const gzipReq = { method: 'GET', url: 'https://x/v', target: 'https://x/v', headers: { 'accept-encoding': 'gzip' } };
const identReq = { method: 'GET', url: 'https://x/v', target: 'https://x/v', headers: { 'accept-encoding': 'identity' } };
const stored = {
  status: 200,
  headers: { 'cache-control': 'max-age=1', vary: 'accept-encoding', etag: '"g"', date: httpDate(t0) },
};
if (cache.put.length === 1) {
  cache.put({
    request: gzipReq,
    response: stored,
    times: { requestTimeMs: t0, responseTimeMs: t0 },
  });
  cache.put({
    request: identReq,
    response: { status: 200, headers: { 'cache-control': 'max-age=1', vary: 'accept-encoding', etag: '"i"', date: httpDate(t0) } },
    times: { requestTimeMs: t0, responseTimeMs: t0 },
  });
} else {
  cache.put({ request: gzipReq, response: stored, requestTime: t0, responseTime: t0 }, t0);
  cache.put(
    {
      request: identReq,
      response: { status: 200, headers: { 'cache-control': 'max-age=1', vary: 'accept-encoding', etag: '"i"', date: httpDate(t0) } },
      requestTime: t0,
      responseTime: t0,
    },
    t0,
  );
}

if (typeof cache.handle === 'function') {
  const later = new k.Cache({ now: () => t0 + 5000 });
  later.put({
    request: gzipReq,
    response: stored,
    times: { requestTimeMs: t0, responseTimeMs: t0 },
  });
  later.put({
    request: identReq,
    response: { status: 200, headers: { 'cache-control': 'max-age=1', vary: 'accept-encoding', etag: '"i"', date: httpDate(t0) } },
    times: { requestTimeMs: t0, responseTimeMs: t0 },
  });
  const before = later.match(identReq);
  await later.handle(gzipReq, async () => ({
    response: { status: 200, headers: { 'cache-control': 'no-store' } },
    times: { requestTimeMs: t0 + 5000, responseTimeMs: t0 + 5000 },
  }));
  const after = later.match(identReq);
  console.log('vary-after-nostore', before.kind, after.kind);
} else {
  const later = new k.Cache({ clock: () => t0 + 70000 });
  later.put({ request: gzipReq, response: stored, requestTime: t0, responseTime: t0 }, t0);
  later.put(
    {
      request: identReq,
      response: { status: 200, headers: { 'cache-control': 'max-age=1', vary: 'accept-encoding', etag: '"i"', date: httpDate(t0) } },
      requestTime: t0,
      responseTime: t0,
    },
    t0,
  );
  const hit = later.lookup(gzipReq, t0 + 70000);
  const identBefore = later.lookup(identReq, t0 + 70000);
  await later.revalidate(hit, async () => ({
    status: 200,
    headers: { 'cache-control': 'no-store' },
    requestTime: t0 + 70000,
    responseTime: t0 + 70000,
  }));
  const identAfter = later.lookup(identReq, t0 + 70000);
  console.log('vary-after-nostore', identBefore.kind, identAfter.kind);
}

console.log('exports', Object.keys(k).sort().join(','));
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/http-cache-core.git http-cache-core-A
cd http-cache-core-A
npm ci
npm run build
npm test   # 预期：观察 passed 数
node verify_36.mjs   # 预期：must-revalidate+max-stale stale-serve ；vary-after-nostore revalidate miss ；exports 含 ResponsePolicy
cd ..
```


B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/http-cache-core.git http-cache-core-B
cd http-cache-core-B
npm ci
npm run build
npm test   # 预期：观察 passed 数
node verify_36.mjs   # 预期：must-revalidate+max-stale stale-revalidate false ；vary-after-nostore hit hit ；exports 含 evaluate
cd ..
```

---

## 第 37 题　Feature 迭代　·　困难　·　无界面
<!-- solo-report:task=37 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/yaml-emit-core　A 分支：https://github.com/gy-vs/yaml-emit-core/tree/A　B 分支：https://github.com/gy-vs/yaml-emit-core/tree/B

存为 `verify_37.mjs`（放在仓库根目录）

```javascript
import * as YAML from './dist/index.js';

const jobs = [
  { name: 'build', image: 'app:1.2', env: 'prod', retries: 3 },
  { name: 'test', image: 'app:1.2', env: 'prod', retries: 3 },
  { name: 'deploy', image: 'app:1.2', env: 'prod', retries: 3 },
];

function emit(label, opts) {
  const out = YAML.stringify(jobs, opts);
  const hasMerge = out.includes('<<:');
  const mergeCount = (out.match(/<<:/g) || []).length;
  console.log(label, 'merge', hasMerge, 'count', mergeCount);
}

emit('mergeCommonEntries', { merge: true, mergeCommonEntries: true });
emit('mergeCommonKeys', { version: '1.1', mergeCommonKeys: true });
emit('neg-threshold-entries', { merge: true, mergeCommonEntries: -5 });
emit('neg-threshold-keys', { version: '1.1', mergeCommonKeys: -5 });

const shared = { NODE: '20' };
const aliased = [
  { name: 'build', env: shared, retries: 3, extra: 'a' },
  { name: 'test', env: shared, retries: 3, extra: 'b' },
];
const withAliasEntries = YAML.stringify(aliased, { merge: true, mergeCommonEntries: true });
const withAliasKeys = YAML.stringify(aliased, { version: '1.1', mergeCommonKeys: true });
console.log('alias-entries-has-merge', withAliasEntries.includes('<<:'));
console.log('alias-keys-has-merge', withAliasKeys.includes('<<:'));
console.log('roundtrip-entries', JSON.stringify(YAML.parse(YAML.stringify(jobs, { merge: true, mergeCommonEntries: true }), { merge: true })) === JSON.stringify(jobs));
console.log('roundtrip-keys', JSON.stringify(YAML.parse(YAML.stringify(jobs, { version: '1.1', mergeCommonKeys: true }), { version: '1.1' })) === JSON.stringify(jobs));
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/yaml-emit-core.git yaml-emit-core-A
cd yaml-emit-core-A
npm ci
npm run build
npx vitest run tests/doc/mergeCommonEntries.ts   # 预期：观察 passed 数
node verify_37.mjs   # 预期：mergeCommonEntries merge true count 3 ；mergeCommonKeys merge false count 0 ；neg-threshold-entries merge false ；neg-threshold-keys merge false
cd ..
```


B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/yaml-emit-core.git yaml-emit-core-B
cd yaml-emit-core-B
npm ci
npm run build
npx vitest run tests/doc/mergeCommonKeys.ts   # 预期：观察 passed 数
node verify_37.mjs   # 预期：mergeCommonEntries merge false count 0 ；mergeCommonKeys merge true count 3 ；neg-threshold-entries merge false ；neg-threshold-keys merge true count 3
cd ..
```

---

## 第 38 题　Bug 修复　·　困难　·　无界面
<!-- solo-report:task=38 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/yaml-alias-core　A 分支：https://github.com/gy-vs/yaml-alias-core/tree/A　B 分支：https://github.com/gy-vs/yaml-alias-core/tree/B

存为 `verify_38.mjs`（放在仓库根目录）

```javascript
import * as YAML from './dist/index.js';

function show(label, fn) {
  try {
    const v = fn();
    console.log(label, 'ok', typeof v);
  } catch (e) {
    console.log(label, e.name, String(e.message).split('\n')[0]);
  }
}

show('circular', () => YAML.parse('&A { <<: *A, B: b }\n', { merge: true }));
show('max0', () => YAML.parse('a: &a { x: 1 }\nb: { <<: *a }', { merge: true, maxAliasCount: 0 }));
show('max1-pass', () => YAML.parse('a: &a { x: 1 }\nb: { <<: *a }', { merge: true, maxAliasCount: 2 }));
show('max1-fail', () => YAML.parse('a: &a { x: 1 }\nb: { <<: *a }', { merge: true, maxAliasCount: 1 }));

let bomb = 'n0: &n0 { v: 1 }\n';
for (let i = 1; i <= 8; i++) {
  bomb += `n${i}: &n${i} { <<: [*n${i - 1}, *n${i - 1}] }\n`;
}
const t0 = Date.now();
show('merge-bomb-8', () => YAML.parse(bomb, { merge: true }));
console.log('bomb-ms', Date.now() - t0);

show('forward', () => YAML.parse('a:\n  <<: *B\nB: &B\n  x: 1\n', { merge: true }));
show('shallow', () => YAML.parse('hello: &a\n  world: 2\nfoo:\n  <<: *a\n', { merge: true }));
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/yaml-alias-core.git yaml-alias-core-A
cd yaml-alias-core-A
npm ci
npm run build
npx vitest run tests/doc/parse.ts tests/doc/anchors.ts   # 预期：观察 passed 数
node verify_38.mjs   # 预期：circular ReferenceError Circular alias reference in merge key ；max0 Alias resolution is disabled ；max1-fail Excessive alias count ；shallow ok
cd ..
```


B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/yaml-alias-core.git yaml-alias-core-B
cd yaml-alias-core-B
npm ci
npm run build
npx vitest run tests/doc/parse.ts tests/doc/anchors.ts   # 预期：观察 passed 数
node verify_38.mjs   # 预期：circular ReferenceError Excessive alias count indicates a resource exhaustion attack ；max0 Alias resolution is disabled ；max1-fail Excessive alias count ；shallow ok
cd ..
```

---

## 第 39 题　Feature 迭代　·　困难　·　无界面
<!-- solo-report:task=39 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/chrono-recur-core　A 分支：https://github.com/gy-vs/chrono-recur-core/tree/A　B 分支：https://github.com/gy-vs/chrono-recur-core/tree/B

存为 `verify_39.js`（放在仓库根目录）

```javascript
const luxon = require('./build/node/luxon.js');
const { DateTime } = luxon;
const Rule = luxon.RecurrenceRule || luxon.Recurrence;
const make = (text, start) => (Rule.fromString ? Rule.fromString(text, start) : Rule.fromRRule(text, start));

const start = DateTime.fromObject({ year: 2026, month: 1, day: 1, hour: 9 }, { zone: 'America/New_York' });
const yearly = make('FREQ=YEARLY;BYMONTH=5;BYDAY=-1MO;BYSETPOS=1', start);
console.log('yearly-setpos', yearly.take(3).map((d) => d.toISODate()).join(','));

const monthly = DateTime.fromObject({ year: 2026, month: 5, day: 1, hour: 9 }, { zone: 'America/New_York' });
const lastWd = make('FREQ=MONTHLY;BYDAY=MO,TU,WE,TH,FR;BYSETPOS=-1', monthly);
console.log('last-weekday', lastWd.take(2).map((d) => d.toISODate()).join(','));

const earlyUntil = DateTime.fromObject({ year: 2026, month: 6, day: 1, hour: 9 }, { zone: 'America/New_York' });
try {
  const r = make('FREQ=DAILY;UNTIL=20260101T000000Z', earlyUntil);
  console.log('until-before', r.take(3).length);
} catch (e) {
  console.log('until-before', e.name);
}

try {
  const r = make('FREQ=DAILY;BYMONTHDAY=1', monthly);
  console.log('daily-bymonthday', r.take(2).map((d) => d.toISODate()).join(','));
} catch (e) {
  console.log('daily-bymonthday', e.name, String(e.message).slice(0, 80));
}

const onlyMonth = make('FREQ=YEARLY;BYMONTH=5', start);
console.log('yearly-bymonth-only', onlyMonth.take(1).map((d) => d.toISODate()).join(','));
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/chrono-recur-core.git chrono-recur-core-A
cd chrono-recur-core-A
npm ci
npm run build-node
$env:TZ = "America/New_York"
npx jest test/recurrenceRule.test.js   # 预期：观察 passed 数
node verify_39.js   # 预期：yearly-setpos 2026-01-01,2026-05-25,2027-05-31 ；last-weekday 2026-05-01,2026-05-29 ；until-before Error ；daily-bymonthday 2026-05-01,2026-06-01
cd ..
```


B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/chrono-recur-core.git chrono-recur-core-B
cd chrono-recur-core-B
npm ci
npm run build-node
$env:TZ = "America/New_York"
npx jest test/recurrence   # 预期：观察 passed 数
node verify_39.js   # 预期：yearly-setpos 2026-01-01,2026-05-04,2027-05-03 ；last-weekday 2026-05-01,2026-05-29 ；until-before 0 ；daily-bymonthday Error Invalid recurrence rule: BYMONTHDAY cannot be used with FREQ=DAILY
cd ..
```

---

## 第 40 题　代码重构　·　困难　·　无界面
<!-- solo-report:task=40 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/chrono-format-core　A 分支：https://github.com/gy-vs/chrono-format-core/tree/A　B 分支：https://github.com/gy-vs/chrono-format-core/tree/B

存为 `verify_40.js`（放在仓库根目录）

```javascript
const fs = require('fs');
const { DateTime, Settings } = require('./build/node/luxon.js');

console.log('has-zoneNameCache', fs.existsSync('test/impl/zoneNameCache.test.js'));
console.log('has-zoneInfoCache', fs.existsSync('test/impl/zoneInfoCache.test.js'));
const util = fs.readFileSync('src/impl/util.js', 'utf8');
console.log('has-getCachedZoneNameDTF', util.includes('getCachedZoneNameDTF'));
console.log('mentions-key-bound', /key space|product of|tens of zones|cannot grow/i.test(util));

let n = 0;
const Orig = Intl.DateTimeFormat;
function Wrapped(locales, options) {
  n += 1;
  return new Orig(locales, options);
}
Wrapped.prototype = Orig.prototype;
Wrapped.supportedLocalesOf = Orig.supportedLocalesOf.bind(Orig);
Intl.DateTimeFormat = Wrapped;

const winter = DateTime.fromObject({ year: 2026, month: 1, day: 15, hour: 12 }, { zone: 'America/New_York' });
const summer = DateTime.fromObject({ year: 2026, month: 7, day: 15, hour: 12 }, { zone: 'America/New_York' });
const a = winter.toFormat('ZZZZ');
const b = winter.toFormat('ZZZZ');
const c = summer.toFormat('ZZZZ');
console.log('formats', a, c, 'constructs', n);
Settings.resetCaches();
winter.toFormat('ZZZZ');
console.log('after-reset', n);
Intl.DateTimeFormat = Orig;
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/chrono-format-core.git chrono-format-core-A
cd chrono-format-core-A
npm ci --no-audit --no-fund
npm run build-node
$env:TZ = "America/New_York"
npx jest test/impl/zoneNameCache.test.js   # 预期：观察 passed 数
node verify_40.js   # 预期：has-zoneNameCache true ；has-zoneInfoCache false ；has-getCachedZoneNameDTF true ；mentions-key-bound true ；formats EST EDT constructs 4 ；after-reset 5
cd ..
```


B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/chrono-format-core.git chrono-format-core-B
cd chrono-format-core-B
npm ci --no-audit --no-fund
npm run build-node
$env:TZ = "America/New_York"
npx jest test/impl/zoneInfoCache.test.js   # 预期：观察 passed 数
node verify_40.js   # 预期：has-zoneNameCache false ；has-zoneInfoCache true ；has-getCachedZoneNameDTF false ；mentions-key-bound false ；formats EST EDT constructs 4 ；after-reset 5
cd ..
```

---

## 第 41 题　Feature 迭代　·　困难　·　无界面
<!-- solo-report:task=41 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/js-using-decl-core　A 分支：https://github.com/gy-vs/js-using-decl-core/tree/A　B 分支：https://github.com/gy-vs/js-using-decl-core/tree/B

存为 `verify_41.js`（放在仓库根目录）

```javascript
const fs = require('fs');
const acorn = require('./acorn');
let pluginErr = 'ok';
let P;
try {
  const plugin = require('./acorn-using');
  P = acorn.Parser.extend(plugin);
} catch (e) {
  pluginErr = e.name + ' ' + e.message;
}
console.log('load-plugin', pluginErr);
console.log('has-tests-using', fs.existsSync('test/tests-using.js'));

function tryParse(label, src, extra) {
  if (!P) {
    console.log(label, 'no-parser');
    return;
  }
  try {
    const ast = P.parse(src, Object.assign({ ecmaVersion: 2022 }, extra || {}));
    const first = ast.body[0];
    console.log(label, 'ok', ast.body.length, first.type, first.kind || '');
  } catch (e) {
    console.log(label, e.name, String(e.message).split('\n')[0]);
  }
}

tryParse('using-decl', 'using handle = open(path)');
tryParse('newline', 'using\nx = 1');
tryParse('for-of-ident', 'for (using of xs) {}');
tryParse('for-await-using', 'async function f() { for await (using x of y) {} }');
tryParse('using-await', 'using await = 1');
tryParse('ident-using', 'using = 1');
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/js-using-decl-core.git js-using-decl-core-A
cd js-using-decl-core-A
npm install
npm run build
node test/run.js   # 预期：观察 passed 数，无 using 用例
node verify_41.js   # 预期：load-plugin ok ；has-tests-using false ；using-decl SyntaxError Unexpected token (1:6) ；newline ok 2 ；ident-using ok
cd ..
```


B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/js-using-decl-core.git js-using-decl-core-B
cd js-using-decl-core-B
npm install
npm run build
node test/run.js   # 预期：观察 passed 数，含 using 用例
node verify_41.js   # 预期：load-plugin ok ；has-tests-using true ；using-decl ok 1 VariableDeclaration using ；newline ok 2 ；ident-using ok
cd ..
```

---

## 第 42 题　Bug 修复　·　困难　·　无界面
<!-- solo-report:task=42 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/js-token-context-core　A 分支：https://github.com/gy-vs/js-token-context-core/tree/A　B 分支：https://github.com/gy-vs/js-token-context-core/tree/B

存为 `verify_42.js`（放在仓库根目录）

```javascript
const acorn = require('./acorn/dist/acorn.js');
const cases = ['foo.if() / 2', 'foo.while() / 2', 'foo.for() / 2', 'foo.with() / 2', 'foo.iff() / 2', 'foo.class() / 2'];
for (const c of cases) {
  try {
    const ast = acorn.parse(c, { ecmaVersion: 2020 });
    console.log('stmt', c, ast.body.length, ast.body[0].expression.type);
  } catch (e) {
    console.log('stmt', c, e.name, String(e.message).split(':')[0]);
  }
}

try {
  const a = acorn.parse('foo.if()\n/a/g.test(x)', { ecmaVersion: 2020 });
  console.log('newline', a.body.length, a.body[0].expression.type, a.body[0].expression.operator || '');
} catch (e) {
  console.log('newline', e.name);
}

try {
  const labels = [...acorn.tokenizer('foo.if() / 2', { ecmaVersion: 2020 })].map((t) => t.type.label).join(' ');
  console.log('tokens', labels);
} catch (e) {
  console.log('tokens', e.name);
}

try {
  const loose = require('./acorn-loose/dist/acorn-loose.js');
  console.log('loose-newline', loose.parse('foo.if()\n/a/g.test(x)', { ecmaVersion: 2020 }).body.length);
} catch (e) {
  console.log('loose-newline', e.name, String(e.message).split('\n')[0]);
}

try {
  const opt = acorn.parse('foo?.if() / 2', { ecmaVersion: 2020 });
  console.log('optional', opt.body[0].expression.operator);
} catch (e) {
  console.log('optional', e.name);
}
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/js-token-context-core.git js-token-context-core-A
cd js-token-context-core-A
npm install
npm run build
node test/run.js   # 预期：观察 passed 数
node verify_42.js   # 预期：foo.if() / 2 等均为 1 BinaryExpression ；newline 1 BinaryExpression / ；tokens SyntaxError ；loose-newline 1 ；optional /
cd ..
```


B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/js-token-context-core.git js-token-context-core-B
cd js-token-context-core-B
npm install
npm run build
node test/run.js   # 预期：观察 passed 数
node verify_42.js   # 预期：foo.if() / 2 等均为 1 BinaryExpression ；newline 1 BinaryExpression / ；tokens name . if ( ) / num ；loose-newline 1 ；optional /
cd ..
```

---

## 第 43 题　Bug 修复　·　困难　·　无界面
<!-- solo-report:task=43 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/css-generator-core　A 分支：https://github.com/gy-vs/css-generator-core/tree/A　B 分支：https://github.com/gy-vs/css-generator-core/tree/B

存为 `verify_43.mjs`（放在仓库根目录）

```javascript
import { parse, generate } from './lib/index.js';
import * as tokenBefore from './lib/generator/token-before.js';

console.log('span-hash', generate(parse('span#foo{color:red}', { parseRulePrelude: false })));
console.log('li-item', generate(parse('li.item{color:red}', { parseRulePrelude: false })));
console.log('custom-prop', generate(parse('x{--a:1%var(--b)#ff0000}')));
console.log('media', generate(parse('@media screen{a{color:red}}', { parseAtrulePrelude: false })));
console.log('spaces-kept', generate(parse('a{margin:1px 2px;border:1px solid #ff0000}')));
console.log('token-before-keys', Object.keys(tokenBefore).sort().join(','));
try {
  console.log('mode-none', generate(parse('a{margin:1px 2px}'), { mode: 'none' }));
} catch (e) {
  console.log('mode-none', e.name);
}
const reparsed = generate(parse(generate(parse('span#foo{color:red}', { parseRulePrelude: false }))));
console.log('roundtrip', reparsed);
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/css-generator-core.git css-generator-core-A
cd css-generator-core-A
npm ci
npm test   # 预期：观察 passed 数
node verify_43.mjs   # 预期：span-hash span#foo{color:red} ；li-item li.item{color:red} ；custom-prop 原样 ；token-before-keys safe,spec ；mode-none a{margin:1px 2px} ；roundtrip span#foo{color:red}
cd ..
```


B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/css-generator-core.git css-generator-core-B
cd css-generator-core-B
npm ci
npm test   # 预期：观察 passed 数
node verify_43.mjs   # 预期：span-hash span#foo{color:red} ；li-item li.item{color:red} ；custom-prop 原样 ；token-before-keys none,safe,spec ；mode-none a{margin:1px2px} ；roundtrip span#foo{color:red}
cd ..
```

---

## 第 45 题　Bug 修复　·　困难　·　无界面
<!-- solo-report:task=45 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/query-signature-core　A 分支：https://github.com/gy-vs/query-signature-core/tree/A　B 分支：https://github.com/gy-vs/query-signature-core/tree/B

存为 `verify_45.js`（放在仓库根目录）

```javascript
const jsonata = require('./src/jsonata.js');
const fs = require('fs');

function ev(expr) {
  return jsonata(expr).evaluate({});
}

Promise.all([
  ev('λ($arg1,$arg2)<n+>{[$arg1,$arg2]}(1,2)'),
  ev('λ($arg1,$arg2,$s)<n+s:a<n>>{[$arg1,$arg2,$s]}(1,2,"a")'),
  ev('λ($a,$b)<a<n>+:o>{[$a[0],$b[0]]}([1,9],[2,8],[3])'),
  ev('λ($arg1,$arg2)<n+>{[$arg1,$arg2]}(1)'),
]).then((rows) => {
  console.log('nplus', JSON.stringify(rows[0]));
  console.log('nplus-s', JSON.stringify(rows[1]));
  console.log('array-plus', JSON.stringify(rows[2]));
  console.log('nplus-one', JSON.stringify(rows[3]));
  const src = fs.readFileSync('src/signature.js', 'utf8');
  console.log('push-args-index', src.includes('validatedArgs.push(args[argIndex])'));
  console.log('span-comment', src.includes('span multiple args'));
}).catch((e) => {
  console.log('eval-error', e.name, e.message);
});
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/query-signature-core.git query-signature-core-A
cd query-signature-core-A
npm install
npx mocha test/run-test-suite.js --grep function-signatures   # 预期：观察 passed 数
node verify_45.js   # 预期：nplus [1,2] ；nplus-s [1,2,"a"] ；array-plus [1,2] ；nplus-one [1] ；push-args-index true ；span-comment false
cd ..
```


B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/query-signature-core.git query-signature-core-B
cd query-signature-core-B
npm install
npx mocha test/run-test-suite.js --grep function-signatures   # 预期：观察 passed 数
node verify_45.js   # 预期：nplus [1,2] ；nplus-s [1,2,"a"] ；array-plus [1,2] ；nplus-one [1] ；push-args-index false ；span-comment true
cd ..
```

---

## 第 51 题　0-1 代码生成　·　困难　·　无界面
<!-- solo-report:task=51 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/dns-resolution-cache　A 分支：https://github.com/gy-vs/dns-resolution-cache/tree/A　B 分支：https://github.com/gy-vs/dns-resolution-cache/tree/B

存为 `verify_51.mjs`（放在仓库根目录）

```javascript
import * as k from './dist/index.js';

function makeClock() {
  if (k.ManualClock) return new k.ManualClock(0);
  let now = 0;
  return {
    now: () => now,
    set(ms) {
      now = ms;
    },
    advance(ms) {
      now += ms;
    },
  };
}

const clock = makeClock();
let calls = 0;
const cache = new k.DnsCache({
  resolver: {
    async resolve(name, type) {
      calls += 1;
      if (k.ManualClock) {
        return { kind: 'answer', records: ['1.2.3.4'], ttlMs: 60000 };
      }
      return {
        status: 'ok',
        answers: [{ type: 'A', name, data: '1.2.3.4', ttlSeconds: 60 }],
        ttlSeconds: 60,
      };
    },
  },
  clock,
  capacity: 2,
  staleWindowMs: 30000,
});

const lookup = (host, type) => (cache.lookup ? cache.lookup(host, type) : cache.resolve(host, type));
const r1 = await lookup('Example.COM.', 'a');
const r2 = await lookup('example.com', 'A');
console.log('norm-kind', r1.kind || r1.status, JSON.stringify(r1.records || r1.answers));
console.log('second-calls', calls);
if (cache.inspect) {
  console.log('inspect', JSON.stringify(cache.inspect('example.com', 'A')));
} else {
  console.log('snapshot-keys', cache.snapshot().map((e) => e.name + '/' + e.type).join(','));
}

clock.set(90000);
const stale = await lookup('example.com', 'A');
console.log('stale-or-refresh', stale.kind || stale.status, calls);

cache.close();
try {
  await lookup('other.com', 'A');
  console.log('after-close', 'ok');
} catch (e) {
  console.log('after-close', e.name);
}
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/dns-resolution-cache.git dns-resolution-cache-A
cd dns-resolution-cache-A
npm ci
npm run build
npm test   # 预期：观察 passed 数
node verify_51.mjs   # 预期：norm-kind answer ["1.2.3.4"] ；second-calls 1 ；inspect 含 freshUntil 60000 ；stale-or-refresh answer 2 ；after-close DnsCacheClosedError
cd ..
```


B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/dns-resolution-cache.git dns-resolution-cache-B
cd dns-resolution-cache-B
npm ci
npm run build
npm test   # 预期：观察 passed 数
node verify_51.mjs   # 预期：norm-kind ok 且 answers 含 1.2.3.4 ；second-calls 1 ；snapshot-keys example.com/A ；stale-or-refresh ok 2 ；after-close CacheClosedError
cd ..
```

---

## 第 52 题　0-1 代码生成　·　困难　·　无界面
<!-- solo-report:task=52 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/range-lock-manager　A 分支：https://github.com/gy-vs/range-lock-manager/tree/A　B 分支：https://github.com/gy-vs/range-lock-manager/tree/B

存为 `verify_52.mjs`（放在仓库根目录）

```javascript
async function load() {
  for (const p of ['./dist/src/index.js', './dist/index.js']) {
    try {
      return await import(p);
    } catch (e) {
      if (e && e.code !== 'ERR_MODULE_NOT_FOUND') throw e;
    }
  }
  throw new Error('no entry');
}

const { IntervalLockManager } = await load();

async function acquire(manager, mode, start, end) {
  if (manager.acquire.length >= 4) {
    return manager.acquire(mode, start, end);
  }
  return manager.acquire({ start, end }, mode);
}

const mgr = new IntervalLockManager();
const a = await acquire(mgr, 'shared', 0, 10);
console.log('one-shared', a.mode);
const exclusiveWait = acquire(mgr, 'exclusive', 0, 10);
await Promise.resolve();
try {
  await a.upgrade();
  console.log('upgrade-while-excl-wait', 'ok', a.mode);
} catch (e) {
  console.log('upgrade-while-excl-wait', e.name);
}
a.release();
try {
  const ex = await exclusiveWait;
  console.log('exclusive-after', ex.mode);
  ex.release();
} catch (e) {
  console.log('exclusive-after', e.name);
}

const mgr2 = new IntervalLockManager();
try {
  await acquire(mgr2, 'shared', -5, 5);
  console.log('neg-interval', 'ok');
} catch (e) {
  console.log('neg-interval', e.name);
}

const mgr3 = new IntervalLockManager();
mgr3.close();
try {
  const p = mgr3.acquire.length >= 4 ? mgr3.acquire('shared', 0, 1) : mgr3.acquire({ start: 0, end: 1 }, 'shared');
  try {
    await p;
    console.log('closed', 'async-ok');
  } catch (e) {
    console.log('closed', 'async', e.name);
  }
} catch (e2) {
  console.log('closed', 'sync', e2.name);
}

try {
  await acquire(new IntervalLockManager(), 'nope', 0, 1);
  console.log('bad-mode', 'ok');
} catch (e) {
  console.log('bad-mode', e.name);
}
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/range-lock-manager.git range-lock-manager-A
cd range-lock-manager-A
npm ci
npm run build
npm test   # 预期：观察 passed 数
node verify_52.mjs   # 预期：upgrade-while-excl-wait ok exclusive ；neg-interval InvalidIntervalError ；closed async ManagerClosedError ；bad-mode InvalidModeError
cd ..
```


B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/range-lock-manager.git range-lock-manager-B
cd range-lock-manager-B
npm ci
npm run build
npm test   # 预期：观察 passed 数
node verify_52.mjs   # 预期：upgrade-while-excl-wait UpgradeConflictError ；neg-interval ok ；closed sync LockClosedError ；bad-mode TypeError
cd ..
```

---

## 第 53 题　0-1 代码生成　·　困难　·　无界面
<!-- solo-report:task=53 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/cookie-policy-jar　A 分支：https://github.com/gy-vs/cookie-policy-jar/tree/A　B 分支：https://github.com/gy-vs/cookie-policy-jar/tree/B

存为 `verify_53.mjs`（放在仓库根目录）

```javascript
async function load() {
  for (const p of ['./dist/index.js', './dist/src/index.js']) {
    try {
      return await import(p);
    } catch (e) {
      if (e && e.code !== 'ERR_MODULE_NOT_FOUND') throw e;
    }
  }
  throw new Error('no entry');
}

const api = await load();
const parseDate = api.parseCookieDate || api.parseDate;
const twoDigit = parseDate('Wed, 06-Nov-94 08:49:37 GMT');
let year = 'null';
if (twoDigit !== null && twoDigit !== undefined) {
  year = String(twoDigit instanceof Date ? twoDigit.getUTCFullYear() : new Date(twoDigit).getUTCFullYear());
}
console.log('two-digit-year', year);

const now = () => Date.UTC(2026, 0, 1);
const jar = new api.CookieJar({ now, clock: { now } });
const href = 'https://www.example.com/app/page';
const header = 'id=1; Domain=example.com; Path=/; Max-Age=3600';
let setResult;
try {
  setResult = jar.setCookie({ url: new URL(href) }, header);
} catch (e) {
  setResult = jar.setCookie(href, header);
}
console.log('set-domain', JSON.stringify(setResult));

let send;
try {
  send = jar.getCookieHeader({
    url: new URL('https://www.example.com/app/x'),
    topLevelUrl: new URL('https://www.example.com/'),
    method: 'GET',
  });
} catch (e) {
  send = jar.cookieHeader('https://www.example.com/app/x', {
    method: 'GET',
    site: 'https://www.example.com',
    topLevelSite: 'https://www.example.com',
    topLevelNavigation: true,
    httpApi: true,
  });
}
console.log('cookie-header', send);

let mismatch;
try {
  mismatch = jar.setCookie({ url: new URL('https://www.other.com/') }, 'x=1; Domain=example.com');
} catch (e) {
  mismatch = jar.setCookie('https://www.other.com/', 'x=1; Domain=example.com');
}
console.log('domain-mismatch', JSON.stringify(mismatch));

const snap = typeof jar.snapshot === 'function' ? jar.snapshot() : jar.entries();
console.log('snapshot-len', snap.length);
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/cookie-policy-jar.git cookie-policy-jar-A
cd cookie-policy-jar-A
npm ci
npm run build
npm test   # 预期：观察 passed 数
node verify_53.mjs   # 预期：two-digit-year 1994 ；set-domain status stored ；cookie-header id=1 ；domain-mismatch status stored 且 hostOnly true ；snapshot-len 2
cd ..
```


B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/cookie-policy-jar.git cookie-policy-jar-B
cd cookie-policy-jar-B
npm ci
npm run build
npm test   # 预期：观察 passed 数
node verify_53.mjs   # 预期：two-digit-year null ；set-domain ok true ；cookie-header id=1 ；domain-mismatch ok false reason domain-mismatch ；snapshot-len 1
cd ..
```

---

## 第 54 题　0-1 代码生成　·　困难　·　无界面
<!-- solo-report:task=54 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/hedged-request-coordinator　A 分支：https://github.com/gy-vs/hedged-request-coordinator/tree/A　B 分支：https://github.com/gy-vs/hedged-request-coordinator/tree/B

存为 `verify_54.mjs`（放在仓库根目录）

```javascript
async function load() {
  for (const p of ['./dist/src/index.js', './dist/index.js']) {
    try {
      return await import(p);
    } catch (e) {
      if (e && e.code !== 'ERR_MODULE_NOT_FOUND') throw e;
    }
  }
  throw new Error('no entry');
}

const api = await load();

if (api.createTokenBudget) {
  const budget = api.createTokenBudget(1);
  budget.refund();
  budget.refund();
  console.log('budget-after-two-refunds', budget.available());
  try {
    api.createCoordinator({});
    console.log('coord-no-budget', 'ok');
  } catch (e) {
    console.log('coord-no-budget', e.name);
  }
  const clock = api.systemClock;
  const c = api.createCoordinator({
    budget: api.createTokenBudget(4),
    clock,
    rng: () => 0.5,
  });
  const out = await c.execute({
    deadline: clock.now() + 1000,
    attempt: async () => 'ok',
    idempotencyKey: 'k',
  });
  console.log('execute', out.ok, out.value || (out.success && out.success.value) || JSON.stringify(out).slice(0, 120));
} else {
  const budget = new api.TokenBudget(1);
  budget.release();
  budget.release();
  console.log('budget-after-two-refunds', budget.available);
  const clock = new api.VirtualClock();
  const c = new api.RequestCoordinator({
    clock,
    sleeper: clock,
    random: () => 0.5,
    hedgeDelayMs: 100,
    budgetTokens: 4,
  });
  const p = c.execute({
    deadlineMs: clock.now() + 1000,
    idempotent: true,
    attempt: async () => 'ok',
  });
  await clock.runAll();
  const out = await p;
  console.log('execute', out.value);
}
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/hedged-request-coordinator.git hedged-request-coordinator-A
cd hedged-request-coordinator-A
npm ci
npm run build
npm test   # 预期：观察 passed 数
node verify_54.mjs   # 预期：budget-after-two-refunds 3 ；coord-no-budget TypeError ；execute true ok
cd ..
```


B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/hedged-request-coordinator.git hedged-request-coordinator-B
cd hedged-request-coordinator-B
npm ci
npm run build
npm test   # 预期：观察 passed 数
node verify_54.mjs   # 预期：budget-after-two-refunds 1 ；execute ok
cd ..
```

---

## 第 55 题　0-1 代码生成　·　困难　·　无界面
<!-- solo-report:task=55 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/accept-negotiation-core　A 分支：https://github.com/gy-vs/accept-negotiation-core/tree/A　B 分支：https://github.com/gy-vs/accept-negotiation-core/tree/B

存为 `verify_55.mjs`（放在仓库根目录）

```javascript
async function load() {
  for (const p of ['./dist/src/index.js', './build/src/index.js']) {
    try {
      return await import(p);
    } catch (e) {
      if (e && e.code !== 'ERR_MODULE_NOT_FOUND') throw e;
    }
  }
  throw new Error('no entry');
}

const api = await load();

let r;
if (api.varyFor) {
  r = api.negotiate(
    [
      { id: 'a', mediaType: 'text/html;level=1', language: 'en-US', encoding: 'gzip', charset: 'utf-8' },
      { id: 'b', mediaType: 'application/json', language: 'en' },
    ],
    {
      headers: {
        accept: 'text/html;q=0.9, text/*;q=0.5, */*;q=0.1',
        acceptLanguage: 'en-US, en;q=0.8',
        acceptEncoding: 'gzip, br;q=0.8',
      },
      weights: { mediaType: 3, language: 2, encoding: 1, charset: 1 },
    },
  );
  console.log('winner', r.status, r.winner && r.winner.variant && r.winner.variant.id);
} else {
  r = api.negotiate(
    [
      { mediaType: 'text/html;level=1', language: 'en-US', data: { id: 1 } },
      { mediaType: 'application/json', encoding: 'gzip', data: { id: 2 } },
    ],
    { accept: 'text/*;q=0.8, application/json', acceptLanguage: 'en;q=0.9', acceptEncoding: 'gzip, identity;q=0' },
    { weights: { media: 2, language: 1, encoding: 1, charset: 1 } },
  );
  console.log('winner', r.ok, r.selected ? JSON.stringify(r.selected.data || r.selected) : 'none');
}

try {
  const bad = api.varyFor
    ? api.negotiate([{ id: 'a', mediaType: 'text/html' }], { headers: { accept: 'text/html;;' } })
    : api.negotiate([{ mediaType: 'text/html', data: { id: 1 } }], { accept: 'text/html;;' });
  console.log('malformed', bad.status, JSON.stringify(bad.vary));
} catch (e) {
  console.log('malformed', e.name);
}

if (api.varyFor) {
  console.log('vary', JSON.stringify(api.varyFor({ accept: 'text/html', acceptLanguage: 'en' })));
} else {
  console.log(
    'vary',
    JSON.stringify(
      api.computeVary(
        [{ mediaType: 'text/html', language: 'en', data: {} }],
        { accept: 'text/html', acceptLanguage: 'en' },
      ),
    ),
  );
}
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/accept-negotiation-core.git accept-negotiation-core-A
cd accept-negotiation-core-A
npm ci
npm run build
npm test   # 预期：观察 passed 数
node verify_55.mjs   # 预期：winner ok a ；malformed invalid-request [] ；vary ["Accept","Accept-Language"]
cd ..
```


B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/accept-negotiation-core.git accept-negotiation-core-B
cd accept-negotiation-core-B
npm ci
npm run build
npm test   # 预期：观察 passed 数
node verify_55.mjs   # 预期：winner true 且 selected.candidate.mediaType 为 application/json ；malformed NegotiationSyntaxError ；vary ["Accept","Accept-Language"]
cd ..
```

---

## 第 56 题　Bug 修复　·　困难　·　无界面
<!-- solo-report:task=56 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/httpx-tls-client-core　A 分支：https://github.com/gy-vs/httpx-tls-client-core/tree/A　B 分支：https://github.com/gy-vs/httpx-tls-client-core/tree/B

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/httpx-tls-client-core.git httpx-tls-client-core-A
cd httpx-tls-client-core-A
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e . "pytest<8" trio uvicorn trustme
python -m pytest tests/test_config.py -k no_verify -q   # 预期：4 passed, 27 deselected
python -c "import ssl, httpx; ctx=httpx.create_ssl_context(verify=False); print(ctx.verify_mode==ssl.CERT_NONE, ctx.check_hostname)"   # 预期：True False
python -c "import ssl, httpx; from unittest.mock import patch; p=patch.object(ssl.SSLContext, 'load_cert_chain'); m=p.start(); ctx=httpx.create_ssl_context(verify=False, cert='client.pem'); print(m.called, m.call_args, ctx.verify_mode==ssl.CERT_NONE); p.stop()"   # 预期：True call('client.pem') True
python -c "import ssl, httpx; from unittest.mock import patch; p=patch.object(ssl.SSLContext, 'load_cert_chain'); m=p.start(); httpx.create_ssl_context(verify=False, cert=('c.pem', 'k.pem', 'secret')); print(m.call_args); p.stop()"   # 预期：call('c.pem', 'k.pem', 'secret')
python -c "import ssl, httpx; user=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT); out=httpx.create_ssl_context(verify=user); print(out is user)"   # 预期：True
python -c "t=open('tests/test_config.py', encoding='utf-8').read(); print(('encrypted_cert' in t), ('assert_called_once_with' in t))"   # 预期：True False
deactivate
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/httpx-tls-client-core.git httpx-tls-client-core-B
cd httpx-tls-client-core-B
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e . "pytest<8" trio uvicorn trustme
python -m pytest tests/test_config.py -k no_verify -q   # 预期：4 passed, 27 deselected
python -c "import ssl, httpx; ctx=httpx.create_ssl_context(verify=False); print(ctx.verify_mode==ssl.CERT_NONE, ctx.check_hostname)"   # 预期：True False
python -c "import ssl, httpx; from unittest.mock import patch; p=patch.object(ssl.SSLContext, 'load_cert_chain'); m=p.start(); ctx=httpx.create_ssl_context(verify=False, cert='client.pem'); print(m.called, m.call_args, ctx.verify_mode==ssl.CERT_NONE); p.stop()"   # 预期：True call('client.pem') True
python -c "import ssl, httpx; from unittest.mock import patch; p=patch.object(ssl.SSLContext, 'load_cert_chain'); m=p.start(); httpx.create_ssl_context(verify=False, cert=('c.pem', 'k.pem', 'secret')); print(m.call_args); p.stop()"   # 预期：call('c.pem', 'k.pem', 'secret')
python -c "import ssl, httpx; user=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT); out=httpx.create_ssl_context(verify=user); print(out is user)"   # 预期：True
python -c "t=open('tests/test_config.py', encoding='utf-8').read(); print(('encrypted_cert' in t), ('assert_called_once_with' in t))"   # 预期：False True
deactivate
cd ..
```

---

## 第 57 题　Bug 修复　·　困难　·　无界面
<!-- solo-report:task=57 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/httpx-zstd-response-core　A 分支：https://github.com/gy-vs/httpx-zstd-response-core/tree/A　B 分支：https://github.com/gy-vs/httpx-zstd-response-core/tree/B

存为 `verify_zstd_empty.py`（放在仓库根目录）

```python
import httpx
import zstandard as zstd

response = httpx.Response(
    200, headers=[(b"Content-Encoding", b"zstd")], content=b""
)
print("empty", repr(response.content))

response = httpx.Response(
    200, headers=[(b"Content-Encoding", b"gzip, zstd")], content=b""
)
print("multi", repr(response.content))

body = zstd.compress(b"test 123")
try:
    httpx.Response(
        200, headers=[(b"Content-Encoding", b"zstd")], content=body[:5]
    )
    print("truncated ok")
except httpx.DecodingError as exc:
    print(type(exc).__name__, str(exc))
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/httpx-zstd-response-core.git httpx-zstd-response-core-A
cd httpx-zstd-response-core-A
python -c "import os; print(os.path.isfile('test'))"   # 预期：False
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e . "pytest<8" trio uvicorn zstandard brotli chardet
python -m pytest tests/test_decoders.py -k zstd -q   # 预期：11 passed, 35 deselected
python verify_zstd_empty.py   # 预期：empty b'' / multi b'' / DecodingError Zstandard data is incomplete
python -c "print(any(('empty' in ln.lower() and 'zstd' in ln.lower()) for ln in open('CHANGELOG.md', encoding='utf-8')))"   # 预期：True
deactivate
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/httpx-zstd-response-core.git httpx-zstd-response-core-B
cd httpx-zstd-response-core-B
python -c "import os; print(os.path.isfile('test'))"   # 预期：True
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e . "pytest<8" trio uvicorn zstandard brotli chardet
python -m pytest tests/test_decoders.py -k zstd -q   # 预期：10 passed, 35 deselected
python verify_zstd_empty.py   # 预期：empty b'' / multi b'' / DecodingError Zstandard data is incomplete
python -c "print(any(('empty' in ln.lower() and 'zstd' in ln.lower()) for ln in open('CHANGELOG.md', encoding='utf-8')))"   # 预期：False
deactivate
cd ..
```
## 第 58 题　Bug 修复　·　困难　·　无界面
<!-- solo-report:task=58 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/httpx-timeout-dispatch-core　A 分支：https://github.com/gy-vs/httpx-timeout-dispatch-core/tree/A　B 分支：https://github.com/gy-vs/httpx-timeout-dispatch-core/tree/B

存为 `verify_timeout.py`（放在仓库根目录）

```python
import httpx

seen = []


def handler(request):
    seen.append(request.extensions.get("timeout"))
    return httpx.Response(200)


client = httpx.Client(transport=httpx.MockTransport(handler), timeout=2.5)
client.send(httpx.Request("GET", "http://example.org/"))
print("manual", sorted(seen[0]), seen[0]["read"])

req = httpx.Request(
    "GET", "http://example.org/", extensions={"timeout": {"read": 0.1}}
)
client.send(req)
print("override", seen[1])


class NewReqAuth(httpx.Auth):
    def auth_flow(self, request):
        yield httpx.Request(request.method, request.url)


seen_auth = []


def handler_auth(request):
    seen_auth.append(request.extensions.get("timeout"))
    return httpx.Response(200)


client2 = httpx.Client(
    transport=httpx.MockTransport(handler_auth), timeout=2.5, auth=NewReqAuth()
)
client2.send(httpx.Request("GET", "http://example.org/"))
print("auth_new", seen_auth[0] is not None)
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/httpx-timeout-dispatch-core.git httpx-timeout-dispatch-core-A
cd httpx-timeout-dispatch-core-A
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e . "pytest<8" trio uvicorn
python -m pytest tests/test_timeouts.py -q -k manual_request   # 预期：观察 passed
python verify_timeout.py   # 预期：manual ['connect', 'pool', 'read', 'write'] 2.5 / override {'read': 0.1} / auth_new True
python -c "import httpx._client as cl; print(hasattr(cl.BaseClient, '_set_default_timeout'), hasattr(cl.BaseClient, '_merge_request_timeout'))"   # 预期：True False
python -c "t=open('CHANGELOG.md', encoding='utf-8').read()[:800]; print(('timeout' in t.lower() and 'Request' in t))"   # 预期：False
deactivate
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/httpx-timeout-dispatch-core.git httpx-timeout-dispatch-core-B
cd httpx-timeout-dispatch-core-B
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e . "pytest<8" trio uvicorn
python -m pytest tests/client/test_client.py tests/client/test_async_client.py tests/client/test_redirects.py -q -k manual_request   # 预期：13 passed, 118 deselected
python verify_timeout.py   # 预期：manual ['connect', 'pool', 'read', 'write'] 2.5 / override {'read': 0.1} / auth_new False
python -c "import httpx._client as cl; print(hasattr(cl.BaseClient, '_set_default_timeout'), hasattr(cl.BaseClient, '_merge_request_timeout'))"   # 预期：False True
python -c "t=open('CHANGELOG.md', encoding='utf-8').read()[:800]; print(('timeout' in t.lower() and 'Request' in t))"   # 预期：True
deactivate
cd ..
```

---

## 第 59 题　Bug 修复　·　困难　·　无界面
<!-- solo-report:task=59 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/httpx-digest-auth-core　A 分支：https://github.com/gy-vs/httpx-digest-auth-core/tree/A　B 分支：https://github.com/gy-vs/httpx-digest-auth-core/tree/B

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/httpx-digest-auth-core.git httpx-digest-auth-core-A
cd httpx-digest-auth-core-A
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e . "pytest<8" trio uvicorn
python -m pytest tests/test_auth.py -q   # 预期：9 passed
python -c "import httpx; auth=httpx.DigestAuth(username='Mufasa', password='Circle Of Life'); request=httpx.Request('GET', 'http://www.example.org/dir/index.html'); flow=auth.sync_auth_flow(request); request=next(flow); challenge='Digest realm=\'testrealm@host.com\', nonce=\'dcd98b7102dd2f0e8b11d0f600bfb0c093\', opaque=\'5ccc069c403ebaf9f0171e9517f40e41\''; response=httpx.Response(401, headers={'WWW-Authenticate': challenge}, request=request); hdr=flow.send(response).headers['Authorization']; print(('qop' in hdr), ('nc=' in hdr), ('cnonce' in hdr)); print(('670fd8c2df070c60b045671b8b24ff02' in hdr))"   # 预期：False False False / True
python -c "import httpx; auth=httpx.DigestAuth(username='Mufasa', password='Circle Of Life'); request=httpx.Request('GET', 'http://www.example.org/dir/index.html'); flow=auth.sync_auth_flow(request); request=next(flow); challenge='Digest realm=\'testrealm@host.com\', nonce=\'dcd98b7102dd2f0e8b11d0f600bfb0c093\', opaque=\'5ccc069c403ebaf9f0171e9517f40e41\', qop=\'auth\''; response=httpx.Response(401, headers={'WWW-Authenticate': challenge}, request=request); hdr=flow.send(response).headers['Authorization']; print(('qop=auth' in hdr or 'qop=\'auth\'' in hdr), ('nc=' in hdr), ('cnonce=' in hdr))"   # 预期：True True True
python -c "t=open('tests/test_auth.py', encoding='utf-8').read(); print(('SHA-256' in t), ('753927fa' in t))"   # 预期：True True
deactivate
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/httpx-digest-auth-core.git httpx-digest-auth-core-B
cd httpx-digest-auth-core-B
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e . "pytest<8" trio uvicorn
python -m pytest tests/test_auth.py -q   # 预期：8 passed
python -c "import httpx; auth=httpx.DigestAuth(username='Mufasa', password='Circle Of Life'); request=httpx.Request('GET', 'http://www.example.org/dir/index.html'); flow=auth.sync_auth_flow(request); request=next(flow); challenge='Digest realm=\'testrealm@host.com\', nonce=\'dcd98b7102dd2f0e8b11d0f600bfb0c093\', opaque=\'5ccc069c403ebaf9f0171e9517f40e41\''; response=httpx.Response(401, headers={'WWW-Authenticate': challenge}, request=request); hdr=flow.send(response).headers['Authorization']; print(('qop' in hdr), ('nc=' in hdr), ('cnonce' in hdr)); print(('670fd8c2df070c60b045671b8b24ff02' in hdr))"   # 预期：False False False / True
python -c "import httpx; auth=httpx.DigestAuth(username='Mufasa', password='Circle Of Life'); request=httpx.Request('GET', 'http://www.example.org/dir/index.html'); flow=auth.sync_auth_flow(request); request=next(flow); challenge='Digest realm=\'testrealm@host.com\', nonce=\'dcd98b7102dd2f0e8b11d0f600bfb0c093\', opaque=\'5ccc069c403ebaf9f0171e9517f40e41\', qop=\'auth\''; response=httpx.Response(401, headers={'WWW-Authenticate': challenge}, request=request); hdr=flow.send(response).headers['Authorization']; print(('qop=auth' in hdr or 'qop=\'auth\'' in hdr), ('nc=' in hdr), ('cnonce=' in hdr))"   # 预期：True True True
python -c "t=open('tests/test_auth.py', encoding='utf-8').read(); print(('SHA-256' in t), ('753927fa' in t))"   # 预期：False False
deactivate
cd ..
```

---

## 第 60 题　Bug 修复　·　困难　·　无界面
<!-- solo-report:task=60 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/httpx-asgi-transport-core　A 分支：https://github.com/gy-vs/httpx-asgi-transport-core/tree/A　B 分支：https://github.com/gy-vs/httpx-asgi-transport-core/tree/B

存为 `verify_asgi.py`（放在仓库根目录）

```python
import asyncio
import httpx


async def raise_exc(scope, receive, send):
    raise RuntimeError("boom")


async def after_start(scope, receive, send):
    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"text/plain")],
        }
    )
    await send({"type": "http.response.body", "body": b"Hello", "more_body": False})
    raise RuntimeError("boom")


async def body_first(scope, receive, send):
    await send({"type": "http.response.body", "body": b"Hello", "more_body": False})
    raise RuntimeError("boom")


async def main():
    transport = httpx.ASGITransport(app=raise_exc, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport) as client:
        response = await client.get("http://www.example.org/")
        print("suppressed", response.status_code, response.content)

    transport2 = httpx.ASGITransport(app=raise_exc, raise_app_exceptions=True)
    async with httpx.AsyncClient(transport=transport2) as client:
        try:
            await client.get("http://www.example.org/")
            print("raised none")
        except RuntimeError as exc:
            print("raised", type(exc).__name__)

    transport3 = httpx.ASGITransport(app=after_start, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport3) as client:
        response = await client.get("http://www.example.org/")
        print(
            "after",
            response.status_code,
            response.content,
            response.headers.get("content-type"),
        )

    transport4 = httpx.ASGITransport(app=body_first, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport4) as client:
        response = await client.get("http://www.example.org/")
        print("bodyfirst", response.status_code, response.content)


asyncio.run(main())
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/httpx-asgi-transport-core.git httpx-asgi-transport-core-A
cd httpx-asgi-transport-core-A
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e . "pytest<8" trio uvicorn
python -m pytest tests/test_asgi.py -q -k "no_raise or after_response_start"   # 预期：8 passed, 20 deselected
python verify_asgi.py   # 预期：suppressed 500 b'' / raised RuntimeError / after 200 b'Hello' text/plain / bodyfirst 500 b'Hello'
python -c "t=open('CHANGELOG.md', encoding='utf-8').read()[:400]; print(('ASGITransport' in t), ('raise_app_exceptions' in t))"   # 预期：True True
deactivate
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/httpx-asgi-transport-core.git httpx-asgi-transport-core-B
cd httpx-asgi-transport-core-B
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e . "pytest<8" trio uvicorn
python -m pytest tests/test_asgi.py -q -k "suppressed or raise_app_exceptions"   # 预期：8 passed, 20 deselected
python verify_asgi.py   # 预期：suppressed 500 b'' / raised RuntimeError / after 200 b'Hello' text/plain / bodyfirst 500 b''
python -c "t=open('CHANGELOG.md', encoding='utf-8').read()[:400]; print(('ASGITransport' in t), ('raise_app_exceptions' in t))"   # 预期：False False
deactivate
cd ..
```

---

## 第 61 题　Bug 修复　·　困难　·　无界面
<!-- solo-report:task=61 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/jinja-bytecode-cache-core　A 分支：https://github.com/gy-vs/jinja-bytecode-cache-core/tree/A　B 分支：https://github.com/gy-vs/jinja-bytecode-cache-core/tree/B

存为 `verify_bccache.py`（放在仓库根目录）

```python
import os
import tempfile
from jinja2 import DictLoader, Environment
from jinja2.bccache import FileSystemBytecodeCache

mod = __import__('jinja2.bccache', fromlist=['x'])
print('module_helper', hasattr(mod, '_is_cache_miss_error'))
print('method_helper', hasattr(FileSystemBytecodeCache, '_is_missing_cache_error'))
print('changes_atomic', 'atomically' in open('CHANGES.rst', encoding='utf-8').read())

d = tempfile.mkdtemp()
cache = FileSystemBytecodeCache(d)
env = Environment(loader=DictLoader({'t': 'hello {{ n }}'}), bytecode_cache=cache)
print(env.get_template('t').render(n=1))
files = [f for f in os.listdir(d) if f.startswith('__jinja2_') and f.endswith('.cache')]
print('cache_ok', len(files) == 1)
print('tmp_left', [f for f in os.listdir(d) if f.endswith('.tmp')])
cache.load_bytecode(cache.get_bucket(env, 'missing', 'n', 'src'))
print('miss_code', cache.get_bucket(env, 'missing', 'n', 'src').code)
cache.clear()
print('after_clear', [f for f in os.listdir(d) if f.endswith('.cache')])
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/jinja-bytecode-cache-core.git jinja-bytecode-cache-core-A
cd jinja-bytecode-cache-core-A
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e . "pytest<8" "markupsafe<2.1"
python -m pytest tests/test_bytecode_cache.py -q                     # 预期：观察 passed；部分用例 patch os.name 为 nt，pathlib 可能失败
python verify_bccache.py                                            # 预期：module_helper False；method_helper True；changes_atomic False；hello 1；cache_ok True；tmp_left []；after_clear []
python -c "from jinja2.bccache import _is_cache_miss_error; print(_is_cache_miss_error)"   # 预期：ImportError: cannot import name '_is_cache_miss_error'
python -c "import inspect; from jinja2.bccache import FileSystemBytecodeCache; print('raise' in inspect.getsource(FileSystemBytecodeCache.clear))"   # 预期：True
deactivate
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/jinja-bytecode-cache-core.git jinja-bytecode-cache-core-B
cd jinja-bytecode-cache-core-B
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e . "pytest<8" "markupsafe<2.1"
python -m pytest tests/test_bytecode_cache.py -q                     # 预期：观察 passed；Windows 删除权限用例在非 Windows 上可能失败
python verify_bccache.py                                            # 预期：module_helper True；method_helper False；changes_atomic True；hello 1；cache_ok True；tmp_left []；after_clear []
python -c "from jinja2.bccache import _is_cache_miss_error; print(_is_cache_miss_error)"   # 预期：打印函数对象
python -c "import inspect; from jinja2.bccache import FileSystemBytecodeCache; print('raise' in inspect.getsource(FileSystemBytecodeCache.clear))"   # 预期：False
deactivate
cd ..
```

---

## 第 62 题　Bug 修复　·　困难　·　无界面
<!-- solo-report:task=62 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/jinja-async-stream-core　A 分支：https://github.com/gy-vs/jinja-async-stream-core/tree/A　B 分支：https://github.com/gy-vs/jinja-async-stream-core/tree/B

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/jinja-async-stream-core.git jinja-async-stream-core-A
cd jinja-async-stream-core-A
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e . "pytest<8" "markupsafe<2.1" "trio<=0.22.2"
python -m pytest tests/test_async.py tests/test_async_filters.py -q   # 预期：观察 passed，用例 id 带 asyncio 与 trio
python -m pytest tests/test_async.py -q -k "generate_async or async_extend or short_circuit or exactly_once"   # 预期：generate_async / async_extend 通过；short_circuit / exactly_once 无匹配
python -c "from jinja2.async_utils import auto_aclose; print(auto_aclose.__name__)"   # 预期：ImportError: cannot import name 'auto_aclose'
python -c "import inspect; from jinja2 import filters; print('auto_aclose' in inspect.getsource(filters))"   # 预期：False
python -c "from jinja2.runtime import async_exported; print('auto_aclose' in async_exported)"   # 预期：False
deactivate
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/jinja-async-stream-core.git jinja-async-stream-core-B
cd jinja-async-stream-core-B
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e . "pytest<8" "markupsafe<2.1" "trio<=0.22.2"
python -m pytest tests/test_async.py tests/test_async_filters.py -q   # 预期：观察 passed，含 short_circuit / exactly_once / render_error
python -m pytest tests/test_async.py -q -k "generate_async or async_extend or short_circuit or exactly_once"   # 预期：generate_async、short_circuit、exactly_once 通过
python -c "from jinja2.async_utils import auto_aclose; print(auto_aclose.__name__)"   # 预期：auto_aclose
python -c "import inspect; from jinja2 import filters; print('auto_aclose' in inspect.getsource(filters))"   # 预期：True
python -c "from jinja2.runtime import async_exported; print('auto_aclose' in async_exported)"   # 预期：True
deactivate
cd ..
```

---

## 第 63 题　Bug 修复　·　困难　·　无界面
<!-- solo-report:task=63 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/jinja-branch-scope-core　A 分支：https://github.com/gy-vs/jinja-branch-scope-core/tree/A　B 分支：https://github.com/gy-vs/jinja-branch-scope-core/tree/B

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/jinja-branch-scope-core.git jinja-branch-scope-core-A
cd jinja-branch-scope-core-A
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e . "pytest<8" "markupsafe<2.1"
python -m pytest tests/test_regression.py tests/test_compile.py tests/test_idtracking.py -q   # 预期：77 passed
python -c "from jinja2 import Environment; t=Environment().from_string('{% if x %}{{ a.b }}{% set a = 1 %}{% elif y %}{% set a = 2 %}{% else %}{% set a = 3 %}{% endif %}{{ a }}'); print(t.render(x=True, a=type('O',(),{'b':'value'})())); print(t.render(y=True)); print(t.render())"   # 预期：value1 / 2 / 3
python -c "from jinja2 import Environment; code=Environment().compile('{% if x %}{% set a = 1 %}{% elif y %}{% set a = 2 %}{% else %}{% set a = 3 %}{% endif %}{{ a }}', raw=True); print('resolve' in code); print('l_0_a = missing' in code)"   # 预期：True / False
python -c "print('loads_before_store' in open('src/jinja2/idtracking.py', encoding='utf-8').read())"   # 预期：False
deactivate
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/jinja-branch-scope-core.git jinja-branch-scope-core-B
cd jinja-branch-scope-core-B
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e . "pytest<8" "markupsafe<2.1"
python -m pytest tests/test_regression.py tests/test_compile.py tests/test_idtracking.py -q   # 预期：test_compile 新增断言失败；idtracking 可能通过
python -c "from jinja2 import Environment; t=Environment().from_string('{% if x %}{{ a.b }}{% set a = 1 %}{% elif y %}{% set a = 2 %}{% else %}{% set a = 3 %}{% endif %}{{ a }}'); print(t.render(x=True, a=type('O',(),{'b':'value'})())); print(t.render(y=True)); print(t.render())"   # 预期：value1 / 2 / 3
python -c "from jinja2 import Environment; code=Environment().compile('{% if x %}{% set a = 1 %}{% elif y %}{% set a = 2 %}{% else %}{% set a = 3 %}{% endif %}{{ a }}', raw=True); print('resolve' in code); print('l_0_a = missing' in code)"   # 预期：True / True
python -c "print('loads_before_store' in open('src/jinja2/idtracking.py', encoding='utf-8').read())"   # 预期：True
deactivate
cd ..
```

---

## 第 64 题　Bug 修复　·　困难　·　无界面
<!-- solo-report:task=64 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/jinja-required-block-core　A 分支：https://github.com/gy-vs/jinja-required-block-core/tree/A　B 分支：https://github.com/gy-vs/jinja-required-block-core/tree/B

存为 `verify_required.py`（放在仓库根目录）

```python
from jinja2 import DictLoader, Environment, TemplateSyntaxError
from jinja2.parser import Parser

e = Environment(loader=DictLoader({
    'base': '{% block x required %}\n{# c #}\n{% endblock %}',
    'child': '{% extends "base" %}{% block x %}ok{% endblock %}',
}))
print('child', e.get_template('child').render())

e2 = Environment(loader=DictLoader({
    'bad': '{% block x required %}\n\n{% if 1 %}a{% endif %}\n{% endblock %}',
}))
try:
    e2.get_template('bad')
    print('if_block', 'no error')
except TemplateSyntaxError as err:
    print('if_block', err.message, err.lineno)

e3 = Environment(loader=DictLoader({
    'bad': '{% block x required %}{% include "z" %}{% endblock %}',
}))
try:
    e3.get_template('bad')
    print('include', 'no error')
except TemplateSyntaxError as err:
    print('include', type(err).__name__, err.message)

print('has_check', hasattr(Parser, '_check_required_block'))
text = open('CHANGES.rst', encoding='utf-8').read()
print('changes_required', 'TemplateSyntaxError' in text and 'required' in text.lower())
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/jinja-required-block-core.git jinja-required-block-core-A
cd jinja-required-block-core-A
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e . "pytest<8" "markupsafe<2.1"
python -m pytest tests/test_inheritance.py -q -k required             # 预期：观察 passed
python verify_required.py                                           # 预期：child ok；if_block ... whitespace 3；include TemplateSyntaxError ... whitespace；has_check True；changes_required False
deactivate
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/jinja-required-block-core.git jinja-required-block-core-B
cd jinja-required-block-core-B
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e . "pytest<8" "markupsafe<2.1"
python -m pytest tests/test_inheritance.py -q -k required             # 预期：观察 passed
python verify_required.py                                           # 预期：child ok；if_block ... whitespace 3；include TemplateSyntaxError ... whitespace；has_check False；changes_required True
deactivate
cd ..
```

---

## 第 65 题　Bug 修复　·　困难　·　无界面
<!-- solo-report:task=65 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/attrs-field-transform-core　A 分支：https://github.com/gy-vs/attrs-field-transform-core/tree/A　B 分支：https://github.com/gy-vs/attrs-field-transform-core/tree/B

存为 `verify_transform.py`（放在仓库根目录）

```python
import attr

seen = []

def hook(cls, fields):
    for f in fields:
        seen.append((f.name, f.alias, getattr(f, 'alias_type', None), getattr(f, 'alias_is_default', None)))
    out = []
    for f in fields:
        if f.name == '_private':
            out.append(f.evolve(name='_renamed'))
        else:
            out.append(f)
    return out

@attr.s(field_transformer=hook)
class C:
    _private = attr.ib()
    _explicit = attr.ib(alias='kept')

print('has_AliasType', hasattr(attr, 'AliasType'))
print('in_hook', seen)
print('fields', [(f.name, f.alias, getattr(f, 'alias_type', None), getattr(f, 'alias_is_default', None)) for f in attr.fields(C)])
print(C(renamed=1, kept=2))
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/attrs-field-transform-core.git attrs-field-transform-core-A
cd attrs-field-transform-core-A
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e . pytest hypothesis
python -m pytest tests/test_make.py tests/test_hooks.py -q            # 预期：观察 passed
python verify_transform.py                                          # 预期：has_AliasType True；in_hook 里 alias 已是 private/kept，alias_type 为 DEFAULT/EXPLICIT；字段 _renamed/renamed；打印 C(_renamed=1, _explicit=2)
python -c "from attr import AliasType; print(list(AliasType))"       # 预期：打印 DEFAULT 与 EXPLICIT
deactivate
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/attrs-field-transform-core.git attrs-field-transform-core-B
cd attrs-field-transform-core-B
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e . pytest hypothesis
python -m pytest tests/test_make.py tests/test_hooks.py -q            # 预期：观察 passed
python verify_transform.py                                          # 预期：has_AliasType False；in_hook 里 alias_is_default 为 True/False；字段 _renamed/renamed；打印 C(_renamed=1, _explicit=2)
python -c "from attr import AliasType; print(list(AliasType))"       # 预期：ImportError: cannot import name 'AliasType'
deactivate
cd ..
```

---

## 第 66 题　Bug 修复　·　困难　·　无界面
<!-- solo-report:task=66 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/attrs-keyword-init-core　A 分支：https://github.com/gy-vs/attrs-keyword-init-core/tree/A　B 分支：https://github.com/gy-vs/attrs-keyword-init-core/tree/B

存为 `verify_kw_only.py`（放在仓库根目录）

```python
import inspect
import attr
import attrs

print('attrs.set_kw_only_override', hasattr(attrs, 'set_kw_only_override'))
print('attr.set_force_kw_only_override', hasattr(attr, 'set_force_kw_only_override'))

@attrs.define(kw_only=True)
class C:
    x: int = attrs.field(kw_only=False)
    y: int

print('sig', inspect.signature(C.__init__))
print('call', C(1, y=2))

@attrs.define
class Base:
    a: int

@attrs.define(kw_only=True)
class Sub(Base):
    b: int

print('sub_sig', inspect.signature(Sub.__init__))
print('sub_call', Sub(1, b=2))

if hasattr(attrs, 'set_kw_only_override'):
    attrs.set_kw_only_override(True)
elif hasattr(attr, 'set_force_kw_only_override'):
    attr.set_force_kw_only_override(True)

@attrs.define(kw_only=True)
class C2:
    x: int = attrs.field(kw_only=False)
    y: int

print('override_sig', inspect.signature(C2.__init__))
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/attrs-keyword-init-core.git attrs-keyword-init-core-A
cd attrs-keyword-init-core-A
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e . pytest hypothesis
python -m pytest tests/test_make.py -q -k "kw_only or keyword_only"   # 预期：观察 passed
python -c "import os; print(os.path.exists('tests/test_kw_only.py'))" # 预期：False
python verify_kw_only.py                                            # 预期：attrs.set_kw_only_override True；attr.set_force_kw_only_override False；sig (self, x: int, *, y: int) -> None；call C(x=1, y=2)；sub_sig (self, a: int, *, b: int) -> None；override_sig 全关键字
python -c "import attrs; print(attrs.get_kw_only_override())"        # 预期：False
deactivate
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/attrs-keyword-init-core.git attrs-keyword-init-core-B
cd attrs-keyword-init-core-B
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e . pytest hypothesis
python -m pytest tests/test_make.py -q -k "kw_only or keyword_only"   # 预期：观察 passed
python -c "import os; print(os.path.exists('tests/test_kw_only.py'))" # 预期：True
python verify_kw_only.py                                            # 预期：attrs.set_kw_only_override False；attr.set_force_kw_only_override True；sig 与 call、sub 与 A 相同；override_sig 全关键字
python -c "import attrs; print(attrs.get_kw_only_override())"        # 预期：AttributeError
deactivate
cd ..
```

---

## 第 67 题　Bug 修复　·　困难　·　无界面
<!-- solo-report:task=67 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/attrs-slotted-cache-core　A 分支：https://github.com/gy-vs/attrs-slotted-cache-core/tree/A　B 分支：https://github.com/gy-vs/attrs-slotted-cache-core/tree/B

存为 `verify_slots_cache.py`（放在仓库根目录）

```python
import functools
import attr
import attrs
from attr import _make

print('has_get_descriptor', hasattr(_make, '_get_descriptor_attribute'))
print('has_super_cached', hasattr(_make, '_is_super_cached_property'))

@attr.s(slots=True)
class C:
    @property
    def f(self):
        raise AttributeError('I am a property')

    @functools.cached_property
    def g(self):
        return self.f

try:
    C().g
except AttributeError as e:
    print('propagated', e)

@attr.s(slots=True)
class D:
    x = attr.ib(init=False, default=attr.NOTHING)

    def __getattr__(self, name):
        return 'fallback'

    @functools.cached_property
    def g(self):
        return 1

try:
    print('missing_slot', D().x)
except Exception as e:
    print('missing_slot', type(e).__name__, e)

calls = [0]

@attrs.frozen(slots=True)
class A:
    x: int

    @functools.cached_property
    def f(self):
        calls[0] += 1
        return self.x * 2

a = A(21)
print('frozen', a.f, a.f, calls[0], hasattr(a, '__dict__'))
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/attrs-slotted-cache-core.git attrs-slotted-cache-core-A
cd attrs-slotted-cache-core-A
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e . pytest hypothesis cloudpickle pympler
python -m pytest tests/test_slots.py -q                              # 预期：观察 passed
python verify_slots_cache.py                                        # 预期：has_get_descriptor False；has_super_cached False；propagated I am a property；missing_slot fallback；frozen 42 42 1 False
deactivate
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/attrs-slotted-cache-core.git attrs-slotted-cache-core-B
cd attrs-slotted-cache-core-B
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e . pytest hypothesis cloudpickle pympler
python -m pytest tests/test_slots.py -q                              # 预期：观察 passed
python verify_slots_cache.py                                        # 预期：has_get_descriptor True；has_super_cached True；propagated I am a property；missing_slot AttributeError 'D' object has no attribute 'x'；frozen 42 42 1 False
deactivate
cd ..
```

---

## 第 68 题　Bug 修复　·　困难　·　无界面
<!-- solo-report:task=68 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/attrs-preinit-core　A 分支：https://github.com/gy-vs/attrs-preinit-core/tree/A　B 分支：https://github.com/gy-vs/attrs-preinit-core/tree/B

存为 `verify_preinit.py`（放在仓库根目录）

```python
import inspect
import os
import attr

seen = []

@attr.s
class C:
    x = attr.ib()
    y = attr.ib(kw_only=True, default=42)

    def __attrs_pre_init__(self, x, y):
        seen.append((x, y))

print('default', C(1).y, seen)
seen.clear()
print('explicit', C(1, y=9).y, seen)

seen2 = []
try:
    @attr.s
    class D:
        y = attr.ib(kw_only=True, default=5)
        x = attr.ib()

        def __attrs_pre_init__(self, y, x):
            seen2.append((y, x))

    print('decl_order', D(1), seen2)
    print('sig', inspect.signature(D.__init__))
except Exception as e:
    print('decl_order', type(e).__name__, e)

seen3 = []

@attr.s
class E:
    x = attr.ib(factory=lambda: 42)
    y = attr.ib(kw_only=True, factory=list)

    def __attrs_pre_init__(self, x, y):
        seen3.append((x, y))

print('factory', E(), seen3)
print('has_changelog', os.path.exists('changelog.d/1319.change.md'))
print('has_unchanged', 'test_init_script_unchanged_without_pre_init' in open('tests/test_make.py', encoding='utf-8').read())
print('has_alignment', 'test_pre_init_inherited_kw_only_alignment' in open('tests/test_make.py', encoding='utf-8').read())
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/attrs-preinit-core.git attrs-preinit-core-A
cd attrs-preinit-core-A
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e . pytest hypothesis pympler
python -m pytest tests/test_make.py -q -k pre_init                    # 预期：观察 passed
python verify_preinit.py                                            # 预期：default 42 [(1, 42)]；explicit 9 [(1, 9)]；decl_order TypeError ... multiple values for argument 'y'；factory E(x=42, y=[]) [(42, [])]；has_changelog False；has_unchanged True；has_alignment False
deactivate
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/attrs-preinit-core.git attrs-preinit-core-B
cd attrs-preinit-core-B
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e . pytest hypothesis pympler
python -m pytest tests/test_make.py -q -k pre_init                    # 预期：观察 passed
python verify_preinit.py                                            # 预期：default/explicit/factory 同 A；decl_order D(y=5, x=1) [(5, 1)]；has_changelog True；has_unchanged False；has_alignment True
deactivate
cd ..
```

---

## 第 69 题　Bug 修复　·　困难　·　无界面
<!-- solo-report:task=69 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/async-queue-window-core　A 分支：https://github.com/gy-vs/async-queue-window-core/tree/A　B 分支：https://github.com/gy-vs/async-queue-window-core/tree/B

存为 `verify_window.mjs`（放在仓库根目录）

```javascript
import PQueue from './source/index.ts';

async function sleep(ms) {
  await new Promise(resolve => setTimeout(resolve, ms));
}

const interval = 200;
const queue = new PQueue({concurrency: 4, intervalCap: 2, interval});
const starts = [];
const t0 = Date.now();
const mark = () => {
  starts.push(Date.now() - t0);
};
await queue.add(mark);
await sleep(40);
await queue.add(mark);
await queue.onIdle();
await sleep(interval + 40);
await Promise.all([queue.add(mark), queue.add(mark), queue.add(mark)]);
await queue.onIdle();
console.log('starts', starts.map(s => Math.round(s)).join(','));
console.log('firstWindow', starts.filter(s => s < interval - 20).length);
console.log('thirdWaits', starts[4] - starts[2] >= interval - 40);

const idle = new PQueue({concurrency: 4, intervalCap: 2, interval: 250});
const idleStarts = [];
const t1 = Date.now();
await idle.add(() => {
  idleStarts.push(Date.now() - t1);
});
await idle.onIdle();
await sleep(40);
await idle.add(() => {
  idleStarts.push(Date.now() - t1);
});
await idle.onIdle();
console.log('idle-keep', idleStarts.map(s => Math.round(s)).join(','), 'secondImmediate', idleStarts[1] < 80);

const re = new PQueue({concurrency: 8, intervalCap: 2, interval});
const reStarts = [];
const t2 = Date.now();
let extra = 0;
re.on('active', () => {
  reStarts.push(Date.now() - t2);
  if (extra < 2) {
    extra += 1;
    re.add(() => {});
  }
});
re.add(() => {});
await re.onIdle();
console.log('reentrant', reStarts.map(s => Math.round(s)).join(','), 'firstWindow', reStarts.filter(s => s < interval - 20).length);
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/async-queue-window-core.git async-queue-window-core-A
cd async-queue-window-core-A
npm install
node --import=tsx/esm --test test/rate-limit.ts                          # 预期：含新增固定窗口与重入用例，全部通过
node --import=tsx/esm --test --test-name-pattern="fixed window restores full quota" test/rate-limit.ts   # 预期：匹配到 1 条并 ok
node --import=tsx/esm --test --test-name-pattern="fixed window resets" test/advanced.ts                  # 预期：0 tests（该文件没有这条新增用例）
node --import=tsx/esm verify_window.mjs                                 # 预期：firstWindow 2、thirdWaits true、idle-keep 的 secondImmediate true、reentrant firstWindow 2
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/async-queue-window-core.git async-queue-window-core-B
cd async-queue-window-core-B
npm install
node --import=tsx/esm --test test/advanced.ts                            # 预期：含新增固定窗口与重入用例，全部通过
node --import=tsx/esm --test --test-name-pattern="fixed window restores full quota" test/rate-limit.ts   # 预期：0 tests（该文件没有这条新增用例）
node --import=tsx/esm --test --test-name-pattern="fixed window resets" test/advanced.ts                  # 预期：匹配到 1 条并 ok
node --import=tsx/esm verify_window.mjs                                 # 预期：与 A 相同，firstWindow 2、thirdWaits true、idle-keep 的 secondImmediate true、reentrant firstWindow 2
cd ..
```

---

## 第 70 题　Bug 修复　·　困难　·　无界面
<!-- solo-report:task=70 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/async-queue-backpressure-core　A 分支：https://github.com/gy-vs/async-queue-backpressure-core/tree/A　B 分支：https://github.com/gy-vs/async-queue-backpressure-core/tree/B

存为 `verify_size.mjs`（放在仓库根目录）

```javascript
import PQueue from './source/index.ts';

function defer() {
  let resolve;
  const promise = new Promise(r => {
    resolve = r;
  });
  return {promise, resolve};
}

const hold = defer();
const queue = new PQueue({concurrency: 1, autoStart: false});
queue.add(() => hold.promise);
queue.add(() => hold.promise);
queue.add(() => hold.promise);
queue.add(() => hold.promise);
let resolved = false;
queue.onSizeLessThan(4).then(() => {
  resolved = true;
});
queue.start();
await new Promise(r => setTimeout(r, 20));
console.log('start-before-finish', resolved, 'size', queue.size, 'pending', queue.pending);

const holds = [defer(), defer(), defer(), defer(), defer()];
const q2 = new PQueue({concurrency: 3, autoStart: false});
for (const h of holds) {
  q2.add(() => h.promise);
}
const flags = {5: false, 4: false, 3: false, 2: false};
q2.onSizeLessThan(5).then(() => {
  flags[5] = true;
});
q2.onSizeLessThan(4).then(() => {
  flags[4] = true;
});
q2.onSizeLessThan(3).then(() => {
  flags[3] = true;
});
q2.onSizeLessThan(2).then(() => {
  flags[2] = true;
});
q2.start();
await new Promise(r => setTimeout(r, 30));
console.log('one-drain', JSON.stringify(flags), 'size', q2.size, 'pending', q2.pending);

const hold3 = defer();
const q3 = new PQueue({concurrency: 1, autoStart: false});
q3.add(() => hold3.promise);
q3.add(() => hold3.promise);
q3.add(() => hold3.promise);
let count = 0;
q3.onSizeLessThan(3).then(() => {
  count += 1;
});
q3.start();
await new Promise(r => setTimeout(r, 20));
q3.emit('next');
await new Promise(r => setTimeout(r, 20));
console.log('no-leak', count, 'nextListeners', q3.listenerCount('next'));
hold.resolve();
for (const h of holds) {
  h.resolve();
}
hold3.resolve();
await Promise.all([queue.onIdle(), q2.onIdle(), q3.onIdle()]);
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/async-queue-backpressure-core.git async-queue-backpressure-core-A
cd async-queue-backpressure-core-A
npm install
node --import=tsx/esm --test --test-name-pattern="onSizeLessThan" test/basic.ts                         # 预期：新增 start / concurrency / interval / abort / 多阈值 / 不泄漏用例全部 ok
node --import=tsx/esm --test --test-name-pattern="does not leak listeners" test/basic.ts                 # 预期：匹配到 1 条并 ok
node --import=tsx/esm --test --test-name-pattern="different limits independently" test/basic.ts          # 预期：匹配到 1 条并 ok
node --import=tsx/esm verify_size.mjs                                   # 预期：start-before-finish true size 3 pending 1；one-drain 5/4/3 为 true、2 为 false；no-leak 1 nextListeners 0
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/async-queue-backpressure-core.git async-queue-backpressure-core-B
cd async-queue-backpressure-core-B
npm install
node --import=tsx/esm --test --test-name-pattern="onSizeLessThan" test/basic.ts                         # 预期：start / concurrency / interval / abort 与多阈值用例 ok，没有不泄漏用例
node --import=tsx/esm --test --test-name-pattern="does not leak listeners" test/basic.ts                 # 预期：0 tests（没有这条用例）
node --import=tsx/esm --test --test-name-pattern="different limits independently" test/basic.ts          # 预期：匹配到 1 条并 ok（concurrency 为 1，并非同一次 drain 跨越多个阈值）
node --import=tsx/esm verify_size.mjs                                   # 预期：与 A 相同，start-before-finish true、one-drain 5/4/3 true 且 2 false、no-leak 1 nextListeners 0
cd ..
```

---

## 第 71 题　Bug 修复　·　困难　·　无界面
<!-- solo-report:task=71 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/async-queue-abort-core　A 分支：https://github.com/gy-vs/async-queue-abort-core/tree/A　B 分支：https://github.com/gy-vs/async-queue-abort-core/tree/B

存为 `verify_abort.mjs`（放在仓库根目录）

```javascript
import PQueue from './source/index.ts';

class NoRemoveQueue {
  constructor() {
    this.items = [];
  }
  get size() {
    return this.items.length;
  }
  enqueue(run) {
    this.items.push(run);
  }
  dequeue() {
    return this.items.shift();
  }
  filter() {
    return [...this.items];
  }
  setPriority() {}
}

const queue = new PQueue({concurrency: 1, autoStart: false});
const events = [];
for (const name of ['error', 'active', 'empty', 'idle', 'next']) {
  queue.on(name, () => {
    events.push(name);
  });
}
const controller = new AbortController();
const pending = queue.add(() => 'ran', {signal: controller.signal});
let rejected = 'pending';
pending.then(
  () => {
    rejected = 'resolved';
  },
  error => {
    rejected = error && error.name ? error.name : String(error);
  },
);
controller.abort('custom-reason');
await new Promise(r => setTimeout(r, 20));
console.log('paused-abort', rejected, 'size', queue.size, 'isPaused', queue.isPaused, 'events', events.join(','));

const q2 = new PQueue({concurrency: 1, autoStart: false});
const a = new AbortController();
const b = new AbortController();
const p1 = q2.add(() => 'one', {id: 'dup', signal: a.signal});
const p2 = q2.add(() => 'two', {id: 'dup', signal: b.signal});
a.abort();
try {
  await p1;
} catch {}
q2.start();
console.log('dup-id', await p2, 'size', q2.size);

const q3 = new PQueue({concurrency: 1, autoStart: false, queueClass: NoRemoveQueue});
const c = new AbortController();
const p3 = q3.add(() => 'ran', {signal: c.signal});
p3.catch(() => {});
try {
  c.abort();
  await new Promise(r => setTimeout(r, 20));
  console.log('custom-queue size', q3.size);
} catch (error) {
  console.log('custom-queue throw', error && error.name ? error.name : String(error));
}
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/async-queue-abort-core.git async-queue-abort-core-A
cd async-queue-abort-core-A
npm install
node --import=tsx/esm --test test/abort.ts                               # 预期：预先 abort、排队 abort、reason、重复 id、共享 signal、事件与监听器计数全部 ok
node --import=tsx/esm --test --test-name-pattern="abort" test/advanced.ts # 预期：只覆盖既有 pending promises with abortions 等，没有 B 侧那批新增 abort 用例
node --import=tsx/esm verify_abort.mjs                                   # 预期：paused-abort custom-reason size 0 isPaused true events empty,idle（无 error / next）；dup-id two；随后 TypeError: this[#queue].remove is not a function
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/async-queue-abort-core.git async-queue-abort-core-B
cd async-queue-abort-core-B
npm install
node --import=tsx/esm --test test/abort.ts                               # 预期：ERR_MODULE_NOT_FOUND（没有 test/abort.ts）
node --import=tsx/esm --test --test-name-pattern="abort" test/advanced.ts # 预期：新增 abort 用例全部 ok
node --import=tsx/esm verify_abort.mjs                                   # 预期：paused-abort custom-reason size 0 isPaused true events error,empty,idle,next；dup-id two；custom-queue size 1（remove 可选，不抛 TypeError）
cd ..
```

---

## 第 72 题　Bug 修复　·　困难　·　无界面
<!-- solo-report:task=72 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/async-queue-drain-core　A 分支：https://github.com/gy-vs/async-queue-drain-core/tree/A　B 分支：https://github.com/gy-vs/async-queue-drain-core/tree/B

存为 `verify_drain.mjs`（放在仓库根目录）

```javascript
import PQueue from './source/index.ts';

const queue = new PQueue({concurrency: 1});
const controller = new AbortController();
const tasks = [];
let release;
queue.add(() => new Promise(r => {
  release = r;
}));
for (let i = 0; i < 3000; i++) {
  tasks.push(queue.add(() => i, {signal: controller.signal}).catch(() => 'aborted'));
}
controller.abort();
release();
const results = await Promise.all(tasks);
console.log('mass-abort rejected', results.filter(v => v === 'aborted').length, 'size', queue.size, 'pending', queue.pending);

const q2 = new PQueue({concurrency: 1, autoStart: false});
const events = [];
for (const name of ['active', 'error', 'next', 'empty', 'idle']) {
  q2.on(name, () => {
    events.push(name);
  });
}
const ac = new AbortController();
const order = [];
q2.add(() => {
  order.push(2);
}, {priority: 2, signal: ac.signal}).catch(() => {});
q2.add(() => {
  order.push(5);
}, {priority: 5});
q2.add(() => {
  order.push(1);
}, {priority: 1, signal: ac.signal}).catch(() => {});
q2.add(() => {
  order.push(4);
}, {priority: 4});
q2.add(() => {
  order.push(3);
}, {priority: 3});
ac.abort();
q2.start();
await q2.onIdle();
console.log('priority-order', order.join(','));
console.log('events', events.join(','));
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/async-queue-drain-core.git async-queue-drain-core-A
cd async-queue-drain-core-A
npm install
npx ava --match "mass abort*"                                           # 预期：新增 mass abort 用例通过
npx ava --match "*aborted*"                                             # 预期：匹配到既有 aborted 用例，没有 B 侧那批事件序列 / 优先级编排
npx tsc --noEmit                                                        # 预期：无类型错误
node --import=tsx/esm verify_drain.mjs                                  # 预期：mass-abort rejected 3000 size 0 pending 0；priority-order 5,4,3
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/async-queue-drain-core.git async-queue-drain-core-B
cd async-queue-drain-core-B
npm install
npx ava --match "mass abort*"                                           # 预期：0 tests matched（用例名是 skipping many aborted / events are emitted）
npx ava --match "*aborted*"                                             # 预期：大批量取消、优先级 5,4,3,2,1、事件序列 deepEqual 等新增用例通过
npx tsc --noEmit                                                        # 预期：无类型错误
node --import=tsx/esm verify_drain.mjs                                  # 预期：mass-abort rejected 3000 size 0 pending 0；priority-order 5,4,3
cd ..
```

---

## 第 73 题　Bug 修复　·　困难　·　无界面
<!-- solo-report:task=73 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/async-queue-interval-core　A 分支：https://github.com/gy-vs/async-queue-interval-core/tree/A　B 分支：https://github.com/gy-vs/async-queue-interval-core/tree/B

存为 `verify_interval.mjs`（放在仓库根目录）

```javascript
import PQueue from './source/index.ts';

const queue = new PQueue({concurrency: 5000, intervalCap: 1000, interval: 1000});
const starts = [];
const t0 = Date.now();
for (let i = 0; i < 5000; i++) {
  queue.add(() => {
    starts.push(Date.now() - t0);
  });
}
await queue.onIdle();
const first = starts.filter(s => s < 800).length;
console.log('big-sync total', starts.length, 'firstWindow', first);

const re = new PQueue({concurrency: 5000, intervalCap: 1000, interval: 1000});
let extra = 0;
re.on('active', () => {
  if (extra < 4000) {
    extra += 1;
    re.add(() => {});
  }
});
try {
  for (let i = 0; i < 1000; i++) {
    re.add(() => {});
  }
  await re.onIdle();
  console.log('reentrant-big total', extra + 1000);
} catch (error) {
  console.log('reentrant-big error', error && error.name ? error.name : String(error));
}
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/async-queue-interval-core.git async-queue-interval-core-A
cd async-queue-interval-core-A
npm install
npx ava --match "*intervalCap is strictly enforced*"                    # 预期：5000 / intervalCap 1000 的同步与 Promise 组合用例通过
npx ava --match "*re-entrant*"                                          # 预期：原始量级重入 add 用例通过
npx ava --match "*no lingering timers*"                                 # 预期：残留计时器用例通过
node --import=tsx/esm verify_interval.mjs                               # 预期：big-sync total 5000 firstWindow 1000；reentrant-big total 5000
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/async-queue-interval-core.git async-queue-interval-core-B
cd async-queue-interval-core-B
npm install
npx ava --match "*intervalCap is strictly enforced*"                    # 预期：0 tests matched（用例名是 high concurrency intervalCap）
npx ava --match "*re-entrant*"                                          # 预期：0 tests matched（用例名是 reentrant，且参数已缩小）
npx ava --match "*no lingering timers*"                                 # 预期：0 tests matched（用例名是 hanging timer）
node --import=tsx/esm verify_interval.mjs                               # 预期：big-sync total 5000 firstWindow 1000；随后 RangeError: Maximum call stack size exceeded
cd ..
```

---

## 第 74 题　Bug 修复　·　困难　·　无界面
<!-- solo-report:task=74 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/markdown-reference-core　A 分支：https://github.com/gy-vs/markdown-reference-core/tree/A　B 分支：https://github.com/gy-vs/markdown-reference-core/tree/B

存为 `verify_ref.mjs`（放在仓库根目录）

```javascript
import {marked} from './lib/marked.esm.js';
import fs from 'node:fs';

function timeParse(src) {
  const t = Date.now();
  const html = marked.parse(src);
  return {ms: Date.now() - t, html};
}

for (const n of [4000, 16000]) {
  const src = '[' + '\\['.repeat(n);
  const r = timeParse(src);
  console.log('unclosed-open n=' + n, r.ms + 'ms', JSON.stringify(r.html).slice(0, 40));
}
console.log('shortcut', JSON.stringify(marked.parse('[foo]\n\n[foo]: /x')));
console.log('plain', JSON.stringify(marked.parse('hello [world]')));
console.log('nested', JSON.stringify(marked.parse('[foo [bar]]\n\n[foo [bar]]: /url')));
console.log('perf-test', fs.existsSync('test/unit/performance.test.js'));
console.log('redos-spec', fs.existsSync('test/specs/redos/quadratic_reflink_search.cjs'));
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/markdown-reference-core.git markdown-reference-core-A
cd markdown-reference-core-A
npm ci
npm run build:esbuild
node --test --test-reporter=spec test/run-spec-tests.js                  # 预期：CommonMark / GFM / redos 通过，含 quadratic_reflink_search
node --test --test-reporter=spec test/unit/performance.test.js           # 预期：规模翻倍、增长倍率小于 3 的性能用例通过
node verify_ref.mjs                                                     # 预期：4000 与 16000 耗时近似线性（约 30ms / 120ms 量级）；shortcut 输出含 a href；plain 仍是普通文本；perf-test true
node --input-type=module -e "import fs from 'node:fs'; const s = fs.readFileSync('test/unit/performance.test.js', 'utf8'); console.log(s.includes('scale * 2'), s.includes('< 3'))"   # 预期：false true
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/markdown-reference-core.git markdown-reference-core-B
cd markdown-reference-core-B
npm ci
npm run build:esbuild
node --test --test-reporter=spec test/run-spec-tests.js                  # 预期：CommonMark / GFM / redos 通过，含 quadratic_reflink_search
node --test --test-reporter=spec test/unit/performance.test.js           # 预期：四倍规模、阈值 scale * 2 的性能用例通过
node verify_ref.mjs                                                     # 预期：与 A 相同的线性耗时与 HTML；perf-test true
node --input-type=module -e "import fs from 'node:fs'; const s = fs.readFileSync('test/unit/performance.test.js', 'utf8'); console.log(s.includes('scale * 2'), s.includes('< 3'))"   # 预期：true false
cd ..
```

---

## 第 76 题　Bug 修复　·　困难　·　无界面
<!-- solo-report:task=76 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/markdown-task-list-core　A 分支：https://github.com/gy-vs/markdown-task-list-core/tree/A　B 分支：https://github.com/gy-vs/markdown-task-list-core/tree/B

存为 `verify_task.mjs`（放在仓库根目录）

```javascript
import {marked} from './lib/marked.esm.js';
import fs from 'node:fs';

const mixed = [
  '- [ ] outer one',
  '- outer two',
  '',
  '  - [ ] mid one',
  '  - mid two',
  '    - [x] inner one',
  '',
  '    - [ ] inner two',
  '- [x] outer three',
  '',
].join('\n');
const html = marked.parse(mixed);
console.log(html);
console.log('loose-input-in-p', html.includes('<p><input'));
console.log('tight-input-direct', html.includes('<li><input'));
console.log('tight', JSON.stringify(marked.parse('- [ ] item 1\n- [x] item 2\n')));
console.log('loose-siblings', JSON.stringify(marked.parse('- [x] one\n\n- [ ] two\n')));
console.log('fixture-a', fs.existsSync('test/specs/new/tasklist_loose_nested.md'));
console.log('fixture-b', fs.existsSync('test/specs/new/tasklist_nested_loose.md'));
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/markdown-task-list-core.git markdown-task-list-core-A
cd markdown-task-list-core-A
npm ci
npm run build:esbuild
node --test --test-reporter=spec test/run-spec-tests.js                  # 预期：含 tasklist_loose_nested，specs 通过
node --test --test-reporter=spec test/unit/marked.test.js                # 预期：自定义 checkbox renderer 与 false 回退用例用全等断言通过
node verify_task.mjs                                                    # 预期：loose 项 input 在 p 内、tight 中层 input 直接在 li 下；fixture-a true fixture-b false
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/markdown-task-list-core.git markdown-task-list-core-B
cd markdown-task-list-core-B
npm ci
npm run build:esbuild
node --test --test-reporter=spec test/run-spec-tests.js                  # 预期：含 tasklist_nested_loose，specs 通过
node --test --test-reporter=spec test/unit/marked.test.js                # 预期：GFM task lists 分组通过，断言多为 assert.match
node verify_task.mjs                                                    # 预期：与 A 相同的 mixed / tight / loose HTML；fixture-a false fixture-b true
cd ..
```

---

## 第 77 题　Bug 修复　·　困难　·　无界面
<!-- solo-report:task=77 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/markdown-blockquote-core　A 分支：https://github.com/gy-vs/markdown-blockquote-core/tree/A　B 分支：https://github.com/gy-vs/markdown-blockquote-core/tree/B

存为 `verify_quote.mjs`（放在仓库根目录）

```javascript
import {marked, Lexer} from './lib/marked.esm.js';
import fs from 'node:fs';

const cases = [
  ['two-lazy', '> > foo\nbar\n> > baz'],
  ['three-lazy', '> > > foo\nbar\n> > > baz'],
  ['multi-lazy', '> > a\nlazy1\nlazy2\n> > b'],
  ['blank-break', '> > a\n\n> > b'],
  ['list-combo', '> > a\n> > - item\nlazy\n> > - item2'],
];
for (const [name, src] of cases) {
  const html = marked.parse(src);
  const tokens = new Lexer().lex(src);
  console.log('CASE', name);
  console.log(html);
  console.log('types', tokens.map(t => t.type).join(','));
  console.log('raw0', JSON.stringify(tokens[0] && tokens[0].raw));
}
console.log('spec-exists', fs.existsSync('test/specs/new/blockquote_lazy_continuation.md'));
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/markdown-blockquote-core.git markdown-blockquote-core-A
cd markdown-blockquote-core-A
npm ci
npm run build:esbuild
node --test --test-reporter=spec test/unit/Lexer.test.js                 # 预期：两层三层 lazy、空行等单测通过；名为 fenced code after lazy line 的用例没有裸行
node --input-type=module -e "import {marked} from './lib/marked.esm.js'; console.log(marked.parse('> > foo\\nbar\\n> > baz'))"   # 预期：两层 blockquote 包着单个 p，内含 foo / bar / baz
node verify_quote.mjs                                                   # 预期：two-lazy / three-lazy / multi-lazy 都是同一深层引用的单个段落；list-combo 合成一个 ul 含 item 与 item2；spec-exists false
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/markdown-blockquote-core.git markdown-blockquote-core-B
cd markdown-blockquote-core-B
npm ci
npm run build:esbuild
node --test --test-reporter=spec test/unit/Lexer.test.js                 # 预期：lazy 与 fenced code / 列表组合、raw 消费长度单测通过
node --input-type=module -e "import {marked} from './lib/marked.esm.js'; console.log(marked.parse('> > foo\\nbar\\n> > baz'))"   # 预期：与 A 相同，两层 blockquote 包着单个 p
node verify_quote.mjs                                                   # 预期：two-lazy 等与 A 相同；list-combo 拆成两个 ul（item 与 item2 分开）；spec-exists true
cd ..
```

---

## 第 78 题　Bug 修复　·　困难　·　无界面
<!-- solo-report:task=78 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/markdown-inline-link-core　A 分支：https://github.com/gy-vs/markdown-inline-link-core/tree/A　B 分支：https://github.com/gy-vs/markdown-inline-link-core/tree/B

存为 `verify_link.mjs`（放在仓库根目录）

```javascript
import {marked} from './lib/marked.esm.js';

function timeParse(src) {
  const t = Date.now();
  const html = marked.parse(src);
  return {ms: Date.now() - t, html};
}

for (const n of [2000, 20000]) {
  const src = '[]("' + ' '.repeat(n);
  const r = timeParse(src);
  console.log('quote-spaces n=' + n, r.ms + 'ms', r.html.includes('href') ? 'LINK' : 'TEXT');
}
for (const n of [2000, 20000]) {
  const src = '[](' + ' '.repeat(n) + '\u0000)';
  const r = timeParse(src);
  console.log('nul-close n=' + n, r.ms + 'ms');
}
console.log('empty-href', JSON.stringify(marked.parse('[]()')));
console.log('angle-href', JSON.stringify(marked.parse('[a](</url>)')));
console.log('esc-paren', JSON.stringify(marked.parse('[a](foo\\(bar\\))')));
console.log('with-title', JSON.stringify(marked.parse('[a](url "title")')));
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/markdown-inline-link-core.git markdown-inline-link-core-A
cd markdown-inline-link-core-A
npm ci
npm run build:esbuild
node --test --test-reporter=spec test/run-spec-tests.js                  # 预期：CommonMark / GFM / redos 通过，含 quadratic_link_href 多档长度
node --test test/unit/redos.test.js                                     # 预期：ERR_MODULE_NOT_FOUND 或 0 tests（没有这个文件）
node verify_link.mjs                                                    # 预期：quote-spaces 两档都是 TEXT 且约 1-4ms；nul-close 20000 也约 0ms；empty-href / angle-href / esc-paren / with-title 为合法链接
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/markdown-inline-link-core.git markdown-inline-link-core-B
cd markdown-inline-link-core-B
npm ci
npm run build:esbuild
node --test --test-reporter=spec test/run-spec-tests.js                  # 预期：含 unclosed_link_href 单条 redos 用例通过
node --test test/unit/redos.test.js                                     # 预期：增长比与合法链接回归用例通过（材料里此前未跑过）
node verify_link.mjs                                                    # 预期：quote-spaces 仍快且为 TEXT；nul-close n=20000 约 500ms 量级（早退被不可达右括号绕过）；合法链接与 A 相同
cd ..
```

---

## 第 79 题　Feature 迭代　·　困难　·　无界面
<!-- solo-report:task=79 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/httpx-socket-options-core　A 分支：https://github.com/gy-vs/httpx-socket-options-core/tree/A　B 分支：https://github.com/gy-vs/httpx-socket-options-core/tree/B

存为 `verify_socks_options.py`（放在仓库根目录）

```python
import httpx

try:
    transport = httpx.HTTPTransport(proxy=httpx.Proxy("socks5://localhost:1080"))
    print(type(transport._pool).__name__)
except TypeError as exc:
    print(type(exc).__name__)
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/httpx-socket-options-core.git httpx-socket-options-core-A
cd httpx-socket-options-core-A
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e ".[socks]" "pytest<8" trio uvicorn
python -m pytest tests/test_transports.py -q   # 预期：观察 passed
python -c "import inspect, socket, httpx; print('socket_options' in inspect.signature(httpx.HTTPTransport.__init__).parameters); t=httpx.HTTPTransport(socket_options=[(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)]); print(type(t._pool).__name__)"   # 预期：True / ConnectionPool
python verify_socks_options.py   # 预期：TypeError
python -c "import socket, httpx; t=httpx.HTTPTransport(proxy=httpx.Proxy('http://localhost:8080'), socket_options=[(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)]); print(type(t._pool).__name__)"   # 预期：HTTPProxy
python -c "print('socket_options' in open('docs/async.md', encoding='utf-8').read())"   # 预期：True
deactivate
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/httpx-socket-options-core.git httpx-socket-options-core-B
cd httpx-socket-options-core-B
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e ".[socks]" "pytest<8" trio uvicorn
python -m pytest tests/test_transports.py -q   # 预期：观察 passed
python -c "import inspect, socket, httpx; print('socket_options' in inspect.signature(httpx.HTTPTransport.__init__).parameters); t=httpx.HTTPTransport(socket_options=[(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)]); print(type(t._pool).__name__)"   # 预期：True / ConnectionPool
python verify_socks_options.py   # 预期：SOCKSProxy
python -c "import socket, httpx; t=httpx.HTTPTransport(proxy=httpx.Proxy('http://localhost:8080'), socket_options=[(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)]); print(type(t._pool).__name__)"   # 预期：HTTPProxy
python -c "print('socket_options' in open('docs/async.md', encoding='utf-8').read())"   # 预期：False
deactivate
cd ..
```
## 第 80 题　Feature 迭代　·　困难　·　无界面
<!-- solo-report:task=80 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/httpx-socks-resolution-core　A 分支：https://github.com/gy-vs/httpx-socks-resolution-core/tree/A　B 分支：https://github.com/gy-vs/httpx-socks-resolution-core/tree/B

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/httpx-socks-resolution-core.git httpx-socks-resolution-core-A
cd httpx-socks-resolution-core-A
python -c "import os; print(os.path.isfile('test'))"   # 预期：True
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e ".[socks]" "pytest<8" trio uvicorn
python -m pytest tests/client/test_proxies.py -q -k socks   # 预期：观察 passed（约 13 passed）
python -c "import httpx; p=httpx.Proxy('socks5h://user:pass@[::1]:1080'); print(p.url.scheme, str(p.url)); print(repr(p))"   # 预期：socks5h socks5h://[::1]:1080 / Proxy('socks5h://[::1]:1080', auth=('user', '********'))
python -c "import httpx; t=httpx.HTTPTransport(proxy=httpx.Proxy('socks5h://user:pass@[2001:db8::1]:1080')); print(type(t._pool).__name__, t._pool._proxy_url.scheme)"   # 预期：SOCKSProxy b'socks5h'
python -c "import httpx; t=httpx.HTTPTransport(proxy=httpx.Proxy('socks5://localhost:1080')); print(t._pool._proxy_url.scheme)"   # 预期：b'socks5'
python -c "print('socks5h' in open('CHANGELOG.md', encoding='utf-8').read())"   # 预期：False
deactivate
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/httpx-socks-resolution-core.git httpx-socks-resolution-core-B
cd httpx-socks-resolution-core-B
python -c "import os; print(os.path.isfile('test'))"   # 预期：False
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e ".[socks]" "pytest<8" trio uvicorn
python -m pytest tests/client/test_proxies.py -q -k socks   # 预期：13 passed, 68 deselected
python -c "import httpx; p=httpx.Proxy('socks5h://user:pass@[::1]:1080'); print(p.url.scheme, str(p.url)); print(repr(p))"   # 预期：socks5h socks5h://[::1]:1080 / Proxy('socks5h://[::1]:1080', auth=('user', '********'))
python -c "import httpx; t=httpx.HTTPTransport(proxy=httpx.Proxy('socks5h://user:pass@[2001:db8::1]:1080')); print(type(t._pool).__name__, t._pool._proxy_url.scheme)"   # 预期：SOCKSProxy b'socks5h'
python -c "import httpx; t=httpx.HTTPTransport(proxy=httpx.Proxy('socks5://localhost:1080')); print(t._pool._proxy_url.scheme)"   # 预期：b'socks5'
python -c "print('socks5h' in open('CHANGELOG.md', encoding='utf-8').read())"   # 预期：True
deactivate
cd ..
```

---

## 第 81 题　Feature 迭代　·　困难　·　无界面
<!-- solo-report:task=81 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/httpx-zstd-codec-core　A 分支：https://github.com/gy-vs/httpx-zstd-codec-core/tree/A　B 分支：https://github.com/gy-vs/httpx-zstd-codec-core/tree/B

存为 `verify_zstd_garbage.py`（放在仓库根目录）

```python
import httpx

try:
    httpx.Response(
        200, headers=[(b"Content-Encoding", b"zstd")], content=b"invalid"
    )
    print("ok")
except httpx.DecodingError:
    print("DecodingError")
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/httpx-zstd-codec-core.git httpx-zstd-codec-core-A
cd httpx-zstd-codec-core-A
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e ".[zstd,brotli]" "pytest<8" trio uvicorn chardet
python -m pytest tests/test_decoders.py -q -k zstd   # 预期：30 passed, 35 deselected
python -c "import httpx; print(httpx.Client().headers['Accept-Encoding']); print('zstd' in httpx._decoders.SUPPORTED_DECODERS)"   # 预期：gzip, deflate, br, zstd / True
python -c "import zstandard, httpx; c=zstandard.ZstdCompressor().compress; d=c(b'hello zstd ')+c(b'again'); r=httpx.Response(200, headers=[(b'Content-Encoding', b'zstd')], content=d); print(r.content)"   # 预期：b'hello zstd again'
python verify_zstd_garbage.py   # 预期：DecodingError
python -c "print('zstandard>=0.18.0' in open('pyproject.toml', encoding='utf-8').read())"   # 预期：False
deactivate
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/httpx-zstd-codec-core.git httpx-zstd-codec-core-B
cd httpx-zstd-codec-core-B
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e ".[zstd,brotli]" "pytest<8" trio uvicorn chardet
python -m pytest tests/test_decoders.py -q -k zstd   # 预期：24 passed, 35 deselected
python -c "import httpx; print(httpx.Client().headers['Accept-Encoding']); print('zstd' in httpx._decoders.SUPPORTED_DECODERS)"   # 预期：gzip, deflate, br, zstd / True
python -c "import zstandard, httpx; c=zstandard.ZstdCompressor().compress; d=c(b'hello zstd ')+c(b'again'); r=httpx.Response(200, headers=[(b'Content-Encoding', b'zstd')], content=d); print(r.content)"   # 预期：b'hello zstd again'
python verify_zstd_garbage.py   # 预期：DecodingError
python -c "print('zstandard>=0.18.0' in open('pyproject.toml', encoding='utf-8').read())"   # 预期：True
deactivate
cd ..
```
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

## 第 100 题　Feature 迭代　·　困难　·　无界面
<!-- solo-report:task=100 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/markdown-token-pipeline-core　A 分支：https://github.com/gy-vs/markdown-token-pipeline-core/tree/A　B 分支：https://github.com/gy-vs/markdown-token-pipeline-core/tree/B

存为 `verify_hook.mjs`（放在仓库根目录）

```javascript
import {Marked} from './lib/marked.esm.js';
import fs from 'node:fs';

const isolated = new Marked();
isolated.use({
  hooks: {
    processAllTokens(tokens) {
      return tokens.filter(t => t.type !== 'hr');
    },
  },
});
console.log('filter-hr', JSON.stringify(isolated.parse('paragraph one\n\n---\n\nparagraph two')));

try {
  const bad = new Marked();
  bad.use({
    hooks: {
      processAllTokens() {
        return null;
      },
    },
  });
  bad.parse('hi');
} catch (error) {
  console.log('non-array', error.message.split('\n')[0]);
}

const counts = [];
const chain = new Marked();
chain.use({
  hooks: {
    processAllTokens(tokens) {
      counts.push('first:' + tokens.length);
      return tokens.filter(t => t.type !== 'space');
    },
  },
});
chain.use({
  hooks: {
    processAllTokens(tokens) {
      counts.push('second:' + tokens.length);
      return tokens.filter(t => t.type !== 'hr');
    },
  },
});
console.log('chain-html', JSON.stringify(chain.parse('p1\n\n---\n\n p2')));
console.log('chain-order', counts.join(','));

const inline = new Marked();
inline.use({
  hooks: {
    processAllTokens(tokens) {
      return tokens.filter(t => t.type !== 'em');
    },
  },
});
console.log('parseInline', JSON.stringify(inline.parseInline('*em* and text')));

const doc = fs.readFileSync('docs/USING_PRO.md', 'utf8');
console.log('pipeline-lists-hook', /4\) The .*processAllTokens/.test(doc));
console.log('dup-4', (doc.match(/^4\) /gm) || []).length);
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/markdown-token-pipeline-core.git markdown-token-pipeline-core-A
cd markdown-token-pipeline-core-A
npm install
npx rollup -c rollup.config.js
node --test --test-reporter=spec test/unit/Hooks.test.js                 # 预期：新增、删除、替换、多 hook 串联（记录 token 数量）与异步串联全部通过
node verify_hook.mjs                                                    # 预期：filter-hr 去掉 hr；non-array 为 hooks.processAllTokens did not return an array of tokens.；chain-order second:4,first:3；pipeline-lists-hook true；dup-4 1
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/markdown-token-pipeline-core.git markdown-token-pipeline-core-B
cd markdown-token-pipeline-core-B
npm install
npx rollup -c rollup.config.js
node --test --test-reporter=spec test/unit/Hooks.test.js                 # 预期：hooks 用例通过；多 hook 串联只断言空串
node verify_hook.mjs                                                    # 预期：filter-hr 与 chain-order 与 A 相同；non-array 为 processAllTokens hooks must return an array of tokens；pipeline-lists-hook false；dup-4 2
cd ..
```

---

## 第 101 题　0-1 代码生成　·　困难　·　无界面
<!-- solo-report:task=101 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/json-patch-transaction-core　A 分支：https://github.com/gy-vs/json-patch-transaction-core/tree/A　B 分支：https://github.com/gy-vs/json-patch-transaction-core/tree/B

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/json-patch-transaction-core.git json-patch-transaction-core-A
cd json-patch-transaction-core-A
npm ci
npm run build
npm test                                                                 # 预期：91 passed
node --input-type=module -e "import { applyPatch } from './dist/index.js'; const src = { foo: [1,2,3] }; const r = applyPatch(src, [{ op: 'add', path: '/foo/-', value: 4 }, { op: 'move', from: '/foo/0', path: '/foo/2' }, { op: 'test', path: '/foo/2', value: 1 }, { op: 'copy', from: '/foo/3', path: '/tail' }]); console.log(r.ok, JSON.stringify(r.doc), JSON.stringify(src));"   # 预期：true {"foo":[2,3,1,4],"tail":4} {"foo":[1,2,3]}
node --input-type=module -e "import { applyPatch } from './dist/index.js'; const src = { a: { b: 1 } }; const r = applyPatch(src, [{ op: 'add', path: '/a/c', value: 2 }, { op: 'test', path: '/a/b', value: 999 }]); console.log(r.ok, r.doc === src, r.errors[0].code, Object.keys(r.errors[0]).join(','));"   # 预期：false true TEST_FAILED opIndex,code,message,pointer,field,mismatchPointer,expected,actual
node --input-type=module -e "import { applyPatch } from './dist/index.js'; const shared = { x: 1 }; const doc = { p: shared, q: shared }; const r = applyPatch(doc, [{ op: 'add', path: '/z', value: 0 }]); console.log(r.ok, r.errors && r.errors[0] && r.errors[0].code);"   # 预期：false UNSUPPORTED_TYPE
node --input-type=module -e "import { applyPatch } from './dist/index.js'; const src = { a: { b: 1 } }; const r = applyPatch(src, [{ op: 'move', from: '/a', path: '/a/inside' }]); console.log(r.ok, r.errors[0].code, r.doc === src);"   # 预期：false MOVE_INTO_SELF true
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/json-patch-transaction-core.git json-patch-transaction-core-B
cd json-patch-transaction-core-B
npm ci
npm run build
npm test                                                                 # 预期：92 passed
node --input-type=module -e "import { applyPatch } from './dist/index.js'; const src = { foo: [1,2,3] }; const r = applyPatch(src, [{ op: 'add', path: '/foo/-', value: 4 }, { op: 'move', from: '/foo/0', path: '/foo/2' }, { op: 'test', path: '/foo/2', value: 1 }, { op: 'copy', from: '/foo/3', path: '/tail' }]); console.log(r.ok, JSON.stringify(r.doc), JSON.stringify(src));"   # 预期：true {"foo":[2,3,1,4],"tail":4} {"foo":[1,2,3]}
node --input-type=module -e "import { applyPatch } from './dist/index.js'; const src = { a: { b: 1 } }; const r = applyPatch(src, [{ op: 'add', path: '/a/c', value: 2 }, { op: 'test', path: '/a/b', value: 999 }]); console.log(r.ok, r.doc === src, r.errors[0].code, Object.keys(r.errors[0]).join(','));"   # 预期：false true TEST_FAILED index,op,code,message,pointerField,resolvedPath,failedToken,mismatchPath
node --input-type=module -e "import { applyPatch } from './dist/index.js'; const shared = { x: 1 }; const doc = { p: shared, q: shared }; const r = applyPatch(doc, [{ op: 'add', path: '/z', value: 0 }]); console.log(r.ok, r.errors && r.errors[0] && r.errors[0].code);"   # 预期：true undefined
node --input-type=module -e "import { applyPatch } from './dist/index.js'; const src = { a: { b: 1 } }; const r = applyPatch(src, [{ op: 'move', from: '/a', path: '/a/inside' }]); console.log(r.ok, r.errors[0].code, r.doc === src);"   # 预期：false MOVE_INTO_DESCENDANT true
cd ..
```

---

## 第 102 题　0-1 代码生成　·　困难　·　无界面
<!-- solo-report:task=102 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/rendezvous-hash-core　A 分支：https://github.com/gy-vs/rendezvous-hash-core/tree/A　B 分支：https://github.com/gy-vs/rendezvous-hash-core/tree/B

存为 `verify_hrw.mjs`（放在仓库根目录）

```javascript
import { RendezvousRouter } from './dist/index.js';

const labeled = [
  { id: 'node-a', weight: 1, labels: ['rack-1'], domain: 'rack-1' },
  { id: 'node-b', weight: 4, labels: ['rack-1'], domain: 'rack-1' },
  { id: 'node-c', weight: 2, labels: ['rack-2'], domain: 'rack-2' },
];

let r = new RendezvousRouter(labeled);
if (r.size === 0 && typeof r.addNodes === 'function') {
  r.addNodes(labeled);
}

console.log('size', r.size);
console.log('api', typeof r.select, typeof r.pick, typeof r.selectReplicas, typeof r.pickReplicas, typeof r.nodes);

const pickOne = (key) => {
  if (typeof r.select === 'function') {
    const n = r.select(key);
    return n && n.id;
  }
  return r.pick(key);
};
const pickK = (key, k) => {
  if (typeof r.selectReplicas === 'function') {
    return r.selectReplicas(key, k).map((n) => n.id).join(',');
  }
  return r.pickReplicas(key, k).join(',');
};

console.log('pick', pickOne('user:123'));
console.log('replicas', pickK('user:123', 2));

try {
  if (typeof r.nodes === 'function') {
    console.log('nodes', r.nodes().map((n) => n.id).join(','));
  } else {
    console.log('nodes', typeof r.nodes);
  }
} catch (e) {
  console.log('nodes', e.name);
}

try {
  const r2 = new RendezvousRouter([{ id: 'a', weight: 1 }], { hash: () => -1n });
  const v = typeof r2.select === 'function' ? r2.select('k') : r2.pick('k');
  console.log('hash-neg', v);
} catch (e) {
  console.log('hash-neg', e.name);
}

try {
  const r3 = new RendezvousRouter({ hash: () => 0n });
  if (typeof r3.addNode === 'function') {
    r3.addNode({ id: 'z', weight: 1 });
    r3.addNode({ id: 'a', weight: 1 });
    console.log('zero-score', r3.scores('k').map((s) => s.id + ':' + String(s.score)).join(','));
  } else {
    console.log('zero-score', 'no-addNode');
  }
} catch (e) {
  console.log('zero-score', e.name);
}
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/rendezvous-hash-core.git rendezvous-hash-core-A
cd rendezvous-hash-core-A
npm ci
npm run build
npm test                                                                 # 预期：38 passed
node verify_hrw.mjs                                                      # 预期：size 3；api function undefined function undefined object；pick node-b；replicas node-b,node-c；nodes object；hash-neg TypeError；zero-score TypeError
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/rendezvous-hash-core.git rendezvous-hash-core-B
cd rendezvous-hash-core-B
npm install
npm run build                                                            # 预期：tsc 报 Duplicate identifier 'nodes'，仍会写出 dist
npm test                                                                 # 预期：pretest 即 tsc，Duplicate identifier 'nodes'，测试未跑
node verify_hrw.mjs                                                      # 预期：size 3；api undefined function undefined function object；pick node-b；replicas node-b,node-c；nodes object；hash-neg undefined；zero-score a:-Infinity,z:-Infinity
cd ..
```

---

## 第 103 题　0-1 代码生成　·　困难　·　无界面
<!-- solo-report:task=103 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/async-phaser-core　A 分支：https://github.com/gy-vs/async-phaser-core/tree/A　B 分支：https://github.com/gy-vs/async-phaser-core/tree/B

存为 `verify_phaser.mjs`（放在仓库根目录）

```javascript
import { Phaser } from './dist/src/phaser.js';

const p = new Phaser();
const a = p.register();
const b = p.register();
console.log('snap', JSON.stringify(p.snapshot));
a.arrive();
try {
  a.arrive();
  console.log('dup-same', 'ok');
} catch (e) {
  console.log('dup-same', e.name);
}
console.log('after-dup', JSON.stringify(p.snapshot));

try {
  a.arriveAndDeregister();
  console.log('aad-after', 'ok', JSON.stringify(p.snapshot));
} catch (e) {
  console.log('aad-after', e.name);
}

const p2 = new Phaser();
const x = p2.register();
const y = p2.register();
try {
  x.deregister();
  console.log('deregister', 'ok', JSON.stringify(p2.snapshot));
} catch (e) {
  console.log('deregister', e.name);
}

const p3 = new Phaser();
const u = p3.register();
u.arriveAndDeregister();
console.log('term', JSON.stringify(p3.snapshot));
try {
  p3.register();
  console.log('reg-after-term', 'ok');
} catch (e) {
  console.log('reg-after-term', e.name);
}

const p4 = new Phaser();
const m = p4.register();
const n = p4.register();
const w = m.awaitAdvance();
m.arrive();
n.arrive();
console.log('wait', JSON.stringify(await w));

console.log('phaser-await', typeof p4.awaitAdvance);
if (typeof p4.awaitAdvance === 'function') {
  const past = await p4.awaitAdvance(0);
  console.log('past-phase', JSON.stringify(past));
}

const p5 = new Phaser();
const t1 = p5.register();
const t2 = p5.register();
const w1 = t1.awaitAdvance();
const w2 = t2.awaitAdvance();
t1.arriveAndDeregister();
t2.arriveAndDeregister();
const r1 = await w1;
const r2 = await w2;
console.log('term-wait', JSON.stringify(r1), r1 === r2);
if (typeof p5.awaitAdvance === 'function') {
  const later = await p5.awaitAdvance(0);
  console.log('term-same', later === r1, JSON.stringify(later));
}

const p6 = new Phaser();
const c = p6.register();
const d = p6.register();
const ac = new AbortController();
const w6 = c.awaitAdvance(ac.signal);
ac.abort('cancel');
try {
  await w6;
  console.log('cancel', 'resolved', JSON.stringify(p6.snapshot));
} catch (e) {
  console.log('cancel', String(e), JSON.stringify(p6.snapshot));
}
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/async-phaser-core.git async-phaser-core-A
cd async-phaser-core-A
npm ci
npm run build
npm test                                                                 # 预期：20 passed
node verify_phaser.mjs                                                   # 预期：snap 含 registered；dup-same / aad-after 均为 DuplicateArrivalError；deregister ok；wait 为 {type:advanced,phase:1}；phaser-await undefined；term-wait {type:terminated} true；cancel 后 unarrived 仍为 2
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/async-phaser-core.git async-phaser-core-B
cd async-phaser-core-B
npm ci
npm run build
npm test                                                                 # 预期：22 passed
node verify_phaser.mjs                                                   # 预期：snap 含 parties；aad-after ok；deregister TypeError；wait 为 {status:advanced,phase:1}；phaser-await function；past-phase {status:advanced,phase:1}；term-same true；cancel 后 unarrived 仍为 2
cd ..
```

---

## 第 104 题　0-1 代码生成　·　困难　·　无界面
<!-- solo-report:task=104 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/framed-stream-core　A 分支：https://github.com/gy-vs/framed-stream-core/tree/A　B 分支：https://github.com/gy-vs/framed-stream-core/tree/B

存为 `verify_frame.mjs`（放在仓库根目录）

```javascript
import { encodeFrame, FrameDecoder } from './dist/index.js';

const f = encodeFrame(new TextEncoder().encode('hello'));
console.log('hex', Buffer.from(f).toString('hex'));

const probe = new FrameDecoder({ onFrame() {}, onError() {} });
console.log('api', typeof probe.push, typeof probe.write, typeof probe.finish, typeof probe.end);

function feed(decoder, chunk) {
  if (typeof decoder.push === 'function') decoder.push(chunk);
  else decoder.write(chunk);
}
function finish(decoder) {
  return typeof decoder.finish === 'function' ? decoder.finish() : decoder.end();
}
function textOf(p) {
  return p && p.payload ? new TextDecoder().decode(p.payload) : new TextDecoder().decode(p);
}

const frames = [];
const errors = [];
const d = new FrameDecoder({
  onFrame(p) {
    frames.push(textOf(p));
  },
  onError(e) {
    errors.push(e.code);
  },
});
for (const b of f) feed(d, Uint8Array.of(b));
console.log('byte-feed', JSON.stringify(frames), JSON.stringify(finish(d)), JSON.stringify(errors));

const frames2 = [];
const errors2 = [];
const d2 = new FrameDecoder({
  onFrame(p) {
    frames2.push(textOf(p));
  },
  onError(e) {
    errors2.push(e.code);
  },
});
const bad = Uint8Array.from(f);
bad[bad.length - 1] ^= 0xff;
const stream = new Uint8Array(bad.length + f.length);
stream.set(bad, 0);
stream.set(f, bad.length);
feed(d2, stream);
console.log('crc-recover', JSON.stringify(frames2), JSON.stringify(errors2), JSON.stringify(finish(d2)));

const d3 = new FrameDecoder({
  onFrame() {},
  onError(e) {
    console.log('half-err', e.code);
  },
});
feed(d3, f.subarray(0, 4));
console.log('half', JSON.stringify(finish(d3)));
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/framed-stream-core.git framed-stream-core-A
cd framed-stream-core-A
npm ci
npm run build
npm test                                                                 # 预期：58 passed
node verify_frame.mjs                                                    # 预期：hex 以 9d6d33c1 开头；api function undefined function number；byte-feed ["hello"] {"ok":true,"remaining":0}；crc-recover 报 ERR_CRC_MISMATCH 后仍产出 hello；half 为 ERR_PARTIAL_FRAME
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/framed-stream-core.git framed-stream-core-B
cd framed-stream-core-B
npm ci
npm run build
npm test                                                                 # 预期：44 passed
node verify_frame.mjs                                                    # 预期：hex 以 9d4a3f21 开头；api undefined function undefined function；byte-feed ["hello"] {"clean":true,"pendingBytes":0}；crc-recover 报 crc-mismatch 后仍产出 hello；half-err truncated-frame，half 为 {"clean":false,"pendingBytes":4}
cd ..
```

---

## 第 105 题　0-1 代码生成　·　困难　·　无界面
<!-- solo-report:task=105 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/text-anchor-transform-core　A 分支：https://github.com/gy-vs/text-anchor-transform-core/tree/A　B 分支：https://github.com/gy-vs/text-anchor-transform-core/tree/B

存为 `verify_anchor.mjs`（放在仓库根目录）

```javascript
import { transform } from './dist/src/index.js';

const r = transform(
  'hello world',
  [{ start: 6, end: 8, text: 'XYZ' }],
  [
    { kind: 'point', offset: 6, affinity: 'left' },
    { kind: 'point', offset: 6, affinity: 'right' },
  ],
);
console.log('text', r.text);
console.log('anchors', JSON.stringify(r.anchors));
try {
  console.log('mapBack7', JSON.stringify(r.reverse.mapBack(7)));
} catch (e) {
  console.log('mapBack7', e.name);
}
try {
  console.log('query7', JSON.stringify(r.reverse.query(7)));
} catch (e) {
  console.log('query7', e.name);
}

const r2 = transform(
  'abcdefgh',
  [{ start: 0, end: 4, text: 'XY' }],
  [{ kind: 'point', offset: 4, affinity: 'left' }],
);
console.log('del-end', r2.text, JSON.stringify(r2.anchors));

const r3 = transform('abcd', [{ start: 0, end: 4, text: '' }], []);
try {
  console.log('full-del-back', JSON.stringify(r3.reverse.mapBack(0)));
} catch (e) {
  console.log('full-del-back', e.name);
}
try {
  console.log('full-del-query', JSON.stringify(r3.reverse.query(0)));
} catch (e) {
  console.log('full-del-query', e.name);
}

try {
  transform('abcd', [
    { start: 0, end: 2, text: 'x' },
    { start: 1, end: 3, text: 'y' },
  ]);
  console.log('overlap', 'ok');
} catch (e) {
  console.log('overlap', e.name, e.code || '');
}

const emoji = 'a\u{1F600}b';
try {
  const rs = transform(emoji, [{ start: 2, end: 2, text: 'x' }], []);
  console.log('surr', rs.text);
} catch (e) {
  console.log('surr', e.name, e.code || '');
}

try {
  const r4 = transform('hello', [{ start: 1, end: 2, text: 'X' }], [{ offset: 1, affinity: 'left' }]);
  console.log('no-kind', JSON.stringify(r4.anchors));
} catch (e) {
  console.log('no-kind', e.name, e.code || '');
}
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/text-anchor-transform-core.git text-anchor-transform-core-A
cd text-anchor-transform-core-A
npm ci
npm run build
npm test                                                                 # 预期：29 passed
node verify_anchor.mjs                                                   # 预期：text hello XYZrld；anchors [6,9]；mapBack7 {kind:inserted,left:6,right:8}；query7 TypeError；del-end XYefgh [0]；full-del-back {kind:mapped,offset:0}；overlap EditValidationError；surr 切开代理对后的文本；no-kind [1]
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/text-anchor-transform-core.git text-anchor-transform-core-B
cd text-anchor-transform-core-B
npm ci
npm run build
npm test                                                                 # 预期：26 passed
node verify_anchor.mjs                                                   # 预期：anchors 为 point 对象；mapBack7 TypeError；query7 {type:inserted,left:6,right:8}；del-end XYefgh [{"kind":"point","offset":2}]；full-del-query {type:inserted,left:0,right:4}；overlap TransformError OVERLAP；surr TransformError SURROGATE_SPLIT；no-kind TransformError INVALID_ANCHOR
cd ..
```

---

## 第 106 题　Bug 修复　·　困难　·　无界面
<!-- solo-report:task=106 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/httpx-url-encoding-core　A 分支：https://github.com/gy-vs/httpx-url-encoding-core/tree/A　B 分支：https://github.com/gy-vs/httpx-url-encoding-core/tree/B

存为 `verify_url_tab.py`（放在仓库根目录）

```python
import httpx

try:
    httpx.URL("https://example.org").copy_with(path="/\t")
    print("ok")
except httpx.InvalidURL:
    print("InvalidURL")
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/httpx-url-encoding-core.git httpx-url-encoding-core-A
cd httpx-url-encoding-core-A
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e . "pytest<8" trio uvicorn
python -m pytest tests/models/test_url.py -q   # 预期：123 passed
python -c "import httpx; u=httpx.URL('https://example.com/a%20b c?x=1%2F2/y'); print(u); print(u.raw_path, u.query); print(httpx.URL(str(u))==u)"   # 预期：https://example.com/a%20b%20c?x=1%2F2%2Fy / b'/a%20b%20c?x=1%2F2%2Fy' b'x=1%2F2%2Fy' / True
python -c "import httpx; u=httpx.URL('https://example.org/a%20b/?c=d e&f=/g'); print(u); print(u.raw_path, u.query)"   # 预期：https://example.org/a%20b/?c=d%20e&f=%2Fg / b'/a%20b/?c=d%20e&f=%2Fg' b'c=d%20e&f=%2Fg'
python -c "import httpx; u=httpx.URL('https://example.org').copy_with(username='a:b', password='c:d@e'); print(u, u.username, u.password)"   # 预期：https://a%3Ab:c%3Ad%40e@example.org a:b c:d@e
python -c "import httpx; u=httpx.URL('https://example.org').copy_with(password='a%20b'); print(u, u.password)"   # 预期：https://:a%2520b@example.org a%20b
python verify_url_tab.py   # 预期：InvalidURL
deactivate
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/httpx-url-encoding-core.git httpx-url-encoding-core-B
cd httpx-url-encoding-core-B
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e . "pytest<8" trio uvicorn
python -m pytest tests/models/test_url.py -q   # 预期：157 passed
python -c "import httpx; u=httpx.URL('https://example.com/a%20b c?x=1%2F2/y'); print(u); print(u.raw_path, u.query); print(httpx.URL(str(u))==u)"   # 预期：https://example.com/a%20b%20c?x=1%2F2%2Fy / b'/a%20b%20c?x=1%2F2%2Fy' b'x=1%2F2%2Fy' / True
python -c "import httpx; u=httpx.URL('https://example.org/a%20b/?c=d e&f=/g'); print(u); print(u.raw_path, u.query)"   # 预期：https://example.org/a%20b/?c=d%20e&f=%2Fg / b'/a%20b/?c=d%20e&f=%2Fg' b'c=d%20e&f=%2Fg'
python -c "import httpx; u=httpx.URL('https://example.org').copy_with(username='a:b', password='c:d@e'); print(u, u.username, u.password)"   # 预期：https://a%3Ab:c%3Ad%40e@example.org a:b c:d@e
python -c "import httpx; u=httpx.URL('https://example.org').copy_with(password='a%20b'); print(u, u.password)"   # 预期：https://:a%20b@example.org a b
python verify_url_tab.py   # 预期：InvalidURL
deactivate
cd ..
```
## 第 107 题　Bug 修复　·　困难　·　无界面
<!-- solo-report:task=107 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/jinja-template-globals-core　A 分支：https://github.com/gy-vs/jinja-template-globals-core/tree/A　B 分支：https://github.com/gy-vs/jinja-template-globals-core/tree/B

存为 `verify_globals.py`（放在仓库根目录）

```python
from collections import ChainMap
from jinja2 import Environment
from jinja2.loaders import DictLoader

env = Environment(loader=DictLoader({'foo': '{{ bar }}'}))
t = env.get_template('foo', globals={'bar': 1})
print('first', t.render(), type(t.globals).__name__, isinstance(t.globals, ChainMap))
t2 = env.get_template('foo', globals={'bar': 2})
print('second', t2.render(), 'same', t is t2)
print('pollute', 'bar' in env.globals)
print('cached_again', env.get_template('foo').render())

env2 = Environment(loader=DictLoader({
    'child': '{% include "foo" %}{% include "foo" without context %}',
    'foo': '{{ bar }}',
}))
env2.get_template('foo', globals={'bar': 'cached'})
print('include', env2.get_template('child', globals={'bar': 'parent'}).render())

env3 = Environment(loader=DictLoader({
    'macros': '{% macro m() %}{{ bar }}{% endmacro %}',
    'child': '{% from "macros" import m %}{{ m() }}',
}))
env3.get_template('macros', globals={'bar': 'cached'})
print('import', env3.get_template('child', globals={'bar': 'parent'}).render())

print('docs_chainmap', 'ChainMap' in open('docs/api.rst', encoding='utf-8').read())
loader = open('tests/test_loader.py', encoding='utf-8').read()
print('has_a_include_name', 'test_cached_include_import_globals' in loader)
print('has_b_include_name', 'test_cached_template_globals_include_import' in loader)
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/jinja-template-globals-core.git jinja-template-globals-core-A
cd jinja-template-globals-core-A
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e . "pytest<8" "markupsafe<2.1"
python -m pytest tests/test_loader.py -q -k globals                   # 预期：观察 passed
python verify_globals.py                                            # 预期：first 1 ChainMap True；second 2 same True；pollute False；cached_again 2；include parentcached；import cached；docs_chainmap False；has_a_include_name True；has_b_include_name False
deactivate
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/jinja-template-globals-core.git jinja-template-globals-core-B
cd jinja-template-globals-core-B
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e . "pytest<8" "markupsafe<2.1"
python -m pytest tests/test_loader.py -q -k globals                   # 预期：观察 passed
python verify_globals.py                                            # 预期：渲染与 A 相同；docs_chainmap True；has_a_include_name False；has_b_include_name True
deactivate
cd ..
```

---

## 第 109 题　Bug 修复　·　困难　·　无界面
<!-- solo-report:task=109 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/acorn-delayed-errors-core　A 分支：https://github.com/gy-vs/acorn-delayed-errors-core/tree/A　B 分支：https://github.com/gy-vs/acorn-delayed-errors-core/tree/B

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/acorn-delayed-errors-core.git acorn-delayed-errors-core-A
cd acorn-delayed-errors-core-A
npm ci
npm run build:main
npm run build:loose
node test/run.js                                                         # 预期：Total 13621 tests run，all passed
node -e "const acorn=require('./acorn/dist/acorn.js'); try { acorn.parse('x = {a = 0}.y',{ecmaVersion:2020}); console.log('ok'); } catch (e) { console.log(e.message); }"   # 预期：Shorthand property assignments are valid only in destructuring patterns (1:7)
node -e "const acorn=require('./acorn/dist/acorn.js'); try { acorn.parse('x = {a = 0}[0]',{ecmaVersion:2020}); console.log('ok'); } catch (e) { console.log(e.message); }"   # 预期：Shorthand property assignments are valid only in destructuring patterns (1:7)
node -e "const acorn=require('./acorn/dist/acorn.js'); try { acorn.parse('x = {a = 0}?.y',{ecmaVersion:2020}); console.log('ok'); } catch (e) { console.log(e.message); }"   # 预期：Shorthand property assignments are valid only in destructuring patterns (1:7)
node -e "const acorn=require('./acorn/dist/acorn.js'); try { acorn.parse('for ({a = 0}.x of y);',{ecmaVersion:2020}); console.log('ok'); } catch (e) { console.log(e.message); }"   # 预期：Shorthand property assignments are valid only in destructuring patterns (1:8)
node -e "const acorn=require('./acorn/dist/acorn.js'); const ast=acorn.parse('({a = 0} = x)',{ecmaVersion:2020}); console.log(ast.body[0].expression.left.type);"   # 预期：ObjectPattern
node -e "const acorn=require('./acorn/dist/acorn.js'); try { acorn.parse('({a = 0}) => x',{ecmaVersion:2020}); console.log('ok'); } catch (e) { console.log(e.message); }"   # 预期：ok
node -e "const fs=require('fs'); console.log(fs.readFileSync('acorn/src/parseutil.js','utf8').includes('isolateExpressionErrors'));"   # 预期：true
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/acorn-delayed-errors-core.git acorn-delayed-errors-core-B
cd acorn-delayed-errors-core-B
npm ci
npm run build:main
npm run build:loose
node test/run.js                                                         # 预期：Total 13617 tests run，all passed
node -e "const acorn=require('./acorn/dist/acorn.js'); try { acorn.parse('x = {a = 0}.y',{ecmaVersion:2020}); console.log('ok'); } catch (e) { console.log(e.message); }"   # 预期：Shorthand property assignments are valid only in destructuring patterns (1:7)
node -e "const acorn=require('./acorn/dist/acorn.js'); try { acorn.parse('x = {a = 0}[0]',{ecmaVersion:2020}); console.log('ok'); } catch (e) { console.log(e.message); }"   # 预期：Shorthand property assignments are valid only in destructuring patterns (1:7)
node -e "const acorn=require('./acorn/dist/acorn.js'); try { acorn.parse('x = {a = 0}?.y',{ecmaVersion:2020}); console.log('ok'); } catch (e) { console.log(e.message); }"   # 预期：Shorthand property assignments are valid only in destructuring patterns (1:7)
node -e "const acorn=require('./acorn/dist/acorn.js'); try { acorn.parse('for ({a = 0}.x of y);',{ecmaVersion:2020}); console.log('ok'); } catch (e) { console.log(e.message); }"   # 预期：Shorthand property assignments are valid only in destructuring patterns (1:8)
node -e "const acorn=require('./acorn/dist/acorn.js'); const ast=acorn.parse('({a = 0} = x)',{ecmaVersion:2020}); console.log(ast.body[0].expression.left.type);"   # 预期：ObjectPattern
node -e "const acorn=require('./acorn/dist/acorn.js'); try { acorn.parse('({a = 0}) => x',{ecmaVersion:2020}); console.log('ok'); } catch (e) { console.log(e.message); }"   # 预期：ok
node -e "const fs=require('fs'); console.log(fs.readFileSync('acorn/src/parseutil.js','utf8').includes('isolateExpressionErrors'));"   # 预期：false
cd ..
```

---

## 第 110 题　Bug 修复　·　困难　·　无界面
<!-- solo-report:task=110 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/async-queue-signal-cleanup-core　A 分支：https://github.com/gy-vs/async-queue-signal-cleanup-core/tree/A　B 分支：https://github.com/gy-vs/async-queue-signal-cleanup-core/tree/B

存为 `verify_abort.mjs`（放在仓库根目录）

```javascript
import { getEventListeners } from 'node:events';
import PQueue from './dist/index.js';

const ac = new AbortController();
const q = new PQueue({ concurrency: 8 });
const tasks = [];
for (let i = 0; i < 40; i++) {
  tasks.push(q.add(() => i, { signal: ac.signal }));
}
await Promise.all(tasks);
console.log('after-done', getEventListeners(ac.signal, 'abort').length);
let userFired = 0;
ac.signal.addEventListener('abort', () => {
  userFired += 1;
}, { once: true });
ac.abort();
console.log('after-abort-user', userFired, getEventListeners(ac.signal, 'abort').length);

const ac2 = new AbortController();
const q2 = new PQueue({ concurrency: 2 });
try {
  await q2.add(() => new Promise(() => {}), { signal: ac2.signal, timeout: 30 });
} catch (e) {
  console.log('timeout', e.name);
}
console.log('timeout-listeners', getEventListeners(ac2.signal, 'abort').length);

const ac3 = new AbortController();
const q3 = new PQueue({ concurrency: 2 });
try {
  await q3.add(() => {
    throw new Error('boom');
  }, { signal: ac3.signal });
} catch (e) {
  console.log('fail', e.message);
}
console.log('fail-listeners', getEventListeners(ac3.signal, 'abort').length);

const ac4 = new AbortController();
ac4.abort();
const q4 = new PQueue();
try {
  await q4.add(() => 1, { signal: ac4.signal });
} catch (e) {
  console.log('preabort', e.name);
}
console.log('preabort-listeners', getEventListeners(ac4.signal, 'abort').length);

const ac5 = new AbortController();
const q5 = new PQueue({ concurrency: 1 });
const p = q5.add(() => new Promise((resolve) => setTimeout(resolve, 80)), { signal: ac5.signal });
setTimeout(() => ac5.abort(), 10);
try {
  await p;
  console.log('run-abort', 'ok');
} catch (e) {
  console.log('run-abort', e.name);
}
console.log('run-abort-listeners', getEventListeners(ac5.signal, 'abort').length);
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/async-queue-signal-cleanup-core.git async-queue-signal-cleanup-core-A
cd async-queue-signal-cleanup-core-A
npm install
npm run build
node --import=tsx/esm --test test/abort-cleanup.ts                       # 预期：12 passed
node verify_abort.mjs                                                    # 预期：after-done 0；after-abort-user 1 0；timeout TimeoutError 且 timeout-listeners 0；fail boom 且 fail-listeners 0；preabort AbortError；run-abort AbortError 且 run-abort-listeners 0
node -e "const fs=require('fs'); const t=fs.readFileSync('test/abort-cleanup.ts','utf8'); console.log(t.includes('dispatchCount'), t.includes('settleCount'));"   # 预期：true false
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/async-queue-signal-cleanup-core.git async-queue-signal-cleanup-core-B
cd async-queue-signal-cleanup-core-B
npm install
npm run build
node --import=tsx/esm --test test/abort-cleanup.ts                       # 预期：10 passed
node verify_abort.mjs                                                    # 预期：与 A 相同，成功/失败/超时/预取消/运行中取消后监听器均为 0
node -e "const fs=require('fs'); const t=fs.readFileSync('test/abort-cleanup.ts','utf8'); console.log(t.includes('dispatchCount'), t.includes('settleCount'));"   # 预期：false true
cd ..
```

---

## 第 112 题　Bug 修复　·　困难　·　无界面
<!-- solo-report:task=112 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/markdown-autolink-entity-core　A 分支：https://github.com/gy-vs/markdown-autolink-entity-core/tree/A　B 分支：https://github.com/gy-vs/markdown-autolink-entity-core/tree/B

存为 `verify_auto.mjs`（放在仓库根目录）

```javascript
import {Marked, Lexer} from './lib/marked.esm.js';

const m = new Marked({gfm: true});
console.log('auto-amp', JSON.stringify(m.parse('<http://example.com/a?b=1&amp;c=2>')));
console.log('auto-quote', JSON.stringify(m.parse('<http://example.com/a?q=&#34;x&#34;>')));
console.log('auto-num', JSON.stringify(m.parse('<http://example.com/&#65;>')));
console.log('inline-amp', JSON.stringify(m.parse('[x](http://example.com/a?b=1&c=2)')));
console.log('image-amp', JSON.stringify(m.parse('![x](http://example.com/a?b=1&c=2)')));
const t1 = Lexer.lex('<http://example.com/a?b=1&amp;c=2>');
const t2 = Lexer.lex('<http://example.com/a?b=1&amp;c=2>');
console.log('repeat-same', JSON.stringify(t1) === JSON.stringify(t2));
const para = t1[0];
const link = para && para.tokens ? para.tokens.find(x => x.type === 'link') : undefined;
console.log('token-href', link && link.href);
console.log('isAutolink', link && link.isAutolink);
const custom = new Marked({
  gfm: true,
  renderer: {
    link({href, text}) {
      return 'HREF=' + href + '|TEXT=' + text;
    },
  },
});
console.log('custom', custom.parse('<http://example.com/a?b=1&amp;c=2>'));
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/markdown-autolink-entity-core.git markdown-autolink-entity-core-A
cd markdown-autolink-entity-core-A
npm ci
npm run build:esbuild
node --test --test-reporter=spec test/run-spec-tests.js                  # 预期：含 autolinks_charrefs 与 links_charrefs_unchanged
node --test --test-reporter=spec test/unit/Autolink.test.js              # 预期：命名 / 数字引用、mailto、百分号、自定义 renderer、重复 parse 通过
node verify_auto.mjs                                                    # 预期：auto-amp href 为 &amp;c=2；auto-quote / auto-num 保留实体；inline-amp 与 image-amp 仍是裸 &；isAutolink true；custom 拿到未解码目标
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/markdown-autolink-entity-core.git markdown-autolink-entity-core-B
cd markdown-autolink-entity-core-B
npm ci
npm run build:esbuild
node --test --test-reporter=spec test/run-spec-tests.js                  # 预期：specs 通过，没有 links_charrefs_unchanged
node --test --test-reporter=spec test/unit/Autolink.test.js              # 预期：没有这个文件，ERR_MODULE_NOT_FOUND
node verify_auto.mjs                                                    # 预期：auto-quote href 变成 %22；auto-num href 变成 A；inline-amp 与 image-amp 的 & 被转成 &amp;；isAutolink undefined；custom 拿到已解码 href
cd ..
```

---

## 第 113 题　Bug 修复　·　困难　·　无界面
<!-- solo-report:task=113 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/markdown-indented-code-core　A 分支：https://github.com/gy-vs/markdown-indented-code-core/tree/A　B 分支：https://github.com/gy-vs/markdown-indented-code-core/tree/B

存为 `verify_indent.mjs`（放在仓库根目录）

```javascript
import {marked, Lexer} from './lib/marked.esm.js';
import fs from 'node:fs';

const cases = [
  ['tab-vt', '\t\v\n'],
  ['then-para', '\t\v\npara\n'],
  ['in-list', '- item\n\t\v\n'],
  ['normal-blank', '    code\n    \n'],
  ['code-then-para', '    code\n    \nparagraph\n'],
];
for (const [name, md] of cases) {
  const t = Date.now();
  const html = marked.parse(md);
  const ms = Date.now() - t;
  const tokens = new Lexer().lex(md);
  console.log(name, ms + 'ms', JSON.stringify(html), 'types', tokens.map(x => x.type).join(','));
}
console.log('worker-a', fs.existsSync('test/unit/fixtures/lex-timeout-worker.mjs'));
console.log('test-b', fs.existsSync('test/unit/indentedCodeBlankLine.test.js'));
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/markdown-indented-code-core.git markdown-indented-code-core-A
cd markdown-indented-code-core-A
npm ci
npm run build:esbuild
node --test --test-reporter=spec test/unit/Lexer.test.js                 # 预期：缩进代码空白行一组用例通过，worker 带超时
node --test test/run-spec-tests.js                                      # 预期：含 code_blank_line redos，specs 通过
node verify_indent.mjs                                                  # 预期：各输入数毫秒内返回；tab-vt 为 pre/code；then-para 后跟 p；worker-a true test-b false
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/markdown-indented-code-core.git markdown-indented-code-core-B
cd markdown-indented-code-core-B
npm ci
npm run build:esbuild
node --test --test-reporter=spec test/unit/Lexer.test.js                 # 预期：既有 Lexer 用例通过，没有 A 侧那组超时 worker 用例
node --test test/run-spec-tests.js                                      # 预期：specs 通过
node verify_indent.mjs                                                  # 预期：HTML / token 类型与 A 相同；worker-a false test-b true
cd ..
```

---

## 第 114 题　Bug 修复　·　困难　·　无界面
<!-- solo-report:task=114 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/markdown-hook-isolation-core　A 分支：https://github.com/gy-vs/markdown-hook-isolation-core/tree/A　B 分支：https://github.com/gy-vs/markdown-hook-isolation-core/tree/B

存为 `verify_iso.mjs`（放在仓库根目录）

```javascript
import {Marked} from './lib/marked.esm.js';
import fs from 'node:fs';

function gate() {
  let release;
  const p = new Promise(r => {
    release = r;
  });
  return {p, release};
}

const seen = [];
const g1 = gate();
const g2 = gate();
const m = new Marked();
m.use({
  async: true,
  hooks: {
    async preprocess(src) {
      seen.push('pre:' + this.options.tag + ':' + src.trim());
      if (this.options.tag === 'A') {
        g1.release();
        await g2.p;
      } else {
        await g1.p;
        g2.release();
      }
      return src;
    },
    postprocess(html) {
      seen.push('post:' + this.options.tag);
      return html;
    },
  },
});
const [a, b] = await Promise.all([
  m.parse('alpha', {tag: 'A'}),
  m.parse('beta', {tag: 'B'}),
]);
console.log('interleave', JSON.stringify(a).trim(), JSON.stringify(b).trim());
console.log('seen', seen.join(','));

const tags = [];
const inst = new Marked({
  tokenizer: {
    heading() {
      tags.push((this.options && this.options.testTag) || 'none');
      if (this.options && this.options.testTag === 'outer') {
        inst.parse('## nested', {testTag: 'inner'});
        tags.push('after:' + ((this.options && this.options.testTag) || 'none'));
        tags.push('lexer:' + ((this.lexer && this.lexer.options && this.lexer.options.testTag) || 'none'));
      }
      return false;
    },
  },
});
const html = inst.parse('# title\n', {testTag: 'outer'});
console.log('tok-html', JSON.stringify(html));
console.log('tok-tags', tags.join(','));
console.log('sync-type', typeof new Marked().parse('hi'));
console.log('file-concurrent', fs.existsSync('test/unit/concurrent-parse.test.js'));
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/markdown-hook-isolation-core.git markdown-hook-isolation-core-A
cd markdown-hook-isolation-core-A
npm ci
npm run build:esbuild
node --test --test-reporter=spec test/unit/Hooks.test.js                 # 预期：Hooks concurrent parses 一组通过
node --test --test-reporter=spec test/unit/concurrent-parse.test.js      # 预期：ERR_MODULE_NOT_FOUND（没有这个文件）
node verify_iso.mjs                                                     # 预期：interleave 各自输出 alpha / beta；tok-html 为 <h1></h1>；tok-tags 含 after:inner 与 lexer:inner；sync-type string；file-concurrent false
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/markdown-hook-isolation-core.git markdown-hook-isolation-core-B
cd markdown-hook-isolation-core-B
npm ci
npm run build:esbuild
node --test --test-reporter=spec test/unit/Hooks.test.js                 # 预期：既有 hooks 用例通过，没有 concurrent parses 分组
node --test --test-reporter=spec test/unit/concurrent-parse.test.js      # 预期：交错、不同 options、tokenizer / renderer 重入隔离全部通过
node verify_iso.mjs                                                     # 预期：interleave 与 A 相同；tok-html 为 <h1>title</h1>；tok-tags 含 after:outer 与 lexer:outer；sync-type string；file-concurrent true
cd ..
```

---

## 第 117 题　Feature 迭代　·　困难　·　无界面
<!-- solo-report:task=117 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/jinja-native-macro-core　A 分支：https://github.com/gy-vs/jinja-native-macro-core/tree/A　B 分支：https://github.com/gy-vs/jinja-native-macro-core/tree/B

存为 `verify_native_macro.py`（放在仓库根目录）

```python
from jinja2 import DictLoader, Environment
from jinja2.nativetypes import NativeEnvironment
from jinja2.runtime import Undefined

s = '{% macro m() %}{{ x }}{% endmacro %}{{ m() }}'
print('native_list', type(NativeEnvironment().from_string(s).render(x=[1, 2])).__name__, NativeEnvironment().from_string(s).render(x=[1, 2]))
print('plain_list', type(Environment().from_string(s).render(x=[1, 2])).__name__, Environment().from_string(s).render(x=[1, 2]))
print('native_num', type(NativeEnvironment().from_string(s).render(x=42)).__name__, NativeEnvironment().from_string(s).render(x=42))
print('undef', type(NativeEnvironment().from_string('{% macro m() %}{{ missing }}{% endmacro %}{{ m() }}').render()).__name__)
print('multi', NativeEnvironment().from_string('{% macro m() %}{{ a }}{{ b }}{% endmacro %}{{ m() }}').render(a=1, b=2))
print('nested', NativeEnvironment().from_string('{% macro i() %}{{ x }}{% endmacro %}{% macro o() %}{{ i() }}{% endmacro %}{{ o() }}').render(x=[1]))

e = NativeEnvironment(loader=DictLoader({
    'base': '{% block c %}{{ v }}{% endblock %}',
    'child': '{% extends "base" %}{% block c %}{{ super() }}{% endblock %}',
}))
try:
    r = e.get_template('child').render(v=[1, 2])
    print('super', repr(r), type(r).__name__)
except Exception as err:
    print('super', type(err).__name__, err)

print('blockref_env', 'environment.concat' in open('src/jinja2/runtime.py', encoding='utf-8').read())
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/jinja-native-macro-core.git jinja-native-macro-core-A
cd jinja-native-macro-core-A
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e . "pytest<8" "markupsafe<2.1"
python -m pytest tests/test_nativetypes.py -q                        # 预期：观察 passed
python verify_native_macro.py                                       # 预期：native_list list [1, 2]；plain_list str [1, 2]；native_num int 42；undef Undefined；multi 12；nested [1]；super [1, 2] list；blockref_env True
deactivate
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/jinja-native-macro-core.git jinja-native-macro-core-B
cd jinja-native-macro-core-B
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e . "pytest<8" "markupsafe<2.1"
python -m pytest tests/test_nativetypes.py -q                        # 预期：观察 passed
python verify_native_macro.py                                       # 预期：宏返回类型与 A 相同；super TypeError sequence item 0: expected str instance, list found；blockref_env False
deactivate
cd ..
```

---

## 第 118 题　Feature 迭代　·　困难　·　无界面
<!-- solo-report:task=118 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/jinja-loop-neighbor-core　A 分支：https://github.com/gy-vs/jinja-loop-neighbor-core/tree/A　B 分支：https://github.com/gy-vs/jinja-loop-neighbor-core/tree/B

存为 `verify_loop_neighbor.py`（放在仓库根目录）

```python
import collections
import collections.abc
import inspect
import os

if not hasattr(collections, 'Mapping'):
    collections.Mapping = collections.abc.Mapping
    collections.MutableMapping = collections.abc.MutableMapping
    collections.Sequence = collections.abc.Sequence
    collections.Iterable = collections.abc.Iterable
    collections.Iterator = collections.abc.Iterator

if not hasattr(inspect, 'getargspec'):
    inspect.getargspec = inspect.getfullargspec

from jinja2 import Environment, StrictUndefined

print('group', Environment().from_string('{% for i in seq %}{% if loop.previtem is defined and i != loop.previtem %}|{% endif %}{{ i }}{% endfor %}').render(seq=[1, 1, 2, 3, 3]))
print('neighbors', Environment().from_string('{% for item in seq %}[{{ loop.previtem }}|{{ item }}|{{ loop.nextitem }}]{% endfor %}').render(seq=[1, 2, 3]))
print('single', Environment().from_string('{% for i in seq %}[{{ loop.previtem is defined }}|{{ i }}|{{ loop.nextitem is defined }}]{% endfor %}').render(seq=[9]))
print('gen_len', Environment().from_string('{% for item in seq %}[{{ item }}|{{ loop.length }}|{{ loop.revindex }}|{{ loop.last }}]{% endfor %}').render(seq=(x for x in range(3))))

try:
    Environment(undefined=StrictUndefined).from_string('{% for i in [1] %}{{ loop.previtem }}{% endfor %}').render()
    print('strict', 'no error')
except Exception as e:
    print('strict', type(e).__name__, e)

tags = open('tests/test_core_tags.py', encoding='utf-8').read()
async_src = open('tests/test_async.py', encoding='utf-8').read()
print('has_break_lookahead', 'test_adjacent_items_generator_break_lookahead' in tags)
print('has_continue_test', 'test_adjacent_items_continue' in tags)
print('has_length_test', 'test_generator_length_last_revindex' in tags)
print('async_def_tests', 'async def test_loop' in async_src)
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/jinja-loop-neighbor-core.git jinja-loop-neighbor-core-A
cd jinja-loop-neighbor-core-A
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e . "pytest<8" "markupsafe<2.1"
python -m pytest tests/test_core_tags.py tests/test_async.py -q       # 预期：观察 passed；async def 用例可能被跳过
python verify_loop_neighbor.py                                      # 预期：group 11|2|33；neighbors [|1|2][1|2|3][2|3|]；single [False|9|False]；gen_len [0|3|3|False][1|3|2|False][2|3|1|True]；strict UndefinedError loop has no previous item；has_break_lookahead False；has_continue_test False；has_length_test False；async_def_tests True
deactivate
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/jinja-loop-neighbor-core.git jinja-loop-neighbor-core-B
cd jinja-loop-neighbor-core-B
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e . "pytest<8" "markupsafe<2.1"
python -m pytest tests/test_core_tags.py tests/test_async.py -q       # 预期：观察 passed
python verify_loop_neighbor.py                                      # 预期：分组与邻居输出同 A；strict UndefinedError 'loop.previtem' is undefined；has_break_lookahead True；has_continue_test True；has_length_test True；async_def_tests False
deactivate
cd ..
```

---

## 第 119 题　Feature 迭代　·　困难　·　无界面
<!-- solo-report:task=119 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/attrs-exception-core　A 分支：https://github.com/gy-vs/attrs-exception-core/tree/A　B 分支：https://github.com/gy-vs/attrs-exception-core/tree/B

存为 `verify_auto_exc.py`（放在仓库根目录）

```python
import copy
import os
import pickle
import attr

E = attr.make_class('E', {'x': attr.ib(), 'y': attr.ib(init=False, default=42)}, bases=(Exception,), auto_exc=True)
e = E(1)
print('repr', repr(e))
print('str', str(e))
print('args', e.args)
print('fields', e.x, e.y)
print('copy', copy.deepcopy(e).x)

K = attr.make_class('K', {'x': attr.ib(), 'y': attr.ib(kw_only=True)}, bases=(Exception,), auto_exc=True)
k = K(1, y=2)
print('kw_repr', repr(k))
print('kw_args', k.args, k.y)

try:
    @attr.s(auto_exc=True)
    class U(Exception):
        x = attr.ib()

        def __init__(self, x):
            self.x = x
            self.custom = True

    u = U(3)
    print('user_init', u.x, getattr(u, 'custom', None))
except Exception as err:
    print('user_init', type(err).__name__, err)

print('has_dark', 'test_auto_exc' in open('tests/test_dark_magic.py', encoding='utf-8').read())
print('has_exc_tests', os.path.exists('tests/test_exceptions.py'))
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/attrs-exception-core.git attrs-exception-core-A
cd attrs-exception-core-A
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e . pytest hypothesis
python -m pytest tests/test_dark_magic.py -q                         # 预期：观察 passed
python verify_auto_exc.py                                           # 预期：repr E(x=1, y=42)；str 1；args (1,)；fields 1 42；copy 1；kw_repr K(x=1, y=2)；kw_args (1, 2) 2；user_init 3 None；has_dark True；has_exc_tests False
deactivate
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/attrs-exception-core.git attrs-exception-core-B
cd attrs-exception-core-B
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e . pytest hypothesis
python -m pytest tests/test_dark_magic.py -q                         # 预期：无 test_auto_exc，观察既有用例
python verify_auto_exc.py                                           # 预期：repr E(1)；str 1；args (1,)；kw_repr K(1)；kw_args (1,) 2；user_init ValueError Can't add __init__ to exception class；has_dark False；has_exc_tests True
deactivate
cd ..
```

---

## 第 120 题　Feature 迭代　·　困难　·　无界面
<!-- solo-report:task=120 generated=2026-09-20 -->

仓库：https://github.com/gy-vs/attrs-pickle-state-core　A 分支：https://github.com/gy-vs/attrs-pickle-state-core/tree/A　B 分支：https://github.com/gy-vs/attrs-pickle-state-core/tree/B

存为 `verify_getstate.py`（放在仓库根目录）

```python
import os
import pickle
import attr

C = attr.make_class('C', ['x'], slots=True)
print('slots_default', '__getstate__' in C.__dict__, '__setstate__' in C.__dict__)
print('roundtrip', pickle.loads(pickle.dumps(C(1), protocol=2)))
state = C(1).__getstate__()
print('state_type', type(state).__name__, state)

D = attr.make_class('D', ['x'], slots=True, getstate_setstate=False)
print('explicit_off', '__getstate__' in D.__dict__, '__setstate__' in D.__dict__)

E = attr.make_class('E', ['x'], slots=False, getstate_setstate=True)
print('nonslots_on', '__getstate__' in E.__dict__, '__setstate__' in E.__dict__)

print('has_attrs_pkg', os.path.isdir('src/attrs'))
print('has_next_gen', os.path.exists('src/attr/_next_gen.py'))
print('has_test_gss', os.path.exists('tests/test_getstate_setstate.py'))
print('has_test_pickle', os.path.exists('tests/test_pickle.py'))

try:
    import attrs
    print('import_attrs', True)
except Exception as e:
    print('import_attrs', type(e).__name__)
```

A 侧：

```powershell
git clone -b A --single-branch https://github.com/gy-vs/attrs-pickle-state-core.git attrs-pickle-state-core-A
cd attrs-pickle-state-core-A
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e . pytest hypothesis cloudpickle pympler
python -m pytest tests/test_getstate_setstate.py -q                  # 预期：观察 passed；文件存在
python verify_getstate.py                                           # 预期：slots_default True True；roundtrip C(x=1)；state_type tuple (1,)；explicit_off False False；nonslots_on True True；has_attrs_pkg True；has_next_gen False；has_test_gss True；has_test_pickle False；import_attrs True
deactivate
cd ..
```

B 侧：

```powershell
git clone -b B --single-branch https://github.com/gy-vs/attrs-pickle-state-core.git attrs-pickle-state-core-B
cd attrs-pickle-state-core-B
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e . pytest hypothesis cloudpickle pympler
python -m pytest tests/test_getstate_setstate.py -q                  # 预期：文件不存在，pytest 报 file not found 或收集失败
python verify_getstate.py                                           # 预期：slots_default True True；roundtrip C(x=1)；state_type dict {'x': 1}；explicit_off False False；nonslots_on True True；has_attrs_pkg False；has_next_gen True；has_test_gss False；has_test_pickle True；import_attrs ImportError
deactivate
cd ..
```
