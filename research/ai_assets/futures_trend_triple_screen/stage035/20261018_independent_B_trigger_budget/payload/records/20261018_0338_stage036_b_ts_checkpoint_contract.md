# Stage036：B_TS 独立账户与自有 checkpoint 入口

- line_id：futures_trend_triple_screen；2026-10-18 03:38 CST。从冻结031 runner SHA3af932bdbde9ae607c507ff8630dde0a0b03f190ca88be94fa43ce5910b0b860适配。实验规则唯一权威为0333 Stage035合同；原C、031/033源码和结果保持。
- 真实B_TS/attempt1，独立outputs/stage036_b_ts_account/B_TS，writer stage036_run_b_ts_checkpoint.py，raw/context/manifest/seal schemas stage036_*；禁止加载C owned checkpoint。源035 pricing/strategy SHA未review+冻结时main preflight/run硬拒绝，不因fixture成功误跑。
- 复用原完整raw立即持久化、原guard后seal及纯export-only安全恢复，实际TradeData身份/合成母OPEN核对不变；B的T估价/final budget/unknown无fallback/新模型域在source和provenance明确。
- A0/周/FI/stack复用，两个历史anchor来源路径维持原C真实请求，独立各一key不扩full；037仅响应此B实际缺口。单次--run内联preflight，actual终态/完整账本之后须新独立038经济审计，不能以代码测试宣告alpha。
- 无金融结果，参数及结果新增/修改/删除0（新研究行为见035合同）。新增过拟合否、继续价值是；当前金融0/网络0/训练0、production_qualified=false。
