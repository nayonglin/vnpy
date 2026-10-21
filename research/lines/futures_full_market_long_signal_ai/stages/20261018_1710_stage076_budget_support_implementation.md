# Stage076 冻结预算行为支持审计：有限实现与合成交接

- line_id：`futures_full_market_long_signal_ai`；记录时间：2026-10-18 17:10 CST。
- 工作区/分支：现 checkout，`codex/ai-training-data-expansion`。本 agent 只维护新076脚本、其测试、本记录及076输出；不改075、LINE、registry或其他线。
- 阶段性质：075合同的收益盲整数可行性实现；不是策略优化、模型训练、现金回放或收益归因。是否重要突破：否。是否触发正式A/B：否。
- 本记录初稿状态：实现已通过6项新合成边界，独立077代码审查进行中；真实源CSV读取0、actual 0，未创建实际输出目录。最终源码SHA及root授权单次执行须见下方交接续记。

## 外部调研与判断

- 复核[Python Decimal官方文档](https://docs.python.org/3/library/decimal.html)与[Cvxportfolio维护者策略源码](https://raw.githubusercontent.com/cvxgrp/cvxportfolio/master/cvxportfolio/policies.py)。十进制输入应从保存字符串构造，不能先经float；预测分数与受约束动作应分开。这里只能证明动作存在，不能证明收益改善。
- 原075合同/协议及070 `reserve_batch`/固定前向metadata校验仅作只读定义核查，没有import其作者核心。源小CSV仍未读取。否决求解器、分数幅度排序、收益最大化、补充独立费用cap或回收D取消余额。
- 数学判断：非负资源下，任何可行替代若有坐标增加，将其余新开仓归零仍可行。故每候选最大单独可行整数上界U完整刻画本冻结域的单坐标增量存在性；不否定减量/全不买、其他候选或新信息机制。

## 本次变更与口径

- 新增：`tools/stage076_budget_support_audit.py`、`tools/test_stage076_budget_support_audit.py`；没有修改或删除旧脚本。
- 新增/修改/删除交易参数：均0。CLI仅四项：`--protocol`、`--protocol-sha256`、`--authorize-source-sha256`、`--output`；可调用actual入口同样核代码与冻结协议SHA。
- 冻结协议4061B，SHA `31b7db98dabc1ca2861ca9039e558dba2adb3a2daaaa49338e00510f449ab9ce`；075合同SHA `44af61b90aa8a8c19c88573dc76b70c39a33b4af72150dde3d2ec4185b69ad62`。
- 只接受`NARROW_COMMON_primary_2020_stress`已绑定229690B预留CSV，源SHA `23eadd5a1ac31924703bece8daf9bfb289953fb6b3110b5ee4205920fa6b19cf`；实际入口读取原bytes一次核验并复用解压。元数据与源码核验不读实际行情或预测大表。
- 候选：完整原`new_entry`、ready20/potential=1、正score、原身份和2020/2023固定前向cutoff；不按budget_state、D、最终持仓/闭合或PnL筛选。缺失/冲突保留unknown，不drop。所有原行白名单字段、身份与非proposal/reduction原数量保留。
- 原权益、既有风险和缓冲保证金冻结；S=.0025E，R=max(0,.02E−existingrisk)，M=max(0,.25E−existingmargin)。unit risk已含原费滑，margin为原缓冲值，无新增费用cap。风险和保证金均非负，qty为原round_lot倍数，一family一个原候选。
- 保存Decimal精确核原b；越界不epsilon放宽。按event_id/budget_id字典序优先直接b+一lot；再用首个U可增候选增加一lot、其他新开仓0作竞争证书。保存逐项额度、风险/保证金余额、整数/family证明、原/替代完整向量。
- 分开披露个体一lot不可达、原cap不足一lot、共同scale<1、至少两可交易候选竞争、不可交易fractional proposal资源占用、直接整数余量。fractional资源只是描述，不宣称其因果拖累或移除后的收益。
- 输出合同：`all_u_rows.csv`仅075白名单；`candidate_bounds.json`、`row_classifications.json`、`u_summary.json`、`certificates.json`、`summary.json`、`terminal.json`、`manifest.json`。fresh目录，失败终态保留，不自动修复重跑。

## 新合成验证与金融结果

- 测试先RED：脚本尚未存在，加载失败。实现后GREEN：`.py311/bin/python -m unittest discover -s research/lines/futures_full_market_long_signal_ai/tools -p test_stage076_budget_support_audit.py -v`，6项通过，0.002秒。
- 真正边界：个体一lot不可达；直接增加且非proposal数量不动；竞争需放弃其余新单且不按score幅度挑；不可增仍可降风险、打印原b越界unknown；未来列改变不改判定、错误固定cutoff保留unknown；错误源码授权在协议/实际源读取前拒绝且不创建实际输出。
- 仅跑本次最少新合成测试，旧suite、旧金融回放均0。合成测试不是实际审计或金融回测。
- 期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率：均N/A；新增/修改/删除金融结果均0。累计研究预算沿333 fit/66 cash，不增。

## 反思与下一步

- 运行前过拟合：否，本阶段只实现已冻结单账本的收益盲动作几何；历史选题与已见历史的条件选择风险仍在。
- 合成验证后过拟合：否，没有读未来结果、换账本、改约束或扫描参数。合成边界只能核工程，不能提供普适交易效力证据。
- 运行前/合成验证后继续价值：是，限于一次小支持反证；尚不能支持金融对照或高分加注。实际审计后无支持则停止本分配题，有支持也只接受“同一u动作可以不同”。
- TODO：完成077独审，root绑定最终代码/协议精确SHA，唯一owner在fresh输出执行一次，实际输出再作独立小数值审查。未获该精确绑定前actual维持0。goal仍active未完成。
- 本 agent 不更新LINE、registry或根历史总账，由root合入者按最终审查与实际证据整理。

## 最终交接续记

- 2026-10-18 17:12 CST封源码：18930B，SHA `2f5cf420113c3a3356993d1260e42b8e94c2a1e7c60c9b3443251a5c18ef15d6`。测试5619B，SHA `90c7130fc2f9875a69edeb52dababe9538b1ff219eb09ca79a35605ca4b88fb2`。
- 077独立代码预审已核数学、排序、冻结资源、完整向量与授权入口，未报告Critical/Important。精度疑问由root明确：本域以保存打印Decimal为精确输入，不推断原float/真实参数误差区间，不增半ULP门或epsilon。因此S250时r250一lot可达，而r250.00000000000001不可达；这是保存值条件域差异，不能推广到隐藏真实精度。原b不合法则source一致性unknown，不推断原金融bug。
- 交接时actual 0、源CSV物理读取0；实际输出目录未创建。唯一owner等待root对上列精确代码SHA/冻结协议SHA绑定后执行一次。
- 唯一拟执行命令（实际尚未执行）：

```sh
.py311/bin/python research/lines/futures_full_market_long_signal_ai/tools/stage076_budget_support_audit.py --protocol research/lines/futures_full_market_long_signal_ai/outputs/stage075_budget_support_protocol/protocol.json --protocol-sha256 31b7db98dabc1ca2861ca9039e558dba2adb3a2daaaa49338e00510f449ab9ce --authorize-source-sha256 2f5cf420113c3a3356993d1260e42b8e94c2a1e7c60c9b3443251a5c18ef15d6 --output research/lines/futures_full_market_long_signal_ai/outputs/stage076_budget_support_audit
```

- 本段没有实际结论；后续单次实际与独审须另据真实终态续记，失败不重试。

## 17:13 CST 单次实际完成，待独立数值审查

- root已fresh核源码/测试/协议和077代码预审C/I=0/0，明确授权唯一owner按上列exact命令一次执行。root授权收据`outputs/stage075_budget_support_protocol/actual_root_authorization.json`为1853B，SHA `acbeaad4ddd7d4d16c1bcb0e200f02de7573485efab8bdaaaefcf8ae7e0a1d3f`。本 agent 未改075/源码/协议。
- 唯一执行成功，约0.080秒，终态UTC `2026-10-18T09:12:56.130400+00:00`，状态`completed_pending_independent_review`。actual_starts=1，reservation_physical_reads=1，无修复、无重试。
- 源229690B SHA、代码SHA、协议SHA全与冻结相符；1731个原行全部保留，659个u，1105个完整原候选。候选行之外的626行仍保留原身份、rowkind与数量，不释放已有仓或拒绝记录。
- 支持159u：直接增加137、竞争重分配22；无正数量增量支持359u；无原新开仓候选141u。unknown=0，u错误=0。这不是所有少买/全不买动作无效的结论。
- 分开披露：共同scale<1为240u；至少两可交易候选并scale<1为149u；个体一lot本来不可达317候选；原cap不足一lot为592候选；不可个体交易fractional proposal为317候选。直接增加证书137u呈现原整数向量下剩余额度，fractional资源占用不解释为因果机会损失。
- 所有实际输出位于`outputs/stage076_budget_support_audit/`。关键绑定：manifest1320B SHA `c34de4903d70e340e5575a7671ec526783a053cfd7c3c3fb34f7b346819fb5d9`；terminal495B SHA `24ab9edc6b4bd544654eab4dab663b04db510097d19d272cd529208aef9d56c3`；summary690B SHA `36e62078bafab5f400947738a80eae078f0553e394d326df77fcb5b3a2c14f28`。
- 实际新增fit/cash/SQL/价格/label/下载/旧金融回放/优化器调用全部0，累计333fit/66cash不变；交易参数与金融绩效全部N/A。本段只增加动作支持结果，不增加、修改或删除旧金融结果。
- 已即时交077独立agent对全部小白名单行、上下界、原向量与证书数值审查。source/protocol冻结，不因审查结果修改或重跑本次实际；此时尚未以独审通过结案。
- 运行后过拟合判断：否，没有按收益或新结果换域/加注/扫参，但历史选题风险继续存在。继续价值判断：本单次支持反证已完成，有价值的下一步仅为独立核验与解释条件范围；是否值得金融对照需另冻，不能由159个支持证书直接推出更高收益/更低DD。完整goal仍active未达成。
