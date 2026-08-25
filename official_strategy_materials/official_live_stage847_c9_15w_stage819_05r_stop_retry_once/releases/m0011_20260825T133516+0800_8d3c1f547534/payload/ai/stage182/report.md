# Stage182 AI Product Pool Live Inference

- Generated at: `2026-08-03 23:44`
- Eval date: `2026-07-31`
- Source max date: `2026-08-03`
- Source prefix: `qmt_roll_stage183_ai_source_floor35`
- Training label cutoff: `2026-05-07`
- Train rows: `1368`
- Feature count: `108`
- Live rows: `18`
- Strategy: `ai_top8_plus_fu_satellite_post_signal_entry_filter`

## Leakage Boundary

Training rows are restricted to eval dates on or before `2026-05-07`. The live pool for `2026-07-31` is scored from features available at that date and is not used to train itself.

## Live Ranking

| ai_rank | product_vt_symbol | predicted_product_suitability_probability | simple_trend_suitability_score |
| --- | --- | --- | --- |
| 1 | jm.DCE | 0.695849 | 2.134880 |
| 2 | si.GFEX | 0.660340 | 2.321076 |
| 3 | SA.CZCE | 0.645589 | -0.166063 |
| 4 | au.SHFE | 0.628731 | 0.158862 |
| 5 | lc.GFEX | 0.620252 | -1.614788 |
| 6 | cu.SHFE | 0.618670 | 0.095412 |
| 7 | SM.CZCE | 0.615907 | 0.076229 |
| 8 | lh.DCE | 0.577337 | 1.472726 |
| 9 | MA.CZCE | 0.527458 | -6.025227 |
| 10 | OI.CZCE | 0.523530 | 0.623274 |
| 11 | FG.CZCE | 0.515984 | 0.156501 |
| 12 | AP.CZCE | 0.504880 | 1.837448 |
| 13 | CF.CZCE | 0.493367 | -2.106422 |
| 14 | ru.SHFE | 0.481431 | -0.520950 |
| 15 | sp.SHFE | 0.479057 | -1.147920 |
| 16 | SH.CZCE | 0.473822 | -1.016887 |
| 17 | rb.SHFE | 0.415390 | 2.127194 |
| 18 | hc.SHFE | 0.381339 | 1.594655 |

## Eligibility Written

| eval_date | product_vt_symbol | score | score_rank | top_n | score_type |
| --- | --- | --- | --- | --- | --- |
| 2026-07-31 | jm.DCE | 0.695849 | 1 | 9 | stage182_live_monthly_ai_probability |
| 2026-07-31 | si.GFEX | 0.660340 | 2 | 9 | stage182_live_monthly_ai_probability |
| 2026-07-31 | SA.CZCE | 0.645589 | 3 | 9 | stage182_live_monthly_ai_probability |
| 2026-07-31 | au.SHFE | 0.628731 | 4 | 9 | stage182_live_monthly_ai_probability |
| 2026-07-31 | lc.GFEX | 0.620252 | 5 | 9 | stage182_live_monthly_ai_probability |
| 2026-07-31 | cu.SHFE | 0.618670 | 6 | 9 | stage182_live_monthly_ai_probability |
| 2026-07-31 | SM.CZCE | 0.615907 | 7 | 9 | stage182_live_monthly_ai_probability |
| 2026-07-31 | lh.DCE | 0.577337 | 8 | 9 | stage182_live_monthly_ai_probability |
| 2026-07-31 | fu.SHFE | 0.577336 | 9 | 9 | stage182_live_fixed_fu_satellite |

## Next Use

Review this file first. Do not overwrite the official Stage78 eligibility file automatically.