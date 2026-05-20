# Stage272 414xx 端口写入本地配置后的 CP Mac SDK 复测

- 记录时间：2026-05-19 15:34 CST
- 研究线：`futures_trend`
- 阶段性质：Stage78-1 CTP/broker-test 底层连接链路复测
- 是否重要突破版本：否；不改变策略、参数、资金口径或发单逻辑

## 背景

用户将 414xx 前置端口直接写入：

- `examples/portfolio_backtesting/ctp_broker_test.local.env`

本次按 Stage271 的 SimNow Mac CP SDK 隔离 wrapper 复测。

## 当前本地配置状态

只记录非敏感字段：

- `CTP_BROKERID=1010`
- `CTP_TD_ADDRESS=tcp://182.140.218.46:41407`
- `CTP_MD_ADDRESS=tcp://182.140.218.46:41415`
- `CTP_APPID` 已配置，长度 `19`
- `CTP_AUTH_CODE` 已配置，长度 `16`
- `CTP_AUTH_CODE` 不是 SimNow 默认 `0000000000000000`

## 复测一：按文件配置原样运行

命令：

```bash
bash examples/portfolio_backtesting/run_ctp_stage271_broker_cp_mac_sdk_readonly_probe.sh --connect --wait-seconds 25
```

结果：

- 行情服务器连接成功
- 行情服务器登录成功
- 交易侧没有进入成功登录/认证状态
- 更长等待复测退出码：
  - `exit_code=139`

解释：

- `139` 是段错误，属于底层 native 扩展/动态库层异常，不是普通 CTP 登录错误。
- 这说明当前 `vnpy_ctp 6.7.2.1` 的 Python 扩展硬加载 `v6.7.7_MacOS_CP` framework 并不完全安全，可能存在 ABI/头文件版本不匹配。

## 复测二：按页面文字顺序临时覆盖

临时覆盖：

- TD：`tcp://182.140.218.46:41415`
- MD：`tcp://182.140.218.46:41407`

命令：

```bash
CTP_TD_ADDRESS=tcp://182.140.218.46:41415 \
CTP_MD_ADDRESS=tcp://182.140.218.46:41407 \
bash examples/portfolio_backtesting/run_ctp_stage271_broker_cp_mac_sdk_readonly_probe.sh --connect --wait-seconds 30
```

结果：

- 行情服务器连接成功
- 行情服务器登录失败：
  - 代码：`64`
  - 信息：`CTP:客户端未认证`

解释：

- `MD=41407` 时进入认证失败；
- `MD=41415` 时行情可登录；
- 因此券商/页面给出的端口文字与实际账号/前置行为存在歧义，必须让券商明确 `41407/41415` 哪个是交易、哪个是行情。

## 匹配版 vnpy_ctp 尝试

为避免 `vnpy_ctp 6.7.2.1` 与 `v6.7.7_MacOS_CP` 库硬拼，本次在 `/private/tmp` 新建临时 venv，尝试安装：

- `vnpy_ctp==6.7.7.2`

结果：

- 安装失败；
- 日志显示编译阶段 `ninja: build stopped: subcommand failed`，最终 `metadata-generation-failed`；
- 没有改动当前 `.py311` 环境。

## 结论

1. 文件写入 414xx 后，Mac CP SDK 路线确实不再是单纯握手失败。
2. 当前端口顺序下，`MD=41415` 可以行情登录成功，但交易侧触发底层段错误。
3. 页面文字顺序下，`MD=41407` 返回 `客户端未认证`。
4. 当前不能把 414xx 路线作为 Stage78-1 虚拟盘默认执行路径。
5. 当前最稳路径仍是原先 `41207/41215 + vnpy_ctp 6.7.2.1`，它已经完成只读和 1 手报撤 smoke order。
6. 414xx 若必须继续，需要券商明确：
   - `41407/41415` 的 TD/MD 对应关系；
   - 该账号在 414xx 的 AppID/AuthCode 是否登记；
   - 是否必须使用官方 CP SDK，并提供可与 Python/vn.py 绑定稳定工作的封装版本或示例。

## 参数和结果变更

- 新增参数：无
- 修改参数：本机 local env 被用户改为 414xx；该文件不入库
- 删除参数：无
- 新增回测结果：无
- 修改回测结果：无
- 删除回测结果：无
- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用

## 过拟合与继续价值反思

- 是否过拟合：否。本阶段是 CTP SDK/前置/认证排障，不涉及策略收益、参数或品种选择。
- 是否有价值继续：有，但继续点必须收敛到券商确认和工程隔离。若继续在 414xx 上反复试错，价值会下降，并可能污染已打通的 412xx 路线。

## TODO

1. 建议将 `412xx` 测试柜台和 `414xx` CP 评测柜台拆成两个 local env，避免互相覆盖。
2. 向券商确认 `41407/41415` 的交易/行情前置顺序。
3. 向券商确认 `代码64：客户端未认证` 对应的 AppID/AuthCode/账号权限登记状态。
4. 若券商坚持 414xx，优先要求 Python/vn.py 可用的匹配封装版本，而不是继续用 `vnpy_ctp 6.7.2.1` 硬加载 `6.7.7 CP` framework。
