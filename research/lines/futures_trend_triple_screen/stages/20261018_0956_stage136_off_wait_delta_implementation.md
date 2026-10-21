# Stage136：065/B_OFF已提交分钟数据的中性复用层实现与一次真实候选冻结

- line_id：`futures_trend_triple_screen`；实施时间：2026-10-18 09:50–09:56 CST；非重要突破，不是新金融臂、策略候选或数据资格收据。
- 开始读取 registry、133真实失败、134最终收据/实际projection、135设计以及原061/021源码。沿135已定设计实施，不修改LINE、registry、Git、旧源码、B目录或旧190交付层。
- 调研继承121/123作者资料与GitHub结论；本步骤没有新alpha假说，接口判断来自真实源代码：旧061失败入口硬绑定063/B_TS，不能直接套到065/B_OFF。只复用其无副作用bytes解析、通用数据容器、七值等值追加和full/anchor资格组合数学，不调用旧终态校验器。

## 实现及权限边界

新增源码 `../tools/stage135_accepted_off_wait_delta.py` 与两个组合方法的 `../tools/test_stage135_accepted_off_wait_delta.py`。`freeze_off_delta` 固定134最终snapshot及独立收据的SHA，实际来源保持065/B_OFF；中性内部helper处理来源绑定和交付，不生成独立dataset审查签名。

- 绑定原134审计projection、134最终审查、133真实exit1、065 context/preflight/failure/capture和087 owner。压缩capture只核bytes及SHA，**不解pickle、不读部分账户/PnL**。来源snapshot使用新135 schema，没有伪造旧063终态。
- 必须有实际gate commit及accepted resolver pointer，两处receipt/data四身份匹配；request归属原run的data_wait目录，canonical SHA、file SHA、request_fingerprint、sequence、response和原input_fingerprints均闭合；`old_keys_changed`必须为整型0。
- 继承原021数据资格，重新冻结只解析本次实际选中的交付bytes，不自行重授原receipt资格。JSON/CSV均从同一已hash bytes解析；绑定每份receipt完整source闭包，发布前再核源SHA。
- 七值为open/high/low/close/volume/open_oi/close_oi，跨交付重叠必须精确相等；full可授anchor，anchor不授full，按精确key合并。输出CSV使用17g；原061 loader使用round_trip读取。失败CF505无commit，无价格、raw或权限进入新层。
- 五项产物保持通用061 DATA schema/loader兼容；metadata明确builder135、实际065来源、`compatible_data_schema_only=true`。基底stack、原两anchor和旧190层仅继承路径/SHA身份，不合并、不重存、不重审旧层；未来runner可按固定顺序叠加。
- 临时目录构建完成后发布新目录，存在即拒绝，不覆盖旧产物。真实manifest只能是`frozen_pending_independent_review`，`new_layer_qualified_research_data=false`、`production_qualified=false`。独立review仍由root另行组织。
- fixture使用独立135 fixture projection/review/terminal/owner schemas，并标明fixture_only；共同helper被同样执行，不伪造真实134收据或087 owner。public actual入口拒绝fixture SHA。fixture中容器兼容性审查仅存在临时目录，不代表真实dataset独审。

## 两个有意义组合测试：真实RED→GREEN

仅运行新增文件的两个方法，没有扩旧suite、金融、模型、provider、网络、guard或readiness执行。

1. 来源与同bytes组合：schema/真实失败终态/双记录指针/old_keys/sequence/完整闭包不符均拒绝；public actual入口拒绝fixture；JSON和CSV在首读后换成poison时，解析不重开路径，最终源漂移校验拒绝发布。
2. 相交scope与容器组合：两个交付共享一key，得到3键、2full、1anchor-only；失败request指向不存在raw仍被排除；独立fixture review后用**未改动的061 loader**读取，等值append不改base，compose不放大anchor权限，临时loader和原cache对象退出后恢复；七个值逐项冲突均拒绝，跨receipt矛盾在发布前拒绝，既有输出拒绝覆盖。

命令：`.py311/bin/python -m unittest discover -s research/lines/futures_trend_triple_screen/tools -p test_stage135_accepted_off_wait_delta.py -v`。

| 实际阶段 | tool chunk / session | 真实退出 | 结果 |
| --- | --- | --- | --- |
| RED，09:53 | `956cf6` | 1 | 2 failures，均因新builder尚未实现，非import/fixture错误 |
| 初次实现检查，09:54 | `b91c7e` | 1 | 第二方法已过；第一测试的poison先碰到测试自身算expected SHA，得到提前hash拒绝 |
| GREEN，09:55 | `f4b5b3` | 0 | 2 tests passed，0.161秒 |

