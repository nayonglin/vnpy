# 正式版衍生：周线指标，关闭0.5R止损

本分支基于正式材料m0008/Stage037、master `e41a0a01d53b7256001e45e686acad53667ef7bf`。仅离线研究。`LINE.md`固定实验合同，`stages/`保存中文结果及独立审查；本地`outputs/`包含输入哈希、失败尝试、补片证据和最终原始表，不由Git保存私有行情。

- A：正式参数、15万元，同期同源数据对照。
- C：将所有AM/history技术指标（MA、MACD、RSI、ATR、Donchian、量仓及形态）改为完整真实合约周线，周期数值不改；关闭0.5R止损及依赖重试。
- 日线撮合、每日盯市、当日极值价格风控、C2盘中风控、月度AI和5交易日换月保留。此版本是周线指标策略，不是将撮合与风控全部改为周频。
- 41根观察门槛成为41个已接受周；缺真实会话的周不计入，未完成周不计入。同一周的交叉信号只在新封周日发出；CZCE同名合约跨十年复用不拼接。
- 历史AI含2019-12-31静态边界至2022年初，不能称全段PIT/OOS；手续费沿用正式回测0，滑点照正式设置。

## 本机复验

本地运行环境入口为`.py311/bin/python`，引用已安装的完整研究环境；vendor为交接包中的`vnpy_portfoliostrategy`。新克隆不会自动提供这些依赖、私有SQLite/分钟数据或凭据。

```sh
PYTHONPATH=. .py311/bin/python research/lines/futures_weekly_formal_no_half_r/tools/test_weekly_adapter.py
PYTHONPATH=.:/Users/mac/Documents/Codex/fian-handoff-20261014/vnpy_handoff_20261014/vendor:examples/portfolio_backtesting .py311/bin/python -m unittest discover -s tests -p 'test_stage249*.py' -q
PYTHONPATH=. .py311/bin/python research/lines/futures_weekly_formal_no_half_r/tools/run_weekly_with_minutes.py --arm C --attempt verification001
```

`run_weekly.py`保留首轮字节；`run_weekly_with_minutes.py`增加已验证分钟补片覆盖与失败暖机审计，不改策略参数。每个输出目录只允许执行一次，禁止覆盖已完成尝试。补片只填缺失时间键，重叠值不一致即拒绝；原始缓存不改。

`replay_audit_helpers.py`复用已验收Stage274导出/异常捕获工具；`daily_coverage.py`仅检查真实持仓日日线，不改变撮合。Stage249分钟校验/下载工具仍从旧研究线导入，交付依赖清单保存其SHA；真实行情读取使用本地忽略凭据，禁止回显或提交。

## 调研与判断

[Backtesting.py官方多周期示例](https://kernc.github.io/backtesting.py/doc/examples/Multiple%20Time%20Frames.html)和[GitHub重采样实现](https://github.com/kernc/backtesting.py/blob/master/backtesting/lib.py)强调高周期指标的因果对齐。这里采用完成周后才发布的原则；不直接复制其交易引擎。周指标更慢不等于更稳，且真实合约41周历史可能不足，必须结合有效覆盖和全窗结果判断，不能缩短窗口救结果。

## Stage003 后续指定配置

用户要求关闭半R、C2和AI选品；实际关闭月度资格门，原19基础池不扩市场。三开关False、AI disabled且0快照、所有盘中事件0；真实首分钟成交校验仍保留。新入口：

```sh
PYTHONPATH=. .py311/bin/python research/lines/futures_weekly_formal_no_half_r/tools/run_stage003_with_anchors.py --arm D --attempt verification001
```

需要本机outputs/stage003_anchor_catalog及stage003_minute_patches证据；原C/A的runner、输入及成果均不覆盖。最新D与C比较图、年度表、审查和报告已保存artifacts/stage003_*及stages/Stage004。
