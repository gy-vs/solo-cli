"""GSB 理由的写作规范与判废规则。

这份表同时喂给三个地方：写理由的 prompt、落库前的清洗、上传前的核验。三处必须共用
一份，否则会出现「prompt 里没禁、核验却拦」的死循环，人在界面上改到第五遍也过不了。

规则对齐的是 solo-qa 的 GSB 质检链路（backend/gsb/），不是它旧的五维质检：
- 理由内容由 R1～R11 判，映射到 G5（理由不合格）、G6（与轨迹不符）、G7（Same 敷衍）；
- AI 化是一次独立的 0～10 分评分，达到 4 分即按 G5 打回；
- 另外复用旧 E1 硬指纹（AI 自指、对话脚手架、套话、markdown、emoji、模板编号）。

要特别记住 AI 化那一项判的是什么，因为它和直觉相反：**写得书面、术语密集、句子长、
篇幅大、段落对称、通篇没有「我」，这些都不算 AI 痕迹**，solo-qa 的评分提示词里逐条
写明了不扣分。真正被判成机器写的是「只有程序才数得出来的量」——步号、工具调用次数、
总步数、增删行数、耗时秒数、file.js:120-136 这种行号区间，以及由这些数字堆出来的
密度。所以这里禁的是数字和步号，不是书面语。

早先这个项目反着来：禁掉「首先/其次/综上/非常/十分」并强制第一人称口语。那份表既拦
不住真正会被打回的东西，又把正常的书面表达判成违规。现在按 solo-qa 的实际口径重写。

表里现在有两类规则，别把它们混在一起看：
- 硬的那类对应平台会打回的东西（机器指标、E1 硬指纹、空洞套话），核验里是红项；
- 软的那类是篇幅、开头句式与措辞，平台不管，但它们决定了这段话读起来像不像一个人
  在给评审意见。两千字、每道题同一个开场、「分水岭」「差一口气」这种词，单看哪条
  都不违规，摞在一起就不像人写的了。这类在核验里只提示，不拦提交。
"""

from __future__ import annotations

import re

# ---------------- 长度 ----------------
# solo-qa 的结构校验按「去掉空白后的可见字符」算，下限 60。
# Same 要论证两边确实等价，比选边更费笔墨，这里自己加高，免得交上去被 G7 判敷衍。
MIN_REASON_CHARS = 60
MIN_SAME_REASON_CHARS = 150

# 上限是我们自己的要求，平台不会因为写得长而打回。但两千字的理由必然带着真人
# 评审观察不到的颗粒度——每个函数名、每处判定、每条用例都点到，读起来就是机器
# 在逐条核对，而不是一个人在给意见。五六百字够把一两个决定胜负的点讲透。
REASON_TARGET_MIN = 500
REASON_TARGET_MAX = 600
REASON_SOFT_MAX_CHARS = 620


# ---------------- AI 化：只有程序数得出来的量 ----------------
# 这是 AI 化评分里权重最高的一维（满分即总分保底 6 分，直接越过 4 分的打回线），
# 所以这几类写法一个都不能留。

# 「第 64 步」「第 19、20 步」「第 48 到 51 步」「步骤 12」「第 3 轮」
STEP_REF = re.compile(
    r"[在于]?\s*第\s*\d+\s*(?:[、,，和及]\s*\d+\s*|(?:到|至|-|~)\s*\d+\s*)*[步轮次]\s*(?:里|中|上|时|的时候)?"
    r"|[在于]?\s*步骤\s*\d+(?:\s*[、,，和及到至-]\s*\d+)*\s*(?:里|中|上|时|的时候)?"
)

# 「113 次工具调用」「86 次 Bash」「25 次编辑」「总步数 81」「交互 47 轮」
TOOL_COUNT = re.compile(
    r"\d+\s*次\s*(?:工具|调用|工具调用|Bash|Edit|Write|Read|Grep|Glob|编辑|读取|搜索|写入|提交)"
    r"|(?:总)?(?:步数|步骤数|工具调用|调用次数|交互轮次|轮次|轮数)\s*(?:是|为|达|共)?\s*\d+"
    r"|\d+\s*轮\s*(?:交互|对话|问答)", re.I)

