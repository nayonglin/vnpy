# Stage461：83 个真实选择变化的有限 score 归因

- line_id：`futures_full_market_long_signal_ai`；实际分析完成：2026-10-20 22:33 CST，记录时间：22:35 CST。
- 当前模式：既有选择/模型分数的离线记账归因；不是重要突破，不新增 alpha，不触发正式 C9 A/B 或晋升。
- 开始判断：本次不重新训练、预测、排序、回测或按成绩调参，新增过拟合操作为否；同一历史反复择题的风险仍为是。继续价值为是：解释冻结 Con4 包造成的既有变化，不能拿归因结果救符号、lag、TTL、映射、窗口或阈值。

## 外部调研与判断

本阶段消费 Stage453/460 已冻结的资料和判断，不新增外部下载或新策略假说：[CFTC 发布规则](https://www.cftc.gov/MarketReports/CommitmentsofTraders/ReleaseSchedule/index.htm)、[官方历史说明](https://www.cftc.gov/MarketReports/CommitmentsofTraders/AbouttheCOTReports/index.htm)、[Liu 等 2023 原论文](https://www.management-review.org/uploads/pdf/paper/mr_2023_42-3_jul_02eng.pdf)、[cot_reports 维护者代码](https://github.com/NDelventhal/cot_reports/blob/main/cot_reports/cot_reports.py)。此前资料只支持集中度假设和有条件历史重建，不证明 strict PIT、国内信号质量或加注资格。当前判断仍是 Stage460 的固定包 `unsupported`，本次只回答既有 83 处选择发生了什么。

## 变更与口径

- 唯一新增分析脚本位于本阶段 outputs 内；未修改策略、配置、训练、K、风控、成本或正式 C9。新增/修改/删除金融参数均 0。
- 原 Stage156 的 accepted `choices_main` 与 Stage456 的 `choices_main`，完整 `161,014` 母身份唯一并逐字段相等：sequence/event/product/family/u_date/u_index/reference、anchor、scope/cutoff、arm/policy。主选择用 `chosen_action_id` 的真实存在位和完整身份比较；Stage156 内部无 K→有 K 的 `1,846` 变化不计入。
- Stage454 可见性审计流完整读取一次，核对上述全母域身份；原始 q 缺失与 unknown 原因原样保留。
- 候选 Stage456 score 只完整读取一次，必要字段筛出 83 母行内旧 A/新 C 已选 action 共 `91` 条；没有读取原 Stage130 score、COMMON、Y、训练表、价格或 native cache。另有探索时表头及首行预览一次，已据实记入 receipt；没有第二次完整流。
- 原大源 SHA 继承 accepted bindings，运行前后 stat（大小/device/inode/mtime）一致；没有额外全文件 hash。两份 main portable JSON 以 accepted hash 核对，最后一列确为 Con4 z，维数 53，2020/2023 系数分别 `0.04525181834683838` / `0.03435646855752286`。

## 选择变化闭合

全域不变 `160,931`，改变 `83/161,014=0.05155%`。A 已选 `4,365`、C 已选 `4,358`，净少 7，等于新增 34−移除 41。

| 变化类型 | 数量 | 占83 | 可见 Con4 | raw N.A |
|---|---:|---:|---:|---:|
| 新增选择 | 34 | 40.9639% | 3 | 31 |
| 移除选择 | 41 | 49.3976% | 31 | 10 |
| 改选合约月 | 8 | 9.6386% | 1 | 7 |
| 合计 | 83 | 100% | 35 | 48 |

“选择”不是已实际资金准入、委托、成交或现金交易。映射产品改变 `37`、90 个结构 N.A 产品中的改变 `46`；实际 q 可见 `35=42.1687%`、raw N.A `48=57.8313%`。后者含结构未映射 46 条，以及映射但 unknown 2 条，原因为 `clock_quarantine;ordinary_grant_crosses_interruption`，没有填原始值 0。

| 年份 | 新增 | 移除 | 改合约 | 全部改变 | 映射 | 可见 |
|---|---:|---:|---:|---:|---:|---:|
| 2020 | 7 | 3 | 0 | 10 | 5 | 5 |
| 2021 | 7 | 14 | 2 | 23 | 12 | 12 |
| 2022 | 10 | 15 | 4 | 29 | 13 | 13 |
| 2023 | 1 | 1 | 0 | 2 | 1 | 1 |
| 2024 | 0 | 3 | 0 | 3 | 2 | 2 |
| 2025 | 0 | 3 | 0 | 3 | 2 | 2 |
| 2026（不完整） | 9 | 2 | 2 | 13 | 2 | 0 |

与 Stage458 全部主年份×映射×可见性分层精确一致。涉及 25 产品，完整品种分层在 `stratified_summary.csv`；改变最多为 DCE.Y 13、DCE.M 11、INE.SC 7。以上是记录分布，不构造新的品种过滤规则。

## 同 action 的 score 分解

对每个存在的旧/新 chosen action，保存两边模型分数，以原 action 身份计算：

`score_delta = saved_C_score − saved_A_old_score`

`direct_Con4 = portable_last_coef × saved_q_z`

`refit52_intercept = score_delta − direct_Con4`

最后一项是全部原 52 维及截距重估的合计残差，不是仅截距；这是减法记账恒等式。本阶段没有读取 COMMON 独立重建 52 维贡献，评分/transform 血缘接受 Stage458 的既有全量核验。不存在的 chosen action 及其所有分数保持 N.A，未补零。

旧 A 选择的旧分数、新 C 选择的新分数与各自 choices 全部吻合，最大绝对误差 0；91 条 score 分解闭合误差 0。

| 范围 | action条数 | 平均总score变化 | 平均direct | 平均52+截距残差 | direct绝对值和 | 残差绝对值和 |
|---|---:|---:|---:|---:|---:|---:|
| 全部存在的A/C选择动作 | 91 | -0.020323534181 | -0.021825252414 | +0.001501718233 | 2.202122105360 | 0.277892760565 |
| q可见动作 | 36 | -0.056072297425 | -0.055169388047 | -0.000902909378 | 2.202122105360 | 0.052710015608 |
| raw N.A动作 | 55 | +0.003075656306 | 0 | +0.003075656306 | 0 | 0.225182744958 |

91 条不是 91 个独立信号样本：75 个开关选择各一个 action，8 个换合约各两个 action。此处均值/绝对值和以 action 为单位，是模型 score 描述；不能称收益、资金或 PnL 的因果贡献，也不能用其占比宣称 Con4 解释了多少收益。

同一 product-u、同一 fold 的 q、z 和 Con4 系数对所有 child 合约是常数，所以直接 q 项不能改变该母行内任意合约的 score 差和 argmax；K 集合和 tie 规则此前未改。8 次实际改选合约的旧/新动作直接项之差均严格为 0，全部 pair 分差变化由 52 维及截距重估残差之差解释，pair 闭合误差 0。同 fold 截距也在 pair 差中抵消；在继承评分血缘成立下，排序变化对应合约相关的原 52 维系数重估部分。唯一可见 q 的 DCE.M 2022-02-24 两动作 direct 均为 `-0.07107534878399051`，总 score 变化却分别 `-0.07117296530218287`、`-0.07067643824644265`，两者分差变化 `+0.0004965270557402146`。不能称 q 直接选中了另一个合约月。

直接项可以改变相对 0 的准入以及跨产品的比较，但原 52 维重估也能改变开关；本次没有把所有新增/移除强行归 q，没有构造去 q 后 argmax、direct-only策略或 hybrid 现金账本。

## 金融结果与执行计数

- 新增/修改/删除金融结果 `0/0/0`；期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率均 N/A，本次没有新回测。
- 本阶段新 fit/cash/SQL/API/预测/价格/native cache/Y/COMMON 读取全部 0；唯一完整分析 `10.744286` 秒。累计仍 `466 fit / 254 completed cash + 1 old partial`。
- inherited Stage460 的 unsupported 及其历史择题、重建时钟、源修订、2026缺源、执行 unknown 等限制不变；本次 score 解释不授予新 alpha、加注、实盘或生产资格。

## 产物、复核与反思

- [receipt.json](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage461_Con4_choice_attribution/receipt.json)：accepted 源绑定、精确读取、全母身份/83分层/score闭合断言、限制。
- [83条完整差异](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage461_Con4_choice_attribution/choice_differences_83.csv)；[91条原保存分数提取](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage461_Con4_choice_attribution/selected_action_score_extract.csv)；[分层表](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage461_Con4_choice_attribution/stratified_summary.csv)；[summary.json](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage461_Con4_choice_attribution/summary.json)。
- 独立 agent 仅复核本阶段小产物和两份 portable，不再读取大源：83/91/各分层和哈希一致，75个不存在 action 的600格分解字段全空；91动作评分匹配/q标准化/分解以及8switch pair差复核通过，未发现阻断性bug。该独审核小产物，不另证本阶段已继承的原大源真实性。
- 结束过拟合判断：本次新增按成绩调参为否，历史择题风险仍为是。没有根据观察到的31个可见移除或31个N.A新增制定任何新规则。
- 结束继续价值：本阶段有限 score 归因已完成；重复重拟合/回测或救当前 Con4 参数无价值。与既有四现金账本的资金准入/右尾损益归因仍可独立衔接，不能把 score 记账当 PnL 因果。
- 本 agent 不修改 `LINE.md`、`research/registry.md`、其他 stage、根 memory/back_log、分支/Git 或生产；日常合入由 root 决定。
