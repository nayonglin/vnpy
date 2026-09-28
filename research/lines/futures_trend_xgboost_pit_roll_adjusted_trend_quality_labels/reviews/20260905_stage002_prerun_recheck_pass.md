# Stage002 首次拟合前修复复审

- 复审时间：2026-09-05 CST
- 独立 reviewer：`01a06e09-bf46-7b01-962f-4e183604ef16`
- 复审方式：只读，未修改文件，未读取 Stage002 结果。
- 最终结论：`PASS`，允许冻结实现并执行预注册的唯一一次首次拟合。

## 阻断项关闭证据

1. 固定 `fu.SHFE` 在训练、预测、指标和 selector 前排除，并按剩余 AI universe 重算 relevance。
2. 授权绑定 V1 特征合同、V2 固定 ranker 实现、XGBoost sklearn 源码及原生库。
3. 标签开放前写入 durable access event；失败包对 `opening` 状态按 expected rows 保守计数。
4. 37 个 seal 均即时复核；最终 replay 从 staging 重读 `predictions.csv.gz`、`monthly_selections.csv`、`fold_audit.csv`，再绑定落盘模型逐月复核。落盘预测篡改测试会 fail-close。

## 剩余边界

- 完整开发标签在内存中可见，因此仍只是逻辑访问门控，不是物理 sealed holdout。
- 本次 PASS 只允许 development OOS；即使效果门通过，也仅允许另行预注册真实撮合 A/C 回测。
