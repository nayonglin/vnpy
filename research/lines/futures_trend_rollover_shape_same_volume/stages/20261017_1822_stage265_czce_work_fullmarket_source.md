# Stage265 郑商所全市场固定快照备用源与官方归档实查

- line_id：futures_trend_rollover_shape_same_volume；记录时间：2026-10-17 18:22 CST。
- 本轮按用户追加要求，范围已从原六产品/91epoch扩大为六所全市场全部品种与历史真实合约日线，目标2010-01-01—2026-10-16。本记录仅负责CZCE来源，不把备用快照写成全市场完成；不新下分钟。
- 是否重要突破：否。取得可复验的备用历史日线与产品目录，但主目标仍需完整日线源、上市资格与独立审计。
- 开始过拟合判断：否，本轮只按固定范围取真实数据、检查价格与身份，不根据回测收益挑来源或参数；继续价值：是，合约历史和量/OI血缘直接约束有效训练样本。

## 取得的真实文件与可复验身份

- Work来源为`ildhj0116/Work`，固定commit `e8dd9a55b9a30b1e3033fe838724c23fcdd87ad1`（2018-04-26）。依据保存的Git tree，18个产品表每表六字段加metadata共126文件全部对预期字节与Git blob SHA-1验真；108个新下载、18个复用，未重下既有raw。总字节`18,643,190`。
- 18个表名：AP/CF/CY/FG/JR/LR/MA/OI/PM/RI/RM/RS/SF/SM/SR/TA/WH/ZC。metadata共1070行/1070完整交割身份，实际代码23种；ME/RO/ER/WS/TC为另外5个历史原码，未按容器文件名改成MA/OI/RI/WH/ZC。未发现WT表/代码，不捏造其覆盖。
- 原始metadata均为第三方候选，不是交易所逐合约上市/末交日认证。未知日期不按规则补齐；完整生命周期资格仍false。原先metadata_candidates/listing_evidence保留，不重写。
- 代码许可文件存在GPLv3文本，但供应商行情数据再分发权未建立；raw、标准化大CSV与请求hash只放本机ignored输出，不进入Git，不执行第三方脚本。

## 标准化结果与拒绝边界

- 六字段完整、OHLC正值与价格几何有效、候选metadata区间可唯一绑定的记录为`47,751`日、`527`个epoch，范围`2015-01-05`—`2018-04-26`。同时保存原始vendor代码、完整YYYYMM、epoch、逐字段原CSV行号、source commit；无合成OHLC、无填零或前值填充。
- 除AP/CY外，各表high/low从2015年1月开始，而open/close/V/OI的部分源早到2003—2014，故不能声称获得2010—2014完整OHLC。所有表均不能提供2018-04-26之后的历史。
- 宽表共`991,898`个未接受键，其中`840,041`为候选生命周期外、已出现字段全0的矩形网格；这是源结构证据，不是84万个缺交易日。其余`151,857`缺必要字段；候选生命周期内V=0且四价空`90,593`，不造价格。
- 源JR/LR/PM/RI/RS的V/OI含重复日期；386个相同非空单元格明确去重。LR/RI六个原始文本差异实查均为空串对0.0，没有两个不同非空数值；相关2018-04-12/13本就没有完整OHLC，没有一条因此进入完整bar。`work_fullmarket_duplicate_dates.json`保留原行号与差异列；若将来出现两个非空数值冲突，工具会整格隔离不择值。
- 完整六字段实际20个产品代码：18现名加ME/TC；RO/ER/WS只保留metadata及其可得稀疏raw，不伪造2015前high/low。

## 本机重叠只读核验