# 「lib/dumper.js:120-136」「stateMachine.js:88」——文件名可以写，钉到行号就是机器在报位置
FILE_LINE = re.compile(r"[\w.\-/]+\.\w{1,6}\s*[:：]\s*\d+(?:\s*[-–~]\s*\d+)?")

# 「+199/−24」「新增 1895 行」「删除 24 行」「改动 30 个文件」
DIFF_STAT = re.compile(
    r"[+＋]\s*\d+\s*[/／]\s*[-−–]\s*\d+"
    r"|(?:新增|增加|删除|删去|改动|修改|变更)\s*\d+\s*(?:行|个文件|处|个测试)"
    r"|\d+\s*(?:行代码|个文件)\s*(?:新增|删除|改动|修改)")

# 「约 46 分钟」「耗时 150 秒」——平台明确不认耗时差异，写了既是 AI 痕迹又是 R5 违规
DURATION = re.compile(r"(?:耗时|用时|花了|历时|约)\s*\d+(?:\.\d+)?\s*(?:秒|分钟|小时|s\b|min\b)"
                      r"|\d+(?:\.\d+)?\s*(?:秒|分钟|小时)\s*(?:内|就|才|完成|跑完)")

# (核验项名, 给人看的说法, 正则)。核验项名要分开，合成一个「机器指标」会让界面上
# 只显示一条笼统的红项，人不知道该改哪句话。
MACHINE_METRICS: tuple[tuple[str, str, re.Pattern], ...] = (
    ("reason_step_ref", "步数说法", STEP_REF),
    ("reason_tool_count", "工具调用计数", TOOL_COUNT),
    ("reason_file_line", "文件行号区间", FILE_LINE),
    ("reason_diff_stat", "增删行数统计", DIFF_STAT),
    ("reason_duration", "耗时", DURATION),
)


# ---------------- AI 化：工具输出搬运 ----------------
# 固定分栏、终端统计原文、一口气列一串符号名，都是把材料原样倒出来而不是在说话。

# 「【产物】」「好：」「不好：」「优点：」这种固定栏目
SECTION_LABEL = re.compile(
    r"【[^】\n]{1,12}】"
    r"|^[ \t]*(?:好|不好|优点|缺点|产物|过程|结论|问题|证据|分析|建议|改进|不足)\s*[:：]",
    re.M)

# 「# tests 32 # pass 32 # fail 0」「43 过 1 败」「6/18 失败」
TERMINAL_DUMP = re.compile(
    r"#\s*(?:tests?|pass(?:ing)?|fail(?:ing|ed)?|skip)\b\s*\d+"
    r"|\d+\s*(?:过|通过)\s*\d+\s*(?:败|失败)"
    r"|\b\d+\s*/\s*\d+\s*(?:失败|通过|passing|failing)\b", re.I)


def symbol_run(text: str, limit: int = 5) -> str:
    """一口气列出 limit 个以上的符号名（测试名、函数名、文件名）就算搬运。

    单个文件名、函数名是正常引用，串起来列就是在倒工具输出。按顿号和逗号切，
    连续片段里全是标识符才算——正常句子里混着动词和虚词，不会整段都是符号。
    """
    ident = re.compile(r"^[A-Za-z_][\w.\-]*(?:\(\))?$")
    for chunk in re.split(r"[。；;\n]", text or ""):
        run = 0
        for part in re.split(r"[、,，]\s*", chunk):
            run = run + 1 if ident.match(part.strip()) else 0
            if run >= limit:
                return chunk.strip()[:80]
    return ""


# ---------------- AI 化：数字密度 ----------------
# 每百字超过 2 个精确数字就满分。业务里该出现的数字（版本号、错误码）不必躲，
# 但不能靠数字堆出对比。
NUMBER = re.compile(r"(?<![\w.])\d+(?:\.\d+)?(?![\w])")
NUMBER_PER_100_LIMIT = 2.0


def number_density(text: str) -> tuple[int, float]:
    """返回 (精确数字个数, 每百字密度)。"""
    body = re.sub(r"\s+", "", text or "")
    if not body:
        return 0, 0.0
    count = len(NUMBER.findall(text or ""))
    return count, round(count * 100 / len(body), 2)


