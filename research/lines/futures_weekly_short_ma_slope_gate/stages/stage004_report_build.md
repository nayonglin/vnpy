# Stage004 四版本同源净值/回撤报告与已审图

- 时间：2026-10-30 01:06 Asia/Shanghai；line_id=futures_weekly_short_ma_slope_gate；day。
- 非重要突破；本次只有派生报告和展示，金融回放0、行情下载0、生产访问0。
- 四份冻结账本：original=stage001_A_attempt003；short_only=stage001_C_attempt003；symmetric=stage002_C_attempt001；long_ma5=stage004_C_attempt001。
- 原19、初始各150000、2020-01-02—2026-10-29、各1652交易日；全部同data_identity、同settings、同effective、同自然预热和日期。MA5-only身份硬门为preflight long_ma_slope_periods=[5]、acceptance MA_periods=[5]/SINGLE/completed_week_MA5_current_lt_previous；空头原MA5/10 OR不变。
- NAV=account_equity/150000；DD=100×(权益/cummax(初始150000与之后全部权益)-1)。四条完整曲线6608点，绝不把权益值当净值、不重设单年基数、不截取2015资金路径。

## 会计指标

| role | end_equity | nav_end | total_return_pct | max_dd_pct | sharpe | total_slippage | modeled_fill_count | round_count | round_win_rate_pct | round_average_win | round_average_loss_abs | round_payoff_ratio | round_profit_factor | open_round_net_mtm |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| original | 1304010.0000000005 | 8.693400000000002 | 769.3400000000003 | -55.04291739512648 | 0.9664999046996732 | 81020.0 | 464 | 228 | 47.80701754385965 | 23003.853211009173 | 15427.966101694916 | 1.491048985937425 | 1.377324910738808 | 467090.0 |
| short_only | 1690065.0000000005 | 11.267100000000005 | 1026.7100000000005 | -56.606513171541195 | 1.036320444996668 | 85160.0 | 435 | 214 | 45.794392523364486 | 31141.785714285714 | 18137.19298245614 | 1.717012425484403 | 1.4760282254164168 | 555810.0 |
| symmetric | 348195.0 | 2.3213 | 132.13 | -70.75471698113208 | 0.5223148320555026 | 24380.0 | 330 | 163 | 41.104294478527606 | 10024.179104477613 | 6539.0 | 1.5329834996907192 | 1.081156783992402 | 147780.0 |
| long_ma5 | 346785.0 | 2.3119 | 131.19 | -57.01251303441084 | 0.5194187823005612 | 28880.0 | 367 | 182 | 41.20879120879121 | 9580.666666666666 | 6316.462264150943 | 1.5167773139470335 | 1.0731914957172408 | 147780.0 |

- 最新MA5-only相比之前双向MA5/10：期末少1410、收益少0.94个百分点、DD改善13.74220395个百分点、Sharpe少0.00289605；三项门只有DD通过，仍MIXED_OR_FAIL_NO_RESCUE_TUNING / NO_PROMOTION。
- 新版完整周期182：75赢/106输/1平；已平净49005，期末3未平轮净MTM147780，合计净利润196785。期末权益346785并非全部已平利润。
- 新版配置静态保证金×1.65/权益峰值106.445575%，超过100%有1日；不能视作历史真实券商保证金或可实盘承载证明。
- 年度切片和完整周期/FIFO区分、平均盈利与平均亏损、PF、末仓、滑点、笔数均落CSV。年度为同一资金路径切片，不是年度独立账户回测。

## 产物与验收

- 代码tools/stage004_report.py，5项测试RED→GREEN：NAV以初资标准化、DD含初资高水位、数值失败、同源/参数/日历拒绝、实际MA5-only硬门、输出隔离。
- load_ledger逐日持仓/逐笔/源哈希/完整周期会计复用原冻结纯报告函数；source前后未变，原子写artifacts/stage004_comparison/。
- 待审图artifacts/stage004_nav_drawdown.png保留原字节（SHA 288867674493a49b1dcbd6ae1d7dec45edf079d3edf0c18679507704a5e5e32c）；comparison.json仍保留生成时PENDING字段，不修改已被独审绑定的文档。
- 独立最终审查stages/stage004_independent_final.json已PASS_WITH_LIMITATIONS，P0/P1/P2=0/0/0。通过后另存已审图artifacts/stage004_nav_drawdown_reviewed.png，只修改标题状态；source/report/review/four daily绑定在stages/stage004_reviewed_visual_receipt.json。
- 从同源daily重绘出的待审图SHA与原待审PNG完全相同；已审与待审的两坐标轴xlim/ylim/位置及5/4条line的全部x/y/色/线型/粗细精确相同，标题状态为唯一变化。
- 已审PNG SHA 5a5b4e54f9b7de62aec070bc7d8bd8a1e266f040f619b564665ac05fd9c8c744；两图均目视检查无裁切、重叠，红色加粗显示最新多头MA5版，橙色点线显示之前MA5/10镜像版。图不是晋级证据。
- 四NAV对CSV最大误差约1.8e-15，DD最大约7.1e-15，仅CSV浮点序列化；真实绘图使用原始daily，数据完全复用。

## 边界和反思

零手续费、静态margin、历史PIT/生命周期、无盘口容量和末未平MTM限制继续存在。整体账户差包含资金/整数手/后续机会/风控反馈，不能全部称MA5过滤直接alpha。
本次报告/已审图没有新增调参过拟合；本实验仍是反复使用历史的样本内比较。继续价值在保留负结果及固定规则验真，不在继续扫角度、MA窗口、品种或年份救参。没有修改Stage001/002/003、另一44池、LINE、根索引/总账。
