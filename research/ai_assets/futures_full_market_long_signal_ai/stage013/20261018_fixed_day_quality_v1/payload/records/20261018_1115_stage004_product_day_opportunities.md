# Stage004：全市场品种日做多观察母体单次导出

- line_id=`futures_full_market_long_signal_ai`；2026-10-18 11:08—11:15 CST。已先读registry、LINE、001与003冻结合同，沿用户自主研究授权实施，不新增审批、工作树或agent。
- 唯一新增两源：`tools/stage004_product_day_opportunities.py`、`tools/test_stage004_product_day_opportunities.py`；本文和 `outputs/stage004_product_day_opportunities/`。未改其他源码、LINE、registry、003合同、原始数据或Git。
- 重要突破：是，用户新范围首次落成可核对的完整观察母体；不是alpha/模型/策略收益突破。金融/native/prepare/model/provider/network执行0。
- 开始/结束新增过拟合：**否**。代表规则在结果前冻结，只用u当日合法数据，不按收益、D行情或未来成熟筛选。继续价值：**是**，交005一次独审代码与实际表，再定有限路径合同；不把母体完成称为高质量识别成功。

## 实际结果

唯一全量导出于11:14:34—11:14:59运行，**exit0，24.858465958秒**。98个目录产品×4074个绑定calendar交易日＝**399252个唯一品种日**，每产品恰4074行；event ID同样399252唯一。没有重复导出、重建、下载或全库hash。

| 口径 | 实际数量 | 含义 |
| --- | ---: | --- |
| contracts目录epochs / 产品 | 10880 / 98 | 六所全部目录，含DCE月均价F及无区间清洗观察的历史产品 |
| 实际源日线 / 有候选epochs / 有候选产品 | 1552456 / 9520 / 97 | 2010-01-01—2026-10-16当日合格行情，不是可交易或训练样本数 |
| 完整product×calendar积 | 399252 | 含所有无资料日期，不按历史上市/退市推断删行 |
| observed_long_research_opportunity | 212852 | 产品当日有至少一条合法正V参考，只是观察方向long |
| no_accepted_observation | 186400 | 价格/成交量为空，不carry、不造0，不擅分未上市/退市/缺资料原因 |
| 被选择参考的旧flag=0 / 缺真实open_oi | 各117995 | 全部保留，旧字段完整性不充当AI准入条件 |
| 被选择参考的F家族产品日 | 702 | 不照搬旧环境代码排除F |
| 当日不合格源行 | 0 | 非静默假设：仍逐行检查并导出拒绝账header；无纠价/删行凑预期 |
| 整段无清洗观察产品 | DCE.S | 保留4074个no_accepted_observation，不将metadata当历史上市公告证明 |

root提供的五项预期输入计数全部实际一致：98目录产品、4074日期、399252积、212852观察日、1552456合格源行；预期仅作断言，不是删行目标。按产品年、所年完整计数已保存。上述行数不等价于独立日期经验、交易次数、成熟标签、可执行机会或模型容量。

## 固定读取与代表规则

SQLite以`mode=ro`、`query_only=ON`打开；单条按产品/日期排序的有界SQL流式读取目标区间，完整roster来自contracts六所集合，不从有行情记录反推目录。每个产品日只比较u当日quality_status=accepted、有限正价格OHLC且几何合法、有限volume>0的真实epoch：**volume降序→有限非负close_oi降序（缺/非法排最后）→epoch字典序升序**。不使用C9 signal、月池、ER阈值、train标志、未来高量、未来主力或D行情。

身份逐行与contracts匹配，重复exact-contract/date或身份冲突明确失败，不keep-last。完整YYYYMM隔离CZCE十年同名；DCE L_F/PP_F/V_F保留。缺open_oi不填0或shift；缺close_oi不删除本来合法的OHLCV观察，仅明确状态并排最后。无参考行数值保持空。每个事件按版本`stage004_product_day_long_v1`、product_id、u_date的canonical hash固定，reference_epoch另保存，不能改代表规则后沿旧版本改旧ID绑定。

planned D仅取绑定calendar的下一日，可以晚于清洗上界，不查询D是否有价格；无后继才标execution_day_unknown。cutoff仅为 `after_u_daily_data_available_before_D_execution` 合同，`publication_pit_certified=false`；未生成feature_known_at、label_known_at、收益、胜负或质量标签。

## TDD与运行实证

按TDD/executing-plans技能先写四个固定方法：

1. 真实小SQLite的六所完整roster×calendar，含F、无行情产品、旧train/legacy flag0和缺开盘OI。
2. 成交量优先、OI缺失/0、epoch稳定tie、十年同名分别读取；零V、非法OHLC、非accepted逐行明确拒绝；重复日键及catalog身份冲突失败。
3. 在固定calendar和目录下追加未来高量合约或删除D行，不改变早期u的完整row/event ID/选择状态；无calendar后继另测unknown。
4. SQLite真实只读和禁止创建、源小库SHA不变、绑定NPY安全加载、压缩导出空值、既有输出拒覆盖、sidecar守门。

真实RED工具chunk=`03656e` **exit1**，四方法均因selector未实现发生AssertionError（非导入语法错误）；实现后GREEN `2d757f` **4/4，0.055秒**。root新增源绑定含inode和预期计数后，按同一四方法再核最终GREEN `b21c30` **4/4，0.055秒**；只编译新增两源，chunk=`54bd42` **exit0**。未增加第五方法、未跑旧suite。运行记录与当时source SHA见component_verification.json。

