# Stage002 截止日完整日K数据源重建通过

- line_id：`futures_trend_xgboost_pit_full_market_source_rebuild`
- 当前模式：day
- 记录时间：2026-09-04 11:55 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：Stage001冻结失败后的唯一数据采集时序修复与原门复验；无标签、无模型、无策略回测。
- 是否重要突破：否；这是数据资格里程碑，不是收益或回撤突破。
- 是否触发A/B：否。
- 用户授权：2026-09-04“授权数据源重建”。

## 外部调研与判断

- TqBacktest 官方文档：<https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.backtest.html>。
- DataDownloader 官方文档：<https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.tools.download.html>。
- TqSdk 专业版历史数据说明：<https://doc.shinnytech.com/tqsdk/latest/profession.html>。
- TqSdk 上游实现：<https://github.com/shinnytech/tqsdk-python/blob/master/tqsdk/api.py>。
- 我的判断：TqSdk 可作为同一生产者的目录、PIT主力映射与日线来源，但 cutoff-day 回测 serial 必须在 `BacktestFinished` 后落盘。Stage002严格只修这一生命周期语义，避免把数据修复和模型效果混在一起。

## 本次变更

- 新增脚本：`tools/stage002_endofday_full_market_source_rebuild.py`。
- 新增测试：`tests/test_stage002_endofday_source_rebuild.py`。
- 修改脚本：无；Stage001 runner与产物保持冻结。
- 删除脚本：无。
- 新增参数：`--phase prepare/acquire/audit`、`--batch-size 40`、`--authorized-data-rebuild`。
- 修改参数：无；目录、映射、986合约计划、54个月和全部资格阈值与Stage001一致。
- 删除参数：无。
- 唯一语义变化：整批订阅 -> 推进至 `BacktestFinished` -> 再复制日K serial。

## 回测/归因参数

- 数据区间：`2021-01-18..2026-06-30`；评估月 `2022-01-28..2026-06-30`，共54月。
- 账户规模：`150,000`，仅用于一手保证金资格计算。
- 成本口径：不适用；未运行策略回测。
- 样本过滤：商品交易所 `CZCE/DCE/GFEX/INE/SHFE`；映射日数 `>=252`、有效close日数 `>=241`、60日活动率 `>=90%`、同日曲线合约 `>=2`。
- 策略/归因口径：每月合格品种 `>=30`；正式替换合格月 `>=36`；每个合格月池外挑战者 `>=10`。

## 结果

- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。
- 抓取：986个状态唯一，`922 fetched / 64 empty / 0 failed`；SHA不匹配0、行数不匹配0、未来行0、重复交易日0。
- 截止日预审：818个合约含 `2026-06-30` 行，其中712个正成交量、765个正close OI；`SHFE.cu2607` volume=`23,802`。
- 归一化日线：894,144行；覆盖3,836行、合格2,900行、池外挑战1,989行。
- 月度资格：54/54月满足每月至少30个合格品种；最小/中位/最大为 `50/53/60`。
- 正式替换：有正式A-rank10的48个月全部合格且动作就绪；最少池外挑战者34。
- 防泄漏：future bar/mapping used=`0/0`，fallback=0，label rows read=0，fit/predict=0，策略回测=0，CTP/订单API=0，生产写入=0。
- 所有 source gates 与 coverage gates 通过。
- 决策：`stage002_endofday_source_rebuild_coverage_pass_allow_new_model_preregistration_only`。
- 独立reviewer：不触发；本阶段没有产生策略回测数据。

## 输出文件

- report：`artifacts/stage002_endofday_source_rebuild/report.md`，SHA256=`6bc3786109e88ae2c8ec0100962c77b431b31a1617513f38fba99f8ce5f784a1`。
- summary：`artifacts/stage002_endofday_source_rebuild/stage002_summary.json`，SHA256=`67dcdb174bf7e253e100138eff1ec0b644c6a7cc68c0806f71aff10c66f00939`。
- monthly：`artifacts/stage002_endofday_source_rebuild/monthly_coverage.csv`，SHA256=`dbd394954d92ef041dcc00f88c6ed90df62e7b2b3578fb6cabaafb848d1c2047`。
- manifest：`artifacts/stage002_endofday_source_rebuild/artifact_manifest.json`，SHA256=`e3894cd20114182e9b3a9e986ed5e0310fe264de06368b5efe1b5efb6903681a`。
- orders/daily：不适用；没有订单或策略权益序列。

## 结论

- 本阶段结论：统一TqSdk全市场PIT源通过原54个月覆盖资格门，Stage001截止日断层已被最小时序修复消除。
- 是否进入下一步：是，但只允许另立“新模型合同预注册”；本结论不授权读标签、训练、真实引擎、A/B、shadow或上线。
- 下一步：冻结本线数据身份；在新研究线中先定义特征、标签、walk-forward切分、逻辑回归A、XGBoost B及融合C的收益/回撤双重硬门，再单次执行。

## 过拟合反思

- 运行前判断：否；目录、映射、计划、月份和门槛均在运行前冻结，未读取标签。
- 运行后判断：否；通过来自机械修复完整截止日日K，未按结果删除月份、品种或降低阈值。
- 原因：模型fit/predict、策略回测和收益指标均为0；数据资格通过不能外推为XGBoost有效。

## 继续价值反思

- 运行前判断：有；Stage001唯一断点有明确生命周期根因。
- 运行后判断：数据源重建本身已完成，不再继续同源修复；整体XGBoost研究仍有条件继续。
- 原因：54个月统一覆盖已建立，下一步可在不缩样本的前提下检验新模型；但只有独立walk-forward收益提升且回撤下降才算达到目标。

## 合入建议

- 是否更新本线 `LINE.md`：是，标记数据资格完成。
- 是否更新 `research/registry.md`：是，登记Stage002通过与严格边界。
- 是否追加根目录 `memory.md/back_log.md`：否；这是模型研究前置资格，不是正式候选或回测突破。
