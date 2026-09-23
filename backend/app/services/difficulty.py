"""难度筛选：两侧都跑得太轻的题，在开分析之前就废弃掉。

放在这个位置是为了额度。GSB 分析是整条流水线上最贵的一步——把两侧的完整轨迹交给
Cursor CLI 读一遍，十几二十分钟的模型时间，后面还接着两道质检各一次调用。而这笔钱
花下去之前，这道题值不值得评其实已经看得出来：两侧都在半小时内收工、都只用了几十步
工具调用，说明题面对模型压根没构成难度，两边都轻松做完了，比出来的只能是 Same 或者
一点无关紧要的措辞差异。这种题交上去也换不回分数，而额度是有限的。

判据只认两个数：这一侧用了多少步、跑了多久。它们都是跑完才有的量——模型实际花了多少
工夫，事前谁也说不准。所以这一步注定排在两侧跑完之后，这不是它的缺陷而是它的位置：
出题时的难度预估归 designer 那边，这里收的是预估失准漏下来的那一批。

口径跟界面上显示的两个数完全一致：步数取 verdict.artifact.tool_calls，也就是列表行里
那个「N 步」；用时取 finished_at 减 started_at，也就是那个「容器用时」。这件事比口径
本身准不准更要紧——轨迹里另有一个 steps_count，它把模型说话的那些步也算进去，数出来
比工具调用多出三四成。用它筛，人会看到界面上写着 45 步的题被一句「不到 40 步」废弃掉，
而他手里没有任何办法对上这笔账。一把尺子量到底，哪怕这把尺子偏松。

读不到的指标一律放行，不算作 0。轨迹没导出、接管路径下 result 没采到，都会让这两个数
缺失，而「一步没调」和「还不知道」是两件事。两个方向的代价也不对等：误放一道简单题，
代价是白花一次分析额度；误废一道真题，代价是两个容器跑掉的两个多小时连同这道题一起
没了。所以拿不准就往下走。

废弃走的是现成的 DISCARDED，不另立状态：人在废弃列表里按「恢复」就能把题捞回来，
而恢复这个动作本身就是他在说「这道题我还是要评」，所以 override 会跟着记上，下一轮
巡检不会拿同一套阈值把它再废弃一次。少了这一笔，人按恢复只会看见题一闪又回到废弃
列表里，而他没做错任何事。
"""

from __future__ import annotations

import logging

from app import config
from app.db import session
from app.models import RUN_OK_STATUSES, RUN_WAITING, Task, TaskRun, as_utc, utc_now
from app.services import settings_store

log = logging.getLogger("difficulty")

# 默认阈值。这些数字必须和 settings_store 里对应 Spec 的 default 一字不差：两处对不上
# 时，设置页显示一套、实际按另一套筛，而废弃是不声不响发生的，事后没人对得出这笔账。
SCREEN_DEFAULT = True
MIN_MINUTES_DEFAULT = 30
MIN_STEPS_DEFAULT = 40
LOW_STEPS_DEFAULT = 30
LOW_PEER_STEPS_DEFAULT = 80
MID_PEER_STEPS_DEFAULT = 60

# 探路（见文件末尾那一节）。默认值取自库里 76 道两侧都跑完的题：按这条线，先跑的
# 那一侧达不到 40 步且不到 30 分钟的有 26 道，它们的另一侧最多也只走了 58 步，
# 没有一道是已提交或等录屏的题。
PROBE_DEFAULT = True
PROBE_STEPS_DEFAULT = 40
PROBE_MINUTES_DEFAULT = 30

PASS = "pass"            # 值得评，往下走
DISCARD = "discard"      # 两侧都太轻，不花这次额度
UNKNOWN = "unknown"      # 指标不全，判不了，按放行处理
SKIPPED = "skipped"      # 筛选被关掉，或者人工已经放行过


def enabled() -> bool:
    return settings_store.get_bool("difficulty.screen", SCREEN_DEFAULT)


