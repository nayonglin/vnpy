# Stage065 Top10 + 固定 fu 正式晋升 AI 物料

- 生成时间（CST）：`2026-08-30T06:10:36+08:00`
- 来源 commit：`6750783fe7aab92e6dbdd6820fa212e2e53ea353`
- 来源 eligibility SHA256：`cf3cced22a61b354dadbc2f67091143eec74d7a2f03577faf2fd4c10dcec0c0d`
- 正式选品策略：`ai_top10_plus_fu_official_live_v1`
- 最新 eval_date：`2026-07-31`
- 训练标签截止：`2026-05-07`
- 自然门禁结论：`FAIL`
- 本次晋升依据：用户显式授权，`operator_override=true`；不得表述为自然通过研究门禁。
- 安全边界：仅转换并固化已有 eligibility；不训练、不评分、不回测、不连接 CTP，send/cancel/order API 调用均为 `0`。

## 已知失败（完整保留）

- Stage061：`offline_width_sweep_no_fullperiod_candidate_keep_stage037`；全周期滑点为正式 Stage037 的 `130.36%`，超过冻结 `105%` 门。
- Stage063：`offline_top9_top10_multicycle_has_hard_fail_keep_stage037`；固定多周期存在成本、回撤非劣和 broker100 硬失败。
- Stage064：`random_stress_diagnostic_only_keep_stage037_stop_topn_scan`；192个随机窗口的回撤非劣率 `72.92%`、总滑点比 `113.66%`，并出现 `1` 个 broker100 失败窗口。

## 最新正式池

| 排名 | 品种 | 角色 | 模型分数 |
| ---: | --- | --- | ---: |
| 1 | jm.DCE | model_ranked | 0.695849 |
| 2 | si.GFEX | model_ranked | 0.660340 |
| 3 | SA.CZCE | model_ranked | 0.645589 |
| 4 | au.SHFE | model_ranked | 0.628731 |
| 5 | lc.GFEX | model_ranked | 0.620252 |
| 6 | cu.SHFE | model_ranked | 0.618670 |
| 7 | SM.CZCE | model_ranked | 0.615907 |
| 8 | lh.DCE | model_ranked | 0.577337 |
| 9 | MA.CZCE | model_ranked | 0.527458 |
| 10 | OI.CZCE | model_ranked | 0.523530 |
| 11 | fu.SHFE | fixed_fu | 0.523529 |

## 结构契约

- AI月份：模型评分 Top10（不含fu）+ 固定 `fu.SHFE`，共11个；rank固定为1..11，top_n固定为11。
- pre-AI边界：2019-12-31静态18品种，不含fu，rank为1..18，top_n为18。
- 所有 score_type 均加 `stage182_promoted_` 前缀，允许后续 Stage182 月更保留历史快照。
