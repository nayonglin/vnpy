# Stage182 AI Product Pool Live Inference

- Generated at: `2026-09-01 16:37`
- Eval date: `2026-08-31`
- Source max date: `2026-09-01`
- Source prefix: `qmt_roll_stage183_ai_source_floor35`
- Training label cutoff: `2026-06-05`
- Train rows: `1386`
- Feature count: `108`
- Live rows: `11`
- Strategy: `ai_top10_plus_fu_official_live_v1`

## Leakage Boundary

Training rows are restricted to eval dates on or before `2026-06-05`. The live pool for `2026-08-31` is scored from features available at that date and is not used to train itself.

## Live Ranking

| ai_rank | product_vt_symbol | predicted_product_suitability_probability | simple_trend_suitability_score |
| --- | --- | --- | --- |
| 1 | si.GFEX | 0.744010 | -1.186722 |
| 2 | cu.SHFE | 0.636249 | 0.346398 |
| 3 | SM.CZCE | 0.623324 | 0.410293 |
| 4 | lc.GFEX | 0.602772 | 0.185476 |
| 5 | SA.CZCE | 0.602435 | 0.135394 |
| 6 | au.SHFE | 0.601456 | 0.410293 |
| 7 | sp.SHFE | 0.582754 | -0.920813 |
| 8 | lh.DCE | 0.569986 | 1.733375 |
| 9 | FG.CZCE | 0.558972 | 0.407916 |
| 10 | SH.CZCE | 0.557877 | -0.107706 |
| 11 | fu.SHFE | 0.557876 | nan |

## Eligibility Written

| eval_date | product_vt_symbol | score | score_rank | top_n | score_type |
| --- | --- | --- | --- | --- | --- |
| 2026-08-31 | si.GFEX | 0.744010 | 1 | 11 | stage182_live_monthly_ai_probability |
| 2026-08-31 | cu.SHFE | 0.636249 | 2 | 11 | stage182_live_monthly_ai_probability |
| 2026-08-31 | SM.CZCE | 0.623324 | 3 | 11 | stage182_live_monthly_ai_probability |
| 2026-08-31 | lc.GFEX | 0.602772 | 4 | 11 | stage182_live_monthly_ai_probability |
| 2026-08-31 | SA.CZCE | 0.602435 | 5 | 11 | stage182_live_monthly_ai_probability |
| 2026-08-31 | au.SHFE | 0.601456 | 6 | 11 | stage182_live_monthly_ai_probability |
| 2026-08-31 | sp.SHFE | 0.582754 | 7 | 11 | stage182_live_monthly_ai_probability |
| 2026-08-31 | lh.DCE | 0.569986 | 8 | 11 | stage182_live_monthly_ai_probability |
| 2026-08-31 | FG.CZCE | 0.558972 | 9 | 11 | stage182_live_monthly_ai_probability |
| 2026-08-31 | SH.CZCE | 0.557877 | 10 | 11 | stage182_live_monthly_ai_probability |
| 2026-08-31 | fu.SHFE | 0.557876 | 11 | 11 | stage182_live_fixed_fu_satellite |

## Next Use

Review this file first. Do not overwrite the official Stage78 eligibility file automatically.