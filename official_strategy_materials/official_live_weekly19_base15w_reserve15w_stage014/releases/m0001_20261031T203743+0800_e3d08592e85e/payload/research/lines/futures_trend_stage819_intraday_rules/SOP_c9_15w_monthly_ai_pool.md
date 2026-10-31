# C9/15万生产月度 AI 池 SOP

## 适用范围

- 当前正式口径：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`
- execution profile：`c9-15w`
- 资金口径：`150000`
- 正式物料策略：`ai_top10_plus_fu_official_live_v1`
- 正式 ruleset：`stage037_stage034_long_short_mirror_hard_block_v1`
- AI 池合同：模型评分 Top10 非 `fu` 品种，加固定 `fu.SHFE`，共 11 个品种。
- 本 SOP 只管理月度池更新、生产回执与 fail-closed，不修改 alpha、排名逻辑、TopN、训练窗或交易价格。

## 事实源

按以下顺序判断生产状态：

1. `/Users/bytedance/Desktop/person/vnpy_production_live` 的 stable HEAD。
2. `~/Library/Application Support/qmt-roll-stage179/production-live/` 下的 release manifest、qualification、activation receipt、activation audit 和 daily-data receipt。
3. stable root 中的当前 live config。

普通开发 checkout 和历史 Stage78 SOP 只可用于研究对照，不得覆盖生产事实。

## 自动流程

1. 工作日 18:20 由 `local.qmt-roll.official-live.15w.c9-production-live-monthly-ai-pool` 启动 Stage947 `--job monthly-ai-pool`。
2. Stage947 先验证 canonical launchd owner、stable root、release、activation 和 qualification，再调用 Stage935。
3. Stage935 按 Stage922 口径计算最新完整月份的预期 `eval_date`：
   - `monthly_ai_pool_already_current`：不重训；Stage947 校验当前安装的不可变物料和现有 daily receipt。
   - `monthly_ai_pool_updated`：只生成候选 AI 池与 material publication request；Stage947 必须立即 fail closed，不得直接调用 Stage909、签发 daily receipt 或让候选池参与新开仓。
   - 其他状态：fail closed，不允许会话入口继续使用旧池生成新开仓。
4. 候选池必须使用 `official_version=ai_top10_plus_fu_official_live_v1`，并完整通过 `prepare → commit → verify → qualification → activate → promote-master → fresh clone → Stage948`；任一步失败都保留原活动 release 并继续 fail closed。
5. Stage948 完成安装后，才允许 Stage909 基于新安装的不可变 release 重建 C9 shadow，并签发绑定新 AI 池、同一 source commit、release identity 和权威 target date 的 daily receipt；回执校验通过后才可解除会话入口阻断。
6. Stage947、Stage935、Stage909 均不得调用 broker order API。

18:20 是每日健康检查时刻，不代表每日重训；真正更新频率仍是月度。

## 正式约束

- 只在上一完整月份的最后交易日数据齐全后更新。
- 禁止 `--allow-incomplete-month`。
- 禁止未来标签、未完成月份、手工改 eval date 或为当天信号临时改排名。
- 当前生产池必须严格是模型评分 Top10 非 `fu` 品种（rank 1-10）加固定 `fu.SHFE`（rank 11），共 11 行且 `top_n=11`；完整性和身份以 Stage935/Stage182 的资格检查及正式物料 manifest 为准，不得仅凭肉眼名单跳过校验。
- `monthly_ai_pool_updated` 产物只能作为候选，禁止覆盖当前活动物料、直接复制到 stable root 或跳过不可变 release 晋升。
- 新池安装后必须有新的、同 target、同 source commit、同 release identity、同 AI 池 identity 的 daily receipt；否则 Stage945/946 必须阻断。

## 手工诊断（会写诊断产物）

Stage935 `--mode check` 不更新 AI 池、不连接 CTP、不调用订单 API，但会创建单例锁并写 summary、report 和 `latest_*` 诊断文件，因此不能称为文件系统只读。只能从 production stable root 运行，并在报告中说明这些写入：

```bash
/Users/bytedance/Desktop/person/vnpy_production_live/.py311/bin/python \
  /Users/bytedance/Desktop/person/vnpy_production_live/examples/portfolio_backtesting/run_qmt_roll_stage935_official_live_monthly_ai_pool_update.py \
  --mode check --email-policy never
```

该命令只用于人工诊断，不等同于生产月更成功。直接运行 Stage182/183 仅用于研究或故障归因。正式生产更新应由 Stage947 -> Stage935 生成候选和 publication request，再走完整不可变物料晋升、fresh clone 审计与 Stage948 安装；不能从候选直接跳到 Stage909 或回执重签。

不得为了“马上恢复交易”手工改池文件、复制历史池或删除 daily receipt。

## 报告字段

至少报告：

- stable source commit 与 execution profile；
- resolved target date、expected eval date、current eval date；
- Stage935 状态与当前产品清单；
- material publication request 的 `official_version`、source commit 与 5 个 AI 产物 SHA256；
- 是否完成不可变 release 晋升、fresh clone、Stage948 安装、Stage909 重算与 daily receipt 重签；
- receipt 是否与 source commit、target date、AI 池一致；
- send/cancel/order API 计数；
- 阻断项和下一步。

阶段记录写入：

`research/lines/futures_trend_rollover_shape_same_volume/stages/`