def thresholds() -> dict:
    """当前生效的阈值。一次取齐，不要在判据里逐个去读。

    settings_store 每次取值都会自己开一条数据库连接，而这个函数的调用方多半已经在
    一个会话里了——巡检那边踩过这个坑，嵌套连接会让 SQLite 在 bind mount 上直接抛
    disk I/O error，整轮巡检当场中断（见 watchdog._scan_abnormal 的注释）。
    """
    return {
        "min_minutes": settings_store.get_int("difficulty.min_minutes", MIN_MINUTES_DEFAULT),
        "min_steps": settings_store.get_int("difficulty.min_steps", MIN_STEPS_DEFAULT),
        "low_steps": settings_store.get_int("difficulty.low_steps", LOW_STEPS_DEFAULT),
        "low_peer_steps": settings_store.get_int("difficulty.low_peer_steps", LOW_PEER_STEPS_DEFAULT),
        "mid_peer_steps": settings_store.get_int("difficulty.mid_peer_steps", MID_PEER_STEPS_DEFAULT),
    }


# ---------------- 两个数从哪儿读 ----------------

def steps_of(run: TaskRun) -> int | None:
    """这一侧的工具调用步数。读不到返回 None，不返回 0。

    只认 tool_calls 这一个来源。轨迹摘要里还有个 steps_count，缺了这个就拿那个顶上
    看着像是兜底，其实是换了一把尺子：那个数把模型说话的步也算进去，同一道题能多出
    三四成，于是「这道题多少步」的答案取决于哪个字段恰好有值。
    """
    value = ((run.verdict or {}).get("artifact") or {}).get("tool_calls")
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def minutes_of(run: TaskRun) -> float | None:
    """这一侧的容器用时（分钟）。读不到返回 None。

    先用两个时间戳相减，这是界面上显示的那个用时。它拿不到时才退到 CLI 自报的
    duration_ms——后者不含容器启动和轨迹导出的开销，比实际短几分钟，两者混用会让
    临界的题按哪个字段有值决定生死，所以顺序固定，不看哪个更大。
    """
    start, end = as_utc(run.started_at), as_utc(run.finished_at)
    if start and end:
        secs = (end - start).total_seconds()
        if secs >= 0:
            return secs / 60
    ms = ((run.verdict or {}).get("protocol") or {}).get("duration_ms")
    if isinstance(ms, (int, float)) and not isinstance(ms, bool) and ms >= 0:
        return float(ms) / 60000
    return None


def metrics(runs: list[TaskRun]) -> dict:
    """两侧的四个数，按侧归好。哪一侧读不到就留 None。"""
    by_side = {r.side: r for r in runs}
    steps: dict[str, int | None] = {}
    mins: dict[str, float | None] = {}
    for side in config.SIDES:
        run = by_side.get(side)
        steps[side] = steps_of(run) if run is not None else None
        value = minutes_of(run) if run is not None else None
        mins[side] = round(value, 1) if value is not None else None
    return {"steps": steps, "minutes": mins}


# ---------------- 判据 ----------------

def _say_steps(steps: dict) -> str:
    return "、".join(f"{s} {steps[s]} 步" for s in config.SIDES)


def _say_minutes(mins: dict) -> str:
    return "、".join(f"{s} {mins[s]:.0f} 分钟" for s in config.SIDES)


def judge(steps: dict, minutes: dict, th: dict) -> tuple[str, str]:
    """四个数 → (结论, 一句话原因)。纯函数，不碰库也不读设置。

    四条判据合起来说的是同一件事：这道题有没有难住至少一边。任何一边真被难住了，
    它的步数就会明显高于另一边——而两边都轻轻松松做完，那道题就没有可比的东西。

    所以除了「两侧都低」这两条硬线，还要看两侧的落差：一侧才二三十步，另一侧就得
    确实吃力（80 步以上）才说明差距出在题上而不是出在风格上；一侧三十几步，另一侧
    也至少要 60 步。少了这两条，一道 A 只用 25 步、B 用 45 步的题会靠 B 的 45 步过关，
    而它其实是道谁都不费劲的题，B 那 20 步之差只是它话多。

    区间写成显式的上下界而不是靠 if 的先后次序兜住：low_peer 和 mid_peer 是设置项，
    人完全可能把它们调成低的那个反而更高，那时候按次序写的版本会静静地漏判。
    """
    if any(v is None for v in steps.values()) or any(v is None for v in minutes.values()):
        missing = [s for s in config.SIDES if steps[s] is None or minutes[s] is None]
        return UNKNOWN, f"{'、'.join(missing)} 侧的步数或用时读不到，难度筛选放行"

    lo, hi = min(steps.values()), max(steps.values())
    if max(minutes.values()) < th["min_minutes"]:
        return DISCARD, (f"两侧都在 {th['min_minutes']} 分钟内跑完（{_say_minutes(minutes)}），"
                         f"题面没构成难度")
    if hi < th["min_steps"]:
        return DISCARD, (f"两侧步数都不到 {th['min_steps']} 步（{_say_steps(steps)}），"
                         f"题面没构成难度")
    if lo < th["low_steps"] and hi < th["low_peer_steps"]:
        return DISCARD, (f"一侧只用了 {lo} 步（不到 {th['low_steps']}），另一侧 {hi} 步也没到 "
                         f"{th['low_peer_steps']} 步，两侧差距不足以比出高下（{_say_steps(steps)}）")
    if th["low_steps"] <= lo < th["min_steps"] and hi < th["mid_peer_steps"]:
        return DISCARD, (f"一侧只用了 {lo} 步，另一侧 {hi} 步没到 {th['mid_peer_steps']} 步，"
                         f"两侧差距不足以比出高下（{_say_steps(steps)}）")
    return PASS, f"{_say_steps(steps)}，{_say_minutes(minutes)}，值得评"