# ---------------- E1 硬指纹 ----------------
# 这几类命中即判，和 AI 化评分是两套，solo-qa 的 GSB 链路两套都跑。

SELF_REFERENCE = (
    "作为一个AI", "作为一个 AI", "作为AI", "作为 AI", "作为一名AI",
    "作为大语言模型", "作为一个大语言模型", "作为一个大模型", "作为大模型",
    "作为人工智能", "作为一个人工智能", "作为AI助手", "作为 AI 助手",
    "我是一个AI", "我是一个人工智能", "我是一个大语言模型",
    "作为语言模型", "身为AI", "本AI",
)

CHAT_SCAFFOLD = (
    "以下是我的分析", "以下是我的评价", "以下是我的看法", "以上是我的分析",
    "以上就是我的", "希望这些能帮到你", "希望这些能帮到您", "希望对你有帮助",
    "希望对您有帮助", "希望能帮到你", "如果你还有其他问题", "如果您还有其他问题",
    "如有其他问题", "如有任何疑问", "请随时告诉我", "随时告诉我",
    "我可以帮你", "我可以为你", "需要我进一步", "需要我继续",
    "下面我将", "下面我来", "接下来我将为你", "很高兴为你",
    "好的，我来", "好的，以下",
)

# 单独出现一个不算违规，凑够两个才判。所以写的时候不必刻意躲开「综上所述」，
# 只是别把这类过渡词当段落骨架反复用。
DELIVERY_CLICHE = (
    "综上所述", "总而言之", "总的来说", "总体而言", "总结如下", "归纳如下",
    "值得注意的是", "需要注意的是", "值得一提的是", "由此可见", "不难看出",
    "简而言之", "一言以蔽之", "最后总结", "总结来看", "整体来看",
    "从以上分析可以看出", "综合来看",
)
DELIVERY_CLICHE_MIN = 2

# 序数三组齐全 + 两个以上栏目标签，才算模板结构
ORDINAL_GROUPS = (
    ("首先", "第一点"),
    ("其次", "然后", "再者", "第二点"),
    ("最后", "总之", "综上", "第三点"),
)
TEMPLATE_LABELS = (
    "问题", "表现", "现象", "原因", "影响", "证据", "分析", "结论", "建议",
    "改进", "优点", "缺点", "不足", "亮点", "风险", "总结", "说明", "举例",
    "具体表现", "存在问题", "改进建议", "核心问题", "主要问题",
)

MD_HEADING = re.compile(r"(?m)^\s{0,3}#{1,6}\s+\S")
MD_BULLET = re.compile(r"(?m)^\s{0,3}(?:[-*+]|\d+[.)])\s+")
MD_BOLD = re.compile(r"\*{1,3}([^*\n]+?)\*{1,3}")
MD_CODE = re.compile(r"`{1,3}([^`\n]+?)`{1,3}")
MD_HR = re.compile(r"(?m)^\s{0,3}(?:-{3,}|\*{3,}|_{3,})\s*$")
MD_ANY = re.compile(r"(?m)(^\s{0,3}#{1,6}\s)|(^\s{0,3}[-*+]\s)|(\*\*)|(`)|(^\s{0,3}>\s)")

EMOJI = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF"
    "\uFE0F\u2705\u274C\u2757\u2753\u2714\u2716\u26A0\u2B50\u2B06\u2B07\u203C\u2728\u2764\u2B55\u3030]")


# ---------------- 空洞套话 ----------------
# 删掉这些之后剩下的实质内容不足一半，就是通篇在说「差不多」「各有优劣」。
HOLLOW_PHRASES = (
    "表现一般", "基本可用", "还可以", "没什么问题", "问题不大", "整体不错",
    "符合预期", "达到预期", "表现良好", "比较好", "还行", "一般般",
    "没有问题", "无明显问题", "尚可", "可以接受", "完成得不错", "做得不错",
    "表现尚可", "总体良好", "整体良好",
    "效果一样好", "效果差不多", "表现差不多", "水平差不多", "没有明显差别",
    "看不出差别", "看不出区别", "难分高下", "各有优劣", "半斤八两",
    "旗鼓相当", "势均力敌", "都不错", "都还行", "都一般",
    "更好一些", "略好一点", "稍微好一点", "明显更好", "更胜一筹",
)
SUBSTANCE_RATIO = 0.5


