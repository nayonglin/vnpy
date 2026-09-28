# PIT换月标签可成交性资格线

- line_id：`futures_trend_xgboost_pit_roll_label_tradeability`
- 创建时间：2026-09-05 01:19 CST
- 上游：已通过并封存的`futures_trend_xgboost_pit_expiry_safe_roll_mapping`。
- 研究问题：全量产品级路径虽然到期安全，是否同时具备非陈旧价格观测和最小1手执行容量。
- 当前状态：Stage001唯一全量资格执行已失败闭线；价格质量与最小1手容量门均失败，不生成标签值、不训练XGBoost、不进入真实引擎。
- 隔离边界：只写本线与registry；不修改上游路径、vendor映射、正式逻辑回归、CTP、订单或生产文件。

## 当前阶段

- Stage000：`stages/20260905_0119_stage000_roll_label_tradeability_preregistration.md`。
- Stage001计划：`plans/20260905_stage001_roll_label_tradeability_qualification.md`。
- Stage001结果：`stages/20260905_0134_stage001_roll_label_tradeability_fail_close.md`。
- 冻结结果：`54,423/56,272=96.714174%`路径合格，`1,849`失败；价格失败`777`路径，容量失败`1,830`路径；离线验证产物`9/9`、输入`6/6`、错误`0`。

## 过拟合反思

- 当前判断：否。
- 原因：100手日成交量与100手持仓量门由既有1%容量原则和最小1手订单直接推出，未读取close、收益、标签或模型效果。
- 边界：不得看到全量失败分布后改阈值、改为均值/分位数或只审计已知6个fallback。

## 继续价值反思

- 当前判断：本线无，XGBoost总目标仍有。
- 原因：唯一执行已证明全量路径不能直接形成可交易标签；后续只能另立PIT候选宇宙资格线，用query date当时可见信息事前排除低流动性候选，不能在本线按失败结果救门。
