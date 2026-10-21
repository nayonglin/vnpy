# Stage129：初开合约月动作数据实现，尚未实际运行

- 时间：2026-10-18 21:41 CST；line_id：`futures_full_market_long_signal_ai`。非重要突破；本次是128固定科学合同的实现，不是新策略成绩。按root授权只实现新代码和小语义fixture，不读取真实行情或构建实际标签。
- 协议：`outputs/stage128_contract_choice_protocol/protocol.json`，23194B，SHA256 `bbd24a6e352fe0fbc77f710eeee18918cc1b4670749339e4f3ae67632095efe0`。

## 实现与接口

新增 `tools/stage129_contract_choice_dataset.py`，29265B，SHA256 `9888c1321e2242f06bf461806141326b88e113884fcf655040746e48c5e78035`；新测试 `test_stage129_contract_choice_dataset.py`，9218B，SHA256 `a9d4f374b85ae1c204a3a88f6d3053061be294355c960a16adfad28d56503875`。原009、049、070、071、042及原资产均不修改。完整依赖bundle、接口列和精确auth模板见 `outputs/stage129_contract_choice_dataset/implementation_receipt.json`，8606B，SHA256 `7cefbd970baa33a7cb9df21273999317f5a7971558c115c6e7884fa435bd1561`。

实际入口必须同时提供冻结协议SHA、root授权SHA、exact source bundle和全新输出路径；授权schema `stage128_exact_root_authorization_v1`、`stage=dataset`。本次未签发或执行实际授权。CLI：

```text
.py311/bin/python research/lines/futures_full_market_long_signal_ai/tools/stage129_contract_choice_dataset.py --protocol <absolute protocol.json> --protocol-sha256 bbd24a6e352fe0fbc77f710eeee18918cc1b4670749339e4f3ae67632095efe0 --authorization <root authorization.json> --authorization-sha256 <authorization SHA> --output <fresh absolute experiment directory>
```

manifest schema `stage129_contract_choice_dataset_v1`，`artifacts`为list，并在顶层给出相同的 `actions/common/mothers/terminal` 四bindings。终态及manifest使用`status=completed,mode=actual`；原生SELECT计数、fit/cash计数明确记录，失败保留现场不自动重启。

`mothers.csv.gz`保存原399252行完整071七列IDENTITY及原顺序；`actions.csv.gz`按母序号和真实epoch顺序流式输出，包含所有映射子观察（非法、历史不足、经济未决等照样保留）、完整070标签字段，以及`action_sequence_index=sequence_index`、`action_id=event_id`、`actual_epoch=reference_epoch`、母身份、anchor、u资格、容量。`common26.npz`为同序float64 Nx26原值和columns。母行无观察时不伪造动作；普通/F精确产品隔离，仅family共用风险名额。

实际只安排一条原生SELECT，复用accepted042 Market；母表取原070已接受IDENTITY。每母事件一次构造期限池，各月份重复只读该池并排除自己，避免049的destructive cache.pop和product/day唯一限制。仅计算COMMON所用13个期限控制，不展开无用qshuffle或巨peer表。前11项重算候选自身009 SMA20 ATR，不混入标签Wilder20 N；最后两项原COMMON分母2N保留。目标/初损/单位风险仍为0.25N。

路径为自身合约NARROW，无PT或DAY强平；保存u canonical为immutable anchor，远月不因初持不同而立刻退出，收盘anchor变化/缺失请求次源日旧持仓open退出，请求持续。取消、unknown、open和未就绪保留；最后u若D超已给日历/end仍按u信息判断eligible，标签右删失，不能用未来D是否有价筛除。只有已知生命周期和u数据/经济/容量等限制可拒绝。1%容量同时预留入场和当日全止损，`entry_capacity_qty>=round_lot`同时约束训练和未来选择。

为避免无效内存膨胀，实际标签按动作逐行输出，只有COMMON26保留一个大数组；不构造150万行宽标签DataFrame，不保存逐路径JSON。预算仍为一native读取/0fit/0cash；费用、风险、止损、模型、窗口无新增寻优参数。

## 有限验证

先运行测试获得缺失新模块的预期失败，再实现。最终只跑本次6个方法，`Ran 6 tests in 0.076s, OK`；另syntax和`--help`各exit0，无旧suite。内容覆盖：容量/缺观察母行、未来D/代表变化对u输入不变、真实候选自身SMA与Wilder区别、逐月期限控制逐列等价旧049、非canonical初持不立即退出及anchor请求锁存、单canonical个体标签对旧070有限回归、非法观察保留、普通F自身经济/peer隔离和noanchor禁止行动。第一次SMA差异fixture把唯一波动放在最新日，二者数学恰好相等；只修fixture为先前已有波动，没有改金融政策。

本次真实SQL、标签构建、模型拟合、现金账户、下载全0；权益、收益、回撤、Sharpe、总滑点、交易数、胜率均N/A。下一步由root核源bundle后授权一次actual，再接130共享6fit和131八现金；之后132独立审实际结果。

## 调研与反思

沿127/128已完成的[RBA期限论文](https://www.rba.gov.au/publications/rdp/2017/2017-03/data-and-measurement-of-commodity-risk-premiums.html)及[LEAN合约筛选源码](https://github.com/QuantConnect/Lean/blob/master/Common/Securities/Future/FutureFilterUniverse.cs)：月份选择具有独立经济含义，但不证明中国窄损可盈利。本次仅落实已冻结问题，无须再重复上网或补下载。

开始/结束按收益调参：否，未产生新收益；历史同数据多轮择题风险：是。继续价值：是，检验之前未允许的真实合约月动作；实现通过不等于收益进步。完整目标未完成，未证明普适高质量long、加大投注或正式资格。