def substance_ratio(text: str) -> float:
    """删掉空洞套话后剩下的字符比例。"""
    body = re.sub(r"\s+", "", text or "")
    if not body:
        return 0.0
    stripped = body
    for phrase in HOLLOW_PHRASES:
        stripped = stripped.replace(phrase, "")
    return round(len(stripped) / len(body), 3)


def visible_chars(text: str) -> int:
    return len(re.sub(r"\s+", "", text or ""))


def cliche_hits(text: str) -> list[str]:
    return [w for w in DELIVERY_CLICHE if w in (text or "")]


def ordinal_template(text: str) -> bool:
    """三组序数词齐全，且带两个以上栏目标签，才算模板骨架。"""
    body = text or ""
    if not all(any(w in body for w in group) for group in ORDINAL_GROUPS):
        return False
    labels = sum(1 for lab in TEMPLATE_LABELS if re.search(rf"(?m)^\s*{lab}\s*[:：]", body))
    return labels >= 2


# ---------------- 措辞 ----------------
# 这一组和平台规则无关，平台不会因为写得口语或者写得花哨而打回。它对应的是
# 「读起来像不像一个人在给评审意见」：比喻性的名词是在写修辞，大白话是在聊天，
# 模棱两可的表态是在和稀泥，三者都不是工程判断该有的样子。
#
# 注意这里禁的不是「正式」。写得正式、用词专业从来不扣分，要躲的是另外两头：
# 一头是把问题包装成「分水岭」「这笔账」这种意象，一头是「差一口气」「手搓」
# 这种随口说法。中间那条路——普通、直接、把事说清楚——才是要的。
WORD_SWAPS: tuple[tuple[str, str], ...] = (
    # 比喻性名词：用意象代替事实，读者还得自己翻译一遍
    ("分水岭", "直说「但是差别在……」"),
    ("这笔账", "直说是什么问题"),
    ("那笔账", "直说是什么问题"),
    ("欠的账", "「做得不够的是……」"),
    ("没账要算", "「也有做得不好的地方」"),
    ("留了个洞", "「留了个缺口」"),
    ("留了条缝", "「留了隐患」"),
    ("那层皮", "直说是哪一层，例如「对外的类型声明」"),
    ("软肋", "直说是哪一处做得不够"),
    ("命门", "直说是哪一处做得不够"),
    ("七寸", "直说是哪一处做得不够"),
    # 大白话：随口说法，不适合写进交付给评审方的意见
    ("差一口气", "「相较差了一点」"),
    ("差了一口气", "「相较差了一点」"),
    ("手搓", "「自己重新写了一套」"),
    ("老实得多", "「做法相对保守」"),
    ("朴素得多", "「实现简单得多」"),
    ("摆得乱", "「组织比较乱」"),
    ("对得住", "「和运行时一致」这类直说"),
    ("栽在", "「输在」或直说错在哪里"),
    ("绕远路", "直说多花了哪些工夫"),
    # 模棱两可的表态：认为对就说对，认为不够就说哪里不够
    ("我认", "去掉，直接说结论"),
    ("姑且算", "去掉，给明确判断"),
    ("见仁见智", "去掉，给明确判断"),
    ("不好说", "去掉，给明确判断"),
    # 翻译腔术语：换成中文里更常用的说法
    ("契约", "「标准」或「约定」"),
    ("建模", "「实现」"),
    ("语义偏移", "「行为不一致」"),
    ("心智负担", "直说维护时要多做什么"),
    # 虚的结论：说了等于没说，评审方无法据此判断严重程度
    ("维护观感", "写清楚这个问题谁会在什么时候撞上"),
    ("观感上", "写清楚具体后果"),
    ("并非全盘", "「并不是所有的点都……」"),
)


def word_swap_hits(text: str) -> list[tuple[str, str]]:
    """返回命中的（词，建议改法）。"""
    body = text or ""
    return [(w, s) for w, s in WORD_SWAPS if w in body]