# ---------------- 对一道题算一遍 ----------------

def evaluate(task_id: int, th: dict | None = None) -> dict:
    """算一道题的筛选结论，不落库、不废弃。试算接口和正式筛选共用这一份口径。

    阈值可以从外面传进来。试算要对整个题库逐题算一遍，而每次 thresholds() 都要开五条
    数据库连接去读设置——几百道题就是上千次查询，读回来的还是同一套数。

    人工放行过的题直接给 SKIPPED：他按过恢复，就是已经替这道题拍过板了，再算一遍
    只会得出同一个废弃结论。
    """
    th = th or thresholds()
    with session() as db:
        task = db.get(Task, task_id)
        if task is None:
            return {"ok": False, "verdict": SKIPPED, "reason": "题目不存在", "thresholds": th}
        runs = db.query(TaskRun).filter(TaskRun.task_id == task_id).all()
        task_no = task.task_no
        overridden = bool((task.difficulty_screen or {}).get("override"))
        nums = metrics(runs)

    base = {"ok": True, "task_no": task_no, "thresholds": th, **nums,
            "checked_at": utc_now().isoformat()}
    if overridden:
        return {**base, "verdict": SKIPPED, "reason": "人工已放行，不再按阈值筛"}
    if len(runs) != len(config.SIDES):
        return {**base, "verdict": UNKNOWN, "reason": "两侧的运行记录不齐，难度筛选放行"}
    verdict, reason = judge(nums["steps"], nums["minutes"], th)
    return {**base, "verdict": verdict, "reason": reason}


def screen(task_id: int) -> dict:
    """算一遍并把结论记在题上。返回 evaluate 的报告，调用方看 verdict 决定废不废。

    开关在这里判，不在 evaluate 里：关掉筛选的意思是「不要自动废弃」，而不是「连算
    都不要算」——试算接口照样要拿这套阈值出名单，那才是人决定要不要打开它的依据。

    结论要留痕，哪怕是放行：一道题后来被人质疑「这么简单为什么还评了」，得能翻出当时
    那四个数和当时的阈值。阈值是设置项，改过之后旧结论就解释不了自己了，所以连阈值
    一起存。
    """
    if not enabled():
        return {"ok": True, "verdict": SKIPPED, "reason": "难度筛选已关闭"}
    report = evaluate(task_id)
    if not report.get("ok"):
        return report
    with session() as db:
        task = db.get(Task, task_id)
        if task is None:
            return report
        # override 那一笔要保住：它是人的决定，不能被这次自动计算擦掉。
        keep = {k: v for k, v in (task.difficulty_screen or {}).items()
                if k in ("override", "override_at")}
        task.difficulty_screen = {**report, **keep}
    if report["verdict"] == DISCARD:
        log.info("题 %s 难度筛选判废弃：%s", report.get("task_no", task_id), report["reason"])
    return report


