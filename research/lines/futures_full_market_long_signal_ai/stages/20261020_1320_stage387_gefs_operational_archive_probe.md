# Stage387：GEFS 当年业务预报档案的两个固定 run 有界探针

- line_id：`futures_full_market_long_signal_ai`。
- 开始：2026-10-20 13:20 CST；13:21 完成全部网络样本；本文汇总于 13:24 CST。先读 `research/registry.md` 及 Stage379 原文。
- 类型：来源与数据语义核验，非重要策略突破、非回测；不修改正式 C9、原模型、账户或冻结前瞻实验。
- **结论：当年 operational GEFS 的原始档案可定位，两个固定日期均有 APCP 索引，并实际支持精确字节 Range；不能再把历史通路写成“未查目录、不可执行”。但本轮没有取得降水数值、完整集合或连续覆盖，未证明金融增量。**

## 1. 本次边界与资料判断

只事前固定 `2018-07-01 00 UTC`、`2023-07-01 00 UTC` 两个 run，不扫全年，不挑能下载的日期。使用 NOAA 开放登记、其链接的维护者文档和 NCEP 官方产品语义。另实际取得一个官方说明 HTML。所有 S3 查询均局限这两个 run；没有凭证、SDK 安装、GRIB 整文件、批量取数、训练或资金回测。

参考与判断：

