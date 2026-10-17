# Stage266 最终清洗库与旧主库的全量价格重叠核对

- line_id：futures_trend_rollover_shape_same_volume；时间：2026-10-17 19:20 CST。
- 受root委托的最后一次有界独立准确性检查；不追差异根因、不纠数、不修改清洗合同、原始数据或主库。是否重要突破：否，是价格重叠验收。
- 开始过拟合判断：否，不使用收益或策略结果；继续价值：是，最终库应与既有价格历史在共同合约日期上可解释地对齐。

## 结果

- 最终清洗库 `outputs/stage266_clean_daily/clean_daily.sqlite` 实际SHA与root指定一致：`4191dc61218b8f4cc804f239f46f099769bd34beddff74929e284a51dc1bd598`，共1,552,466行。
- 与只读旧主库 `.vntrader/database.db` 共同812,865个合约日期键、4,398真实交割年月epoch；四价逐字段精确相同812,855键，异10键。绝对误差1e-8复核后仍是10键，因此没有浮点微差伪冲突。
- 所有10差异都在2026-04-20或2026-04-21，clean所选来源全部rqalpha；按所CZCE2、DCE5、SHFE3。只是两库观测不同，不因旧库存在就宣称其为正确真值；数量与OI不作比较。
- 非共同键739,601不被当作不一致或缺失；旧库没有目标内全历史覆盖，本轮只比较精确共同键。

| clean所选来源族 | 共同键 | 四价精确相同 | 异 |
|---|---:|---:|---:|
| official | 12,591 | 12,591 | 0 |
| old_tq | 772,305 | 772,305 | 0 |
| recent_tq | 442 | 442 | 0 |
| rqalpha | 27,527 | 27,517 | 10 |

| 所 | 共同键 | 四价精确相同 | 异 |
|---|---:|---:|---:|
| CFFEX | 33,619 | 33,619 | 0 |
| CZCE | 214,925 | 214,923 | 2 |
| DCE | 240,930 | 240,925 | 5 |
| GFEX | 16,204 | 16,204 | 0 |
| INE | 45,339 | 45,339 | 0 |
| SHFE | 261,848 | 261,845 | 3 |

2015–2025每年共同键均全部四价相同；2026共同18,217键，其中18,207同、10异。按年、所、所×年、全部source_id和source family的完整分组在JSON。

## 精确连接与只读保证

两个SQLite均使用URI `mode=ro`，连接启用query_only。利用旧主库已有(symbol,exchange,interval,datetime)唯一索引，interval固定d，datetime精确为同一trade_date的00:00:00；独立确认旧库所有日线时间确为午夜。

- CZCE：由clean完整YYYYMM取后3位，前接大写PRODUCT；同时严格同交易日连接，原完整epoch留在结果，不把十年同名合约跨日期拼接。
- CFFEX：大写PRODUCT+YYYYMM后4位。
- 其余所：小写product+YYYYMM后4位；F合约从PRODUCT的字面`_F`后缀恢复交易所F后缀，避免SQL通配符混淆。
- 每个旧库row_id最多只连接一个完整epoch，跨epoch重复旧行0；没有连接连续合约，没有读取或比较旧DB.open_interest。
- 两个输入的字节数和mtime_ns执行前后完全相同。没有重hash大原包、重跑units、写主库或修数据。

## 证据与后续边界

- 可复现工具：`tools/stage266_legacy_db_price_overlap.py`。
- 汇总：`outputs/stage266_clean_daily/stage266_legacy_db_price_overlap.json`，SHA `ef29eacd0b3cb892e9a032a125d3279739ef8d9704d351b60d9afb7fc031d6ac`。
- 10行完整差异CSV：`stage266_legacy_db_price_overlap_differences.csv`，SHA `45a8002f25c0270f41d51fe4b718827f02554e347587705b26e4e2f9608f74f4`；每行保留完整epoch/date、old row_id、两组OHLC、不同字段、clean原始定位，供root决定保守隔离，不在本轮改清洗库。
- 差异键：CZCE.SR.202605/202609（04-21）；DCE.A.202605/202607、J.202605（04-20），DCE.PG.202605/202607（04-21）；SHFE.AL.202605/202606（04-20），SHFE.ZN.202605（04-21）。
- 价格交叉核对执行PASS，P0=0；P1=1限这10个尚未证明哪源为真的价格分歧，不应对全812,865键声称百分百相同。
- 新增/修改/删除策略参数无，训练0、回测0、财务指标不适用。只新增本工具、JSON、差异CSV和本唯一stage，不改LINE/registry。
- 结束过拟合判断：否，纯价格验证且没有收益反馈；继续价值：有界验收已完成，保留10行证据交给root，无需追逐根因或重下数据。
