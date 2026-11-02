# Stage182 AI Product Pool Live Inference

- Generated at: `2026-10-08 16:39`
- Eval date: `2026-09-30`
- Source max date: `2026-10-08`
- Source prefix: `qmt_roll_stage183_ai_source_floor35`
- Training label cutoff: `2026-07-07`
- Train rows: `1404`
- Feature count: `108`
- Live rows: `11`
- Strategy: `ai_top10_plus_fu_official_live_v1`

## Leakage Boundary

Training rows are restricted to eval dates on or before `2026-07-07`. The live pool for `2026-09-30` is scored from features available at that date and is not used to train itself.

## Live Ranking

| ai_rank | product_vt_symbol | predicted_product_suitability_probability | simple_trend_suitability_score |
| --- | --- | --- | --- |
| 1 | cu.SHFE | 0.637378 | 0.008968 |
| 2 | SM.CZCE | 0.618429 | 0.099202 |
| 3 | lh.DCE | 0.618429 | -0.122395 |
| 4 | si.GFEX | 0.611094 | -2.454598 |
| 5 | au.SHFE | 0.601338 | 0.099202 |
| 6 | SA.CZCE | 0.596845 | 0.099202 |
| 7 | rb.SHFE | 0.592654 | -1.362169 |
| 8 | CF.CZCE | 0.581144 | -0.259634 |
| 9 | sp.SHFE | 0.577269 | -1.784792 |
| 10 | FG.CZCE | 0.553192 | 0.099202 |
| 11 | fu.SHFE | 0.553191 | nan |

## Eligibility Written

| eval_date | product_vt_symbol | score | score_rank | top_n | score_type |
| --- | --- | --- | --- | --- | --- |
| 2026-09-30 | cu.SHFE | 0.637378 | 1 | 11 | stage182_live_monthly_ai_probability |
| 2026-09-30 | SM.CZCE | 0.618429 | 2 | 11 | stage182_live_monthly_ai_probability |
| 2026-09-30 | lh.DCE | 0.618429 | 3 | 11 | stage182_live_monthly_ai_probability |
| 2026-09-30 | si.GFEX | 0.611094 | 4 | 11 | stage182_live_monthly_ai_probability |
| 2026-09-30 | au.SHFE | 0.601338 | 5 | 11 | stage182_live_monthly_ai_probability |
| 2026-09-30 | SA.CZCE | 0.596845 | 6 | 11 | stage182_live_monthly_ai_probability |
| 2026-09-30 | rb.SHFE | 0.592654 | 7 | 11 | stage182_live_monthly_ai_probability |
| 2026-09-30 | CF.CZCE | 0.581144 | 8 | 11 | stage182_live_monthly_ai_probability |
| 2026-09-30 | sp.SHFE | 0.577269 | 9 | 11 | stage182_live_monthly_ai_probability |
| 2026-09-30 | FG.CZCE | 0.553192 | 10 | 11 | stage182_live_monthly_ai_probability |
| 2026-09-30 | fu.SHFE | 0.553191 | 11 | 11 | stage182_live_fixed_fu_satellite |

## Next Use

Review this file first. Do not overwrite the official Stage78 eligibility file automatically.