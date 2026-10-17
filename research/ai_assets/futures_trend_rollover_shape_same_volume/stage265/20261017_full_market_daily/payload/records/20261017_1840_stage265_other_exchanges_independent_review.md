# Stage265 SHFE/INE/CFFEX官方原包与规范日线独立复核

- line_id：futures_trend_rollover_shape_same_volume；时间：2026-10-17 18:40 CST；reviewer为CZCE子agent，独立于下载/规范化实现者。
- 受root委托复核已冻结的other_exchanges产物；不新增联网，不重解析全部XLS，不修行情，不改变策略/模型。是否重要突破：本记录是数据取得的独立验收，不是策略突破。
- 开始过拟合判断：否，固定来源/范围/质量合同的只读审计；继续价值：是，官方锚点能独立约束全市场供应商数据是否可用，避免把下载成功混为训练资格。

## 独立结论

- 下载与规范化验收：PASS，P0=0/P1=0，限定本组SHFE/INE/CFFEX已取得的官方参考数据。
- 统一训练资格：NOT_QUALIFIED，P0=0/P1=2。P1是`188,965`条有效参考日单位仍明确unknown、尚无统一单位/closeOI/PIT接受合同，以及全市场逐合约生命周期/上市元数据尚未认证（本官方集合GFEX仍缺源）。这两项不否定本组下载成功，不以unknown为由反复联网或修数据。
- 报告`outputs/stage265_deep_daily/czce/other_exchanges_independent_review.json`，SHA `ebd37e0cc8c75abdd4d6b9fee9342ba3c35ce6895e1d1ca98cdd9d49136b0af9`。可复现入口`tools/stage265_czce_review_other_exchanges.py`。

## 原包与血缘

- 34年度包（SHFE2002—2026、INE2018—2026）加199个CFFEX月包（201004—202610）共233ZIP；另外SHFE/INE的10/08、09、12、13、14、15、16各7个JSON，共247来源。
- 全247来源独立重算SHA与字节，共`378,216,882`字节；233ZIP全部逐成员CRC校验通过，文件成员name/size/CRC与manifest一致，目录条目不作为数据成员计入。14JSON逐个report_date、o_curinstrument长度和原manifest一致。
- Stage264六包SHFE2014—2019直接指向原raw_years路径，合计`21,606,045`字节，未复制/重下。检查三份原source manifest与normalization_manifest的hash绑定一致，来源ID247个唯一，未用实现者自报的PASS代替独立hash。
- 三份清单与规范清单hash：`official_archive_sources_manifest.json=cccb1f02727561e57aae1d1166a3d194d232109e23e9edf102591f1c8321a778`；`cffex_month_sources_manifest.json=f07d455b2e1800c3e52a39ceb24e388959a2e79481f3b7203bcf936e611c67c7`；`official_tail_sources_manifest.json=7e1fdb16fce049f547076b7549cdd3d23c8118209323de7f16679f36ae5ed319`；规范清单`8bb05edd2664b63c4c51a84ddd04f25dbdd4e7fdbc80feb46041399af391a432`。

## 全部规范行及抽样原值

- 741个gzip（247×accepted/no_trade/rejected）全部独立重算hash；747,972已接受普通期货行逐行检查有限数、正四价、low<=open/close<=high、V/OI非负、真实YYMM代码与完整交割年月对应、source/exchange一致、<=2026-10-16、close_end_of_day时钟标签。未导入实现者函数复算。
- 独立有效计数：SHFE617,437行/3,337epoch；INE62,837行/396epoch；CFFEX67,698行/692epoch；总33产品、4,425epoch。零重复exchange/product/完整YYYYMM/date，0非法accepted OHLCV，0accepted/rejected键交集。
- 已接受表本次实际V0行0；no_trade表188,950行全部V0，rejected188,980行，其中188,950键与no_trade重叠。另30个异常源行留reject，不填价、不按两份表相加虚增。
- SHFE已接受/无成交/拒绝普通行均无sc/nr/lu/bc/ec，INE仅此五产品，故SHFE发布包中的INE镜像未重复进入候选；跨source有效键全局去重为0冲突。
- 只从12个分层原文件坐标抽样72数值字段，全部与规范值相等：SHFE2002、2014、2019、2024、2026，INE2018、2024、2026，CFFEX201004/202610，以及SHFE/INE20261016 JSON。覆盖OLE XLS、XLSX XML、GB18030 CSV和当期JSON；没有重解析全部XLS。每个样本的原member/sheet/行号留在JSON。

## 最新日期与单位边界

- 33产品逐个有效日期上下界均与catalog一致，全部有效max_date=2026-10-16；SHFE/INE2026年度包只到9/30，10/08—10/16用独立官方日JSON补尾。CFFEX202610真实月包同样到10/16，规范行无10/19未完成条。
- 独立重建10/16全集按集合并：CFFEX28普通=28有效；INE63普通=50有效+13零成交；SHFE238普通=214有效+24零成交。INE13与SHFE24的无成交也在reject里，只计一次，不再相加。
- 单位行数独立统计：原双边259,619；脚注明确单边229,842；原单位未推定188,965；CFFEX明确单边67,698；2026官方日JSON单边1,848。未进行任何除2或将closeOI改成openOI。
- unknown是显式保留的13个来源边界，集中早年SHFE及部分新XLSX无脚注，不由年份猜单边；日期边界也不等同上市/退市认证。全市场训练仍需统一来源、时钟、生命周期和PIT合同，不能拿本参考集合直接训练。

## 主库与结束判断

- 独立流式重算`.vntrader/database.db` SHA `273f0bc18de3070e4e085e4d6585fba71d6e1bb1256e3c7fb5adfc6532836a54`，与Stage264执行前冻结基线完全相等；主库未改。原raw/normalized文件只读，新增仅审计工具/轻量JSON/本记录。
- 本轮新增/修改/删除策略参数无；新增回测结果无。训练0、财务回测0、网络请求0、主库写入0、订单API0；权益/收益/回撤/Sharpe/滑点/交易次数/胜率均不适用。
- 结束过拟合判断：否，未按收益挑样本或调AM120；继续价值：是，来源补齐与冻结验收合同有价值，本组独立下载审计已闭合，无需为unknown单位或已解释重复继续无界补查。
