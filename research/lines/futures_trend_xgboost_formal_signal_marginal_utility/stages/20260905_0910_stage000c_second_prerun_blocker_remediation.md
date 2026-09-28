# Stage000C 第二轮独立预审阻断整改

- line_id：`futures_trend_xgboost_formal_signal_marginal_utility`
- 记录时间：2026-09-05 09:10 CST
- 阶段性质：Stage001唯一执行前静态整改
- 是否重要突破：否
- 回放/标签/训练/预测：均未运行

## 第二轮独立预审结论

- 第二轮独立只读预审决定：`BLOCK_STAGE001_UNIQUE_RUN`。
- 严重度：P0=0、P1=2、P2=2、P3=0。
- 原始审查记录：`reviews/20260905_0849_stage001_prerun_second_review_blocked.md`及对应JSON。
- 因存在P1/P2，未创建authorization、claim、event、final或failed产物，Stage001唯一执行未被消费。

## 整改

1. 父进程输入发现改为纯文件合同：正式身份、生产HEAD和1409项输入均直接读取固定路径及Git元数据，不导入生产模块、不启动子进程；生产模块只允许在execution state耐久发布后的worker内导入。
2. worker移除Git子进程；macOS sandbox改为允许初始`process-exec`但禁止`process-fork`，Python guard同时拦截`subprocess.Popen`、`subprocess._fork_exec`、`os.system`、`os.popen`、`posix_spawn*`、`spawn*`、`fork*`和`exec*`。
3. 成功worker receipt冻结固定schema，逐项校验完成状态、时区时间顺序、正式身份、事件数、事件表规范SHA，以及DB、空setting、sandbox profile、事件CSV的真实path/size/mtime/SHA。
4. 最终产物在清理attempt前复制A1/A2事件CSV、空setting、sandbox profile和worker日志；数据库只保留已核验SHA、来源逻辑键和明确标注的临时相对路径。最终receipt不再引用会被删除的worker绝对路径。
5. execution-state staging名称写入完整campaign nonce与lease。claim-only、空目录、event-only、截断event及完整pre-rename staging均可先原子恢复为固定状态，再单向发布技术失败；任何恢复路径都不允许重放。

## 静态验证

- 当前线测试：`92 passed`。
- 回执校验覆盖：固定字段、status、时区时间顺序、正式身份、事件数/SHA、四类真实文件身份漂移及发布后相对证据可读。
- 进程级故障注入：独立Python子进程写入claim后以`os._exit(91)`退出，恢复后固定claim/event为0600、发布failed bundle且不运行策略。
- staging故障覆盖：empty、claim-only、event-only、truncated-event、完整pre-rename；既有非零敏感计数在恢复中保留。
- Stage001正式基准回放、标签、训练、预测、CTP、账户、订单和生产写入均为0。

## 结果指标

- 期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率：不适用，未运行回放且未生成任何结果字段。

## 过拟合与继续价值

- 过拟合判断：否。本次只修复运行隔离、证据真实性和崩溃恢复，没有读取结果、调整特征、样本、阈值或模型参数。
- 是否继续：是，但只进入第三轮独立预审。只有P0/P1/P2全为0且决定精确为`ALLOW_STAGE001_UNIQUE_RUN`，才创建一次性授权并执行唯一回放。
