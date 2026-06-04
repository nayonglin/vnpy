# Stage349 ec.INE 期货代理新鲜度取证

## 基本信息

- 时间：2026-06-04 11:34 CST
- 阶段性质：低单笔风险扩池 / 第二独立风险槽 `ec.INE` 的本地期货代理数据新鲜度 forensic
- 所属研究线：`futures_trend_drawdown30_preserve_return`
- 是否重要突破版本：否；这是数据管道阻塞定位，不是收益候选
- 是否修改交易规则：否
- 是否做收益回测：否
- 是否连接 CTP/SimNow：否
- 是否生成 selector / paper / A/B / 交易白名单：否，全部继续锁定

## 调研结论

- 外部调研：
  - INE EC 产品页确认 EC 是 SCFIS 欧线期货，标的是上海航运交易所发布的 SCFIS 欧线指数，指数行情指向上海航运交易所。
  - INE 英文合约页显示 EC 合约乘数、交易时间、最低保证金、现金交割等实盘合约条件。
  - AKShare GitHub 文档有 `futures_contract_info_ine` 接口，可用于只读核验 INE 合约参考信息。
  - GitHub 搜索没有发现可靠的专用 SCFIS 历史 Python 包；SCFIS 路线仍应继续用官方页面 raw hash + 自定义 parser + PIT ledger。
- 本次外部只读核验：
  - 沙箱内 AKShare/INE DNS 失败后，按权限规则外部网络只读重跑成功。
  - `ak.futures_contract_info_ine(date="20260603")` 显示 2026-06-03 官方活跃 EC 合约为 `ec2606/ec2607/ec2608/ec2609/ec2610/ec2611/ec2612/ec2703`。
- TQSDK 只读探针：
  - 沙箱内访问 `auth.shinnytech.com` DNS 失败。
  - 外部网络 TQSDK 认证读行情探针被策略拒绝，未绕行、未写库、未获取新日线。
  - 因此本阶段只做取证和修复路径定义，不宣称已完成 EC 行情修复。

参考链接：

- INE EC 产品页：`https://www.ine.cn/products/futures/index_f/ec_f/`
- INE 英文 EC 合约页：`https://www.ine.cn/eng/market/futures/index/ec/index.html`
- 上海航运交易所 SCFIS：`https://en.sse.net.cn/indices/scfisnew.jsp`
- AKShare INE 合约信息文档：`https://github.com/akfamily/akshare/blob/main/docs/data/futures/futures.md`

## 本次改动

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage649_ec_ine_futures_proxy_freshness_forensic.py`
- 只读输入：
  - `examples/portfolio_backtesting/downloaded_futures/tqsdk_daily_2010_2026_04/INE/ec*.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage633_independent_risk_slot_correlation_map_product_map_stage633_independent_risk_slot_correlation_map_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage647_ec_ine_second_slot_source_probe_product_evidence_stage647_ec_ine_second_slot_source_probe_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ec_ine_scfis_master_pit_ledger.csv`
- 新增参数：无
- 修改参数：无
- 删除参数：无
- 新增回测结果：无，未做收益回测
- 修改回测结果：无
- 删除回测结果：无

## 核心结果

- decision：`ec_ine_futures_proxy_stale_due_missing_revised_contracts_selector_locked`
- 本地 EC 合约文件数：`12`
- 官方 2026-06-03 活跃 EC 合约数：`8`
- 官方活跃合约本地覆盖率：`0.00%`
- 本地 EC 最新可交易日：`2026-02-09`
- 本地 INE dump 最新可交易日：`2026-04-15`
- 本地 EC 到官方参考日 `2026-06-03` 的日历缺口：`114` 天
- Stage633 `days_behind_latest_tradable`：`67`
- 官方活跃合约全部缺失：`ec2606/ec2607/ec2608/ec2609/ec2610/ec2611/ec2612/ec2703`
- 在本地 dump 最新日期前已经上市但仍缺失的合约：`7`
- Stage633 `data_pass`：`0`
- Stage633 `watch_corr_pass`：`0`
- Stage633 `low_corr_pass`：`0`
- max abs corr to P0：`0.1634`
- rolling abs corr p75 to P0：`0.2175`
- tail abs corr to P0：缺失
- SCFIS master rows：`1`
- SCFIS collection PIT dates：`1`
- hard gates：`4/9`
- selector / paper / trading whitelist：`0 / 0 / 0`

回测记录字段：

- 期末权益：不适用（未做收益回测）
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage649_ec_ine_futures_proxy_freshness_forensic_report_stage649_ec_ine_futures_proxy_freshness_forensic_v1.md`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage649_ec_ine_futures_proxy_freshness_forensic_decision_stage649_ec_ine_futures_proxy_freshness_forensic_v1.json`
- local contracts：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage649_ec_ine_futures_proxy_freshness_forensic_local_contracts_stage649_ec_ine_futures_proxy_freshness_forensic_v1.csv`
- official gap：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage649_ec_ine_futures_proxy_freshness_forensic_official_contract_gap_stage649_ec_ine_futures_proxy_freshness_forensic_v1.csv`
- gates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage649_ec_ine_futures_proxy_freshness_forensic_gates_stage649_ec_ine_futures_proxy_freshness_forensic_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage649_ec_ine_futures_proxy_freshness_forensic_chart_stage649_ec_ine_futures_proxy_freshness_forensic_v1.png`

