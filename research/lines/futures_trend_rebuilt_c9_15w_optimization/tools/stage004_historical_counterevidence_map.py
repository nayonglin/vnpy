from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[4]
LINE_DIR = PROJECT_DIR / "research" / "lines" / "futures_trend_rebuilt_c9_15w_optimization"
OUTPUT_DIR = LINE_DIR / "outputs" / "stage004_historical_counterevidence_map"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage004"
MODEL_TAG = "stage004_historical_counterevidence_map_v1"

PROHIBITED_PATH = OUTPUT_DIR / f"rebuilt_c9_stage004_prohibited_shapes_{MODEL_TAG}.csv"
ALLOWED_PATH = OUTPUT_DIR / f"rebuilt_c9_stage004_allowed_principles_{MODEL_TAG}.csv"
CHART_PATH = OUTPUT_DIR / f"rebuilt_c9_stage004_rejected_return_retention_{MODEL_TAG}.png"
DECISION_PATH = OUTPUT_DIR / f"rebuilt_c9_stage004_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"rebuilt_c9_stage004_report_{MODEL_TAG}.md"


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    data = frame if max_rows is None else frame.head(max_rows)
    if data.empty:
        return "_空_"
    columns = list(data.columns)
    rows = []
    widths = {col: len(str(col)) for col in columns}
    for _, row in data.iterrows():
        item = ["" if pd.isna(row[col]) else str(row[col]) for col in columns]
        rows.append(item)
        for col, value in zip(columns, item):
            widths[col] = max(widths[col], len(value))

    def fmt(values: list[str]) -> str:
        return "| " + " | ".join(value.ljust(widths[col]) for value, col in zip(values, columns)) + " |"

    header = fmt([str(col) for col in columns])
    sep = "| " + " | ".join("-" * widths[col] for col in columns) + " |"
    body = "\n".join(fmt(row) for row in rows)
    suffix = ""
    if max_rows is not None and len(frame) > max_rows:
        suffix = f"\n\n_仅展示前 {max_rows} 行，共 {len(frame)} 行。_"
    return f"{header}\n{sep}\n{body}{suffix}"


