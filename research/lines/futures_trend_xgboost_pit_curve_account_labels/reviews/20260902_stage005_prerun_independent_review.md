# Stage005 首轮预运行独立复核

- 复核时间：2026-09-02 17:24 CST
- reviewer agent：`01a0615c-3878-7ef2-84e1-0aceee57614e`
- 模式：独立只读复核
- 未修改文件、未创建campaign、未运行worker或策略回测、未连接CTP或订单API
- **结构化决策：`BLOCK_STAGE005_BATCH`**
- **严重度：`P0=0/P1=5/P2=2/P3=0`**
- **置信度：99%**

## P1

1. 冻结运行身份已失效。生产数据库从Stage004的SHA256 `584501...`、`112,267,264`字节更新为`db3342...`、`112,271,360`字节，Stage004 runtime gate当前失败。
2. Stage004 smoke完整身份没有被Stage005静态绑定；其主力映射SHA256从`89c8ae...`更新为`093d3b...`，若直接运行会用未经smoke的新映射生成标签。本项与数据库漂移合并计为一个“冻结运行身份失效”P1。
3. validator恢复留痕可绕过：`run_batch`在aggregate之前就把attempt写成complete，`--validate-only`不新建attempt；aggregate失败后旧attempt gate仍可能通过。
4. 显式零计数存在假阴性：隐藏holdout `label.json`、`ranker.json`、`send_order`命令以及普通CTP/fit日志均可未被当前有限规则计数。
5. 金额量化顺序未完全落实：target CSV先用浮点`sum()`聚合再量化总和，反例中逐行量化误差为0而现实现为`-1e-6`。
6. review授权用字符串包含判断；BLOCK文档若在说明中出现放行关键词和零严重度文本，可能误通过。该项与授权门完整性合并计入P1总数。

## P2

- 同campaign恢复时，旧`_validate_completed_job`不校验新增的5个原始predecision文件；损坏后仍会跳过worker，直到aggregate才失败。
- 最终decision的holdout/order/CTP字段仍直接写`0/false`，没有从`execution_scope_audit`机械回填。

## 必须修复

- 重建并重新smoke当前数据库与主力映射，或恢复并完整绑定Stage004原身份；未完成前不得创建Stage005完整批次。
- attempt生命周期必须覆盖aggregate，`validate-only`也必须写start/end。
- scope audit改为精确允许文件树、精确worker命令、holdout日期路径扫描、模型文件名/后缀扫描和受控API事件计数，并补全负向测试。
- 所有金额序列必须逐元素按`1e-6`量化后再求和。
- review/run authorization必须使用结构化decision和严重度精确校验。
- 同campaign恢复时必须在跳过rank10 worker前复核5个原始predecision文件。
- 最终decision的零计数从机械audit回填。

## 验证

- 首轮专项测试：`10 passed`；四文件`py_compile`通过，但测试未覆盖上述反例。
- Stage005 artifact root、campaign、run authorization均不存在；Stage005回测任务数为0。
- 当前修复前SHA仅用于阻断记录，不得生成授权：runner `3058d930b727af9559790484b7954365932aaa8e36aac4ab4bf9cb0515e53244`；core `14e4aca182f5787db61ea6e687e5aa73fd88d1bc12de71793083a9ca92c88e43`；core test `a80d04e6b8c9387ebd3c473962f7db895bc3250031936b98e4bc63cdfa46744e`；runner test `9f063249d6d4df8f2a80e163978c8ccf41b2175493116c4285a802fbda5cd2d2`；prereg `ec96369d156b40f0b0400a68bdc7f45934e628a2aba4001af85a2102ed2a68cd`。

## 最终判断

- 过拟合：否；只审计合同和门禁，未读取新标签或选择样本。
- 继续价值：是，但必须修复后重新独立预运行评审。
- 当前唯一合法动作是修复和固定4任务re-smoke；不得启动270任务、训练模型或读取sealed holdout。
