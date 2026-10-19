# Stage085 延期 OPEN 原授权与资金事实闭环

时间：2026-10-20 01:13（Asia/Shanghai）。研究线：`futures_trend_full_market_noai_one_lot`。非收益突破；属于取消一手限制后发现的执行状态修复。作者参与085/086实现，不能担任该金融版本的独立审查者。

## 失败事实与范围

v2 `run_20261020_contract_weekly_risk05_v2` 虽完成全段，独立审查确认13次旧单原授权丢失：原下一会话缺bar或整单量不足，实际未成交，native actual=0 reconcile 仍 reset 掉未成交层和068 receipt，target/旧OPEN尚存，后续重挂成为无授权拒单。13案中8案映射未变，5案为空或换合约，不能把全部丢失解释为换月。典型包括 RS201509 原信号2015-06-04空113手、6/5量6；fb201509空13手遇量7；wr202005空19手遇量14。

本阶段不重跑或覆盖v2，不改冻结的074、078、079、068、075或其他历史模块。新增085两个 cooperative mixin 与独有测试；086为独立入口。判断依据包括独立代理的真实MRO复现和原生 on_bars/flatplan/reconcile/rebalance 时序，以及官方 [vn.py 组合策略模板](https://github.com/vnpy/vnpy_portfoliostrategy/blob/main/vnpy_portfoliostrategy/template.py) 的实际持仓/目标/活动委托分离。冻结本地实现及真实引擎测试是决定性证据。

## 窄适配

`PendingOpenLifecycleMixin` 位于新策略MRO最前。只保护actual=0、唯一未同步层、唯一真实活动OPEN且原068 receipt 的合约/产品/方向/信号/日期/整数授权量/冻结止损与target精确一致的意向。long还验证原075周线授权，short不查询周线。原receipt对象和字段保持不变，不重新计算预算，也不因新的信号扩大或替换授权。

每天native reset后识别有效旧意向并恢复pending产品占位，跳过其flatplan，actual=0 reconcile保留同一个层/receipt；新信号不能覆盖。无活动单的旧层和孤儿target不受保护，清理旧OPEN诊断/target/订单并归档，不动真实CLOSE或实际仓位。真实新信号通过原开仓链创建的新层/receipt会取得本回调双对象身份标记，仅用于资金计量中的首次派单过渡；不是凭日期重造授权。

映射空/变合约、授权/量/target失效显式取消，不能调用原生平层函数制造CLOSE、损益或streak。缺当前bar但映射仍为同一合约时保持意向；rebalance仅为已验证的延期OPEN补缓存报价供派单，缓存不进AM、信号、history_data或成交资格。真实成交仍需要后续真实bar、全单足量、原预算/止损/周线/生命周期闸门。新 `PendingOpenLifecycleEngineMixin` 在原生命周期取消调用前归档原receipt，截止表达式与时点沿用原016，没有提前一个会话。

Stage502先cross再on_bars，因此仅在收盘取消映射失效还不够。085通过真实缺bar/低量延期或每日preserve记录原receipt对象身份；只有该延期/保留链在以后fill前核当前因果映射和原绑定，失效先取消。普通首次 T→T+1 OPEN未新增映射门，保留原语义。延期身份不依赖事后利润，不能授权新意向。

## 资金与真实浮盈亏

仅保留层还会揭示旧max口径漏占用：003的 `max(native层保证金,actual保证金)` 无法相加“已全部排平但尚未成交的实际A”和“待开B”。085外部保证金按实际物理数量保证金 + 有效未成交OPEN保证金逐合约相加，并按cluster相加。只在估值查询使用因果缓存，不把补价传给整个风险刷新或指标。

global及cluster reserved动态使用上述资金事实，并扣除078已见证的pending reservation重复覆盖；未解释的原生额外reserve只保守叠加。本回调真正创建的fresh rollover新腿即使旧合约实际仓位尚待平，也必须计入资金，不能被旧pending的保留资格过滤掉。078的强制规划作用域仍直接super，维持 `actual - 有效pendingClose + intent` 的专用规划语义，不把真实保证金底线加回去造成重复减仓。

cluster真实浮盈亏只来自仍实际持有的份额：同步剩余层 + pendingClose lot 的原entry价，数量与实际仓位守恒。未成交OPEN不计假浮盈亏，已经排平但尚未成交的实际份额继续计算真实浮动损益。原heat、保证金、预算等经济阈值均未修改。

每日每个有效旧意向仅在reset写一条preserve事件，包含日期/合约/手数/target/活动委托ID/原receipt与weekly JSON；status读取无日志副作用。取消和缓存派单独立记录，086输出并绑定 `pending_open_lifecycle_events.csv`。086账户快照增加物理保证金、实际+pending保证金、reserved、原pending reserve及cluster资金/真实PnL的只读审计列。

## TDD 与验证

首次无产品模块的真实079链9项测试产生7个断言失败、1个错误；精确包含低量后native reset删层、缺bar取消重挂、孤儿target和映射清理遗漏。实现期间只校正了合成fixture的原周末/信号日期与provider字段，未修改冻结输入。随后对独审新增的以下事实分别建立RED再GREEN：缺bar漏270保证金；实际500+待开270漏算为500；纯pending产生300假cluster浮盈；真实延期跨新日映射变化先成交；fresh rollover资金漏新腿；无层/单孤儿诊断未清理。

最终定向 `test_stage085_pending_open_lifecycle.py` 63项通过（0.370秒）：085+079、最终086双栈的18类新场景，以及074的13项、078的14项真实引擎保护在最终086复验。原078合成fixture在新测试子类中补全085要求的原始身份/日期/周证据，未修改冻结078测试。`test_stage086_runner.py` 3项通过（0.038秒），验证经济参数全键一致、MRO/provenance及缓存asof仅导出标注。

完整研究线回归：

```text
PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/tmp/fian-risk05-mpl .py311/bin/python -m unittest discover -s research/lines/futures_trend_full_market_noai_one_lot/tools -p 'test_stage*.py'
Ran 401 tests in 31.034s
OK
```

合成断言包括：缺bar/低量→真实native on_bars/flatplan/reconcile/rebalance→以后真实足量fill，receipt对象和signal日期保留；真正fresh新信号首派单；新signal竞争不重算；mapping切换前置拒绝与普通首次next-open对照；原风险/止损/周门拒绝；缺bar到生命周期截止仍由原gate取消；强制取消后不复活；global/cluster770、原额外reserve7保守成为777；真实250 cluster浮盈；原078规划仍为270；多空、移仓、部分/全部待平保护。

## 参数、结果和冻结

新增、修改、删除经济参数均无。保留0.5%=0.005总权益预算、整数向下取整、原信号预算上限与开盘整单拒绝、exact-contract已完成40周long门、short规则、原日期区间、生命周期及全部原始行情。没有金融回放；无新增有效业绩。期末权益、收益、回撤、Sharpe、滑点、交易次数和胜率均不适用；v2因P1被阻断，不能作为有效完整结论。

085源码 SHA256：`33099a87fbc2d37b2f64d839ae652113d5c47c91eb8eaf03a024fa8066c625c3`。
085测试 SHA256：`1d7ba7905638d72ca159903cf9b05673271e069fc8bf22d64a3575fa034ec98d`。
086源码 SHA256：`90ac9d27ef0326eb3a72be1e84e26e186d85e066e95f9eb2462b61aec4ce3bf4`。
086测试 SHA256：`159de4d6bd4876ddeeea6739f643532daff51cdabbf98ea02d895b6481f8289e`。

不是过拟合：所有条件来自延期授权、真实数量、占用资金和未成交/已成交的事实区分，没有按收益选参数。有价值继续：独立审查已证明v2无法正确表达该生命周期，修复后才有值得评价的金融结果。下一步为独立Stage088预审，通过后Root冻源、预注册并只跑新v3；完成后由未参与金融实现者审实际结果。未修改LINE/registry/Git/生产或任何旧输出。
