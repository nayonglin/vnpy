# Stage265 SHFE/INE/CFFEX官方全市场日线原包与隔离规范层

- line_id：`futures_trend_rollover_shape_same_volume`
- 当前模式：day数据补齐；本agent只负责官方reference层，不训练、不回测。
- 记录时间：2026-10-17 18:36 CST；主要操作约18:07—18:35，最终自验18:34:58。
- 工作区/分支：`codex/ai-training-data-expansion`；未改LINE、registry、根总账、主行情库或生产。
- 阶段性质：用户授权六所全品种、全部历史普通合约（含已退市）的公开日线扩展。
- 是否重要突破：否；是实质数据覆盖进展，不是策略/AI有效性或晋升证据。
- 是否触发A/B：否，策略参数、模型、训练和账户回测均未改动。

## 外部调研与判断

- 先读registry、LINE及Stage264已下载/规范记录。SHFE官方索引提供2002—2025历史年包和2026已发布部分，复用Stage2642014—2019六包，不重新下载。
- INE官方索引同构，提供2018实际上市后至2026部分；没有制造2010—2017的INE行情。
- CFFEX公开主页现链接`/cn/lssjxz.html`，页面自己的`/r/cms/www/default/js/sj-download.js`第75行明确`/sj/historysj/YYYYMM/zip/YYYYMM.zip`。正常官方HTTP可达、HTTPS连接超时；首包201004、近月202609和202610实取真ZIP后，按月顺序限速取得199包，避免数千日请求。
- 公开GitHub Akshare只作为路由参考读取，固定commit `4771e6ea34f6139f226e2bf4fab88ce17579831d`，文件SHA与初次main文件一致；未执行第三方代码。
- GFEX正常HTTPS证书主机名不匹配；正常HTTP页面和first/latest两次POST返回HTTP200 JS防护HTML而非行情JSON；普通IAB导航超时。未禁用证书验证、未解算JS挑战、未绕过验证码或访问控制。GFEX首品种实际2022-12-22上市，不虚构2010记录；官方reference本次未取得GFEX行情，通用层由root另取。
- 调研判断：优先官方整年/月原包能高效保留远月和已退市合约；官网原包也包含期权、镜像及不满足OHLC几何的报价，不能直接宣称全市场已具备可训练统一源。
- 主要一手来源：[SHFE下载索引](https://www.shfe.com.cn/reports/tradedata/datadownload/download.json)、[INE下载索引](https://www.ine.cn/reports/tradedata/datadownload/download.json)、[CFFEX历史下载页](http://www.cffex.com.cn/cn/lssjxz.html)、[CFFEX页面自身下载脚本](http://www.cffex.com.cn/r/cms/www/default/js/sj-download.js)、[当前SHFE日统计及单位说明](https://www.shfe.com.cn/reports/tradedata/dailyandweeklydata/?query_params=kx)、[GFEX首品种政府上市记录](https://jrjgj.gz.gov.cn/gkmlpt/content/8/8726/post_8726018.html?jump=true)。本地URL/原响应/SHA/commit见`official_source_research.json`。

## 本次变更

- 新增本线独有脚本：`stage265_exchanges_official_archives.py`、`stage265_exchanges_cffex_months.py`、`stage265_exchanges_tail.py`、`stage265_exchanges_normalize.py`、`stage265_exchanges_verify.py`。
- 正式脚本/配置修改、删除：0；策略/模型参数新增、修改、删除：0。
- 下载工程参数：年度原包上限96MiB，外层ZIP展开上限1GiB；无自动重试，普通GET支持Range续传，已完成包以SHA/字节/ZIP CRC核对后跳过；逐包约0.35秒间隔。不开账户凭证、环境代理或netrc认证。
- 规范器仅读本地XLS/XLSX/CSV/JSON，XLS用xlrd，XLSX用标准库XML；未新增解析依赖。缓存仅在raw/parser/输出SHA一致时复用，不冒称跳过验证。
- 最初14次尾部旧路由返回HTML已停并隔离失败记录；核对公开源码与现行页后使用`/data/tradedata/future/dailydata/kxYYYYMMDD.dat`的`o_curinstrument/report_date`。14份正确尾部已取得；保存后的tail工具不冒认此前内联下载入口，另做全离线核验。
- CFFEX20250314到期债券合约T2503等原CSV使用`null`表示空OHLC，首次规范停止；先重现`number('null')`失败，随后只把该缺值保留为None。真实T2503回归验证保留close107.75、volume0和empty open，不补0价格或前值。所有脚本编译通过；5项字段语义断言及该真实回归通过。

## 数据合同、参数与边界

- 目标完整交易日：2026-10-16；保留官方更早历史。SHFE年包2002—2026、INE年包2018—2026、CFFEX月包201004—202610。
- SHFE/INE2026年包实际均2026-01-05—09-30；10月08/09/12/13/14/15/16各7份尾部补到10/16。CFFEX202610包自身已有这7日。
- 普通合约使用字母1—3位+YYMM识别，明确YYYYMM交割epoch；期权/TAS/汇总等保留raw并计数，不混普通候选。SHFE发布源含INE镜像，按sc/nr/lu/bc/ec归属剔除SHFE源镜像、优先INE自身源；日期是交易所交易日，不是盘中/UTC时间戳。
- 公共schema：exchange, product, source_symbol, contract_yyyymm, date, OHLC, volume, open_interest, source_id, unit_regime；另保留contract_epoch_id、vt_symbol、settle、pre_settle、turnover、oi_timing、原成员/表/行和row_quality。
- OI明确为收盘持仓，非既有TQ importer的open_oi；V/OI和成交额均保留原数，未机械除2或混源。明确脚注者标双边/单边；没有脚注者保留unknown。unknown涉及部分早期以及近年XLSX，不能一概按年份推定；有效候选中unknown为188,965行，具体来源见catalog。
- 零成交缺价不造K线，单列no_trade；所有不合格普通报价保留_rejected。官方4条close在H/L之外、26条非零成交缺OHLC/close0等仍隔离，可能涉及交割定盘语义，未自行纠价。
- 观察到的首末日期不等于上市/退市元数据认证；不据此声称全部生命周期连续性已通过。

## 结果与自验

- 年度来源34（28新增、6复用），月度来源199，尾部日来源14，共247source；233ZIP+14JSON。原包/尾部总378,216,882字节，含复用Stage264 21,606,045字节；新增356,610,837字节。所有.part已完成。
- 实际读取6,949,142条有日期原记录，规范有效普通合约日747,972；SHFE617,437、INE62,837、CFFEX67,698，33产品，4,425交割epoch（SHFE3337/INE396/CFFEX692）。
- 镜像原行剔除42,007；期权/TAS/汇总等非普通记录5,970,183；零成交缺价单列表188,950；其余不满足OHLC条件30条。原包保留全部原记录。
- 747,972是镜像处理后对实际gzip键的唯一计数，不能与RQAlpha或其他来源行数再次相加。全源SHA/字节、233ZIP CRC、14report_date、所有规范文件SHA/行数、747,972键唯一性、OHLC/V/OI几何自验通过；跨source重复键0、已接受非法OHLC/V/OI0。
- 10/16 reference合约census：{"CFFEX": {"ordinary_contract_count": 28, "accepted_ohlc_contract_count": 28, "zero_trade_contract_count": 0, "rejected_ohlc_contract_count": 0, "zero_trade_also_accepted_count": 0}, "INE": {"ordinary_contract_count": 63, "accepted_ohlc_contract_count": 50, "zero_trade_contract_count": 13, "rejected_ohlc_contract_count": 13, "zero_trade_also_accepted_count": 0}, "SHFE": {"ordinary_contract_count": 238, "accepted_ohlc_contract_count": 214, "zero_trade_contract_count": 24, "rejected_ohlc_contract_count": 24, "zero_trade_also_accepted_count": 0}}。ordinary计数是accepted/zero_trade/rejected合约集合并集，后两类可能重叠，不能相加；详表有每品种合约清单。
- 自验结论仅`pass_implementer_self_audit_not_independent_review`。root已安排独立CZCE agent读最终manifest、实际gzip/ZIP/hash与抽样，不把本实现者的自验冒充独立review。
- 新增/修改/删除回测结果均0；期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率均不适用。训练/回测/账户凭证/CTP/SMTP/订单API均0。

## 输出与复现

- 单一入口：`outputs/stage265_deep_daily/other_exchanges/official_reference_catalog.json`；全源明细、范围、原SHA/URL、规范SHA、unknown单位和限制。
- 原包清单：`official_archive_sources_manifest.json`、`cffex_month_sources_manifest.json`、`official_tail_sources_manifest.json`。
- 规范层：`normalized/official_normalization_manifest.json`、各SOURCE.csv.gz、SOURCE_no_trade.csv.gz、SOURCE_rejected.csv.gz及SOURCE.inventory.json。
- 质量：`official_self_validation.json`、`latest_trade_date_census.json`、`official_source_research.json`及原公开探针。原始数据全部ignored不提交Git。
- 离线复现：`.py311/bin/python research/lines/futures_trend_rollover_shape_same_volume/tools/stage265_exchanges_tail.py`；`stage265_exchanges_normalize.py --resume`；`stage265_exchanges_verify.py`。后二者默认全程离线；重新下载须显式--download。

## 结论与反思

- 本阶段结论：官方reference原包及普通期货隔离规范层补齐到10/16，GFEX官方仍受阻；统一量/OI/上市元数据和跨通用源验收未完成，不宣称已具备正式训练或生产资格。
- 是否进入下一步：可交独立review与root统一候选源验收；不训练、不跑财务回测、不改正式材料。
- 运行前/后过拟合判断：均否。来源和完整历史目标在运行前固定，没有依据收益挑产品、日期、阈值、模型或利润曲线；后验数据修订/源单位风险继续显式保留。
- 运行前/后继续价值判断：均是。远月、退市与早年日线实物已显著扩大；下一步价值是复核和数据合同，不是跳过unknown、拿不完整历史重新拟合。
- 合入建议：本agent不更新LINE/registry/根memory/back_log，由root合并独立review后统一整理。
