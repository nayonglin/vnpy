# Stage003 干净候选账户边际标签计划结果

- line_id：`futures_trend_xgboost_pit_curve_account_labels`
- 当前模式：研究隔离/标签值读取前合同审计
- 记录时间：2026-09-02 15:02 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：账户边际标签样本切分、资格路径和运行前硬闸审计
- 是否重要突破：否
- 是否触发A/B：是；未运行策略A/B

## 外部调研与判断

- XGBoost官方Learning to Rank文档要求按查询组学习组内次序；本线后续每月为一个`qid`：<https://xgboost.readthedocs.io/en/stable/tutorials/learning_to_rank.html>。
- scikit-learn时间序列切分要求测试样本晚于训练样本；本阶段机械冻结连续35月开发、12月账户标签封存：<https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html>。
- 我的判断：旧Stage015标签器不是直接可复用组件；只有“历史干净Top10全路径覆写+目标月rank10唯一替换”通过，候选标签才与当前A基线账户状态一致。

## 本次变更

- 新增脚本：`tools/account_label_plan.py`、`tools/stage003_account_label_plan.py`。
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：前35月开发、后12月账户标签封存；哨兵索引`(0,11,23,34)`；固定4项smoke。
- 修改参数：旧单月rank10替换改为目标日前全部干净Top10路径覆写。
- 删除参数：固定rank10..18任务网格；新任务按每月真实候选数量生成。

## 回测/归因参数

- 数据区间：`2022-01-28`至`2025-11-28`。
- 账户规模：后续15万元；本阶段未运行账户。
- 成本口径：后续沿用旧Stage015正式成本、滑点、保证金、整数手和最多4持仓口径；本阶段未计算。
- 样本过滤：47个月374行全部保留，只按连续时间切分。
- 策略/归因口径：内存构造资格表并审计SHA，不写266份完整资格文件。

## 结果

- 决策：`stage003_account_label_plan_pass_smoke_blocked_on_runtime_preflight`。
- 结构门：`20/20`通过；双跑切分、任务和266个资格SHA逐值一致。
- 开发集：35月/266行；账户标签封存集：12月/108行；封存任务创建数和标签读取数均为0。
- 开发任务：266个主任务+4个rank10 A/A哨兵=`270`；job_id全部唯一。
- 固定smoke：`20220128_R10`、`20220128_R10_A2`、`20220228_R10`、`20220228_R11`。
- 每个任务均完整覆写目标日前干净Top10；正式历史、目标月以后正式行和固定`fu.SHFE` rank11逐字段不变。
- rank10任务与A/A哨兵资格SHA精确相同；挑战者只改变目标月rank10一行，允许变化列仅产品、概率和score_type。
- 旧冻结运行时不存在；生产数据库当前SHA=`5845010108e73661557e723556520d7a3ea42dc6bca4bbe5d50ca3bd419d4cad`，不得冒充旧SHA=`ecbe812bd092ec8cedbd00d8b4b3ec2b1fa9311034dc8379fc6981033405eaf3`。
- 磁盘门已恢复通过，运行时观测可用`39,060,123,648`字节；生产HEAD匹配且checkout clean。剩余阻断只有旧运行时缺失和新隔离研究快照尚未冻结。
- 按旧campaign均值估算，270任务双worker理想耗时约`2.6195`小时、输出约`63.13 MiB`；4任务smoke约`2.33`分钟。
- 期末权益：不适用，未回测。
- 总收益：不适用，未回测。
- 最大回撤：不适用，未回测。
- Sharpe：不适用，未回测。
- 总滑点：不适用，未回测。
- 总交易次数：0。
- 胜率：不适用。

## 输出文件

- `full_feature_split.csv`：SHA256=`a87c73e94eb2afae47ffb106ec60d2720ff881fcecda496aa81af5895165c2b1`。
- `development_jobs.csv`：SHA256=`7ee2062e9700d1c1e8800f42ce8dd0ba75470e4953e30c099c37741aed39b8f3`。
- `development_eligibility_audit.csv`：SHA256=`9bb8bbe8749b69f9436ef6bbb1a9665b7c58eb332859f1468b2eb0c2ffc642ed`。
- `runtime_estimate.json`：SHA256=`4ab7b8486bb49f81d02e3b00ccc2196cf4703a0d86440a0e97445bdfdd5c5591`。
- `stage003_summary.json`：SHA256=`b44e21dc5070675b23c03a26973cc76f4ad8c93d79c6add7be4fd480cd945c0a`。
- `artifact_manifest.json`已发布；全线测试：`.py311/bin/python -B -m pytest research/lines/futures_trend_xgboost_pit_curve_account_labels/tests -q`，`15 passed`。

## 结论

- 本阶段结论：账户标签结构适配通过；旧标签器必须按新路径语义分叉，不能直接复用。
- 是否进入下一步：是，但只能先做新隔离研究运行时和固定4任务smoke。
- 下一步：预注册Stage004运行时身份，建立生产数据库的隔离冻结快照，完成SQLite完整性/行数/最大日期审计后运行固定smoke。

## 过拟合反思

- 运行前判断：否，但整个期限结构方向先验风险较高。
- 运行后判断：否。
- 原因：标签值、收益、回撤均未读取；切分、资格路径、哨兵和smoke在结果前固定，374行未删改。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是，但仅授权最小smoke。
- 原因：路径错位风险已排除，运行时身份仍需重新闭合；smoke能低成本验证真实账户标签器的A/A确定性和候选隔离。

## 合入建议

- 是否更新本线`LINE.md`：是。
- 是否更新`research/registry.md`：是。
- 是否追加根目录`memory.md/back_log.md`：否；没有回测数据。
