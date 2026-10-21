# Stage323：最小因果前瞻三模块独立静审与tiny证据审查

- 审查完成记录：2026-10-20 03:01 CST；line_id=`futures_full_market_long_signal_ai`；非重要突破。
- **静审完成，core_blockers=0，无开放P0/P1/P2。可交root整合最小调用链；本结论不代表receiver、真正T0、PIT、盈利或生产ready。**
- 唯一收据：`outputs/stage323_minimum_forward_review/static_receipt.json`，8550B，SHA `a342319dfe5dc08f407359979d0fb223c512656401e60e97bf8f52e8688ba8bb`。
- 先读registry线身份、317盘点/refs、318及root forward_preparation_acceptance、319实施计划；原004/042/070/129/130/131/156/157仅核关键数学、时钟与D顺序。三模块各在作者final后一次读新source/test和tiny收据，最后只核小文件SHA；未import作者或旧核、未重跑作者tiny、未新增第四组、未读真实价格/标签/缓存/大表。
- 本审0新测试、0金融回测/fit/cash、0SQL/network、0旧suite、0T0创建。只写323自有stage/output，不改作者、LINE或registry。

## 固定依据与审查边界

317/318/root接受的是纯COMMON52最新main/2023 portable+原scaler、156/157同K和070/131 NARROW；没有新臂/阈值、312整数算子或新训练。便携模型/scaler身份继承已接受小binding，未重新打开训练、joblib、全COMMON或旧scores。