- 只读当前`.vntrader/database.db`、按真实合约epoch与日期匹配；47,751源日中4,406重叠，OHLC四价4,406/4,406全部一致，相对本机新增43,345日。此处新增指全Work可接受快照相对本机，不能替代原91target的AM120统计。
- V有355日不同，355日均等于数据库的2倍；OI有347日不同。存在331日源OI等于下一可得数据库日OI的2倍，支持部分TQ open_oi与收盘持仓/单双边口径差异；此为诊断关系，不允许用下一日OI做特征，也不授权全源统一除2或覆盖主库。其余大批源值本来与本机V/OI相等，进一步否定机械统一除2。
- 逐产品计数和所有差异见`work_fullmarket_existing_overlap.json`、`work_fullmarket_existing_differences.csv`。原单位和时钟保留pending，未合入主库。

## 官方与其他合法来源调研结论

- 官方年度归档三种已知路径的普通HTTPS GET：2010 `exchange/datahistory2010.zip`、2015 `DFSStaticFiles/Future/2015/FutureDataHistory.zip`、2025 `ALLFUTURES2025.zip`均HTTP412、返回HTML非ZIP。请求时间、URL、bytes与hash在`official_archive_probe_requests.json`；没有绕过访问控制。结论是本机普通路径受阻，不能说历史数据不存在。
- 官方2025年6月月报公开内容列26个期货品种（[官方月报](https://www.czce.com.cn/cn/rootfiles/2025/07/04/1750859895384730-1750859895409197.pdf)）；[官方2025服务实体经济报告](https://www.czce.com.cn/cn/content_file/gyjys/qhscyjcs/cgxc/2026/4/077939e9d8fc4ad088cd76a52ed8d3a0.pdf)的检索内容支持PL于2025-07-22上市，共构成已核查27产品目录，不能把目录视为2026-10-16全部历史合约已齐。
- Work完全没有CJ/PF/PK/PL/PR/PX/SA/SH/UR九个后上市产品；对应产品目录、文件覆盖及来源在`source_product_inventory.csv/json`。纯苯BZ属于DCE，未混入CZCE。
- AKShare官方源包装仍取交易所静态端点，不能当独立历史数据；SubjectNoi保存的tree无CZCE；Sina/主连/收费或试用skill的支持说明不能证明旧合约覆盖。没有注册、付费、试用或执行不可信代码。

## 工具、验证与后续

- 可复现入口：`stage265_czce_fullmarket.py fetch/normalize`、`stage265_czce_source_inventory.py`、`stage265_czce_compare_existing.py`、`stage265_czce_verify_raw_bind.py`；metadata与全市场身份/重复隔离合计10项unittest通过。
- 本次新增/修改/删除策略参数：无；模型训练0、财务回测0、主库写入0、分钟下载0、CTP连接0、订单API0。收益、权益、回撤、Sharpe、交易、滑点、胜率均不适用，未生成回测结果。
- 结束过拟合判断：否，未调策略/标签/AM120或按收益筛数据；继续价值：是，但旧Work到此只作已冻结备用源，不继续无界找镜像/补单元格。下一步独立复核root正在下载的RQAlpha公开全市场H5与metadata，尤其CZCE跨十年身份、六字段/量OI时钟、全产品边界和原SM77日。


## 18:29 补录：RQAlpha公开月包独立原始审计

- 本段是root取得RQAlpha月包后的独立核验；原始H5审计没有联网或复用root生成的inventory统计。读取原`futures.h5`、`instruments.pk`、`trading_dates.npy`、旧Stage264 manifest与已冻结Work/SHFE数据。四个原始文件SHA均独立重算并与下载receipt一致；H5 SHA `d288f6e4c7468981e95fbb0c1c9e2e1e66bfb99f5ba607843728aec535c8bfee`。
- metadata先用pickletools逐opcode检查，无GLOBAL/STACK_GLOBAL/REDUCE/NEWOBJ/EXT/PERSID等执行操作，再用find_class/persistent_load全拒绝的限制Unpickler读取纯类型；没有普通pickle.load，也没有执行第三方代码。日期npy使用allow_pickle=False。
- 11,036个H5 dataset全部能找到Future metadata；标准YYMM及单独F月均价family、月份、元数据exchange与underlying校验后10,547个真实合约（含2010前寿命与42个F合约），489连续/非交割源被排除。2010-01-01—2026-10-16范围有2,157,204原始行，六所97产品代码；这是该供应商bundle的实存覆盖，不是交易所全部生命周期的完整性认证。
- CZCE共2,841个真实交割dataset、33产品代码：27现名加ER/ME/RO/TC/WS/WT，2010-01-04—2026-09-30共609,165原始行，量>0有389,422行。LR最后只有2026-01-16，其余停牌/停止挂牌与缺行情需要按产品边界区分，不能机械将所有日历空缺当漏下。
- 原231目标全部存在H5 dataset，metadata exchange 231/231匹配。原first_main之前名义原行AM120为190个；仅计算V>0且有效OHLC时为180个，这只是保守对照诊断，不能事后更改既有AM120合同或宣称训练资格已通过。少于120者须继续用真实上市/活跃历史寿命区分。
- 核心P1：原SM77缺日在RQ中77/77存在，但全部V0、四价相等且>0；对应Work原CSV逐字段独立检查77/77 V0且四价空。例SM1501/2015-01-09 RQ四价5950/V0/OI7366，2015-01-13四价6160/V0/OI7366。它们是供应商对无成交空价的平价编码证据，不是77个真实交易日补齐。`rqalpha_SM77_raw_rows.csv`同时保存RQ原值与Work空字段。
- 全六所607,134行V0仍有正四价，不能只用OHLC>0判断有效成交。量>0但OHLC几何错误807行：DCE743、GFEX61、INE1、SHFE2；CZCE与CFFEX为0。原数据未删除/改写，root的研究标准化应保留状态并隔离这些行。
- H5没有重复日或倒序；原月包价格截止2026-09-30，没有超10/16价格。trading_dates.npy虽到2027-12-31，只是日历而非未来行情；root的近期TQ补尾含10/19未完成条，必须严格按用户<=10/16截断，本agent未写该补尾。
- metadata候选listed_date与695个SHFE原始行存在冲突，集中FU1901/03/04/05/06及WR1903..07。其中3行还有真实正成交量：FU1905/2018-05-09 V4/OI0；WR1906/2018-06-28 V12/OI4及2018-07-02 V4/OI0。故不能把供应商listing当已经官方认证的生命周期；冲突须显式隔离，不能捏造解释。
- Work全部47,751与RQ重叠四价100%一致；V争议733日、OI争议799日，任意字段争议800日。SHFE官方29,316与RQ四价100%一致；V争议69日、OI争议76日，任意字段争议98日。差异不是统一2倍：例如CU1901/2018-12-24官方V45004/OI80464，RQ V41704/OI78370；CU1902/2019-01-25官方V36874/OI66714，RQ V31422/OI66472。保留各源原值和官方优先证据，不能宣称V/OI口径已经全部消解。
- 独立产物：`rqalpha_independent_audit.json`、`rqalpha_independent_contract_inventory.csv`、`rqalpha_independent_old231_coverage.csv`、`rqalpha_independent_row_issues.csv`（1,502条：807正量价格几何问题+695上市候选冲突）、`rqalpha_work_field_differences.csv`、`rqalpha_shfe_official_field_differences.csv`、`rqalpha_SM77_raw_rows.csv`。重放入口`stage265_czce_rqalpha_independent_audit.py`。
- Work另已完成所有47,751行×6字段=286,506单元格原始坐标绑定复验，零重复epoch日；没有拿标准化脚本自己的统计当原始值证明，结果`work_fullmarket_raw_bind_check.json`。
- 独立判定：来源取得有实质价值，条件性接受“隔离raw全市场补史+明确供应商语义”，不接受“全六所2010—10/16生命周期已全齐、SM77已补成真实交易、上市元数据已官方认证、可直接训练或回测”。P0=0；上述无成交填价、正量几何错误、上市冲突和量OI争议均已明确告知root，作为P1研究验收阻碍，不是生产事故。
- 补录结束过拟合判断：否，审计不调策略/模型/样本阈值；继续价值：是，新公开源提供跨2010—2026且全部原231的真实有成交历史，值得受控补尾与冻结质量合同；没有因77个伪平价或重复拟合放宽AM120。仍然训练0、财务回测0、主库写入0、RQ审计脚本网络请求0、正式物料/生产改变0。


## 18:31 合约family边界复审修正

- root复审指出仅接受纯字母+YYMM会漏掉大商所月均价F合约；本agent直接检查H5与安全读取metadata，确认正好42个真实F后缀合约，L_F/PP_F/V_F各14个，原始每family1290行，首日2025-10-29，末日2026-09-30。它们作为独立family保留，绝不并入普通L/PP/V。
- 初次审计10505/94只覆盖标准期货边界，已纠正为10547/97；上面正文和所有审计输出均已更新。旧ER/ME/RO/TC/WS/WT连续代码即便带有效maturity也仍排除。月均价例如L2602F合约月份为202602，虽maturity在2026-01-30，身份仍按代码月份，F后缀与L_F原underlying保留。
- [大商所发布的月均价交易业务说明（瑞达镜像）](https://www.rdqh.com/content/show/228/198985)与[交易所上市通知原文转刊](https://www.topwinfr.com.cn/ExchangeNotice/info/2609)支持这类合约命名与2025-10-28夜盘上市；本机原始首交易日2025-10-29与夜盘交易日口径一致。参考说明用于分类，未新下载行情、未绕站点限制。
- 新增4项分类回归通过：F按合约月、不并普通产品、错误交易所拒绝、旧连续有到期日仍排除、SC一月合约可在前一年十二月到期。原metadata/Work10项保持通过，合计14项。
- F family的正量价格几何错误独立NumPy与普通逐行循环均得5个：L2605F/20251111、L2609F/20260312、PP2609F/20260313、PP2612F/20260618、PP2703F/20260907；故总数807。已把此精确键列表发root对齐其初步808猜测，不按双方预期强行改数字。CZCE、SM77、旧231和Work/官方重叠对照均不受分类修正影响。


## 18:34 root与独立审计计数精确对账

- 808与807唯一差异是`Y0607/2006-07-14`：H5 O/H/L=5110、close=5139、V22、OI42。这条在2010前；root统计全部历史，而独立审计限定2010起。月均价F的异常始终只有5条，先前“第6个F”猜测被精确键差集否定。2010起双方异常集合完全一致。
- root全历史raw行2,331,029，对比独立2010起2,157,204，差173,825行均属于日期统计边界，不改任何raw。
- root排除493对比独立H5内排除489，差`S88/S888/S889/S99`，四者均只存在metadata、不在H5，均为DCE旧大豆连续或指数，maturity/de_listed_date=2003-01-15、listed_date=0000-00-00。root遍历H5与metadata并集，独立排除清单只遍历H5，故是母集边界而非误分类。
- 已对原始安全读取的全部11,355条Future metadata重新应用独立分类函数（未重跑H5审计），独立真实metadata集合10,862与root真实metadata集合逐ID完全相同、对称差集0。双方真实H5均10,547，315真实metadata无dataset。
- 对账产物`czce/rqalpha_independent_count_reconciliation.json`；只读比较和新增证据记录，无改行情、无全审计重跑、无联网或写主库。过拟合判断否；此项差异定位已完成，有价值且无需继续为计数差异改数据。

- 18:37 补充全历史分类：2,331,029=1,700,630正量合法+629,377零量+808几何异常+214供应商日历冲突。107合约各涉及2006-01-26/27；已从root inventory独立计数107/214，并抽原H5 A0603核V42/92且两日不在vendor日历。此为2010目标外的日历冲突，不能称日期非法或删改行情；2010范围结论不受影响。
