# Stage024B 指定合约元数据寻址探针

- line_id：`futures_trend_xgboost_history_compatible_root_utility`；2026-09-06 06:10 CST。
- Stage024唯一目录结果保持不变：摘要SHA `417a26acd7d5a9553c76cf3d9438b022716f2e1c04319af45e3d2835f823b778`，缺13合约/20事件，未下载行情。
- 本探针只验证“目录缺失”是否等于“指定合约元数据不可寻址”，不是重跑目录资格或挽救策略收益。
- 固定请求：直接对原13个缺失合约执行一次query_symbol_info，TqBacktest时点仍为2026-08-28。若存在缺失/失败，再在原最早受影响决策日2020-01-08执行一次同集合查询，判断historical timestamp能否改变元数据可得性。最多两次，不循环重试、不连接CTP、不读行情/标签。
- 第二日期只是历史接口控制，不宣称13个合约当日均应已上市；结果不能直接填入训练集。成功也仍需完整全链来源资格。
- 复用Stage024 RAW_COLUMNS与normalise，保存原始返回必要字段与输入身份；缺字段/数值失败如实记录，不以已知价格或符号码猜expire_datetime。
- 使用一次性研究驱动，输出仅写本线`artifacts/stage024b_explicit_contract_probe/`；不修改已冻结Stage024工具/产物、共享源或生产。
- 运行前过拟合判断：否，本探针没有收益标签或模型选择；继续价值：是，可区分列表遗漏和历史元数据边界。reviewer0，没有新增回测指标。
