# Stage000B 独立预审阻断整改

- line_id：`futures_trend_xgboost_formal_signal_marginal_utility`
- 记录时间：2026-09-05 08:36 CST
- 阶段性质：Stage001唯一执行前静态整改
- 是否重要突破：否
- 回放/标签/训练/预测：均未运行

## 独立预审结论

- 首轮独立只读预审决定：`BLOCK_STAGE001_UNIQUE_RUN`。
- 严重度：P0=0、P1=3、P2=3、P3=0。
- 原始审查记录：`reviews/20260905_0811_stage001_prerun_independent_review_blocked.md`及对应JSON。
- 因存在P1/P2，未创建authorization、claim、event、final或failed产物，Stage001唯一执行未被消费。

## 整改

1. eligibility合同冻结为唯一`2019-12-31`静态18边界及56个明确动态月份；每个动态月恰为10个模型排名行加rank11固定`fu.SHFE`。
2. 事件先硬校验`2020-01-02 <= decision_date <= 2026-08-28`及`ai_eval_date < decision_date`，再排除静态期和固定`fu`。
3. A1/A2新增macOS deny-default sandbox：读输入、仅写自身worker目录、完全禁止网络，限制继承到原生库及后代进程。
4. Python敏感操作guard实际拦截`connect_ex`、DNS连接入口、敏感模型/CTP导入、fit/predict、账户/订单调用、子进程、标签/holdout数据读取和worker外写入；任何尝试均记账并fail-close。
5. 输入清单固定为1409个逻辑键，纳入`/usr/bin/sandbox-exec`并移除未消费的生产setting；合同摘要包含规范化path/size/mtime/SHA，运行前后逐项比较。
6. worker receipt硬校验PID、解释器、版本、cwd、sys.path、模块路径、HOME/TMP/MPL、DB、空setting、source contract、sandbox、敏感guard、网络尝试及恰好一次正式基准回放。
7. claim与event改为同一状态目录原子发布；中断状态只允许恢复为技术失败。成功final先原子发布，再清理attempt，清理失败不破坏终态。

## 静态验证

- 当前线测试：`72 passed`；其中包含状态目录fsync/rename、final rename、final已发布但event未更新、attempt清理失败等故障注入。
- OS sandbox反例实际覆盖：直接`connect_ex`、后代Python进程`connect_ex`和worker外文件写入均被内核拒绝。
- 真实active eligibility无回放校验：634行、57快照、静态18行、动态616行/56月，首月`2022-01-28`、末月`2026-08-31`。
- 真实输入清单无回放校验：1409项，逻辑键SHA `9f694b5f5d82bca86190d80fd805883477d062da4305e2c3ee860e3c4e96753e`，生产HEAD与正式release匹配，网络连接尝试0。

## 结果指标

- 期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率：不适用，未运行回放且未生成任何结果字段。

## 过拟合与继续价值

- 过拟合判断：否。本次仅把运行前合同从字段自报升级为可执行边界，没有观察任何收益或回撤结果，也未改变样本覆盖门和12项特征。
- 是否继续：是，但仅允许重新独立预审。只有P0/P1/P2全为0且决定精确为`ALLOW_STAGE001_UNIQUE_RUN`，才可创建一次性授权。
