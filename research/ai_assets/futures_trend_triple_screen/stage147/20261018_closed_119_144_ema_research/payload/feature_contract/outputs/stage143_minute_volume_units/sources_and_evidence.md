# Stage143 查询与有限证据

2026-10-18 10:09 CST；只读核查，不是数据资格或金融receipt。Stage140开始/结束均应为SHA `86fbb20d85a3c74d42dc72e99e22fdb08f5863cb9b4d1f52920399e19d851d6c`。

## 两组查询（没有第三组）

组1：`2020年1月1日 成交量 持仓量 单边 统计 上期所 大商所 郑商所`；`site:doc.shinnytech.com tqsdk volume 单边 成交量`；`site:github.com/shinnytech/tqsdk-python 成交量 单边`。

组2：`site.shfe.com.cn "2020年1月1日" "单边" "成交量"`（该条实际写成site.shfe，非严格域过滤）；`site:dce.com.cn "2020年1月1日" "单边"`；`site:czce.com.cn "统计口径" "2020" "单边"`；`site:gfex.com.cn "成交量" "单边"`。

结果选择只采用协会官方说明、交易所官方细则、交易所署名公告镜像、TqSdk官方文档/GitHub；新浪/澎湃/普通投资者站点等搜索结果未用作技术结论。7hcn上期所答记者问页面正文open失败，不作为已成功读取的完整原文。

## 实际读取的网络来源

- https://www.cfachina.org/inv/wqbh/rxwd/202302/t20230208_36029.html ：成功，页面正文时间2022-12-23，网页路径2023-02；实时行情定义与2020统一改单边。
- https://www.bocifco.com/newsinfo.aspx?cid=3&id=15893 ：成功，2019-08-02上海期货交易所署名公告镜像，能源中心相关定义自2020-01-01改单边。
- https://www.shfe.com.cn/regulation/ineregulation/businessmethods/trade/202609/t20260914_833389.html ：成功，2026-09-14现行能源中心细则；不独自承担历史起点证明。
- https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.api.html ：成功，线上3.10.3；get_kline_serial的bar期间volume定义、insert_order期货手数；页面find单边无匹配。
- https://doc.shinnytech.com/tqsdk/latest/usage/mddatas.html ：成功，真实合约与行情字段；没有用它声称单双统计保证。
- https://github.com/shinnytech/tqsdk-python/blob/master/tqsdk/api.py ：成功，官方源码同期间成交量定义；页面find单边无匹配。
- https://www.gfex.com.cn/ 及 http://www.gfex.com.cn/ ：均返回400/timeout，GFEX专门历史条款未取得。
- https://www.7hcn.com/article/358881-1.html ：搜索摘要显示上期所答记者问，但正文open 400/timeout，未冒称完整成功。

## 本地实际路径与SHA

均相对于`/Users/mac/Desktop/fian/`；只读源码/已有证据，没有import或执行provider/SDK。

| 路径 | SHA256 | 本轮用途 |
| --- | --- | --- |
| research/lines/futures_trend_triple_screen/tools/stage012_provider_batch.py | 6c2d949f2c38baded87fea4904af1bf7a01d1a4050b16ecb15d8d97c66c8e155 | collector逐字段float原值→DataFrame |
| research/lines/futures_trend_triple_screen/tools/stage087_off_data_provider.py | 33b6bca67115e3c8438de768b6e180d055139470fa2b7069b7a4459b1d101b46 | 实际60秒Kline订阅路线 |
| research/lines/futures_trend_triple_screen/tools/stage041_exact_daily_request_provider.py | e4320208cc70d25959db7f66b80518ac0f6ceaaf3e6a61a97bdfc23f008bfa0d | 原collector/save CSV，无缩放 |
| .py311/lib/python3.11/site-packages/tqsdk/api.py | 264fff3e3979a156294d8bca745c8aa6c26136c8cbe58ef2bc7ceffd8b811c96 | 本机SDK期间成交量注释 |
| .py311/lib/python3.11/site-packages/tqsdk/objs.py | e348cccd0da94559a19fcb771b0942d8424d8adcb99bb0291e3b61b062558bdc | Kline.volume int，未说明单双 |
| research/lines/futures_trend_triple_screen/outputs/stage008_independent_review/review_receipt.json | aab0b7062ff32e67d4fdf2f3132b00188c5779cf59c1462144f002a7b25ddaa6 | 已有345根精确研究资格，不扩权 |
| research/lines/futures_trend_triple_screen/outputs/stage008_oi_requalification/field_checks.csv | 4bcd6656091f850fb70ba4b45216dee1984fd4dcf0bb211c8157dabbcfb6e1e4 | 既有V聚合与CSV/DB均740132、差0 |
| research/lines/futures_trend_triple_screen/outputs/stage007_tqsdk_stream_probe/network_attempt1/raw_completed_minutes.csv | 0805e7083b24e988469bee78fabc53419d2855e85f92928256a184d9db9480ac | 只读header/两行，未新算聚合 |

本轮有限实证只有读取原008结果与两行raw，不重新运行其原审查，不授任何新exact-key资格。单个vendor分钟/日线内部一致不能证明单双，文中建议是明确披露的源级研究假设。所有绩效N/A。