# ---------------- 开头句式 ----------------
# 一道题看不出模板，几道题摆在一起就看得出：同样的开场、同样的段落顺序、
# 同样的收尾。这是跨题才能发现的问题，所以核验时拿本题的开头去比其他题的开头。
# 取前八个字：短了会把「两侧都……」这类自然开头误判成雷同，长了又几乎撞不上。
# 八个字刚好覆盖「这道题我比较在意」这种整句式的开场——真正要拦的就是它被反复套用。
OPENING_SIGNATURE_CHARS = 8


def opening_signature(text: str) -> str:
    """取理由开头的句式骨架。

    去掉 A、B、文件名、数字和标点之后，剩下的就是句式本身。「这道题我比较在意
    两点」这类固定开场，后面接什么内容都一样，签名因此能对上。
    """
    head = re.split(r"[。；\n]", (text or "").strip(), maxsplit=1)[0]
    head = re.sub(r"[A-Za-z0-9_.\-/]+", "", head)
    head = re.sub(r"[\s，、：:,。！？…—~()（）「」『』\"'‘’“”]", "", head)
    return head[:OPENING_SIGNATURE_CHARS]


# ---------------- 只看理由文本的那些规则 ----------------
# 这一组的判定只需要理由本身（外加结论和别的题的开头），所以生成时就能自查，
# 不必等到上传前核验。两个地方共用这一个函数：分析生成完先拿它挑毛病、让模型
# 照着改；上传前核验再拿它出红黄项。写成两份的下场是 prompt 里没禁、核验却拦，
# 人在界面上改到第五遍也过不了。
#
# 要对照两侧材料才能判的规则（理由提到的文件是否真实存在）不在这里，留在核验里。

ABS_PATH = re.compile(r"(?<![\w.])/(?:[A-Za-z0-9_.\-\u4e00-\u9fff]+/)+")


