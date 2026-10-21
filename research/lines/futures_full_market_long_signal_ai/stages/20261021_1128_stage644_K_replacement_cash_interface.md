# Stage644：原u旧槽纯K续接现金实验的最小接口

- 时间：2026-10-21 11:28 CST；先读registry，研究线 `futures_full_market_long_signal_ai`。非重要突破；本轮只准备接口，尚未冻结643，没有交易实现、载荷预读或actual。
- 640/638已接受旧四账结构支持28组/17族，但没有证明新预算≥1lot或收益。本轮不能把637名单当C策略：未来C必须根据自身逐日真实持仓、来源和预算重新判断。
- 精确交接：`outputs/stage644_K_replacement_cash/input_handoff.json`，15187B，SHA `7261a7428da64473a2f1ecdb0821d95bc52a526fdf8b37479f1863044da7e40f`。原637文件未改。

## 最小复用边界

新增隔离 `tools/stage644_K_replacement_kernel.py`、`stage644_K_replacement_cash.py` 与一份必要合成测试即可。kernel保持131完整签名和原book字段，新增replacement_audit、replacement_root_ids；入口为 `--protocol --source-ready --output`，fresh目录、root唯一actual。不会引入通用账户引擎。

已定位可直接复用的源：

- 原157完整4365 signals（583263B），含选中action、u/D、实际epoch/anchor及source/K/effective来源。不读取actions334MB、E、Y、全score、旧模型或COMMON，也不重新选择。
- 627 `mother_identity.csv.gz`（19563157B），一次压缩hash及必要列流读建立全u/product canonical references，保留98产品/95族。该文件与原母表体积相近，不声称节省19MB。
- 132 accepted `native_store_cache.npz`（110273488B），原restore函数一次绑定读取并np.load，9520 epoch、1552456合约日；只stat原DB，不SQL或全hash数据库。原CachedMarket提供bar/indicator，5587原日历来自052绑定44824B npy。
- 052绑定economics（8146494B），一次读取精确9520epoch。原131 NARROW真实风险公式为 `.25*N*mult + 双边费 + 双边滑点`；052历史通用字符串仍写2N，不能把该字符串当本轮变更指令。
- A只复用157真实四OWN账户summary/daily及共享diagnostics，不重放A。配对统计沿157→148 `paired_statistics`：相同日序列、原2000重复、252日块、两个旧indices（13144128B与7320128B），不改seed或重生indices。必要时仅按643明确授权附读小BUY身份表。

准备阶段只读131/070/042、157/148/575及132有限源码、157/052/132/639/640小metadata，0 numeric payload、0 CSV数据行、0新header扫描；157小manifest因第一次打印含完整artifacts而被工具输出截断，后续只提取必要绑定，并为交接写入再读metadata，没有隐瞒为单次读取。实际各输入一次IO计划单独冻结，不能沿157老execute调用，因为它会重新读actions和原母表。

## 需要643明确、实现无需扩大框架的接口

u先保持原131自身totals、insolvency、reduction和普通fresh真实target/jointscale预算；replacement单独识别该family旧root来源为严格纯K、下一D到K、旧u非stale/deferred、无reduction且canonical等于旧entry anchor，并使用原same-u另一实际epoch的m1信号。不得要求旧actual epoch等于canonical anchor。所有资格依C自身路径重复计算，不依据A未来持仓或637事后D事实。

642需冻结旧槽风险、margin与两腿费用的精确独立上限，credit只限replacement；普通fresh不能借将来退出额度，prefloor后残余不重分。D沿原131旧仓循环保留，只记录指定旧root确实在开盘以lifecycle_exit完整平仓；只有匹配replacement可在其旧family完整退出后绕过closed_today，其他fresh、deferred、减仓、其他force或日内止损退出仍保持原阻断。D只按冻结分配减量，不凭D盈利增配或重分资金；不能用未来Dlow取消已知开盘两腿计划。

新root使用新epoch/action、N/.25N/low20/raw-open SL0和原quote/qty/fee/margin；旧episode完成独立结算、两腿费用都进账。CapacityLedger继续按各真实epoch日gross计数，旧风险退出不截断，原缺失/超量unknown保留，不能借完整旧SELL宣称新BUY有容量。新增unknown与固定gate的关系仍待643冻结。

## 研究判断与后续

本轮复用635/640已核官方/维护者换月两腿执行资料，不再开新网络或用连续feed替代真实旧平新开；读过version-ab-experiment的触发边界，本线仍是独立研究A157，不是正式实盘baseline或晋级试验。本轮没有新收益，因此没有按收益救参；长期同史反复择题风险仍高。一次预先固定的4C机制检验有条件价值：640已证明结构存在，预算与经济收益仍待验证；失败后不改K、挑月份/品种或加新阈值。

新增/修改/删除经济参数均0，回测未运行，期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率全部N/A。0fit/0cash/0Y，累计551fit/290已完成cash＋旧partial1不变。后续等待root冻结643，再实现必要合成fixtures、source-ready、独立源审及root唯一actual；本历史研究截止2026-10-16，不等待今天日线。

## 11:52 CST：643v2实现与source-ready

