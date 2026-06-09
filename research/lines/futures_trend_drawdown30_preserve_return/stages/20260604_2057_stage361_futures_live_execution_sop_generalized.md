# Stage361：期货实盘执行 SOP 泛化命名

- 时间：2026-06-04 20:57 CST
- 研究线：`futures_trend_drawdown30_preserve_return`
- 决策：`futures_live_execution_sop_generalized_stage_neutral`
- 是否重要突破版本：否。本阶段是实盘执行 SOP 命名和引用迁移，不是策略 alpha 或参数优化。

## 本次改动

- 将旧的版本绑定执行 skill 迁移为通用目录 `skills/futures-live-execution-sop/`。
- 将 skill frontmatter 名称改为 `futures-live-execution-sop`，描述改为“期货官方实盘执行 profile + CTP/SimNow/券商测试/影子盘/AI池/闸门/对账纪律”。
- 将 `agents/openai.yaml` 展示文案从 Stage78-1/50万改为通用“期货实盘执行SOP”。
- 将 `AGENTS.md` 的触发规则改为读取 `skills/futures-live-execution-sop/SKILL.md`。
- 将仓库内旧 skill 路径引用机械替换到新路径。
- 当前 official live profile 仍由 `examples/portfolio_backtesting/qmt_roll_official_live_config.py` 决定，目前为 `official_live_stage653_20w_force95_to80`，资金口径 `200000`。

## 回测结果

- 本阶段未新增回测。
- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- order API 调用：`0`

## 验证

- `rg` 已确认旧 skill 名称和旧路径无残留。
- 系统 `quick_validate.py` 因本机 Python 环境缺少 `yaml` 包无法执行。
- 已使用 Ruby/YAML 做等价静态校验：`SKILL.md` frontmatter 可解析、`name` 与目录名一致、名称字符合法、`agents/openai.yaml` 可解析。

## 判断

- 过拟合反思：否。本阶段没有调策略参数、没有跑收益筛选、没有根据回测表现修改交易逻辑，只是把执行 SOP 从历史版本名中解耦。
- 继续价值反思：有价值。实盘/虚拟盘 SOP 名称若继续挂 Stage78，会提高未来误用历史 50万路径的概率；通用命名后，后续版本切换应通过 official live config 完成，而不是再新建带具体 Stage 编号的执行 skill。

## TODO

- 后续所有实盘、影子盘、SimNow、券商测试、AI池月更、委托草案、提交前闸门和每日对账请求，先读取 `skills/futures-live-execution-sop/SKILL.md`。
- 若未来官方实盘版本从 Stage653 切到其他版本，只更新 `qmt_roll_official_live_config.py` 和当前研究线记录，不再重命名 skill。
