# Stage003 无拟合证据恢复实施计划

1. 为 float hex 持久化与 bit-exact 回读、Stage002 event/access event 验证、模型重放和 seal 核验写测试。
2. 实现独立 Stage003 runner；只 import 已冻结 Stage002 core/contract，不修改 Stage002 文件。
3. 在任何效果标签读取前完成 37 折 primary/repeat 模型加载、预测重建、选择重建和原 seal 精确核验。
4. 生成 lossless hex 预测证据并二次回读，证明 2,000 行逐元素完全一致。
5. 技术门全过后才重新生成 36 月 predictive/effect 表，并调用已冻结 Stage002 门槛。
6. 绑定 Stage002 失败 bundle、原输入、Stage003 实现与运行时 SHA，生成新 nonce 和 durable execution event。
7. 唯一执行后发布完整或失败 bundle；独立 reviewer 复核，不做任何参数或样本救援。