def _prohibited_shapes() -> pd.DataFrame:
    rows: list[dict[str, Any]] = [
        {
            "family": "鸡蛋/AI共享池",
            "shape": "full-market AI top9 + jd + maxpos5",
            "source": "memory.md Stage405",
            "evidence": "C=590,220 / 195.1100% / -59.3539% / Sharpe 0.6476; 收益保留仅 4.5756%; broker10 108.0745%",
            "failure_mode": "全市场重排替换正式右尾，jd 自身也为负，组合左尾和保证金压力同时恶化",
            "forbid": "禁止继续扫 topN/maxpos、月份、rank、方向或黑名单救 Stage405",
            "allowed_if_any": "只能作为账户级 selector 重训样本或独立小 sleeve 的观察输入",
            "return_retention_pct": 4.5756,
        },
        {
            "family": "鸡蛋/AI共享池",
            "shape": "原正式 AI 池 + jd 参与 AI rerank top9",
            "source": "memory.md Stage407",
            "evidence": "C=3,284,935 / 1542.4675% / -33.2821% / Sharpe 1.3858; 收益保留 36.1730%; jd 46/51 月入选但自身仅 +21,990",
            "failure_mode": "jd 不一定亏，但重排挤掉 jm/fu/lc/lh/si/oi 等核心右尾",
            "forbid": "禁止把 jd 直接塞回共享 AI 排名主池；禁止 top8/top10/maxpos6 整数救参",
            "allowed_if_any": "非挤占式 sleeve、独立风险预算、账户级 selector",
            "return_retention_pct": 36.1730,
        },
        {
            "family": "鸡蛋/共享路径",
            "shape": "原 AI 池 + 额外追加 jd + maxpos5",
            "source": "memory.md Stage406",
            "evidence": "C=7,674,990 / 3737.4950% / -32.7510% / Sharpe 1.6160; jd 自身 +518,620，但仍低于 A 8,728,285",
            "failure_mode": "jd 有边际机会，但共享路径仍会改变核心右尾排队和复利路径",
            "forbid": "禁止用共享 maxpos 增加来替代正式池；禁止用回撤改善掩盖收益保留不足",
            "allowed_if_any": "独立 sleeve 可以保留为结构方向，但需要证明 jd 材料性",
            "return_retention_pct": 87.9270,
        },
        {
            "family": "鸡蛋/独立槽",
            "shape": "正式核心不动 + jd sleeve20k/50k",
            "source": "memory.md Stage418",
            "evidence": "sleeve20k 仅 +140，sleeve50k -290；核心红框保持正式版，不再挤占右尾",
            "failure_mode": "隔离结构正确，但 jd 当前独立收益没有材料性",
            "forbid": "禁止继续扫 jd sleeve 大小、月份、方向、AI rank 或 topN",
            "allowed_if_any": "先做 forward/paper 或新 selector 证明 jd 质量，再给小独立预算",
            "return_retention_pct": 99.9990,
        },
        {
            "family": "风险释放/延迟恢复",
            "shape": "先开 50%，+0.5R 后恢复",
            "source": "futures_trend_c9_minrisk_highquality Stage002",
            "evidence": "收益保留 66.2493%; DD 只改善 4.3135pp; broker10 111.7365% -> 116.8005%",
            "failure_mode": "代理高估；恢复太晚且恢复后噪声止损，右尾复利底座被削弱",
            "forbid": "禁止扫 50%/0.5R/0.25R/1R、年份、品种、方向救 delayed restore",
            "allowed_if_any": "只保留为已反证形状的教材；后续质量标签不能用单一 progress-first",
            "return_retention_pct": 66.2493,
        },
        {
            "family": "保证金/账户生存",
            "shape": "broker10 >95% 后 largest-margin 减到 80%",
            "source": "futures_trend_c9_minrisk_highquality Stage003",
            "evidence": "收益保留 58.8738%; DD 从 -45.0827% 恶化到 -54.1289%; broker10 变差",
            "failure_mode": "滞后粗砍赢家，削弱 ru/rb/CF/jm/MA 等趋势长仓",
            "forbid": "禁止扫 trigger/target/priority、产品、方向或年份",
            "allowed_if_any": "账户生存只能转非交易层资金分层/出金/保证金预案，不直接砍赢家",
            "return_retention_pct": 58.8738,
        },
        {
            "family": "保证金/风险释放",
            "shape": "仅 broker10 cap 事件内 delayed restore",
            "source": "futures_trend_c9_minrisk_highquality Stage004",
            "evidence": "收益保留 59.8070%; DD 恶化 7.6512pp; broker10 恶化到 117.9016%",
            "failure_mode": "缩窄触发仍破坏右尾；少数大手数恢复后同日止损",
            "forbid": "禁止继续筛 cap 事件、手数阈值、R、年份、品种",
            "allowed_if_any": "cap 只做诊断字段，不做恢复满风险规则",
            "return_retention_pct": 59.8070,
        },
        {
            "family": "分钟负质量",
            "shape": "no-follow 30m 降到 half 或 80%",
            "source": "futures_trend_c9_minrisk_highquality Stage008/Stage019",
            "evidence": "half 收益保留 77.6488%; 80% 收益保留 78.8296%; 均低于 80% 且 broker10/回撤不达标",
            "failure_mode": "no-follow 是有价值负标签，但不是错误充分条件，反例仍有右尾",
            "forbid": "禁止扫 70/75/80/85/90、15/30/60m、品种、方向、年份",
            "allowed_if_any": "保留为 read-only/forward-watch 负质量特征，不能单独交易化",
            "return_retention_pct": 78.8296,
        },
        {
            "family": "分钟退出",
            "shape": "opening range adverse break exit",
            "source": "futures_trend_c9_minrisk_highquality Stage009",
            "evidence": "收益保留 40.2072%; DD 改善 6.8986pp 但 Sharpe 降、3x 成本 DD 恶化",
            "failure_mode": "用砍右尾换平滑；触发集合官方净 PnL 仍为正",
            "forbid": "禁止扫 OR 分钟数、break 倍数、退出比例、品种、方向、年份",
            "allowed_if_any": "只保留为开盘回踩解释标签",
            "return_retention_pct": 40.2072,
        },
        {
            "family": "利润保护/保本",
            "shape": "entry-day confirmed breakeven",
            "source": "futures_trend_c9_minrisk_highquality Stage046",
            "evidence": "收益保留 77.7088%; DD 恶化到 -62.8055%; broker10 恶化到 134.2634%",
            "failure_mode": "确认后回踩常是趋势日内波动，保本退出砍掉右尾",
            "forbid": "禁止扫 confirm R、保本价、同根优先级、品种、方向或年份",
            "allowed_if_any": "利润保护仅保留复盘标签，不做正式候选",
            "return_retention_pct": 77.7088,
        },
        {
            "family": "账户层回撤地板",
            "shape": "DD>=30% -> 0.5x 主动降风险",
            "source": "futures_trend_c9_minrisk_highquality Stage251",
            "evidence": "收益保留 12.6009%; DD 改善 7.7785pp; broker10 改善但复利基本被切断",
            "failure_mode": "地板覆盖恢复段和高权益阶段，错过后续右尾",
            "forbid": "禁止扫 25/30/35、hysteresis、ladder、年份、品种、方向或事件豁免",
            "allowed_if_any": "转部署层资金分层/出金锁盈，不改变生产持仓路径",
            "return_retention_pct": 12.6009,
        },
        {
            "family": "高质量入场标签",
            "shape": "ai_rank_4_6 ∩ entry/first aligned 直接交易化",
            "source": "futures_trend_c9_minrisk_highquality Stage016",
            "evidence": "主交集 24 笔、10 产品、7 年、官方 PnL 10,677,322.5；但补集仍有 375 笔和 27,213,520 大赢家",
            "failure_mode": "标签干净但样本小、收益覆盖不足，不能让补集默认低风险",
            "forbid": "禁止把单桶或交集直接作为开关/满风险唯一条件",
            "allowed_if_any": "可作为高质量加风险候选特征之一，必须与非挤占风险预算和多起点验证结合",
            "return_retention_pct": None,
        },
        {
            "family": "加风险/顺势加仓",
            "shape": "+0.5R progress 同手数加仓或固定1手 sleeve",
            "source": "futures_trend_stage819_intraday_rules Stage882/883",
            "evidence": "同手数加仓收益大但 DD -61.6881%、broker10 203.4450%; 固定1手多 1,046,670 但 broker10 127.4316%、Sharpe 降",
            "failure_mode": "方向证明能增厚右尾，但主账户生存线和 broker10 压力不可接受",
            "forbid": "禁止扫 2手/3手、progress R、止损位置、品种、方向或年份",
            "allowed_if_any": "若加风险，只能是小额独立 sleeve + broker10 生存硬约束 + 多周期验证",
            "return_retention_pct": None,
        },
        {
            "family": "stop/retry 派生微规则",
            "shape": "二次重试、retry cooldown、progress-confirm retry、禁止跨时段重试、EOD exit",
            "source": "futures_trend_stage819_intraday_rules Stage868-880",
            "evidence": "多条路线均误伤 rb/jm/OI/fu/sp 等右尾；progress-confirm 降 DD 但 C9 少 3,969,007 且 broker10 更高",
            "failure_mode": "当前尝试失败不等于后续同品种方向失效；右尾来自少数复杂路径",
            "forbid": "禁止继续扫重试次数、cooldown 天数、session 边界、progress R 或 EOD 平仓",
            "allowed_if_any": "stop/retry 只保留执行法证和监控，不作为 Stage005 优先方向",
            "return_retention_pct": None,
        },
        {
            "family": "数据源/微观结构",
            "shape": "用现有 Tq tick、Stage449 zero-volume/raw bar、外生 cache ready/missing 直接写规则",
            "source": "futures_trend_c9_minrisk_highquality Stage076/080/085-090",
            "evidence": "route scorecard rule_candidate_allowed=0；Stage449 100% zero-volume/OHLC-flat；Tq transform 未同源闭环",
            "failure_mode": "数据缺口和同源性不足，ready/missing 本身承载右尾冲突",
            "forbid": "禁止把 download/exact/mismatch/inside-spread/ready/missing/source_id 写成交易条件",
            "allowed_if_any": "只能先做授权点时化数据工程，再重启只读审计",
            "return_retention_pct": None,
        },
    ]
    return pd.DataFrame(rows)


