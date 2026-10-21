# Stage104 国内会员排名与仓单/库存：本机实存与有界历史通路盘点

- line_id：`futures_full_market_long_signal_ai`。
- 时间：2026-10-18 19:06—19:16 CST；工作区 `/Users/mac/Desktop/fian`，沿用本线工作分支。
- 性质：只读来源盘点与最多 5 MiB 小响应验证；不是策略、特征、模型或现金实验。
- 是否重要突破：否。发现了值得继续认证的原始主体类别观测，但没有收益、回撤或泛化进步证据。
- 本次新增：本 stage 与 `outputs/stage104_external_position_inventory/` 小原表/元数据。修改/删除策略、参数、既有回测结果：均无。
- 新增 fit / cash / SQL / 分钟下载：`0 / 0 / 0 / 0`。期末权益、收益、回撤、Sharpe、滑点、交易次数、胜率：本次均 N/A，不复制旧成绩充新结果。
- 已先读 registry、本线 LINE 与 066 来源结论，再浏览交易所一手规则/入口及 AKShare 维护者 GitHub，随后有限定位本机 source/cache/provider 路径。registry/LINE 中历史摘要已见；未读取当前模型/现金产物，不以金融成绩挑来源。

## 结论与唯一下一来源

**当前没有现成可训练的全市场会员/仓单历史缓存。最值得下一步单独认证的唯一来源是 SHFE 官方原始 `pmYYYYMMDD.dat` 中的“期货公司 / 非期货公司”产品汇总行。** 2020/2023 原表真实存在这两类总买/总卖/成交量及变化，通用库会过滤掉它们；这比复试 Top20 净持仓/净变化多了一层原始观测。它仅代表交易所业务类别，不是产业/投机、聪明钱、受益人、客户类型或套保身份。

本轮并未证明该类别层可覆盖 2020 训练前缀：2010 锚点没有此字段；类别首次出现、连续日期、聚合合约范围、口径版本与首发时刻仍未知。应先 source-only 核这些问题，再决定是否冻结科学实验。本轮不授权 fit，也不把局部 SHFE 覆盖缩成用户全市场母体。

仓单 level 也真实可取，但只代表交易所登记的可交割凭证，不能称社会总库存；变化不能解释为物理出入库。SHFE 库存周报入口存在，**本轮没有取得历史周报原表**，因而没有认证“库存小计 / 期货”的单位、字段定义或连续覆盖。不能把日报 `WRTWGHTS` 冒充周报库存小计。

## 本机实存：旧路径与当前机器严格分开

以下均真实 `Path.exists()/stat` 定位；元数据见 `local_stat_inventory.json`。当前 checkout 中对应路径不存在，不是机械迁移成功：

| 目标 | 本机精确路径 | 实测 |
| --- | --- | --- |
| 会员历史缓存 | `/Users/mac/Desktop/fian/examples/portfolio_backtesting/backtest_outputs/external_domestic_member_rank_cache` | 不存在 |
| 供需/仓单历史缓存 | `/Users/mac/Desktop/fian/examples/portfolio_backtesting/backtest_outputs/external_supply_demand_cache` | 不存在 |
| 旧线 Stage080 补数产物 | `/Users/mac/Desktop/fian/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage080_member_rank_2022_backfill_feasibility` | 不存在 |
| 旧线 Stage091 CZCE raw | `/Users/mac/Desktop/fian/research/lines/futures_trend_c9_minrisk_highquality/outputs/stage091_preentry_window_raw_full_backfill/raw/czce_member_rank` | 不存在 |
| 旧线 Stage095 数值提取 | `/Users/mac/Desktop/fian/research/lines/futures_trend_c9_minrisk_highquality/outputs/stage095_full_numeric_feature_extraction_stability_audit` | 不存在 |
| 旧线 Stage099 来源 manifest | `/Users/mac/Desktop/fian/research/lines/futures_trend_c9_minrisk_highquality/outputs/stage099_finer_source_feasibility_manifest` | 不存在 |

