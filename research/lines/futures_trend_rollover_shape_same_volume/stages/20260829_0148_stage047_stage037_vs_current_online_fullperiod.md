# Stage047 Stage037 与当前线上版本全周期复核

- line_id：`futures_trend_rollover_shape_same_volume`
- 当前模式：`day`
- 记录时间：`2026-08-29 02:03 CST`
- 工作区/分支：`.worktrees/stage047-stage037-vs-live-fullperiod` / `codex/stage047-stage037-vs-live-fullperiod`
- 阶段性质：只读全周期 A/C 复核；固定版本、固定参数、固定起点，不扫描参数
- 是否重要突破：否；单一全周期结果明显占优，但没有提供独立起点或样本外证据
- 是否触发A/B：是；按 `version-ab-experiment` 纪律冻结 A/C 身份和数据合同

## 外部调研与判断

- 参考资料：AQR《A Century of Evidence on Trend-Following Investing》；Moskowitz、Ooi、Pedersen《Time Series Momentum》。
- 我的判断：外部证据支持趋势跟随需要跨较长历史和不同市场状态检验，但不直接证明 Stage037 的精确图形阈值。此次只回答“Stage037 相对当前线上版本在相同全周期口径下表现如何”，不把单一起点优势解释为可直接晋升的因果证据。

## 本次变更

- 新增脚本：`tools/stage047_stage037_vs_current_online_fullperiod.py`，同时新跑当前线上 A 和 Stage037 C，并锁定生产身份、数据库、AI池、配置差异、过滤合同与五日换月合同。
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：无；仅新增研究臂命名和身份校验。
- 修改参数：无；Stage037 完整继承历史冻结参数。
- 删除参数：无。
- 当前线上到 Stage037 的完整差异共 13 项：启用多空 10 日区间/ATR5 过滤、`3×ATR` 区间、近 3 日 `0.5×ATR` 停滞、严格大于 `4×ATR` 的有序逆向移动、三类开仓上下文、五交易日延迟换月，以及新合约自身历史模式。不能将结果仅归因于某一个新增拦截条件。

## 回测/归因参数

- 数据区间：请求 `2018-01-01 -> 2026-08-28`，实际交易日 `2018-01-02 -> 2026-08-28`，共 `2101` 个交易日。
- 账户规模：A/C 均为 `150,000 CNY` 独立空仓启动，风险乘数均为 `0.4`。
- 成本口径：两臂使用同一真实引擎和同一品种成本配置；没有改变手续费、滑点或保证金口径。
- 样本过滤：生产数据库 SHA256 `ee83eae2159afec2b745a5827f73aaf9da1e71d65af2c0a624496555c08b6ebe`，最新日线 `2026-08-28`；AI池 SHA256 `56b6a35419831809a27cf222a019e0a62c9dc34390fd996243ee26353a7004cf`，`513` 行、`56` 个月度评估日。
- 策略/归因口径：A 为当前线上 `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`；C 为 `stage037_stage034_long_short_mirror_hard_block_v1`。生产 HEAD 与 `origin/master` 均为 `09aa96a03fb91124be90bd69861be3f834ab6299`，线上配置 SHA 与生产配置 SHA 完全一致。
- 正式物料：`m0015_20260825T205121+0800_c097d7836dd4`，manifest SHA256 `495f37eaa9802ba5b8042d15ca599d62d72ab607f595d4b1492a5904981c38d0`。
- 线上代码绑定：A 臂从生产 worktree 直接加载 `s513/s827/s901/live_config/strategy` 五个核心模块，全部路径通过生产目录白名单；生产策略 SHA256 `af5d0fb9affedbb8a54f5c6691a2e0f0d32b6cc2193d5379b1b3923a3813ad94`。生产 HEAD、本地 `origin/master` 与实时 `git ls-remote origin master` 三者均为 `09aa96a03fb91124be90bd69861be3f834ab6299`。
- AI池绑定：研究物料与生产物料分别读取并校验，路径不同但 SHA256、行数和评估日期范围逐项一致；`production_parity_pass=true`。

## 结果

### A 当前线上 Stage847-C9-15w + Q

- 期末权益：`14,665,615.10`
- 总收益：`9677.0767%`
- 最大回撤：`-44.9033%`
- Sharpe：`1.461353`
- 总滑点：`1,743,270`
- 总交易次数：`847`（成交记录口径）
- 胜率：`52.6690%`（非零交易日胜率）
- 其他关键指标：CAGR `69.8397%`；broker10 保证金/权益峰值 `99.6724%`；超 `100%` 天数 `0`；账户最低权益 `128,690.00`。

