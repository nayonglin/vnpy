# Stage001 V2换月感知标签路径资格审计

## Task 1：manifest verifier TDD

- [ ] 写RED测试：逻辑key/path manifest通过，key当文件名的旧算法应失败。
- [ ] 实现path目录边界、存在、size和SHA验证。
- [ ] 写RED测试：path越界、缺文件、size/SHA漂移均失败。

## Task 2：V2端到端复验

- [ ] 复用原线冻结core与全部10项测试，不修改研究语义。
- [ ] V2 runner合成发布测试、编译和全相关回归通过。
- [ ] 冻结V2实现、测试、预注册、输入和runtime SHA。

## Task 3：唯一执行与记录

- [ ] 使用用户默认授权生成V2一次性authorization receipt。
- [ ] 唯一运行Stage001 V2并`--verify-only`，不因结果重跑。
- [ ] 记录中文结果并更新LINE/registry；无策略回测则不拉回测reviewer。
