# Stage033/033B 持仓观察等价通过，原同步样本定义未通过

- line_id：futures_trend_xgboost_history_compatible_root_utility。
- 记录时间：2026-09-06 08:25 CST。
- 工作区/分支：/Users/bytedance/Desktop/person/vnpy / codex/stage130-option-probe。
- 阶段性质：无动作控制回放与数据资格，不是新策略回测或XGBoost候选；非重要突破，不触发A/B晋级或reviewer。
- 用户最新规则：日常改动、资格检查、失败实验均不启动reviewer；只对完整C同时改善收益与回撤且通过基本稳健性检查的有价值候选评审。本轮reviewer为0。

## 调研与判断

- [Longstaff-Schwartz论文索引](https://escholarship.org/uc/item/43n1k4jb)检索摘要提供条件继续价值的思路；直接打开被JS验证阻断，未绕过，不声称读完论文正文。
- [ArbitrageLab的XOU最优停止说明](https://github.com/hudson-and-thames/arbitragelab/blob/master/docs/source/optimal_mean_reversion/xou_model.rst)假设均值回归与两次交易；不照搬到趋势/组合路径，也不复制其阈值。
- 本地旧实验否定过固定止盈、保本与统一早停，但未找到同形状的持仓期XGBoost已运行证据。关键词排重不等于穷尽全部历史。
- 当前仅判断持仓决策域能否取得合法状态。日positions不能替代目标仓位、待平库存、活动订单和真实成交成本的完整证据；持仓日数量也不能直接当作独立训练样本数。

## 本次变更

- 新增工具：tools/stage033_holding_observer.py、tools/stage033b_holding_population.py；新增相应测试与08:04/08:19事前合同。
- 08:13冻结前测试发现旧Stage007a入场gate不支持观察器闭包，改用原始A worker分支，只安装无动作观察器。旧gate、旧入口及正式策略均未改，Stage007a七表等价验证继续复用。
- 08:15:15冻结1521逻辑输入；08:15:40-08:20:56唯一历史A控制回放，08:21:08父验证/归档完成；08:21:54完成只读根数量核验。
- 新增参数：无模型或策略参数。观察阶段仍固定原完整区间、FU不作为候选、60个严格月前已结束根门。新增命令仅为研究freeze/run/worker。
- 修改/删除策略参数：无；新增/修改/删除训练标签和模型：均无。旧失败的10输入、宏观输入和迁移输入候选不复活。

## 固定回放结果

数据区间2020-01-02至2026-08-28，本金150000；原成本、LR选品、C9与所有原执行参数不变。以下为无动作A与冻结A精确相同的结果，不是收益优化证据。

本文的实际/真实成交均指冻结历史回放产生的成交记录，不是券商实盘成交。

| 指标 | A与观察A |
| --- | ---: |
| 期末权益 | 12,226,270.60 |
| 总收益 | 8050.847067% |
| 最大回撤 | -45.921573% |
| Sharpe | 1.683943 |
| 总滑点 | 1,100,560 |
| 手续费 | 0 |
| 总成交记录数 | 655 |
| 非零日胜率 | 54.241877% |

- 胜率为非零净收益交易日口径，不冒称逐笔闭合交易胜率；655为成交记录数，不是655笔独立根交易。
- daily、positions、trades、entry_candidates、entry_risk、root_features、stop_retry_events七张语义表逐值精确相同；root_features沿用本线10项共同特征，不声称与旧V4的12列文件字节相同。
- 没有新增、修改或删除C策略结果，没有训练、预测新模型、构建或读取效用标签。原正式LR只读推断仍按原白名单运行。

## 观察与数量结果

- 1614日期、19产品、30666状态行；1755个非零合约日与原positions实际仓位完全一致。
- 分类：flat 27180、fixed_fu 1614、unfilled_or_inconsistent_plan 275、layer_not_synchronized 1002、pending_orders_or_close_inventory 548、rollover_pending 47；stable_holding为0。
- 1597个非FU实际持仓产品日全部唯一归入原根生命周期，涉及253根；276根全部保留，其中23根没有日末持仓观察。未成交、当日全平及删失不能伪造为稳定日。
- 原生命周期273成熟、1未成交撤单、1期末持仓删失、1期末待入场删失不变；同一根多日记录不重复计根，也不声称不同根统计独立。
- 事前严格同步条件下，合格持仓日、合格成熟根均为0，没有首个可训练月。不可变前缀与完整最大回撤均为2022-06-02的-45.921573%；当前定义不能进入模型训练。
- Stage033B的population_qualified_not_execution_or_model状态仅表示原始归属审计完成，其decision明确为stop_current_shape_joint_objective_impossible。不能把状态名解释为训练资格已通过。

## 同步字段的实际语义

- 1002个被同步条件挡住的日涉及155根；其中1002层entry_price均为正、entry_price_synced均为False、entry_date均为8位紧凑日期。
- 冻结生产源码qmt_roll_portfolio_strategy.py:6118创建层时使用信号bar日期和bar.close_price；:9444的_bar_date输出%Y%m%d。:3434的_sync_open_trade则将真实成交时间格式化为%Y-%m-%d，并在:3442要求与layer.entry_date完全相同后才更新价格与同步标记。格式不一致；下一日成交还存在日历日不同。
- 首个实际例证：2020-01-10 jm2005.DCE多2手，实际与目标一致、无活动订单；层entry_date=20200109、entry_price=1202.5、synced=False，逐笔BACKTESTING.3在2020-01-10真实成交1203.0。计划价不能直接当作真实成本。
- 这解释了当前字段不能支撑我们要求的成本同步资格，不是观察器改变了原策略，也不证明持仓期XGBoost必然无效。不能将False改为True或忽略此门来增加样本。
- 实际运行来源已记录：Stage847StopRetryEngine继承Stage840/Stage827/Stage502；new_bars、cross_delayed_orders、价格解析来自Stage502，_fill_order来自Stage827，cross_same_day_close_orders为null。先撮合已有订单，再处理当日策略；未来退出不能用当日完整bar信息回填同日较早成交，解析器还存在daily-next-open fallback，后续必须核查真实价格来源。

## 验证与身份

- 观察器测试先20 RED后GREEN，新增路由反例先1失败/26通过再27通过；根归属11项先RED后GREEN。最终本线与上游生命周期/回撤时间门共438 passed in 27.41s。
- 记录写入后再次运行同套测试438 passed in 26.70s；1521冻结输入仍全部未变，生产HEAD不变且git工作区干净。
- 08:24再次核验1521逻辑输入/1519唯一路径、冻结A科学输入、7压缩归档及7语义表精确等价、原始观察哈希/分类/仓位、根审计11来源与3输出身份、实际引擎源码哈希，全部通过。
- Stage033 file contract：aa736558c6eea8ed93570646e3373cb7ab0ffbde60bf2c5c1eeb042ddea8164d。
- Stage033 summary SHA256：d4567a19da9364e4f855006ce0c86467c60d88a0ce398ec7506a81e359345069。
- Stage033 worker receipt SHA256：dd55f72e8739a8dcc22857c7a87984b4dca0f3d49d1bebc7ea53d808d879e6bb。
- Stage033 trace gzip SHA256：7cd88bc94b215bcdd6f3531783499f09b2d5b0a90ff20659eb79b077c865ffba；解压SHA256：e9c7df22f11a86aec6b847acd12bfde6e00d00ead14969c918f4f1c68900cef6。
- Stage033B summary SHA256：72eaa894db8d84249131d496f0ae4146966e2c825a8504a8b5798652a9a93f54。
- 私有runtime及run.lock均清理；所有本轮进程已退出。网络、CTP、账户查询、真实订单API、生产写入、模型拟合/新预测、效用标签读取/构建等敏感计数均0。
- 08:24生产git工作区干净，HEAD仍为d492ee072aa5a9d71477235d79f17d2a5db59db3。未改正式策略/数据/映射/配置，未commit/push。

## 输出与下一步

- artifacts/stage033_holding_observer/summary.json；workers/A/holding_states.json.gz、observer_receipt.json、receipt.json及七份csv.gz。
- artifacts/stage033b_holding_population/summary.json；linked_holding_days.csv、root_population.csv、monthly_population.csv。
- 保留零样本结论，不改冻结Stage033分类或旧A。下一步仅研究用截至决策时点的真实逐笔成交与持仓账本建立独立成本记录，需覆盖减仓、全平、换月和原止损重试并逐日守恒；不把原层计划价当真实成本、不根据最终收益选择观察点。
- 只有成本来源、动作优先级、下一真实成交窗口及独立根时间门通过，才定义新的持仓退出效用合同。旧根入场效用标签不能挪用；也不能把Stage033B当前零样本几何结论推广到尚未定义的新动作。

## 反思与合入

- 运行前是否过拟合：否，本轮预声明观察条件，不按盈亏调参；长期历史反复开发的选择偏差仍在。
- 运行后是否过拟合：本轮否，原严格门得出0样本后没有降门或训练；观察器等价和测试通过均不是alpha证据。
- 是否有价值继续：是，仅继续真实成交成本与执行时钟的必要条件研究；直接训练当前零样本定义没有价值。收益提升且回撤下降的总目标未达到。
- 仅更新本线LINE.md与本线产物，不改registry、其他线和根memory.md/back_log.md，不启动reviewer。
