# Stage030：C_TS 独立账户经济复核准备

- line_id：futures_trend_triple_screen；记录时间：2026-10-18 02:50 CST。
- 阶段性质：仅准备独立复核工具，不是回测、归因或策略研究；不是重要突破；不修改 LINE、registry、正式实现或配置。
- 外部资料：本阶段不新增网络调研，沿 Stage028 收益前冻结合同和 02:42 持仓因果补充；不重新研究或优化假说。独立判断：条件入场必须用真实 OPEN 订单证明母单，不能将 conditional_pending 当成原 opened，也不能把未触发候选计入胜率。
- 新增脚本：`tools/stage030_independent_ordered_account_review.py`。新增审计 CLI：`--self-test` 和必须显式给定的 `--completion-evidence`；策略参数新增/修改/删除均无。
- 工具边界：只接受 `outputs/stage028_ordered_account/C_TS`，只写 `outputs/stage030_independent_account_review`；不导入引擎、不启动回放/训练/网络、不读数据库、不重复原 1950 raw-source 或全分钟库资格、不重新经济审查 A0。
- 审计设计：独立填单现金流、日收盘估值、费用/滑点、单次流读 positions 对齐逐合约 start/end 库存与保证金、真实母订单/retry/roll 关联、未完结母单剔除、条件订单时间/手数/S 与实际风险、全日分钟申请以及实际后缀读取证据、参数/来源/小型收据身份、原七门 `stage001_compare.evaluate_metrics`。
- A0：仅允许按已接受独立收据和产物 SHA 复用，实际原始权威指标待本次复核时读取；不使用任务导航数字替代权威输出。
- actual R/保证金：允许超过 u 收盘预测，按合同披露，不改判成重新执行原 Stage830 入场 gate。保证金只证明日收盘库存估值，不声称完整分钟 PIT 峰值。
- 验证：`.py311/bin/python ... --self-test` 通过 3 个有限非金融 fixture（conditional_pending 实际母订单；retry 费用合并；尚未完结 retry 母单排除及错单拒绝）；`py_compile` 通过。未访问 C_TS 金融输出。
- 当前权益/收益/DD/Sharpe/滑点/成交/胜率：全部 N/A，未启动或计算 C_TS；独立复核金融 engine runs=0，模型训练=0，promotion_allowed=false，production_qualified=false。
- 等待条件：root 明确交付完整 summary 与实际终态 exit=0 证据后，才运行；不轮询输出目录。
- 开始/结束过拟合判断：否，本次只验证既定执行证据，不新增或选择 alpha 参数；既有历史研究选择偏差仍须在正式结果置信度中披露。
- 开始/结束继续价值：是，防止经济账/母单血缘错误进入原七门，但准备组件本身不是金融进展或收益结论。
