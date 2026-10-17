# Stage059：固定 pairwise19 历史资格的最小修复设计

- line_id：`futures_trend_triple_screen`；记录时间：2026-10-18 05:35 CST；分支 `codex/ai-training-data-expansion`，读到 HEAD `008575e132ea76032d904cbd407aa6f85566b349`。
- 阶段性质：有限只读资格设计，非重要策略突破。本次仅新增本文，没有实现、模型加载、训练、预测、金融回放、行情下载或订单；不改 LINE、registry、035 或任何被消费来源/协议/收据。
- 原 B session70433 / PID21822 按原冻结合同继续；本次没有干扰进程、读取其中途 PnL 或据运行进度选择参数。本文不是下一次金融授权。

## 建议

**先准备 A/B 共同移除 pairwise 决策依赖的全 2020—2026 公平资格对照；暂不以现有 50 行 pair 队列直接滚动重训。** 这是消除一项不可证明历史可用性的依赖，不是证明无模型更好，也不是用弱基准救 B。需要新入口与独立接合证据，不能仅把策略开关改成 False 就复用当前 036 跑。

本文的“无模型”精确限定为 **无 pairwise19 模型**：原 AI 月度选品资格链仍是另一项学习系统依赖，必须保持原字节和既有资格限制。不能把 pairwise-off 宣称为整套策略完全没有模型、全历史严格 OOS 或获得生产资格。

若下一次只在修复后的 A_OFF/B_OFF 之间表现较好，却没有同时满足全区间收益更高且 DD 更低的原目标，目标仍未完成。原 A0 固定模型曲线保留为明确受限的反事实参照，不能从报告中隐藏。

## 证据边界与历史 PIT 术语

先读 registry、本线 LINE、[035 固定 B 合同](/Users/mac/Desktop/fian/research/lines/futures_trend_triple_screen/stages/20261018_0333_stage035_b_ts_execution_contract.md)、[055 条件 context 设计](/Users/mac/Desktop/fian/research/lines/futures_trend_triple_screen/stages/20261018_0514_stage055_ordered_context_ai_design_memo.md)、[057 实体来源审计](/Users/mac/Desktop/fian/research/lines/futures_trend_triple_screen/stages/20261018_0524_stage057_pairwise_training_asof_evidence.md)及已落盘的 [058 独立复核](/Users/mac/Desktop/fian/research/lines/futures_trend_triple_screen/stages/20261018_0532_stage058_pairwise_asof_independent_review.md)。另由只读 agent 交叉核对开关/fallback 接线；本次没有重复加载 joblib 或重算原样本。

057/058 的两项 P1 是：固定实体没有按历史日控制信息可用性的门；缺完整训练来源、成熟标签时钟和选择规则绑定。当前实体与 2020-09-17—2022-12-08 的 50 行/25 日队列高度吻合，61 个候选的最大复算标签终点为 2023-01-06；这些是强队列佐证，**不是原 fit 时刻，也不是给 2023+ 自动放行的 cutoff**。当前账本可审计，与严格历史可交易性是不同判断。

合法历史 PIT 模拟可以在今天重建历史模型，wall-clock fit 时间无须实际早于历史 u。要求的是：每个历史 u 所选择的模拟版本，其训练、预处理、标签成熟、选参和版本选择所用信息都只来自当时已知集合，且可复验。真实历史部署另需当时发布/可用的事实证据，不能由今天模拟补造。后续 manifest 应分别记录真实运行时间与 `simulated_asof/model_available_from_simulated`，禁止混为同一 trained_at。

## 当前真实接线：关闭开关会发生什么