检查中的修正只把测试expected SHA在poison注入前固定，生产保护未放宽。RED、检查失败、GREEN全部原样记录，未隐去失败。初次RED使用原configure_runtime默认mkdir路径，未import matplotlib、未产生matplotlib缓存；后续测试及actual均先把runtime.OUTPUT重定向临时目录，finally恢复，再使用临时空shared配置同一022冻结数值栈。不向历史022输出写运行缓存。

证据位于 `../outputs/stage136_off_wait_delta_implementation/`：`red_command.json/red.log`、`implementation_check01_command.json/.log`、`green_command.json/green.log`、`actual_tool_terminals.json`。GREEN log SHA：`473dd8ad611460994b7f9d79a809dc13d4125837159b7a64064337afccfa406f`。

## 一次真实候选冻结

新增两方法GREEN后，直接执行一次相同helper的public actual入口。输入为134最终snapshot SHA `f601f0f32eb258b6cde458754709d2451b433025dbe297619992c59beb42ea18`，134最终独立receipt SHA `2d6f19e8fbb6f94976380ae114c7ca6cde8c70ea4ad5df3d2f9628aeaa9edd7a`。命令完整参数见`actual_freeze_command.json`。

- 2026-10-18 **09:55:37.094346–09:55:39.897085+08:00**；tool session `64940`，initial chunk `eaf675`，terminal chunk `963f0d`，真实 **exit0**。actual freeze次数为**1**，没有重试/覆盖。
- 输出独立目录：`../outputs/stage135_accepted_off_wait_delta/81ffc8f704ce4c5eb701e97e0397b12a/`。
- **159**份真实已提交交付，**36,391**唯一键，**36,345** full，**46**仅anchor，合计36,391键可anchor，均与134审查范围一致；旧键修改0。末失败请求`7422216c316b1eeea381af05e31318dfbea8903ffe77c31c6c9b6c7cf2c087eb`明确excluded。
- `source_fingerprints`共**2,783**项，只绑定所选交付闭包及实际必要来源身份，不重hash projection中7,663个旧市场源。原190层未合并，原159份交付未改动。

| 产物 | bytes | SHA256 |
| --- | ---: | --- |
| manifest.json | 850,092 | `563556d9a70a4f841f606e6b668c6422ae11c7f28f0dcc9203451c20ab2e694a` |
| source_run_snapshot.json | 6,278 | `3e070f4ca1c836b986e5e33fb06e37ca4c43c69f9512a32200bcd51ebef0d232` |
| accepted_deliveries.json | 3,403,323 | `e045bd42b9a97e50b2413d1b1abfb7c41d379214faa62884a9c399107b15a8f0` |
| overlay.csv | 2,630,128 | `c0f979fa5abb8c84d239a01ab1617ccd6fd09def164e9ecf5e0b252b59467f8e` |
| rights.csv | 3,945,752 | `358c986819a505a8d2d276cd2b3f7d53a4350f0b03cec608a6cc4ea3a2ba3ad0` |

源码SHA：builder `e128a199deddf728b24a58ee4511bdb781121fe668945249351a1ed573cc5977`；test `4c990835b19ea6852d05e637d37fa3bfa4a854f0ca17130549045e02e4bca735`。`actual_candidate_inventory.json`绑定五产物与两源码SHA/bytes；actual log SHA `58f5357ab25e59a8be1a24bd84f32cce48d84ea45ac9f1f199360902211ff7a0`。

## 判断、限制及后续

新增/修改/删除策略参数0；新增金融/训练/预测/provider/network/guard/readiness均0；新增完整回测结果0，修改/删除旧结果0。期末权益、收益、最大回撤、Sharpe、滑点、交易数和胜率均 **N/A**，没有读取金融途中指标。

开始及结束新增过拟合判断：**否**，这一步只按固定实际commit资格冻结数据，没有按收益选数据或改策略；不消除此前研究的选择偏差。继续价值判断：**是**，已交付数据可在独立资格通过后减少重复等待；但数据复用不证明alpha，也不把原B失败拼成完整账户。

实施在此停止，供root一次独立代码＋实际候选数据整体审查；作者未签自己的dataset，尚无新层金融使用资格。本阶段不构建未来runner、不启动新金融，不扩大原1800/7200/840秒等限制，不改旧失败与累计金融尝试数。
