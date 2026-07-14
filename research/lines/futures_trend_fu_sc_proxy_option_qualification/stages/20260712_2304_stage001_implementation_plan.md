# Stage001 FU-SC T-1 beta 资格实施计划

- line_id：`futures_trend_fu_sc_proxy_option_qualification`
- 记录时间：`2026-07-12 23:04 CST`
- 阶段性质：预声明后的实现计划；未读取统计结果
- 回测：否

## 实现

1. 从 Stage131 机械得到 SC 上市后全部 FU 事件，预期当前快照 `32` 个、核心 `6` 个。
2. SQLite 只读加载 FU/SC 实际合约日线；每个 return date 只按前一产品交易日 OI 选约。
3. 若 T-1 top-OI 合约次日缺 bar，记录缺失，不递补第二合约。
4. 同合约 close-to-close 构造日收益，FU/SC 按日期内连接。
5. 每事件只取 entry 前最后126共同日，固定全窗与两个63日半窗。
6. 输出逐日选约、共同收益、逐事件 beta/corr、gate、decision、lineage 与 manifest。
7. 本地 gate 失败不调用 TqSdk；通过才进入同 Stage001 的 SC 历史链覆盖子步骤。

## 测试先行

- 负例：同日 OI 反转不能改变当日所选合约。
- 负例：T-1 第一合约次日缺失不能递补第二名。
- 正例：固定线性收益应恢复 beta 与相关系数，且 entry day 必须排除。

## 边界

- 不读取任何策略盈亏或期权价格。
- 不修改正式策略与其他研究线。
- 不因本地结果更换代理、窗口或阈值。

