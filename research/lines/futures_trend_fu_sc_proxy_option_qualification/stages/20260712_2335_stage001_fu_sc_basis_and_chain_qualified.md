# Stage001 FU-SC T-1 basis 与历史期权链资格终版

- line_id：`futures_trend_fu_sc_proxy_option_qualification`
- 当前模式：`day`
- 记录时间：`2026-07-12 23:35 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：跨品种 basis 与历史 metadata 数据资格；不是策略回测
- 是否重要突破：是，首次证明单一 `FU->SC` 代理具有严格 T-1 关系与全事件历史链
- 是否触发 A/B：否

## 外部调研与判断

- 跨品种期权套保在直接工具缺失时具有理论资格，但会把价格风险替换成 basis/quantity/liquidity risk，不能直接假定保护有效。
- 上能中心确认 SC 期权自 `2021-06-21` 上市，标的是1000桶原油期货、美式、CALL/PUT 均有；TqSdk 官方接口支持历史 `TqBacktest`、`query_options` 与 symbol metadata。
- OLS hedge ratio 必须显式带截距；连续期货 roll 与实际合约收益必须分开。本阶段采用前一交易日 OI 选实际合约、同合约 close-to-close。
- 我的判断：Stage001 证明的是“代理关系与期权链存在”，不是“保护能赚钱”。下一步必须先验证真实 ask/spread/volume/OI 和整数粒度。

## 本次变更

- 新增 `tools/stage001_fu_sc_t1_beta_gate.py`。
- 新增 `tools/stage001_sc_option_chain_coverage.py`。
- 新增标准库测试两份，共 `6/6` 通过。
- 新增预声明与两份实施计划。
- 新增 T-1 选约、共同收益、事件 beta/corr、gate、lineage、manifest、SC query plan、32个原子 event cache 和 normalized metadata。
- 新增参数：单对 `fu.SHFE->sc.INE`、SC上市日、`126/63+63`、`corr>=0.50`、`beta>0`、核心 `6/6`、全体 `>=90%`。
- 修改参数：无。
- 删除参数：无。
- 正式 C9、AI、止损重试、CTP、邮件、launchd：均未修改。

## 冻结输入

- Stage131 events：`365/365` unique，SHA256 `7abf7a0414238517349e383a6ef7282b5f8d16921686ddc1edb6f2e70e5cc77a`。
- SC上市后 FU events：`32`，日期 `2022-02-25 -> 2026-01-20`，原风险合计 `4,385,686.4`。
- 核心 FU events：`6`，原风险 `956,200`。
- SQLite database SHA before/after：`59f0bd364253d7ec029cc183d48f161c15b9ee9af01075956924b4dad958f723`，稳定。
- 本阶段不读取 realized PnL、未来收益、账户权益或期权价格。

## T-1 return panel

- FU/SC 原始相关日线 `40,571` 行，contract-date 重复 `0`、非正 close `0`、负 OI `0`。
- 选约账本 `2,952` 行，有效 `2,951`；唯一缺失是 `2020-01-02` FU top-OI 合约次日无 bar，未递补第二名且早于全部事件窗口。
- FU/SC roll 切换 `22/68` 次；每一收益仍用被选同一实际合约的两日 close，跨合约直接相除 `0`。
- 共同收益 panel `1,475` 日，重复日期 `0`、T-1违规 `0`。
- `32/32` 事件均取得严格 `<entry_date` 的最后126共同日；entry-day/未来行 `0`。

## Beta/correlation 结果

| 窗口 | beta 最小/中位/最大 | corr 最小/中位/最大 |
| --- | --- | --- |
| full126 | `0.767208 / 0.862791 / 1.016563` | `0.744848 / 0.863910 / 0.929877` |
| early63 | `0.713699 / 0.881777 / 1.100689` | `0.667376 / 0.873258 / 0.940063` |
| late63 | `0.773751 / 0.844077 / 1.031046` | `0.714616 / 0.874594 / 0.935457` |

- 核心 history/pass：`6/6`。
- 全体 history/pass：`32/32`。
- 五项本地 gate：全部通过。
- 32个窗口高度重叠，最大共享 `123/126` 日；只能解释为32个事件均满足同一机械门，不能解释成32个独立样本。

## SC 历史链结果

- 固定 query plan：32 unique FU events；每条 SC underlying 由 entry day 的 T-1 OI mapping 得到。
- 核心6条严格先运行，`6/6 extracted` 后才继续剩余26条。
- 网络调用：`32`；总耗时约 `54.9163s`，每事件 `1.4640 -> 3.7687s`。
- request/cache：`32/32 valid`；metadata `32/32 extracted=100%`。
- normalized metadata：`2,148` 行；每事件 `40 -> 100` 行。
- CALL/PUT：`1,074/1,074`；每个 event/expiry/strike 恰好一对，异常 `0`。
- wrong underlying、event-option重复、无效 strike/expiry、expired true、非正 multiplier/tick：全部 `0`。
- multiplier 全部 `1000`，price tick 全部 `0.05`。
- 32 event manifests 共 `160` payload hashes；root manifest `37` 项，独立重算全部匹配。
- 凭据精确命中 `0`；premium/bar/tick API调用 `0`，价格字段 `0`。

## 机械决策

- `ALLOW_STAGE002_EXECUTION_DATA_PREDECL_ONLY`。
- `ready_for_option_strategy_ab=false`。
- `ready_for_live=false`。
- 不批准 premium/bar/tick 下载、收益回测、A/B、正式候选或实盘；Stage002 必须先单独预声明。

## 回测结果占位

- 期末权益：N/A。
- 总收益：N/A。
- 最大回撤：N/A。
- Sharpe：N/A。
- 总滑点：N/A。
- 总交易次数：`0`。
- 胜率：N/A。

## 独立 review 1：beta gate

- `P0=0/P1=0/P2=2/P3=3`；数值正确性 `99%`、metadata准入 `96%`。
- 独立逐行复算选约、收益、OLS 与相关系数；beta 最大误差 `1.11e-15`、收益最大误差 `9.96e-17`。
- P2：预声明写“未到期合约”，实现未显式 expiry gate；当前实际选约没有进入或越过交割月，不改变结果。
- P2：lineage 未冻结工具/test/predecl/SQL extract hash 与供应商来源；不影响当前数据库与事件 hash 闭合。
- P3：缺 OI tie、到期、重复规范化、零方差与90%边界测试；事件窗口非独立；当时尚无结果 stage。
- 按用户要求，均不影响当前资格数字，保留日志而不重跑 beta 参数。

## 独立 review 2：metadata chain

- `P0=0/P1=0/P2=1/P3=1`；终审置信度 `99%`。
- 独立复算32 cache、2,148 metadata、CALL/PUT、九项字段、underlying、expiry、expired、manifest与凭据泄露，全部闭合。
- P2：Stage001 cache复用 validator 只验 hash/identity/行数，没有重算 normalized metadata 语义；当前快照已被 reviewer 全量独立复算，不影响当前批准，但 Stage002 执行前必须用独立 validator 修复。
- P3：ledger/manifest 使用绝对路径，降低迁移性但不是凭据泄露，不影响 hash。

## 验证

- focused unittest：`6/6`。
- py_compile：通过。
- beta tool SHA：`1564670332c32c296b623a09dbb2cae8e567d20cd0ade8cda158259e2d077046`。
- chain tool SHA：`9531cd05272b7c66631b7e24626d9e071db0c42dd9ef82fd6e2c0f3710918f9e`。
- beta decision SHA：`f318bd57553fbf3dc90d0c9cc03453289efbf331804d2afab07884053362b7e0`。
- chain decision SHA：`0d2f578f514b8424b9e05e3b91c996cd19c73f642fffbec9827cedaeafb90885`。
- chain root manifest SHA：`00ea4de43fed68d96dc193ebce97131d0be90dfa2b77675135cce1107a50bd10`。

## 过拟合反思

- 运行前判断：中低；FU来自2022亏损归因，有后验动机，但单一pair、全集和固定门限制自由度。
- 运行后判断：否；没有调窗口、阈值、pair或删事件，没有读取收益。
- 风险提醒：高重叠事件不构成独立样本；后续若按结果调 strike/DTE/预算会立刻转为高过拟合。

## 继续价值反思

- 运行前判断：有，只值得做单pair一次资格门。
- 运行后判断：有，但只限 Stage002 execution-data 资格。
- 原因：basis与metadata已通过，但 option premium、ask spread、成交量/OI、theta、整数过度对冲和退出价格均未知。

## 下一步

- Stage002 先做独立 metadata semantic revalidation，修复 reviewer P2。
- 冻结 T-1 SC prior close 最近 ATM + adverse-side 单一选券，不扫描 strike/DTE。
- 只获取 entry-day minute/tick 做可成交性和 money-delta 粒度门；先核心6条 canary。
- 未通过即关闭；通过也不自动进入收益回测。

