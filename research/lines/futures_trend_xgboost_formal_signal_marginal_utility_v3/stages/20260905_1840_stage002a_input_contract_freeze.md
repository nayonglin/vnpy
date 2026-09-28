# Stage002A 输入合同冻结

- line_id：`futures_trend_xgboost_formal_signal_marginal_utility_v3`
- 记录时间：2026-09-05 18:40 CST
- 阶段性质：V3 Stage002唯一无标签事件资格执行前冻结
- 是否重要突破：否；尚未执行正式回放
- 是否触发reviewer：否

## 冻结值

- 输入文件数：`1433`
- 逻辑key SHA256：`10484e319e3b5cc1f223658469ab88cd8c5d978c1e8d152bf3776f84d53a8c19`
- file contract SHA256：`077bcb61d7d9800c6ea8b787346e7711d84848dd8fed78104cb943f8720a4c99`
- runtime contract SHA256：`04396eb74da1ed4812b0eabcc94e28cd2a64f90a1839d08ace6630faf2149e1e`
- 数据库SHA256：`a683e8d99c1925ef2af546e62b61f62c9946d21ea4e5be4af42737a80f77eef5`
- 特征工具SHA256：`e131e0a4e689fdb47769cf0d4aae01a82d793f3033b9b14c839cdbc688163d5a`
- 生产HEAD：`d492ee072aa5a9d71477235d79f17d2a5db59db3`
- 正式release：`m0005_20260901T165450+0800_1961d98ccb2b`
- 正式执行版本：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`
- 资金口径：150000元

## 实现与测试状态

- V3 Stage001+Stage002：`26 passed`
- 复用V2安全与事件工具：`29 passed`
- pytest跨线同名测试必须分进程运行；联合收集的同名模块冲突不属于代码失败。
- claim、成功目录和失败目录在冻结时均不存在。
- `execution_authorized=true`仅授权本Stage002预注册合同的一次执行；claim创建即永久消费。

## 运行前判断

- 过拟合风险：低。V2未看到事件结果，本次原样冻结其12项特征和全部资格门，只修复已被Stage001证明等价的metadata I/O隔离。
- 继续价值：有。只有根事件在年度、方向、品种和特征基数上合格，后续标签与XGBoost训练才有统计基础。
- reviewer：保持关闭；本阶段没有候选收益与回撤。

## 回测结果字段

- 期末权益：不适用；尚未执行
- 总收益：不适用；尚未执行
- 最大回撤：不适用；尚未执行
- Sharpe：不适用；尚未执行
- 总滑点：不适用；尚未执行
- 总交易次数：不适用；本阶段只报告根事件数
- 胜率：不适用；无标签
