# Stage012 全部AI选品关闭的语义纠正（J/H绩效前）

- line_id：futures_weekly_formal_no_half_r；day；2026-10-23T16:02+08:00；重要突破：否；尚无J/H完整绩效。
- 用户要求关闭AI选品。独立源码审查发现旧D/E/F实际仅enable_ai_product_pool_filter=False；enable_selection_pairwise_v2=True及volume_tilt=True，后者predict_proba排序会影响最多4持仓准入，并按rank调整long手数（继承strength0.15）。旧“AI关闭”表述不完整，不能追认为无AI版本；原账本和旧代码数值不改。
- 本次J/H两臂同步显式False：enable_ai_product_pool_filter、enable_selection_pairwise_v2、enable_selection_pairwise_v2_catastrophic_veto、enable_selection_pairwise_v2_catastrophic_hard_filter、enable_selection_pairwise_v2_volume_tilt。其余规则型风险层不关闭，资金/成本/原19/窗口、bar-open模型维持Stage011合同；只比较同口径J/H，不能把旧E335420当此控制。
- 运行时对pairwise模型构造设Forbidden计数，selection_pairwise_runtime必须None、月池status=disabled且eval_dates为空、全部candidate score/rank/enabled/veto/tilt_applied/model_tag为0或空。proof保存ai_selection_acceptance.json并纳输入/输出审查。不能仅凭配置False宣称实际关闭。
- pairwise模型、summary、其日线CSV特征源不加载、不预测；不需要把这批未消费输入当作执行依赖。日K primary模型继续0分钟/0proxy读取，逐实际fill和anchor以SQLiteopen核验。
- TDD先缺API红，再7项纯边界绿；新报告wrapper显式绑定上述proof和完整flags，旧report不改。每个J/H完整账本完成后独立全审，不自动晋级/实盘。
- 外部/源码判断：用户要求全义优先；月池准入与候选排序是两层独立机制，应全部关闭才符合本实验。源码qmt_roll_portfolio_strategy.py 930构造、4236评分、4680排序与4455tilt；Backtesting.py官方next-bar-open文档 https://kernc.github.io/backtesting.py/doc/backtesting/backtesting.html 支持本次已声明的bar开盘模型选择，不据收益选择执行模型。
- 新增/修改参数：四个pairwise开关显式False（两臂相同）；删除alpha：AI打分排序/AI手数倾斜；新增/修改/删除绩效：均无（尚未首跑J/H）。
- 过拟合判断：否，按用户既定“关闭AI选品”修复遗漏，且在J/H收益出现前完成；同历史窗仍非OOS。继续价值：是，执行与AI口径终于符合用户本次研究目标；固定两臂不扫参，保留负结果。
