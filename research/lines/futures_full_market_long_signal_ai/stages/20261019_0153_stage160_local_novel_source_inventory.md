# Stage160 本机外生信息去重与可用来源盘点

- 时间：2026-10-19 01:53 CST；line_id：`futures_full_market_long_signal_ai`。
- 开始先读 `research/registry.md`、本线 `LINE.md`。目标仍为六所全市场高质量 long AI；Stage159 后不救 K、模型、stop/risk，不重做 OI、FX 或排序归因。
- 性质：本机小文件/既有 source inventory、manifest、receipt 与有限 raw header 核查；本轮不自行联网，不下载，不读行情、labels、矩阵或 SQL，不训练/回测。累计仍 **397 fit / 210 cash**；本轮新增 fit/cash/SQL/下载均 **0**。所有金融结果指标 N/A，无参数/既有结果增删。
- 不是重要突破。结论是一个已存字段方向值得一次 source-only 支持核，而不是已有 alpha 或新金融协议。

## 去重结果

| 信息族 | 本线实际状态 | 本轮判断 |
| --- | --- | --- |
| 四类境内市场滞后代理 M0/M1；跨代码相关 q | Stage010—013、033—036 已实际研究并排除固定包 | 不是新信息，不再换窗口/代理救参 |
| 期货近远月结构、同类收益 | Stage052—056 已训练/比较 | 期货价差不能改称现货基差后当新来源 |
| EIA 三个已发布库存量的季节创新 | Stage059—064 已实际 6 fit / 12 cash，固定包未获支持 | 不复活分量/窗口；境内仓单与其经济对象不同，但须另有来源 |
| 结算相对收盘 | Stage067—073 已实际研究 | 不是未用外部供需源 |
| OI；CNY/USD 滞后信息 | Stage084—089；144—150 已实际研究，固定包未获支持 | 本轮不重做 |
| SHFE 主体类别总仓构成 | Stage110—115 实际 12 fit / 8 cash，固定 NFC 包未获支持 | 已用的是 rank=-1/0 四个 L/S 分类 level，不能改分母/方向冒充新族 |
| 正排名会员的侧内分布/集中度 | Stage066 已提出但未训练；110 的冻结 scalar 没用 rank>0 | 想法不是首次提出；新可用事实是连续抓取 raw 保留了这层原字段，尚可检查具体支持 |
| 境内交易所仓单 level；真正现货基差 | Stage105 仓单草案未激活；本轮未找到可用连续本机现货基差源 | 尚未实际训练不等于本机已可开工 |

Stage110 的实际 scalar 为 `(LN-SN)/(LN+SN+LF+SF)`；成交及变化只作 QA。唯一 product-all 优先、否则完整已披露 contract 类别成对相加的范围规则，不是会员分布模型。Stage111 accepted manifest 记录全母域399252行，观察43540、缺失355712；其中非精确 SHFE 映射缺失317694。这个类别覆盖数不能借给正排名会员层。Stage115 固定包的失败不能推出所有会员分布无效，也不支持挽救旧 NFC 分母。

## 最多两个本机候选路径

**1. 已存 SHFE 会员排名 raw：建议一次有界 source-only probe。**

候选根为 `/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage109_member_category_history/`。完成后的 accepted 索引是同线 `outputs/stage119_source_environment_continuation/{date_manifest.jsonl,source_provenance.jsonl,completion_receipt.json}`，须按索引追109/116/119的实际原文引用，不自行把某个 raw 目录视作全部历史。`outputs/stage111_member_category_projection/experiment/manifest.json` 已绑定119的完成 receipt（5757 B）、date manifest（10191072 B）与 accepted source acceptance。这里只读小 manifest/receipt，未重散列、遍扫1.26GB原响应或10MB逐日索引。

119 receipt：3588个冻结源日，3567次 HTTP200、13个复用源日、2个 interrupted_unknown、6个网络错误；已知原响应1261656239 B。这是来源完成状态，不证明每日 rank>0 的产品/月合约覆盖、首发字节或稳定定义。不得把“有 HTTP200”变成“所有上市月份都有前20名”。

本轮仅读 `raw/pm20181106.response.gz` 解码前8192字符，已见 `RANK=-1,0,1,2,3` 与原 `INSTRUMENTID`、`PARTICIPANTID1/2/3`、`PARTICIPANTABBR1/2/3`、`CJ1/2/3`、相应 `_CHG`。另读旧106的20130104原文前1800 B，已见 `cu1301` 正rank合约行；早期无ID。**CJ2/ABBR2 是买持仓侧，CJ3/ABBR3 是卖持仓侧；CJ1 是成交侧。同一rank的三列是三套独立会员排序，不能当一个会员联表。** `all` 汇总与真实月份必须分别检查，类别层的 all 不可替代各合约的正排名。