本轮已完成隔离644 kernel、薄runner及同一份8类合成fixture，未改原131/157/637或其他冻结源。548只并行编写644薄runner，作者汇总kernel、fixture和ready；没有历史载荷预读或任何actual。本次仍非重要突破，尚无收益结论。

协议从未执行的643v1升级为结果前唯一v2：`outputs/stage643_K_replacement_cash_protocol/protocol_v2.json`（21949B，SHA `b017e3480dafd4eff14f318c78551a658383c07cc22283f6839919597e56ea32`），原v1保留。v2保留原u有界连续target生成Ra/Ba，qu取整只作为最大手数，D不能增加qu；这是读取任何新历史结果前修正重复取整的会计问题，不是看到收益后调参。普通原reserve_capped所有rows的实数分配（含qty_cap=0）进入D虚拟Rother/Bother；日表普通reserve仍只计原pending正手数，与独立contingent列分开，不能双贷旧槽或循环余量。

kernel隔离复制131实际账户循环，原旧仓退出/mark循环与ordinary算术不变。u基于C自身真实root、原same-u m1、严格纯K和旧canonical判断，每次重算，不用637的28组名单。只在指定旧root真实完整K开盘SELL、旧腿容量已知后，才允许对应另一epoch新BUY绕过该次closed_today。D预算只读冻结u快照、已确认旧腿相对u mark的非正净变化、新D.open单位成本，不能读取其他root D.low/close后的账户权益。每个新旧root均保存source/effective/voluntaryK及新anchor、parent和entry_kind，后续仍按自己的K延续或退出；SL0为新raw-open−.25N，原费用/滑点/风险退出/容量unknown不变。

runner仅20个已列输入各一次读取、hash与同buffer解析。132恢复数组体在644本地复用已读取日历/meta，避免原restore隐式重读128/052/calendar；无SQL。A真实四账summary/daily和固定indices只引用，不重放A，不读旧diagnostics、actions、E、Y、COMMON、模型。完整C账本和独立replacement_audit落盘；原signals、calendar、family inventory、A summary/daily和indices原字节复制。只把实际调用的market bar/indicator（含缺失与容量prior）、economics和canonical（含missing）保存新literal给645，避免独审再次读取native或母表。固定门只按v2的C口径，A原unknown另披露，不增A veto；即使promising也仅为条件历史研究，不能证明正式、真实收益或AI加注资格。

### 必要验证与真实执行次数

只运行本轮8类合成fixture，未运行旧suite。第一轮8 FAIL为新kernel尚不存在（RED）；首实现6通过、2失败，分别为fixture精确浮点断言和抽象共同scale输入设置，均定位并修正；v2一轮8通过0.067秒。补入同一8类中的v2明确数例与runner缺失留证/门断言后，最终8通过0.072秒、exit0。完整过程及源码绑定保存fixture_receipt，不将前期失败隐去。最终覆盖无替换131精确数值等价、旧槽不双贷、费用及prefloor、100→100.01仍1手、fund绑定、共同scale/不回收取消及取整额度、严格K/canonical/减仓、旧腿缺失/部分/错因/容量unknown、新raw-stop及未来自身K、D无其他low/close信用、极端tick原cash约束。

- `tools/stage644_K_replacement_cash.py`：27137B，SHA `9a9a603d0f838922d1d1a4fabf3aace76fa594589a20d4cbd05fe42132a1064b`。
- `tools/stage644_K_replacement_kernel.py`：24916B，SHA `3c245f8e442fd4bd8ecb1c76c5630413b0c6e47d894c9e7f849a7839cddaab4f`。
- `tools/test_stage644_K_replacement_cash.py`：13200B，SHA `7fcfd5942d58a8d59e722e69d154e1cb7ec3e826ef06a276224d67964ca1ccb3`。
- `outputs/stage644_K_replacement_cash/fixture_receipt.json`：2190B，SHA `bddb53ecdeec03f38a123802c6b0fbc00fda7f95601dda278df7759f09c05fb8`。
- `outputs/stage644_K_replacement_cash/source_ready.json`：14396B，SHA `04be698d01d38d96b390a944010842d5f300752d0dde6c53f3e4f9439d7de5ad`；包含协议/3源码/fixture/20输入/旧source绑定、新literal schema和原131隔离差异patch。

已交root与645一次完整源审，作者不运行actual。唯一预定实际命令：

```sh
.py311/bin/python -B research/lines/futures_full_market_long_signal_ai/tools/stage644_K_replacement_cash.py --protocol research/lines/futures_full_market_long_signal_ai/outputs/stage643_K_replacement_cash_protocol/protocol_v2.json --source-ready research/lines/futures_full_market_long_signal_ai/outputs/stage644_K_replacement_cash/source_ready.json --output research/lines/futures_full_market_long_signal_ai/outputs/stage644_K_replacement_cash/actual_run1
```

新增经济阈值0；修改实现仅为643/v2明确的独占旧槽预算及对应K两腿续接；未修改原N/stop/K/选品/成本参数。没有新财务指标，全部N/A；0fit/0cash/0新Y，累计551fit/290已完成cash＋旧partial1不变。开始与source-ready结束均判断：没有按新收益调参，但同史反复择题风险高；一次固定4C真实路径检验有价值，固定门失败后关闭该精确政策，不再救参。本研究不依赖今天收盘，END仍2026-10-16。
