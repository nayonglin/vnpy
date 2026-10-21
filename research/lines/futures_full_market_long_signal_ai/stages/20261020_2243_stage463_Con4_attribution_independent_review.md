# Stage463 Con4既有现金归因桥独立复核

- line_id：`futures_full_market_long_signal_ai`；时间：2026-10-20T22:43+08:00；非实现者只读审查。
- 阶段性质：纯既有会计归因，不是新backtest或重要突破，不触发新参数/模型/分配规则；不改461/462、LINE、registry、Git或生产。
- 起始边界：已读registry及460 next_scope；沿用accepted461的完整83=34新增/41移除/8换月与同母q常数不能直接改变月排序结论，不重复流1,933,480 scores。

## 调研与判断

本阶段不做新alpha研究或资料扩展，复用冻结453/460的外部资料边界和已独审459/461的来源资格。没有本轮新网络/GitHub访问。判断仅来自封存本地材料：可以确认新派生会计桥真实闭合，不能把changed/unchanged路径分类写成q的独立因果效应，也不能因UR单赢家新增分配规则。

## 实际审查

- 一次执行`outputs/stage463_Con4_attribution_review/review.py`，无作者kernel导入，不运行462实现。
- 结果：`status=completed`、`core_blockers=0`、`core_problems_remaining=0`；153,350项核对。
- 从原八本账户一次读取16个closed/open表的必要字段和8个summary，逐根核全部6,332根。20个末端open；末端open中无已部分退出者。所有根均按累计realized gross－全部entry fees－全部exit fees＋open剩余unrealized计净贡献，关闭根另与net_pnl核对。该公式保留任何已发生partial exit的累计损益/费用，不以“最后一笔”代替全部费用。
- 新派生覆盖：3,274配对event_id根、36个classification×membership单元、22年度切片、83改变母行、332个83×四账暴露行、333 unchanged admission行。跨账户以event_id配对，核mother/epoch/family/product/entry_date，不用带账户前缀root_id跨账匹配。
- 除UR定位外，不重读fills、daily、全部reservations/拒绝路径，不做native/price/SQL/API/fit/cash。UR只新增一次读取C2020stress reservations/rejections相应表并筛目标行，Aclosed直接复用本轮根读取。
- 当前最大比较绝对差`9.3132257461547852e-10`元，为本轮Decimal累计与binaryfloat余额的普通尾差。462原math.fsum根到权益残差仍为4.656612873077393e-10元；两者度量不同，不作bug或修复循环。

## 终值桥及分类闭合

| 账户对 | Δgross | Δfees | Δunrealized | Δequity | 改变选择母行贡献 | 选择不变路径贡献 |
|---|---:|---:|---:|---:|---:|---:|
| primary_2020_base | -3010.0000 | 150.6025 | 9000.0000 | 5839.3975 | 29768.2665 | -23928.8690 |
| primary_2020_stress | -8070.0000 | -496.7115 | 6690.0000 | -883.2885 | 13516.6570 | -14399.9455 |
| cold_2023_base | 52770.0000 | 167.3510 | 6760.0000 | 59362.6490 | 14780.0570 | 44582.5920 |
| cold_2023_stress | -1820.0000 | 326.4495 | 6690.0000 | 4543.5505 | 6627.5605 | -2084.0100 |

四对均满足`Δequity=Δgross−Δfees+Δunrealized`；全部原根到summary、原根到派生root bridge、root到mother、classification/membership、changed与unchanged及年度到终值加法闭合。显示到0.0001元的金额表加法残差为零；这只是本批数据的观察显示量纲，不是交易所货币或手续费精度规则。

## UR2309限定个案

- primary_2020/stress，u=2023-07-17，`CZCE.UR.202309`，两侧相同动作，属于unchanged account path transmission。
- A原closed：2023-07-18入场5手，2023-08-01退出；gross29,900.0000－fees129.1500=净29,770.8500元。
- C原reservations与rejections均确认：joint_scale=0.06374168138376071，target_qty_prefloor=0.3675025037304832，round_lot=1，qty_cap=D_qty=0，D_state=`risk_margin_or_one_lot_rejected`。原预算行显示u_equity=993,367.0545、existing_risk=4,896.538555963025、existing_buffered_margin=241,938.4000元。
- 结论仅是这条已发生预算路径未入资，不是“更高权益必然入资”，也不是原A反事实重新插入C后仍获同收益的证明。不设置单赢家/单合约新规则。

## 年度与限制

- cold2023/stress：2023–25差额−4,154.5150元，2026部分年度+8,698.0655元，总差+4,543.5505元。22个年度行对既有459/460已接受年度结果核对，不重读daily。
- 年度仍为连续账户切片；2026部分年、起点高度重叠。stale、capacity unknown和first-seen PIT等限制保留。原`unsupported`、不晋级/不加注裁决不变。
- “identical funded path”逐笔签名沿用462及原现金接受证据，本轮独立核实际root的金额、数量、状态一致；其他333行准入字符串只作派生桥一致性，原始预算新定位仅UR一例。本轮不声称重新独立验证所有逐笔路径或内核。
- sourcebindings、检查覆盖和限制均保存在精简receipt；不需另第三轮review或额外价格工程。

## 变更、反思与TODO

新增审查脚本/receipt和本stage；新增/修改/删除策略参数均0，新增/修改/删除backtest结果均0。期末权益、收益、DD、Sharpe、滑点、交易次数与胜率均沿用459已独审原账，本阶段不重造新成绩。

开始与结束过拟合判断：本次机械会计复核本身否；事后叙事与长期同史择题风险是，因此只保留路径关联，不救当前Con4包。开始时继续价值是，必要闭合一次；结束时本归因任务已完成，继续扩展本赢家规则/小数格式/重复审查的价值否。保留原向前四账户，等真实21日事实仍有价值。

TODO仅由root合入审查摘要和研究状态，不由本agent修改LINE/registry/根账或重启实验。

输出：`outputs/stage463_Con4_attribution_review/review_receipt.json`。本轮root/path源绑定均在receipt，不重复整个459。
