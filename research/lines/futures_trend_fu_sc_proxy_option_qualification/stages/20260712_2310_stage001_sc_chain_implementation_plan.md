# Stage001 SC 历史期权链覆盖实施计划

- line_id：`futures_trend_fu_sc_proxy_option_qualification`
- 记录时间：`2026-07-12 23:10 CST`
- 阶段性质：本地 beta gate 通过后的 metadata 子步骤计划；尚未联网
- 回测：否

## 前置事实

- 本地 provisional decision：`LOCAL_BETA_GATE_PASS_REQUIRES_OPTION_CHAIN`。
- 全体 FU 事件 `32/32` 历史完整且三窗通过；核心 `6/6` 通过。
- 该结果正在独立 review；真实网络必须等 review 无 P1 或 P1 修复重跑后才启用。

## 固定执行顺序

1. 由 beta 选约账本把每个 FU `entry_date` 映射到同日使用的 T-1 OI SC 实际合约。
2. 核心 6 事件作为固定 canary，逐事件独立 `TqBacktest(entry_date)` 查询 `expired=False` 的 SC option chain。
3. canary 必须 `6/6 extracted`；否则剩余 26 事件不运行，直接关闭。
4. canary 通过后运行其余事件；全体 extracted coverage 必须 `>=90%`。
5. 本阶段只保存 metadata；不下载 premium/bar/tick，不选 strike/DTE，不回测。

## 产物与安全

- 每事件原子目录：sanitized request、status、symbols、untouched/normalized metadata、manifest/hash。
- producer 固定引用已通过审查的 Stage132 metadata fetch/normalize/audit 函数，并保存 producer SHA。
- 默认 `STAGE001_SC_CHAIN_ENABLE_NETWORK=0`；只有显式置1才可联网。
- 凭据只由 vn.py settings 读取，不写入任何 request/status/report；异常消息沿用 Stage132 redaction。

## 机械决策

- canary不足6条、请求未完成、核心不是6/6或全体覆盖低于90%：`CLOSE_LINE_OPTION_CHAIN_INELIGIBLE`。
- 全部通过：`ALLOW_STAGE002_EXECUTION_DATA_PREDECL_ONLY`；仍禁止收益回测。

