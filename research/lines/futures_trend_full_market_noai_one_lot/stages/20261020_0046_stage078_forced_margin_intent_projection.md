# Stage078 强制保证金减仓：区分未成交意向、规划减量与真实持仓

时间：2026-10-20 00:46（Asia/Shanghai）。研究线：`futures_trend_full_market_noai_one_lot`。不是收益突破版本；是多手执行正确性修复。作者参与实现，不能作为后续金融回放的独立审查者。

## 已冻结失败及根因

首轮金融输出 `outputs/run_20261020_contract_weekly_risk05_v1` 在 2017-03-13 失败，没有完整有效金融指标。本阶段只读该失败源，未重跑或覆盖它。341 笔前缀成交重建实际仅持 SR 空18手、a 空20手；快照中的 TA16、p17、v29 均是未成交 OPEN，实际为0。原生 on_bars 先发这些委托，再在 forced margin 环节遍历策略层，未区分其是否已同步成交，于是为零实际持仓创建平仓事件和 lot；074 在写 lot 前正确拒绝。快照缺少层及实际候选信息，不能断言三个意向中具体哪个触发。

独立失败审查又确认第二问题：003 保留真实保证金底线，所以实际5手尚未真实平仓时，原生 while 每次仍看5手保证金，反复排出 `[2,2,1]`，把应减至3手变成全部平仓。不能通过全局释放真实保证金或放松074解决。

## 新模块及边界

只新增 `tools/stage078_forced_margin_planning.py`，导出 `ForcedMarginIntentMixin`。Root 的新079将其放在074和生命周期之前。旧070、074、原生源码及失败v1完全保留。

强制减仓内部使用独立规划保证金：每个合约 `abs(actual) - 有效pendingClose + 未成交OPEN层数量`，乘因果当前收盘或引擎缓存收盘、合约乘数与保证金率。真实平仓成交前，外部保证金查询仍调用原003逻辑，保留完整实际持仓保证金底线。作用域仅覆盖强制减仓入口与原生 while，异常也在 finally 恢复。

仅在原 forced 功能启用、参数有效，且规划比例超过原 trigger 时，先按原 priority 三种排序之一整单撤销未成交 OPEN，直至规划比例不高于原 target 或没有意向。只撤 OPEN 委托，保留真实 CLOSE。清未成交层、相应目标、待入场诊断、价覆盖及产品预留；保留原预算和周线 receipt 的归档，不改写授权。混合状态只删除未同步部分，剩余层与真实待平量不变。

预留释放通过 cooperative `_reserve_intrabar_entry` 记录本模块实际见证的 pending 预留增量，跨日随原 reset 清空；撤销只扣该 pending 记录，不释放 `total_margin_in_use` 或实际 cluster margin。未见证的旧预留不猜测扣减。当前 replay 的每天开仓预留均经该 hook。

撤销后继续调用原生 forced while：候选只包含已同步、与实际扣待平量相符的剩余层。原 trigger、target、priority、broker multiplier、max reductions 数值及原生数量选择函数均保留，没有复制原生大函数。已有 RSI、生命周期或移仓待平量已从规划中扣除，避免同日和延期重复减仓。

独立取消证据为 `stage078_intent_cancellations`，另有取消次数、数量；不累加 native `forced_margin_deleverage_closed_volume`，不写平仓事件、已实现损益、streak、outcome 或 pendingClose。取消行保留实际取消日期与独立 quote_datetime，防止缓存价日期被误写成取消日；包括 receipt_json、weekly_authorization_json、旧委托ID、实际量/待平量、规划比例前后及释放的 pending 保证金。Root079 导出 `unfilled_intent_cancellations.csv`。

## TDD 和实际引擎验证

产品模块不存在时，空 mixin 接入冻结070真实策略与引擎，首轮8项出现4个断言失败、4个错误，精确复现未成交17手触发074方向硬拒绝、实际5手被清成0、已有 RSI 待平2被重复排成 `[2,2,1]`。实现后首轮8项通过。

扩展到14类场景，在070+078与最终079实际 MRO 各运行一遍，另将074的13项真实平仓场景在最终079再运行，共41项。测试中缓存价跨日取消日期另经历 RED→GREEN，确保记录实际取消日。

最终命令：

```text
PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/tmp/fian-risk05-mpl .py311/bin/python -m unittest discover -s research/lines/futures_trend_full_market_noai_one_lot/tools -p test_stage078_forced_margin_planning.py -v
Ran 41 tests in 0.112s
OK
```

场景包括：多空未成交17手撤销；多空实际5手、权益750、价格110、乘数10、保证金率0.1、broker1.65、trigger0.95、target0.8时仅排2手且重复调用不再平；已有 RSI 和生命周期待平；缺当日行情但有因果缓存的意向撤销；旧OPEN次日不复活；延迟后真实平仓前后实际保证金仍为550、330；三个原优先级及到 target 即停止；同步3/实际5/待平2/未成交17混合状态；取消后真实保证金仍超限继续原生减仓；旧合约待平5+新合约待开17同品种移仓；缺价/未来价拒绝及异常恢复；原074全部数量保护在079栈继续通过。

源码 SHA256：`a3b8477c949fb8321690401c6a9721394cd0ec0950b3599fbf826ba4eaa4f604`。
测试 SHA256：`8e303704208e4a1c209d907cc926a9c19e96cb4fef6558111840ff04d242e27c`。

## 调研与判断

依据冻结原生 `_process_forced_margin_deleverage`、候选排序、`_record_trade_event`、减层函数、003真实保证金底线、074守卫、068授权与原生成交同步顺序核对；外部参照 [vn.py 官方组合策略模板](https://github.com/vnpy/vnpy_portfoliostrategy/blob/main/vnpy_portfoliostrategy/template.py) 对实际持仓、目标和委托的分离。本机真实引擎与冻结源码是决定性证据。

判断：不是过拟合，两个修复都来自未成交意向和实际持仓、规划平仓和已成交平仓的事实区分，没有看收益选参数。有价值继续，原多手版本已在真实回放触发该交互；必须修复后才有可解释的完整金融结果。

## 参数、结果与下一步

新增经济参数无、修改经济参数无、删除经济参数无。0.5%权益预算、信号授权、开盘整笔拒绝、整数取整、long自身合约完整40周门、short规则均未改变。

本阶段没有金融回放。新增、修改、删除的有效金融结果均无；期末权益、收益率、最大回撤、Sharpe、滑点、交易次数和胜率均不适用。失败v1不能当作完整业绩。

下一步：未参与实现者预审078/079，Root全套回归并冻结代码后，仅运行新v2输出。完成后由未参与金融实现的代理全面审查参数和原始数据一致性、逐笔0.5%预算、周线证据、多手FIFO/费用/保证金/移仓/残仓、取消授权和数量投影。作者参与074/078，不提供自我独立认证。未修改 LINE、registry、Git、其他研究线或生产。
