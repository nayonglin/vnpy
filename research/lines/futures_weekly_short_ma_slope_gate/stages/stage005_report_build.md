# Stage005 无MA斜率门＋空头缓存价格区间底20%门：纯会计报告

- 时间：2026-10-30 12:33 Asia/Shanghai；line_id=futures_weekly_short_ma_slope_gate；day。
- 非重要突破；本工作只派生报告/图形，金融回放0、行情下载0、行情修改0、生产访问0。
- 原A：outputs/stage001_A_attempt003；新C：outputs/stage005_C_attempt001。
- 两组各150000/0持仓独立起点，原19品种、2020-01-02—2026-10-29、1652实际交易日；严格同data_identity、SQLite、settings/effective/成本/保证金/暖机/日历。

## 新合同和loader适配

- 两侧MA斜率门真实关闭，short/long证书enabled=False、decision/applied=0、MA_periods=[]，没有用另一个角色绕过旧loader验证。
- 新C的真实arm仍C，price_range=True、threshold=.2，history_scope=all_available_same_physical_epoch_daily_through_signal，signal_day_close对同epoch全部缓存有效日线累计min(low)/max(high)，包括信号日；<=底20%阈值拒开short_case1a，flat range拒绝，换月不加门。
- 原stage001_report.load_ledger硬编码candidate必须short-slope=True。因此本线新stage005_report采用窄AST adapter：只替换原函数中唯一slope_arm_flag_mismatch那条if为真实新证书校验；保留原armC检查、其余所有数据/逐日/逐笔/完整周期/风险会计代码。旧源码与preflight/旧输出全部未改。
- comparison.json保存原loader SHA、替换次数1、变更后AST SHA及保留检查标签；实际source仍绑定原文件和新adapter源码。
- 额外硬门：证书signal_day_close、includes_signal_day=True、range_fields low/high、rollover=False、flat reject、listing_start_completeness_proven=False；不把accepted-week子集、周close或主连当缓存日线。

## 结果

| role | end_equity | nav_end | total_return_pct | max_dd_pct | sharpe | total_slippage | modeled_fill_count | round_count | round_win_rate_pct | round_average_win | round_average_loss_abs | round_payoff_ratio | round_profit_factor | open_round_count | open_round_net_mtm |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| original | 1304010.0000000005 | 8.693400000000002 | 769.3400000000003 | -55.04291739512648 | 0.9664999046996732 | 81020.0 | 464 | 228 | 47.80701754385965 | 23003.853211009173 | 15427.966101694916 | 1.491048985937425 | 1.377324910738808 | 4 | 467090.0 |
| price_range | 2435919.9999999986 | 16.239466666666658 | 1523.9466666666658 | -44.45432460924966 | 1.1616606116703656 | 148790.0 | 414 | 201 | 45.77114427860697 | 60456.086956521736 | 30333.703703703704 | 1.9930334767903772 | 1.6977692580066177 | 0 | 0.0 |

- 新C完整201轮：92赢/108亏/1平，净已平2285920，期末0仓/0未平MTM。
- 相比原A：权益+1131910，收益+754.6066667个百分点，最大DD改善10.58859279个百分点，Sharpe+0.195160707；三门全通过，仅PASS_FIXED_WINDOW_ONLY / NO_PROMOTION。
- 完整周期胜率45.7711%低于原A47.8070%，均盈/均亏比升为1.9930，PF升为1.6978；不混用FIFO胜率。
- 新C配置静态交易所margin×1.65峰97.8840%，0天>100%；这不证明历史真实券商资金容量。
- 自然年2025新C-0.2162%、年度DD-41.6242%，原A+34.4696%、DD-40.3520%；全期改善不等于各年普胜。年度仍同一资金路径切片，非每年新账户。

## 图表/文件与验证

- artifacts/stage005_comparison：summary、annual、两条daily、完整轮、末仓、nav_drawdown、comparison、delivery_manifest。
- artifacts/stage005_nav_drawdown.png：生成时PENDING，原图保留。蓝色原始无MA/无区间门，红色新C，NAV=权益/150000，DD高水位显式包括初始150000，两组均完整1652点。
- loader纯会计重算全部实际持仓行/真实fills/日盈亏/成本/闭合库存/末仓，核对原metrics与source，共3056绑定生成前后零变化。
- 6测试RED→GREEN涵盖实际关闭MA门、全部日线/信号日/close/无换月合同、AST只改1条并保留arm与会计、NAV/DD定义、同源/日历/参数和输出隔离；git diff --check通过。
- 待审图目视无标题/图例/轴裁切重叠。独立审查及最终review JSON由root负责；明确通过且最终JSON定稿后才另存reviewed图/收据，避免绑定半成品审查。

## 边界与反思

“全部历史”只指同物理epoch的全部已有缓存，不是上市首日起完整真值；旧基准65候选中7个缓存首日晚于已知上市日。原PIT/生命周期/报价容量、静态保证金和零手续费限制继续。整体权益差包含动态仓位、整数手、保证金及后续机会反馈，不能全部说成过滤直接alpha。
本次派生报告没有新调参过拟合，但历史反复开发与规则选择偏差仍在；固定窗口改善有进一步固定起点/OOS/成本压力验证价值，禁止据收益继续扫20%附近阈值或挑品种年份。没有修改其他stage、LINE、44池、根索引总账或正式策略。


## 2026-10-30 12:39 最终独审锁定后的已审图

- root明确锁定final JSON SHA `22127736d09f768254006a9d530628cc96178e6c669c75b4e9cd7667ff62657a`；生成前精确核对通过，status=PASS_WITH_LIMITATIONS、P0/P1/P2/failures=0。未在审查补字段过程中提前绑定。
- 已另存artifacts/stage005_nav_drawdown_reviewed.png（SHA `4b797e39e36d1aed16f564d8622f4457155d6a6e435978566108d2be883a15f6`），stages/stage005_reviewed_visual_receipt.json绑定锁定final、两份原daily/派生CSV、原待审图/comparison及report/visual源码。
- 同源重绘待审PNG的SHA与原待审图完全一致；已审对待审两axes的xlim/ylim/位置与3/2条line全部x/y/颜色/线型/线宽精确相同，唯一改动标题审查状态。
- 原待审图与comparison字节保持；NAV/DD CSV舍入误差上限约3.6e-15/7.1e-15，图使用原daily数组。目视已审图无裁切重叠，NO_PROMOTION保持。
- 0额外金融回放/0下载/0生产；没有修改旧阶段、LINE、另一44池或任何正式资产。
