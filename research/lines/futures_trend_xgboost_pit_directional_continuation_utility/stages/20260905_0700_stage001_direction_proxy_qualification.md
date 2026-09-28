# Stage001 方向代理无标签资格审计

- line_id：`futures_trend_xgboost_pit_directional_continuation_utility`
- 当前模式：冻结结果只读复验；禁止重跑、未来标签、模型和回测。
- 记录时间：2026-09-05 07:00 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：首次且唯一的全市场query-date方向代理资格审计，不是标签实验、模型实验、回测或上线。
- 是否重要突破：否；结果为fail-close，证伪当前方向代理标签机制。
- 是否触发A/B：否；逻辑回归主体、正式AI池、C9/15w、CTP和生产均未修改。

## 外部调研与判断

- 参考资料：Stage000已冻结XGBoost LTR官方文档、Time Series Momentum、realized semivariance与Return Signal Momentum证据。
- 我的判断：以query-date正式延续条件定义事前方向在经济上优于用未来路径符号定义方向，但它无法覆盖全部正式动作日；必须接受证伪，不能针对已知失败日救援。

## 本次变更

- 新增脚本：`tools/directional_continuation_proxy.py`、`tools/stage001_direction_proxy_qualification.py`。
- 修改脚本：无正式策略、引擎、AI池或生产脚本改动。
- 删除脚本：无。
- 新增参数：无策略参数；仅冻结AM41、方向覆盖、成本来源和一次性执行硬门。
- 修改参数：无。
- 删除参数：无。
- 新增测试：方向oracle独立性、严格future OHLC canary、生产/fixture入口隔离、授权绑定、并发event/claim、相同lease重放、异常保留与输入漂移。

## 回测/归因参数

- 数据区间：面板共1,067个qid；development 1,046个qid，inference-only 21个qid。
- 账户规模：不适用；未运行账户级回测。
- 成本口径：只生成`research_code_defined_cost_proxy`元数据，17个正式显式产品、46个研究fallback产品；未计算未来净收益。
- 样本过滤：基础57,528行中仅按预注册排除固定`fu.SHFE` 1,067行，模型层56,461行、63个产品；未事后删日期或品种。
- 策略/归因口径：当前Stage847 C9/15w最终继承链，精确41根真实bar；手工公式与正式`_generate_signal + _rollover_reopen_allowed`逐行比对。

## 结果

- 决策：`stage001_direction_proxy_qualification_fail_close_no_future_labels`。
- 硬门：13项中12项通过，唯一失败为`formal_action_direction_coverage`。
- 唯一失败日：`2022-07-29`；50/50行可观测，long/short/neutral=`0/0/50`，active direction为0，技术错误与公式不一致均为0。
- 全局方向：long `6,850`、short `6,763`、neutral `42,833`；可观测`56,446`、不可观测`15`。
- 非退化：1,043个development qid有非零方向；2022至2026每年long和short计数均大于0。
- 因果与身份：33项直接输入before/after一致，drift为0；1,551项实际源审计通过；future OHLC字段访问/数值解析、post-query bar、平填bar、公式不一致与技术错误均为0。
- 禁止操作：未来close/return/label、标签生成、逻辑回归/XGBoost fit/predict、策略回测、true engine、holdout、CTP、订单API和生产写入计数均为0。
- 期末权益：不适用；未运行回测。
- 总收益：不适用；未运行回测。
- 最大回撤：不适用；未运行回测。
- Sharpe：不适用；未运行回测。
- 总滑点：不适用；未运行回测。
- 总交易次数：0；未运行回测或交易。
- 胜率：不适用；未运行回测。
- 新增/修改/删除的回测结果：均无。

## 验证与评审

- 本线测试：`24 passed`。
- 全部`futures_trend_xgboost_pit_*`测试：`395 passed`。
- `py_compile`、动态runtime身份、27项冻结输入SHA、尾随空白与`git diff --check`通过；`ruff`未安装，未运行。
- 唯一执行：event=`completed`、claim=`claimed`，均为`0600`且绑定同一nonce/lease/授权摘要。
- `--verify-only`：9个artifact，0错误。
- 独立预审：PASS，P0-P3为0，置信度0.98，允许唯一执行。
- 独立post-review：冻结结果PASS、进入未来标签BLOCK；P0/P1为0，仅台账同步P2，置信度0.99。

## 输出文件

- report：`artifacts/stage001_direction_proxy_qualification/report.md`
- summary：`artifacts/stage001_direction_proxy_qualification/summary.json`
- audit：`artifacts/stage001_direction_proxy_qualification/direction_proxy_audit.csv.gz`
- qid：`artifacts/stage001_direction_proxy_qualification/qid_direction_diagnostics.csv.gz`
- source：`artifacts/stage001_direction_proxy_qualification/source_contract_audit.csv.gz`
- identities：`artifacts/stage001_direction_proxy_qualification/input_identities.json`
- authorization：`stages/20260905_stage001_execution_authorization.json`
- event/claim：`artifacts/stage001_execution_event.json`、`artifacts/stage001_execution_claim.json`

## 结论

- 本阶段结论：当前`counterfactual_rollover_continuation_direction_proxy`未通过正式动作日全覆盖硬门，本线按预注册fail-close。
- 是否进入下一步：本线否；禁止读取未来收益、生成标签、训练或回测，禁止删除`2022-07-29`、降低门槛、补造方向、修改AM41/公式或重跑。
- 下一步：XGBoost总研究目标只能另立研究线，重新定义独立经济对象并事前冻结；候选可研究真实PIT持仓/事件状态驱动的日级资格，或事前定义且允许弃权的效用建模，但不得围绕已知失败日调参，并须使用新的独立时间段验证。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否；接受失败并闭线。
- 原因：方向、样本和门槛在首次分布读取前冻结，结果失败后没有改规则；若在同线删月、降门或补方向则会成为明显事后过拟合。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：本线否，XGBoost总目标仍有条件价值。
- 原因：本线已完成证伪职责，继续救援只会制造选择偏差；更换第一性原理经济对象并重新预注册仍可能改善收益/回撤，但必须从新研究线开始。

## 合入建议

- 是否更新本线`LINE.md`：是，标记Stage001已完成并闭线。
- 是否更新`research/registry.md`：是，标记fail-close且禁止未来标签。
- 是否追加根目录`memory.md/back_log.md`：是；当前机制属于正式证伪的路线废弃，只追加简短摘要，不覆盖其他并行修改。
