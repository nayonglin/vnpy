# Stage230 外生数据实盘可执行性审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-06-01 21:08 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：数据工程可执行性审计；不新增交易规则，不做收益回测
- 是否重要突破：否；但明确基本面/舆情路线的当前可执行边界
- 是否触发A/B：否。本阶段不产生策略版本。

## 外部调研与判断

- 参考资料：
  - Tushare `fut_holding` 文档显示会员成交持仓排名可按交易日、品种、交易所查询：https://tushare.pro/document/2?doc_id=139
  - Tushare 期货数据说明显示合约级行情和品种级持仓/仓单字段口径不同，需要先统一映射：https://tushare.pro/document/2?doc_id=134
  - AKShare 期货数据文档列出基差、注册仓单、交易所仓单等接口：https://akshare-hh.readthedocs.io/en/stable/data/futures/futures.html
  - AKShare GitHub 显示当前仍是活跃 Python 财经数据接口库：https://github.com/akfamily/akshare
- 我的判断：
  - 基本面数据“有接口”不等于“可直接接入实盘策略”。必须满足：可稳定日更、明确发布时间、品种/合约映射一致、历史覆盖可回放、缺失处理可解释。
  - 舆情路线当前不具备回测资格。仓库没有带真实接收时间戳、历史可回放、商品品种映射的舆情账本；如果直接用回溯新闻/摘要，会产生信息泄漏。
  - 结合 Stage229，外生数据当前最合理用途不是直接 alpha，而是：解释 2022 坏窗口、做一次低自由度强逆风防守验证、或构建 paper 监控；不能再救旧因子小参数。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage530_external_data_execution_readiness.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：无新增收益回测；读取既有 Stage316/358/374 覆盖审计。
- 账户规模：无
- 成本口径：无
- 样本过滤：外生数据通道级别，不筛交易样本。
- 策略/归因口径：
  - 检查本地 `akshare` / `tushare` 包和凭证。
  - 复核 Stage316、Stage358、Stage374 供需覆盖结果。
  - 输出每类数据是否允许进入实盘候选。

## 结果

- 期末权益：无新增回测
- 总收益：无新增回测
- 最大回撤：无新增回测
- Sharpe：无新增回测
- 总滑点：无新增回测
- 总交易次数：无新增回测
- 胜率：无新增回测
- 其他关键指标：
  - 决策：`basis_explain_ready_member_and_sentiment_not_live_ready`
  - `akshare`：已安装，版本 `1.18.55`
  - AKShare 函数存在：`futures_spot_price`、`futures_shfe_warehouse_receipt`、`futures_warehouse_receipt_czce`、`futures_warehouse_receipt_dce`、`futures_gfex_warehouse_receipt`
  - `tushare`：已安装，版本 `1.4.29`
  - `TUSHARE_TOKEN`：环境变量存在，但 `fut_basic` 冒烟失败，返回“token不对”
  - Stage316：2023-2026 外生信号 `28,840` 行，候选命中率 `57.9224%`，实际开仓命中率 `44.7619%`，但质量分样本外不单调
  - Stage358：2020-2022 外生信号 `22,684` 行，实际开仓命中率 `53.6508%`，但历史仓单覆盖不完整
  - Stage374：2015-2019 基差 `20/20` 可用、CZCE仓单 `17/20` 可用、SHFE仓单 `0/20`、DCE仓单 `0/20` 且报错、GFEX仓单 `0/20`

## 通道判定

| 路线 | 当前状态 | 允许用途 | 阻塞 |
| --- | --- | --- | --- |
| 基差 | AKShare 可用，历史覆盖较好 | 坏窗口解释、一次固定强逆风防守验证 | 旧因子样本外不单调，不能继续调权重/窗口 |
| 仓单/库存 | 函数存在，但 SHFE/DCE/GFEX 历史覆盖有缺口 | 数据工程修复、解释层 | 不能作为核心信号，黑色链三组件不完整 |
| 会员持仓 | 包存在但 Tushare token 冒烟失败 | 暂不进入 live pipeline | 先修复 token 或换交易所/AKShare源；Stage016 已反证直接因子 |
| COT | 官方可得 | 解释层 | 周频外盘数据不能直接映射中国商品日频候选 |
| 舆情 | 无点时化账本 | 暂不进回测 | 没有真实接收时间、发布延迟、历史可回放和品种映射 |

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage530_external_data_execution_readiness_report_stage530_external_data_execution_readiness_v1.md`
- readiness：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage530_external_data_execution_readiness_readiness_stage530_external_data_execution_readiness_v1.csv`
- coverage：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage530_external_data_execution_readiness_prior_coverage_stage530_external_data_execution_readiness_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage530_external_data_execution_readiness_decision_stage530_external_data_execution_readiness_v1.json`

## 结论

- 本阶段结论：
  - 基差可以继续作为解释层和一次固定强逆风防守验证的候选输入。
  - 仓单/库存当前不允许进入核心信号，除非先修复 SHFE/DCE 历史覆盖。
  - 会员持仓当前不能作为实盘数据通道，因为 Tushare token 冒烟失败；即便修复，也只能复验，不允许继续救 Stage016 小参数。
  - 舆情当前不具备回测资格，必须先建实时接收账本和品种映射。
- 是否进入下一步：是，但不是直接外生 alpha。
- 下一步：
  1. Stage231 优先做 `r080_pc25_maxpos4` 坏窗口逐笔/退出形态复盘。
  2. 外生数据只允许并行做“基差强逆风是否解释 2022 坏窗口”的只读验证。
  3. 舆情路线先暂停回测，除非先建实时采集/paper OOS 数据。

## 过拟合反思

- 运行前判断：否。本阶段是可执行性审计，不看收益调参数。
- 运行后判断：否。
- 原因：
  - 输出保留了 token 失败和历史覆盖缺口，没有为了接入外生因子忽略阻塞。
  - 对旧因子保留反证结果，不继续调窗口、权重或阈值救回测。

## 继续价值反思

- 运行前判断：有价值。用户明确要求研究基本面/舆情是否可用，必须先判断实盘可执行性。
- 运行后判断：有价值，但路线优先级降低。
- 原因：
  - 基差/仓单/会员持仓更适合作为解释和低自由度防守验证；舆情在没有点时化账本前不能回测。
  - 主线优化仍应优先处理 Stage229 暴露出的 2022 长回撤和成本压力。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：是
- 是否追加根目录 `memory.md/back_log.md`：是，作为基本面/舆情路线边界。
