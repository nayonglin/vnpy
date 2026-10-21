# Stage470：固定年度成熟更新唯一实际 fit/selection 完成

- line_id：`futures_full_market_long_signal_ai`；记录时间：2026-10-20 23:35 CST。
- 工作区 `/Users/mac/Desktop/fian`；沿用 `codex/ai-training-data-expansion`。本记录只读新manifest/terminal/fit_records/selection_summary/held_diagnostic/source_read_receipt，未重读原129动作、COMMON或130分数，未重训、重测或改核心代码。
- 阶段性质：469冻结协议的唯一实际模型与选品执行，非重要突破；独立全市场研究，不是正式C9整合或晋级。

## 协议与调研判断

469协议SHA `f62281e099200e065785b61cc89a47a2111fe7d3dbf2ec60102b167b0708d4f6`；root精确代码授权SHA `97c489de9184bc551c211de41d62935c1847ac76881f2493889ffecb5204e844`。沿准备阶段重新核过的 [Qlib扩窗任务生成器](https://github.com/microsoft/qlib/blob/main/qlib/workflow/task/gen.py) 与 [sklearn时间分割](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html) 只借用时间顺序和扩窗设计。变长first-exit标签以原130的 `u_date<Jan1` 且非空 `label_known_date<Jan1` 为成熟门，固定行gap不能替代该门。

本次唯一变更是固定自然年吸收原目标的已成熟经验。原COMMON52、Ridge(alpha=1/intercept/cholesky)、原129 first-exit `net_R_stress`、原union/day权重算法、原train-only scaler算法、原156共同K/正分/月份动作/ordinary-F家族优先级均不变。新增参数为已冻结annual Jan1时钟；修改为打分更新时钟；删除参数0。没有新增Con4、生存/删失收益、频率搜索、阈值、杠杆或373最新模型回填。

## 唯一实际终态与数据合同

root启动唯一session19352，实际exit0、`status=completed`、耗时 **315.189915542秒**，自动重试false。精确15次新fit attempted/completed均完成，旧六fit仅复用、0旧重训/0旧score重算。0现金、0SQL/API/download；没有生产/CTP/邮件/调度或原四前瞻账变更。

- 原129动作唯一usecols流，读取并保留 **1,552,456** 动作；COMMON矩阵一次解包，原NPZ字节同流生成本次复现copy；原130分数唯一流 **1,933,480** 行，只在2020/2023年度保存分数复用。
- 原母表唯一流保留 **399,252** 母身份、**98产品/95family**。main前向161,014母/966,740动作；holdout_0为64,077母/388,666动作；holdout_1为96,937母/578,074动作，held并集仍161,014母/966,740动作。总输出完整1,933,480条main+held分数。
- 本次完整训练投影、COMMON原字节copy、15新fit的训练身份/权重、union组、scaler、portable/joblib、正规方程、预测checkpoint及阶段checkpoint均保存于实际目录；source_read_receipt的原输入before/after身份全部相同，无新增专门大文件hash扫描。
- 15新fit正规方程最大绝对残差最大值 `5.052424967288971e-08`，全部通过执行时冻结数值检查；这不替代独立审查。

## 七年度成熟训练规模

下表是新fit_records的小metadata摘录；2020/2023行为原六fit，不是本次重新训练。每个held_j训练排除family哈希组j，预测仅取组j；普通/F共享family。

| training_cutoff | 类型 | main训练行 | held_0训练行 | held_1训练行 | 各scope训练日期数 | 最大label_known_date |
|---|---|---:|---:|---:|---:|---|
| 2020-01-01 | 复用3fit | 247,795 | 171,712 | 76,083 | 2,411 | 2019-12-31 |
| 2021-01-01 | 新3fit | 302,256 | 207,846 | 94,410 | 2,654 | 2020-12-31 |
| 2022-01-01 | 新3fit | 369,919 | 250,577 | 119,342 | 2,897 | 2021-12-31 |
| 2023-01-01 | 复用3fit | 445,475 | 297,404 | 148,071 | 3,139 | 2022-12-30 |
| 2024-01-01 | 新3fit | 529,259 | 349,349 | 179,910 | 3,381 | 2023-12-29 |
| 2025-01-01 | 新3fit | 613,421 | 400,525 | 212,896 | 3,623 | 2024-12-31 |
| 2026-01-01 | 新3fit | 707,049 | 455,295 | 251,754 | 3,866 | 2025-12-31 |

各年度部署到该年末/下一Jan1前，末年截于2026-10-16；2026模型只使用2026-01-01前成熟经验。数值权重和scaler对各新训练集重算，仍使用原算法。

## 选品变化与连续性

main选中3,705母，held_0选中1,619母、held_1选中3,680母；这些是信号数量，不能写为现金成交数。相对已接受原156共同K主对照，main **915** 个母选择变化；相对已接受原held_K，held并集 **1,192** 个母变化。selection_summary各scope内部的 `changed_parent_choices` 是同分数加共同K前后对比，不能误当作年度候选相对A157的变化数。

复用年度2020和2023，main与held并集的chosen_action_id、chosen_epoch、chosen_action_sequence_index、selected均严格对齐原控制：2020每域23,814行、2023每域23,716行。2020/2023相同年选择一致是机械复用与相同选择政策的预期事实，不构成现金数量/权益必同证明。

`cutoff` 与 `deployment_fold_cutoff` 保留原2020/2023；年度只在 `training_cutoff` 单列，不按年清仓、切账或重置资本。所有年度main信号拼成一条连续流后交471，2020连续账户与2023冷启动账户仍分别只运行一次/费用口径。因为选择发生变化，不能省略现金检查；完整assembled signal/ranking相同性判定由现金端完成。

## Held原first-exit诊断

诊断是共同K选中动作关联到原129 first-exit压力目标、先family-u后等u的B减A差；不是共同K现金路径，不是收益/回撤资格。distinct未知继续为未知，同一action可抵消差值0但披露原结果未解。

| scope | 已知等u均值增量R | 差异未知family-u | 同动作共同未解 | 全family-u | 已知增量family-u | 状态 |
|---|---:|---:|---:|---:|---:|---|
| holdout_0 | +0.0016927451179754643 | 5 | 22 | 62,434 | 62,429 | unknown |
| holdout_1 | +0.0010111489497926767 | 13 | 30 | 93,651 | 93,638 | unknown |

两组已知均值均非负，但合计18个差异未知，`unknown_R_bounds=null`；不可把它们填0、写稳定跨family完整通过或从均值推导有限总体增量界。

| 年度 | held_0已知均值差R | held_1已知均值差R | held_0/1差异未知 |
|---|---:|---:|---|
| 2020 | 0 | 0 | 0 / 0 |
| 2021 | -0.000803546330 | +0.007810592968 | 0 / 2 |
| 2022 | -0.005185795720 | +0.000105185369 | 2 / 8 |
| 2023 | 0 | 0 | 0 / 0 |
| 2024 | +0.004257732318 | -0.001222638452 | 0 / 0 |
| 2025 | -0.001032460001 | -0.001262637209 | 0 / 0 |
| 2026截至10-16 | +0.018361282503 | +0.001811638942 | 3 / 3 |

已知增量跨年与跨组混合，2020/2023的0由复用机制产生。不能依据2026正值更换频率、舍弃2021/22/25或挑选held组。

## 最终绑定与财务边界

实际目录：`outputs/stage470_annual_mature_fit_select/actual_run1/`。最终manifest先写后保持不变，handoff最后绑定该manifest，不存在循环hash。

| 文件 | bytes | SHA256 |
|---|---:|---|
| manifest.json | 92,956 | `bab35aa627f071abfcea174b83ecc5371ebf2657f60d1be042111a38e19bf268` |
| actual_terminal.json | 778 | `f9879f58a84e89ba7bf64aae4ab67c68beefca86dd164b720e825a397bd1bc0d` |
| fit_records.json | 73,797 | `4b07823975d4c35494ca7ee386680c701277c40a8ae1061e79cdd3c57af8291b` |
| held_diagnostic.json | 3,791 | `f03e1f1a9039c93b4da96f2d6a5b8c4a5c4d0791324b76574c251be27b7a7935` |
| cash_handoff.json | 2,901 | `6480b07dd3361aa05ec63bedaf863c4f5f749720de4f1e227217f089fdf9db16` |

本阶段新增15实际模型fit，累计 **481fit**；本阶段0现金。23:35记录时471四账仍运行，累计完成现金仍 **254**，另1旧partial，须由root实读现金终态后更新。期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率全部 **N/A**，不从信号或first-exit代理推算。production/increased betting/goal资格均未获得。

## 反思与下一步

运行前/后新增按结果调参过拟合：否，本轮只执行冻结年度时钟和原学习规则，无结果驱动代码或参数更改；长期同史多次研究选择风险仍是，当前不是盲OOS。继续价值：是，有条件地完成已授权四本现金账与一次独立综合数值审查；选择变化和已知held均值不能代替财务证据。

下一步root持有471进程与独审协调，本agent不重复启动或监控实际进程，不重跑完成phase。若冻结年度包未过原财务闸门，停止本包，不再以月/季/rolling/decay或新参数救参。本次不改LINE/registry或根memory/back_log，由root统一汇总。