旧机器 `/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/` 下两个原始缓存目录也实测不存在。旧线 044 文档仅声明 member `2023-01-03—2026-04-17 / 15产品`、warehouse `2020-01-02—2026-04-17 / 17产品`；080 又声明非 DCE 2022 补数。它们是旧文档声明，**不是本机全表实测，也不是全市场覆盖**。旧 257/258 源合同脚本用于定位原缓存、raw、manifest，未运行其金融分析。

有限 `rg --files` 和 source 路径检索未发现替代缓存；`backtest_outputs` 一级目录中没有对应 external/cache 目录。本结论限定于已查目标与命名范围，不声称证明整个磁盘绝无数据。未扫描原始行情、数据库内容或其他研究线全部输出。

## 历史 HTTP 实测与原响应

先在沙箱发起相同六 URL，均 DNS 失败，0 字节，失败收据保留为 `probe_receipt_sandbox_dns_failure.json`。随后授权联网读取六 URL，另增加唯一 `2010-01-04` 训练前缀锚点。**7 个历史原表全部 HTTP 200、无截断，保存 1,701,395 B。** 另有一次官方周报入口 HTML 读到上限加 1 sentinel 字节 `500,001 B` 后终止，未解析/保存 raw，未追 JS、未猜周报历史端点。总有界 HTTP 响应 `2,201,396 B < 5,242,880 B`。没有登录、凭证、env 或验证码规避。

所有保存文件的绝对根为：`/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage104_external_position_inventory/`。

