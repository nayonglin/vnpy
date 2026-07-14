# Stage000 AI 排名稳定性外部假设与路线去重

- line_id：`futures_trend_ai_rank_year_jackknife_qualification`
- 当前模式：`day`
- 记录时间：`2026-07-13 01:30 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：外部/GitHub调研、现有研究去重、新线注册
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- Stability selection 支持用子样本扰动检查选择稳定性，但经典误发现控制依赖 IID；不能把其定理直接套到当前时序横截面评分。
- 时间序列 bagging 论文支持 bootstrap aggregation 处理模型/参数不确定性，也明确序列依赖与非平稳性需要专门重采样；本线拒绝随机 IID bootstrap。
- 排名聚合研究支持透明的 scoring/Borda 类聚合；本线固定平均 ordinal rank，不学习聚合权重。
- 我的判断：当前 full-market “AI” 是固定公式，不存在需要 bootstrap 的模型参数。只对 `24%` 的累计策略收益记忆做过去自然年度 jackknife，最能直接检验单年历史赢家依赖。

## 仓库去重

- 已反证/停止：full-market top8、bottom veto、top quartile、AI+simple top8 共识、AI/account composite、趋势效率、账户高水位、风险簇/产业链、同向相关、covariance/MRC、短时盘口权限路线。
- 已有 moving-block bootstrap 多用于既成资金曲线稳健性，不等于月度 selector 的训练历史年度敏感性。
- 未发现对 current full-market 固定评分逐月删除过去完整年份、再做 Top8 平均名次共识和严格未来60日换入/换出审计的既有阶段。

## 本次变更

- 新增研究线目录、`LINE.md` 与 Stage000/Stage001 预声明。
- 新增/修改/删除正式参数：均无。
- 新增回测结果：无；未读取 future60 结果。

## 结果

- 期末权益/收益/回撤/Sharpe/滑点/胜率：均不适用。
- 总交易次数：`0`。

## 结论

- 本阶段结论：该方向与已有简单 AI 共识不同，允许一次固定资格审计。
- 是否进入下一步：是，进入 Stage001 TDD 与全月度资格审计。
- 下一步：结果前冻结所有输入、扰动、标签和 gate，不跑策略引擎。

## 过拟合反思

- 运行前判断：中等风险；动机来自当前评分直接使用历史盈利，且用户目标特别关注2022，容易后验化。
- 运行后判断：尚未读取标签结果；通过自然年度全覆盖、固定Top8/权重/聚合和无阈值扫描控制风险。
- 原因：不选择“最有利删除年”，而是每个过去完整年份全部进入。

## 继续价值反思

- 运行前判断：有；它直接检验当前全市场评分最可能的结构脆弱点。
- 运行后判断：值得一次资格审计，不代表值得回测。
- 原因：若换入没有跨年未来 edge，可立即关闭而无需昂贵真引擎。

