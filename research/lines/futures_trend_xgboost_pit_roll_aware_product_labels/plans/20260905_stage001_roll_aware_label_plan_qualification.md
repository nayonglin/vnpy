# Stage001 换月感知标签计划资格审计

**目标：** 不读取价格值，用冻结PIT映射和bar身份为56,272行建立精确20段可执行产品持有路径。

## Task 1：纯函数与测试

- [x] 写RED测试：第一段query映射、后续T-1映射、换月衔接、20段和禁止fallback。
- [x] 实现输入manifest复验、标签分区和逐段bar身份索引。
- [x] 写RED测试：缺映射、缺起止bar、未来映射、重复键和截止外隔离。

## Task 2：单次runner与产物

- [x] 实现只读runner、完整失败明细、摘要、报告和manifest。
- [x] 增加close列禁止访问、收益/模型/回测/生产零副作用审计。
- [x] 跑测试、编译和小样本runtime smoke。

## Task 3：唯一资格执行

- [x] 冻结直接输入identity并运行唯一Stage001；入口在source manifest预检失败。
- [ ] `--verify-only`复验final bundle；final不存在，因此本线不可执行此项且不得重跑补齐。
- [x] 记录中文结果并更新LINE/registry；无策略回测数据，不触发独立回测reviewer。
