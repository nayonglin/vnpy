# Stage130 TqSdk 2022 过期期权链数据探针预声明与实施计划

> **执行要求：** 按 TDD 顺序完成；网络探针只读，不连接 CTP、不创建账户委托、不调用订单 API。每个产物完成后由独立 agent 复核。

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：`day`
- 预声明时间：`2026-07-11 11:52 CST`
- 阶段性质：全新外生 PIT 数据源 readiness；不是收益回测，不产生策略候选
- 是否重要突破：待数据权限和历史链结果
- 是否触发 A/B：否；只有完整 PIT 数据验收后，下一阶段才允许预声明唯一保护性期权 A/B

## 目标与架构

- 目标：确认当前已能下载 jd 分钟数据的 TqSdk 凭证，是否也能查询和读取 `2022` 已到期商品期权历史链。
- 唯一探针标的：`DCE.m2209`；窗口 `2022-03-09 -> 2022-03-11`；只尝试一次 CALL/PUT 同到期链。
- 数据流：`vnpy.trader.setting.SETTINGS` 脱敏凭证状态 -> TqBacktest 时点的 TqSdk `query_options(expired=False)` -> 选择同到期 CALL/PUT -> `get_kline_serial` 读取期权与标的日线 -> raw/过滤/PIT/字段/hash 审计 -> readiness 决策。
- 语义说明：这些合约在今天已经到期，但在固定回测时点 `2022-03-09` 仍是 active；TqSdk 回测查询会携带该历史 timestamp，因此必须使用 `expired=False`。首轮 `expired=True` 是 API 时点语义错误，不是参数调整。
- 隔离：代码、测试和输出只写本研究线；不写共享行情目录，不修改 SQLite、主力映射、Stage847、Stage013、实盘 env、CTP、邮件或 launchd。

## 外部调研与判断

- [TqSdk 官方仓库](https://github.com/shinnytech/tqsdk-python) 明确支持期货、期权历史数据和回测。
- [TqApi 期权查询接口](https://tqsdk-python.readthedocs.io/en/stable/reference/tqsdk.api.html) 提供 `query_options`、`query_atm_options` 等期权合约查询。
- [DataDownloader 官方文档](https://tqsdk-python.readthedocs.io/en/latest/reference/tqsdk.tools.download.html) 明确历史期权下载属于专业版能力；本阶段必须用实际权限探针裁决，不能由“已有用户名密码”推断权限。
- [期权基础示例](https://tqsdk-python.readthedocs.io/en/stable/demo/option_base.html) 展示期权、标的联合 K 线以及 IV/Greeks 计算接口，但本阶段不计算信号或收益。
- 我的判断：保护性期权是现有账户阈值、AI、OI、趋势广度、协方差和现金桶之外的正交结构，理论上可保留期货趋势右尾并限制单笔不利跳变；但 2022 主要是长时间震荡水下，是否有效完全未知。数据不完整时禁止做 premium proxy 或用 Black-Scholes 伪造历史成交价。

## 固定成功门

- TqSdk 模块、`TqApi/TqAuth/TqSim/TqBacktest` 和脱敏凭证状态全部 ready。
- `DCE.m2209` 的 expired option query 返回至少一个 CALL 和一个 PUT，且 option symbol、underlying、strike、expiry、option class 全部非空。
- 同到期 CALL/PUT 与 underlying 在固定窗口至少各有一条可用日线；所有 bar date 位于固定窗口内。
- option/underlying OHLC 非空、OHLC 关系合法、负成交量为 0、重复 symbol+datetime 为 0。
- 查询时间、探针窗口、原始文件 SHA256、代码和测试 SHA256 全部落 lineage/manifest；任何凭证值不得落盘。
- 任一门失败即 `stage130_tqsdk_expired_option_chain_not_ready_close`；不更换品种、窗口、交易所、端点或凭证来源继续试。
- 全部门通过才是 `stage130_tqsdk_expired_option_chain_ready_for_acquisition_manifest`；不代表保护性期权有效，也不允许直接做 A/B。

## 文件边界

- 新增工具：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage130_tqsdk_expired_option_chain_probe.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage130_tqsdk_expired_option_chain_probe.py`
- 新增输出：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage130_tqsdk_expired_option_chain_probe/`
- 更新记录：本文件补写结果；完成后更新本线 `LINE.md`，重要数据突破才更新 registry/back_log。

## TDD 实施计划

- [x] 新增失败测试：凭证审计只返回 bool/count，不返回用户名或密码。
- [x] 新增失败测试：期权 metadata 只接受同一 underlying、同一 expiry、CALL/PUT 各一条；缺任一腿 fail-close。
- [x] 新增失败测试：bar 审计拒绝窗口外日期、重复键、OHLC 空值/关系错误和负成交量。
- [x] 新增失败测试：readiness 只有在模块、凭证、CALL/PUT metadata、三腿日线和 PIT/hash 全通过时才为 ready。
- [x] 运行 focused tests，确认因 Stage130 模块缺失而 RED。
- [x] 最小实现纯函数、脱敏审计、单次网络探针、report/decision/lineage/manifest；不得加入 IV、Greeks、收益或策略参数。
- [x] 运行 focused tests 和相关 Stage040/051/052 回归测试。
- [ ] 以 `STAGE130_ENABLE_NETWORK_PROBE=1` 运行唯一网络探针；设置总超时，成功或失败都完整落盘。
- [ ] 机械复核原始文件、hash、日期、字段、重复、凭证泄露和决策。
- [ ] 拉独立 agent 只读复核权限、PIT、数据质量、代码、测试、manifest、结论和继续价值；有 P0/P1 必须修复后重跑。

## 运行前反思

- 过拟合：否。本阶段没有收益标签、策略规则、阈值搜索或品种选择；`DCE.m2209/2022-03-09` 在运行前固定，仅用于回答历史期权链权限是否存在。
- 继续价值：有。现有内部特征路线已大面积证伪，期权保护层是少数真正正交、且机制上可能不压低趋势右尾的方向；但数据权限失败时继续价值立即归零。

## 停止边界

- 不把成功下载解释为策略有效。
- 不根据返回结果切换到另一期权品种或日期。
- 不使用理论期权价格、当前 quote、未来 expiry 信息或不带 hash 的旧导出替代历史链。
- 不在本阶段修改正式策略、实盘入口或风险参数。

## 首轮无效探针与独立审查

- 首轮时间：`2026-07-11 12:06 CST`；调用 `query_options(DCE.m2209, expired=True)` 返回 `0`，机械输出为 not-ready。
- 独立 review：`P0=0/P1=1/P2=3`，不批准关闭结论。TqSdk `_query_options_by_underlying` 在回测模式会把查询 timestamp 固定为 `2022-03-09`，随后按该时点 `expired` 过滤；m2209 期权当时 active，`expired=True` 必然排除。
- 处置：首轮输出保留隔离，不作为权限或数据能力证据；按同一标的、窗口、端点修正为 `expired=False` 后仅重跑一次。
- 同步修复 P2：移除 `query_symbol_info` 后多余 wait；保存过滤前 raw bars 和过滤审计；lineage 增加生成时间、SDK 版本、固定查询参数；hash 门改为实际文件 SHA256 验证。
- 过拟合判断：否；这是 API 历史状态谓词修复，没有使用收益结果，也没有更换研究样本。
- 继续价值判断：有；只有修复后探针才能回答真实权限和历史链可得性。
