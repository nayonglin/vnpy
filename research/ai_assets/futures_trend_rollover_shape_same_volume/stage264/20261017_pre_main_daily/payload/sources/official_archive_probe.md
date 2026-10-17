# Stage264 官方交易所归档公开探针

记录时间：2026-10-17 17:39 CST。研究线 `futures_trend_rollover_shape_same_volume`。本报告描述独立执行的公开来源探针及随后明确授权的六年官方原包下载；TqSdk、Sina、EDB 结果由其他 agent 记录。没有修改主数据库、策略、原配置或环境。

**实际进展：上期所官方 2014—2019 六包全部下载成功，21,606,045 字节、17 个真实 XLS 成员，最终离线 SHA/ZIP/CRC/索引绑定核对全部通过。原包已交独立 parser 做逐日质量和覆盖验收，尚未写数据库。郑商所年度包被 412 拦截，大商所历史入口连接超时，均未继续重试。**

## 首轮五次公开 GET

所有显式探针使用正常 GET、无认证、无 cookie、无代理/`.netrc` 自动凭证读取，无自动重试；单响应上限 20 MiB。发生拦截后没有处理验证码、执行 WAF 挑战或枚举替代 URL。

| 目标 | 实际结果 | 响应字节 | 解释 |
| --- | --- | ---: | --- |
| CZCE 2015 `FutureDataHistory.zip` | HTTP 412，HTML，非 ZIP | 2,845 | 未获得年包，不能断言历史不存在或一包覆盖全部合约 |
| SHFE 2015-01-05 `kx20150105.dat` | HTTP 200，`application/json`，真 JSON | 51,448 | 有明确报告日期、普通合约与远月数据 |
| SHFE 官方数据下载页面 | HTTP 200 | 122,231 | 页面从 `./download.json` 加载年度下载索引 |
| SHFE 页面引用的 `report_date_download.js` | HTTP 200 | 4,982 | 使用 `data.historicalData`，`type=1` 选择期货，再按 year 匹配精确 url |
| DCE 官方历史数据入口 | `ConnectTimeout`，约 16 秒，无 HTTP 状态 | 0 | 未获得历史索引或年度文件；未猜测 histdata 年度文件名 |

请求时刻、完整 URL、HTTP 元数据、返回体 SHA256 和本地隔离路径均在 `official_archive_probe.json` / `official_archive_probe_requests.json`。四个实际响应保存在 `official_archive_probe_raw/`；DCE 超时没有响应文件。

## 上期所 2015 日文件实际内容

