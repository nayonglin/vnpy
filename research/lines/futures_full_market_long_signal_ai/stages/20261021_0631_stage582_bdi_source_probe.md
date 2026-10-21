# Stage582 BDI新观测单响应试取

- line_id：futures_full_market_long_signal_ai；模式day；记录时间2026-10-21 06:31 CST；分支codex/ai-training-data-expansion。
- 非重要突破；仅新源可执行性，不是AI或策略收益证明。前轮578为实际progress；本轮独立于正式C9。

## 调研与判断

先读registry/LINE并对本线stage/source小清单搜索BDI、Baltic、GoodsIndexService、spot_goods，未发现已用BDI信息；不得将‘其他商品/运价’sector标签或INE.EC期货当作已有BDI外部数据。

- [原作者Bakshi/Panayotov/Skoulakis2010](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1747345)研究BDI增长与全球股票/商品指数/经济活动预测关系，并非中国全品种窄损策略盈利证明。
- [2024中国期货/BDI原作者研究](https://www.sciencedirect.com/science/article/pii/S027553192400240X)的重要方向是用中国期货预测BDI，不能倒过来引用为BDI预测中国期货。
- [AKShare维护源码](https://github.com/akfamily/akshare/blob/main/akshare/index/index_spot.py)明示新浪GoodsIndexService，BDI/GP/PB是不同symbol，本轮只取BDI；不安装该库，不复制dropna清洗成已完整样本。
- [Baltic官方2018-02-28通告](https://www.balticexchange.com/en/data-services/Circulars/market-announcements-/category-a/2018/circular-08-18---changes-to-the-baltic-dry-index--bdi-.html)明确2018-03-01改为40% Cape/30% Panamax/30% Supramax并移除Handysize，乘数0.1。不能混淆2017计划日期与最终生效日。

我的判断：航运运费受需求和船队供给共同驱动，增长不自动为商品多头利好；作为不同信息对象值得一次小源验证。英国日与中国source日/夜盘不同，网页当前历史响应不能证明首发PIT；不存在尚未核证的13:00或21:00固定发布资格。

## 唯一实际请求

- 原URL：https://stock.finance.sina.com.cn/futures/api/openapi.php/GoodsIndexService.get_goods_index?symbol=BDI&table=0
- 单次GET，exec40674终态exit0；HTTP200，852412B，SHAc825f71fbcfef651fb78720f6655c1d0b946f9ee75ee35c5568aa1742dac17ac，请求耗时2.405253秒。
- 取得时间2026-10-20T22:28:48.388941+00:00至2026-10-20T22:28:50.777710+00:00，4127原records。没有第二次行情GET/翻页/批量采集，未执行native SQL/分钟/COMMON/cache读取。
- raw路径`outputs/stage582_bdi_source_probe/actual_run1/response.bin`，receipt同目录。原raw不改。
- 依维护代码gb18030解码的初次receipt中name出现乱码；原body编码需独立按bytes核，不把显示问题写成价格造假。首两opendate是0023-06-02/0024-03-20；不能静默补2000年或drop后声称全样本无误。尾两日期2026-10-09/12；实际可用年限、频率、重复和覆盖待583完整小源核。

## 变更、参数与结果

新增仅本stage/raw/receipt；未改策略/参数/模型。新fit0/cash0/SQL0；新增训练特征0，财务指标（期末权益/收益/DD/Sharpe/总滑点/交易次数/胜率）全部N/A。累计535实际fit/282完成cash及1旧partial不变。

583只审这份852KB响应和必要原作者/官方方法，不额外抓行情；先核编码、全行身份、日期/频率/价格，保留坏行和missing，再判断是否值得研究。源取得不授权新训练或资金，也不是全goal完成；完整98/95目标active。

## 前后反思

运行前过拟合风险：是，同史择题高风险；新增收益后调参：否，本轮未读BDI与策略盈亏关系。结束风险仍是，不能从连接成功推alpha。运行前继续小源验证价值：是，信息对象不同且单响应可取得；运行后是否进模型未知，等独审再裁决。原正式/生产/CTP/邮件/调度/Git不改，普通记录不追加根memory/back_log。
