# Stage002 ALFRED全球风险板块残差development OOS失败闭线

- line_id：`futures_trend_xgboost_alfred_global_risk_sector_residual`
- 当前模式：冻结单次development OOS A/B/C；A为正式LR，B为15特征standalone诊断，C为LR base-margin上的板块残差候选。
- 记录时间：2026-09-04 22:39 CST；唯一执行完成于22:28 CST，独立复核完成于22:39 CST。
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：本线首次且唯一标签访问、模型拟合及未来60交易日产品贡献路径代理评估；不是真实策略引擎回测。
- 是否重要突破：否；结果失败并关闭当前全球风险板块残差模型形状。
- 是否触发A/B：是；属于研究A/B/C，未修改正式版本、CTP或订单链路。

## 外部调研与判断

- 参考资料：ALFRED历史快照说明`https://alfred.stlouisfed.org/help/downloaddata`；FRED的`DEXCHUS/DTWEXBGS/VIXCLS`官方序列页；NBER `w13901`；BIS Working Paper 1083。
- 调研结论：美元、人民币与VIX有独立PIT经济机制，但文献也提示美元与商品关系会发生结构变化，因此预注册没有固定方向，而是只允许浅层树学习板块残差。
- 本阶段判断：数据机制与PIT合同成立不等于存在可交易增量；唯一冻结实验已经证明当前15特征、标签和树形状不足以改善正式LR。

## 本次变更

- 新增脚本：`tools/stage002_alfred_global_risk_development_oos.py`。
- 新增测试：`tests/test_stage002_alfred_global_risk_development_oos.py`。
- 新增预注册：`stages/20260904_2124_stage002_alfred_global_risk_development_oos_preregistration.md`。
- 新增授权：`stages/20260904_stage002_execution_authorization.json`，绑定21项规范绝对路径和SHA，只允许一次运行。
- 新增结果：`artifacts/stage002_alfred_global_risk_development_oos/`及一次性execution marker。
- 修改脚本：无；授权后未修改预注册、实现、测试或任何绑定输入。
- 删除脚本：无。
- 新增参数：B/C固定`n_estimators=32`、`max_depth=1`、`learning_rate=0.03`、`min_child_weight=20`、`gamma=0.1`、`subsample=0.8`、`colsample_bytree=0.8`、`reg_alpha=1.0`、`reg_lambda=20.0`、`max_delta_step=1.0`、`tree_method=hist`、`random_state=42`、`n_jobs=1`。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：训练月从`2020-01-23`扩展；development OOS测试月为`2022-04-29..2026-05-29`，未来效果路径最晚到`2026-08-24`。
- 账户规模：不适用；无资金、保证金、整数手、相关性或账户持仓模拟。
- 成本口径：消费冻结正式`net_pnl`产品贡献路径；不等于完整组合执行成本。
- 样本过滤：50折、每折18品种、900行OOS预测；标签只为Stage001冻结的1,386个键构造；固定`fu.SHFE`模型行0。
- 策略/归因口径：A/C按稳定分数选Top10；仅汇总Top10 membership变化月份的未来60交易日贡献和从0起点路径最大回撤。B只诊断信息量，不参与晋级。

## 结果

