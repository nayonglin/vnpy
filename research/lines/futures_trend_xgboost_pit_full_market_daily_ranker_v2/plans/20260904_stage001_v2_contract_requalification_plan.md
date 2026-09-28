# Stage001 V2无标签合同复资格执行计划

**目标：** 只读复验V1全部冻结产物，独立重算20/60日流动性失败集合，以volume并集460重新评估同一合同并原子发布receipt。

## 约束

- 使用`.py311/bin/python`。
- 不读取entry/exit close，不计算未来收益或relevance，不训练、不预测、不回测。
- V1 final和源输入只读；V2 final存在即拒绝覆盖。

## Task 1：审计核心

- [x] 写RED测试：V1 manifest/输入漂移、流动性集合并集和420旧值失败。
- [x] 实现V1 bundle复验、流动性覆盖诊断与V2门禁。
- [x] 跑本线测试与V1/源回归。

## Task 2：唯一执行与记录

- [x] 执行一次Stage001 V2并verify-only。
- [x] 记录中文结果，更新LINE和registry；通过只允许Stage002预注册。