新源码以已接收、按版本绑定的输入为前提。本阶段核组件与合成证据，不执行实际新日，不证明全98未来接收覆盖或当前日历/费用元数据已取得。外部原则复用318及root已核的[sklearn预处理/泄漏说明](https://scikit-learn.org/stable/common_pitfalls.html)、[Freqtrade维护者lookahead说明](https://github.com/freqtrade/freqtrade/blob/develop/docs/lookahead-analysis.md)，没有重复搜索、安装或跑其框架。

## 320：因果原26、固定52与原选择

`stage320_causal_forward_core.py`仅从固定SHA小源码抽取纯定义，不运行旧imports、simulate_action、action_stream、fit或CLI。数组先截到u再形成观察、anchor、pool及资格；未来独有product不回写旧u状态。Wilder snapshot明确只代表自己的latest u；要重建旧u应引用旧版本，不能拿未来snapshot重算过去决定。

原004 anchor保留正V最大、有限非负OI降序/missing后、epoch tie，普通/_F按精确产品分池。每个传入既有产品都有母行，无行情与新目录unsupported明列；这证明代码全域构造，不是本阶段实际98覆盖验证。

原own11需21条同epoch、源calendar连续valid bar，分母SMA20 TR；Wilder则20TR seed后逐日`(19N+TR)/20`，保存N/seed/run/last close及low20队列，不以只留21条窗口重种。tiny的N=2→2.9→2.855与原递推一致；缺口/invalid重暖。原u资格可在第20条已成立，own11此时仍NaN；代码没有新增raw全finite准入门。

maturity13按原query排除形成peer统计，front/next basis沿完整product-u pool；最后成本及low20距离沿2N单位。原scaler26值标准化、非有限位置design0加26missing flags、原列序和main2023系数/intercept保持，非有限raw没有改成已知经济0。156仍先D<K/正score/原资格，再argmax和普通/F family优先；精确K pending但已知D早于K_target的充分证明分支保持。确认D不能给此前未知D构造的观察静默升级，需以确认上下文重建因果观察。

selected signal含原157边界及source lifecycle目标。原calendar尾部len是哨兵，不能随扩历冒充真到期；此信息被322接续。JSON journal需将raw NaN编码为null并保留missing flags/unknown状态，不能填数值0。

## 321：时钟和本地追加版本

及时决策的可达分支要求source_completed_at>T0、completed≤received≤sealed<D_open，所有已提供时刻带时区并转UTC。冻结前晚取、缺完成/接收/D时钟、迟到和未seal分别保留；T0=None为not_frozen。forward观察域与及时可决策域分开，不机械自然日+1或制造T0。

journal记录本机真实UTC recorded_at，不能由调用者回填；同key同内容幂等、同key异内容拒绝，修订需新key并保留旧版本。已存在同key但object缺失/变化会报错，不悄悄重建；断尾、链错和entries读到的对象损坏拒绝。append核小索引及当前object，entries是显式完整对象核读，不声称每次追加重hash所有历史payload。

本地内容链是可复核证据，不是交易所首次发布证明、外部可信时间戳或不可篡改服务器；给定clock关系通过不等于source时钟已被验证。

## 322：own-state封存与原D推进

seal_u复制自己的连续ledger，在Through(u)视图内使用原prepare closure封存预算；不读D价。advance_D使用原131 run bytecode及私有globals/ledger恢复，实际D价之前核封存准备、经济作用域和原预算投影。原source模块及globals不改，不使用312，不跨单回收D取消/减量额度。历史singleton末日不prepare下一日的行为由下一seal显式补齐，daily的reserve随同own-state更新。

JSON保存/恢复保留资金、持仓、pending、预算/减仓记录关联、capacity tuple keys及ever_insolvent；拒重复u/D和场景/账户串态。base/stress各自连续，不从100万重复开账。缺价保留entry_execution_unknown或stale/deferred及旧mark语义，不伪造成已知零结果。

source/K目标随原entry复制到position，显式pending哨兵用len+1并标状态；扩展只追加的日历后按首个≥目标的源日重绑。已知完整日历时，`min(search(source_target),search(K_target))=search(min(targets))`，保持原有效边界；未知时不凭旧长度提前退出。原anchor_request在seal刷新，D仍按原强制/减仓/stop/pending顺序。

state组的字面权益可另手算：base D1入场总379手、费用758、未实现3411，权益1,002,653；D2 R的378手退出gross−756、累计费1514，剩余stale未实现9，权益997,739。stress相应D1为1,000,137、D2为997,553。这里只核合成例算术；没有实际盈利证据。

## 三组tiny证据与精确源码绑定

| 模块 | tool SHA256 | test SHA256 | 作者最终证据 |
| --- | --- | --- | --- |
| 320 | `8728cb5730c775c973322ea6f030ed1200f5bb931fd5c448f85e26c415ca35d6` | `772a336bd79d02e7a875099f801b553d1b4451db8bcc8945aa4920b05d205151` | 1方法/4子例，GREEN .223s |
| 321 | `b687c3d6ae8f78dee30a05094c09fb0da3d5c9daa4e12d7132262c3ee052e003` | `3331e6f13c6e21fb43f94783a0021f27be9ad8c7244ec4236ff4c344fca22de4` | 1方法，GREEN .004921s |
| 322 | `8d015968b9c91938e3ac1b38d09b3082fe89bc8ea3e9ea7f12bef47dad989a1e` | `31c01d61eb86882b28ecae4d9566a25b3def1f6f58a044313273430a46064d85` | 1方法，GREEN .249s |

三组均有RED证据。320在同组实现中修复future-only unsupported状态和D-context升级；321修复同key缺object静默恢复；322两次中间ERROR为marshal CodeType引用标记使诊断hash不稳，改稳定code字段后通过，未改策略。323按最终源码核这些路径，不重跑。

322所报8次synthetic原核调用包括小session拆分、恢复和原核比较，全部虚构小行情，不是8本历史/forward金融回测。全phase恰3组/3方法，独审新增组0。各fixture与source_bundle、317/318/319/acceptance精确小binding均在323 receipt。

## 剩余接线及结论限度

后续仅是原318/319已知工作：root连接当前u观察/reference、已封D推进和及时性检查，再以自己的收盘状态seal下一D并追加journal；绑定实际收到的版本/完成时钟/日历/经济/catalog及获授权warmup、真实初始状态，齐全后由root另定T0。本审没有建立接收器、读历史warmup或初始化真实账户，也没有运行最终driver，不能把组件通过说成端到端forward已经开始。

新增结果调参过拟合否；原模型与政策的历史择题风险仍是，forward不自动洗掉。继续价值仅为让随后新证据可核，当前未证明高质量long、收益/DD改善、窄损安全、加注或生产资格。新增/修改/删除金融参数与实际结果均0，权益/收益/DD/Sharpe/滑点/交易次数/胜率N/A。323到此停止，不追加测试或资格循环。

