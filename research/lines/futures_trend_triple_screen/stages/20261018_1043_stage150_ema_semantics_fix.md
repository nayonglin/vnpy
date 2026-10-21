# Stage150：固定EMA独立机制证据的集中修复

记录时间：2026-10-18 10:43 CST；line_id=`futures_trend_triple_screen`；非重要突破。承接Stage148 I3及root的一次集中修复pass。仅修改本线 `tools/stage140_independent_ema_review.py`，新增本记录和 `outputs/stage150_ema_semantics_fix/`；不改原策略、checkpoint/runner/wait、组合测试、LINE、registry或Git。

## 修复结果和边界

已将固定127的决策、预算、intent/setup、成交回执、execution与真实TradeData串联。缺决策、缺预算、重复意图/回执、重复消费setup、未成交却有成交回执、原生初始成交未被消费、未知母链、已完成DAY仍残留pending均拒绝。预算独立复核risk/margin/single/max及可选broker/cluster手数上界、最小手数、最终q、排序与gross/cluster前缀；前缀继续消耗原始a，包括q=0和DAY未成交，不回填预算。冻结L/S/q必须同decision/预算/成交链一致，合约size、配置risk tick、margin ratio继续与原参数相符。

实际F来自已核TradeData，另核同D/信号日/分钟时间、方向、legal tick、L约束、严格一tick穿透及V≥q。按固定127标量定义重算预测及实际risk/margin、差额和比值；错侧gap的R及其差额/比值必须None，同母只保留真实开平两笔且不得retry。原095 AST提取和030/033现金、库存、成本、权益及母链算法未修改；合法retry可超过初始L，ordinary held-roll继续走原算法。

新增门只审计已有账户，不产生交易。R/L/K/E/B等原生sizing输入采用已冻结的原生观察值，检查其跨表绑定和固定127公式；没有借本次修复重做generic风险模型、vendor定价或分钟峰值保证金资格。fixture中cluster门关闭；其启用公式按已接受127实现，本次没有另造完整金融账户覆盖该分支。pending的未来D分支有严格关联核验，但本保存fixture的pending为空，未以该fixture声称真实末端流量已验证。

## 真实RED→GREEN证据

唯一复用原145保存raw：run_id=`ab83889cb4c240e4862210698b9efa1a`，SHA `71587d488bb59906524bbcace976d8161341f9292540f768880dc6cb62380919`，18420 bytes。原raw和export均未改；每个毒化只在临时副本同步对应CSV后调用完整 `_audit_payload`，避开旧fixture的writer/context SHA变动。数值runtime缓存临时重定向，不写历史022输出。

命令均为 `.py311/bin/python research/lines/futures_trend_triple_screen/outputs/stage150_ema_semantics_fix/regress_saved_raw.py --phase <PHASE>`：

| PHASE | 真实terminal | exit / 秒 | 结果 |
|---|---|---|---|
| RED | `dfaabc` | 1 / 0.455 | 原3类毒化均错误接受，reject断言真实失败 |
| GREEN | `a0bc00` | 0 / 0.458 | 原3类均拒绝；保留当时中间源SHA，不冒充最终冻结源 |
| RED_ASSOCIATION | `fa4aa3` | 1 / 0.552 | 任务明确要求的setup唯一消费、未成交终态DAY两个必要关联反例仍可绕过，真实失败 |
| FINAL_GREEN | `5db740` | 0 / 0.546 | 两条门补齐后，原3类及关联2类共5/5拒绝；保存基线仍通过 |

原3标签：`all_decisions_absent`、`budget_q_differs_from_filled_q`、`risk_margin_values_wrong`。建议root在既有独审方法中额外采用两种有限关联标签：`consumed_setup_reused`、`terminal_outside_account_DAY`；实现脚本展示了对应的跨表一致毒化，不需要新增engine。

保存基线仍为9个真实fixture fills、3个初始EMA成交、1个错侧gap、1个DAY未成交、1次合法retry、1次ordinary held-roll；现金/库存/成本残差最大 `2.91e-11`，cycles residual `1.14e-13`。fixture期末权益149499.69、滑点210、commission20.31保持不变，只用于检验原数学接合，不能外推alpha或计入真实金融12。未重演native/prepare，没有新增回测。

## 冻结与交接

最终唯一修改源SHA：`b510a283756c547325001af547ee6791ad3df800e97ccc58b1178fdeb99d8b9e`，副本 `outputs/stage150_ema_semantics_fix/reviewer_frozen.py` 同字节；最终回归收据 `final_green_receipt.json` SHA `0cb303e0d22c1083336ff2097912b9fd213969917483702d6088917771473808`。脚本SHA `97957b91aac5712831932afdb4c249263805eb547c480fe68dbb2a11e06da9ab`。命令终态、每次中间源SHA及输出SHA见 `implementation_receipt.json` 和各phase收据。旧095 source仍为 `be688b02314b7c9d5a23d21f3cf0575e9d66a6e1f7a8a5b8c80ebcd627426b6f`。

作者已停止编辑独审源；交root将集中修复纳入原四方法+六源compile的一次最终组合验证与裁定，不自行签独立接受，不新增审查人。真实金融累计仍11 attempts / 4 accepted；本轮native/金融/训练/model/provider/network全部0。

## 参数、结果和反思

新增/修改/删除策略参数均0；新增/修改/删除回测结果均0。真实期末权益、收益、最大回撤、Sharpe、总滑点、交易次数、胜率均N/A（本轮仅复用已存fixture验账）。后续只等待root既定组合验证与真实入口裁定。

调研继承121/123/138/143与140/144及148的已闭合源码、协议和来源；本轮只读固定127的预算与actual risk标量定义，未新增联网研究或引入新撮合假设。判断：固定机制值得一次真实证伪，资格和验账通过尚不能证明alpha。开始和结束新增过拟合：**否**，修复与收益高低无关，没有选参、重训或新增金融；既有历史选择偏差不因此消失。开始和结束继续价值：**是**，防止经济账相同但机制证据缺失或任意的账户被标为接受；门补齐后应进入既定真实证伪，不继续样式微修。
