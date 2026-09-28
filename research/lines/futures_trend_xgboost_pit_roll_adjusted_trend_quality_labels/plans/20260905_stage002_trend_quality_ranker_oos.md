# Stage002 趋势质量 XGBRanker 样本外实施计划

1. 为连续趋势质量建立纯函数：线性 NDCG@10、随机排序精确期望、Rank IC、A/C 月度效果及冻结门槛。
2. 在所有模型操作前排除固定 `fu.SHFE`，按剩余 AI universe 重新计算 relevance；建立保守单槽选择器：正式第 10 名只有在 XGBoost Top10 排除它且纳入池外 challenger 时才允许替换。
3. 建立阶段门控标签存储：成熟训练标签可开，测试 qid 必须在模型、预测和选择 seal 后才能开。
4. 复用既有固定 `XGBRanker` 参数、qid 构造、双拟合确定性检查和 estimator audit，不复用旧的裸收益标签逻辑。
5. 先写核心与 runner 测试并确认 RED，再实现到 GREEN；随后跑本研究线测试和全部 XGBoost PIT 回归测试。
6. 冻结实现、测试、预注册、实际复用的 V1/V2/XGBoost 代码与输入 SHA256，生成一次性授权回执与父目录同步的 durable execution event。
7. 首次且唯一一次执行 37-fold development OOS；逐 fold 原子保留模型、seal、预测、选择和进度。
8. 标签开放后立即持久化访问审计；37 个 seal 在生成后及汇总前各复核一次。发布完整或失败证据包，独立 reviewer 复核预注册一致性、泄漏、确定性和结论边界。
9. 仅在全部门通过后，另行预注册 A/C 真实撮合回测；本阶段不改正式策略或生产配置。
