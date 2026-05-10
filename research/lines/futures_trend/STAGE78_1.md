# Stage78-1 正式基准

## 定义

- 短别名：`78-1`
- 官方版本：`official_stage78_1_defensive_50w_no_sizing_cap`
- 策略家族：`official_stage78_defensive_v1`
- 定位：当前期货趋势策略正式基准与影子盘默认口径

## 固定口径

- 初始资金：`500,000`
- sizing资金封顶：`0.0`，即关闭100万sizing cap
- AI选品：开启
- FU卫星规则：开启
- 风控四档：`0.045 / 0.06 / 0.06 / 0.025`
- 新开空门禁：只允许 `short_case1a`
- 数据库：项目级 `.vntrader/database.db`
- 运行目录：仓库根目录 `/Users/bytedance/Desktop/person/vnpy`
- Python：`.py311/bin/python`
- `PYTHONPATH`：`/Users/bytedance/Desktop/person/vnpy:/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting`

## 新Agent默认理解

- 用户说“回测78-1”：运行当前文件定义的Stage78-1正式基准。
- 用户说“用78-1做影子盘”：运行Stage78-1影子盘日报入口。
- 用户只说“78版本”：先追问是否指`78-1`；若用户说“最新正式基准”，按`78-1`执行。
- 不要手写旧参数；必须读取 `qmt_roll_official_stage78_config.py`。

## 主回测入口

```bash
PYTHONPATH=/Users/bytedance/Desktop/person/vnpy:/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting \
/Users/bytedance/Desktop/person/vnpy/.py311/bin/python \
examples/portfolio_backtesting/run_qmt_roll_official_stage78_1.py
```

## 影子盘日报入口

```bash
PYTHONPATH=/Users/bytedance/Desktop/person/vnpy:/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting \
/Users/bytedance/Desktop/person/vnpy/.py311/bin/python \
examples/portfolio_backtesting/build_qmt_roll_stage78_1_shadow_daily_runner.py
```

## 关键代码

- 官方配置：`examples/portfolio_backtesting/qmt_roll_official_stage78_config.py`
- 主回测入口：`examples/portfolio_backtesting/run_qmt_roll_official_stage78_1.py`
- 影子盘日报入口：`examples/portfolio_backtesting/build_qmt_roll_stage78_1_shadow_daily_runner.py`
- 50万影子盘启动包入口：`examples/portfolio_backtesting/build_qmt_roll_stage168_50w_qmt_shadow_startup_pack.py`

## 对照版本

- 旧30万无封顶：`stage78_30w_no_sizing_cap_previous_formal`
- 旧30万有100万封顶：`stage78_30w_sizing_cap_1m_previous_formal`
- Stage75收益上限参考：`stage75_return_ceiling`

## 参考指标

- 全样本 `2020-01-01` 至 `2026-04-30`
  - 期末权益：`25,542,885`
  - 总收益：`5,008.5770%`
  - 最大回撤：`-40.0607%`
  - Sharpe：`1.1295`
  - 总滑点：`1,968,150`
  - 总交易次数：`880`
- 2026冷启动 `2026-01-01` 至 `2026-04-30`
  - 期末权益：`450,540`
  - 总收益：`-9.8920%`
  - 最大回撤：`-28.5861%`
  - Sharpe：`-0.6975`
  - 总滑点：`4,660`
  - 总交易次数：`27`

## 风险提示

- `78-1`取消100万sizing cap后，百分比最大回撤未明显恶化，但绝对回撤和滑点显著放大。
- 后续优化必须同时看收益、百分比回撤、绝对回撤、保证金峰值、滑点压力和Monte Carlo尾部。
- 不允许为了修补单一弱窗口继续做小数级资金参数优化。
