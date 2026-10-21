# Stage133：B_OFF原账户触及原预算，真实失败封存

- line_id：`futures_trend_triple_screen`；2026-10-18 09:43 CST；非重要突破，目标仍active。
- 同分支`codex/ai-training-data-expansion`、HEAD `4f42805c2c71f8492a44a6876a82672f410f44df`，不建worktree、不推送/部署，不动其他研究线。

## 实际终态和结果

root独占的金融session47648在chunk4e198d真实exit1，最后一次poll43.012675917秒；原run `81ffc8f704ce4c5eb701e97e0397b12a`，07:43:14.055881启动，未被观察器重启或主动终止。真实异常为2025-04-11 bar的`TimeoutError(qualified_data_wait_budget_exceeded)`，外层`RuntimeError(backtest_bar_failed)`；不是猜测SIGALRM先触发，也不是收益门失败。策略等待CF505该日full-session，没有数据response；原run7200秒上限到达。

原wait1800/run7200/provider启动剩余840秒、每包一次、570/600秒和批4连接全部保留。108 final batch129实际exit0/0连接、paused_budget_or_four_connections，末prepare-only packet没有运行/response，130未启动。全run116网络连接/116published、159实际response来自108总账；response不等于gate commit或完整数据审查。后续是否可复用必须按134独立审查的实际gate事实，不能凭文件存在。

实际run_failure为`failed_partial_no_engine_seal`；failure_capture 1,686,556 bytes，SHA `c0047f6bf2d7dc2bcfd0175da58b4a836e9986fc96f5b570e6d4230725cfc260`。没有完整raw checkpoint、seal、summary或export_success，不能export-only恢复或拼接部分资金曲线。期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率全部N/A，不输出途中PnL。

事实证据`outputs/stage133_B_OFF_actual_failure/actual_tool_terminal.json`，SHA `8d287ff4d22277c63ed89034fcf553560de10cf9ffb10c8e7b4a6834e9859172`；绑定actual tool/session/chunk、context/preflight/failure/partialcapture的实际SHA/bytes与缺失完整产物，创建命令6f4d38 exit0。累计金融11attempt/4完整独立accepted、训练0。A_OFF已接受结果不变；本阶段不重跑任何账户。

## 同期组件与数据审查

122仅审closed026—129：104terminal/104runtime manifests/591sidecars，125新交付=90network+35local，28301唯一键；有限审查P0/P1/P2=0/0/0，8分层样本2971行。115+119+122只覆盖151份，不称全部159response均复核；另外8份尚未由这些范围覆盖。

EMA限价新组件按124/126固定设计完成六方法GREEN及一次compile，132独立整体审查P0/P1/P2=0/0/0、六源SHA无漂移；收据bb4d79bd77a40475e98e0631737bc8b937d64ff609fc6d4771c48e06fd0e640b。仅组件接受，没有新金融臂/readiness/alpha或生产资格。代码及微型成本均不是回测表现。

## 改动、判断和后续

本阶段新增/修改/删除策略参数0，新增完整回测结果0，修改/删除旧结果0；新增的是实际失败记录。没有为完成曲线放宽预算、取daily-open fallback或删除困难订单。调研继承121/123原著/作者官网/GitHub结论：EMA穿透是可明示独立适配，尚无收益证据；本次失败判断来自真实终态和固定源码，不新增网上搜索。

开始/结束新增过拟合判断：否，本次只封存真实失败，不读取途中PnL选参；历史选择偏差仍在。继续价值：是，限于一次独立失败诊断和精确已消费数据复用，避免盲目重跑/重复下载；不把基础设施进展当目标完成。

134独立审查已派发：核实际terminal/失败schema/原预算，审计-only提取真实resolver/gate committed与input bindings，判定可复用范围及旧061是否直接兼容。得到证据前不启动新金融。所有旧失败、原预算和原配置继续保留；production_qualified=false。