| 位置与证据 | `enable_selection_pairwise_v2=False` 的实际结果 | 修复时必须保留的边界 |
| --- | --- | --- |
| [qmt 初始化](/Users/mac/Desktop/fian/examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py:929) | 新实例的 `selection_pairwise_runtime=None`，不在策略构造器加载 joblib | 要使用新实例，不能复用带旧 runtime 的对象；其他学习模块不能偷偷接替 |
| [评分方法](/Users/mac/Desktop/fian/examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py:4236)及 [plan 默认字段](/Users/mac/Desktop/fian/examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py:4223) | 评分立即返回；score/rank/veto/enabled 为 0，model_tag 为空 | 不调用原 runtime，不沿用旧 score/rank 快照，不用填入虚构中性模型代替禁用 |
| [原 planner](/Users/mac/Desktop/fian/examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py:4670) | 模型分数排序及 rank 赋值不执行；slot 仍按可开候选顺序分配 | 无模型并不等于无限 slot；原并发上限、OI/通用过滤及 sizing 继续生效 |
| [volume tilt](/Users/mac/Desktop/fian/examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py:4454) | runtime 为 None 时立即返回，即使 tilt flag 遗留 True 也不会放大手数 | 新合同仍显式关闭 tilt 及其方向 strength，不能依赖偶然早退宣称隔离 |
| [incremental margin gate](/Users/mac/Desktop/fian/examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py:3263) | 普通 margin 逻辑不随 pairwise 关闭；`protected_by_rank` 需要 `0 < rank <= protected_rank`，rank=0 不享受保护 | 保留普通资金上限、触发范围和减量规则；显式让 protected_selection_rank=0，不把 fallback 序号灌入 AI rank |
| [B 最终预算](/Users/mac/Desktop/fian/research/lines/futures_trend_triple_screen/tools/stage035_b_ts_pricing.py:127) | rank=0 时以原 plan 插入顺序做 gross 前缀；最终仍只缩量、不回收/补位 | 不新增分数、不改变 T/S、预算字段、只缩量或 D gap 披露；这些仍是 B 原声明行为 |
| [B intent](/Users/mac/Desktop/fian/research/lines/futures_trend_triple_screen/tools/stage035_b_ts_strategy.py:126)及 [条件 heap](/Users/mac/Desktop/fian/research/lines/futures_trend_triple_screen/tools/stage028_ordered_engine.py:194) | intent 的 `rank` 可回退到 plan 枚举序号，用于确定同时间条件事件先后 | 这是执行序号，不是 `selection_pairwise_rank`，不能给 margin gate 产生新的“前几名”豁免；真实时间仍优先 |
| [036 预检](/Users/mac/Desktop/fian/research/lines/futures_trend_triple_screen/tools/stage036_run_b_ts_checkpoint.py:676)调用 [022 model smoke](/Users/mac/Desktop/fian/research/lines/futures_trend_triple_screen/tools/stage022_run_c0_qualified_wait.py:369) | **仍无条件 joblib.load，并对 5 行调用 predict_proba**；策略开关不能截断它 | 未来独立 runner 必须有可审计的 pairwise-disabled 分支，不能照搬这项 smoke 后声称全入口无模型加载/预测 |

fallback 的准确来源是：[metadata 将 continuous product symbols 排序](/Users/mac/Desktop/fian/examples/portfolio_backtesting/main_contract_mapping.py:160) → qmt 的 `self.product_symbols` → [同序构造 day_contexts](/Users/mac/Desktop/fian/examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py:1307) → 可开计划插入序。不调用模型时 planner 自身没有再排序；因此本入口最终体现为已定义产品字符串的稳定顺序，而不是 AI rank、临时 CSV 行序或新发明的按 T/波动/OI 排序。两臂须记录同一 metadata 产品列表和 SHA，不能看到收益后改优先级。

只读 A0 的 `actual_strategy_settings.json` 也确认请求配置曾启用 pairwise 和 long tilt=0.15；未读取 A0 曲线之外的新金融结果。qmt 类默认 incremental gate=False、protected rank=0，**但请求 JSON 未出现某字段不等于所有 MRO 的实际属性均已证明为默认值**；未来必须捕获实际对象属性与继承覆盖，不能据此跳过有效设置验收。

## 两条路线的比较

| 事项 | 路线一：双方共同 pairwise-off | 路线二：严格 as-of 滚动重建 |
| --- | --- | --- |
| 修复对象 | 从决策链移除有问题的实体及其分数/仓位用途 | 以可复验历史信息集重建模型，并按 u 选择合法版本 |
| 最小新增工作 | 新入口的共同开关、有效属性、确定性 fallback 和少量真实接合证据 | 全机会母体与成熟标签、训练/预处理 manifest、冷启动与版本策略、模型选择及接合门 |
| 现有样本是否足够 | 不依赖原训练样本，不要求重训 | 不能把原 50 个相关 pair 当充分证据；早期无已成熟支持、候选-only 选择与截断标签必须先处理 |
| 作用于账户 | 同时移除排序、tilt 和 AI rank 豁免；风险和收益都会变，不能说是“只少一列分数” | 排序、slot、tilt、margin/protected rank 全会随新版本改变；修时钟不等于隔离这些经济行为 |
| 资格上能声称什么 | 在既有月池和其他固定条件下，新的全区间 pairwise-free 对照；原 pairwise P1 不再是其决策依赖 | 只有逐 u 的数据/标签/模型选择链成立，才有对应范围的严格 PIT 模拟资格；不等于真实历史部署 |
| 本阶段建议 | **优先准备，但先完成下述证据，原 B 终态后由 root 决定是否另立项** | 保留为后续资格工程；当前不训练，不用它顺便实施 055 |

