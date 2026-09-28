# Stage001到期安全换月映射资格计划

## Task 1：选择器TDD

- [x] RED：未到期原始合约保持不变。
- [x] RED：到期原始合约按mapping date持仓量、成交量、到期日、代码确定性选择fallback。
- [x] RED：不得用return date存在性选约；最终缺bar必须失败而非再选一次。
- [x] fail-closed覆盖：无合格候选冻结无效审计行，重复leg身份拒绝；catalog/流动性重复与缺失由同一结构校验拒绝。

## Task 2：Stage001 runner

- [x] 复用冻结V2分区与窗口，读取catalog及bars的允许列，发布全量路径/legs/fallback审计/失败表。
- [x] 合成端到端发布和verify-only测试；相关回归`82 passed`且py_compile通过。
- [ ] 冻结实现、测试、合同、输入与runtime SHA，生成一次性authorization receipt。

## Task 3：唯一执行与记录

- [ ] 唯一运行Stage001并执行`--verify-only`，不因结果重跑。
- [ ] 记录中文结果，更新LINE/registry；不产生回测则不拉独立回测reviewer。
- [ ] 通过只允许另立roll-aware标签生成预注册；失败关闭本机制。
