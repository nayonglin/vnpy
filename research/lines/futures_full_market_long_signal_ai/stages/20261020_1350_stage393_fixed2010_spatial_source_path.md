# Stage393：固定2010作物空间先验已有县级小表通路，无需全国大栅格

- line_id：`futures_full_market_long_signal_ai`；2026-10-20 13:50 CST。先读registry，本轮承接386/388/391唯一2020样本，仅做固定更早2010 CDL的通路/成本定位。
- 与正式C9和冻结双模型前瞻独立；不改391、386、LINE或registry。不取其他年份，不读取价格、训练或金融结果，不做县—州—天气映射。
- 开始判断：固定2010在当前金融结果前选择、无收益择图，本轮直接调参过拟合否；长期适应性择题风险仍是。为已固定天气供给机制补具体空间通路有价值，目标不是“找一个能跑的年份”。

## 可执行通路已找到，本阶段到此停止

官方公开ZIP里确有`CDL_Cnty_Pixel_2010_30m.csv`，压缩约298KB、解压约1.14MB。可以只取这一个2010成员，不下载1.87GB全国图或整个约10.86MB跨年ZIP。**本轮只核中央目录和已落在尾部的README，未下载CSV正文；县名/FIPS/列名/行数仍未解析，不宣称空间映射已完成。**

这能支持后继透明的县级结构近似，比整个州土地均匀分配更有物理意义；仍不拥有县内田块位置，更不是官方产量。2010土地利用本身早于固定2020样本，但当前下载包的重制/边界/编码时间要披露为结构重建，不能说已拿到2011原始文件。

## 严格有限的实际HTTP与原件

原件与收据在`outputs/stage393_fixed2010_spatial_source_path/actual_run1/`。计划4请求实际4请求，不重试、不跟随重定向；累计响应**正文262,144B，等于256KiB上限**，此后没有任何网络请求。

