# Stage074 供需数据2015-2019覆盖审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：day
- 记录时间：2026-05-27 01:20 CST
- 阶段性质：供需外生数据历史覆盖审计
- 是否重要突破：否。本阶段确认长期数据覆盖边界，不改变策略。
- 是否触发A/B：否。不产生候选版本，不合并交易规则。

## 外部调研与判断

- 参考资料：
  - AKShare 官方期货数据文档列出期货基差、注册仓单、仓单日报、会员持仓排名等期货基础数据入口。
  - 本地 AKShare 包也存在 `futures_warehouse_receipt_dce`，但现有 Stage316 供需脚本未接入 DCE 仓单解析。
- 我的判断：
  - 2015-2019 可以继续补齐，但补齐后的用途应是历史覆盖完整性和解释层，不应作为供需强逆风过滤二次救援。
  - DCE 仓单接口存在但当前返回 JSONDecodeError，需要单独处理数据源兼容性，不能直接假设 `jm/lh` 这类 DCE 品种仓单可用。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage374_supply_demand_2015_2019_coverage_audit.py`
- 新增输出：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage374_supply_demand_2015_2019_coverage_audit_samples_stage374_supply_demand_2015_2019_coverage_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage374_supply_demand_2015_2019_coverage_audit_summary_stage374_supply_demand_2015_2019_coverage_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage374_supply_demand_2015_2019_coverage_audit_decision_stage374_supply_demand_2015_2019_coverage_audit_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage374_supply_demand_2015_2019_coverage_audit_report_stage374_supply_demand_2015_2019_coverage_audit_v1.md`
- 修改脚本：无
- 删除脚本：无

## 审计参数

- 区间：`20150101-20191231`
- 抽样规则：每年每季度首个交易日，共 `20` 个样本日。
- 数据源：
  - 基差：`futures_spot_price`
  - SHFE仓单：`futures_shfe_warehouse_receipt`
  - CZCE仓单：`futures_warehouse_receipt_czce`
  - DCE仓单：`futures_warehouse_receipt_dce`
  - GFEX仓单：`futures_gfex_warehouse_receipt`
- 交易逻辑：无。本阶段不生成信号、不回测。

## 结果

| source | sample_days | ok_days | empty_days | error_days | avg_product_count |
| --- | --- | --- | --- | --- | --- |
| basis | 20 | 20 | 0 | 0 | 12.15 |
| shfe_warehouse | 20 | 0 | 20 | 0 | 0.00 |
| czce_warehouse | 20 | 17 | 0 | 3 | 4.60 |
| dce_warehouse | 20 | 0 | 0 | 20 | 0.00 |
| gfex_warehouse | 20 | 0 | 20 | 0 | 0.00 |

## 判定

- `basis_and_czce_backfillable_but_shfe_dce_warehouse_gaps`

## 结论

- 2015-2019 基差可补齐，且覆盖 `AU/CF/CU/FG/FU/HC/JM/MA/OI/RB/RU/SM`，2019 开始增加 `SP`。
- CZCE 仓单可部分补齐，2015 前三季度解析失败，2015 四季度后多数可用。
- SHFE 仓单在当前解析口径下为空；DCE 仓单接口存在但当前全部报 JSONDecodeError。
- 因此 2015-2019 可以补齐为解释层，但不能称为完整供需三组件数据，更不能直接作为策略过滤的强证据。

## 后续规划

- 若继续补齐，Stage075 应只做全量 `2015-2019` raw cache 和 features 构建，先输出覆盖审计，不合并交易。
- 若需要让 `rb/hc/fu/ru/sp/jm` 的供需解释更完整，需要单独研究 SHFE/DCE 仓单历史网页解析或替代数据源。
- 不继续调 `supply_demand_headwind_threshold=-0.35`、`MAX_SIGNAL_AGE_DAYS=7` 或组件权重。

## 过拟合反思

- 运行前判断：不是过拟合。审计维度和抽样规则预先固定，没有根据收益选择日期。
- 运行后判断：不是过拟合。结果保留了 SHFE/DCE 缺口，没有把可用基差误包装成完整供需因子。

## 继续价值反思

- 运行前判断：有价值。长期多周期报告如果从 2015 开始，就需要知道供需数据到底缺在哪里。
- 运行后判断：有价值，但不直接解决回撤30以内目标。它提升长期报告可信度，并明确供需路线不能作为当前主解。
