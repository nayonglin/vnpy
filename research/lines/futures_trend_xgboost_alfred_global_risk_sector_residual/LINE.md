# ALFRED全球风险状态LR-XGBoost板块残差线

- line_id：`futures_trend_xgboost_alfred_global_risk_sector_residual`
- 研究对象：用严格ALFRED历史快照构造美元、人民币与VIX全球风险状态，在正式18品种逻辑回归raw margin之上由固定浅层XGBoost学习板块残差。
- 线上基准：`m0005_20260901T165450+0800_1961d98ccb2b` / `ai_top10_plus_fu_official_live_v1`；正式C9/15w、固定`fu.SHFE`、成本、保证金、整数手、相关性和最多持仓规则均不变。
- 当前状态：Stage002唯一冻结development OOS失败并经独立review `PASS`确认闭线；C相对正式LR的预测质量、选择覆盖、产品贡献和路径回撤代理均未改善，不进入Stage003；未运行真实策略引擎或触碰生产。
- 核心假设：美元强弱、人民币相对压力和全球风险厌恶对不同商品板块的趋势持续性影响具有非线性和阶段性；正式LR保留产品内排序，XGBoost只允许学习预声明的板块级残差。
- 隔离边界：只写本研究线与`research/registry.md`；禁止修改正式发布物、共享映射、数据库、CTP、订单、launchd或旧研究线。

## 冻结阶段

- Stage000：`stages/20260904_1805_stage000_alfred_global_risk_sector_design.md`。
- Stage001：`stages/20260904_1852_stage001_alfred_global_risk_contract_result.md`；231/231快照、总字节与聚合SHA、77月/1,386行/15列/308状态及全部7类硬门通过，离线manifest 241文件复验通过。
- Stage002：`stages/20260904_2239_stage002_alfred_global_risk_development_oos_fail_close.md`；50折/900行/PIT 0，C相对A的logloss与Rank IC均变差，仅改变1个月/1年，贡献代理`-177,480`、回撤代理恶化`-172,560`，8项门失败；独立review见`reviews/20260904_2239_stage002_independent_review.md`。
- Stage003：禁止进入；不得重跑、调参、删月/年或调整门槛救援。

## 过拟合反思

- 当前判断：是，高风险且没有稳定增量。
- 原因：development月份已被观察且只有308个有效月板块状态；B有39/50个月常数分数，C只改变1个月并同时恶化质量、贡献和回撤代理，任何看结果后删日期、改窗口、换序列、改树或调整表达都属于结果后救参。

## 继续价值反思

- 当前判断：本线无继续价值；总体XGBoost目标仅在新增独立信息或真正未见数据时有继续价值。
- 原因：231/231快照与PIT合同虽有效，但当前15特征板块残差没有形成可用排序增量；同口径调参或重跑只会扩大研究自由度，不能穿越周期。
