# Stage007 官方TqBacktest历史K线流的单窗口能力探针

- line_id：futures_trend_triple_screen；冻结时间2026-10-17 23:38 CST。
- 性质：正规行情接口数据能力/质量验证，不是C9金融回放。Stage001累计金融attempt仍4、完整A0仍1；不启动C0_attempt3。

## 调研与判断

已核对[官方快速入门](https://doc.shinnytech.com/tqsdk/latest/quickstart.html)、[版本说明](https://doc.shinnytech.com/tqsdk/latest/version.html)、[GitHub auth源码](https://github.com/shinnytech/tqsdk-python/blob/master/tqsdk/auth.py)和本机已装3.10.2源码。普通`TqBacktest + get_kline_serial`与要求`tq_dl`的区间下载API是不同的官方通路；此前后者权限拒绝不能证明前者也不可用。普通路径仍需服务端真实授权/配额，代码说明不能代替实际成功证据。不安装或升级SDK，不修改任何鉴权/授权检查。

用户先前已要求补齐研究数据并提供本机配置位置；本次只使用该已配置的数据账户。凭证来源`.vntrader/vt_setting.json`仅本地读取，不回显、不写入参数/日志/manifest，不提交。此处不用CTP、资金账户或生产配置。

## 固定范围与执行前门

1. 唯一订阅`SHFE.rb2010`、60秒K线；目标交易日2020-08-12，对应物理Aug11 21:00—Aug12 14:59、原helper预期345分钟。提供商回放窗口固定2020-08-11—2020-08-13，以便观察目标末分钟的后继K线证明完成。
2. 只创建官方普通`TqBacktest`与明确的本地`TqSim`用于数据流；无C9/策略账户引擎，无insert_order/cancel_order/TargetPosTask/资金账户。提供商数据回放1次，可能消耗当天1次回测配额；金融策略回放0。
3. 实现者先完成最小工具、少量完成K线/时区/拒绝不完整的测试及离线preflight，给root核对具体目标、超时和脱敏后，才由root批准唯一网络运行。
4. 总墙钟上限180秒，由父进程强制约束；正常权限、配额、认证或网络拒绝即停止，不自动重试，不扩窗，不更换账号，不绕过授权，不购买/开通付费服务。保留失败receipt及安全错误类别。

## 完成K线与验收

- 只保存已观察到后继K线的完成记录（例如serial中最后一行之前的数据）；不把回放结束时的最后形成中K线强行计为完成。逐键记录完成依据/观察到的后继时间，同键完成值冲突则拒绝。
- Tq纳秒时间戳按UTC绝对时间转Asia/Shanghai，明确记录为分钟起始时刻；交易日仍用原session helper，不能自然日归属夜盘。
- 目标完整345网格、唯一键、有限合法OHLC/量仓，与既有精确合约日线CSV及原DB可用字段核对聚合；来源缺失/聚合不一致/末分钟无完成证据均不接受。原数据保持不变。
- 输出独立本地raw CSV（沿原`vt_symbol,bar_datetime,open,high,low,close,volume,open_oi,close_oi`格式）、完成证据和小型质量/来源receipt。SDK输出先脱敏，仅保存安全日志；原始分钟和私有配置不进Git。

## 可得结论

成功只证明这个窗口在当前账号/当前时间合法可取且数据质量可验；不能外推全部品种/年份、全市场历史权限或已有完整候选数据。失败只按实测认证/权限/配额/网络类别报告，不把正常DataDownloader权限扩张为所有接口不可用。

即使成功，不直接并入base/overlay，不改变Stage001执行合同或自动重跑账户。下一步须根据Stage005初始信号与后续rollover/close需求制定一次性批量数据计划，沿用源冲突隔离和独立审查。

过拟合判断：否，目标窗口来自已确认数据缺口，不读收益/不调参数；原历史选择风险仍在。继续价值：是，先用一个有明确网格和日线对照的小窗口确认正规数据能力，能决定后续是否具备完成真实候选回放的条件。
