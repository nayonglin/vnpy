# Stage295：Stage78 降为历史对照，实盘默认切到 Stage653

- 时间：2026-06-04 20:36 CST
- 工作模式：day
- line_id：`futures_trend`
- 性质：跨线实盘口径切换记录

## 结论

- Stage78-1 `official_stage78_1_defensive_50w_no_sizing_cap` 不再是当前实盘默认 signal source。
- Stage78-1 50万保留为历史/研究对照，以及 CTP/SimNow 执行安全资产的来源。
- 当前官方实盘默认版本为 Stage653/20万：`official_live_stage653_20w_force95_to80`。

## 影响范围

- `research/lines/futures_trend/LINE.md` 已更新定位。
- `research/registry.md` 已更新当前线状态。
- `AGENTS.md` 与 `skills/futures-live-execution-sop/SKILL.md` 已更新触发规则和默认口径。
- Phase B 草案、每日执行闸门已改为读取 Stage653 official live 配置。

## 保留边界

- Stage78 历史指标不删除、不覆盖。
- Stage188/Stage186 等 50万 runner 保留为研究对照，不作为实盘默认入口。
- 执行安全纪律不变：默认 dry-run，fresh read-only，人工确认，order API 调用必须显式授权。

## 反思

- 过拟合判断：否。本阶段不改变策略参数，只改变官方部署默认口径。
- 继续价值判断：是。这样后续实盘相关问题会使用用户指定的 Stage653，而不是继续误用 Stage78/50万。
