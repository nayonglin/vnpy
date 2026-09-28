# Stage001换月标签可成交性资格失败闭线

- 改动时间：2026-09-05 01:19-01:34 CST
- line_id：`futures_trend_xgboost_pit_roll_label_tradeability`
- 是否重要突破版本：否；这是标签前数据与执行资格审计，不是模型、策略或收益版本。
- 唯一授权nonce：`d979717c-b4d3-419a-8998-331415977f85`
- 决策：`stage001_roll_label_tradeability_fail_close_no_label_values`
- 当前线状态：唯一全量执行已消费并失败闭线，不生成标签值、不训练XGBoost、不进入真实引擎。

## 调研与判断结论

- QuantConnect容量文档和LEAN `VolumeShareSlippageModel`都以订单相对市场成交量衡量容量/冲击；CME也把成交量与持仓量作为期货流动性核心维度。
- 仓库既有1%订单/成交量与1%持仓/OI容量原则，对最小1手订单等价于执行日`volume >= 100`且`open_interest >= 100`。
- 判断：上游“到期安全且bar存在”不足以生成可交易标签。失败主要集中在长期低流动性品种，但跨2022-2026每年都出现，不是单一年份或单一到期异常。
- 参考：<https://www.quantconnect.com/docs/v2/lean-engine/statistics/capacity>、<https://github.com/QuantConnect/Lean/blob/master/Common/Orders/Slippage/VolumeShareSlippageModel.cs>、<https://www.cmegroup.com/education/files/a-traders-guide-to-futures.pdf>。

## 本次版本改动

- 新增参数：价格观测端点要求`volume > 0`且`open_interest > 0`；最小1手执行要求`volume >= 100`且`open_interest >= 100`。
- 修改参数：无。
- 删除参数：无。
- 新增实现：endpoint审计、entry/roll_close/roll_open/exit事件构造、一手容量审计、失败产物发布和离线验证。
- 修改实现：无上游实现修改；复用冻结到期安全路径与原始bar身份/成交量/OI。
- 删除实现：无。
- 数据读取边界：只打开`datetime/symbol/exchange/interval/volume/open_interest`；`close`、收益、标签、holdout均未打开。

## 唯一执行

- 预运行回归：跨线`89 passed`，新线`7 passed`，`py_compile`通过。
- `--run`：仅执行一次，退出码`2`是预注册失败闭线语义；未重跑。
- `--verify-only`：产物`9/9`、输入`6/6`、错误`0`。
- manifest SHA256：`1579376b8fa7d7686e421bb331c36dea337c23c96d26fd4e6d7821d6e1b73ce3`。
- summary SHA256：`42131fa9ca148e0189838a836d7acfcb707cc48558c8b7042b9f28316daf8267`。
- authorization SHA256：`aa92c605fe9a59546ce03378026e98338b61c115a6b95d0ecb7aff23095d3d38`。

## 新增资格结果

- 冻结路径：`56,272`行、`1,046`个qid；leg：`1,125,440`行；换月事件：`29,360`个。
- 执行事件：`171,264`行，其中entry/exit各`56,272`，roll_close/roll_open各`29,360`。
- 最终可交易路径：`54,423/56,272=96.714174%`；失败`1,849=3.285826%`。
- 价格观测失败：`777`路径、`3,066`个leg；容量失败：`1,830`路径、`4,063`个事件。
- 失败交集：仅价格失败`19`路径、仅容量失败`1,072`路径、两者均失败`758`路径。
- 容量事件中`692`个成交量为0，另有`3,371`个成交量和OI均为正但至少一项低于100；这不是只靠过滤零成交即可解决。
- 失败角色：exit `1,259`、entry `1,216`、roll_close `998`、roll_open `590`，覆盖完整执行链。
- 失败产品仅`10/63`个，但`wr/RS/fb/bb`贡献`1,633/1,849=88.3180%`失败路径：
  - `wr.SHFE`：`527/607=86.8204%`失败。
  - `RS.CZCE`：`466/470=99.1489%`失败。
  - `fb.DCE`：`380/1,002=37.9242%`失败。
  - `bb.DCE`：`260/271=95.9410%`失败。
- 年度失败率：2022 `3.4967%`、2023 `2.2540%`、2024 `3.1473%`、2025 `3.9368%`、2026 `3.8263%`。
- 6个到期fallback全部容量失败：`wr2401`端点价格质量通过但最少一个执行事件不满足100/100；5个`RS607`路径同时价格与容量失败，映射日成交0/OI6。

## 门禁结果

- 通过：上游manifest、输入身份、上游决策、冻结计数、身份唯一性、执行事件结构、fallback覆盖、零副作用。
- 失败：`price_observation_quality_gate`、`minimum_one_lot_capacity_gate`。
- `close`读取、未来收益计算、标签读取、fit、predict、策略回测、holdout、CTP、订单API、生产写入：全部`0`。

## 回测结果

- 新增回测结果：无。
- 修改回测结果：无。
- 删除回测结果：无。
- 期末权益：不适用，未回测。
- 总收益：不适用，未回测。
- 最大回撤：不适用，未回测。
- Sharpe：不适用，未回测。
- 总滑点：不适用，未回测。
- 总交易次数：不适用，未回测。
- 胜率：不适用，未回测。
- 独立reviewer：不触发；本阶段没有产生回测数据。

## 决策与TODO

- 本线禁止重跑、降低100/100门、删失败行、按品种/年份修补、缩短20日窗口或读取close救援。
- 不允许把`54,423`条事后通过路径直接当训练样本；这样会使用未来20日执行质量筛选标签，形成前视偏差。
- 若继续总目标，另立“PIT可交易候选宇宙”资格线：只允许使用query date当时可见的历史成交量/OI与生命周期信息，先验证能否事前排除不可交易路径，同时保持每月候选广度。

## 过拟合反思

- 运行后判断：否。
- 原因：全部阈值、样本、失败条件在打开全量分布前冻结；失败后未改门、未删品种、未重跑，也未读取任何收益结果。

## 继续价值反思

- 当前线：无继续价值，必须闭线。
- XGBoost总目标：仍有继续价值，但下一步只能研究事前可交易候选宇宙；当前没有模型效果、收益提升或回撤下降证据。
