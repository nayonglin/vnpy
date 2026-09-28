# Stage002 ALFRED全球风险板块残差独立结果复核

- 复核时间：2026-09-04 22:39 CST
- 复核对象：Stage002预注册、单次授权回执、实现、测试、执行marker及冻结结果包。
- 复核方式：独立只读agent；未修改文件，未调用`--authorized-development-oos`。
- 结论：`PASS`；P0/P1/P2均无发现，不存在改变失败结论的审计缺口。

## 完整性与授权链

- 结果manifest登记10个文件，共235,120 bytes；SHA/bytes错配0、缺失0、未登记0。
- 源receipt与结果包receipt SHA256均为`bf2c70c4449d8042fd3d2fdd7b7bd8ff3979605b7b4a84fbc7df4b05e3a6e9ad`。
- receipt与marker的authorization nonce均为`6a379360-9efb-49ea-a891-87808e9cf7e9`；21项绑定在执行前后身份稳定。
- marker状态为`completed`、`rerun_allowed=false`，绑定决策为`stage002_alfred_global_risk_development_oos_fail_close_no_true_engine`。
- 结果存在后，`--preflight-only`按预期被final output和execution marker拒绝；未发现可重复执行路径。

## 合同复算

- 50 folds、900行OOS、每月18品种、正式108特征、状态15特征。
- LR/scaler fit为50/50；B/C各重复拟合100次，XGBoost合计200次；重复预测误差均为0。
- 冻结标签1,386行，缺失/额外键0/0；900行用于OOS。PIT违规0行/0折，sealed holdout行0，固定`fu.SHFE`模型行0。
- 独立效果路径为900个产品月、54,000个日值；和值错配0、末日错配0，最大误差`1.4552e-11 < 1e-8`。
- true engine、CTP、订单API和生产写入计数均为0；静态调用链未发现相关入口。

## 指标与失败门

- B有39/50个月分数横截面为常数；B/C仅35/33折产生split，低于冻结50/50门。
- 加权logloss A/C为`0.7629080498/0.7629164482`，C变差。
- 月均Rank IC A/C为`-0.0226976937/-0.0241047046`，C变差。
- Top10仅改变1个月、1个年份，低于8个月、3年门。
- 唯一变化月为`2026-01-30`：C用`sp.SHFE`替换`lh.DCE`；产品贡献代理减少`177,480`，路径回撤代理恶化`172,560`。
- leave-best return/drawdown为`0/0`，joint-positive比例为0，变化年度return/drawdown均为负。
- 独立复算的8个失败门与summary一致：`finite_nonconstant_predictions`、`xgboost_non_degenerate`、`candidate_quality_increment`、`minimum_action_coverage`、`joint_return_drawdown_effect`、`leave_best_robustness`、`joint_positive_rate`、`yearly_robustness`。

## 验证命令

- `--verify-only`：10个文件，错配0，未登记0。
- Stage002测试：33 passed；本研究线全部测试：67 passed。
- 只读语法编译：`COMPILE_OK 2`。
- 两份receipt `shasum -a 256`完全一致。
- 两次独立内存重建的标签、路径、指标、选择和全部gate与产物一致。

## 最终建议

- 失败结论有效，应关闭本线，不得重跑、调参或进入Stage003。
- `-177,480/-172,560`仅为60交易日产品贡献和路径回撤代理，不是期末权益、总收益或真实组合最大回撤；Sharpe、滑点、交易次数和胜率均不适用。
- 过拟合判断：是，高风险；仅308个有效宏观状态且development月份已被观察。
- 继续价值判断：本线无继续价值；未来只能基于真正新增的独立信息或未见数据另立研究线。