def reason_checks(text: str, *, verdict: str = "",
                  peer_openings: dict | None = None) -> list[tuple[str, str, str]]:
    """查理由文本，返回 (核验项名, 轻重, 给人看的说法)。

    轻重只对核验界面有意义：block 对应平台会打回的东西，warn 对应篇幅、措辞、
    开头句式这类平台不管但读起来不像人写的毛病。生成时自查不分轻重，列出来的
    都要改。
    """
    out: list[tuple[str, str, str]] = []
    reason = text or ""

    n = visible_chars(reason)
    floor = MIN_SAME_REASON_CHARS if verdict == "Same" else MIN_REASON_CHARS
    if n < floor:
        extra = "，Same 要论证两边确实等价，比选边更费笔墨" if verdict == "Same" else ""
        out.append(("reason_length", "block", f"理由去掉空白只有 {n} 字，不足 {floor} 字{extra}"))
    if not re.search(r"\bA\b|A\s*侧", reason) or not re.search(r"\bB\b|B\s*侧", reason):
        out.append(("reason_both_sides", "block", "理由里没有分别写到 A 和 B 两侧"))

    # ---- 只有程序数得出来的量 ----
    for name, label, pattern in MACHINE_METRICS:
        if m := pattern.search(reason):
            out.append((name, "block",
                        f"理由里有{label}（{m.group(0).strip()[:40]}），"
                        f"这是 AI 化评分里权重最高的一类证据，位置该用文件名和函数名来指"))
    count, density = number_density(reason)
    if density > NUMBER_PER_100_LIMIT:
        out.append(("reason_number_density", "block",
                    f"理由里有 {count} 个精确数字，每百字 {density} 个，"
                    f"超过每百字 {NUMBER_PER_100_LIMIT} 个的线"))
    if chunk := symbol_run(reason):
        out.append(("reason_symbol_dump", "block",
                    f"理由里连着罗列了一串符号名（{chunk}），这是在搬运工具输出"))
    if m := TERMINAL_DUMP.search(reason):
        out.append(("reason_terminal_dump", "block",
                    f"理由里有终端输出原文（{m.group(0).strip()[:40]}）"))
    if m := SECTION_LABEL.search(reason):
        out.append(("reason_section_label", "block",
                    f"理由里有固定分栏（{m.group(0).strip()[:20]}），平台的理由框是纯文本"))
    if MD_ANY.search(reason):
        out.append(("reason_markdown", "block",
                    "理由里有 markdown 记号（标题、列表符号、加粗或反引号），平台的理由框不渲染"))
    if EMOJI.search(reason):
        out.append(("reason_emoji", "block", "理由里有表情符号"))

    # ---- E1 硬指纹与空洞套话 ----
    hits = cliche_hits(reason)
    if len(hits) >= DELIVERY_CLICHE_MIN:
        out.append(("reason_cliche", "block",
                    f"理由里有 {len(hits)} 个交付套话（{'、'.join(hits[:5])}），"
                    f"凑够两个就会被判成模板"))
    if ordinal_template(reason):
        out.append(("reason_template", "block",
                    "理由是「首先／其次／最后」加栏目标签的模板骨架"))
    if hit := next((p for p in SELF_REFERENCE if p in reason), ""):
        out.append(("reason_self_reference", "block", f"理由里有 AI 自指（{hit}）"))
    if hit := next((p for p in CHAT_SCAFFOLD if p in reason), ""):
        out.append(("reason_chat_scaffold", "block", f"理由里有对话腔（{hit}）"))
    ratio = substance_ratio(reason)
    if ratio < SUBSTANCE_RATIO:
        out.append(("reason_hollow", "block",
                    f"删掉「各有优劣」「表现良好」这类空话后只剩 {int(ratio * 100)}% 的内容，"
                    f"不足一半，整段没有落到具体事实上"))

    # 理由会原样交给评审方，绝对路径写进去等于把本机目录结构一起交出去
    if m := ABS_PATH.search(reason):
        out.append(("reason_abs_path", "block",
                    f"理由里有绝对路径（{m.group(0)[:40]}），会把本机目录结构一起交出去"))

    # ---- 篇幅、措辞、开头句式 ----
    if n > REASON_SOFT_MAX_CHARS:
        out.append(("reason_too_long", "warn",
                    f"理由 {n} 字，超过 {REASON_TARGET_MAX} 字的上限；"
                    f"挑一两个决定胜负的点展开，其余一句带过"))
    if swaps := word_swap_hits(reason):
        word, suggest = swaps[0]
        more = f"，另有 {'、'.join(w for w, _ in swaps[1:4])}" if len(swaps) > 1 else ""
        out.append(("reason_wording", "warn",
                    f"理由里有「{word}」这类比喻或口语说法{more}，改成{suggest}"))
    sig = opening_signature(reason)
    if sig:
        same = sorted(no for no, s in (peer_openings or {}).items()
                      if s and (s == sig or s.startswith(sig) or sig.startswith(s)))
        if same:
            out.append(("reason_opening_repeat", "warn",
                        f"开头的句式和第 {'、'.join(same[:3])} 题一样（{sig}），"
                        f"按这道题自己的矛盾换一个写法"))
    return out


