# Stage001 上市后PIT市场上下文覆盖结果

- line_id：`futures_trend_xgboost_pit_market_context_after_listing`
- 完成时间：2026-09-02 13:22 CST
- 决策：`stage001_market_context_coverage_pass_ready_for_feature_preregistration`
- 是否重要突破：否；通过标签前数据可行性门
- 策略回测/CTP/订单：`0/0/0`

## 技术结果

- Stage003条件PIT逻辑回归OOS输入为797行、47个月，每月15至18个已上市品种；排序后Top9/rank10/挑战者分别为423/47/327行。
- 120日完整窗口：Top9 `421/423`、rank10 `45/47`、挑战者 `313/327`。
- 覆盖层活跃月`43/47`，超过预注册36月门；2022/2023/2024/2025分别`11/11/10/11`个月，全部超过每年6月门。
- 8个fold活跃月依次为`6/5/5/6/4/5/6/6`，全部超过每fold 3月门。
- PIT、fallback、跨合约、有效状态非有限收益、空合约违规均为0；双跑逐值一致，输入运行前后身份稳定。
- runner只读取LR OOS的`eval_date/product_vt_symbol/pit_logistic_probability/window_id`四列；未来标签列读取0，原XGBoost sealed holdout文件读取0。

## 四个机械回退月

- `2022-12-30`：rank10 `si.GFEX`仅5个有效收益日。
- `2023-05-31`：Top9 `si.GFEX`仅103个有效收益日。
- `2024-01-31`：rank10 `SH.CZCE`仅90个有效收益日。
- `2024-02-29`：Top9 `SH.CZCE`仅105个有效收益日。
- 另有14个不完整挑战者行，均来自`si/lc/SH`上市后未满120日；它们保留在A横截面，但当月不能进入XGBoost覆盖层。
- 共有1,159个缺失窗口单元，全部留痕；没有补0、缩窗、删A品种或删月份。

## 产物身份

- `ranked_a_panel.csv` SHA256=`1c841acc3a76a1ecd0f5f3572013c3c97cf4092ac456657f1b87ad3031c14df2`
- `coverage_by_eval_product.csv` SHA256=`54eab60914d94dbf90f64b8cf266263eeaa8d17d29007e0c1849e8a0097f57b7`
- `month_activation_audit.csv` SHA256=`0f18589174f65ad3014797fcb2fe932480090c104b1667eec8e66b6a37871f93`
- `fold_activation_audit.csv` SHA256=`fd0207425f5daadc09f18e55f8c68d23c9dda0efef41ee3cc8e7e32ebf61491c`
- `year_activation_audit.csv` SHA256=`8916756ee5bdba0c17da22added5653eb83ed8eda07168325b6081f6d3e36460`
- `missing_window_cells.csv.gz` SHA256=`adce019521859990c8e76a1f26b6ce1f59daeb4574446068fa826bd77928483b`
- `stage001_summary.json` SHA256=`2fbd2140b52df417263971ff796af88d82a3e3a7daa2256dd0fee209bd3f4ec1`
- 新增测试6项通过；Stage001没有训练或回测。

## 版本变更与回测记录

- 新增参数：覆盖窗口120日、最少2个完整挑战者、活跃月总数/逐年/逐fold门`36/6/3`。
- 修改参数：无。
- 删除参数：无。
- 新增/修改/删除回测结果：均无。
- 期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率：均N/A。
- `back_log.md`未追加；无回测结果，不触发独立reviewer。

## 运行后反思

- 是否过拟合：本阶段**否**；门槛、排序、窗口和回退规则均在读取覆盖结果前冻结，且没有读取效果列。路线整体仍有高自适应风险，后续必须继续预注册。
- 是否值得继续：**是**；43个月覆盖跨越四年和全部fold，证明新信息源不是只在末段可用。下一步只授权冻结六项市场组合上下文特征和一个月分组排序模型设计，尚不授权训练。

