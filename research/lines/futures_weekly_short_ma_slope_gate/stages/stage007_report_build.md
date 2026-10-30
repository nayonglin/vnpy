# Stage007 多头prior顶部20%门＋严格新高豁免：三臂纯会计报告

- 时间：2026-10-30 13:16 Asia/Shanghai；line_id=futures_weekly_short_ma_slope_gate；day；非重要突破。
- 本子任务只派生报告/图，金融回放0、下载0、数据修改0、生产访问0。
- original=Stage006 A001（无价格门），short_only=Stage006 C001（仅空头底20%），long_top20=Stage007 C001。两个旧已审控制只读复用，不重跑。
- 三臂各150000/0持仓独立2015起点，2014只自然预热；实际2015-01-05—2026-10-29各2871交易日，同data_identity/SQLite、settings/effective/成本/保证金/日历。两MA斜率门真实OFF、无加仓。

## 固定新增合同

多头新信号long_case1a及long_case2，先取同physical epoch严格date<signal_date的全部缓存有效日线prior L/H。P为信号日close，prior L+0.8(H-L)<=P<=H则拒开；P>H才严格新高豁免，等于H仍拦。豁免只免本价格门，不覆盖信号/尺寸/资金/原风险。flat时等H拦、超H豁免、低于H允许。

空头Stage005/006既有底20%类/参数/历史包含signalday的规则不变；本轮没有把空头也改成prior-only。新增long proof硬验证所有preflight字段、prior history_scope、includes_signal_day=False、.8位置阈值/.2顶部占比、strict>突破规则、无换月门、两种long signal、非完整上市史声明。旧Stage006纯会计窄AST loader原字节复用，未改arm、preflight或任何旧代码。

## 结果

| role | end_equity | nav_end | total_return_pct | max_dd_pct | sharpe | total_slippage | modeled_fill_count | round_count | round_win_rate_pct | round_average_win | round_average_loss_abs | round_payoff_ratio | round_profit_factor | open_round_count | open_round_net_mtm |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| original | 3661109.999999998 | 24.40739999999999 | 2340.739999999999 | -56.31217255222158 | 0.890090476503845 | 255980.0 | 725 | 356 | 44.38202247191011 | 46183.86075949367 | 25890.913705583756 | 1.7837864389287057 | 1.4306510525418046 | 4 | 1314570.0 |
| short_only | 3180474.9999999963 | 21.203166666666643 | 2020.3166666666643 | -53.107122522571416 | 0.8653563191218632 | 221670.0 | 618 | 304 | 42.76315789473684 | 62816.92307692308 | 29858.866279069767 | 2.103794648122859 | 1.5900773503254166 | 0 | 0.0 |
| long_top20 | 917065.0 | 6.113766666666667 | 511.37666666666667 | -54.80371774489421 | 0.661910242726575 | 62690.0 | 403 | 200 | 44.5 | 21784.26966292135 | 10749.8623853211 | 2.0264696311524593 | 1.654640341032742 | 0 | 0.0 |

- 最新C200个完整轮：89赢/109亏/2平，完整周期胜率44.5%；FIFO203段胜率45.3202%，不能混称。
- 最新C对short_only：权益少2263410，收益少1508.94个百分点，DD恶化1.69659522个百分点，Sharpe低0.203446076；三项门全失败，MIXED_OR_FAIL_NO_RESCUE_TUNING / NO_PROMOTION。
- 对original：权益少2744045，收益少1829.3633333个百分点，DD好1.50845481个百分点，Sharpe低0.228180234。
- 最新C已平净767065，期末0仓/0MTM；short_only已平3030475，期末也0仓；两者差额−2263410均在已平净账本中。但两条资金路径仍有动态仓位/整数手/后续机会反馈，不能把差额说成99笔固定反事实交易的直接亏盈。
- 完整周期PF1.65464略高于short_only1.59008，胜率也略高，但权益/DD/Sharpe全退步；不能以PF或胜率单项替代整体判断。平均盈亏比2.02647与PF1.65464分别为均赢/均亏和总赢/总亏。
- C静态margin×1.65峰94.561617%，0天>100%；不构成历史真实券商保证金或可实盘承载证明。