def findings_checks(findings: dict, *, label: str = "") -> list[str]:
    """查一侧 findings 的每一条，返回要改的地方。

    规范说的是「reason 与 findings 里每一条都按这个来」，所以这里共用同一批表。
    不分红黄：findings 不上传给平台（只有 reason 会），核验那边管的是会被打回的
    东西，这些条目进不了核验，列出来的都是生成时该改掉的。

    有三类不能照搬理由的口径：

    - 篇幅、是否写到两侧、开头句式：findings 是一条条短句，这几条不适用。
    - 数字密度：不查。这条线是按五六百字的成段散文校准的，它防的是「靠数字堆出
      对比」。findings 是一条条十几二十个字的短句，「改了两处判定，补了三条用例」
      这种正常表述就已经超线，照搬只会逼人把该写的数字删掉。
    - 空洞套话与交付套话：按这一侧所有条目拼起来算，规范说的本来就是「整段」。
    """
    items = [(kind, i, str(t)) for kind in ("good", "bad")
             for i, t in enumerate((findings or {}).get(kind) or []) if str(t).strip()]
    out: list[str] = []

    for kind, i, text in items:
        where = f"{label}{kind}[{i}]"
        for name, desc, pattern in MACHINE_METRICS:
            if m := pattern.search(text):
                out.append(f"{where} 有{desc}（{m.group(0).strip()[:40]}）")
        if chunk := symbol_run(text):
            out.append(f"{where} 连着罗列了一串符号名（{chunk}）")
        if m := TERMINAL_DUMP.search(text):
            out.append(f"{where} 有终端输出原文（{m.group(0).strip()[:40]}）")
        if m := SECTION_LABEL.search(text):
            out.append(f"{where} 有固定分栏（{m.group(0).strip()[:20]}）")
        if MD_ANY.search(text):
            out.append(f"{where} 有 markdown 记号（标题、列表符号、加粗或反引号）")
        if EMOJI.search(text):
            out.append(f"{where} 有表情符号")
        if hit := next((p for p in SELF_REFERENCE if p in text), ""):
            out.append(f"{where} 有 AI 自指（{hit}）")
        if hit := next((p for p in CHAT_SCAFFOLD if p in text), ""):
            out.append(f"{where} 有对话腔（{hit}）")
        if swaps := word_swap_hits(text):
            word, suggest = swaps[0]
            out.append(f"{where} 有「{word}」这类比喻或口语说法，改成{suggest}")
        if m := ABS_PATH.search(text):
            out.append(f"{where} 有绝对路径（{m.group(0)[:40]}）")

    joined = "".join(t for _, _, t in items)
    if joined:
        hits = cliche_hits(joined)
        if len(hits) >= DELIVERY_CLICHE_MIN:
            out.append(f"{label}整段有 {len(hits)} 个交付套话（{'、'.join(hits[:5])}）")
        ratio = substance_ratio(joined)
        if ratio < SUBSTANCE_RATIO:
            out.append(f"{label}整段删掉空话后只剩 {int(ratio * 100)}% 的内容，没有落到具体事实上")
    return out


# ---------------- 写进 prompt 的规范 ----------------
# 只讲怎么写，不讲我们内部怎么核验。

