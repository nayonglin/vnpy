# Stage077 预算支持域独立审查

- line_id：`futures_full_market_long_signal_ai`；记录时间：2026-10-18 17:07 CST。
- 工作区：`/Users/mac/Desktop/fian`；本次只改 Stage077 工具、独立输出和本唯一 stage；不改作者产物、Stage075、LINE、registry、其他研究线或正式策略。
- 性质：有限动作可行域审查，非金融回测、alpha、优化器或收益比较；重要突破：否；正式 A/B：否。

## 开始反思与外部调研

开始是否新增过拟合：**否，限本次冻结候选域的收益盲支持证明**。本次不按 score 大小、最终利润或未来标签选证书，不扩窗口、臂、成本或候选池。既有历史择题偏差仍然存在。

开始是否值得继续：**是，限一次小型可行性反证与独立验收**。它能否决“只要换分配就存在新增一手空间”的解释；它不能证明更高收益、更低回撤或可信的分数幅度。

实际复看 [SPO 原论文](https://arxiv.org/abs/1710.08005) 与 [Cvxportfolio 维护者策略源码](https://raw.githubusercontent.com/cvxgrp/cvxportfolio/master/cvxportfolio/policies.py)。判断：可借鉴预测与当时动作约束分开检查；文献不证明本线换资金分配有收益，不应引入 solver、RL 或纸面预期人民币。

## 第一阶段：合同科学预审

- 已读 AGENTS、registry 本行、Stage074 必要提案、Stage075 合同和冻结协议。
- Stage075：`5209` 字节，SHA256 `44af61b90aa8a8c19c88573dc76b70c39a33b4af72150dde3d2ec4185b69ad62`。
- protocol：`4061` 字节，SHA256 `31b7db98dabc1ca2861ca9039e558dba2adb3a2daaaa49338e00510f449ab9ce`。
- 静态阅读 Stage070 `reserve_batch` 与其候选开关定义，未 import 作者 core，未读真实 `reservations.csv.gz`，未重算模型、金融或旧 suite。
- 科学范围预审：**Critical 0 / Important 0**，实现及真实输出尚待验收。

独立数学反证：设所有新单占用系数非负、原持仓冻结，`q_i` 是正整数 lot 的非负倍数。若某可行向量 `q` 满足 `q_i >= b_i + lot_i`，将其他新单置零只会减少总风险与总保证金消耗。因此同一候选的单坐标可行上界 `U_i` 必须至少达到 `b_i+lot_i`；反过来，若达到，该坐标增加一 lot、其他新单为零就是可行证书。`U_i` 判据在该固定候选域内必要且充分；先试直接 `b+lot` 仅决定展示何种证书，不削弱完整性。

可执行输入必须守住：同一 u 的权益、已有风险和缓冲保证金一致；先核原 `b` 可行；完整 `new_entry`、原 `potential=1`、`label_history_ready20=1`、有限正 score、原 family 唯一、正整数 lot；风险/保证金成本符合原保存值。前向 cutoff 沿 Stage070 固定分块：`u_date < 2023-01-01` 用 `2020-01-01`，之后用 `2023-01-01`。拒绝、减仓或其他非新开仓行不得升格候选，也不得释放旧仓额度。

精度范围在真实 CSV 仍 0 读时由 root 明确：沿 Stage075 的 `Decimal_saved_print_values` 几何，保存十进制值就是本小审计的精确输入，不反推原浮点或真实交易参数的未知误差区间，也不加 epsilon、半 ULP 或其他资格门。若单候选 cap=250，则每手风险=250 的一手可达，250.00000000000001 的一手不可达；结论对该打印边界敏感。原 `b` 在这套几何不合法，属于与已接受原决策的不一致，标记 unknown、不自动归因策略 bug、不放宽约束。负结论只能是“保存打印 u 几何、固定原候选域没有任一坐标增加空间”，仍可少买或全部不买，不涉及别的候选域或信息机制，也不认证实际 D 成交资格。

## 第二阶段：实现与新合成检查

已完整静态审查 Stage076 小实现与全部六项新合成 unittest 的源码；不 import 作者 core、不重跑作者 suite 或旧金融。作者新合成检查报告为六项通过，独审不把它冒称自己的执行证据。

- `stage076_budget_support_audit.py`：18930 字节，SHA256 `2f5cf420113c3a3356993d1260e42b8e94c2a1e7c60c9b3443251a5c18ef15d6`。
- `test_stage076_budget_support_audit.py`：5619 字节，SHA256 `90c7130fc2f9875a69edeb52dababe9538b1ff219eb09ca79a35605ca4b88fb2`。
- 纯标准库、导入无执行；数值 floor 用整数比率，避免 Decimal 除法取整边界。候选资格、前向块 cutoff、原向量、同 family、非负资源/正整数 lot、完整向量保留、ID 字典序直接优先/竞争证书、未来字段投影、精确 source/protocol 授权及 fresh 失败终态均符合小合同。
- **实现可执行预审：Critical 0 / Important 0**。精度疑点已在未读真实值前按上述协议范围澄清；无待修改阻断项，不增新门，不要求多轮旧检测。
- 预审仅允许 root 对上面这份源码和协议精确绑定后启动唯一 actual；它不是实际结果验收或金融结论。

## 第三阶段：唯一实际小输出验收

root 精确授权收据：`outputs/stage075_budget_support_protocol/actual_root_authorization.json`，1853 字节，SHA256 `acbeaad4ddd7d4d16c1bcb0e200f02de7573485efab8bdaaaefcf8ae7e0a1d3f`。Stage076 唯一 actual 冻结 manifest 为 1320 字节，SHA256 `c34de4903d70e340e5575a7671ec526783a053cfd7c3c3fb34f7b346819fb5d9`；终态 `completed_pending_independent_review`，source read=1、actual=1，未自动重试。

独审先冻结自己的标准库 Fraction 小检查器，不 import 作者计算代码、不运行作者 suite：`tools/stage077_independent_budget_support_review.py`，17268 字节，SHA256 `12ca03e564e54847c4189e7f1d9c1257af76d6be1609b84140b0a9b0a26203dc`。冻结收据 `outputs/stage077_budget_support_review/pre_actual_v1/reviewer_freeze.json` 为 1266 字节，SHA256 `e6e54c56efb6fde4b55d73d1318a985b06a4a19361a2c0327ea6361fda95fe74`。

2026-10-18 17:14 CST，按授权只执行一次独立数值验收，源 229690 字节 CSV 独立物理读取 **1 次**，SHA 与 Stage075 一致。逐行核白名单原值、身份、kind、候选资格及原/替代完整向量；用精确有理数独立重算每个 u 的限额、每候选单坐标上下界、所有证明的占用与余量，并逐个核 ID 字典序直接增加优先和竞争全其他新单置零的确定性证书。未读取966084预测或价格，未复算旧金融。

- **实际验收通过：Critical 0 / Important 0**。
- 全部预算行：**1731**；全部 u：**659**；完整原新开仓候选：**1105**。
- 有增量支持：**159 u**（直接增加 137、竞争放弃其他新单 22）；不可增加任一原候选坐标：**359 u**；没有原新开仓候选：**141 u**。
- unknown：**0**；每份原向量在保存打印几何下可行，所有上下界和替代证书均通过独立检查，非新开仓行未释放预算。
- `D_*`、执行日、利润、未来标签、最终持有状态没有进入候选、排序、数量或证书；没有纸面目标函数或假想现金路径。
- 真实验收收据：`outputs/stage077_budget_support_review/actual_review1/review_receipt.json`，1347 字节，SHA256 `2bfaa65641964d17e935f8baa7e5dd2cf1a3810a4c68c036f7cb0e6b1f9f8b1f`，状态 `accepted`。预审、冻结和实际收据分目录保留，未覆写已签收据。

可执行结论是：**保存打印 u 几何下，同一原候选域中部分动作可以不同**。它不证明 score 幅度已校准、不证明更高分应获更多资金、不证明机会损失、盈利、低回撤或券商资金可用性。若下一步讨论纯决策金融对照，须另行冻结科学问题与授权，本审计不自动开启 solver 或新的 fit/cash。

## 变更与结果边界

- 新增/修改/删除交易参数：0；新增/修改/删除金融结果：0。
- 期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率：全部 N/A。
- 本阶段 actual financial / SQL / fit / cash / 价格 / label / 旧 suite / 模型重核 / 全库 hash / 订单 API 均为 0；仅一次独立小数值验收，不是金融启动。
- 不更新 LINE、registry 或根总账，由 root 合入。

结束是否新增过拟合：**否，限此次支持审计与独立验收**。核了预定固定账本的全部 u 和候选，没有按盈利、分数幅度或未来结果选择可行证书，也没有见结果后变 cap、换窗口、扩母体或重新解释打印边界。历史择题偏差仍保留。

结束是否值得继续：**是，完整目标仍有价值，支持域已获一次可复核的正面事实**；但继续自动优化资金/追逐高分/宣称收益改进：**否**。下一步金融研究的价值需先有可反证的独立决策设计和分数语义判断，不得把159个支持 u 当盈利证据。完整 goal 仍 active，未由本阶段完成。