- 期末权益：不适用；未运行真实策略引擎。
- 总收益：不适用；`-177,480`是changed month的产品贡献代理差额，不是收益率。
- 最大回撤：不适用；`-172,560`是changed month的路径回撤代理变化，负数表示C更深，不是真实组合最大回撤。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。
- 折/预测/特征：`50/900/108+15`；LR/scaler/B-XGB/C-XGB fit为`50/50/100/100`，XGBoost合计200。
- 标签：生成1,386行、缺失键0、额外键0；development OOS使用900行。
- PIT违规行/折：`0/0`；sealed holdout行0；固定fu模型行0。
- join缺失/重复/修改：`0/0/0`；非有限输出0。
- 重复预测最大误差B/C：`0/0`。
- B/C split nodes：`1,012/870`；有split折：`35/50`与`33/50`，均未达到冻结50折门。
- B常数分数月份：`39/50`；A/C常数月份均为0。
- C correction绝对值中位数/最大值：`0.00564538/0.04240207`。
- 加权logloss A/B/C：`0.76290805/0.69021696/0.76291645`。B虽较低但严重常数化且仅为诊断；C相对A变差。
- 月均Spearman Rank IC A/B/C：`-0.02269769/-0.01654702/-0.02410470`。B的常数月按预注册记0；C相对A变差。
- Top10变更：`1`个月、`1`个年份，低于`8`个月、`3`年门。
- 唯一变化月`2026-01-30`：C用`sp.SHFE`替换`lh.DCE`；A/C贡献代理为`-21,590/-199,070`，return delta `-177,480`；A/C路径最大回撤为`-184,120/-356,680`，drawdown improvement `-172,560`。
- leave-best return/drawdown：`0/0`；joint-positive比例0；最小年度return/drawdown为`-177,480/-172,560`。
- 路径审计：900个产品月、54,000个日值；缺失0、和值错配0、末日错配0，最大和值误差`1.4552e-11`。
- true engine、CTP、订单API、生产写入计数：均为0。
- 失败门：`finite_nonconstant_predictions`、`xgboost_non_degenerate`、`candidate_quality_increment`、`minimum_action_coverage`、`joint_return_drawdown_effect`、`leave_best_robustness`、`joint_positive_rate`、`yearly_robustness`。

## 输出文件

- report：`artifacts/stage002_alfred_global_risk_development_oos/report.md`。
- summary：`artifacts/stage002_alfred_global_risk_development_oos/summary.json`，SHA256 `ed262ae89707d92df64734886c1c806e58a25b3f40ba6220d0914b75e4a4ef33`。
- predictions：`artifacts/stage002_alfred_global_risk_development_oos/oos_predictions.csv`。
- monthly/yearly：`artifacts/stage002_alfred_global_risk_development_oos/monthly_effects.csv`、`yearly_effects.csv`。
- manifest：`artifacts/stage002_alfred_global_risk_development_oos/artifact_manifest.json`，SHA256 `2f818c652bd8279c9dbc73ce2941e80ebcbb6ec2671cb13f55e82c256725d056`；10文件、错配0、未登记0。
- execution marker：`artifacts/stage002_alfred_global_risk_development_oos_execution.json`，`completed`且`rerun_allowed=false`。
- orders：不适用。
- daily：不适用；未发布真实组合daily。
- quality：授权前preflight为标签读0、fit 0、输出写0；执行后`--verify-only`通过；Stage002测试33项、本线67项、联合回归126项通过。
- review：`reviews/20260904_2239_stage002_independent_review.md`。

## 独立复核

- 结论：`PASS`；P0/P1/P2均无发现。
- receipt、marker、21项输入身份、10文件manifest、训练计数、PIT、900条路径、A/B/C指标和8个失败门均独立复算一致。
- reviewer明确要求：认可失败闭线，不得重跑、调参或进入Stage003。

## 结论

- 本阶段结论：`stage002_alfred_global_risk_development_oos_fail_close_no_true_engine`。
- 是否进入下一步：否；本线不预注册、不执行Stage003。
- 下一步：禁止改树、特征、板块、窗口、LR、权重、TopN、标签、fold、日期、品种、门槛或删除失败月/年救援；不得运行真实C9、holdout、shadow或正式接入。若继续总目标，只能以新的独立PIT经济信息或真正未见数据另立研究线。

## 过拟合反思

- 运行前判断：是，高风险。
- 运行后判断：是，高风险且没有稳定增量。
- 原因：development月份已被观察且只有308个有效month-sector状态；B大面积常数化，C只改变1个月且质量、贡献和回撤代理全部变差，任何同口径调参或重跑都属于结果后救参。

## 继续价值反思

- 运行前判断：有，限唯一冻结Stage002，用于证伪独立全球风险机制。
- 运行后判断：本线无继续价值；总体XGBoost目标仍只在新增独立信息或真正未见数据时有继续价值。
- 原因：当前C既没有更好的预测质量，也没有足够选择覆盖，更没有收益/回撤代理改善；继续同一形状只会扩大研究者自由度。

## 合入建议

- 是否更新本线`LINE.md`：是，标记Stage002失败闭线。
- 是否更新`research/registry.md`：是，登记冻结失败结论与禁止项。
- 是否追加根目录`memory.md/back_log.md`：否；不是重要突破、正式候选或跨线合并。
