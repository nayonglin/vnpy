# AI选品XGBoost PIT全市场数据源重建线

- line_id：`futures_trend_xgboost_pit_full_market_source_rebuild`
- 资产/策略：商品期货趋势 / 线上逻辑回归独立研究分支的数据基础设施
- 当前状态：Stage002已通过原54个月覆盖硬门，决策`stage002_endofday_source_rebuild_coverage_pass_allow_new_model_preregistration_only`。唯一修复是整批订阅后推进到`BacktestFinished`再复制截止日日K；Stage001失败产物保持冻结。未读取标签、未训练模型、未运行策略回测，正式实盘、CTP、订单与共享数据均未改。
- 研究目标：在固定截止日 `2026-06-30` 下，从同一生产者 TqSdk 重建 `2021-01-18` 至截止日的全商品期货合约目录、主力映射和日线，并按上一研究线原封不动的 54 个月资格门重新审计。
- 上游失败证据：`futures_trend_xgboost_pit_full_market_one_slot` Stage001 因旧映射在 `2026-05` 起从 `86` 个品种缩到正式池 `19` 个，导致末段合格品种与池外挑战者归零而闭线。
- 隔离边界：只允许写本研究线；禁止修改共享主力映射、`.vntrader/database.db`、生产 release、CTP、订单、正式AI配置或任何旧研究线。
- 固定结论边界：数据覆盖通过只允许另立模型预注册，不等于 XGBoost 有效，不授权标签、真实引擎、A/B、shadow 或上线。

## 当前阶段

- Stage000：`stages/20260904_1117_stage000_full_market_source_rebuild_preregistration.md`
- Stage000A：`stages/20260904_1121_stage000a_dce_monthly_average_contract_exclusion.md`
- Stage000B：`stages/20260904_1125_stage000b_unresolvable_calendar_stale_placeholders.md`
- Stage001：已冻结 `stage001_source_rebuild_coverage_fail_close_no_model`；54月中仅`2026-06-30`失败，根因是截止日日K未推进到结束；结果记录为`stages/20260904_1155_stage001_cutoff_open_snapshot_fail.md`。
- Stage002：已完成并通过；986个计划合约为`922 fetched / 64 empty / 0 failed`，54月合格品种最小/中位/最大为`50/53/60`，正式替换48月全部动作就绪，最少池外挑战者34；结果记录为`stages/20260904_1155_stage002_endofday_source_rebuild_pass.md`。

## 冻结硬门

1. 截止日目录必须由 `TqBacktest(2026-06-30, 2026-06-30)` 查询；主力映射必须由 `TqContCalendar` 精确请求 `2021-01-18..2026-06-30`。
2. 商品范围固定为 `CZCE/DCE/GFEX/INE/SHFE`；CFFEX排除。
3. 旧归档只复用截止日已到期且文件内容 SHA 可重验的 TqSdk 合约；截止日仍存续或主力映射必需但缺失的合约必须用截止日回测 serial 线内重建。
4. 映射、日线输出不得出现 `date > 2026-06-30`，不得使用邻日、连续合约行情、跨品种代理或人工补值。
5. 54个月覆盖门保持不变：每月合格品种 `>=30`；A-rank10合格月 `>=36`；每个A-rank10合格月池外挑战者 `>=10`；`252/241/60日90%/同日2合约`门全部保持。
6. 标签读取、模型fit/predict、策略回测、CTP、订单API、生产写入全部必须为0。

## 下一步

- 本数据源重建线冻结收口，不再继续同源补洞或修改Stage001/002产物。
- 若继续XGBoost，必须另立模型合同预注册线：先冻结特征、标签、walk-forward切分、逻辑回归A、XGBoost B、融合C及收益/回撤双重硬门，再申请单次执行授权。
- 当前通过只证明全市场PIT数据资格，不授权读标签、训练、真实引擎、A/B、shadow或上线。

## 过拟合反思

- 当前判断：否。Stage000-002只验证数据源可得性、身份和覆盖，不接触收益标签或模型输出。
- 风险边界：若根据末段覆盖结果修改品种、日期或门槛，或把通过误写成收益证据，将构成结果后过拟合。

## 继续价值反思

- 当前判断：本线继续修复价值为否，数据资格目标已经完成；整体XGBoost研究有条件继续。
- 原因：统一TqSdk源已通过原54个月硬门，继续改源只会增加结果后自由度；下一步价值只存在于另立、事前冻结、可证伪的模型实验。
