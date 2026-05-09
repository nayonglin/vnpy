# Stage208 QMT回测TRADER_DIR防错门禁

- line_id：futures_trend
- 当前模式：day
- 记录时间：2026-05-10 04:56
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：工程防错门禁
- 是否重要突破：是，修复会影响后续所有QMT回测可信口径
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - Python 官方 `site` 文档：解释器初始化会尝试导入 `sitecustomize`，可用于站点级启动定制。
  - CPython `site.py` 说明：`sitecustomize` 在用户脚本执行前导入，适合做轻量环境纠偏。
- 我的判断：
  - 不应修改 vn.py 通用 `utility.py` 的全局逻辑，否则会污染包行为。
  - 应在本仓库回测边界做门禁：启动早期纠偏 + 回测公共入口显式检查 + agent skill 命令修正。

## 本次变更

- 新增文件：
  - `sitecustomize.py`
  - `examples/portfolio_backtesting/sitecustomize.py`
  - `examples/portfolio_backtesting/qmt_backtest_runtime_guard.py`
- 修改文件：
  - `examples/portfolio_backtesting/qmt_universe.py`
  - `examples/portfolio_backtesting/run_qmt_roll_backtest.py`
  - `.trae/skills/qmt-roll-validation/SKILL.md`
  - `.trae/skills/qmt-roll-review/SKILL.md`
  - `.trae/skills/qmt-roll-risk-grid/SKILL.md`
- 删除文件：无

## 防错机制

- 第一层：仓库根目录 `sitecustomize.py`
  - 当命令设置 `PYTHONPATH=/Users/bytedance/Desktop/person/vnpy` 时，Python 启动早期自动加载。
  - 临时切换到仓库根目录预加载 `vnpy.trader.utility`，让 vn.py 绑定项目级 `.vntrader`。
  - 随后恢复原始工作目录，避免破坏 `python run_xxx.py` 这种相对脚本路径。
- 第二层：`qmt_backtest_runtime_guard.py`
  - 校验 `TEMP_DIR == /Users/bytedance/Desktop/person/vnpy/.vntrader`。
  - 校验项目级 `database.db` 存在。
  - 对 Stage196 已修复的2015哨兵合约做数据可见性检查：`rb1505.SHFE`、`jm1505.DCE`、`MA506.CZCE`。
- 第三层：公共入口接入
  - `qmt_universe.py` 导入时检查 `TRADER_DIR/TEMP_DIR`。
  - `run_qmt_roll_backtest.py` 构建引擎前检查 Stage196 哨兵数据。
- 第四层：agent skill修正
  - QMT Roll 验证、复盘、风险网格 skill 的默认 cwd 改为仓库根目录。
  - 标准命令改为 `examples/portfolio_backtesting/xxx.py` 路径。

## 验证

- 正常路径：
  - 从 `examples/portfolio_backtesting` 目录执行 Python，设置 `PYTHONPATH=/Users/bytedance/Desktop/person/vnpy`。
  - 结果：`TRADER_DIR=/Users/bytedance/Desktop/person/vnpy`，`TEMP_DIR=/Users/bytedance/Desktop/person/vnpy/.vntrader`。
  - `assert_stage196_database_sentinels()` 通过。
- 失败路径：
  - 设置 `QMT_BACKTEST_DISABLE_STARTUP_CWD_GUARD=1`，从 `examples/portfolio_backtesting` 目录导入 `qmt_universe`。
  - 结果：抛出 `QmtBacktestRuntimeError`，明确显示当前读到 `~/.vntrader`，并提示从仓库根目录运行或保持启动门禁开启。
- 静态检查：
  - `GetDiagnostics` 对新增/修改 Python 文件无报错。
  - `py_compile` 对新增/修改 Python 文件通过。

## 过拟合反思

- 运行前判断：否。本轮不是调参数，也不使用收益结果选择策略。
- 运行后判断：否。本轮是运行时口径门禁，目标是防止数据源漂移。
- 风险：
  - `sitecustomize` 会在设置本仓库 `PYTHONPATH` 的 Python 启动时生效，因此代码必须保持轻量。
  - 已采用“临时切目录预加载再恢复”的方式，降低对普通脚本 cwd 的副作用。

## 继续价值反思

- 运行前判断：有价值。否则后续所有回测都可能因 cwd 不同读到不同 `.vntrader`。
- 运行后判断：有价值。现在错误路径会显式失败，不再静默产出错误覆盖率和收益。
- 下一步：
  - 后续如新增 QMT 回测公共入口，应复用 `qmt_backtest_runtime_guard.py`。
  - 若要跑不依赖项目数据库的临时脚本，可显式设置 `QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR=1`，但正式回测不得使用。

## 合入建议

- 是否更新本线 `LINE.md`：建议后续合入时补充“正式回测必须绑定项目级 `.vntrader`”。
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：可选，属于跨阶段重要工程门禁。