def _allowed_principles() -> pd.DataFrame:
    rows = [
        {
            "principle": "核心 C9 不挤占",
            "rule": "任何新增品种、鸡蛋、外生信号或加风险，都不得改变原核心右尾品种的主账户排队、连败状态和保证金路径。",
            "evidence": "Stage406/407/418 共同指向：共享池挤占是主要破坏源，隔离能保住核心路径。",
        },
        {
            "principle": "鸡蛋先隔离后评价",
            "rule": "jd.DCE 只能先走独立 sleeve/独立风险槽/forward watch；不能直接进共享 AI rerank。",
            "evidence": "Stage418 证明隔离结构正确但 jd 当前材料性弱；Stage405/407 反证共享 rerank。",
        },
        {
            "principle": "高质量标签必须入场可见",
            "rule": "允许使用 AI rank/score、entry/first aligned、no-follow、OI/价格一致、组合状态、保证金压力等入场时可见字段；禁止最终盈亏/MFE/MAE 反推。",
            "evidence": "Stage015/016 标签有只读价值；Stage082 反证 maxDD/历史亏损 cohort 救参。",
        },
        {
            "principle": "加风险只允许独立小预算",
            "rule": "不能主账户同手数 pyramiding；若要加风险，只能是小额独立 sleeve，有 broker10 生存硬闸和多周期 A/C 验证。",
            "evidence": "Stage882/883 显示 progress add-on 能增厚右尾但 broker10/回撤不可接受。",
        },
        {
            "principle": "先代理、再真引擎、再多起点",
            "rule": "任何候选先做冻结代理；代理通过后才能写真组合引擎；真引擎通过后再复跑 Stage167 口径、年度大于一年口径和 AI 审计。",
            "evidence": "Stage002/013/250 等多次证明代理容易高估真实资金路径价值。",
        },
        {
            "principle": "收益保留不是可谈判项",
            "rule": "默认必须保留当前 Stage167 中位总收益的 80% 以上，且不能只靠牺牲右尾换年度平滑。",
            "evidence": "Stage003 当前保留线为 162.9140%；多个回撤改善候选因收益保留不足被反证。",
        },
        {
            "principle": "完整点时化数据优先",
            "rule": "若使用外生数据，必须有完整历史覆盖、可审计 raw/hash/schema、entry_date 前可得、右尾缺口安全；否则只做数据工程。",
            "evidence": "Stage076/080/085-090 均显示现有本地源还不能直接进规则。",
        },
    ]
    return pd.DataFrame(rows)


