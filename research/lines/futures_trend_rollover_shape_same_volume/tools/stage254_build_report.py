"""从固定Stage254单窗输出生成报告与资金曲线；不导入策略或修改回测结果。"""
import argparse
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    a = ap.parse_args()
    src, out = a.source.resolve(), a.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    read = lambda path: json.loads(path.read_text())
    m = read(src / "metrics.json")
    p = read(src / "run_provenance.json")
    s = read(src / "statistics_audit/summary.json")
    check = read(src / "data_check.json")
    settings = read(src / "actual_strategy_settings.json")[0]["actual"]
    assert m["start"] == "2025-01-01" and m["end"] == "2026-10-14"
    assert m["account_capital"] == 150000
    assert settings["enable_ai_product_pool_filter"] is True
    assert settings["enable_stage847_half_r_stop_retry"] is True
    assert p["official_parameters_match_baseline"]
    assert p["all_data_and_model_inputs_unchanged_during_run"]
    assert p["captured_bar_failure_count"] == 0
    assert p["diagnostic_incomplete_minutes"] and s["diagnostic_incomplete_minutes"]
    d = pd.read_csv(src / "daily.csv")
    y = pd.read_csv(src / "statistics_audit/year_month_results.csv")
    anchors = pd.read_csv(src / "execution_anchor_requests.csv").fillna("")
    bad = anchors[anchors.coverage_status.ne("complete")]
    cycles = s["periods"]["all"]["entry_cohort_complete_cycles"]
    episodes = s["periods"]["all"]["entry_cohort_complete_episodes"]
    assert s["periods"]["all"]["start"] == m["start"]
    assert len(d) == s["daily_rows"] and s["fill_count"] == int(m["total_trade_count"])
    assert abs(float(d.account_equity.iloc[-1]) - m["end_equity"]) < 1e-6
    base = float(m["account_capital"])
    equity = np.r_[base, d.account_equity.to_numpy(float)]
    dates = pd.to_datetime([m["start"], *d.date.astype(str)])
    dd = (equity / np.maximum.accumulate(equity) - 1) * 100
    assert abs(float(dd.min()) - m["max_dd_pct"]) < 1e-8
    curve = pd.DataFrame({"date": dates.strftime("%Y-%m-%d"), "equity": equity, "drawdown_pct": dd})
    curve.to_csv(out / "equity_curve.csv", index=False)
    with plt.rc_context({"font.family": "DejaVu Sans", "font.size": 11}):
        fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True,
                                 gridspec_kw={"height_ratios": [2, 1]}, layout="constrained")
        axes[0].plot(dates, equity, color="#2563eb", lw=1.7)
        axes[0].axhline(base, color="#94a3b8", ls="--", lw=1)
        axes[0].set_ylabel("Account equity (CNY)")
        axes[0].set_title("Official settings | independent CNY 150,000 start | 2025-01-01 to 2026-10-14\n"
                          "Existing-data diagnostic: 2 close-price anchors use daily-open fallback", loc="left")
        axes[1].fill_between(dates, dd, 0, color="#e76f51", alpha=.55)
        axes[1].set_ylabel("Drawdown (%)")
        for ax in axes:
            ax.grid(alpha=.18)
            ax.spines[["top", "right"]].set_visible(False)
        fig.savefig(out / "equity_drawdown.png", dpi=160)
        fig.savefig(out / "equity_drawdown.svg")
        plt.close(fig)
    y.to_csv(out / "year_month_results.csv", index=False, encoding="utf-8-sig")
    bad.to_csv(out / "execution_data_gaps.csv", index=False, encoding="utf-8-sig")
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    summary = {
        "scope": "official_parameters_independent_start_existing_data_diagnostic",
        "start": m["start"], "end": m["end"], "actual_first_trading_date": str(d.date.iloc[0]),
        "material": check["material"], "ruleset": check["ruleset"], "profile": check["profile"],
        "accepted_stage249_correctness_overlay": True, "strategy_parameter_delta": {},
        "capital": base, "metrics": m, "closed_cycle_statistics": cycles,
        "closed_episode_statistics": episodes, "end_open_contracts": s["end_open_contracts"],
        "end_open_mtm": s["end_open_mtm"], "end_open_episode_net_mtm": s["end_open_episode_net_mtm"],
        "daily_rows": len(d), "scan_keys": s["scan_keys"],
        "incomplete_scan_keys": s["incomplete_scan_keys"],
        "ordinary_anchor_requests": len(anchors), "incomplete_ordinary_anchors": len(bad),
        "strict_performance_accepted": False, "market_download_count": 0,
        "new_training_count": 0, "production_access": False,
        "source": str(src), "source_hashes": {n: sha(src / n) for n in [
            "metrics.json", "run_provenance.json", "daily.csv", "trades.csv", "effective_parameters.json",
            "statistics_audit/summary.json", "statistics_audit/complete_cycles.csv",
            "minute_scan_requests.csv", "execution_anchor_requests.csv"]},
        "plot_sha256": sha(out / "equity_drawdown.png"),
    }
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    f = lambda v: f"{float(v):,.2f}"
    lines = ["# 正式版2025年至今回测与逐笔复盘", "",
             "**状态：正式参数的现有数据诊断回测，严格数据验收未通过。** 两次平仓首分钟缺失，采用日线次开盘估算；不得据报告中的数学风控通过字段认定生产可部署。", "",
             f"用户区间2025-01-01至2026-10-14；实际交易日{d.date.iloc[0]}至{d.date.iloc[-1]}，{len(d)}日。初始150,000元，空仓独立起步，沿用正式指标预热，不继承2024资金或仓位。截止日本地完整行情仅到2026-10-14，未下载10月15日数据。", "",
             f"版本：{check['material']} / {check['ruleset']} / C9 15万。月度Top10非fu+固定fu、0.5R止损/一次重试、C2条件1R、pairwise排序及多头倾斜均保持正式配置。使用此前已验收的Stage249权益与分钟执行修复，冻结发布文件未改。未核对远端生产身份，不声称这是实际账户业绩。", "",
             "|指标|结果|", "|---|---:|",
             f"|期末权益|{f(m['end_equity'])}元|",
             f"|净盈亏|{f(m['end_equity']-base)}元|",
             f"|总收益|{m['total_return_pct']:.2f}%|",
             f"|最大回撤|{m['max_dd_pct']:.2f}%|",
             f"|Sharpe|{m['sharpe']:.3f}|",
             f"|总滑点|{f(m['total_slippage'])}元|",
             f"|成交记录（开平分计）|{int(m['total_trade_count'])}|",
             f"|已平仓周期|{cycles['closed_cycles']}|",
             f"|周期胜率|{cycles['wins']}/{cycles['closed_cycles']} = {cycles['win_rate_pct']:.2f}%|",
             f"|合并同日重试后的完整交易段|{episodes['closed_cycles']}|",
             f"|合并重试后的胜率|{episodes['wins']}/{episodes['closed_cycles']} = {episodes['win_rate_pct']:.2f}%|",
             f"|保证金/权益峰值（broker10）|{m['max_broker10_margin_to_equity_pct']:.2f}%|",
             f"|保证金超过权益日数|{int(m['days_over_100pct'])}|", "",
             f"期末未平仓{s['end_open_contracts']}个合约，未平仓周期净盯市{f(s['end_open_mtm'])}元。未平仓不计胜负；完整周期净盈亏加未平仓盯市与账户净盈亏一致。", "",
             "![权益与回撤](equity_drawdown.png)", "",
             "## 年度及月度结果", "",
             "以下按逐日盯市归属，2026继承本次2025年末权益，不是第二次15万元独立起点。", "",
             "|年份|期初权益|期末权益|净盈亏|期间收益|年内回撤|", "|---|---:|---:|---:|---:|---:|"]
    for r in y[y.frequency.eq("year")].itertuples():
        lines.append(f"|{r.period}|{f(r.start_equity)}|{f(r.end_equity)}|{f(r.net_mtm_pnl)}|{r.return_pct:.2f}%|{r.max_dd_pct:.2f}%|")
    lines += ["", "|月份|月末权益|净盈亏|月收益|", "|---|---:|---:|---:|"]
    for r in y[y.frequency.eq("month")].itertuples():
        lines.append(f"|{r.period}|{f(r.end_equity)}|{f(r.net_mtm_pnl)}|{r.return_pct:.2f}%|")
    lines += ["", "## 数据缺口及解释边界", "",
              f"{s['scan_keys']}个去重入场扫描键全部完整；{len(anchors)}个普通成交首锚请求中{len(bad)}个缺失，均为平仓。原严格运行保留于run/run_failure.json，诊断运行另存run_diagnostic，没有覆盖失败证据。", "",
              "|交易日|合约|应有首分钟|诊断估算平仓价|", "|---|---|---|---:|"]
    for r in bad.itertuples():
        lines.append(f"|{r.trading_date}|{r.vt_symbol}|{r.expected_start}|{r.price:g}|")
    lines += ["", "两处缺口可能影响本笔盈亏及后续定仓；未取得确切分钟，不能量化误差，也不能把本结果升级为严格验收。用户要求不再下载分钟，本轮不补数。其余会计与源文件一致性另经独立review，不以算术正确替代成交数据完整。", "",
              "成本沿用正式零手续费与固定滑点；历史外部供需信号实际0行、no_signal权重1，与既有基准一致。月池历史规则存在既有后验选择风险、旧训练源尚未随修复重建；本轮不重训，也不把已看过的区间称为严格样本外。", "",
              "2025年重新起步的收益不能与2020年起累计收益直接比较：起点资金、历史持仓、已积累风险状态和整数手约束不同。本次重新运行引擎，未截取或缩放旧资金曲线。参考[VeighNa组合回测源码](https://github.com/vnpy/vnpy_portfoliostrategy/blob/main/vnpy_portfoliostrategy/backtesting.py)，调研判断是独立起点需要独立账户路径，而非静态截段。", "",
              "## 交付及核验", "",
              "- [逐笔复盘HTML](recap/index.html)：全部已平仓周期（包括初次和重试），同信号root关联；残余仓位单列。", 
              "- [原始成交](run_diagnostic/trades.csv)、[完整周期账本](run_diagnostic/statistics_audit/complete_cycles.csv)、[合并重试交易段](run_diagnostic/statistics_audit/complete_episodes.csv)。",
              "- [逐日权益](equity_curve.csv)、[年月统计](year_month_results.csv)、[两处执行缺口](execution_data_gaps.csv)。",
              "- [运行来源及参数证据](run_diagnostic/run_provenance.json)、[独立审查](independent_review.md)。", "",
              "复盘沿用canonical图表，具体合约成交标记与背景主力代理区分，不提供缺失的15分钟图。页面检查结果及浏览器不可用限制见复盘审计摘要。", "",
              "运行后反思：本轮没有新增过拟合——固定参数、固定用户指定起点，无寻优；区间观察有价值，但不能证明泛化或正式晋升。新执行为1次严格失败与1次现有数据诊断完成，下载0、重训0、生产访问0、策略参数修改0。遵照用户要求，不继续反复补数或修小问题。"]
    (out / "report.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({"report": str(out / "report.md"), "summary": str(out / "summary.json"),
                      "end_equity": m["end_equity"], "diagnostic": True}, ensure_ascii=False))


if __name__ == "__main__":
    main()