### C Stage037 多空镜像硬拦截

- 期末权益：`16,862,237.30`
- 总收益：`11141.4915%`
- 最大回撤：`-39.9147%`
- Sharpe：`1.539584`
- 总滑点：`1,671,655`
- 总交易次数：`734`（成交记录口径）
- 胜率：`53.1502%`（非零交易日胜率）
- 其他关键指标：CAGR `72.6018%`；broker10 保证金/权益峰值 `93.5807%`；超 `100%` 天数 `0`；账户最低权益 `122,871.30`。

### C 相对 A

- 期末权益 `+2,196,622.20`，总收益 `+1464.4148pp`，最大回撤改善 `4.9886pp`，Sharpe `+0.078231`。
- 总滑点 `-71,615`，成交记录 `-113`，非零交易日胜率 `+0.4812pp`，broker10 峰值下降 `6.0917pp`。
- Stage037 共 `972` 条过滤诊断，`971` 条有效；条件命中 `152`，实际新增硬拦截 `144`，其中多头 `73`、空头 `71`；另有 `8` 条在前序规则已归零，不重复计数。
- 过滤、目标合约自身历史和五交易日延迟换月合同全部通过；A/C 均账户存活，超 `100%` 保证金占比天数为 `0`。
- 全周期比较门通过，但 `promote_to_official=false`：单一全周期起点不触发自动晋升。
- 独立 reviewer 初审曾发现 A 臂只锁配置、未锁生产策略源码的身份缺口；修复后 A 改为直接运行生产 checkout 核心模块，并新增生产 AI 池 parity 与实时远端 master 门。最终机械重跑数值与初次结果逐值一致，说明数值未受影响，身份合同已闭合。

## 输出文件

- report：`artifacts/stage047_stage037_vs_live/stage047_stage037_vs_live_report.md`
- summary：`artifacts/stage047_stage037_vs_live/stage047_stage037_vs_live_summary.csv`
- orders：`artifacts/stage047_stage037_vs_live/stage047_stage037_vs_live_trades.csv`
- daily：`artifacts/stage047_stage037_vs_live/stage047_stage037_vs_live_curve.csv`
- quality：`artifacts/stage047_stage037_vs_live/stage047_stage037_vs_live_decision.json`、`stage047_stage037_filter_contract.csv`、`stage047_stage037_filter_diagnostics.csv`
- chart：`artifacts/stage047_stage037_vs_live/stage047_stage037_vs_live_equity.png`

## 结论

- 本阶段结论：在当前生产数据、当前 AI 池、同成本和同资金口径的 `2018-01-01 -> 2026-08-28` 全周期中，Stage037 的收益、最大回撤、Sharpe、滑点和成交数量均优于当前线上版本。
- 是否进入下一步：可以作为研究候选继续做固定多起点/分段稳健性复核；不能仅凭本结果自动晋升或部署。
- 下一步：如需评估晋升，应复用已冻结 Stage037，不调参，检查不同起点、年度贡献和拦截交易的样本外稳定性。

## 过拟合反思

- 运行前判断：本次复跑本身不是新增过拟合，因为版本、参数和起点均事先固定；Stage037 历史形成过程仍有较高后验选择风险。
- 运行后判断：结论不变，仍存在过拟合风险。
- 原因：全周期优势较全面，但只有一个起点，且 Stage037 含 13 项相对线上差异，无法由本次对比隔离每项规则的独立贡献，也不能替代跨起点或样本外验证。

## 继续价值反思

- 运行前判断：有价值；能够用当前真实线上身份和最新生产数据消除旧基准误配疑问。
- 运行后判断：仍有价值继续做稳健性诊断，但没有继续扫参数的价值。
- 原因：Stage037 在收益和主要风险成本指标上同时改善，信号不是单一收益指标偶然变好；下一步应验证稳定性，而不是围绕结果继续调阈值。

## 安全边界

- 本次为隔离 worktree 内的离线研究；没有连接 CTP，order/send/cancel API 调用均为 `0`。
- 未修改当前线上生产 worktree、正式物料、AI池、launchd、邮件、远端 master 或券商状态。

## 合入建议

- 是否更新本线 `LINE.md`：否；同线存在并行研究，只提交唯一 Stage047 记录，待统一合入时整理。
- 是否更新 `research/registry.md`：否；研究线归属未变化。
- 是否追加根目录 `memory.md/back_log.md`：否；当前只是全周期诊断，不是正式候选晋升或重要突破。