def _plot_retention(prohibited: pd.DataFrame) -> None:
    data = prohibited.dropna(subset=["return_retention_pct"]).copy()
    data = data.sort_values("return_retention_pct")
    labels = []
    for index, (_, row) in enumerate(data.iterrows(), start=1):
        source = str(row["source"])
        stages = "/".join(re.findall(r"Stage\d+", source))
        labels.append(f"{index:02d} {stages or 'historical'}")
    colors = ["#b91c1c" if value < 80 else "#92400e" for value in data["return_retention_pct"]]
    fig, ax = plt.subplots(figsize=(14, 8), constrained_layout=True)
    ax.barh(range(len(data)), data["return_retention_pct"], color=colors)
    ax.axvline(80, color="#111827", linewidth=1.5, linestyle="--", label="80% retention")
    ax.set_yticks(range(len(data)))
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_xlabel("return retention %")
    ax.set_title("Rejected Historical Shapes: Return Retention")
    ax.legend(loc="lower right")
    for index, value in enumerate(data["return_retention_pct"]):
        ax.text(value + 1, index, f"{value:.1f}%", va="center", fontsize=8)
    fig.savefig(CHART_PATH, dpi=150)
    plt.close(fig)


def _write_report(prohibited: pd.DataFrame, allowed: pd.DataFrame) -> dict[str, Any]:
    now = datetime.now().strftime("%Y-%m-%d %H:%M CST")
    below80 = prohibited[pd.to_numeric(prohibited["return_retention_pct"], errors="coerce") < 80]
    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "prohibited_shape_count": int(len(prohibited)),
        "allowed_principle_count": int(len(allowed)),
        "return_retention_below_80_count": int(len(below80)),
        "decision": "stage004_counterevidence_map_use_as_stage005_guardrail",
        "next": (
            "Stage005 may only design a frozen proxy that keeps C9 core non-displaced, "
            "treats jd as isolated/non-displacing, and uses entry-visible quality features."
        ),
        "outputs": {
            "prohibited": str(PROHIBITED_PATH),
            "allowed": str(ALLOWED_PATH),
            "chart": str(CHART_PATH),
            "report": str(REPORT_PATH),
        },
    }
    lines = [
        "# Stage004 历史反证清单与下一阶段护栏",
        "",
        f"- line_id：`{LINE_ID}`",
        "- 当前模式：`day`",
        f"- 记录时间：`{now}`",
        "- 阶段性质：历史反证整理，不改策略逻辑，不跑真实组合引擎",
        "- 是否重要突破：否",
        "- 是否触发A/B：否",
        "",
        "## 外部调研与判断",
        "",
        "- Trend following / CTA 风险管理资料支持长期分散化趋势跟随，但也提示右尾复利容易被 drawdown control、止盈、提前降仓破坏。",
        "- Deflated Sharpe / PBO / multiple testing 框架提示：历史上已经跑过大量候选后，继续围绕失败形状扫小参数会显著增加虚假发现概率。",
        "- 本阶段采纳：把历史失败形状固化为约束；否决：继续在 `topN/maxpos/R/分钟窗口/品种/方向/年份` 上救参。",
        "",
        "## 禁止重复尝试清单",
        "",
        _md_table(
            prohibited[
                [
                    "family",
                    "shape",
                    "source",
                    "evidence",
                    "failure_mode",
                    "forbid",
                    "allowed_if_any",
                ]
            ],
            max_rows=None,
        ),
        "",
        "## 下一阶段允许原则",
        "",
        _md_table(allowed, max_rows=None),
        "",
        "## 结论",
        "",
        "- 当前不能直接进入新策略参数扫描。历史已经反复证明：共享 AI 池加鸡蛋、默认最小风险再恢复、no-follow 降仓、OR 退出、保本、DD 地板、同手数加仓都会在收益保留、右尾、broker10 或多起点稳定性上失败。",
        "- 下一步如果做 Stage005，只允许做一个冻结代理：C9 核心不挤占；jd 独立或非挤占；高质量标签必须入场时可见；加风险只能小额独立预算；通过后再写真引擎。",
        "",
        "## 输出文件",
        "",
        f"- prohibited：`{PROHIBITED_PATH}`",
        f"- allowed：`{ALLOWED_PATH}`",
        f"- chart：`{CHART_PATH}`",
        f"- decision：`{DECISION_PATH}`",
        f"- report：`{REPORT_PATH}`",
        "",
        "## 过拟合反思",
        "",
        "- 运行前判断：否。本阶段是把历史失败经验固化成护栏，不产生新候选。",
        "- 运行后判断：否。没有根据失败窗口调参数，也没有选择性只保留好结果。",
        "- 风险提醒：如果下一步绕过这张清单继续扫 `topN/maxpos/R/窗口/品种/方向/年份`，就是明显过拟合。",
        "",
        "## 继续价值反思",
        "",
        "- 运行前判断：是。目标要求高，必须避免重复已反证路线。",
        "- 运行后判断：是。Stage004 已把 Stage005 的可行形状收敛到非挤占鸡蛋和入场可见质量标签。",
        "- 后续规划：Stage005 写冻结代理，不直接改正式策略；代理必须先验证是否跨年份、跨品种、跨起点保留右尾。",
        "",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    DECISION_PATH.write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    return decision


def main() -> None:
    prohibited = _prohibited_shapes()
    allowed = _allowed_principles()
    prohibited.to_csv(PROHIBITED_PATH, index=False)
    allowed.to_csv(ALLOWED_PATH, index=False)
    _plot_retention(prohibited)
    decision = _write_report(prohibited, allowed)
    print(json.dumps(decision, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
