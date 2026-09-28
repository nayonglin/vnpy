# Stage002 截止日完整日K数据源修复预注册

- line_id：`futures_trend_xgboost_pit_full_market_source_rebuild`
- 当前模式：day
- 记录时间：2026-09-04 11:41 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：Stage001冻结失败后的数据采集时序缺陷修复与原门复验；不是模型、标签或策略回测。
- 是否重要突破：否。
- 是否触发A/B：否。
- 用户授权：2026-09-04“授权数据源重建”继续覆盖本次同一数据源的端-of-day缺陷修复；不扩展到标签、模型或回测。

## Stage001冻结结果

- 决策：`stage001_source_rebuild_coverage_fail_close_no_model`。
- 源合同门：全部通过；986个增量合约 `922 fetched / 64 empty / 0 failed`，SHA漂移/未来行/重复键均为0。
- 覆盖：54月、3,836行、2,840合格、1,947池外挑战；A-rank10合格47月、动作就绪47月、合格月最少挑战者34。
- 唯一失败月：`2026-06-30`，80个品种全部不合格，曲线合约不足68个品种，其他12个品种先被更早资格门拒绝。
- 其余53个月合格品种为 `50..59`，全部通过30品种门。
- Stage001结果与manifest保持冻结，不覆盖、不删除、不改写。

## 根因与最小复现

- Stage001增量抓取在每个 `get_kline_serial` 返回后立即 `copy`，没有推进 cutoff-day 回测到结束。
- 官方 `TqBacktest` 文档说明回测K线在创建和结束时各更新一次：<https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.backtest.html>。
- 单合约 `SHFE.cu2607` 同一截止日复现：
  - 创建快照：OHLC均`102790`，volume=`0`，open/close OI=`56845/56845`。
  - 推进到 `BacktestFinished`：OHLC=`102790/103270/101820/103160`，volume=`23802`，open/close OI=`56845/48605`。
- 因此Stage001的`2026-06-30`曲线全0是采集时点缺陷，不是原覆盖门反证；修复必须另发Stage002，不能覆盖Stage001。

## 唯一允许变更

1. 旧时序：订阅一个合约 -> 立即复制serial -> 下一个合约。
2. 新时序：先订阅整批全部合约 -> `wait_update`推进到`BacktestFinished` -> 再逐合约复制serial。
3. 批次默认40；失败批次仅允许逐合约重试一次，不能改日期、品种或字段。
4. Stage001截止日目录、主力映射、旧归档清单、986合约计划、54个月正式排名和覆盖核心全部字节级复用。
5. Stage002写入独立 `artifacts/stage002_endofday_source_rebuild/`，不得修改Stage001 raw/summary/manifest。

## 冻结Stage001输入身份

- catalog SHA256=`c733e5d85bab4349efb9bd25e2afdd689562718ffd608bff9a4f11964ab13bfc`。
- mapping SHA256=`1b9059e42161a71aaacd7d6367cbe4c7cd95eb944a1f463baf360aa038fec34d`。
- archive inventory SHA256=`04ff533525f8da3a25b283f292de7882050dcf5ebd774dbdee5034de57b7df37`。
- acquisition plan SHA256=`21a2e2f5dd6b2c76cbbed39ca43c96c22155dc50f35b02d04471db53657b9a24`。
- prepare receipt SHA256=`971076b5242273b79728a7b94a4fecae5bffd649018793887454e8fa9041587d`。
- Stage001 summary SHA256=`a9ba8d212aa0f40587fedca7ac50667a8fee23799e8a9e6a320706f246ef67fc`。
- Stage001 monthly SHA256=`3d864f14a1f858be796cef2e0c1abcc054a082f954a4e143db2a23adf5162bb6`。
- Stage001 manifest SHA256=`d40046f9ef81aeca66849bfdcfc75093e650b286e478357f42f270859c09fc3b`。

## 实现与测试身份

- Stage002 runner SHA256=`03802baafe4c712f3263bf1a3ca1c0a337073a4ec91bd37b98192613fb541f1b`。
- Stage002测试 SHA256=`e29dba422fc27abf6a7e4989fccaeef41949238b88cbc96c721e5f3e7c0b7b4a`。
- TDD红灯：Stage002模块不存在时收集失败。
- TDD绿灯：假API证明两个合约均先完成订阅，`wait_update`改变日K后抛出结束异常，返回文件中的volume/close只能是推进后值。
- 当前全线限定测试：`20 passed`；Stage002 `py_compile`通过。

## 覆盖硬门

- 与Stage001完全相同：54个月、252映射日、241有效close、60日活动率90%、同日曲线至少2合约、每月至少30品种、A-rank10至少36月、每个合格月池外挑战者至少10。
- 未来行、fallback、重复、CFFEX合格、标签读取、fit/predict、策略回测、CTP、订单API和生产写入全部为0。
- 不允许删除 `2026-06-30`、退截止日、使用6月29日曲线、邻日回填、降低曲线门或只补正式品种。

通过决策：`stage002_endofday_source_rebuild_coverage_pass_allow_new_model_preregistration_only`。

失败决策：`stage002_endofday_source_rebuild_coverage_fail_close_no_model`。若端-of-day完整日K仍不能通过原门，本线关闭，不再做第四次同源修复。

## 回测记录占位

- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。

## 过拟合反思

- 运行前判断：否；整体XGBoost目标仍为高风险。
- 原因：修复由同一日K在回测创建/结束两个生命周期状态的直接对照触发，未读取收益标签；目录、映射、计划和效果门全部冻结。

## 继续价值反思

- 运行前判断：有，且只限这一个采集生命周期缺陷。
- 原因：Stage001其余53个月均明显通过，失败集中于截止日且与volume=0机械对应；一次端-of-day修复有明确可证伪价值。若仍失败，继续同源修复价值为否。