## 门控计数与年度

最新C多头303条诊断，106 would_block、99次正计划手数实际归零，13条strict breakout_exempt诊断。后者不是13笔成交；独审按实际fills/anchor另核实11笔新高开多（case1a7/case2 4）。would/diag不与真实开仓笔数混用。空头仍100诊断/56would/55applied，规则合同原样；不据同计数断言全路径完全一致。

年度CSV是同一账户路径切片，非逐年独立新账户。新C2017−14.9409%、2018−12.9466%、2023−0.9312%，2020/2021/2022仅+1.2924%/+10.8500%/+1.5943%；2024/2025/2026截至29分别+77.5039%/+27.8987%/+40.6261%。不通过挑年份或顶部阈值救参。

## 文件与验证

- artifacts/stage007_comparison：summary/annual/三daily/完整轮/末仓/nav_drawdown/comparison/delivery。
- artifacts/stage007_nav_drawdown.png：生成时PENDING，三条各2871真实点共8613点；NAV=权益/150000，DD含独立初资150000高水位。原始灰虚线、仅空头蓝线、最新多空价格门红色加粗。
- 纯会计重建全持仓/逐日/真实fills/闭合库存/成本/末仓，与原metrics核对；3129源绑定生成前后零变化，未伪造参数或替换scope。
- 4项有效测试RED→GREEN：prior/不含当日/strict突破/两long信号/flat合同错误拒绝，preflight .8/开关硬门，NAV/DD独立初资，三臂选择/输出隔离。冗余只镜像常量测试未保留。
- 待审图目视无标题图例轴裁切重叠。独审及final由root负责；只有root明确锁定最终review SHA后才另存reviewed图与receipt，不修改原PENDING图/comparison。

## 边界与反思

缓存同epoch历史不等于上市完整史，PIT/生命周期和缺口、零手续费、静态保证金/无盘口容量局限均继承。严格prior范围避免信号日高点把突破条件变成自我引用，但这个因果正确性不证明本门有盈利价值。
本次报告没有新调参过拟合；实验仍反复使用历史，当前负结果应冻结保留。继续价值在核对结构性错杀/后续固定OOS，不能在本样本继续扫80%/新高豁免/品种年份救参。没有改旧阶段、LINE、另一44池、根总账或正式资产。


## 2026-10-30 13:17 最终独审锁定后的已审图与稳定状态

- root明确锁定final JSON SHA `5fe51f23fe684e52f7d834757099b2aa815e39bea40e94a10980bce9689a698a`（12494bytes），执行前后精确复验未变；PASS_WITH_LIMITATIONS、P0/P1/P2/failures=0。独审core349012项、report65642项、52tests和8613曲线点见final；本报告自身4项行为测试通过。
- 已另存artifacts/stage007_nav_drawdown_reviewed.png，SHA `6d80352d566d3da03e5da3c6996a0037313dca055ceb25dc2e8537d57e91e046`；stages/stage007_reviewed_visual_receipt.json绑定最终锁定审查、三份原daily/派生CSV、原pending/comparison和report/visual源码。
- 同源重绘pending PNG的SHA与原pending图完全一致；reviewed只改标题。两axes的xlim/ylim/位置、4/3条line的所有x/y/颜色/线型/线宽精确相同；三条各2871点未改变，CSV浮点序列化误差仅约3.6e-15/7.1e-15。
- 原pending图/comparison不改；已审图目视无裁切/图例重叠，策略三门全失败与NO_PROMOTION保持，不将审计通过当策略成功。
- 本子任务全部Stage007文件至此稳定，不再写入，交root锁最终交付manifest/提交。0额外金融回放/0下载/0生产访问，未改其他stage/LINE/44池或正式资产。
