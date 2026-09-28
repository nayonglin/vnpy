# Stage003 运行前独立审查

- 审查时间：2026-09-05 04:52 CST
- reviewer：独立 agent `01a06e09-bf46-7b01-962f-4e183604ef16`
- 审查范围：Stage003 预注册、实施计划、runner 与测试
- 数据边界：reviewer 未读取 Stage002 `predictive_monthly.csv`、`effect_monthly.csv` 或任何效果数值
- 最终结论：**PASS，可进入一次性授权**

## 初审阻断与修复

1. 初审发现授权未显式绑定 publisher 实现。已改为绑定 `publisher.__file__` 对应的 `stage001_daily_ranker_contract.py`，并增加测试。
2. 初审发现 access event 在标签开放前未要求 `opened_labels_sha256`。已增加 64 位小写 hex 完整性硬门及缺失字段拒绝测试。
3. 初审发现逐 qid 标签重放中途失败可能低报访问。已在每个 qid 开放前原子持久化保守 qid/row 计数，失败汇总读取该状态，并增加异常注入测试。
4. 二审进一步确认原进度覆盖写不具备崩溃级持久性。已改为临时文件写入、文件 `fsync`、`os.replace` 和目录 `fsync`，并增加调用链测试。

## 最终复审

- publisher 源码已纳入授权 SHA，且不再与 feature contract 混淆。
- 36 个 access event 的状态、行数、seal SHA 与 opened-label SHA 格式均在标签开放前验证。
- 74 个冻结模型只执行 `load_model` 与 `predict`，runner 无任何训练调用。
- 37 折 primary/repeat 预测 bit 一致、原预测/选择 seal 与 lossless hex 回读 seal 均为硬门。
- 每个效果 qid 开放前先写 durable 保守访问状态；handled exception 或进程中断后的失败证据不会低报。
- Stage003 不解析或消费 Stage002 的 lossy 预测/效果 CSV；正常发布采用目录级原子替换。
- 旧 P1 全部关闭，未发现新的 P0/P1。

## reviewer 反思

- 是否过拟合：**否**。本阶段没有新拟合、调参或门槛修改，只恢复冻结证据。
- 是否值得继续：**是**。技术证据链已经满足一次性运行条件；效果门仍须按预注册结果机械执行。