def override(task: Task) -> bool:
    """人工放行：这道题不再按阈值筛。返回有没有真的改动。

    在打开的会话里直接改传进来的 task，由调用方提交——恢复废弃题是一个事务里的事，
    状态改回去和放行记号必须一起落盘，否则中间那一瞬间是「已恢复但仍会被筛」，
    而巡检正好每三十秒就扫一遍。

    只对被筛掉的题打这个记号。别的原因废弃的题（重跑用尽、查重命中）恢复之后仍然
    该走一遍难度筛选：它们压根没被筛过，跳过等于给这一步开了个绕行口。
    """
    report = dict(task.difficulty_screen or {})
    if report.get("verdict") != DISCARD:
        return False
    report.update({"override": True, "override_at": utc_now().isoformat()})
    task.difficulty_screen = report
    return True


def preview() -> list[dict]:
    """把两侧都正常跑完的题按当前阈值试算一遍，不落库。按题号排。

    这是调阈值时唯一靠得住的办法。阈值定高一点能省下多少额度、会不会连着废掉几道
    本该评的题，光看数字想不出来，得拿手里这批题实际跑出来的步数和用时算一遍看名单。
    所以它连已经分析过、已经提交的题也一起算：那些题的结论已经不会改了，但它们正是
    用来回答「这套阈值当初会不会把它们误杀」的样本。

    两侧都得是 FINISHED 才算数，光有两条运行记录不够。跑挂、超时、被打断的那一侧
    步数天然就低——容器在半路没的，本来也没机会多走几步——把它们算进来，名单会凭空
    多出一大批「会被废弃」的题，而它们一道也不会真的走到筛选这一步：那条路上
    `_advance_pair` 只在两侧都正常收尾时才判难度，没跑成的题归重跑和次数上限管。
    库里这个差别不小：有两条运行记录的题 118 道，两侧都正常跑完的只有 76 道。
    """
    th = thresholds()
    with session() as db:
        by_task: dict[int, list[str]] = {}
        for run in db.query(TaskRun).all():
            by_task.setdefault(run.task_id, []).append(run.status)
        tasks = [(t.task_no, t.id, t.status) for t in db.query(Task).all()
                 if len(by_task.get(t.id, [])) == len(config.SIDES)
                 and all(s in RUN_OK_STATUSES for s in by_task[t.id])]
    return [{"id": tid, "status": status, **evaluate(tid, th)}
            for _, tid, status in sorted(tasks)]


# ---------------- 探路：先跑完的那一侧就够判了 ----------------
#
# 上面那套判据要等两侧都跑完，那时两个容器的机器时间已经全花出去了，它省下的只是
# 后面那次分析。探路做的是同一件事，但站在只有一侧跑完的时候：先跑完的那一侧要是
# 又快又轻，另一侧压根不必出闸。
#
# 这件事成立有个前提，得说清楚它是经验不是逻辑：一侧轻的时候另一侧不会重。库里 76 道
# 两侧都跑完的题里，先跑完那一侧不到 40 步且不到 30 分钟的有 26 道，它们的另一侧最多
# 只走了 58 步，一道已提交或等录屏的题都没有。反过来说，这条线万一撞上一道「A 秒过、
# B 卡死」的题，那道题就被白废了——所以它可以关、阈值可以调、废掉的题在废弃列表里
# 按恢复就能捞回来重跑。
#
# 能省到多少取决于调度那边怎么排。现在两侧几乎是同时放出去的（库里两侧出闸时间差
# 中位 12.5 分钟，76 道里 54 道在先跑完的那一刻另一侧已经在跑了），这种情况下就算
# 立刻判出来也没什么可省的。所以第二侧在队列里降一档排到队尾，让别的题的首侧先走，
# 等它排上来时先跑完那一侧多半已经有结论了。
#
# 降级而不是硬扣住，是因为空着的槽位比少省一点更亏。队列排空、机器闲着的时候，
# 第二侧照样出闸两侧并行，这时候拦着它一分钟机器时间也省不下来，只是白拖长这道题
# 出结果的时间。真正硬拦的只有一种：先跑完那一侧已经判出太轻，这道题下一轮巡检就要
# 废掉，那时候放另一侧出去，跑出来的东西没人会看。

PROBE_HOLD = "hold"      # 还没到判的时候（另一侧没跑完、或这一侧指标读不到）


def probe_enabled() -> bool:
    return settings_store.get_bool("difficulty.probe", PROBE_DEFAULT)


def probe_thresholds() -> dict:
    return {
        "probe_steps": settings_store.get_int("difficulty.probe_steps", PROBE_STEPS_DEFAULT),
        "probe_minutes": settings_store.get_int("difficulty.probe_minutes", PROBE_MINUTES_DEFAULT),
    }


