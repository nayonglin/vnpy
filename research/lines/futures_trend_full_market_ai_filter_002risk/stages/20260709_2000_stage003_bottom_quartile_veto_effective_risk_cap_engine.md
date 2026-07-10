# Stage003 全市场 AI 底部四分位 veto + 有效风险 0.02 真实引擎

- line_id：`futures_trend_full_market_ai_filter_002risk`
- 当前模式：`day`
- 记录时间：`2026-07-09 19:36 CST`
- 阶段性质：独立研究线最小 A/C 真实引擎回测
- 是否重要突破：否，Stage002 独立 review 后的有效风险语义验证
- 是否触发A/B：是，A=官方 C9/15w；C=Stage002 active full-market bottom25 veto + risk_ratio_* 0.02 + OI restore disabled

## 本次变更

- 新增脚本：`research/lines/futures_trend_full_market_ai_filter_002risk/tools/stage003_bottom_quartile_veto_effective_risk_cap_engine.py`
- 新增参数：`enable_oi_price_confirm_risk_restore=False`、`oi_price_confirm_risk_restore_multiplier=1.0`
- 修改参数：继承 Stage002 active full-market bottom25 veto 与 `risk_ratio_* = 0.02`，但关闭 OI confirm 风险恢复，避免有效风险被放大到 `0.04`。
- 删除参数：删除 OI confirm restore 对本候选的加风险效果。

## 回测参数

- 数据区间：`2020-01-01` 到 `2026-06-30`
- 账户规模：`150,000`
- 成本口径：沿用 C9 真实引擎原成本/slippage 配置。

## 结果

- A 期末权益：`5,979,281.00`；总收益 `3886.1873%`；最大回撤 `-55.3701%`；Sharpe `1.3959`
- C 期末权益：`525,988.00`
- C 总收益：`250.6587%`
- C 最大回撤：`-81.9919%`
- C Sharpe：`0.6378`
- C 总滑点：`215,020.00`
- C 总交易次数：`1,503`
- C 胜率：`51.0609%`，口径为非零交易日胜率，不是逐笔胜率。
- C 最大 broker10 保证金/权益：`234.1020%`
- C 相对 A 收益差：`-3635.5287` 百分点；回撤差：`-26.6217` 百分点。

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_full_market_ai_filter_002risk/outputs/stage003_bottom_quartile_veto_effective_risk_cap_engine/full_market_ai002_stage003_bottom_quartile_veto_effective_risk_cap_engine_report_stage003_bottom_quartile_veto_effective_risk_cap_engine_v1.md`
- summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_full_market_ai_filter_002risk/outputs/stage003_bottom_quartile_veto_effective_risk_cap_engine/full_market_ai002_stage003_bottom_quartile_veto_effective_risk_cap_engine_ac_summary_stage003_bottom_quartile_veto_effective_risk_cap_engine_v1.csv`
- eligibility：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_full_market_ai_filter_002risk/outputs/stage003_bottom_quartile_veto_effective_risk_cap_engine/full_market_ai002_stage003_bottom_quartile_veto_effective_risk_cap_engine_eligibility_stage003_bottom_quartile_veto_effective_risk_cap_engine_v1.csv`
- feature_panel：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_full_market_ai_filter_002risk/outputs/stage003_bottom_quartile_veto_effective_risk_cap_engine/full_market_ai002_stage003_bottom_quartile_veto_effective_risk_cap_engine_feature_panel_stage003_bottom_quartile_veto_effective_risk_cap_engine_v1.csv.gz`
- daily：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_full_market_ai_filter_002risk/outputs/stage003_bottom_quartile_veto_effective_risk_cap_engine/full_market_ai002_stage003_bottom_quartile_veto_effective_risk_cap_engine_candidate_daily_stage003_bottom_quartile_veto_effective_risk_cap_engine_v1.csv.gz`
- risk_restore_audit：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_full_market_ai_filter_002risk/outputs/stage003_bottom_quartile_veto_effective_risk_cap_engine/full_market_ai002_stage003_bottom_quartile_veto_effective_risk_cap_engine_risk_restore_audit_stage003_bottom_quartile_veto_effective_risk_cap_engine_v1.csv`

## 结论

- 本阶段结论：`stage003_stop_or_attribution_before_more_runs`
- 是否进入下一步：等待独立 agent review 后决定。
- 下一步：若仍明显失败，停止 full-market broad-veto 方向，回到更窄 AI 承载或只读归因。

## 过拟合反思

- 运行前判断：否。关闭 OI restore 是修正有效风险定义，不是根据结果调小数。
- 运行后判断：等待独立 review。

## 继续价值反思

- 运行前判断：有价值，因为 Stage002 发现 `0.02` 会被 OI restore 放大。
- 运行后判断：等待独立 review。

## 独立 Agent Review

- review 时间：`2026-07-09 20:05 CST`
- reviewer：独立 agent `019f46aa-aec4-7a50-9d66-6158a9de5dbd`
- review 结论：无 P0。没有发现 Stage003 输出不可用、AI 文件未接入、summary 造假或明显未来函数导致结果失真的证据。
- P1：Stage003 结果形状仍然失败，不建议晋级多周期验证。C 期末权益 `525,988.0` 虽较 Stage002 的 `106,927.8` 明显修复，但远低于 A official `5,979,281.0`；最大回撤 `-81.9919%`、broker10 max `234.1021%`，已经超过本线继续推进的风险容忍。最差回撤日 `2024-03-22`，权益 `95,921.8`；broker10 峰值日 `2023-05-26`。
- P1：这不是 OI restore 没关干净的 bug。risk audit 与明细一致：`entry_risk` 735 行、`entry_candidates` 2427 行，`risk_ratio min=max=0.02`，`risk_multiplier min=max=1.0`，`oi_restore enabled/applied=0`。
- P2：Stage003 确实继承 Stage002 active full-market bottom25 veto。Stage002/Stage003 eligibility 均为 `2880` 行，outer merge 后 `both=2880`，`score/rank/top_n` 差异全为 `0`；eligibility audit 78 个评估月一致。
- P2：PIT 审查通过。特征构造只取 `date <= eval_date`；旧特征只合入预声明 market feature 列，没有合入 future label；输出层 `signal_date > candidate date` 为 `0`、`signal_date == candidate date` 为 `0`。
- P2：AI 接线自洽。entry_candidates 中 AI enabled `2427/2427`、allowed `1715`、blocked `712`、opened `706`；无 opened but AI not allowed，allowed 行均可在 eligibility key 中找到。
- reviewer 置信度：中高。summary 复算一致：`end_equity=525,988.0`、`return=250.6587%`、`max_drawdown=-81.9919%`、`Sharpe=0.6378`、slippage `215,020`、trade_count `1,503`、非零交易日胜率 `51.0609%`、broker10 max `234.1021%`。
- review 后决策：不进入逐半年多周期；停止 `full-market broad-veto + 0.02 effective risk` 作为候选推进。若继续，只做只读归因，解释 2022-2024 深回撤和 broker10 压力来源。