1. [NOAA 管理的 AWS GEFS 登记](https://registry.opendata.aws/noaa-gefs/)确认 `noaa-gefs-pds` 公共桶及四个日循环；登记仍有旧成员数描述，不能当全部年份的版本合同。
2. [awslabs 维护者 README](https://github.com/awslabs/open-data-docs/tree/main/docs/noaa/noaa-gefs-pds)给出 GRIB2、run/member/lead 命名与旧 `pgrb2a/` 路径。本次实际 2018 对象直接在 run 下、2023 有 `atmos/pgrb2ap5/`，因此 README 是入口，具体对象必须按目录确认。
3. [NCEP GEFS 官方历史](https://www.emc.ncep.noaa.gov/emc/pages/numerical_forecast_systems/gefs.php)区分业务升级与离线 reforecast；2015 年 V11、2020 年 V12 的成员、动力框架和分辨率发生改变。该页正文记 V12 于 2020-09-23 上线而表格写 2020.10，不能据此把任一新格式静默套到全部旧年。2018 属较早业务世代，2023 属 V12 上线后；本次未逐条核实其间每次小版本。
4. [NCO 原产品 inventory](https://www.nco.ncep.noaa.gov/pmb/products/gens/gec00.t12z.pgrb2af06.shtml)是实际取得的唯一额外官方说明对象：28,284 B，SHA256 `3ac352cc1dca3df0354c6051042336fdf3b67c379de7ef59565be7df961c821b`，HTTP200，页面自记 Last Updated 2015-12-14。它将 APCP 定义为总降水 `kg/m^2`，示例 f06 为 0—6 小时累计。这个文档不是 2023 数值解码结果。

本轮读取的是 operational 桶原 key，**没有用后来统一生成的 GEFS reforecast 替代当年预报**。这修复 Stage379 的一个来源未知项；作物暴露、季节、水分状态与金融条件增量仍须另行闭合。

## 2. 两个固定 run 的真实返回

自执行 Python 采用 HTTPS `urllib`，每个目录/XML/idx 正文设 32,769 B 上限，官方页设 65,537 B 上限；Range 只读 17 B 后关闭，若不满足16 B/206则不视为通过。普通沙箱初次两条请求发生 DNS 失败，没有响应正文；改为获准的公开只读网络访问后成功，不是档案不存在。网页工具也未能直接展示两个 S3 URL，其不可访问提示不能替代 S3 实际响应。

### 2018-07-01 00 UTC

- 目录：`https://noaa-gefs-pds.s3.amazonaws.com/?list-type=2&prefix=gefs.20180701%2F00%2F&delimiter=%2F&max-keys=20`。
- HTTP200；5,167 B；SHA256 `fa8cb810f810896776ce957b04d1d953c237cab2efb8b3e6d8c0a16d531bb200`；S3 request ID `QKH8HNHJR9H3JZAJ`；服务器 Date `2026-10-20T05:20:11Z`。
- XML `KeyCount=20, IsTruncated=true`。这是截断目录，**不证明 run 全成员、全部 lead 或整个 2018 年完整**。没有继续分页。
- 精确数据 key：`gefs.20180701/00/gec00.t00z.pgrb2af024`；文件4,035,282 B；ETag `b4cbf6f78cfebbbb3870fe59b30602a3`；LastModified `2018-08-10T19:38:17Z`。
- 精确 idx key：`gefs.20180701/00/gec00.t00z.pgrb2af024.idx`；HTTP200；5,630 B；83 行；SHA256 `1221a4fa93fe03ec3f3dcc20d163dcfd0dd5ba841b747e4237d051f07feead55`；ETag `83fd75d1c5f04ed607ae944ea1fbfcd0`；LastModified `2024-04-30T22:15:46Z`；request ID `564RF9M7MQA4MW09`。

已读 idx 的相邻记录：

```text
67:3438692:d=2018070100:APCP:surface:18-24 hour acc fcst:ENS=low-res ctl
68:3472930:d=2018070100:CSNOW:surface:18-24 hour ave fcst:ENS=low-res ctl
```

所以这一 APCP 消息候选范围为 `bytes=3438692-3472929`，长度34,238 B。**f024 不能解释为0—24小时总雨量**；这里是 run 后18—24小时这6小时的累计，valid end 为 `2018-07-02T00:00:00Z`，interval start 为 `2018-07-01T18:00:00Z`。

实际只请求头 `Range: bytes=3438692-3438707`，HTTP206，Content-Range `bytes 3438692-3438707/4035282`，Content-Length16；request ID `D9T73MEP866KQCG4`。返回 hex `475249420000000200000000000085be`，SHA256 `a5b5c4ecf6c1e85c512b251386256bebce6a65f16c68059d814dcc952a4754f6`：魔数 GRIB、edition2、消息头总长度34,238，恰与 idx 下一偏移之差相等。未读其余降水消息字节。

### 2023-07-01 00 UTC

- run 根目录查询同上，仅 prefix 换为 `gefs.20230701/00/`：HTTP200；500 B；SHA256 `ecf8df2bc4a6ff0b0a0f2d2c86ef89c7e0fb8bebb0e7d825f8b1f7b3ac04cd7a`；request ID `VE4H6RCC9B1AE1NM`。XML `KeyCount=3, IsTruncated=false`，只有 `atmos/`、`chem/`、`wave/` 三个子目录。
- `atmos/` 限定目录：HTTP200；692 B；SHA256 `092026e64fc08576239135101894c65a13525ca9d969bd11516318464bc637bb`；request ID `APYEE5924YJKJ0MH`。五个子目录含 `pgrb2ap5/`、`pgrb2bp5/`、`pgrb2sp25/`；没有扫描其所有文件。
- 精确 prefix `gefs.20230701/00/atmos/pgrb2ap5/gec00.t00z.pgrb2a.0p50.f024`、max-keys2：HTTP200；818 B；SHA256 `43cb6c439aa91a998e7b9989a9b5b0a07a1926b3932e2ab199f9c6631b47b64d`；request ID `T81X7N4M10P1Y7F8`；XML2对象且非截断，仅证明该数据/idx 对。
- 数据 exact key 为上述 prefix 本身；14,881,156 B；ETag `7dc015e27430169a0b9901293423fe18`；LastModified `2023-07-01T03:54:02Z`。
- idx exact key 为上述 key 加 `.idx`：HTTP200；5,815 B；85 行；SHA256 `e7ed0d294e89307ea672bfb584dbcea3a4cabdf40c39afe2893a26b24aed1764`；ETag `42222d0cd829a49fc97a5fad1a3d29b8`；同一 LastModified；request ID `73TAQ01ABYDWPQ36`。

已读 idx 的相邻记录：

```text
69:12868302:d=2023070100:APCP:surface:18-24 hour acc fcst:ENS=low-res ctl
70:12965829:d=2023070100:CSNOW:surface:18-24 hour ave fcst:ENS=low-res ctl
```

候选完整消息范围 `bytes=12868302-12965828`，97,527 B。valid interval 为 `2023-07-01T18:00:00Z` 至 `2023-07-02T00:00:00Z`，仍是6小时累计。

实际仅 `Range: bytes=12868302-12868317`；HTTP206；Content-Range `bytes 12868302-12868317/14881156`；Content-Length16；request ID `FGSW6VX4M21632KH`。hex `47524942000000020000000000017cf7`；SHA256 `5b08b63b46a0b0fea72d9ccbf3c3681f92d9ec944d70f13dd91e8f1b6f6add5e`；GRIB2 消息长97,527，等于相邻 idx 差。未取其余消息。

## 3. 已解决与仍未知的数据准确性

已解决：

- 两个预声明日期确有原业务命名的 run/lead/control member 对象，不能把 HTTP200误当空页；返回含真实目录 key、大小、ETag、idx内容。
- 两个 APCP 偏移都以最小16 B头证实是消息起点，且实际206响应，**可用小 Range 提取单一变量而无需整个4—15MB GRIB文件**。
- idx 指明累计窗，原官方说明给 APCP 单位；`1 kg/m²` 水当量对应 `1 mm`，不是降雨率，也不是把 f024自动视为24小时累计。

仍未知/不可声称：

- 本轮没有解码格点值、GRIB product template 或 grid section，因此实际数值、缺测、格点坐标/扫描方向、降水编码与单位的逐对象验证尚未完成；语义文档与idx/头一致只是结构证据。
- 没有整个集合21/31成员、所有 lead、连续日期及替换/修订完整性证明。唯一控制成员并非 ensemble mean。
- `geavg` 没有在本次有限目录中出现可确认 exact key：2018目录截断且2023只查子目录/control exact prefix，不将“没展示”写成“没有”。
- 后继如构造未来7日累计，必须按实际消息起止窗取无重叠区间，不能把各lead累计 blindly 相加；预报更新须比较同一 valid-time 区间，不能把run变老导致的horizon变化当新消息。

## 4. 发布时间与保守历史重建边界

**00 UTC 是起报/初始化标签，不是公开到达时刻，不能把北京时间08:00当当时已可用。**

- 2018 数据对象在8月10日写入，距7月1日约40天，idx更在2024年写入，明显包含归档回填/后制索引时钟。它们不能证明7月1日同一时刻首次公开，也不能被简单当作2018业务发布时间。
- 2023对象及idx的S3写入为起报后3小时54分02秒；这证明当前对象元数据如此，支持这个对象在当日形成的合理性，但不是所有历史 run 的发布 SLA、first-seen log 或从未替换证明。
- 不能把固定加4小时包装为已经验证的 PIT。严格本地 first-seen 从未来实际收到时开始留存；历史档案仍可在明确假设下开展**保守重建研究**，不永久禁止。

一个可预声明的保守研究口径示例：对北京时间 D 日21:00 的决策，只使用 UTC 日期 D−1 的00run，初始化至决策间隔37小时；预测累计区间仍须在决策之后，缺成员或区间不闭合就保持未知。37小时是刻意滞后的研究假设，**不是本轮证明的发布上界**；归档回填年代不能借此声称严格当时留存。如果这一路径有物理/经济支持，先有限量建立完整同口径样本，并报告真实first-seen与历史重建两个证据等级，禁止把假设伪装成事实。本轮没有实施或优化lag、没有看收益选择lag。

## 5. 不追加请求的 TMP 线索

Root 在本次网络预算结束后提出：经济agent有独立农学高温阈值线索，能否从已读 idx 找 TMP。以下仅用已打印的2018完整idx，不发额外请求、不换掉本次APCP真实探针：

```text
61:3098506:d=2018070100:TMP:2 m above ground:24 hour fcst:ENS=low-res ctl
62:3142724:d=2018070100:RH:2 m above ground:24 hour fcst:ENS=low-res ctl
```

所以2018同一对象的2m TMP候选范围为 `bytes=3098506-3142723`，44,218 B，描述是瞬时 `24 hour fcst`，valid end `2018-07-02T00:00:00Z`。没有取它的Range，不能声称已解码温度。NCO同一说明页将 TMP 写为K；摄氏转换及气温时间聚合需以后明确，不能用一个f024点声称全天高温暴露。

2023 idx虽完整读入内存并算SHA，但当时只打印APCP/CSNOW两行，没有留存完整本地文件；原Python进程已结束。因此本轮不能恢复2023 TMP偏移，不凭印象补造，不重请求。如果后继收益前声明改用TMP，须作为新取数范围记录，而非本次偷偷扩大。

## 6. 执行账本与结束判断

- 自执行Python成功公共HTTP GET 9次：两个run的目录/idx及一个官方HTML，共46,906 B文本；另两个16 B头共32 B，总46,938 B。最初2条沙箱DNS失败无正文；浏览器正文/访问错误的工具读取另记于会话工具证据，不混入上述字节统计。不是9个run，也不是9次金融数据API。
- 原始S3小正文仅在工具响应中留证，本文记录SHA、精确key/相邻记录及request ID；未构造持久原始数据集。没有完整GRIB、降水格点、行情文件或大数据下载。
- 新代码、参数新增/修改/删除0；fit0、资金回测0、行情API0、SQL0、CTP/订单0、账户/模型/Git变更0。金融指标包括期末权益、收益、最大回撤、Sharpe、滑点、交易次数、胜率均N/A，本轮无金融结果新增/修改/删除。
- **开始过拟合判断：本轮不按收益调参，两个日期事前固定；长期自适应择题仍有风险。结束判断：未引入收益择参，不能由数据通路成立推断alpha。**
- **继续价值：是。** 本次把 Stage379 的档案未知推进为两个实物样本和可执行精确Range，形成真实新增证据。后继只在独立经济暴露/单一变量定义闭合后，做最小完整数值解码和保守时钟样本；不因数据可取立即全量下载/训练。全市场目标保留，无天气物理暴露的品种保持未知，不强填0、不强加统一long符号。对小止损加注资格没有新增肯定证据。