def probe_judge(steps: int | None, minutes: float | None, th: dict) -> tuple[str, str]:
    """先跑完那一侧的两个数 → (结论, 一句话原因)。纯函数。

    两个条件要同时不达标才废，这跟两侧都跑完时那套判据不一样——那边「都不到 40 步」
    和「都不到 30 分钟」是各自独立成立的两条线。这里收紧成「且」，因为手上只有一侧
    的信息：一侧 20 步但跑了两小时，说明它在少数几步上啃了很久，那道题未必简单。

    指标读不到就等着，不当作 0：另一侧还没起，等两侧都跑完之后还有一道更准的关口。
    """
    if steps is None or minutes is None:
        return PROBE_HOLD, "这一侧的步数或用时还读不到，先不判"
    if steps < th["probe_steps"] and minutes < th["probe_minutes"]:
        return DISCARD, (f"先跑完的一侧只用了 {steps} 步、{minutes:.0f} 分钟，"
                         f"没到 {th['probe_steps']} 步也没到 {th['probe_minutes']} 分钟，"
                         f"另一侧不必再跑")
    return PASS, f"先跑完的一侧走了 {steps} 步、{minutes:.0f} 分钟，另一侧接着跑"


def _probe_one(runs: list[TaskRun], th: dict) -> tuple[str, str, str]:
    """一道题的探路结论 → (结论, 原因, 先跑完的是哪一侧)。

    只在「恰好一侧正常跑完、另一侧还在等槽位」时给出 PASS 或 DISCARD，别的情形一律
    HOLD。另一侧已经在跑的时候判它没有意义：那台容器的时间已经花下去了，这时候废掉
    整道题，省下的只是它剩下的几分钟，却要中断一次正在进行的运行。
    """
    done = [r for r in runs if r.status in RUN_OK_STATUSES]
    waiting = [r for r in runs if r.status in RUN_WAITING]
    if len(done) != 1 or len(waiting) != len(runs) - 1:
        return PROBE_HOLD, "两侧的进度不在「一侧跑完、另一侧还没出闸」这个当口", ""
    first = done[0]
    verdict, reason = probe_judge(steps_of(first), minutes_of(first), th)
    return verdict, reason, first.side


def probe_order(db, task_ids: list[int]) -> tuple[set[int], set[int]]:  # noqa: ANN001
    """这批题里在等槽位的 run，哪些不该出闸、哪些可以往后排。返回 (拦下, 降级) 两组 run_id。

    借调用方的会话查，不自己开：调度那个循环两秒一轮，每轮为几十道题各开一条连接，
    在 bind mount 上的 SQLite 迟早撞上 disk I/O error（watchdog 那边踩过）。

    这里分两档而不是一刀切，因为「不该跑」和「不着急跑」是两回事，而机器空转是比
    少省一点更实在的损失。

    拦下的只有一种：先跑完那一侧已经判出太轻了。这道题下一轮巡检就要整个废掉，这时候
    放另一侧出去，跑出来的东西没人会看。

    其余一律降级——第二侧排到队尾，别的题的首侧先走，轮完了要是还有空槽，它照样出闸。
    没动过的题、有一侧正在跑的、跑完了但指标还没落盘的、跑挂了等重跑的，都归这一档。
    它们的共同点是「还不知道这道题轻不轻」，而不知道不构成不跑的理由：槽位空着的时候
    让它等，省不下任何机器时间，只是白白拖长这道题出结果的时间。

    降级本身就能把探路做成。队列里通常有的是排队的题，第二侧被压到队尾之后，绝大多数
    时候轮不到它，等它排上来时先跑完那一侧的结论早出来了；而队列空到连它都能排上，
    说明这台机器本来就没活干。
    """
    if not (probe_enabled() and task_ids):
        return set(), set()
    th = probe_thresholds()
    by_task: dict[int, list[TaskRun]] = {}
    for run in db.query(TaskRun).filter(TaskRun.task_id.in_(task_ids)).all():
        by_task.setdefault(run.task_id, []).append(run)

    held: set[int] = set()
    deferred: set[int] = set()
    for tid, runs in by_task.items():
        if len(runs) != len(config.SIDES):
            continue
        waiting = [r for r in runs if r.status in RUN_WAITING]
        if not waiting:
            continue
        task = db.get(Task, tid)
        if task is not None and (task.difficulty_screen or {}).get("override"):
            continue    # 人工放行过的题不再拦，跟两侧都跑完那套判据同一个口径
        moved = [r for r in runs if r.status not in RUN_WAITING]
        if not moved:
            # 两侧都还没出闸：让 side 排前面的那个占住首发，另一个降级。首发不能也降级，
            # 否则整道题一起沉到队尾，探路无从开始。
            deferred |= {r.id for r in sorted(waiting, key=lambda r: r.side)[1:]}
        elif all(r.status in RUN_OK_STATUSES for r in moved):
            first = min(moved, key=lambda r: as_utc(r.finished_at) or utc_now())
            got = probe_judge(steps_of(first), minutes_of(first), th)[0]
            if got == DISCARD:
                held |= {r.id for r in waiting}
            elif got != PASS:
                # 指标还没落盘。通常几秒就写上了，降一档让它下一轮再来，
                # 别在这几秒里把一道可能要废的题放出去。
                deferred |= {r.id for r in waiting}
        else:
            deferred |= {r.id for r in waiting}
    return held, deferred


