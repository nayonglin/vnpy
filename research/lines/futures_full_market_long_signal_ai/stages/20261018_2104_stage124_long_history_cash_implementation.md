# Stage124 固定12个月历史背景资金入口实现

- 时间：2026-10-18 21:04 CST；研究线 `futures_full_market_long_signal_ai`。
- 性质：实现冻结，非重要突破；本阶段没有运行真实回测，没有收益结论。
- 当前独立目标：全市场全品种高质量做多研究；本包只测固定12日历月历史信息增量，不能替代总目标或正式策略。

## 设计依据与判断

已读取本线 registry 与 Stage121 固定协议，SHA `c9a9538de0160266624c2bbfd8912964a44b2cfda97e639d1079fb1614bd7421`。前置调研以 Time Series Momentum 原论文及 GitHub `kieranjwood/trading-momentum-transformer` 数据准备代码为依据，由 root 固定为同合约日收益链的12日历月背景，不复制月度多空策略，也不把 feature 指数说成实际收益。124 无新研究选择，直接实现被冻结的资金检验。

开始反思：本实现没有新增结果调参；同一历史反复研究的选择风险**存在**。继续有价值：此前只含20日背景，本包新增更长但固定的信息跨度，且用完全相同资金引擎检验，具有可证伪性。

## 版本变更与参数

- 新增 `tools/stage124_long_history_cash.py` 与8项有限 synthetic 边界测试；只借用113作有限模板，不改113或070/042/054纯helper。
- 两臂固定 `CONTROL` / `LONG_HISTORY`；第二臂使用123实际完成的同维度固定模型分数。没有读取会员类别数据、旧模型或旧预测。
- 输入精确为 `market_protocol/narrow_labels/narrow_manifest/fit_manifest/predictions_main/held_diagnostic` 六项；两臂继续共同保留 `external_missing`，缺失和未来未知标签不成为资金开仓门槛。
- 新增实验身份：protocol Stage121；fit schema `stage123_long_history_fit_v1`；cash schema `stage124_long_history_cash_v1`。
- 没有新增或修改alpha、标签、止损、风险、成本参数；没有删除原执行保护。原070 NARROW、初始100万元、0.25N初始止损、单family0.0025、总计划风险0.02、保证金0.25与buffer1.1、20low/换月/lifecycle/stale/gap不封顶全部沿用。
- 2个独立资金起点 × 2种成本 × 2臂 = 8账户；共享1次native SQL；原070两套252源日block/2000次bootstrap indices原样绑定，绝不重新生成。
- 原u联合预算预留、D只减量、整数手、当u不循环使用卖出释放预算均未变。滑点已在成交价中，只在报表归因，不重复扣减。

## 闸门与输出

四组收益、回撤、自身正收益和主stress严格正CI条件照121；另三组差值允许恰为0，primary stress收益差与CI下限均须严格大于0；不按实现结果修改闸门。两组held只作原已知u日等权净R诊断，不能进资金回放。完整unknown/open/stale状态、无交易DD为N/A、破产账本保留。输出保留全部账户账本、年度与2026未完年切片、全family含0贡献、集中度、费用/滑点、gap及超过1R损失、finite native案例和不确定性报告。

最终 manifest 的 `artifacts` 是list；`terminal` 是精确文件绑定。初始actual目录固定为 `outputs/stage124_long_history_cash/cash`，必须fresh。CLI `--protocol --protocol-sha256 --authorization --output`，无 `--authorization-sha256` 选项；授权文件运行时完整绑定并写manifest，且只接受schema `stage121_exact_root_authorization_v1`、root、cash、exact_source_authorized与协议/输出/六inputs/source bundle的精确值。实施授权不等于actual授权，本阶段只留实现freeze。

## 有限验证

8项synthetic fixture：缺失及未来unknown不删行动；完整双臂及共享missing闭包；primary stress严格收益差与其他三组非负；CI必须有限且严格正；相对收益不能掩盖自身亏损/破产；未知不覆盖名义失败且不能把未成交信号当现金暴露；空reference DD及缺held不判成功；原bootstrap矩阵必须匹配源日历且为合法整数索引。

先红：目标实现不存在，8项明确断言失败。后绿：8项通过，0.036秒。两个新文件语法通过，CLI help退出0。没有旧suite/重复回测/新下载/标签构造/大库hash。

| 真实执行或结果 | 本阶段值 |
| --- | --- |
| 新模型fit / 新现金账户 / native SQL | 0 / 0 / 0 |
| 新标签 / 下载 / whole DB hash | 0 / 0 / 0 |
| 期末权益、收益、回撤、Sharpe、总滑点、交易次数、胜率 | 未运行；全部不适用，不用0替代 |
| 新增/修改/删除真实回测结果 | 无 / 无 / 无 |

## 精确冻结与后续

- 源码 `27397` bytes，SHA `cd7d4da128a1995ae618c1a0232ff8ef0e8fb1b7f56f96d9c65134b762600023`。
- 测试 `6005` bytes，SHA `c56b8c0919548b65d82ec5ddebf88851e22d661abfdf71fdfe4b7f3e7661315b`。
- 可复验接口/完整source bundle：`outputs/stage124_long_history_cash/implementation_freeze.json`。
- TODO：root等122/123的终态与精确bindings，另签一次actual现金授权；若123训练支持不足则0cash。实际8账户完成后由125独立全面复审，126统一决策。不进行多轮预审或为失败救参。

结束反思：实现本身没有对收益进行拟合，历史选择风险仍**是**；继续固定检验有价值**是**，但本阶段没有证明可加注、可晋级、可盈利或目标完成。
