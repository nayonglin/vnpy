# Stage001 L1 历史 Tick Canary 完成并闭线

- line_id：`futures_trend_l1_topbook_entry_quality`
- 当前模式：`day`
- 记录时间：`2026-07-13 01:23 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：固定12事件真实历史 L1 tick 权限/覆盖 canary、独立审查、机械闭线
- 是否重要突破：否；排除了当前账号下的精确历史 tick 路线
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：Stoikov micro-price、Cont/Kukanov/Stoikov OFI、queue imbalance、`sstoikov/microprice`、`nkaz001/hftbacktest` 与 TqSdk 官方 `get_tick_data_series` 文档。
- 我的判断：真实 L1 best bid/ask price+size 对短时 adverse selection 有研究先验，但不能替代 MBP10/MBO、queue/cancel、深度冲击或多日趋势信息。本阶段先做权限和覆盖硬门是必要的；当前账号没有 TqSdk 专业版 `tq_dl` 权限，继续实现特征或收益回测没有数据基础。

## 本次变更

- 新增脚本：`tools/stage001_l1_tick_canary.py`。
- 新增测试：`tests/test_stage001_l1_tick_canary.py`。
- 修改脚本：无正式策略、AI、回测或实盘脚本修改。
- 删除脚本：无。
- 新增参数：固定 `12` 事件；日盘 `08:59-09:05`、夜盘前一 global trade date `20:59-21:05`；开盘后 `60s` 合法双边 L1；单请求墙钟上限 `120s`。
- 修改参数：无正式策略参数修改。
- 删除参数：无。

## 回测/归因参数

- 数据区间：固定事件覆盖 `2018-01-15 -> 2026-04-30`；每事件只请求固定6分钟窗口。
- 账户规模：不适用。
- 成本口径：不适用。
- 样本过滤：Stage131 `365` 事件按 `exchange × has_night_session` 分层，机械选择每层最早/最晚，共6层12事件；事件源 SHA `7abf7a0414238517349e383a6ef7282b5f8d16921686ddc1edb6f2e70e5cc77a`。
- 交易日源：Stage847 curve `8,148` 行、`2,037` 个唯一 global trade dates，SHA `199926a5dac7e21c0381dfd807675235e07cf650429fa0295e2e2705d94cc56d`。
- 策略/归因口径：只读 `TqApi.get_tick_data_series` 权限/数据完整性；不读取 PnL、markout、MAE、stop/retry、权益或回撤。

## 测试与执行

- `.py311` 未安装 `pytest`，改用标准库 `unittest`，不新增依赖。
- TDD 首轮因目标模块不存在按预期为红；实现后 `6/7`，发现全非法 float-ns 时全 `NaT` 列退化为无时区 dtype，会让失败审计异常。
- 修复为显式 `datetime64[ns, Asia/Shanghai]` 后专属测试 `7/7`，`py_compile` 通过。
- fake fetch 已证明 `12/12` 失败仍留在固定分母，decision 不会误标 feature/backtest/live ready。
- 真实 run_id：`20260713T011519+0800`；12条按冻结顺序独立进入认证历史查询路径。

## 结果

- decision：`CLOSE_LINE_L1_TICK_COVERAGE_INELIGIBLE`。
- 终态：`authentication_or_permission_failed=12/12`，`extracted=0/12`，覆盖率 `0%`。
- 12条原始错误完全一致：TqSdk 明确返回 `get_tick_data_series` 仅限专业版用户；本地 TqSdk `3.9.4` 源码先检查 `_auth._has_feature("tq_dl")`，失败发生在合约校验和 DataSeries 请求之前。
- 固定身份：`12/12` 匹配；终态事件唯一 `12/12`；没有失败样本剔除。
- attempt：`12` 个唯一 `attempt_0001`，临时目录残留 `0`。
- attempt/root manifest 文件集、bytes、SHA、detached checksum 问题 `0`；凭据字面量命中 `0`；`git diff --check` 通过。
- 期末权益：不适用，未运行回测。
- 总收益：不适用，未运行回测。
- 最大回撤：不适用，未运行回测。
- Sharpe：不适用，未运行回测。
- 总滑点：不适用，未运行回测。
- 总交易次数：`0`。
- 胜率：不适用，未运行回测。

## 独立审查

- reviewer：独立 agent `Banach`（`019f5754-5985-7b71-8dc1-870f79c45fa1`），只读复算代码、测试、计划、12份 attempt、账本、decision 与 TqSdk 本地源码。
- 结论：`P0=0 / P1=0 / P2=3 / P3=1`；权限直接原因置信度 `99%`，机械闭线置信度 `99%`，完整证据合同置信度 `90%`。
- P2-1：权限失败 attempt 没有空 `raw_tick.csv/normalized_tick.csv/schema.json`，不完全满足预声明“每 attempt 全文件落盘”；不影响权限失败即闭线，不改写不可覆盖 attempt、不重复请求。
- P2-2：`network_called=true` 只能解释为已进入带认证 `TqApi` 路径；`tq_dl` 本地权限检查先失败，不能表述为12个历史 tick 请求均已发送到数据服务端。不影响闭线。
- P2-3：异常分类关键词包含较宽的“用户/账户”，其他异常未来可能误分类；本次原始文本精确命中专业版权限提示，不影响本次终态。
- P3：脱敏单测未覆盖秘密互相包含或编码泄露；本次真实输出递归字面量扫描为0，不影响结果。

## 输出文件

- report：`outputs/stage001_l1_tick_canary/report.md`。
- plan：`outputs/stage001_l1_tick_canary/frozen_canary_plan.csv`。
- terminal ledger：`outputs/stage001_l1_tick_canary/terminal_ledger.csv`。
- decision：`outputs/stage001_l1_tick_canary/decision.json`。
- attempts：`outputs/stage001_l1_tick_canary/attempts/`。
- manifest：`outputs/stage001_l1_tick_canary/manifest.csv`、`manifest.sha256`。

## 结论

- 本阶段结论：当前 TqSdk 账号不具备精确时间段历史 tick 的专业版权限，固定 canary `0/12`，本线按预声明关闭；这不是品种、年份、窗口、纳秒或统计失败。
- 是否进入下一步：否；不进入全365事件采集、L1特征、markout、收益 proxy、真引擎或A/B。
- 下一步：权限不变时不继续本线。未来若获得合法 TqSdk 专业版权限，只允许保持原12事件、原窗口和原硬门，新增不可覆盖 attempt 重新验证。

## 过拟合反思

- 运行前判断：否；只验证预先冻结的数据权限和完整性，不读取收益。
- 运行后判断：否；失败后没有换事件、换接口、改窗口、放宽60秒或使用分钟/last-price proxy 救参。
- 原因：结果由统一权限硬门决定，不存在参数选择或坏窗口拟合。

## 继续价值反思

- 运行前判断：有但仅限一次固定 canary；真实 L1 是当前本地日线/OI/账户字段之外的新信息结构。
- 运行后判断：当前权限状态下无继续价值。
- 原因：专业版权限在所有事件合约校验和数据请求之前统一失败；继续写特征或收益逻辑只会制造不可执行研究。

## 合入建议

- 是否更新本线 `LINE.md`：是，标记 Stage001 完成并关闭。
- 是否更新 `research/registry.md`：是，标记权限硬失败和禁止下一阶段。
- 是否追加根目录 `memory.md/back_log.md`：只追加 `back_log.md` 跨线闭线摘要；不修改 `memory.md`。