路线一是当前更小且有效的下一步，因为不需要从不可证明的历史训练队列补造精确 cutoff；路线二不是原模型改个文件名或日期条件就完成。移除旧排序也可能使结果更差，不能预先称为优化。

## 路线一的具体未来合同

新 A_OFF 保留原 native/C9 信号；新 B_OFF 保留 035 独立有序信号、T 估量、原 u 的 S、最终只缩量预算和条件执行。两者共同固定 2020-01-01—2026-10-14、本金 150000、原月池与严格资格时钟、相同成本/数据权限/持仓退出/0.5R 与一次 retry/换月；不改当前 A0/B 文件。**这比较的是完整 035 B package 在共同无 pairwise 条件下的增量，不足以单独归因为信号本身**：T 估量和最终硬预算仍是原已声明差异，不在本次悄悄扩成共同新 alpha。

双方有效值显式固定：

- `enable_selection_pairwise_v2=False`；`enable_selection_pairwise_v2_catastrophic_veto=False`；`enable_selection_pairwise_v2_catastrophic_hard_filter=False`；`enable_selection_pairwise_v2_volume_tilt=False`。
- `selection_pairwise_volume_tilt_strength=0`、`selection_pairwise_volume_tilt_long_strength=0`、`selection_pairwise_volume_tilt_short_strength=0`；这是共同移除既有耦合，不是扫描新强度。
- `incremental_margin_budget_gate_protected_selection_rank=0`。普通 incremental margin、总/单笔/cluster 资本、slot 和 830 cap 等沿各自固定合同，不关闭它们换取手数；若当前有效值本已是 0，就记录无实质数值变化。
- 新实例 runtime 必须 None；决策 score/rank/veto/enabled=0、model_tag 为空；tilt multiplier=1、applied=0。fallback 执行序号单独记录，不进入保护排名字段。其他模型模块保持原禁用状态并捕获有效属性，不能引入替代评分器。

新 runner 不能修改 036 原有身份/输入相等门。它需另声明“仅上述共同政策变化”的精确设置允许差异，其他属性逐项等于旧基准；pairwise model smoke 记录 `disabled_by_shared_pairwise_free_policy`、load/predict/fit=0，而不是伪造一份 passed smoke。模型旧资产可以作为受限参照存档，不能由预检或 fallback 进入决策。日期、完整 1641 日、数据资格、原 source pins、durable checkpoint、独立账本与失败留存的门不放宽。

## 路线二若未来继续，缺什么才算补什么

1. 对训练行记录事件身份、observation 时间、完整 label_end、实际 label_available_at、特征来源和 SHA；同日 pair 的两侧都须已成熟。未入选、未触发、取消、母交易/重试和右删失均保留状态，不能只从旧交易或旧入选竞争日提取“可见赢家”。现有 5/10/20 日 quality 是代理，候选当日整根极值、合约末尾不足 20bar 的截断不能默认为成熟的 B 母交易质量。
2. 先固定一个可识别目标与全机会母体。若只做旧模型资格重建，必须明确旧代理的局限，不能声称已解决 B 触发后交易目标；若要研究 055 的真实母交易净 R，则必须先完成其未入选机会价格路径与成本合同。任一目标都不能在留出结果出来后换标签救参。当前母体/标签或真实竞争不足，**不训练**。
3. 版本选择由事前固定时间表与信息条件决定：每次预测 u 仅选择 `model_available_from_simulated <= decision_at(u)` 的合法版本，其全部训练标签可用时间须严格早于该版本模拟训练截止，且截止早于本次预测信息时点。source、训练 sample IDs/标签 manifest、预处理/选参政策、模型 SHA、数值栈和两种时间分别绑定。今天真实 fit 时间用于复现，不拿它冒充历史已部署时间。
4. 原队列在早期历史并无足够成熟支持的证明。须在全 2020—2026 内预声明共同冷启动政策：没有合格版本/标签时双方用同一 pairwise-off fallback 或明确资格失败；不能回退旧固定模型、让一臂偷用新模型，也不能从 2023 后才计收益。未来若有真实 2020 前样本，另验证其资格，不在本文假定它们存在。
5. 同日所有 pair 按日期归组；同一 setup/母交易及重叠结果区间需 purge，使用实际 label_available_at 和依赖关系控制时间，不能把“删 20 行”当“20 个交易日已成熟”。标准化、校准和超参选择只用合法训练/内层过去验证；完整失败版本计入研究谱系。两臂用同一预声明训练/版本政策，B 新标签的支持风险单独审计，相同策略政策不保证候选分布相同。

