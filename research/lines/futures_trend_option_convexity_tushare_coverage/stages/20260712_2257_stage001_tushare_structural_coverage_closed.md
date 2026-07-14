# Stage001 Tushare 与同标的期权结构覆盖终版

- line_id：`futures_trend_option_convexity_tushare_coverage`
- 当前模式：`day`
- 记录时间：`2026-07-12 22:57 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：数据权限与市场工具存在性硬门；不是策略回测
- 是否重要突破：是，证明 2022 关键缺口主要是市场结构不存在，而不是历史文件缺失
- 是否触发 A/B：否；明确禁止 A/B

## 外部调研与判断

- Tushare 官方 `opt_basic/opt_daily` 理论上提供历史合约 metadata 与日行情，但本机当前 token 被服务端明确拒绝，不能声称拥有该数据。
- 郑商所一手资料显示：甲醇期权 2019 年上市，锰硅期权 2023 年上市，玻璃期权 2024 年上市。
- 上期所一手资料显示：燃料油期权 2025 年上市；热轧卷板期权到 2026-04-30 仍处于合约征求意见阶段。
- 大商所一手资料显示：焦煤期权 2026 年上市。
- 跨期货/期权风险管理文献支持凸性工具有理论价值，但也明确存在基差、数量与流动性风险；不存在的同标的期权无法靠更换数据 vendor 补出。
- 我的判断：同标的期权保护在 2022 核心回撤窗口不存在足够交易工具，继续补 Tushare 数据或只回测已覆盖子集会形成严重选择偏差。

## 本次变更

- 新增预声明：`stages/20260712_2233_stage001_tushare_event_coverage_predecl.md`。
- 新增结构门工具：`tools/stage001_structural_option_existence_gate.py`。
- 新增标准库回归：`tests/test_stage001_structural_option_existence_gate.py`。
- 新增输出：核心窗口逐事件账本、产品汇总、decision 与 report。
- 新增参数：冻结 `2022-03-09 -> 2022-06-29`、核心覆盖 `>=90%`、`fu/jm/FG/SM/hc` 各 `>=85%`。
- 修改参数：无。
- 删除参数：无。
- 正式 C9、AI 月池、止损重试、CTP、邮件、launchd：均未修改。

## 权限 smoke

- Python：`3.11.15`；Tushare SDK：`1.4.29`。
- token：环境变量存在，trim 后调用 `pro.opt_basic(exchange='DCE', ...)`。
- 服务端终态：`您的token不对，请确认。`
- 本机未发现第二个配置来源；仓库旧 Stage230/248 也记录同类失败。
- 下载数据行数：`0`；token 原值、前缀、hash 均未写入产物。

## 冻结输入与统计

- Stage131 query-events SHA256：`7abf7a0414238517349e383a6ef7282b5f8d16921686ddc1edb6f2e70e5cc77a`，重算一致。
- 全集仍是 `365` 个唯一事件；结构门只用预声明核心窗口做足以否决硬门的最大可能覆盖上界。
- 核心窗口：`16` events、`7` products、原风险 `3,143,984.2`。
- 不读取 realized PnL、未来收益、MFE/MAE、期权价格、strike、DTE、delta 或策略权益。

| 产品 | 事件 | 原风险 | 2022 同标的期权最大可能覆盖 |
| --- | ---: | ---: | ---: |
| `fu.SHFE` | 6 | 956,200.0 | 0% |
| `MA.CZCE` | 3 | 701,400.0 | 100% |
| `SM.CZCE` | 1 | 452,000.0 | 0% |
| `jm.DCE` | 2 | 438,526.2 | 0% |
| `FG.CZCE` | 1 | 350,658.0 | 0% |
| `au.SHFE` | 1 | 130,560.0 | 100% |
| `hc.SHFE` | 2 | 114,640.0 | 0% |

## 硬门结果

- event 最大可能覆盖：`4/16=25%`，失败于 `>=90%`。
- 原风险最大可能覆盖：`831,960/3,143,984.2=26.461965%`，失败于 `>=90%`。
- `fu/jm/FG/SM/hc`：各自 `0%`，全部失败于 `>=85%`。
- 机械决策：`CLOSE_LINE_MARKET_STRUCTURE_INELIGIBLE`。
- `ready_for_option_strategy_ab=false`、`ready_for_live=false`。
- 禁止 covered-subset PnL、真引擎、strike/DTE/预算扫描和任何收益外推。

## 回测结果占位

- 期末权益：N/A。
- 总收益：N/A。
- 最大回撤：N/A。
- Sharpe：N/A。
- 总滑点：N/A。
- 总交易次数：`0`。
- 胜率：N/A。
- 原因：本阶段没有运行策略或生成交易。

## 验证

- `.py311/bin/python -m unittest ...`：`2/2` 通过。
- `py_compile`：通过。
- `git diff --check`：通过。
- tool SHA256：`280ace45bc73d5a6974ffb335c6d1b81841c18f5b7eeb5699aeef48cd5d4aa00`。
- test SHA256：`4e5cc1ae518bd07b16c83c08358e048ba3e28da4d222ca6125e60375e8725093`。
- decision SHA256：`042f77483da66121b5e912bf50f03a68c720c3b5528de7006fe10659c6901992`。
- ledger SHA256：`d7a17a8d19813995a8b711cc6b9f69cf388497a7045e28f2f4cb6e2b1afabe40`。
- product summary SHA256：`4159eeafe85077028cb1b332522a72f6d4557ba313c0dd24fbfd1507f862b027`。

## 独立 agent 最终 review

- reviewer 独立重读代码、预声明、Stage131/132、官方上市资料并复算核心账本。
- 复算一致：`16` events、`MA 3 + au 1`、`4/16=25%`、`831,960/3,143,984.2=26.461965%`。
- `P0=0`。
- `P1=1`：技术结论已关闭但 `LINE.md/registry.md` 尚写等待审计，可能误导后续继续抓数；本次结果记录同步修复。
- `P2=4`：上市年份只能构造偏宽松最大可能上界；decision/token 状态部分为常量而非统一机械派生；部分来源是年份汇总而非精确公告；缺 input-drift/上市日边界/非法风险/通过分支负向测试。
- `P3=3`：存在本地 `__pycache__`、部分 CSV 浮点表现、输出未做完整 manifest/lineage/checksum 与事务原子写入。
- P2/P3 均不影响结果：所有事件在 2022，缺失产品均在以后才上市；偏宽松上界仍只有 `25%/26.46%`。按用户要求保留日志，不扩大无收益数据阶段的工程修复。
- 置信度：闭线 `99.9%`、统计 `99.5%`、代码无遗留问题 `90%`。

## 结论与边界

- 本线关闭；换有效 Tushare token 或其他 vendor 也不能补出 2022 年不存在的同标的期权。
- 本结论不等于“期权保护无效”，只等于“同标的期权无法覆盖目标历史窗口”。
- 如继续凸性路线，只能另开跨品种代理期权研究线，先验证严格 T-1 相关性和基差风险，未过门不得取期权行情或回测。

## 过拟合反思

- 运行前判断：否；全集、核心窗口、分母和门槛在 API 返回前冻结。
- 运行后判断：否；没有读取收益、没有挑 covered subset、没有调阈值。
- 若用仅 `MA/au` 四事件回测并外推 2022，则会产生严重选择偏差，已明确禁止。

## 继续价值反思

- 运行前判断：有；需要区分数据缺失与市场工具不存在。
- 运行后判断：本线无继续价值。
- 原因：最宽松结构上界已远低于硬门；继续补数据不能改变事实。

## 输出

- `outputs/stage001_structural_option_existence_gate/stage001_critical_window_structural_ledger.csv`
- `outputs/stage001_structural_option_existence_gate/stage001_critical_window_product_summary.csv`
- `outputs/stage001_structural_option_existence_gate/stage001_structural_decision.json`
- `outputs/stage001_structural_option_existence_gate/stage001_structural_report.md`