Ruling：003要求在既有clean流程上导出，但旧Stage266 reader强含旧七列完整性和pandas依赖；新选择器复用其mode=ro/显式epoch/截断合同，以stdlib实现这一次不依赖opening OI的流式选择，未修改或调用旧heavy reader。技能中工作树、Git commit、另派审查脚本与本任务独占/不改Git要求冲突，以root明确范围为准，验证ledger保存于自有outputs，独立005由root随后派发；没有漏做或冒称作者独立审查。

实际运行命令：

```sh
.py311/bin/python research/lines/futures_full_market_long_signal_ai/tools/stage004_product_day_opportunities.py \
  --bindings /Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage003_product_day_contract/source_bindings.json \
  --bindings-sha256 4423b84d1f16c76947d59a9c1a247916e44d634ebba77ece5b02ebf56260baeb \
  --output /Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage004_product_day_opportunities/export
```

原session82511（启动chunk4ac257，终态chunk1249a2）实际exit0；actual_terminal.json记录唯一actual_export_invocations=1。实际解释器 `/Users/mac/Desktop/fian/.py311/bin/python`，Python3.11.5/SQLite3.43.1/NumPy2.2.3；NumPy只用于`np.load(allow_pickle=False)`读取44,824字节绑定calendar，未引入pandas/策略/模型依赖。

本次不再查原大库的保存后校验chunk=`8584e6` **exit0**：顺序读取新gzip，核399252行、唯一event/品种日、每产品4074、空状态数值空、方向long、原始标记保留计数及所有新artifact SHA。它是作者导出校验，不替代005独审。

## 绑定和边界

DB path仍为旧线 `outputs/stage266_clean_daily/clean_daily.sqlite`，378552320 bytes、mtime_ns1792236170627661666、inode28078628；读取前后完整file state相同，无WAL/SHM。SHA `a63f92ce7e1d51080ba92f7214fc493f1e6a69aa0079d6ecef7190eea9b58711`继承266接受，不重新全库hash；manifest中的source_bytes_hashed_again=0按相邻database_sha_policy指此大库全hash读取为0，小绑定实际仍全部核SHA并从同份bytes解析，不能解读为没核小绑定。

root原binding SHA=`4423b84d1f16c76947d59a9c1a247916e44d634ebba77ece5b02ebf56260baeb`；16项小binding含清洗manifest/contract、单位合同、旧独立receipt、002阶段/manifest/terminal及003事前合同。calendar SHA=`57dd7f539d1cdbefb528978a6c7bd79b118790f933ce63c37b10747b999f9585`。003 SHA=`664a3210b666880b58d27c9ea31b0cfcc535572a0536f5b957867f1b87157bdf`；原266总receipt SHA=`c8067bfad40db0f1817f5e81be9b7c0e4b024a09356d097ed0f5a7aa0b904576`。

002是新线实际盘点终态，**未独审**；manifest明确input_inventory_independently_reviewed=false。本次继承原266固定源准确性范围，不把stat/SHA或计数当逐价全验证、历史PIT发布证明或新资格。

| 新源/产物 | SHA256 |
| --- | --- |
| stage004_product_day_opportunities.py | `a6093f91c30fe835f3ddd84882a074f7b13185ef36013d2ed6f41a0e9ee8f8af` |
| test_stage004_product_day_opportunities.py | `f9357a8fc03ae90f310665b33578f023ad273e6796c87bbe3efa746c41edcd64` |
| export/manifest.json | `1c1c28e54af995dbe4aa516fcd0d7aa80e9be347fe0efaa4408f329425274003` |
| export/actual_terminal.json | `a72b06d9dcfab8e6e41261cc35d1e5dcb8c53762a28741463412b7c9f7da447b` |
| export/product_day_opportunities.csv.gz | `8c6fc733cb14bb2ceb7573735d11f26e8885efd7cfce0d7be5232a3b3910a9ce` |
| export/product_roster.csv | `142b05ff2797ee0510d86144f2a497fda7416121fae100a7e72bc59bbd92624e` |
| export/product_year_counts.csv | `15d55dcdcf4ecf79cf35d6f601b5d0995aa8df3e0715cee78988cf976d7faf61` |
| export/exchange_year_counts.csv | `dca02f0f256f00feb0fbcc8f5426e95f0a5436695d38234b7623d91b26cdb31f` |

原root binding按JSON值归一保存为export/source_bindings.json，SHA=`290b55a1e0aed0cf224a522ca0e5b84a0eb6f4e99e620d9f90f661ad4ecaa1d7`；其格式化字节不同不冒称原binding字节SHA，原原文仍以4423…绑定。

沿001/003已读primary资料及GitHub判断，本次不新增网络：首触达/事件区间不能替代真实交易路径，公开接口骨架不当可运行完整labeler。没有新策略参数、阈值扫描、财务回测结果；权益/收益/DD/Sharpe/滑点/交易次数/胜率均N/A。研究代表规则不是交易所正式主力，更不是可成交证明。缺乘数/tick/margin/费率/时段/限价/分钟不妨碍观察导出，但全部financial_ready/label_ready/model_ready=false。

下一步只交005一次独审代码和实际母体；通过后才另定少量收益盲long路径样本，不抢跑训练、造标签、窄损或加注。新增过拟合否，继续价值是；目标仍active、production_qualified=false。
