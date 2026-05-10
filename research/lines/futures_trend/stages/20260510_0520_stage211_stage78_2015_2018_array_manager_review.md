# Stage211 第78 2015-2018 ArrayManager 信号链路复核

- line_id：futures_trend
- 当前模式：day
- 记录时间：2026-05-10 05:20
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：回测复盘 / bug归因 / 只读诊断
- 是否重要突破：否，但修正了 Stage210 的表述重心
- 是否触发A/B：否

## 外部调研与判断

- vn.py PortfolioStrategy 文档说明：策略初始化会加载历史K线，`ArrayManager`缓存指标，初始化完成后策略才可正常发出交易信号。
- vn.py `ArrayManager` 实现中，`update_bar()` 后 `count >= size` 才会把 `inited` 置为 `True`。
- 我的判断：
  - 用户质疑成立。不能把2015-2018无成交简单解释为“没有符合开仓信号”。
  - 更准确的层级是：真实合约级 `ArrayManager` 在早期主力换月中绝大多数天没有初始化，因此大多数日期根本没有进入 `_generate_signal()`。

## 本次变更

- 新增脚本：无
- 修改脚本：无
- 删除脚本：无
- 新增产物：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage211_2015_2018_am_readiness_summary.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage211_2015_2018_am_readiness_by_year_size120.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage211_2015_2018_am_readiness_by_product_size120.csv`

## 代码链路

- `QmtRollPortfolioStrategy.__init__()` 为每个真实合约 `vt_symbol` 创建独立 `ArrayManager`。
- `ArrayManager` 实际大小：
  - `max(ma_extra_long + donchian_entry_period + 20, array_manager_size_floor)`
  - 第78当前为 `max(40 + 20 + 20, 120) = 120`
- `on_init()` 调用 `load_bars(warmup_days=90)`，但正式信号仍要求目标真实合约自己的 `ArrayManager(size=120)` 已初始化。
- `on_bars()` 每天先更新所有真实合约AM，再根据主力映射找 `target_contract`。
- 如果 `target_am.inited == False`，代码直接 `continue`，不会调用 `_generate_signal()`。
- 因此，早期没有信号不等价于“指标算完没有信号”，很多时候是“合约级指标窗口不够，未计算信号”。

## 2015-2018 AM就绪复核

- 第78静态品种池映射日：`18,525`
- 有真实target bar的 product-days：`11,136`
- AM size = `120` 时：
  - `inited_days = 41`
  - `not_inited_days = 11,095`
  - 初始化占比：`0.3682%`
- 年度：
  - 2015：target bar `2,608`，inited `5`
  - 2016：target bar `2,766`，inited `8`
  - 2017：target bar `2,708`，inited `11`
  - 2018：target bar `3,054`，inited `17`
- 只有两个品种出现过 AM 初始化：
  - `au.SHFE`：target bar `975`，inited `33`
  - `CF.CZCE`：target bar `975`，inited `8`

## AM窗口敏感性

| AM size | target_bar_days | inited_days | inited_ratio |
| ---: | ---: | ---: | ---: |
| 40 | 11,136 | 5,161 | 46.3452% |
| 60 | 11,136 | 2,873 | 25.7992% |
| 80 | 11,136 | 906 | 8.1358% |
| 90 | 11,136 | 394 | 3.5381% |
| 120 | 11,136 | 41 | 0.3682% |

## 与前序阶段交叉验证

- Stage201：
  - 正式合约级AM在2015-2018几乎无信号。
  - 连续主力AM恢复出大量信号，2015-2018分别有 `56 / 123 / 139 / 148` 条原始信号。
- Stage202：
  - 复权连续主力指标继续证明“信号断裂”来自合约级AM换月断裂。
  - 差值复权2015-2018原始信号分别为 `55 / 121 / 140 / 146`。
- Stage203：
  - 连续差值复权指标在2020-2026正式样本显著劣化，最大回撤 `-50.1180%`，不适合作为第78正式升级。
- Stage206：
  - 2015-2017无交易直接原因不是 `fu` 数据缺口，而是合约级AM初始化极少。
  - 2015、2018各有一个短信号候选，但被第78短侧规则拒绝。

## 修正 Stage210 表述

- Stage210 的结论“AI池/卫星过滤不是主因”仍成立。
- 但 Stage210 如果被理解为“策略没有符合的开仓信号”，是不完整的。
- 更准确表述：
  - 第78在2015-2018大多数日期没有进入信号计算，因为当日主力真实合约AM未初始化。
  - 在极少数AM初始化并生成候选的日期，出现过两个短侧候选，但被 `short_signal_rejected` 拦截。
  - 所以根因排序是：
    1. 合约级AM换月断裂导致信号函数调用极少。
    2. 少数已生成候选被短侧 `short_case1a` 门禁拒绝。
    3. AI池/卫星过滤不是主要拦截点。

## 结论

- 用户记忆正确：早期无成交的主要工程原因确实和 `ArrayManager` 有关。
- 2015-2018不是“市场没有趋势信号”，而是第78正式口径使用真实合约级AM，换月后每个真实合约独立冷启动，120日窗口导致绝大多数主力日未初始化。
- 连续主力指标能恢复信号，但此前已证明不能直接合入第78正式版，因为2020-2026正式样本回撤和收益质量明显劣化。

## 过拟合反思

- 运行前判断：否。本轮只做链路审计和AM就绪统计。
- 运行后判断：否，但要警惕“为了让2015-2018有交易而改指标口径”的过拟合。
- 原因：
  - 调小AM窗口或改连续主力指标都能恢复早期信号，但会改变策略定义。
  - Stage203已显示连续复权口径在正式样本不过关。

## 继续价值反思

- 运行前判断：有价值。它修正了对2015-2018无成交的误读。
- 运行后判断：有价值，但方向应是审计和标注，而不是直接改第78。
- 下一步：
  - 可以把长样本报告中2015-2018标注为“合约级AM冷启动/低信号可用期”。
  - 如果继续研究，只能把连续主力指标作为诊断或独立新策略线，不能直接替换第78正式口径。

## 合入建议

- 是否更新本线 `LINE.md`：建议合入者下次整理时补充“2015-2018合约级AM冷启动”解释。
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：否
