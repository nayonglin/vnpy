# Stage396：取得并校验官方2010全国县级代表点

- line_id：`futures_full_market_long_signal_ai`；2026-10-20 14:01 CST汇总；实际ZIP请求/解析13:59:44—13:59:46 CST。
- 开始前已读registry及394的 `next_scope.json`。本阶段只补官方、早于2020的县级空间参考点，不修改390物理量、作物表、母域98产品/95家族、模型或账户。
- **结果：官方2010全国county Gazetteer已实际取得并完整解析，3,221个county/等价实体GEOID唯一、代表点缺失0。** 这是来源/结构进展，非策略重要突破、非alpha或金融回测。

## 官方资料定位与选择判断

1. [Census官方2010 Gazetteer页面](https://www.census.gov/geographies/reference-files/time-series/geo/gazetteer-files.2010.html)明确地理vintage为2010-01-01，并在Counties章节提供全国县文件，范围50州、DC、Puerto Rico；页面介绍坐标是representative latitude/longitude。人口/住宅字段后来添加，不以这些附带字段的更新时间改变地理vintage。
2. 为保存原页面而进行的stdlib同页读取返回403，失败记录保留，没有自动重试。网页工具已读到官方页面事实，但仅展示下载锚点标签，未展开完整href。随后在[Census官方QuickFacts定位参考](https://www2.census.gov/data/api-documentation/locating-quickfacts-data-points-in-data-census-gov-and-census-gov.pdf)的搜索索引正文中，“Land area…2010”部分明确列出下列exact URL；未下载该PDF，也未采用其2020文件链接。

唯一最终文件URL：

`https://www2.census.gov/geo/docs/maps-data/data/gazetteer/Gaz_counties_national.zip`

本次没有猜测一串文件URL、改用2020+地理、获取大地图或安装GIS。事前范围及来源定位记录在 `outputs/stage396_census2010_county_points/source_scope.json`。两项官方定位资料不等于严格历史字节vintage；实际下载仍是当前取回历史结构。

## 唯一实际请求、原件与原schema

新增单用途 `tools/stage396_census2010_county_points.py`：10,258 B，SHA256 `8b973842241f6100049f1cdbd5a60154d3973b117bac70cd740b978f0aca3970`。使用原 `.py311/bin/python` 与stdlib，只做语法解析检查，没有跑旧suite或再安装依赖。

实际handle `76987`，终态exit0，HTTP200，最终ZIP GET恰1次、0retry、0redirect。下载压缩上限2MiB、总解压上限5MiB，均未触及。

物料全部在 `outputs/stage396_census2010_county_points/actual_run1/`：

| 物料 | 字节 | SHA256 |
| --- | ---: | --- |
| 原 `Gaz_counties_national.zip` | 167,168 | `592fd19e5027658a4af44be22396561907032ec56b6fbd7ea2dc65ea9ddf4118` |
| 原 `Gaz_counties_national.txt` | 650,834 | `09800b5b16348449074db3905737c53e47c5448c3059ffc611b803c0d787e2eb` |
| 完整 `county_points.jsonl` | 2,624,552 | `eda4e2c18ae67f423ec93df6283778fcf5a6e531047fd719d8cd6ba6809024cc` |
| `manifest.json` | 4,319 | `735283bb8f936124f4bb2b7115747815585290ba7c9cd3113f3910de1c27ad2c` |

HTTP headers/status在 `source.response.json`，响应Content-Length167168，Content-Type application/zip，Last-Modified `2013-04-03T13:11:37Z`。这支持当前官方对象自述的较早修改时钟，不证明本机历史first-seen。

ZIP只有一个TXT成员，deflate压缩166,984 B、解压650,834 B，CRC32 `68130bbc`，完整读取时经zipfile校验通过。原TXT为tab分隔、cp1252编码；UTF-8严格解码失败后使用cp1252，原件字节没有转码覆盖。原schema：

```text
USPS GEOID ANSICODE NAME POP10 HU10 ALAND AWATER ALAND_SQMI AWATER_SQMI INTPTLAT INTPTLONG
```

其中原 `INTPTLONG` 表头后带空格，原header字符串保存在manifest；解析副本仅strip表头/取值用于校验。每条JSONL保留完整 `original_fields`，包括原GEOID、ANSICODE及原始经纬度字符串。派生 `state_FIPS=GEOID[:2]`、`county_FIPS=GEOID[2:]`，不将标识变成整数、不补造丢失前导0的GEOID。

## 完整校验与后继使用边界

- 完整3,221行、3,221个唯一五位GEOID，重复GEOID0；52个USPS实体（50州+DC+PR），每个USPS对应唯一原州FIPS。
- INTPTLAT/INTPTLONG全为有限、合法角度，缺失0、重复坐标对0。纬度范围17.948052—69.449343，经度−164.188912—+178.338813；Alaska跨日期变更线的正经度仍为合法原坐标，不作西经强改。
- 附带人口、住宅、陆地/水面面积等numeric列只检查有限且非负，保持原列；本阶段不把这些值用作大豆权重。
- 代表点是官方县内部/代表点，**不是县内真实大豆种植像元，也不是作物面积重心**。空间近似、同2010作物县表的FIPS join、未匹配处理及最近原生格点选择均由root397在合成前固定；本阶段不读取热负荷选地理，不因现代县界细差自动修crosswalk。
- 当前对象对应2010地理结构，仍诚实标为历史结构重建，无严格当时首见证明。不把下载日期2026当原来源发布日期，也不将2013 Last-Modified包装为已验证发布日志。

变更账本：只新增396脚本、输出及本文；不动390、LINE/registry及其他研究线。fit0、cash0、prediction0、行情API0、SQL0、金融partial0，CTP/委托/邮件/调度/Git0。期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数和胜率均N/A，金融参数及回测结果新增/修改/删除0。

开始/结束过拟合判断：本次没有按收益或热量选择县、年份或代表点，取完整固定2010官方源；历史自适应择题和代表点近似的模型误差仍存在。继续价值：是，已补齐397事前可固定空间映射规则的实际小源，随后可与原2010作物结构合成原2020单例；尚不能据此推出稳定成本后优势、小止损加注或完整目标完成。原件已交root，后继联合独审由root安排，不重复下载。