WRITING_RULES = f"""
理由怎么写（reason 与 findings 里每一条都按这个来）：

一、篇幅与取舍
1. 正文写 {REASON_TARGET_MIN} 到 {REASON_TARGET_MAX} 字，不要超过 {REASON_TARGET_MAX} 字。
   这是给人看的评审意见，不是核对清单。
2. 只挑一到两个真正决定胜负的点展开，其余的最多一句带过，不够格的一句都不写。
   两次跑之间的差异动辄十几处，全列出来就成了清单，真人评审也观察不到那种颗粒度。
3. 挑点的依据是「哪一条决定了谁更好」，常见的有：题面明写的硬约束有没有守住、
   改动有没有引入新的错误、对外的接口与类型声明有没有被动、交付的测试是不是真跑过。
4. 赢的一方也要写到不足，输的一方也要写到长处，但都服从上面的篇幅，不要因为
   要「写全」就把每个函数名、每处判定、每条用例都点一遍。

二、不要套骨架（这一条最容易犯）
5. 不要每道题都用同一个开头、同一种段落顺序、同一句收尾。按这道题自己的矛盾来
   组织：核心差异只有一条，就一条讲透；两边各有对错，就先摆出纠结在哪再说为什么
   这样判；输的一方栽在一个具体错误上，就开门见山把那个错误说出来。
6. 段落数不固定，两段三段都行，不要凑成对称的四段。
7. 不要固定用「我比较在意两点：第一点……第二点……」这种编号句式开场。偶尔用一次
   没问题，不能每道题都这么起头。
8. 结论句也换着写，不要每篇都是「所以判 X 更好」。

三、措辞：普通、正式、直说
9. 不用比喻性的名词指代问题：分水岭、这笔账、欠的账、留了个洞、留了条缝、那层皮、
   软肋、命门，一律改成直说，例如「但是差别在……」「做得不好的地方是……」。
10. 不用大白话和口头禅：差一口气、手搓、老实得多、朴素得多、摆得乱、对得住。
    换成「相较差了一点」「自己重新写了一套」「做法相对保守」「组织比较乱」。
11. 不用模棱两可的表态：「这笔账我认」「姑且算」「见仁见智」。认为对就说对，
    认为不够就说清楚哪里不够。
12. 少用翻译腔术语：契约写成标准或约定，建模写成实现，语义偏移写成行为不一致。
13. 不写双重否定绕弯的句子：「并非全盘落后」写成「并不是所有的点都做得不好」。
14. 结论要落在具体后果上。不要写「影响只在维护观感」「整体更稳」这种虚的，要写清楚
    这个问题会让谁在什么时候撞上、补上什么才能修好。

四、必须写到的内容
15. A 和 B 分别写，各自好在哪、差在哪，不要只写「A 比 B 好」就收尾。
16. 产物和过程都要写。过程问题要说清是在哪个环节出的、模型当时具体做了什么、
    由此造成了什么后果；产物问题要指到具体文件名、函数名、报错原文，或者哪一条
    需求没实现。
17. 要写出判断依据：你更看重哪几点、为什么这几点压过了另一侧的长处。两次跑通常
    各有优劣，要体现权衡，不要给没有来由的结论。
18. 结论选 Same 时同样写足，写清哪些点确实等价、哪些点各有优劣相互抵消。
    一句话的 Same 会被直接打回。
19. 主观评价后面要跟客观依据。说「实现得更完整」就要说出是哪个功能点、在哪个文件里。

五、绝对不能出现的东西（这几类会被判成机器写的）
20. 不写步数：「第 38 步」「第 19、20 步」「步骤 12」「第 3 轮」一次都不要出现。
21. 不写只有程序数得出来的量：工具调用次数、总步数、交互轮次、新增删除了多少行、
    改了多少个文件、耗时多少秒或多少分钟。
22. 不写文件行号区间：可以写 lib/dumper.js，不要写 lib/dumper.js:120-136。
23. 不要把终端输出原样搬进来，例如「# tests 32 # pass 32 # fail 0」「43 过 1 败」。
24. 不要一口气罗列五个以上的测试名或函数名。
25. 控制数字密度：整段里精确数字不要超过每百字两个。业务本身要求的数字照写，
    但不要靠数字堆出对比。
26. 不用固定分栏：不要【产物】【过程】这类栏目，不要「好：」「不好：」，
    不要 1. 2. 3. 的编号。
27. 不用表情符号，不用 markdown（标题井号、列表符号、加粗星号、反引号都不要），
    平台的理由框是纯文本，这些记号会原样显示出来。
28. 不写自己是什么：不要出现「作为 AI」「作为大语言模型」这类话，也不要
    「以下是我的分析」「希望对你有帮助」这种对话腔。

六、容易写空的地方
29. 少用「各有优劣」「难分高下」「看不出差别」「表现良好」「基本可用」「更好一些」
    这类词。用了就必须紧跟具体的事实，否则整段会被判成没有实质内容。
30. 过渡词不必刻意躲，但不要拿「综上所述」「总的来说」「值得注意的是」当段落骨架
    反复用，同一段里出现两个以上就会被判成套话。

七、关于「正式」的分寸
31. 写得正式、用词专业不算机器痕迹，不必为了像人而刻意堆口语或者第一人称。
    要控制的是篇幅和颗粒度，不是正式程度。
32. 文件名、函数名、方法名、命令、报错原文都可以照写，这是定位问题的正常方式，
    只要不带行号。路径太长时可以只写文件名或者说清是哪个目录，不必背全路径。

八、不作为判断依据的因素
33. 只写模型自身能力造成的差异。推理快慢、网络波动、网关超时、请求失败、
    模型没报错但戛然而止，这几类都受部署和排队影响，不反映能力，不写进理由。
    如果某一侧确实出现了这类情况，只在 remark 里写一句说明。
34. 提到文件只写仓库内的相对路径，例如 lib/rules_inline.mjs。不要出现任何绝对
    路径或本机目录名——这段理由会原样交给评审方，写进去等于把本地目录结构一起交出去。
35. 不写你是怎么核验的：不写有没有装依赖、能不能联网、跑没跑起来，也不要出现
    「产物副本」「沙箱」「我这边」「我的环境」。跑不起来就只依据代码和轨迹下结论。
""".strip()
