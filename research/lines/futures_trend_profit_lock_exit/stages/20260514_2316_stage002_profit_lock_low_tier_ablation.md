# 2026-05-14 23:16 Stage002 / Stage272 去掉低档位盈利锁 A/C 最小验证

## 基本信息

- 工作模式：day
- 所属研究线：`futures_trend_profit_lock_exit`
- 策略基准：Stage78-1 `official_stage78_1_defensive_50w_no_sizing_cap`
- 资金口径：50万
- 是否重要突破：否
- 结论：`C_no_2_3pct_early_lock` 未通过最小晋级门，不进入 Stage273；正式 78-1 锁盈档位保持不变。

## 外部调研与判断

- 调研方向：trailing stop 优化、walk-forward optimization、purged cross-validation、交易策略超参数过拟合控制、GitHub 上常见 walk-forward 研究框架。
- 参考链接：[GitHub walk-forward-optimization topics](https://github.com/topics/walk-forward-optimization)、[walk-forward analysis glossary](https://tradingstrategy.ai/glossary/walk-forward-analysis)、[purged cross-validation](https://en.wikipedia.org/wiki/Purged_cross-validation)。
- 判断结论：锁盈/移动止损属于高自由度退出模块，不能直接按全样本收益调阈值；更合理的方法是先做交易级归因，再只验证低自由度结构候选，并用起始年份、弱窗口和近端窗口拦截过拟合。

## 本阶段改动

- 新增脚本：`examples/portfolio_backtesting/run_qmt_roll_stage272_profit_lock_low_tier_ablation.py`
- 修改脚本：`examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
- 新增实验参数：`profit_lock_tiers`
  - 默认值：空字符串
  - 默认行为：完全沿用正式档位 `30->20,20->15,10->8,5->3,3->1,2->0.1`
  - 用途：仅用于隔离式 A/B/C 实验，不改变正式 78-1 配置。
- 修改参数：无正式参数修改。
- 删除参数：无。
- 修改正式 Stage78-1 配置：无。

## A/C 设计

- A：当前 Stage78-1 正式盈利锁定档位。
- C：保留 `5/10/20/30%` 档位，去掉 `2%->0.1%` 与 `3%->1%` 早锁档位。
- 本阶段不是参数搜索，只验证 Stage271 暴露的低档位早锁疑点。

## 新增回测结果

| 窗口 | A期末权益 | C期末权益 | C-A | A最大回撤 | C最大回撤 | A Sharpe | C Sharpe |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| full_2020_2026 | 26,353,935 | 26,083,610 | -270,325 | -40.17% | -40.02% | 1.1374 | 1.1347 |
| since_2021 | 20,123,025 | 20,122,390 | -635 | -45.00% | -43.92% | 1.0725 | 1.0788 |
| since_2022 | 8,980,305 | 8,282,030 | -698,275 | -43.03% | -43.57% | 1.0476 | 1.0087 |
| since_2023 | 5,875,385 | 5,395,180 | -480,205 | -39.30% | -39.16% | 1.2418 | 1.1886 |
| since_2024 | 3,046,815 | 2,986,750 | -60,065 | -40.24% | -40.26% | 1.1745 | 1.1635 |
| since_2025 | 2,548,825 | 2,519,525 | -29,300 | -28.88% | -29.11% | 1.6598 | 1.6397 |
| since_2026 | 569,180 | 569,180 | 0 | -40.76% | -40.76% | 0.3323 | 0.3323 |
| stage269_aug_nov_2025 | 879,710 | 871,010 | -8,700 | -27.97% | -27.67% | 1.5092 | 1.5004 |
| stage131_q2022_4_proxy_252d | 665,020 | 665,020 | 0 | -11.03% | -11.03% | 1.4119 | 1.4119 |

全周期 C 版本统计：

- 期末权益：`26,083,610`
- 总收益：`5116.72%`
- 最大回撤：`-40.02%`
- Sharpe：`1.1347`
- 总滑点：`2,077,620`
- 总交易次数：`885`
- 胜率：`43.49%`

对照 A 正式基准全周期统计：

- 期末权益：`26,353,935`
- 总收益：`5170.79%`
- 最大回撤：`-40.17%`
- Sharpe：`1.1374`
- 总滑点：`2,057,380`
- 总交易次数：`883`
- 胜率：`43.36%`

## 晋级判定

```json
{
  "promotion_decision": "fail_or_hold_no_promotion",
  "pass_minimal_gate": false,
  "full_return_ok": true,
  "full_dd_ok": true,
  "latest_2026_ok": true,
  "weak_ok_count": 2,
  "start_year_win_count": 0,
  "next_step": "stop_no_low_tier_candidate_or_keep_as_attribution_only"
}
```

关键原因：

- C 的全周期回撤略好，但权益和 Sharpe 略弱。
- C 在所有 `since_` 起始年份窗口都没有赢过 A，`start_year_win_count=0`。
- 低档位早锁确实可疑，但“直接去掉 2%/3% 早锁”没有形成跨窗口优势。

## 过拟合反思

- 运行前判断：不是过拟合。
- 原因：本阶段只有一个由 Stage271 归因提出的结构候选，不是逐档网格搜索。
- 运行后判断：若继续围绕 `2%/3%` 的小数阈值微调，就是过拟合。
- 原因：C 没有通过起始年份一致性检验；继续调成 `2.5%/0.5%`、`4%/1.5%` 之类，会变成按历史窗口找舒适点。

## 继续价值反思

- 运行前判断：有价值。
- 原因：可以验证手工锁盈分层里最可疑的低档位是否值得进入正式候选。
- 运行后判断：这条低档位删除候选不值得继续；盈利锁定研究线仍有价值，但下一步应换成机制级归因或更少自由度的退出结构，而不是继续微调低档位。
- 原因：失败提供了清晰边界：当前 78-1 手工档位不能被简单删除法击败。

## 输出文件

- 报告：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage272_profit_lock_low_tier_ablation_report_stage272_profit_lock_low_tier_ablation_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage272_profit_lock_low_tier_ablation_summary_stage272_profit_lock_low_tier_ablation_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage272_profit_lock_low_tier_ablation_comparison_stage272_profit_lock_low_tier_ablation_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage272_profit_lock_low_tier_ablation_decision_stage272_profit_lock_low_tier_ablation_v1.json`
