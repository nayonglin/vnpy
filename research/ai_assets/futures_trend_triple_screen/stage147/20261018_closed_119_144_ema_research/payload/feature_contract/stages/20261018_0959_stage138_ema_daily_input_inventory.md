# Stage138：EMA 日线与 u 时执行 tick 输入接合盘点

- line_id：`futures_trend_triple_screen`；时间：2026-10-18 09:58—09:59 CST；性质：有界只读输入证据，非重要突破、新数据资格、金融 readiness 或正式臂。
- 已读 registry、既有 LINE、Stage121/123/124/126/127；本线尚未入 registry，本次不修索引。按 root 分工只新增本文和 `outputs/stage138_ema_daily_input_inventory/`，不改旧源、LINE、Git、135/136文件；不派子 agent。
- 原B真实失败与134独立结论沿用；本次没有重启B、新账户、provider、下载、模型/训练、全历史 feature build、native 或旧 tests。

## 有限调研与判断

仅一组两项查询：`site.doc.shinnytech.com tqsdk get_kline_serial 86400 KQ.m real contract datetime is_changing`、`site:github.com/shinnytech/tqsdk-python get_kline_serial 86400 is_changing`；之后只在同组官方资料中打开/定位，没有扩搜或插件。

[TqSdk 官方合约与行情文档](https://doc.shinnytech.com/tqsdk/latest/usage/mddatas.html)区分真实合约与 KQ 主连/指数，K线 datetime 表示起点；[官方 GitHub API 源码](https://github.com/shinnytech/tqsdk-python/blob/master/tqsdk/api.py)给出日线86400、序列从最新bar向历史取数及持续更新语义。判断：请求周期、文件存在、末行存在都不能替代本机“已完成、同真实合约”的资格。沿013采用同symbol严格更大source id及更晚有效日线时间作为完成证据；不将网页或本次 hash 当价格全验证。

Elder机制判断继续引用121/123：逆向EMA限价是值得一次透明适配证伪的不同第三层，作者公开材料未唯一确定统计算法。本次不再定义EMA、选参数或声称原样复刻；13/26及实际-real-bar合同按124/126/127。

## 冻结 DB、字段与实际覆盖

唯一实际盘点命令为 `.py311/bin/python research/lines/futures_trend_triple_screen/outputs/stage138_ema_daily_input_inventory/inventory.py`；工具chunk `25dc9b`，真实 **exit 0**，1.753292秒。终态保存在 `actual_terminal.json`。一次只读SQL会话使用 `mode=ro&immutable=1`、`PRAGMA query_only=ON`；读取前后DB及sidecar stat完全相同，无WAL/SHM，未复制、更新或checkpoint DB。

| 证据 | 实测结果 |
| --- | --- |
| `.vntrader/database.db` | 112,726,016 bytes；SHA `273f0bc18de3070e4e085e4d6585fba71d6e1bb1256e3c7fb5adfc6532836a54`，与027、013及原A_OFF preflight相同 |
| 027相同scope | `interval='d'`、2019-06-01至2026-10-14、仅accepted metadata；116,394行，533个有数据真实合约，实际首日2019-06-03 |
| metadata | 806合约，均通过真实合约代码/非alias连续校验；273个在此区间无行，不等于273个数据缺口 |
| 完整日线字段 | DB已有 `open_price/high_price/low_price/close_price/volume`，无需从分钟或native重建；NULL、非法OHLC形状、负量、同合约日重复键均0；全为本地午夜datetime |
| 原日历 | 与 `stage005_potential_signal_demand/global_engine_calendar.csv` 的1,786日逐日相同；SHA `a3edfab95f284cc368be2712127c2900197ff4c6dfb62cba62a651de1c1137f3` |
| 零量 | 1,468条DB日线volume=0；不能据此认定为carry或新增正量门 |

027源码直接SQL读DB中的目标metadata合约，并未调用native loader，也未按产品拼接；其FI已有结果的 `fi2_daily.csv` 不是日线源，缺open/OHLC等完整字段，不能直接喂127。当前SQL计数/结构检查和四个OHLCV样本均值差0，仅证明限定scope与样本接合，**不证明116,394行全部价格/完成性独立认证**。

原A_OFF preflight SHA `c8c1d1bfcc5faf61be9e170f5ae6998557e856e2c9aff2fb2434de08452e7ad2`，context SHA `c7e861612f4635bb40ff79ed278822ee369dd5caa581fc02b8e7e122f38153d6`；旧data stack manifest SHA `2b650761fbf2bc30aa0046147b7e369a2a0a10a68ee6b520204dde8d4d7226a0`。本次只读此身份及有限来源，没有重hash其4,639/7,663级大闭包、重跑旧数据栈或继承旧金融owner。

## carry、零量及缺session

真实活动MRO为847→840→827→502，四源SHA均与A_OFF一致。**502 `ConfirmedDailyNextRealOpenEngine.new_bars`** 在 `history_data[(dt,vt)]` 缺失且已有旧bar时，现场构造 `open=high=low=close=old.close` 的BarData，仅写引擎 `self.bars`；并不写DB，也不加入本日传给strategy的真实 `bars`。vendor与旧SameDayClose也有类似补值，但本次以实际502路径为证，未运行native。

DB导入器 `import_tqsdk_all_futures_daily_to_db.py:93` 则将原CSV的OHLCV逐行直接转为BarData，datetime明确上海时区，无缺日forward-fill。其SHA `0fd37e73b40a7c104eacc9acf9b2e456559cf1ebdcef0c8ce9acc2fd578255cb`。013旧排除的16个carry诊断键，本次逐键只读SQL均 **0条真实DB行**；因此这些是loader后补，绝不能导出到EMA。

有限零量反例：`AP101.CZCE/2021-01-14` 在原CSV与DB均为OHLC5778、volume0、OI51；原CSV下一日为5700、volume1。原CSV SHA `0e05dbebb1f6510cfd2d72d79d8dc5e0b94b361d091c48b12bd2e8f45bf64dc4` 匹配A_OFF。它证明至少此零量行原来已经存在，并非native后补；原CSV没有provider serial，不能把“有下一CSV日期”夸成013式serial完成证明，也不外推认证其余1,467条。

124没有“日线volume必须大于0”的规则。规范化时应保留已获真实来源资格、OHLC合法且volume有限非负的零量bar；缺真实key、carry、冲突或不合格bar不得填平/压缩，按原global calendar中断并重暖机。127 `build_ema_rows` 只验OHLC与日历连续性，**不会替调用者识别carry或授予来源资格**；qualified_keys必须先排除不合格来源。分钟volume的 `V>=q` 是D撮合合同，不能倒用为u日线正量筛选。

## 现成精确资格与最小规范化接合

- 013 `network_attempt1/qualified_daily.csv` SHA `89cd6502bba89bb32fce4ca032adb1266a8978b91fd7f1b0e1519aa464df6833`；独立receipt SHA `194e48847c9e0927772c482cd5bacc3529a625ac76aeec2a157089924177c795`，仅 **4,500个精确键/94合约**，不认证94份raw全历史。两条no_forward_successor拒绝与16个carry排除仍保留。本次3个跨期样本与DB OHLCV差0。
- A_OFF绑定34个 `qualified_daily.csv` 路径，属多个旧精确请求，可能重叠；本次只列已声明path/SHA，不重新聚合认证。原FI的533个合约中，400个原daily文件存在，397个进入该preflight；133个原路径缺失不等于DB缺行或没有其它已接受替代来源。该数字只为来源清单，不是下载清单。
- 013/原daily CSV含 `trade_date,datetime,...`，schema不等于127严格的 **`date,vt_symbol,open,high,low,close,volume`**。目前没有可直接调用 `load_bound_daily_csv` 的全scope规范化CSV与独立exact-key绑定；不能把013的4,500键外推成116,394键，也不能把138 inventory SHA当qualifier SHA。已达38根的覆盖未在本阶段计算。

最小下一步由root另做一次**研究级规范化绑定**：以相同已接受冻结DB、producer/carry边界及有限跨源证据为基础，明确可继承的日线scope/key资格，再在DB无非空WAL、只读稳定快照下导出上述七列；`date`按原上海本地日语义、`vt_symbol=symbol+'.'+exchange`，只保留原metadata及原时间范围，绝不从native `self.bars`取值/补session/拼连续价。保存导出CSV SHA、原DB SHA、参数/日历SHA、exact `(vt_symbol,date)` 集合及资格文档/原receipt的绑定，核导出数值/键未变。127从同一bytes hash并解析，传入 `qualified_keys=frozenset(...)` 与该独立资格SHA；本次没有执行导出或新资格。

这一步可以复用已接受DB源，不要求逐bar重新认证全市场、重新下载133合约、重审7663来源或重算旧FI。若个别key无法继承资格，留下明确缺口并按124重暖机/unknown；不能默授资格，也不能按收益选择删日。

## feature.execution_tick 的既有唯一规则

接受参数来源：A0 `effective_parameters.json` SHA `c49a2560d687bd506705e1ce7bd8cfee2fecb697869f1c51da3c6f7f1debfa61`；A_OFF实际参数SHA `c4f585ad2349b57aa5c39ea2591c576925ecdf7b17d22ef41bea6b919d8306e4`。两者806合约的 `contract_sizes/priceticks` 完全相同；lc configured tick=20。原成本/风险tick仍按accepted metadata，不做新规格选择。

执行规则源 `qmt_roll_intraday_execution.py:66`，SHA `95de37e240ed5f34e8370cf9652e958c3c44fa3f36bef1d905c3e757a8304272`：仅 `lc[0-9]+.GFEX` 在 **执行交易日D<2024-12-18** 返回50；其余返回该真实合约 `parameters['priceticks'][contract]`。027本来就按 `next_day[u] or u` 调它；127 engine按D再算并要求与冻结intent完全相同，mismatch应失败，不能D内改L救单。

因此未来给 `(u,contract)` 的feature补字段应为：在u已知 `D=next_session(u)`、且规格变更在u已公开时，`execution_tick=effective_pricetick(contract,D,accepted_configured_tick)`；附D、规格source/basis及known-asof。没有下一D则不生成订单；未来规格尚未u-known时保持unknown，不回退configured风险tick。此处用已知日历和已知规格，不读取D最终价格。

root另行取得的公告时点证据闭合唯一变更边界：[交易所原文地址](http://www.gfex.com.cn/gfex/tzts/202412/917905b781b040d1bfc189c0b5559d24.shtml)本轮root访问400/timeout；成功读取[南华转发的广州期货交易所署名337号原文](https://www.nanhua.net/news/2024/12/b0c7febb-514a-422c-8b9c-386f640b37a1.html?updatetime=short)，原文日期2024-12-06、转发时间16:56:08，规定12/17结算起改20及12/18首笔成交价规则。**推论：u=12/17完整收盘后为D=12/18准备时，20已事前公开**；直接拿 `effective_pricetick(contract,u,20)` 会错误得到50。此证据由root完成，本agent不再扩搜或假称官方直连成功。更早u发往D<12/18仍为50；12/17夜盘按D=12/18归属用20。原风险minimum-risk/成本tick不随此执行规则改写。

## 终态、变更与反思

产物：`inventory.py` SHA `7daef24f2a7077c3ebded724baabe69536467b6fa7bb60371e80921d0376bead`；`inventory.json` SHA `01d8c0bd0aae3a15326fca2173d193da36d471cd96e5d5af0415cbac210d42a4`；`bounded_followup.json` SHA `6de842800f3dc9e96d7886b6480ec5909c0dbbbbac1b430eb0bc866ae9c07a3a`。后者有限补读与source存在性统计实际chunk `a9fc4e` exit0；前一次可选AP101探针因未指定utf-8-sig识别BOM字段exit1，已记录，修正只读解析后exit0，未重查DB。

新增仅138盘点脚本/证据/本文；新增、修改、删除策略参数均0，回测结果均0；期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率均N/A。金融/feature/native/模型/provider调用0；本阶段无需回测结果独立审计，不自签数据资格，`financial_ready=false, production_qualified=false`。

开始/结束**新增过拟合：否**，固定源、字段、tick与carry边界，无收益筛选或参数搜索；历史选择偏差不因此消失。开始/结束**继续价值：是**，本次已把后续一次规范化与feature build所需接缝和真实未决说清；证据已足，本盘点到此收口，不继续无限清洗或扩市场。下一步有价值的是root一次规范化资格后真实build，不能把来源盘点当alpha、金融readiness或目标完成。LINE/registry/memory/back_log由root按合入需要统一处理，本次不改。
