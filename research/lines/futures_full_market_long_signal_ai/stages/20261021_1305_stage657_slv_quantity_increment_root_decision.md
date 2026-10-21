# Stage657：SLV数量条件增量固定实验结案

- line_id：futures_full_market_long_signal_ai；时间：2026-10-21 13:05 CST；day模式；工作区/分支：/Users/mac/Desktop/fian / codex/ai-training-data-expansion。重要突破：否。独立信号实验，不晋级正式版。
- 调研与判断：沿653/655原ETF论文、BIS WP952与作者GitHub，份额不等于纯买盘，采用NAV/AI状态控制；不能证明因果flow/strict PIT。
- 变更：新增656隔离kernel/runner/5fixture与657报告/决定/本地资产角色；旧正式代码、模型、scaler、标签、H、风险/止损和旧结果修改/删除0。
- 参数：P/Q原相邻NAV/Shares对数比；B[Ahat,P,AhatP]，C只加[Q,AhatQ]；原stressR−own Ahat目标；源组总权1、训练scale、Ridge1不罚截距；两个完整纽约weekday假设/CN15点；252源块/2000次/seed20261021，两个原cutoff/era及两family留出。
- 母体：98历史代码/95族；2020—2022、2023—2026-10-16；main161014、留出合161014母体，1933480child；未知/无源/零覆盖保留，不等今天日线。
- 唯一实际：session91284→21ad8a exit0/169.409738秒，12/12fit、0A重训/现金/SQL/网络/重启。累计551→563fit，294完成cash及1旧partial不变。
- 结果：main早期C−B+0.005240169R/95%CI[+0.002386280,+0.008404815]；后期+0.000053267R/CI[-0.002461459,+0.002791018]。held1后期增量−0.002022764R，held0后期C自身−0.003246429R；四项原门全false，关闭本精确包，不进现金。
- 独审：655一次81.747561秒/1083项全过，C/I/M0/0/0；全12方程/scaler/预测/966084选择/未知/统计/共享bootstrap/门/63年度/5985族/4740MSE组一致，0refit/旧大载荷。收据SHA66a3bb1e0999d4909684e3d071f8fa8cea43b36912acc6ca09fc719cae0eed88。
- 期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率：全部N/A（0账户资金回测）；4491个C主样本理论选择不是成交笔数。
- 开始/结束新增结果调参过拟合：否/否；未改合同救分，长期同史选择风险高。继续本包价值否，完整全市场目标是；旧629 false/inconclusive及646关闭保持，正式/PIT/窄损/加注均未通过。
- 下一步建议先核ESR真实发布/修订/MY，再决定是否冻结单项需求数量检验；未启动ESR特征/训练/现金，不混SLV救分，不等今日国内日线。
- [完整报告](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage657_slv_quantity_increment_root_decision/report.md)；[决定](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage657_slv_quantity_increment_root_decision/decision.json)；[资产角色](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage657_slv_quantity_increment_root_decision/asset_declarations.json)；[独审](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage655_slv_method_clock_pre_review/actual_review1/review_receipt.json)。
- root统一更新本线LINE/registry各一次，例行负结果不写根memory.md/back_log.md；无Git提交/推送或生产操作。