def probe(task_id: int) -> dict:
    """判一道题的探路结论并留痕。返回 verdict 为 DISCARD 时调用方负责废弃整题。

    结论记在 difficulty_screen 的 probe 一栏里，和两侧都跑完那份结论放在一起：一道题
    事后被问起「另一侧为什么一次都没跑」，凭据只有先跑完那一侧的这两个数和当时的线。
    """
    if not probe_enabled():
        return {"ok": True, "verdict": SKIPPED, "reason": "探路已关闭"}
    th = probe_thresholds()
    with session() as db:
        task = db.get(Task, task_id)
        if task is None:
            return {"ok": False, "verdict": PROBE_HOLD, "reason": "题目不存在"}
        runs = db.query(TaskRun).filter(TaskRun.task_id == task_id).all()
        if (task.difficulty_screen or {}).get("override"):
            return {"ok": True, "verdict": SKIPPED, "reason": "人工已放行，不再探路"}
        verdict, reason, side = _probe_one(runs, th)
        first = next((r for r in runs if r.side == side), None)
        report = {"verdict": verdict, "reason": reason, "side": side,
                  "steps": steps_of(first) if first is not None else None,
                  "minutes": _round(minutes_of(first)) if first is not None else None,
                  "thresholds": th, "checked_at": utc_now().isoformat()}
        if verdict != PROBE_HOLD:
            task.difficulty_screen = {**(task.difficulty_screen or {}), "probe": report}
        task_no = task.task_no
    if verdict == DISCARD:
        log.info("题 %s 探路判废弃：%s", task_no, reason)
    return {"ok": True, "task_no": task_no, **report}


def probe_preview() -> list[dict]:
    """按当前探路阈值把跑完的题试算一遍，看这条线当初会在哪些题上提前收手。

    和 preview 分开是因为问的不是同一件事：那个问「这套阈值会废掉哪些题」，这个问
    「另一侧本来可以不跑的有哪些、省下多少机器时间」。样本同样只取两侧都正常跑完的
    题——只有它们才知道另一侧后来跑了多久，也才算得出省下的那笔账。
    """
    th = probe_thresholds()
    out: list[dict] = []
    with session() as db:
        by_task: dict[int, list[TaskRun]] = {}
        for run in db.query(TaskRun).all():
            by_task.setdefault(run.task_id, []).append(run)
        for task in db.query(Task).all():
            runs = by_task.get(task.id, [])
            if len(runs) != len(config.SIDES) or any(r.status not in RUN_OK_STATUSES for r in runs):
                continue
            ordered = sorted(runs, key=lambda r: as_utc(r.finished_at) or utc_now())
            first, second = ordered[0], ordered[-1]
            verdict, reason = probe_judge(steps_of(first), minutes_of(first), th)
            out.append({"id": task.id, "task_no": task.task_no, "status": task.status,
                        "verdict": verdict, "reason": reason, "first_side": first.side,
                        "first_steps": steps_of(first), "first_minutes": _round(minutes_of(first)),
                        "peer_steps": steps_of(second), "peer_minutes": _round(minutes_of(second))})
    return sorted(out, key=lambda x: x["task_no"])


def _round(value: float | None) -> float | None:
    return round(value, 1) if value is not None else None