## 图表视觉复盘

- 左上图：官方活跃 EC 合约横向时间线全部是红叉；本地最新 EC 线停在 `2026-02-09`，而官方参考日是 `2026-06-03`，说明缺口不是某个单日异常，而是新挂牌合约没有进入本地下载清单。
- 右上图：`114` 天缺口是最大柱，`Stage633 days behind=67` 是在本地全品种最大日期口径下的相对落后；两者都指向同一问题：EC 代理不新鲜。
- 左下图：`max abs corr=0.1634` 高于严格 `0.15` 线但低于/接近观察区，`rolling p75=0.2175` 已高于 `0.20` 观察线，tail corr 缺失；即使修好日线，也必须重新审计相关性，不能直接晋级。
- 右下图：绿灯只有官方合约清单、本地旧 EC 文件、SCFIS master 和 fail-closed；红灯集中在当前官方活跃合约覆盖、新挂牌合约下载、本地代理新鲜度、Stage633 data/watch corr。
- 视觉质量：图表无关键遮挡；左上图时间刻度略密，但不影响读取“全部红叉”和三条参考线。

## 结论

- `ec.INE` 的当前问题不是已经被证明没有独立趋势机会，而是本地可交易期货代理在 2026-02 后断档。
- 断档根因高度指向 EC 挂牌结构变化后的合约清单/下载覆盖缺失：本地只有到 `ec2602`，但官方 2026-06-03 活跃合约是 `ec2606/ec2607/ec2608/ec2609/ec2610/ec2611/ec2612/ec2703`。
- 因此 Stage633/647 的 EC 相关性和趋势证据只能作为历史 watch 证据，不能作为可部署新风险槽证据。
- 下一步必须先做只读 EC 合约发现 + 日线修复 collector，优先目标为 `ec2606/ec2607/ec2608/ec2609/ec2610/ec2612/ec2703`；`ec2611` 是 2026-05-26 后新上市，只有数据源允许 post-May 刷新时才应纳入。
- 在日线修复、tail/rolling corr 重算、PIT/outcome 样本、真实 TCA 全部闭合前，`ec.INE` 不允许进入 selector、paper、A/B 或交易白名单。

## 过拟合反思

- 运行前判断：不是过拟合。
- 运行后判断：不是过拟合。
- 原因：
  - 本阶段没有改策略、没有扫参数、没有用未来收益筛品种。
  - 外部官方合约清单只用于判断本地数据覆盖，不用于生成交易信号。
  - 结论是锁定晋级并要求补数据，而不是为了扩池放宽门槛。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但下一步必须先修数据。
- 原因：
  - `ec.INE/SCFIS` 的经济驱动与 P0 核心商品不同，仍可能是第二独立风险槽。
  - 当前最大阻塞是可交易代理缺失，不是 alpha 已被反证。
  - 如果修复后相关性仍高或 tail corr 失败，应果断降级；如果修复后低相关和 PIT/outcome 能闭合，再讨论 selector。

## TODO

- 新建只读 EC 合约发现与日线修复 collector，输入官方 INE 合约列表，输出缺失合约清单和本地 raw csv，不写交易规则。
- 修复完成后重跑 Stage633 相关性图，专门比较修复前后 `ec.INE` 的 `max_abs_corr / rolling p75 / tail corr / data_pass`。
- 若仍只能到 watch corr 或 tail corr 缺失，继续 monitor；不得因为“航运驱动看起来独立”就提前放行。