| 次序 | 实际操作 | HTTP | 实际正文/文件信息 |
| --- | --- | --- | --- |
| 1 | GET[官方Release](https://www.nass.usda.gov/Research_and_Science/Cropland/Release/) | 200 | 62,040B HTML，实际2010 anchor |
| 2 | GET[官方FAQ](https://www.nass.usda.gov/Research_and_Science/Cropland/sarsfaqs2.php) | 200 | 保存前缀134,568B，触本轮HTML预算上限；未宣称全文完整 |
| 3 | HEAD实际2010全国ZIP anchor | 200 | Content-Length=1,866,483,557B，Accept-Ranges=bytes；正文0 |
| 4 | GET县级ZIP `Range: bytes=-65536` | 206 | 65,536B；Content-Range明确总大小10,859,656B |

实际anchor及其标签保存在`selected_original_anchors.json`，不按多年文件名猜URL：

- Release页标签`2010 National CDL (1.8 GB)`→[全国2010 ZIP](https://www.nass.usda.gov/Research_and_Science/Cropland/Release/datasets/2010_30m_cdls.zip)。HEAD当前Last-Modified=`2022-02-10 07:20:12UTC`。它说明当前实体被放置/变更的服务器时间，不能单凭该时间认定像元改变或未改变。
- FAQ实际`County_Pixel_Count.zip`anchor→[县级ZIP](https://www.nass.usda.gov/Research_and_Science/Cropland/docs/County_Pixel_Count.zip)。Range当前Last-Modified=`2026-03-24 20:08:40UTC`；本轮取得尾部偏移`10794120—10859655`，SHA256 `b6820d1ff53a498c97fa5787c508ba43f7eddd8342cde083e92257b025e9d7be`。

`receipt.json`保存每次URL、方法、Range、状态、全响应headers、采集UTC与原字节SHA。FAQ无Content-Length，读取恰达上限且尾部尚未闭合HTML；收据初始字段`body_truncated_at_fixed_cap=false`只表示没有已知Content-Length超限，不构成全文证据。`path_assessment.json`已明确`complete_html_proven=false`及`fixed_cap_reached=true`。所需2010发布文字和县ZIP anchor都在保存前缀中，无需为完整FAQ再发请求。

## ZIP中央目录实际证明的小文件与成本

尾部包含完整EOCD和4,286B中央目录（offset10,855,348），共40项、非ZIP64/非多卷；逐项解析签名、名称、大小及偏移并核目录长度，元数据保存在`county_zip_central_directory.json`。只关注预先固定的2010两项，其余年份目录名存在不等于下载或比较过它们：

| 固定2010成员 | DEFLATE压缩字节 | 解压字节 | Local header偏移 | CRC32 |
| --- | ---: | ---: | ---: | --- |
| `CDL_Cnty_Pixel_2010_30m.csv` | 298,067 | 1,141,625 | 5,671,161 | `70bfc98e` |
| `CDL_Cnty_Acres_2010.csv` | 254,291 | 1,076,261 | 634,049 | `6831db42` |

下一阶段若root明确取固定pixel成员，可单次Range **`bytes=5671161-5969284`**，298,124B，从该成员local header覆盖至下一个成员之前，包含完整局部头和压缩体。取得后应核local header的真实文件名/压缩方法、解压长度1,141,625及CRC32，不信任仅由中央目录推得的对象。这只是已定位的后继成本，**393未发此Range**；它大于本阶段剩余0B预算，不因“文件很小”自动扩限。

## 同一尾部里的README原文已离线核验

`readme_County_Pixel_Count.txt`的local header与1,038B压缩体完全落在已取得64KiB尾部。没有增加HTTP，直接离线DEFLATE解码，核解压长度2,508B和CRC32`72d38a21`；原解压文件SHA256 `d315094b7e9e99dea813128082d34612227da44b3d100356acbe2573222c5386`，绑定在`readme_binding.json`。

维护方README明确这些县级像元/面积数**不是官方NASS面积估计**；分类与像元计数会有偏差，通常相对官方估计偏低。它同时明确给出大豆汇总的字典组合：

`Soybeans_all = Category_005 + Category_026 + Category_239 + Category_240 + Category_241 + Category_254`。

因此后继优先核此维护方汇总与6类之和是否相符，避免只取单作005遗漏含豆双季类。但本轮未取CSV，不能预先断言这份2010CSV有哪些列、6类是否均出现或空列是否表示0。缺类别/县标识必须按实际字典和表结构解释，不自行填零。

## 历史版本与近似的正确含义

保存FAQ前缀包含其2010图在**2011年1月首周**公布的官方说明，及历史catalog后来重编码/发布的说明。这支持“2010土地覆盖是一项早于2020的结构先验”，不支持“2026年ZIP中的每个县界/像元统计都在2011逐字节已知”。当前县包已经包含2007—2025年度，服务器时间2026，明显应称现代分发/重建包。

本线可以在金融结果前明示并冻结这种历史结构重建假设，不无限追索2011原始字节作为所有研究的前置条件；也不能把它包装成严格first-seen。2010与2020真实作物轮作、种植扩张和分类误差仍存在，需要保留近似身份，不因后来效果差换2019/2020/多年频率图。

县级像元仅拟给**州内空间份额**；391的2019逐州官方产量仍是州间经济权重，不用这份像元面积替代Q2019，也不将有偏的原面积数解释成大豆产量。县到GEFS格网还需要公开边界/几何或清楚的粗化规则，当前没有做。全市场宇宙与m一个产品的来源映射不变，其他产品不伪造天气值。

## 交付与边界

`path_assessment.json`记录`single_fixed2010_county_csv_path_found_stop_no_more_http`，绑定收据、两原anchor、中央目录、README及后继唯一固定Range成本。没有新增tool文件，只保存本轮小原文/元数据及本文；未改391/LINE/registry。

本轮fit=0、cash=0、行情API=0、完整ZIP/全国图/年度CSV下载=0、参数寻优=0、账户/正式C9/Git变更=0。金融指标全部N/A。结束判断：本轮没有结果择图，过拟合直接调参否，结构重建和同史择题风险必须披露；继续取得并核这个唯一2010县级小表**有价值**。可执行路径已定位，当前393结束，不再扩页、扩年或下载地图；未证明全国热害或任何做多alpha，更没有小止损加注资格。