| 类别/日期 | 一手 URL | 保存文件 | 字节 / 实际小表范围 | SHA256 前12 |
| --- | --- | --- | --- | --- |
| member SHFE 20100104 | [官方原表](https://www.shfe.com.cn/data/tradedata/future/dailydata/pm20100104.dat) | `member_SHFE_20100104.dat` | 135,301 / 528行，26真实合约，7产品，无all | `ab2ecf3200f9` |
| member SHFE 20200102 | [官方原表](https://www.shfe.com.cn/data/tradedata/future/dailydata/pm20200102.dat) | `member_SHFE_20200102.dat` | 435,202 / 1,128行，53真实合约＋14all，15产品 | `cadd3200e609` |
| member SHFE 20230103 | [官方原表](https://www.shfe.com.cn/data/tradedata/future/dailydata/pm20230103.dat) | `member_SHFE_20230103.dat` | 567,788 / 1,470行，70真实合约＋15all，18产品 | `c5c5edea1ad6` |
| member CZCE 20200102 | [官方原表](https://www.czce.com.cn/cn/DFSStaticFiles/Future/2020/20200102/FutureDataHolding.xls) | `member_CZCE_20200102.xls` | 251,904 / 1,351×10，20品种标题＋45合约标题 | `2c74b711227b` |
| warehouse SHFE 20200102 | [官方原表](https://www.shfe.com.cn/data/tradedata/future/dailydata/20200102dailystock.dat) | `warehouse_SHFE_20200102.dat` | 72,764 / 316行，19仓库/厂库报表标题 | `13b0ba7704a8` |
| warehouse SHFE 20230103 | [官方原表](https://www.shfe.com.cn/data/tradedata/future/dailydata/20230103dailystock.dat) | `warehouse_SHFE_20230103.dat` | 87,908 / 373行，24仓库/厂库报表标题 | `d0d20a43ea07` |
| warehouse CZCE 20200102 | [官方原表](https://www.czce.com.cn/cn/DFSStaticFiles/Future/2020/20200102/FutureDataWhsheet.xls) | `warehouse_CZCE_20200102.xls` | 150,528 / 1,052×9，20品种单位标题 | `615ad31d1abb` |

行数包含报表合计/表头，不是独立训练样本数。SHFE 原 metadata 最初的 67/85 instrument count 包含 14/15 个 `all`，已在同次盘点中明确更正为真实合约 53/70；`probe_receipt.json` 保留两种数，不能再报成 67/85 真实合约。两张 CZCE 文件具有 OLE XLS 魔数且 pandas/xlrd 小读成功，绝非 HTTP200 挑战页。

## member：新增信息、字段与必须保留的边界

2020/2023 SHFE 原始字段为 `INSTRUMENTID, PRODUCTSORTNO, RANK, PARTICIPANTID1/2/3, PARTICIPANTABBR1/2/3, CJ1/2/3, CJ1_CHG/CJ2_CHG/CJ3_CHG, PRODUCTNAME`。三套会员分别是成交、买仓、卖仓排名，**同一 rank 的三人不能横向当作一个主体**。

`cuall` 等行：`RANK=-1` 标签“期货公司”；`RANK=0` 标签“非期货公司”；`CJ1` 成交、`CJ2` 买仓、`CJ3` 卖仓，均附变化。2020 all 产品为 `ag/al/au/bu/cu/fu/hc/ni/pb/rb/ru/sn/sp/zn`；2023 再含 `ss`。`nr` 虽在两个排名文件中有真实合约，`bc/lu` 虽在 2023 有真实合约，却不在这些 all 类别行中。缺类别不能填零，也不能只保留已有类别产品重定义全市场。

两个铜小样本可复验：20200102 FC 买/卖 `309365/304953`，NFC `1935/6347`；20230103 FC `382932/385805`，NFC `5315/2442`。两例加总买=卖，仅证明这两格的内部恒等式；不替代全历史聚合范围/单位认证，也不证明方向能预测收益。

同一编号 `0009` 在 2020 小样本为“五矿经易”，2023 为“五矿期货”，证明 raw 编号与名称变更均存在。不能用字符串同名跨所合并、把所有名称变更都当同一经济主体，或因两个例子宣称编号永久稳定。2010 原表没有 ID/PRODUCTNAME/all/report-update-print 元数据，只有简称与合约排名。原始名称仍不可被补成已认证受益人身份。

CZCE 20200102 原表给“名次、会员简称、成交量（手）、增减量、会员简称、持买仓量、增减量、会员简称、持卖仓量、增减量”，包含品种汇总与合约分表。20 品种标题含 AP/CF/CJ/CY/FG/LR/MA/OI/PM/RI/RM/RS/SA/SF/SM/SR/PTA/UR/WH/ZC；是当日小表范围，不是其全历史品种集合。不得把品种汇总与各合约重加一遍；CZCE 三位合约如 `AP001` 必须按报告日、交割年月和原 epoch 映射，不能凭字符串把十年同名串起来。SHFE 的 `all` 也不能进入真实合约成交价格链。

会员量与交易所层 OI/成交量口径须分别核验，不能机械统一除 2 或把总OI当现成相同量纲分母。数据发布门槛造成未上榜/未公布；它不是仓位 0。现行官方信息办法按达到公布标准的合约发布排名，并发布品种主体类别总量；[2018 官方产品手册](https://www.shfe.com.cn/products/futures/metal/ferrousandpreciousmetal/au_f/manual/201807/P020240320678994870285.pdf) 的可检索段落又采用“活跃月份”表述。因此 `all` 名称不自动证明所有上市月份全覆盖，须验证历史聚合范围与规则版本。

[2025 官方会员管理办法](https://www.shfe.com.cn/regulation/exchangerules/otherrules/202508/t20250807_828510.html)、[章程第16—18条](https://www.shfe.com.cn/regulation/exchangerules/rules/202509/t20250929_829157.html) 与 [2024 官方教学旧规则](https://edu.shfe.com.cn/MemberCorner/HowToBe/538.html) 将其归为业务范围/会员资格分类；所查准入条款未把非FC等同某品种产业经营者或套保目的。期货公司汇总中同样可能承载产业客户。当前规则只能解释当前法定类别，不能冒充 2010 定义版本证据。

## warehouse：level、变化、单位与周库存区别

SHFE 两张原表字段均为 `VARNAME, VARSORT, REGNAME, REGSORT, WHABBRNAME, WHROWS, WGHTUNIT, WRTWGHTS, WRTCHANGE, ROWORDER, ROWSTATUS`。它含仓库、地区、合计/总计，不能将所有层级行相加。2020 有“沥青仓库/厂库”分开，2023 还可见“低硫燃料油、纸浆、螺纹钢”的仓库/厂库分开；标题数变动不能当可比产品数增长或库存增长。

`WGHTUNIT` 原码：黄金/白银 `1`，多数字段 `2`，原油 `3`。这批 JSON 没有字面单位字典，本轮保留原码，**未认证跨产品/跨时期 kg、吨、桶的完整转换**，不得硬合并规模。产品名称中有中英文 `$$`、仓库/厂库、BC 与国内铜之别，不能粗截名称把不同经济品种合并。

CZCE 首标题直接写出单位“张”与实物换算，例如 20200102：SR `1张=1手×10吨=10吨`，CF `1张=8手×5吨=40吨`，CY `20吨/张`，AP `20吨/张`，ZC `1张=200手×100吨=20000吨`。这些是该日官方原表打印证据，不是未来所有年份固定乘数。原表另有仓库编号/简称、年度、等级、品牌、仓单数量、当日增减、有效预报、升贴水，列随产品变化；有效预报不可并为已注册仓单。

仓单 level 可以支持“登记交割资源是否稀缺”的待检验经济命题；仓单注销/到期/交割/转移不能直接解释成库存消耗或需求冲击。厂库信用与仓库存货亦不同。相对 level 必须用严格过去、同定义/同单位历史；当前仅两个 SHFE 日期与一个 CZCE 日期，**不足以构造过去多年分位、季节位置或稳定 scarcity 指标**。

[官方日周入口](https://www.shfe.com.cn/reports/tradedata/dailyandweeklydata/?query_params=weeklystock) 把仓单日报与库存周报分开列出。本次未取得周报历史 raw，不声称存在可用“库存小计 / 期货”周序列或其仓库/厂库可比定义。入口一次小读取触及上限即终止，没有扩成采集工程。

## 发布时间、可知滞后与修订证据

[SHFE 2025 信息管理办法第11—12条](https://www.shfe.cn/regulation/exchangerules/otherrules/202508/t20250807_828526.html) 将每日信息定义为每交易日闭市后发布，含排名/主体总量与仓单，周信息在周末交易日闭市后；[CZCE 2022](https://www.czce.com.cn/cn/uploadfile/2022/08/31/20220831170528656.pdf) 与 [2023 交易管理办法](https://www.czce.com.cn/cn/uploadfile/2023/04/27/20230427112409129.pdf) 也给闭市后日信息。它们不是逐日历史首发分钟证据，也不能回溯认证所有 2010/2020 规则版本。

| raw | report_date | update_date | print_date |
| --- | --- | --- | --- |
| SHFE member 20200102 | 20200102 | 20200102 20:00:30 | 20200102 20:00:40 |
| SHFE member 20230103 | 20230103 | 20230103 19:57:20 | 20230103 20:00:40 |
| SHFE warehouse 20200102 | 20200102 | 20200102 20:00:47 | 20200102 20:00:55 |
| SHFE warehouse 20230103 | 20230103 | 20230103 20:00:08 | 20230103 20:00:55 |

上述字段只能证明当前归档原表所载的更新/打印信息，不能认定为首次向公众可见时刻。2010 SHFE 文件无此字段；CZCE XLS 小样本只有报告日期，无首发分钟。7 个响应 HTTP Last-Modified 分别集中在 SHFE `2024-03-20`、CZCE `2025-06-30`，证明当前服务器文件时间不是原交易日首发证据；不知道是否修订、何时修订、首发内容是否完全相同。

未来如采用一完整源交易日滞后，只能是预声明的保守历史重建假设：不能让当日日盘收盘前读取本日报，也不能把“16:30左右”库说明统一贴到历史。日历必须区别日盘收盘、当晚所属的下一交易日与节假日；假期不可猜固定工作日 lag。即使 lag 一天，未知历史修订仍不因此自动消失。

## 2020/2023 训练前缀与六所边界

| 需求 | member | warehouse / inventory |
| --- | --- | --- |
| 2020 cutoff 前训练 | 2010 Top20 原表可取，但没有所需类别/ID；2020-01-02 已在 cutoff 后。类别前缀长度未知，当前不支持开训 | 无 cutoff 前原表或连续序列证明；2020-01-02 在 cutoff 后。当前不支持 |
| 2023 cutoff 前训练 | 2020 有类别锚点，说明不是仅最新页/近90天；2010无类别、2020—2022连续覆盖/定义未验，当前不支持开训 | 2020 有level锚点；无连续过去level/周库存覆盖，当前不支持 |
| 全市场 | SHFE/部分INE与CZCE单日局部；DCE/CFFEX/GFEX及退市产品连续覆盖未验证 | SHFE/部分INE与CZCE局部；不能声称覆盖六所，金融品种不具有同一种商品仓单经济定义 |

DCE、CFFEX、GFEX 仅从维护者代码定位到了候选通路，本轮未向这些历史端点发请求。AKShare 对 DCE 写明可能 HTTP412，但这不是本机实测；GFEX POST `gen_date` 或 CFFEX CSV 路径也不是成功覆盖证据。SHFE 原表出现 `nr/bc/lu`、仓单出现原油，不代表 INE 全历史已独立认证。全部本线机会与 family 应保留，缺源保持 unknown；来源局部可用不等于只研究旧19品种或正式月池。

## 维护者代码调研与取舍

- [AKShare cot.py](https://github.com/akfamily/akshare/blob/main/akshare/futures/cot.py)：SHFE parser 删除 `PARTICIPANTID1/2/3`，并只保留 `rank>0`，会丢掉本轮看到的类别总量；其“20020107开始/16:30左右”属于库说明，本轮没有认证该全历史/分钟承诺。不能直接调用默认产品清单后宣称全市场。
- [AKShare cons.py](https://raw.githubusercontent.com/akfamily/akshare/main/akshare/futures/cons.py)：给出本轮真实验证的 SHFE canonical pm 路径和 CFFEX 等候选路径；作为端点发现依据，不作为历史全覆盖证据。
- [AKShare futures_warehouse_receipt.py](https://github.com/akfamily/akshare/blob/main/akshare/futures/futures_warehouse_receipt.py)：给出 CZCE 日期 XLS/XLSX 与 SHFE 日报路径，并记录 2025 后 HTML/schema 改动。该后段切换没有本轮实测，未来不得把旧字段强行套全段。
- 采用官方 raw 以保存库丢弃的信息，否决直接沿用旧 TopK 缓存/把供应商覆盖宣称当本机证据。维护者 main 为调研时页面，不是已锁定代码版本。全部已看 URL/用途保存在 `viewed_sources.json`。

## 收尾核验、反思与 TODO

19:15 CST 用 `.py311/bin/python` 重核 7 个小文件：全部状态200、未截断、字节/SHA相符；4个有 report_date 的 JSON 日期匹配请求；两 XLS 魔数/日期标题有效；连续覆盖与首次发布时间资格明确为 false。只散列这批小附件，未重新 hash 大库/原行情。收据 `verification_receipt.json`，SHA256 `bca8ac6a4c1847513c3538d95e6ac78619cedf9c703a8dc33da77caaa6719304`。`probe_receipt.json` SHA256 `6fb9d0eb617692326af5333cf861b55bbb8ae240bd76037ee844aca2c4c24a7b`；`local_stat_inventory.json` SHA256 `c0fa2e4f0a29ac0158e366e04f1e2ac0c99f709cd2fcfca28a8c5b5e7cceacd6`。

开始与结束是否过拟合：**本轮新增否**。选择依据是事前经济区别与 raw 实际存在的额外观测，0fit/现金/成绩择参；整条线已有多轮择题风险仍在，不能把后续验证称新的盲 OOS。不得据两个铜例子先定交易方向或把缺数据设为负类。

是否继续有价值：**是，但只继续 SHFE 原始主体类别层的有界 source-only 资格确认**；是否扩量/训练由下一阶段单独冻结。唯一下一步先定位类别首次出现、连续训练前缀、产品/活跃月份聚合范围、版本与时钟，失败则保留 unknown 并停止该信息假设。仓单日报可留备选证据；不同时推进多源大采集，也不把源工程当用户收益目标。

本次未改 LINE/registry、其他研究线、根 memory/back_log、Git、正式策略、CTP、env、生产、邮件或定时任务；没有重训、重放现金账本或清洗原行情。完整全市场高质量做多目标仍未达成。
