# Stage172 - rb broker/shadow 差异复查

## 基本信息

- 时间：2026-07-08 17:10 CST
- 研究线：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 实盘版本：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`
- 本阶段性质：实盘 shadow/broker 对账差异复查；不改策略参数、不改 AI 池、不连接真实下单。

## 触发问题

用户追问：当前 broker 侧仍有 `rb2610.SHFE short 11`，但 Stage901/Stage929 最新 shadow 是 0，是否有问题，以及为什么会有这个差异。

## 复查命令与证据

- 读取 SOP：`skills/futures-live-execution-sop/SKILL.md`
- 读取 official shadow skill：`/Users/bytedance/.codex/skills/futures-official-shadow/SKILL.md`
- 读取当前模式：`work-type.txt`
- 读取索引：`research/registry.md`
- 复查 Stage901 当前输出：
  - `qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow_trades_stage901_stage847_c9_2026_ytd_live_shadow_v1.csv`
  - `qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow_entry_candidates_stage901_stage847_c9_2026_ytd_live_shadow_v1.csv`
  - `qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow_entry_risk_stage901_stage847_c9_2026_ytd_live_shadow_v1.csv`
  - `qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow_current_positions_stage901_stage847_c9_2026_ytd_live_shadow_v1.csv`
- 复查 AI 池：
  - `qmt_roll_stage182_ai_product_pool_live_inference_combined_stage78_eligibility_stage182_ai_product_pool_live_inference_v1.csv`
  - `qmt_roll_stage182_ai_product_pool_live_inference_eligibility_stage182_ai_product_pool_live_inference_v1.csv`
- 复查阶段记录：
  - Stage109：`20260622_1731_stage109_c9_live_monthly_ai_pool_wiring_fix.md`
  - Stage145：`20260630_1700_stage145_live_artifacts_rebuild.md`
  - Stage150：`20260630_2120_stage150_stage182_183_deterministic_rebuild.md`
  - Stage169：`20260702_1732_stage169_sh_shadow_broker_divergence_attribution.md`

## 关键发现

- 2026-06-22 当时的实盘修复记录 Stage109 明确显示：
  - AI 池 eval_date：`2026-05-29`
  - Top9 包含 `rb.SHFE`
  - Stage901 pending order：`rb2610.SHFE Short Open volume=11 price=3126.0`
- 2026-06-23 Stage121 仍显示：
  - expected/current eval_date：`2026-05-29`
  - Top9：`SA.CZCE, si.GFEX, FG.CZCE, MA.CZCE, OI.CZCE, jm.DCE, AP.CZCE, rb.SHFE, fu.SHFE`
- 当前 2026-07-08 的 Stage901 重放结果不是 rb 路径：
  - 当前 shadow trades 为 2026-06-23 开 `SH609.CZCE short 5` 与 `lh2609.DCE short 1`，2026-06-25 平 `lh2609`，2026-07-07 平 `SH609`。
  - 当前 entry_candidates 中，2026-06-22 的 `rb2610.SHFE` 是 `ai_product_pool_blocked`。
  - 当前 current_positions 为空。
- 当前 combined AI eligibility 文件：
  - `eval_date` 尾部为 `2026-01-30`、`2026-02-27`、`2026-06-30`，缺 `2026-03-31`、`2026-04-30`、`2026-05-29`。
  - 当前文件中 `2026-05-29` 行数为 0。
  - 当前文件中 `2026-06-30` Top9 为 `ru.SHFE, si.GFEX, SA.CZCE, FG.CZCE, AP.CZCE, au.SHFE, jm.DCE, SM.CZCE, fu.SHFE`。
- Stage935 2026-06-30 16:57:37 有一次 `monthly_ai_pool_updated`：
  - update_reasons 包含 `trading_calendar_stale_before_wall_clock_cutoff`、`current_stage182_eval_date_missing`、`current_stage182_outputs_invalid`、`force_requested`。
  - 该次重建后 `2026-05-29` Top9 变为 `SA.CZCE, MA.CZCE, OI.CZCE, si.GFEX, AP.CZCE, FG.CZCE, SM.CZCE, jm.DCE, fu.SHFE`，即 `SM` 替换了早先线上记录里的 `rb`。
- Stage169 已经在 2026-07-02 给出同一根因：
  - 7 月月更后 combined 只保留最新 live eligibility 截面，未保留 3/31、4/30、5/29 live 重建截面。
  - Stage901 回放 2026-06-22 时不能使用 6/30，只能向前落到 2/27，导致 SH/lh 替代原先 rb 路径。

## 结论

- 这是一个真实问题，但不是 broker 读错，也不是策略今天新发了隐藏信号。
- 直接原因：当前 shadow 使用的 AI eligibility 历史月度截面不完整，并且 2026-05-29 线上池曾被当前输入重算覆盖；因此当前重放 2026-06-22 时没有使用当时真正驱动实盘 rb 信号的线上池。
- broker 侧 `rb2610.SHFE short 11` 来自 2026-06-22 当时的策略信号/人工补单路径；当前 shadow 为 0 是当前重算输入断档导致的错误回放，不应据此认定 rb 不是策略仓，也不应据此生成 SH/lh 的实盘动作。
- 当前执行层保持 fail-closed 是正确的；但后续信号邮件和对账报告不能把这个差异只写成普通“broker/shadow 不一致”，必须解释为 AI 池历史截面断档导致的 shadow 口径错误。

## 后续建议

1. 修复 Stage182/Stage935 的 combined eligibility 产出逻辑，保留 live 历史月度截面，至少不得在月更后丢失 2026-05-29 这种仍用于冷启动回放的 PIT 截面。
2. 增加 Stage901/Stage929 校验：如果 `analysis_start -> target_date` 期间应有的月度 AI eval_date 缺失，报告应明确标红并 fail-closed，不应静默回退到更早月份。
3. 用 Stage109/Stage121/Stage143 等线上记录中的 2026-05-29 池，或可验证原始 5 月底 eligibility，重建 `2026-06-16 -> 当前` shadow，再重新做 broker/shadow 对账。
4. 在修复前，不要用当前 Stage901 的 `shadow=0` 去判断是否应自动处理 broker 侧 rb 仓位；rb 仍应被视为需单独接管/对账的策略相关仓位。

## 反过拟合与继续价值

- 过拟合判断：否。本阶段只做执行数据版本归因，不调整 C9 规则、AI 排名、品种池或风控参数。
- 继续价值判断：是。该问题会直接影响实盘对账和信号解释；修复后才能保证后续 shadow 与实盘路径一致，避免月更后改写历史实盘持仓。
