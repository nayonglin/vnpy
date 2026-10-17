# Stage033：C_TS attempt2 完整账户独立复核与固定形状失败结论

- line_id：futures_trend_triple_screen；复核时间：2026-10-18 03:23 CST；审查员 ordered_financial_auditor。
- 阶段性质：独立金融与来源复核，不是重要突破；无新增金融回放、训练、网络、生产/CTP动作；不修改031或原028交易模块、旧030/失败收据、LINE、registry。
- 实际金融运行：root以write_stdin确认session68356 exit0；2026-10-18 03:13:45开始，03:17:39导出完成；本审查不把summary/seal本身当账户通过。1641个实际交易日2020-01-02—2026-10-14与已接受A0完全一致，无run_failure，barfailures0。
- 规则/参数：C_TS与收益前Stage028/0242合同一致，周许可→更早FI2准备→新native信号→下一真实日突破；unknown回退、同原生q/S、AI/成本/0.5R/retry once/roll/holding均不变。此次策略参数新增/修改/删除0；031仅实际TradeData身份导出与raw持久化。
- 调研与判断：沿冻结CMT Elder、LEAN FI、Backtrader与实际827 producer源合同，不新增网络alpha研究；经典框架不构成优势证据。金融结果现已反证固定C组合形状，不能救扫周/FI阈值、月份、品种或手数。独立B_TS尚是另一信号假说，不能把C失败外推为完整框架已被反证。

## 独立经济结果与原七门

| 指标 | C_TS独立重建 | A0已接受权威输出 |
| --- | ---: | ---: |
| 期末权益 | 660,825.00 | 2,262,595.00 |
| 总收益 | 340.550000% | 1408.396667% |
| 最大回撤 | -32.758963% | -48.789850% |
| Sharpe | 0.991077 | 1.367364 |
| 总滑点 | 78,550 | 605,450 |
| 成交fill数 | 382 | 816 |
| 日收盘broker10=1.10峰值 | 81.552643% | 63.124228% |

- 原七门使用原 `stage001_compare.evaluate_metrics`，不改口径：更高收益失败、较低回撤通过、Sharpe不低失败、保证金峰不差失败、超100日不增通过、生存通过、非空通过。收益差-1067.846667pp，回撤改善16.030887pp；`fullperiod_screen_pass=false`，不进入此形状的多周期晋升。
- 现金流/盯市独立重建与daily最大差5.82e-10；内部权益1.16e-10；累计净PnL0；逐合约start/end库存0；exchange/broker margin2.91e-11；滑点/佣金0；佣金总额0（冻结rates口径，不自行改费率）。库存单次有效账期遍历506,986行。
- 3742条起点前positions warmup只在date<2020-01-01且start/end/poschange/成交/turnover/fees/slip/各PnL全0后剔除，账期内或末尾缺日未被忽略。
- 母单：188个已闭合contract cycles，retry合母后163个完整episode，59赢，胜率36.196319%；25个retry真实parent串与实际OPEN关联，6个roll目标OPEN均有同日旧合约真实close血缘。末尾1个未完结contract，净盯市1200，其母单不进入胜率。roll保持不同episode，不能把它们强行合为赢单。

## 条件执行、风险与数据边界

- 152个真实条件intent=100实际初始成交+52未触发，未触发真实订单0、末尾pending0；actual order_id连回conditional_pending候选和实际trade，不能把候选当母单；unknown selected58沿原opened路径。
- 同native q冻结，不在fill重过Stage830：100/100条件成交actual R超过u预测，最大50.0倍、最大差28000；77/100 actual margin超过预测，最大1.043616538倍、最大差3528。这是收益前合同选择的风险后果，必须披露，不能描述成fill-time硬额度已获满足。
- 原七门日收盘broker10倍率固定1.10；Stage830准入/强平预算倍率1.65。额外1.65日收盘诊断峰122.328964%，超100%为1日、超90%为3日；不替换原七门，也不声称为完整分钟/tick PIT保证金峰值。
- 487条分钟请求全部complete/0missing，包含52个未触发日的full-session资格。70个条件初始成交日收盘仍有仓的母entry，均有额外精确entry timestamp后缀读取请求；首bar open仅在冻结独立copy视图改成actual fill，普通路径/AM/history/env保持fullD。该持仓因果核验依动态后缀请求+冻结源码/已过因果fixture，金融审查员未再次聚合全分钟OHLC。
- 382实际TradeData身份逐trade一一核对；98 synthetic原producer usage缺signal字段被准确保留raw，normalized来自实际字段并有真实母OPEN、同合约/交易日/时间/signal血缘，冲突0。
- source859仅继承Stage016已独立接受的usage-limited delta与Stage021 gate收据，不把anchor-only扩成full-session，不重新做全库价格资格，也不把全请求complete误称全市场真实价格重新认证。

## 来源、审计消费者修正与置信度

- raw checkpoint `2f193bb7501efe32ca38fe27f9abbfd487be58fbd71cb3ed558dd3b1312a9b58`；seal `672fe49f2faa2ba4117669a1c3af65fdf12e30f9a1f6bf0aecd076b06f53fb72`；runner精确 `3af932bdbde9ae607c507ff8630dde0a0b03f190ca88be94fa43ce5910b0b860`；冻结strategy d4f870...、engine f7d745...，旧030算法3fe153...。本机所有权、manifest/context/SHA/seal先验后才读自生成raw；未载foreign pickle。
- 全raw combined/全部非trade frames/equity/实际身份到CSV逐表序列化SHA一致，raw trade关键经济字段与normalized身份再独立核对；没有仅复述metrics.json。未扫描原1950行情源/原DB/大分钟cache，未重跑A0经济账。
- 原始preflight_used清单2007项到末尾raw2117项，新增110，旧逐项SHA无变化，其他字段JSON投影完全一致；真实原因为preflight持有可变recorder.files引用。第一次审计消费者错误收据已保留 `audit_attempt1_failure.json`；其后索引、CSV日期格式、枚举、零warmup和1.10/1.65语义误设仅修033，解析/只读核验有重试，金融回放0。完整修正清单见 `consumer_contract_resolutions.json`。
- 最终033 SHA `940ab1180392c7ca3a6cceef15b3bb33f3d37d6510c48f86b9e7c109b7205cbf`；P0/P1/P2=0/0/0（限定本次完整账本/实际身份/来源审计，历史028失败缺陷与旧收据不改）。算术/描述性七门置信度高，跨周期与新OOS优势置信度低；既有历史选择偏差、完整分钟PIT峰值、真实费用/撮合差异未由本次消除。
- 收据：`outputs/stage033_independent_account_review/review_receipt.json`；详细账本 `account_checks.json`、cycles/mother/retry/roll link、`independent_equity.csv`、`additional_165_daily_margin.csv` 和 `conditional_holding_suffix_request_links.csv`。
- 开始/结束过拟合判断：本次新增否，复核和消费者格式修正未改交易规则或见结果调参；原历史选择偏差仍在。
- 开始/结束继续价值：对固定C_TS形状否，应停止且不救参；对完成可信审计是，已完成。总体目标继续active，不能因可复算组件成功宣称更高收益且更低回撤目标达成。promotion_allowed=false，production_qualified=false。
