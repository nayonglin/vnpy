"""Render exact linear contributions from the verified reproduction artifacts."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
import numpy as np
import pandas as pd


OUT = Path(__file__).resolve().parents[1] / "artifacts/stage001_20260731"
PROB = "predicted_product_suitability_probability"
NAMES = {
    "jm.DCE": "焦煤", "si.GFEX": "工业硅", "SA.CZCE": "纯碱", "au.SHFE": "黄金",
    "lc.GFEX": "碳酸锂", "cu.SHFE": "铜", "SM.CZCE": "锰硅", "lh.DCE": "生猪",
    "MA.CZCE": "甲醇", "OI.CZCE": "菜油", "FG.CZCE": "玻璃", "AP.CZCE": "苹果",
    "CF.CZCE": "棉花", "ru.SHFE": "天然橡胶", "sp.SHFE": "纸浆", "SH.CZCE": "烧碱",
    "rb.SHFE": "螺纹钢", "hc.SHFE": "热卷", "fu.SHFE": "燃油",
}
GROUPS = ["收益水平", "波动与盈利日", "回撤与尾部", "信号与趋势", "交易与规模", "滑点金额", "组合与候选"]
BASES = {
    "net_pnl_sum": ("累计策略净利润", 0), "net_pnl_mean": ("日均策略净利润", 0),
    "net_pnl_std": ("盈亏波动标准差", 1), "net_pnl_sharpe_like": ("策略类Sharpe指标", 1),
    "pnl_positive_day_mean": ("盈利日比例", 1),
    "net_pnl_drawdown": ("策略盈亏曲线回撤金额", 2), "net_pnl_min_day": ("最低单日策略净利润", 2),
    "net_pnl_max_day": ("最高单日策略净利润", 2), "avg_loss_streak_mean": ("连亏状态均值", 2),
    "candidate_count_sum": ("候选信号数量", 3), "candidate_day_mean": ("候选信号日比例", 3),
    "opened_count_sum": ("开仓候选数量", 3), "opened_day_mean": ("开仓候选日比例", 3),
    "breakout_rate_mean": ("突破信号比例", 3), "bullish_alignment_rate_mean": ("多头排列比例", 3),
    "bearish_alignment_rate_mean": ("空头排列比例", 3), "avg_rsi_mean": ("候选RSI均值", 3),
    "abs_pos_change_sum": ("仓位变化绝对量累计", 4), "active_contract_count_sum": ("持仓合约日累计", 4),
    "selected_volume_sum_sum": ("筛选后候选手数累计", 4), "selected_volume_ungated_sum_sum": ("过滤前候选手数累计", 4),
    "turnover_sum": ("策略成交额", 4), "trade_count_sum": ("策略交易次数", 4),
    "trade_day_mean": ("策略交易日比例", 4), "slippage_sum": ("策略滑点金额", 5),
    "avg_active_positions_before_mean": ("候选出现前组合持仓数均值", 6),
    "avg_corr_gate_weight_mean": ("相关性过滤权重均值", 6),
    "avg_same_direction_active_count_mean": ("同方向持仓数均值", 6),
    "avg_same_direction_max_corr_mean": ("同方向最大相关性均值", 6),
    "avg_pairwise_score_mean": ("候选比较分均值", 6), "best_pairwise_rank_mean": ("日内最佳候选名次均值", 6),
    "avg_volume_tilt_multiplier_mean": ("仓位倾斜倍率均值", 6),
    "avg_volume_tilt_score_gap_mean": ("候选组最高最低分差均值", 6),
    "avg_volume_tilt_top_gap_mean": ("候选组首二名分差均值", 6),
    "corr_gate_enabled_count_sum": ("相关性过滤启用次数", 6),
    "volume_tilt_applied_count_sum": ("仓位倾斜应用次数", 6),
}


def label(feature: str) -> str:
    base, window = feature.rsplit("_", 1)
    return window[:-1] + "日" + BASES[base][0]


def group(feature: str) -> str:
    return GROUPS[BASES[feature.rsplit("_", 1)[0]][1]]


def table(rows: list[list], headings: list[str]) -> str:
    return "\n".join(["| " + " | ".join(headings) + " |", "| " + " | ".join(["---"] * len(headings)) + " |"] + ["| " + " | ".join(map(str, row)) + " |" for row in rows])


def compact_terms(frame: pd.DataFrame, n: int, positive: bool) -> str:
    values = frame[frame.contribution_log_odds.gt(0) if positive else frame.contribution_log_odds.lt(0)]
    values = values.nlargest(n, "contribution_log_odds") if positive else values.nsmallest(n, "contribution_log_odds")
    return "；".join(f"{label(r.feature)} {r.contribution_log_odds:+.3f}" for r in values.itertuples())


def charts(scores: pd.DataFrame, grouped: pd.DataFrame, detail: pd.DataFrame) -> None:
    plt.rcParams.update({"font.family": "Arial Unicode MS", "font.size": 12, "axes.unicode_minus": False})
    ordered = scores.sort_values("model_rank")
    matrix = grouped.pivot(index="product_vt_symbol", columns="factor_group", values="contribution_log_odds").reindex(index=ordered.product_vt_symbol, columns=GROUPS)
    cmap = LinearSegmentedColormap.from_list("signed", ["#b84f60", "#fafbfa", "#187e75"])
    limit = float(np.abs(matrix.to_numpy()).max())
    fig, (ax, bar) = plt.subplots(1, 2, figsize=(15.8, 10.4), gridspec_kw={"width_ratios": [3.9, 1.25]})
    fig.subplots_adjust(left=0.12, right=0.965, bottom=0.14, top=0.84, wspace=0.14)
    im = ax.imshow(matrix, cmap=cmap, norm=TwoSlopeNorm(vmin=-limit, vcenter=0, vmax=limit), aspect="auto")
    ax.set_xticks(range(len(GROUPS)), ["收益\n水平", "波动与\n盈利日", "回撤与\n尾部", "信号与\n趋势", "交易与\n规模", "滑点\n金额", "组合与\n候选"])
    ax.set_yticks(range(len(ordered)), [f"{r.model_rank:02d}  {NAMES[r.product_vt_symbol]}" for r in ordered.itertuples()])
    ax.tick_params(length=0, pad=8)
    ax.set_title("108 项特征按类别汇总：相对训练均值的加减分", fontsize=13, pad=16)
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            value = float(matrix.iloc[i, j])
            ax.text(j, i, f"{value:+.2f}", ha="center", va="center", fontsize=11, color="white" if abs(value) > limit * 0.58 else "#202828")
    ax.axhline(9.5, color="#182b28", linewidth=2.4)
    for spine in ax.spines.values():
        spine.set_visible(False)
    y = np.arange(len(ordered))
    colors = ["#187e75" if rank <= 10 else "#899694" for rank in ordered.model_rank]
    bar.barh(y, ordered[PROB] * 100, color=colors, height=0.66)
    bar.set_ylim(len(ordered) - 0.5, -0.5)
    bar.set_xlim(0, 83)
    bar.set_yticks([])
    bar.set_xticks([0, 25, 50, 75], ["0", "25", "50", "75"])
    bar.set_title("当期模型分数 / %", fontsize=13, pad=16)
    bar.axhline(9.5, color="#182b28", linewidth=2.4)
    for i, value in enumerate(ordered[PROB] * 100):
        bar.text(value + 1.3, i, f"{value:.2f}", va="center", fontsize=10)
    for side in ("top", "right", "left"):
        bar.spines[side].set_visible(False)
    fig.text(0.12, 0.95, "正式 AI 选品：当期分数贡献", fontsize=23, weight="bold", color="#16352e")
    fig.text(0.12, 0.905, "评估日 2026-07-31  |  18 个模型评分品种  |  原分数复现误差 0  |  分界线以上为正式 Top10", fontsize=12, color="#54625e")
    fig.text(0.12, 0.06, "格内单位为 log-odds，不是概率百分点。截距 +0.211396 加上各类别贡献，再经 sigmoid 得到右侧分数。", fontsize=11)
    fig.text(0.12, 0.025, "燃油固定入池，不参与这 18 个品种的模型评分。正贡献仅指模型加分，不代表经济因果或鼓励增加成本、亏损。", fontsize=11, color="#54625e")
    fig.savefig(OUT / "contribution_overview.png", dpi=160)
    plt.close(fig)

    fig, axes = plt.subplots(2, 2, figsize=(17, 11))
    fig.subplots_adjust(left=0.26, right=0.97, bottom=0.08, top=0.86, wspace=1.45, hspace=0.44)
    for ax, symbol in zip(axes.flat, ["jm.DCE", "lc.GFEX", "au.SHFE", "OI.CZCE"]):
        item = detail[detail.product_vt_symbol.eq(symbol)].copy()
        top = pd.concat([item.nlargest(3, "contribution_log_odds"), item.nsmallest(3, "contribution_log_odds")])
        remaining = item[~item.feature.isin(top.feature)]
        labels = [label(f) for f in top.feature] + ["其余正贡献合计", "其余负贡献合计"]
        values = top.contribution_log_odds.tolist() + [remaining.contribution_log_odds.clip(lower=0).sum(), remaining.contribution_log_odds.clip(upper=0).sum()]
        row = scores[scores.product_vt_symbol.eq(symbol)].iloc[0]
        assert abs(sum(values) - row.contribution_sum_log_odds) <= 1e-12
        limit = max(max(values), -min(values)) * 1.32
        y = np.arange(len(values))
        ax.barh(y, values, color=["#187e75" if v >= 0 else "#b84f60" for v in values], height=0.66)
        ax.set_yticks(y, labels, fontsize=10)
        ax.invert_yaxis()
        ax.set_xlim(-limit, limit)
        ax.axvline(0, color="#788784", linewidth=0.8)
        for i, value in enumerate(values):
            ax.text(value + (limit * 0.03 if value >= 0 else -limit * 0.03), i, f"{value:+.3f}", va="center", ha="left" if value >= 0 else "right", fontsize=10)
        ax.set_title(f"{NAMES[symbol]}  #{int(row.model_rank)}  分数 {row[PROB]:.4f}\n108项净贡献 {row.contribution_sum_log_odds:+.4f}", fontsize=13, pad=10)
        ax.tick_params(axis="y", length=0)
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
    fig.text(0.08, 0.95, "加分与减分必须一起看", fontsize=23, weight="bold", color="#16352e")
    fig.text(0.08, 0.905, "每图显示最大三项加分、最大三项减分及剩余项合计；完整覆盖 108 项。单位：log-odds。", fontsize=12)
    fig.text(0.08, 0.027, "单项贡献相对训练样本均值。不同窗口、相关特征可互相抵消；这些是模型计算事实，不是可直接交易的因果规律。", fontsize=11, color="#54625e")
    fig.savefig(OUT / "selected_product_contributions.png", dpi=160)
    plt.close(fig)


def main() -> None:
    summary = json.loads((OUT / "reproduction_summary.json").read_text())
    model = json.loads((OUT / "model_snapshot.json").read_text())
    assert summary["decision"] == "exact_current_score_reproduction_pass"
    scores = pd.read_csv(OUT / "product_scores_and_features.csv", float_precision="round_trip").sort_values("model_rank")
    detail = pd.read_csv(OUT / "feature_contributions.csv", float_precision="round_trip")
    detail["品种"] = detail.product_vt_symbol.map(NAMES)
    detail["特征解释"] = detail.feature.map(label)
    detail["factor_group"] = detail.feature.map(group)
    detail["相对训练均值"] = np.where(detail.standardized_value.gt(1e-12), "高于", np.where(detail.standardized_value.lt(-1e-12), "低于", "相等"))
    detail.to_csv(OUT / "feature_contributions_zh.csv", index=False, encoding="utf-8-sig")
    grouped = detail.groupby(["product_vt_symbol", "model_rank", "factor_group"], as_index=False).contribution_log_odds.sum()
    group_sum = grouped.groupby("product_vt_symbol").contribution_log_odds.sum()
    assert np.max(np.abs(group_sum - scores.set_index("product_vt_symbol").contribution_sum_log_odds)) <= 1e-12
    grouped.to_csv(OUT / "factor_group_contributions.csv", index=False, encoding="utf-8-sig")
    coefficient = pd.read_csv(OUT / "model_coefficients.csv", float_precision="round_trip")
    coefficient["特征解释"] = coefficient.feature.map(label)
    coefficient["factor_group"] = coefficient.feature.map(group)
    coefficient.to_csv(OUT / "model_coefficients_zh.csv", index=False, encoding="utf-8-sig")
    matrix = detail.pivot(index="product_vt_symbol", columns="feature", values="contribution_log_odds")
    pair_records = []
    for i in range(len(scores) - 1):
        high, low = scores.iloc[i], scores.iloc[i + 1]
        difference = matrix.loc[high.product_vt_symbol] - matrix.loc[low.product_vt_symbol]
        assert abs(difference.sum() - (high.decision_log_odds - low.decision_log_odds)) <= 1e-12
        for feature, value in difference.items():
            pair_records.append({"higher_product": high.product_vt_symbol, "lower_product": low.product_vt_symbol,
                                 "higher_rank": int(high.model_rank), "lower_rank": int(low.model_rank),
                                 "feature": feature, "特征解释": label(feature), "contribution_difference_log_odds": value})
    pairs = pd.DataFrame(pair_records)
    pairs.to_csv(OUT / "adjacent_rank_contributions.csv", index=False, encoding="utf-8-sig")
    charts(scores, grouped, detail)

    lines = ["# 正式 AI 选品：2026-07-31 当期分数逐项解释", "",
             "## 核对结论", "",
             "原始 18 个品种及正式 Top10 的概率复现误差均为 **0**，18 个模型排名与 Top10 入选顺序完全一致。正式物料为 `m0004_20260831T112631+0800_2485073e9594`，训练输入两份 SHA256 与 2026-08-03 原始记录完全一致。",
             "", "当期模型实际为 **108 个特征**，纠正前次机制说明中的 111 个。训练样本 1,368 行、76 个月；训练评估月末范围 " + summary["training_start"] + " 至 " + summary["training_end"] + "，60交易日标签截止门为 2026-05-07，数据源终点为 2026-08-03。此次仅按原参数重建模型做解释，没有策略回测、模型调参、生产文件写入或订单 API。",
             "", "## 如何读贡献", "",
             "`单项贡献 = 系数 × (当期特征值 - 训练均值) / 训练标准差`。标准化均值为原 StandardScaler 使用的非加权训练均值；分类器仍使用原样本权重。",
             "", f"`logit = {model['intercept']:.12f} + 108项贡献之和`；`概率 = 1 / (1 + exp(-logit))`。训练均值对应基准概率 {model['baseline_probability_at_training_mean']:.6%}。",
             "", "贡献单位是 **log-odds**，不是概率百分点。正值为模型加分，负值为模型减分；逐项相加是精确的，但不能把每一项解释成经济因果。基准不是当月横截面均值，排名差异请看后面的两品种差值。",
             "", "![当期贡献概览](contribution_overview.png)", "", "## 当前全排名", ""]
    overview = []
    for row in scores.itertuples(index=False):
        symbol = row.product_vt_symbol
        item = detail[detail.product_vt_symbol.eq(symbol)]
        overview.append([row.model_rank, NAMES[symbol] + " " + symbol, f"{getattr(row, PROB):.6f}", "Top10入池" if row.model_rank <= 10 else "未入池", compact_terms(item, 2, True), compact_terms(item, 2, False)])
    lines.append(table(overview, ["模型排名", "品种", "分数", "正式资格", "最大两项加分", "最大两项减分"]))
    lines += ["", "燃油 `fu.SHFE` 固定进入正式池第11位，不在这次18个模型评分品种中。其发布分数是第10名分数减 `0.000001`，不是真实模型预测，不能做模型贡献拆解。玻璃的模型第11名与燃油的正式席位第11位是两种不同编号。",
              "", "## 关键发现与解释边界", "",
              "1. 焦煤和工业硅的主要加分项包含近期策略滑点金额。焦煤20日滑点为4,200，训练均值252.124，标准化值6.277，系数+0.168992，单项贡献+1.060794；工业硅同项+0.483089。这里是回放的滑点总金额，可能同时代理交易规模、频率及波动机会，不能解释成增加真实交易成本会改善策略。",
              "2. 碳酸锂有明显的正负抵消：120日最低单日净利润-200,520贡献+0.766657，60日回撤金额-225,270贡献+0.518886，20日回撤贡献+0.480349；20日和120日盈亏波动分别贡献-0.670828、-0.640915。深亏加分只是当前拟合系数的计算结果，不能当成逆势加仓规则。",
              "3. 黄金近120日基础策略持仓合约日累计为0，这项贡献+0.204490；60日交易日比例0贡献+0.146687，120日开仓候选数量0贡献+0.141981。其排名高不等于这段时间策略已在黄金上赚很多钱；无持仓或无信号的零值特征也可能被模型加分。",
              "4. 菜油和玻璃靠近入池边界。不是菜油所有指标都更好，而是正负差项抵消后微幅领先。详情见下一节。",
              "5. 同一指标不同窗口可有相反系数，例如20/60日回撤系数为负而120日为正；仓位倾斜次数60日为正、120日为负。相关或重复特征的单项系数不能脱离其他项解读。",
              "6. 候选统计是基础策略在有信号日记录并按交易日补齐的数据；无信号日多数填0，相关性过滤权重、仓位倾斜倍率使用中性1。候选组首二名分差是当时同方向候选组前两名的分差，并非该品种独有优势。",
              "", "![重点品种加减分](selected_product_contributions.png)", "", "## 排名差异：菜油为什么略高于玻璃", ""]
    high = scores[scores.product_vt_symbol.eq("OI.CZCE")].iloc[0]
    low = scores[scores.product_vt_symbol.eq("FG.CZCE")].iloc[0]
    boundary = pairs[pairs.higher_product.eq("OI.CZCE")]
    lines += [f"菜油 {high[PROB]:.6f}，玻璃 {low[PROB]:.6f}，相差 **{(high[PROB] - low[PROB])*100:.4f} 个概率百分点**；108项差值合计 **{high.decision_log_odds - low.decision_log_odds:+.6f} log-odds**。", ""]
    best = pd.concat([boundary.nlargest(5, "contribution_difference_log_odds"), boundary.nsmallest(5, "contribution_difference_log_odds")])
    difference_rows = [[label(r.feature), f"{r.contribution_difference_log_odds:+.6f}", "菜油相对占优" if r.contribution_difference_log_odds > 0 else "玻璃相对占优"] for r in best.itertuples()]
    other = boundary[~boundary.feature.isin(best.feature)].contribution_difference_log_odds.sum()
    difference_rows.append(["其余98项合计", f"{other:+.6f}", "未省略净贡献"])
    lines.append(table(difference_rows, ["因素", "菜油减玻璃的贡献差", "模型方向"]))
    lines += ["", "这说明边界名次由多个大幅相反贡献抵消后形成；此处没有做扰动实验，不据此声称排名不稳定或具有统计显著性。", "", "## 各品种逐项解释", ""]
    for row in scores.itertuples(index=False):
        symbol = row.product_vt_symbol
        item = detail[detail.product_vt_symbol.eq(symbol)]
        top = pd.concat([item.nlargest(5, "contribution_log_odds"), item.nsmallest(5, "contribution_log_odds")])
        other = item[~item.feature.isin(top.feature)]
        lines += [f"### {row.model_rank}. {NAMES[symbol]} {symbol}", "",
                  f"分数 `{getattr(row, PROB):.9f}`；正贡献总和 `{row.positive_contribution_sum:+.6f}`，负贡献总和 `{row.negative_contribution_sum:+.6f}`，净贡献 `{row.contribution_sum_log_odds:+.6f}`。", ""]
        rows = [[label(r.feature), f"{r.raw_value:.6g}", f"{r.training_mean:.6g}", f"{r.standardized_value:+.4f}", f"{r.coefficient:+.6f}", f"{r.contribution_log_odds:+.6f}"] for r in top.itertuples()]
        rows += [["其余正贡献合计", "", "", "", "", f"{other.contribution_log_odds.clip(lower=0).sum():+.6f}"],
                 ["其余负贡献合计", "", "", "", "", f"{other.contribution_log_odds.clip(upper=0).sum():+.6f}"]]
        lines += [table(rows, ["因素", "原值", "训练均值", "标准化值", "系数", "贡献log-odds"]), ""]
    lines += ["## 校验与完整数据", "",
              "- 原18品种概率最大误差：0；正式Top10概率最大误差：0；保存特征值最大误差：0。",
              "- 截距加贡献还原模型决策值最大误差：4.440892098500626e-16；还原概率最大误差：1.1102230246251565e-16。",
              "- 完整明细：18品种×108特征=1,944行；相邻名次差异：17组×108特征=1,836行。",
              "- [中文逐项贡献CSV](feature_contributions_zh.csv)、[108项模型系数](model_coefficients_zh.csv)、[相邻排名差异](adjacent_rank_contributions.csv)。",
              "- [复现与来源证据](reproduction_summary.json)、[模型快照](model_snapshot.json)、[分数逐项核对](score_parity.csv)、[训练样本](training_samples.csv)。",
              "", "## 外部调研与判断", "",
              "参考 [SHAP线性解释器](https://shap.readthedocs.io/en/latest/generated/shap.LinearExplainer.html) 和 [scikit-learn GitHub实现](https://github.com/scikit-learn/scikit-learn/blob/main/sklearn/linear_model/_logistic.py)。线性模型可在log-odds空间按系数与中心化特征精确拆解。本次直接使用原StandardScaler和分类器的系数，不引入近似解释器、不做条件SHAP估计；在高度相关输入下，这种归因说明计算构成，不解决经济因果。",
              "", "## 研究判断", "",
              "是否新增过拟合：否。原输入哈希、原参数、原评估日全部冻结，分数逐项完全复现，没有调参、策略回测或按解释结果改规则。",
              "", "是否值得继续：是，但价值在持续可解释性与输入语义审计，而非直接把正贡献因子改成选品规则。已完成本期分数解释；若后续要检验滑点、规模或零值特征是否形成不稳健代理，需要另行预注册独立验证，不能从本次归因直接推导策略优化。"]
    (OUT / "report.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({"report": str(OUT / "report.md"), "feature_rows": len(detail), "adjacent_rows": len(pairs), "group_rows": len(grouped)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
