# Stage006 2015独立起点A/C净值报告

- 时间：2026-10-30 12:53 Asia/Shanghai；line_id=futures_weekly_short_ma_slope_gate；day；非重要突破。
- 只做纯会计报告/图表，新增金融回放0、下载0、数据修改0、生产访问0；金融回放由root此前独立执行。
- 来源：stage006_A_attempt001与stage006_C_attempt001，两组各150000/0仓，实际2015-01-05—2026-10-29各2871日，2014真实自然历史只预热，不继承旧资金/持仓。
- Stage005类原字节复用，20%/同epoch缓存全部日线high-low/含信号日close/无MA门保持；唯一金融实验变化为起点。A也有range诊断但enabledFalse/applied0，不将would_block误当已作用；C enabledTrue。
- 同data_identity/SQLite、settings、effective、成本/保证金和日历完全相同。

## 纯loader窄适配

旧stage001_report是2020窗口且candidate强制空头斜率True。本线stage006_report仅AST替换1条gate身份检查；将2020-01-01→2015-01-01、首实际2020-01-02→2015-01-05共2个窗口常量替换，并更新对应错误消息名。原arm A/C校验及其余全部逐日/逐笔/库存/成本/保证金/末仓会计保持。没有伪造preflight、切换角色、复制结果或修改旧源码。AST替换次数、日期计数、原SHA、保留检查和修改后AST SHA均进comparison.json。

## 全期指标

| role | end_equity | nav_end | total_return_pct | max_dd_pct | sharpe | total_slippage | modeled_fill_count | round_count | round_win_rate_pct | round_average_win | round_average_loss_abs | round_payoff_ratio | round_profit_factor | open_round_count | open_round_net_mtm |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| original | 3661109.999999998 | 24.40739999999999 | 2340.739999999999 | -56.31217255222158 | 0.890090476503845 | 255980.0 | 725 | 356 | 44.38202247191011 | 46183.86075949367 | 25890.913705583756 | 1.7837864389287057 | 1.4306510525418046 | 4 | 1314570.0 |
| price_range | 3180474.9999999963 | 21.203166666666643 | 2020.3166666666643 | -53.107122522571416 | 0.8653563191218632 | 221670.0 | 618 | 304 | 42.76315789473684 | 62816.92307692308 | 29858.866279069767 | 2.103794648122859 | 1.5900773503254166 | 0 | 0.0 |

- C 304完整合约轮：130赢/172亏/2平；胜率42.76316%，不是FIFO分段胜率44.58599%。
- C相对A期末少480635，收益少320.4233333个百分点，最大DD改善3.20505003个百分点，Sharpe低0.024734157。三项门仅DD通过，MIXED_OR_FAIL_NO_RESCUE_TUNING / NO_PROMOTION。
- A净利润3511110=已平2196540+末4轮净MTM1314570；C净利润3030475=已平3030475+末MTM0。会计桥：已平差+833935与末MTM差−1314570合计−480635。两条独立路径的已平差包含资金/手数/后续机会反馈，不能当固定底仓上的直接过滤alpha，也不能因为A含浮盈就否认其统一盯市权益。
- A静态margin×1.65峰110.00765%、3天>100%；C峰98.46771%、0天>100%。仍非历史真实券商保证金、成交容量或可上线资格。

## 年度与独立起点边界

年度CSV为同一资金路径自然切片，不是每年新账户。2015 C−13.64%(A−8.1833%)、2018 C−28.3893%(A−27.6592%)；2024 C+95.9534%(A+73.4119%)，2025 C+0.7350%(A+37.7615%)，2026截至29 C+52.1598%(A+87.2169%)。不能按失败年份删样本或换门救参。

2019末A311920、C330325；逐原positions核实：A持FG005多11/OI005多5/cu2002多2，C持FG005多11/OI005多6/cu2002多2，均有继承仓位；2020独立Stage005原A/C均从150000、0仓起跑。所以2015账户的2020后子曲线不是2020独立回测，不能拼接、截段或用同一名义本金比较。原Stage005 2020窗改善不被覆盖，但本次2015更长窗没有同向整体通过。

## 文件和验收

- artifacts/stage006_comparison含summary、annual、两daily/完整轮/末仓及nav_drawdown、comparison、delivery。
- artifacts/stage006_nav_drawdown.png当前PENDING，NAV=account_equity/150000、DD含起始150000高水位，两条合5742真实点。
- 3059来源绑定生成前后不变，纯会计重算全持仓/逐日/逐笔/成本/库存/末仓，原metrics一致。图目视无裁切/图例重叠。
- 6报告测试RED→GREEN：A诊断可存在但无作用、C固定20%和daily/epoch、AST仅gate与两date、独立初资NAV/DD、2015窗口不能2020拼接、输出隔离；diffcheck通过。
- 先前stage006_data_preflight已明确245个2014日历交易日、hc1505只有13有效完整预热周且须等21-ready；573零成交+18结构坏mapping只分类不造bar。数据历史真值/PIT/生命周期、零费、静态margin/无盘口容量局限继承。
- 独立审查及final JSON由root负责；只有root明确锁定最终审查SHA后才另存已审图和receipt，不修改PENDING原图/comparison。

## 反思

本次派生报告没有新增调参过拟合；更长固定窗口属于反证，不是新OOS。2015与2020起点综合结论不同，应保留负结果，不扫20%附近阈值/年/品种/窗口救参。继续价值在固定规则稳健性与路径归因，不支持凭2020一窗直接晋级。没有改旧阶段、LINE、44品种线、根索引总账或正式资产。


## 2026-10-30 13:00 已锁定最终独审后的已审图

- root明确锁定最终审查JSON SHA `cd22fb6b9f4282376f37ec61174b4d62518bca5a622654e148c9720003e1be98`（7351bytes）；执行前/后精确重验相同，PASS_WITH_LIMITATIONS，P0/P1/P2/failures=0。独审45测试、47825报告复核项另见final证据，本报告自身6测试保持通过。
- 已另存artifacts/stage006_nav_drawdown_reviewed.png，SHA `6b2d6e96b1b5916cc7c6710ed06af60aa51db74c67015f43d0ae3f929401a9ef`；stages/stage006_reviewed_visual_receipt.json绑定锁定final、两原daily/派生CSV、原pending图/comparison及report/visual脚本。
- 按同源daily重绘pending PNG与原pending图SHA完全相同；已审与待审两axes的xlim/ylim/位置、3/2条line的全部x/y/颜色/线型/线宽精确一致。唯一变化为标题审查状态，原待审图与comparison字节不改。
- 每臂2871真实点；NAV/DD CSV舍入误差约3.6e-15/7.1e-15，绘图数组直接来自原daily。已审图目视无裁切/图例重叠。策略三门失败、NO_PROMOTION不因会计/图审核通过改变。
- 至此本子任务全部Stage006文件稳定，0额外金融回放/0下载/0生产；未提交，交由root锁定最终交付manifest和提交。