请求：[官方 2015-01-05 日行情](https://www.shfe.com.cn/data/tradedata/future/dailydata/kx20150105.dat)。原始响应 SHA256：`081e0f49525c9e77d9940429bce7b9769ec3f55d3eb7e575c48915b5d53e6fd7`。

- `report_date=20150105`、`o_code=0`；原始 `o_curinstrument` 共 149 行，排除小计/合计后 136 个普通合约，12 个产品。
- 存在字段：`PRODUCTID`、`DELIVERYMONTH`、`OPENPRICE/HIGHESTPRICE/LOWESTPRICE/CLOSEPRICE`、`PRESETTLEMENTPRICE/SETTLEMENTPRICE`、`VOLUME`、`OPENINTEREST/OPENINTERESTCHG`。
- 其中 42 个普通合约成交量为 0，开盘/最高/最低为空；严格正数 OHLC 门下不能用作正常 bar。这 42 行全部是零成交行，不能据此称供应商数据损坏，也不能补造价格来制造 AM120。
- 94 行通过基础正数 OHLC 关系检查；此检查不等于全寿命、跨源一致性或交易日完整验收。

| 交易日 | 普通合约 | 开 | 高 | 低 | 收 | 结算 | 原始成交量 | 原始 OI |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2015-01-05 | rb1505 | 2,550 | 2,570 | 2,540 | 2,560 | 2,556 | 2,891,694 | 2,212,768 |
| 2015-01-05 | rb1510 | 2,583 | 2,598 | 2,574 | 2,589 | 2,587 | 159,400 | 373,514 |

官方日文件确实有不同到期月份，支持“全部挂牌合约日线而非仅主力片段”的可行方向；`rb1510` 是否处于本研究映射中的 pre-main，仍应由原冻结映射具体核对，不能凭月份远近替代该检查。

该历史文件 `update_date=20151218 19:47:24` 晚于 `report_date`。当前拿到的是官方事后归档，不能声称它就是 2015-01-05 收盘时的发布字节，也不能借此认证当时历史保证金或数据未修订。

## 归档路线与当前边界

上期所原始 [数据下载页](https://www.shfe.com.cn/reports/tradedata/datadownload/) 和其引用的 [公开下载脚本](https://www.shfe.com.cn/images/report_date_download.js) 共同给出明确流程：读取 [官方年度索引](https://www.shfe.com.cn/reports/tradedata/datadownload/download.json)，从 `data.historicalData` 选 `type=1`、目标 year，再使用索引里的精确 URL。不要猜 ZIP 文件名或逐日遍历所有日期。root 已保存索引及其六年选取清单，SHA 见年度状态清单。

2015 首包于 `17:34:54—17:35:02 CST` 下载成功：HTTP 200、2,284,105 字节、SHA256 `79ffb605f4a1b4d786e772f683201a50b3c55b147b1dfd992a2a5e3ccef8b36c`；成员 `MarketData_Year_2015.xls`，解压 9,678,336 字节，OLE XLS 签名正确。root 随后处理 xlrd 2.0.2 解析依赖，本 agent 未安装包。独立 parser agent 核对唯一 sheet `所内合约行情报表` 为 37,695×15，表头含合约、日期、OHLC、结算、成交量、成交金额、持仓量；远月 `rb1510` 的 2015-01-05 四价与上述官方日 JSON 一致。原包脚注明确成交量/OI 为手、双边计算。合约分组后续空单元格需有边界地向下填充，遇页脚重置，禁止把页脚当 bar。

首包通过后才请求其他五年；六年的唯一下载账本为 `shfe_official/year_download_status.json`，原包在 `shfe_official/raw_years/`，这些数据路径已被 Git 忽略。下载只按索引精确 URL；每包上限 32 MiB，校验 ZIP 和 CRC，完成包复核 SHA 后跳过，不覆盖既有原包。部分老包 ZIP 成员名存在 CP437/GBK 展示乱码，应以成员对象读取并保留原始标识，不因文件名不一致误判无数据。

最终于 `2026-10-17 17:39:29 CST` 离线核对六包 SHA、字节数、所有成员 CRC、所有成员 OLE XLS 签名、原始官方索引 SHA、年份/URL 集合及 Git 忽略规则，全部通过。2019 特别是 12 个月文件，ZIP 内成员次序不是月份次序；其余五年各一个 XLS。完成的原包将被校验后跳过；这里的断点是按已完成年度保留，不声称已实现 HTTP 字节 Range 续传。

| 年份 | 原包字节 | XLS 数 | SHA256 前 16 位 |
| --- | ---: | ---: | --- |
| 2014 | 2,049,865 | 1 | `dd9f0a225696d1849` |
| 2015 | 2,284,105 | 1 | `79ffb605f4a1b4d7` |
| 2016 | 1,815,988 | 1 | `71b8996857b26a5c` |
| 2017 | 1,847,623 | 1 | `f2a2f754f7000255` |
| 2018 | 3,339,665 | 1 | `feb7cf908c0f748f` |
| 2019 | 10,268,799 | 12 | `e2f25d9e02facde9` |

完整 URL、本地绝对路径、64 位 SHA、开始/结束时间、HTTP 状态和成员清单只维护在唯一年度状态 JSON。当前 `batch_complete=true` 与 `all_archives_integrity_verified=true` 仅代表下载和文件完整性；不代表所有年份数据已获策略使用资格、pre-main 全覆盖或 AM120 就绪。

下载完成后另将复用工具落盘为本线 `tools/stage264_download_shfe_years.py`，默认只展示计划，`--verify-only` 无网络、无状态写入；5个离线边界测试通过，并对真实六包/17成员离线复验通过。工具源码SHA与“原包由先前内联命令取得”的时序都在唯一年度状态中说明，避免把后补脚本当作历史执行来源；离线证明为 `shfe_official/download_entrypoint_offline_verification.json`。

CZCE 本轮测试的是 [2015 年包地址](https://www.czce.com.cn/cn/DFSStaticFiles/Future/2015/FutureDataHistory.zip)，直接返回 412；[官方历史页](https://www.czce.com.cn/cn/jysj/lshqxz/H770319index_1.htm) 的浏览工具读取也被 412 拦截。年度包有待通过正常可用入口取得真实 ZIP 后再查成员和字段，本轮无法确认“一包是否覆盖全年全部普通合约”。

DCE [官方历史入口](https://www.dce.com.cn/dalianshangpin/xqsj/lssj/index.html) 连接超时；未认证具体 histdata 年包的精确 URL、格式、覆盖或体积。不能把第三方年包列表、月报 PDF 或当代日行情 POST 当成已经取得旧年度日线。本轮后续按 root 指令停止 DCE/CZCE 请求，留作独立路线。

## 判断

开始和结束判断均为：本轮不构成新增过拟合，没有模型、阈值、收益排序或账户回测；仍保留既有源的后验性。继续价值为是：SHFE 已取得真实旧普通合约和远月数据，年度包可以实质改变 Stage263 的 AM120 数据条件。但当前只接受原始来源探针；完整 pre-main、全寿命、逐日质量、历史成交量/OI统计口径和跨源重叠一致性须由独立解析/复核验收。

本轮新增/修改/删除策略参数均为 0；期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数和胜率不适用，没有跑回测。
