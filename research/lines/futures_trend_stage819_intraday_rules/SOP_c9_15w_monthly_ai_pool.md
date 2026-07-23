# C9/15万生产月度 AI 池 SOP

## 适用范围

- 当前正式口径：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`
- execution profile：`c9-15w`
- 资金口径：`150000`
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
   - `monthly_ai_pool_already_current`：不重训，Stage947 校验现有 daily receipt。
   - `monthly_ai_pool_updated`：Stage947 立即通过同一条合格的 Stage909 production precompute 重建 C9 shadow，并签发绑定新 AI 池、同一 source commit 和权威 target date 的 daily receipt。
   - 其他状态：fail closed，不允许会话入口继续使用旧池生成新开仓。
4. Stage947、Stage935、Stage909 均不得调用 broker order API。

18:20 是每日健康检查时刻，不代表每日重训；真正更新频率仍是月度。

## 正式约束

- 只在上一完整月份的最后交易日数据齐全后更新。
- 禁止 `--allow-incomplete-month`。
- 禁止未来标签、未完成月份、手工改 eval date 或为当天信号临时改排名。
- 当前生产池的完整性、产品数和卫星品种规则以 Stage935/Stage182 的资格检查为准；不得仅凭肉眼名单跳过校验。
- 更新后必须有新的、同 target、同 source commit、同 AI 池 identity 的 daily receipt；否则 Stage945/946 必须阻断。

## 手工诊断（会写诊断产物）

Stage935 `--mode check` 不更新 AI 池、不连接 CTP、不调用订单 API，但会创建单例锁并写 summary、report 和 `latest_*` 诊断文件，因此不能称为文件系统只读。只能从 production stable root 运行，并在报告中说明这些写入：

```bash
/Users/bytedance/Desktop/person/vnpy_production_live/.py311/bin/python \
  /Users/bytedance/Desktop/person/vnpy_production_live/examples/portfolio_backtesting/run_qmt_roll_stage935_official_live_monthly_ai_pool_update.py \
  --mode check --email-policy never
```

该命令只用于人工诊断，不等同于生产月更成功。直接运行 Stage182/183 仅用于研究或故障归因。正式生产更新应由 Stage947 -> Stage935 持有，不能绕过回执重签流程。

不得为了“马上恢复交易”手工改池文件、复制历史池或删除 daily receipt。

## 报告字段

至少报告：

- stable source commit 与 execution profile；
- resolved target date、expected eval date、current eval date；
- Stage935 状态与当前产品清单；
- 是否触发 Stage909 重算与 daily receipt 重签；
- receipt 是否与 source commit、target date、AI 池一致；
- send/cancel/order API 计数；
- 阻断项和下一步。

阶段记录写入：

`research/lines/futures_trend_stage819_intraday_rules/stages/`
