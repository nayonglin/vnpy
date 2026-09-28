# CFFEX宏观状态LR-XGBoost残差线

- line_id：`futures_trend_xgboost_cffex_macro_state_residual`
- 研究对象：以中金所股指/国债期货构造跨资产宏观状态，在正式18品种逻辑回归raw margin之上由固定浅层XGBoost学习板块状态残差。
- 线上基准：`m0005_20260901T165450+0800_1961d98ccb2b` / `ai_top10_plus_fu_official_live_v1`；固定`fu.SHFE`仍是发布层卫星，不进入模型。
- 结构动机：前一正式108特征base-margin残差线只改变5个月且跨年不稳；本线不调旧模型参数，只引入此前XGBoost未使用的独立CFFEX跨资产信息。
- 当前状态：Stage001唯一冻结无标签合同失败并闭线；官方源、PIT、日期和面板门通过，但离散breadth只有4个唯一值，违反预注册的每特征至少20值；未读标签、未训练、未回测。
- 隔离边界：只写本线和`research/registry.md`；不修改前序闭线、正式材料、生产数据库、CTP、订单、邮件或launchd。

## 冻结研究臂

- A：正式`StandardScaler + LogisticRegression(C=0.20)`，18品种中选择Top10。
- B：仅用39项CFFEX宏观/板块特征的固定浅层XGBoost，作为信息量诊断，不具备单独晋级资格。
- C：使用与B相同的39项特征，并以A的raw log-odds作为训练和预测`base_margin`；C是唯一真实晋级候选。
- 固定`fu.SHFE`在模型排名后追加，A/B/C均不训练或打分fixed-fu。

## 阶段

- Stage000：`stages/20260904_1710_stage000_cffex_macro_state_residual_design.md`。
- Stage001：`stages/20260904_1750_stage001_cffex_macro_contract_fail_close.md`；决策`stage001_cffex_macro_contract_fail_close_no_labels`，本线关闭。

## 最终证据

- 官方源84月/1,695日文件/26,066,955字节/847,781原始行/35,595核心行，聚合SHA精确匹配，重复0。
- 六根各1,694个PIT日，future/stale/fallback/换月非零收益均0；77/77正式月末和50/50 OOS均完整。
- 面板77月/1,386行/39特征，非有限、one-hot和交互误差均0。
- 唯一失败：`cffex_equity_breadth_60d`按三个股指正动量占比定义最多只有4种值，低于预注册20值门。
- manifest文件97，离线验证通过；标签、fit/predict、回测、holdout、CTP、订单和生产写入全部0。

## 过拟合反思

- 当前判断：Stage001本身否，但结果后降门或改breadth会构成研究者自由度。
- 原因：失败由离散定义的数学上限触发，与收益标签无关；必须按预注册闭线。

## 继续价值反思

- 当前判断：本线无继续价值；总目标仅可凭不同独立机制继续。
- 原因：同一CFFEX形状已无法通过自身冻结表达门，禁止降门、改特征、删月、换窗口或进入Stage002救援。
