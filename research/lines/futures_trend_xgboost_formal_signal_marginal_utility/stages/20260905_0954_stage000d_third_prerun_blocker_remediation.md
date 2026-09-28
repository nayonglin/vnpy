# Stage000D 第三轮独立预审阻断整改

- line_id：`futures_trend_xgboost_formal_signal_marginal_utility`
- 记录时间：2026-09-05 09:54 CST
- 阶段性质：Stage001唯一执行前静态整改
- 是否重要突破：否
- 回放/标签/训练/预测：均未运行

## 第三轮独立预审结论

- 第三轮独立只读预审决定：`BLOCK_STAGE001_UNIQUE_RUN`。
- 严重度：P0=0、P1=1、P2=3、P3=0。
- 原始审查记录：`reviews/20260905_0924_stage001_prerun_third_review_blocked.md`及对应JSON。
- 因存在P1/P2，未创建authorization、claim、event、final或failed产物，Stage001唯一执行未被消费。

## 整改

1. worker入口新增父进程签发的一次性capability。capability精确绑定campaign nonce、lease、worker ID、attempt/runtime/output/input manifest/sandbox profile/runner路径及SHA，并要求固定claim/event已耐久存在且处于对应worker阶段；worker在创建output和导入生产模块前原子消费capability，二次消费失败。
2. worker同时核对sandbox profile真实文件SHA、固定`/usr/bin/sandbox-exec`路径和环境声明。独立进程测试证明：缺少capability，或伪造完整capability但不存在固定claim/event时，均在output目录出现前失败。
3. execution-state staging使用完整nonce和lease命名，staging目录创建后立即fsync父目录；受控fsync或rename异常不再删除staging，由reconcile单向恢复为固定不可重放失败状态。
4. failed bundle改用完整nonce和lease绑定的可恢复staging。目录创建、receipt写入、manifest写入及rename前fsync四个位置分别由独立Python进程执行`os._exit(91)`故障注入；reconcile均可补全或保留证据、原子发布failed终态且不允许重放。
5. 成功产物保留A1/A2原始worker `receipt.json`和已消费capability，分别绑定真实文件SHA；portable receipt冻结精确schema，只保留临时路径的相对证明，不发布可能泄露运行内容的worker日志。
6. portable receipt逐项核对原始回执未变字段、数据库来源SHA、空setting、sandbox profile、capability、事件CSV条数及规范SHA；success bundle在原子rename前后各执行一次完整校验，并重新计算artifact manifest。
7. 最终无进程探针发现`platform.platform()`在macOS上可能为processor信息间接启动系统命令；runtime合同改为只读取`os.uname()`、`sys`及已加载库版本，并新增真实`subprocess.run`封锁测试。父进程claim前输入发现现已完整覆盖为无生产导入、无网络、无子进程。

## 静态验证

- 当前线测试：`102 passed`。
- 全部XGBoost及PIT相关套件合并执行：`834 passed`。
- `py_compile`：runner、特征工具及两份测试文件均通过。
- `ruff`：当前`.py311`环境未安装，未宣称执行成功。
- 进程级故障覆盖：无capability、伪造capability无固定账本，以及failed bundle四个耐久发布中断点。
- claim前无进程输入探针：1409项输入，逻辑键SHA `9f694b5f5d82bca86190d80fd805883477d062da4305e2c3ee860e3c4e96753e`，当前文件合同SHA `13b6580afe94b978ec0096e95d916cba6b57a99eac686185e7703bead332a817`；生产模块导入前后均为空，封锁`subprocess.run`后清单仍可完成。
- 生产副本：`git status --short`为空，HEAD仍为`d492ee072aa5a9d71477235d79f17d2a5db59db3`；正式release、策略、执行版本、manifest和15万元口径精确匹配。
- Stage001正式基准回放、标签、训练、预测、联网、CTP、账户、订单和生产写入均为0。

## 结果指标

- 期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率：不适用，未运行回放且未生成任何结果字段。

## 过拟合与继续价值

- 过拟合判断：否。本次只修复一次性执行授权、证据真实性、原子发布和崩溃恢复，没有读取结果、调整特征、样本、阈值或模型参数。
- 是否继续：是，但只进入第四轮独立预审。只有P0/P1/P2全为0且决定精确为`ALLOW_STAGE001_UNIQUE_RUN`，才创建一次性授权并执行唯一回放。