官方 Qlib `RollingGen` 支持 expanding/sliding 与 `trunc_days` 截除，scikit-learn `TimeSeriesSplit` 提供按序切分与 `gap`；后者的 gap 是样本数，且可比时长的说明以等距样本为前提。B 的事件/pair 不等距且标签依赖可变，这两项工具都不能自动证明成熟标签、无选择泄漏或 alpha。本次仅查官方方法，不安装 Qlib，不升级冻结 sklearn1.8.0/pandas2.3.3/numpy2.4.4/joblib1.5.3，也不执行这些工具。[Qlib 官方源码](https://github.com/microsoft/qlib/blob/main/qlib/workflow/task/gen.py)、[scikit-learn 官方文档](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html)

## 下一次金融前的最小证据与停止条件

本阶段不运行以下验收；它们是未来实施的有限门，不要求重扫旧 suite：

1. **有效政策与无加载证明。** 新 A_OFF/B_OFF 独立 settings/源码/参数 manifest 对照，明确共同关闭项、原 B 差异和其他零差异；覆盖真实新策略初始化及新 runner 的禁用分支，证明 joblib load、model smoke、predict 都未进入，模型/特征不存在时不能转入隐式评分。只看配置字典不够。
2. **一个联合预算反例。** 真实 native planner 加 B 包装，两个以上候选争 slot/margin，旧 score 残值即使被注入也不能改变确定性顺序/tilt/保护资格；rank=0 不受保护；普通 margin 仍能拒绝或缩量。核 final q、gross 前缀、单 reserve 和 fallback 执行序号，不给 A/B 伪造相同手数或声称固定资本上限等于风险暴露完全匹配。
3. **一个真实执行接合场景。** 沿真实 847/028 组合证明无 AI rank 时 ordinary/conditional 的时间队列、actual fill、synthetic/母单和 retry 身份及成本仍闭合，缺分钟仍同原门阻塞。只验证必要边界，不重放旧 26 组或整栈数据资格。
4. 以上由独立审者接受后，root 才能另行冻结新入口并决定一次全区间 A_OFF/B_OFF 资格比较。只准当前两臂，不给排序、tilt、冷启动日期或本金做变体搜索；不得在原 B 运行中换模/换参数、重启或先看部分收益决定是否完成。

验收保留两个不同问题：

- **修复后的增量是否成立：** B_OFF 对同条件 A_OFF 的成本后全期净收益更高、DD 幅度更小，Sharpe 不低，margin/生存/非空门不恶化；失败则结束这次固定比较，不靠变弱 A 或删早期段改结论。
- **原用户目标是否完成：** 同表公开 A0 固定模型反事实、冻结 B 原终态（若已接受）、A_OFF/B_OFF 的完整指标与资格限制。原 A0 为 2,262,595 / 1,408.396667% / DD −48.789850% / Sharpe 1.367364；它有 057/058 的限制，不能冒称严格 PIT 正式基准。若 B_OFF 仅胜 A_OFF、绝对净收益或 DD 未同时优于原目标参照，则最多称受限条件下有增量，**不宣布已找到收益更高且回撤更低的版本**。即使超过原反事实数字，也需其余 PIT/成本和固定 1月/6月独立 1/2/3年多周期、弱段及独立审查，不能由一条全期曲线晋级。

如有效属性不一致、旧模型仍被加载或影响决策、fallback 非确定、预算/身份接合失败，金融前即停。滚动路线如无合法早期版本政策、成熟标签不可识别或机会不足，停在数据/标签研究，不训练。055 context 的 19 对 19+context 仍未获得实施资格；本次资格修复不代替该增量证据，也不自动豁免 035 的失败停止规则。

## 本阶段结果与反思

新增/修改/删除策略参数、实现和金融结果：均 0；期末权益、总收益、最大回撤、Sharpe、滑点、交易次数和胜率：本阶段均 N/A（未运行）。只写此唯一 Stage059，未改 LINE/registry 或运行资产。

开始与结束是否新增过拟合：否。本次依据已确认的资格问题设计共同政策，没有看 B 中途收益挑方向；既有历史研究选择偏差并未因关闭一个模型而消失。是否值得继续：**有界的资格修复值得，立即滚动训练/context 或金融运行尚无证据和本阶段授权。** 推荐路线一的准备工作，是因为依赖少且能直接回答全区间共同无 pairwise 时 B package 的增量，不是因为预知它会赢。
