# Stage001 L1 历史 Tick Canary 预声明

- line_id：`futures_trend_l1_topbook_entry_quality`
- 当前模式：`day`
- 记录时间：`2026-07-13 01:03 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：看数据结果前冻结12事件、窗口、接口、完整性与机械决策
- 是否重要突破：否
- 是否触发A/B：否

## 固定12事件

- CZCE day：`2018-03-29 AP805`、`2026-04-30 SH607`。
- CZCE night：`2018-02-05 OI805`、`2026-03-06 SM605`。
- DCE day：`2021-04-12 lh2109`、`2025-08-13 lh2511`。
- DCE night：`2018-06-11 jm1809`、`2025-10-28 jm2601`。
- GFEX day：`2023-08-24 si2310`、`2025-12-18 lc2605`。
- SHFE night：`2018-01-15 au1806`、`2026-01-27 ru2605`。
- event_id、tqsdk_underlying、entry_date 与分层必须由代码重新机械推导并逐项匹配，不手写替换。

## 固定完整性

- 原始响应、请求、状态、schema、normalized、audit、manifest 均原子落盘；旧attempt不可覆盖。
- datetime 保留原始integer ns；任何 float64 二次精度往返直接失败。
- 合法双边行：top1价格正且有限、ask>=bid、top1 size非负有限、时间在窗口内、symbol一致。
- `session_open -> +60s` 至少一条合法双边行；不要求level2-5，不把缺少深档视为L1失败。
- 12/12全过才允许下一阶段全事件采集预声明；任何网络/权限/空数据/完整性失败都闭线。

## 测试先行

- deterministic earliest/latest canary选择必须有测试。
- 周一夜盘必须使用前一global trade date，不用自然日前一天。
- integer ns normalize、越界、crossed spread、负size、重复键、volume回退、symbol错配和凭据脱敏必须有正负测试。
- fake fetch必须证明失败留在分母且不会写ready。

## 反思

- 过拟合：预声明阶段否；若查询失败后换事件/窗口/接口或只保留成功层，则是。
- 继续价值：只值一次固定canary；失败后无补分钟proxy价值。
