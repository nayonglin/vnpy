# Stage001 实现计划

- line_id：`futures_trend_tight_stop_quality_sizing`
- 记录时间：`2026-07-13 22:46 CST`
- 阶段性质：实现计划，不含结果

## 计划

1. 先写 focused tests，锁住严格 T-1、Wilder 指标、分批平仓聚合、discovery-only 阈值和 AI 字段禁用。
2. 新增 `tools/stage001_baseline_technical_attribution.py`，调用当前主策略入口全新运行一次。
3. 重新生成 daily/trades/entry risk/entry candidates/closed lots，并把策略结果字段与技术特征字段分层保存。
4. 从实际合约日线计算冻结特征；缺失不补零、不跨合约拼接，按缺失 fail-close。
5. 生成主策略图、技术特征图、分段/年份统计、drawdown attribution 和证据 manifest。
6. 运行 focused tests、py_compile、manifest verifier 和 `git diff --check`。
7. 拉独立 agent 从原始输出复算；修复所有会影响结果的问题并原口径重跑。

## 不做

- 不改主策略和正式配置。
- 不搜索技术指标周期、止损倍数或仓位倍率。
- 不使用 AI 字段、产品/年份黑名单或事后 MFE/MAE 生成规则。
- 不因旧研究成功或失败而提前接受/拒绝任何规则。
