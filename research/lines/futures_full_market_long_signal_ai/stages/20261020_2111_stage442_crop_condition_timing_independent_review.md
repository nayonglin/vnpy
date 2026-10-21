# Stage442：Soybeans原优良率→M延迟开盘时机的独立数值复核

- line_id：`futures_full_market_long_signal_ai`；2026-10-20 21:11 CST。独立于作者441；不是新策略或正式A/B，不是重要突破版本。
- 结论：**仅接受441算术与固定协议执行，`remaining_core_problems=0`；经济门失败，停止本固定soy deterioration→DCE.M delayed-open方案。** 不翻方向、换作物/产品/年份/月份/时钟/持有期/阈值/止损或模型救参，不启动成本后现金、加注或扩展98品种。

## 授权范围与真实运行

root先接受439 source收据，再单独授权441一次历史诊断和本独立数值复核。新增唯一独立脚本`tools/stage442_crop_condition_timing_review.py`（21,578 B；SHA256 `098a988e477f1a7882e947356d8f7189542659f480725e5493f568d9fc01ad8c`），不import作者numeric，不重跑441/438。

只读取441本次manifest/receipt/results/event_facts/bootstrap_replicates/terminal及438 crop_rows、440协议、441源码；schema探查额外读到同次started/source_qualification两个元数据，已主动报告，root明确将本次白名单扩到这8个文件，没有扩经济参数。完整全局日历只从accepted427的source_day_features.csv.gz逻辑读取`u_index,u_date`；不读取427的q/价格/成绩，不重读399252母表或110MB cache，不访问原TXT。

首个review1在bootstrap前退出，保留`outputs/stage442_crop_condition_timing_review/actual_run1/failure.json`：审查器错误要求从缺previous_close但仍有u/D报价的非joint事实补算gap，随后发生None减float异常（3,754项检查）。这是审查器null假设错误，未修改作者事实、收益或样本。root另行明确授权修正guard后唯一完整review2；完整已报收益才重算，known要求四价/收益完整，missing exact tuple的D收益整体保留null，不补可计算片段。

review2于21:10:54一次exit0，自计0.5680秒：**41,969项检查，最大数值差2.7756e-16，core=0**。累计2次审查启动、1次完整；没有额外suite、作者重跑、价格cache或金融运行。收据：

- `outputs/stage442_crop_condition_timing_review/actual_run2/review_receipt.json`
- SHA256：`e0b55bc14ec53d4d6c36d8e83714c1d038f5f8f43a44a156422c3d584efe635a`

## 独立重建与结果

作者441代码SHA `1673348e01ce772dc7d9faedad9ff531c2bbe404a0f48a95bc16347eec061a01`，440协议SHA `8ef8794e51f857aa77cbc34dda4c6bef51b9ef1b94e30c59e04a2dd8d1a45c52`；新输出manifest、启动/终态、输入绑定和author日志范围一致。root授权/执行inputs原文件未重开，只核其在已接受started/receipt中的绑定一致；旧报价真值不在本复核范围。

独立从438重建309个soy事件的q、source状态、America/New_York时区次日00假设、第一u15:00及D=u+1，按同u最新发布含unknown覆盖；缺日期1、superseded2、active306，均与441一致。u21仅作最早D开盘下界，不伪造精确夜盘；own_u/gap/after_open/total按发出的同epoch价格重算，恒等误差2.1511e-16。joint采用同一五字段支持，不以已知q替代完整价格。

4074日完整日历、无事件NaN、两era和9年统计全部重建；source资格按release_year、统计era按decision u_date。开发期1459日/209保留事件/joint100，后期727日/97保留事件/joint52。原162个soy source差分不冒充162个价格joint样本。

独立以固定seed 20261020在完整日历生成非循环252日moving blocks，每era2000次，共享indices哈希完全一致；两era×8统计×2000＝32,000个replicate逐值复核，CI、defined/undefined及全部门一致。每项均defined2000/undefined0，不代表3个后期年已有充足独立证据。

| 预定主指标 | 开发2017—2022 | 后期2023—2025 | 后期252日block 95%区间 |
| --- | ---: | ---: | --- |
| q与after_open控制own_u的partial correlation | −0.1000553 | 0.0763409 | [−0.1020059, 0.4772629] |
| 恶化−非恶化的after_open均值差（log gross） | 0.0002445 | 0.0032818 | [0.0009827, 0.0074205] |

后期均值差为正是**mixed支持项**，不能覆盖另一预定primary区间跨0、开发partial为负与逐年门失败：2023/2024/2025只有2024两项primary同时>0，不满足至少2年。全部gate重算为false；不能挑后期未控制raw correlation或均值差宣布优势。

这不是美国条件报告无信息的证明，也不否定论文中的美国即时反应或产量解释。原论文方法局限沿439/440：Bethlem为价格水平回归且断点按best fit选择，不能把摘要数当策略收益；Lehecka只核摘要，不能扩大其美国close→open结论到中国延迟可交易收益。本阶段没有新联网或GitHub搜索，因为只验证已冻结实验计算；不重开WASDE、天气或HGB包。

## 限制、账本与反思

- 原档历史首见/首发字节仍unknown；NY次日00是固定可得性假设，非严格PIT。3个后期作物年的bootstrap只是条件性脆弱筛查，不是已校准的独立周95%显著性。
- 本复核使用新发出的M同epoch事实核算术，没有重读报价来源、母表代表选择或独立价商真值。它不认证真实成交、费用、滑点、止损、现金账户或因果传导。
- 新增/修改/删除策略参数与回测结果均0；权益、总收益、最大回撤、Sharpe、总滑点、交易数、胜率均N/A。原TXT/旧母表/旧cache/API/下载/SQL/fit/cash/forward_D/账户/生产/CTP/邮件/调度修改均0。只写本线独有442脚本、输出和此stage，不改LINE/registry或他线。
- 开始/结束按本次新收益救参过拟合：**否**，冻结参数不变，独审只修自己的null guard；长期自适应择题风险：**仍高**。继续本固定延迟开盘规格：**否**，预定门失败，禁止挑mixed正项救参。独立复核的价值：**有且已完成**，能将真实负结果与算术错误分开。完整高收益低回撤/全市场高质量long目标仍未完成。