最小、可直接复用的12个稀疏原文为 `outputs/stage106_member_category_probe/raw/pm{20110104,20130104,20140102,20150105,20170103,20190102,20191231,20210104,20250102,20250630,20250701,20261016}.response`，逐日 URL/headers/bytes/hash 在同根 `requests/YYYYMMDD.json`；另104复用20100104/20200102/20230103。106已有 `scope_per_date_audit.json` 和 `execution_receipt.json` 可先读，不需重新获取。其现有审计针对类别，未替正排名分布完成资格证明。

新信息的代数可识别性示例：两种世界均固定 `LF=SF=100,LN=SN=0`，旧 scalar均0，且可见20名两侧总仓均100。世界A多侧数量为 `(81,1×19)`、空侧为 `(5×20)`，侧内归一平方和差为 `0.658-0.05=0.608`；世界B交换这两套数量，差为 `-0.608`，原类别总仓与总量不变。因此分布差不能从旧 NFC scalar或四个类别总仓代数恢复。这只是反例，**没有选择 HHI 作为正式字段、交易方向或参数**。可见Top20的归一集中度不是全市场 HHI；缺榜会员不是零仓。

必要缺项：各历史 schema 的正rank数量/并列/截断规则、两侧独立数量有效性、真实月合约与all的披露范围、旧短符号全epoch映射、正排名的2020前训练前缀、跨年定义转换；稳定会员身份并未证明。若只做匿名侧内分布，不需要先把不同年份名字强行拼成同一席位，但仍须处理名单截断与排序规则。

时间限制：2010—2015抽样无 report/update/print；2017后有 update/print，2025又有字段变化。20130104 request 的 HTTP Date为2026、Last-Modified为2024，不是2013首发。原表更新时间也不证明首次公开可见；完整源日滞后只能写为历史重建假设，不能自动认证 PIT、夜盘归属或历史修订。六所全母域及无观察行必须保留，非SHFE不得复制值或用0代缺失。

建议下一步只在上述**已存**106稀疏raw上固定做一次支持核：核两侧正排名清单/数量/身份范围与时间元数据，明确能够支持哪些匿名分布字段、哪些缺失。无需遍扫全部历史、不新增source batch、不读收益。若关键范围/历史支持缺失则止步；若成立，另行冻结单一新字段及同missing控制，才讨论后续模型对照。旧130分数只能作固定参考，旧模型没有新字段系数，不能直接当新信息预测；跨市场 shared-missing 非恒0，不能照搬 FX 零列等价桥复用130控制fit。完整母/action域公平对照仍须单独定义，本轮未授权 fit。

**2. 已存仓单小样本：当前 no-go。**

候选根为 `/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage104_external_position_inventory/`。Stage104记录只有 SHFE 20200102/20230103两日与CZCE 20200102一日仓单原表，没有本地连续仓单或已接受周库存序列；日仓单也不是全部实物库存。原字段含 `VARNAME,REGNAME,WHABBRNAME,WGHTUNIT,WRTWGHTS,WRTCHANGE,ROWSTATUS` 等，层级总计不能全加，仓库/厂库及单位版本仍需区分。Stage105相对仓单level草案需要前12个完整月末基准；三日期不够，不缩短基准来制造可行。缺连续历史/单位/当时发布证据，故不做新列、拟合或200+新下载。

相关旧线 Stage044 source inventory 曾写现货基差24482行/18品种、仓单13084行/17品种及会员/CFTC缓存，但引用旧 bytedance 机器路径。本轮定点检查当前 `examples/portfolio_backtesting/backtest_outputs/{external_supply_demand_cache,external_domestic_member_rank_cache,external_cftc_cot_cache}` 均不存在，对应重建线/v2输出目录也不存在；这是指定来源的本机否定结果，不是声称扫描了全盘。Stage258旧供需source audit亦有原时戳、单位等缺口。旧记录的行数不能充当现在可读的连续现货基差，也不据其失败结果反向挑参数。

## 反思与收束

开始/结束是否新增过拟合：**否，本轮仅去重与来源支持判断，0金融、不按收益择日/品种/方向**；397次历史fit积累的择题风险仍在，分布信息独立不等于预测有用。是否值得继续：**是，仅一次已存raw的有界支持核；仓单/现货基差本机连续源当前no-go**。不因为缺六所同源就删除其他市场，也不因全市场缺失多而直接否决任何新增信息；应把可观察范围与收益证据分开。本轮不冻结金融公式、模型、方向、阈值、来源下载批次或实际回测。
