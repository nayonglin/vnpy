# 正式物料全市场无AI一手研究线

- line_id：`futures_trend_full_market_noai_one_lot`
- 创建时间：2026-10-18 15:34 CST
- 独立工作树：`/Users/mac/.codex/worktrees/full-market-noai-one-lot/fian`
- 分支：`codex/full-market-noai-one-lot`，起点 master `e41a0a01d53b7256001e45e686acad53667ef7bf`；已通过只读远端核对。
- 用户目标：基于正式策略建立独立研究版，关闭AI选品、放开全部空头case、100万初始资金、全市场期货、只交易1手、2015年至今回测并生成规范复盘HTML。
- 拟定执行：每品种最多1手，不加仓；保留其余正式信号、换月、退出与风控。全市场须覆盖六所历史品种，并披露不可用数据；截至最新完整数据日。
- 物料：本地正式身份校验通过，Stage037 ruleset，`ai_top10_plus_fu_official_live_v1`，m0008，source `2a7420a9f9550ab912b5c4a302a61acc5740b04c`，release `334d18f069de06df3aa7728203e942e3ecb94ce9`，manifest `94b6936ab4b338430981f4c2f7e0f4ff38f24534c32f1d16722c8d1367d89474`。
- 身份边界：原生产stable目录不存在，release-manifest、qualification、activation、activation receipt、data-readiness五项生产凭证缺失，不能声称已验证本机当前生产资格；不连接CTP、不调用订单API。
- 环境：原工作区`.py311/bin/python`可用，pandas/numpy/vnpy_portfoliostrategy/talib/plotly可发现，matplotlib缺失；新工作树没有`.py311`。现有数据仅可只读复用，不修改其他任务的数据或缓存。
- 状态：只完成工作树、分支、只读预检和研究合同；尚无策略修改、回测、HTML。已请求确认上述研究范围和生产身份边界，尚未收到回复。
- 独立review：每次实际回测完成后必须另拉独立agent审查结果、数据、逻辑、置信度与bug。
- 开始过拟合判断：否，本轮固定整体政策比较，不扫阈值/品种/年份救参；正式策略历史选择偏差仍须披露。
- 继续价值判断：是，可检验AI选品和空头case限制，但固定1手不等风险，不能把低回撤自动解释成alpha改进。
- 调研：查阅https://github.com/vnpy/vnpy_portfoliostrategy 与官方文档；判断复用现有引擎、真实合约与规范复盘渲染器，先核数据和时钟，不另造撮合。

## 参数与结果

新增/修改/删除策略参数：尚未实施；新增/修改/删除回测结果：0。期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率均N/A。不是重要突破版本。

结束过拟合判断：否，未查看新策略收益；继续价值：是，待范围确认后实施。TODO：绑定只读数据和环境、验证全市场覆盖、独立候选代码与测试、实际回测、独立review、冻结结果并生成规范HTML。
