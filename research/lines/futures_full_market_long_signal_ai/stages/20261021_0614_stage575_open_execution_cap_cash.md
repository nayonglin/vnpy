# Stage575 原开盘执行模型买价上限：四账实际完成，固定门失败

- line_id：`futures_full_market_long_signal_ai`；已先读 registry，完整 98 品种/95 家族母域不缩。
- 记录时间：2026-10-21 06:14（Asia/Shanghai）。
- 工作区：`/Users/mac/Desktop/fian`；分支沿用 `codex/ai-training-data-expansion`，没有工作树或生产操作。
- 阶段性质：实现已冻结的 Stage577；root 唯一成功 actual 已完成四个新 C 现金账，等待 576 全面独审。
- 是否重要突破：否；是否触发 A/B：是，使用 157 OWN 四个既有 A 账户为精确对照，没有重放 A。
- 当前累计：535 actual fit /282 completed cash，另 1 个旧 partial 保留。本阶段 2 次 actual 启动、1 次完成；第一次 0 账即失败，第二次新增 4 cash，0 fit/SQL/GET/A replay。

## 外部调研与判断

本实现复用同轮 Stage574/576 已保存的原作者、官方与 GitHub 调研，不另开重复下载或资料门。它们已核对 CME 订单类型、Foucault 限价/不执行取舍，以及 LEAN、vn.py 的 bar 成交假设。我的判断是：价格上限是有别于换特征的执行干预，取消机会可能改善或损害完整账户；不能由订单常识推出昨收盘这个锚有 alpha。尤其不能搬用 `D.low` 穿价等成交，把本协议改成整日限价单。

当前仍是预先声明上限、按原 `D.open + 不利滑点/向上 tick` 模型允许或取消的日线情景，不代表已证明公开开盘后还能回到同一拍成交；原执行容量、历史 stale/unknown 边界保留。

## 本次变更与冻结规则

新增三个隔离脚本，没有修改任何旧策略/纯函数/数据：

- `tools/stage575_open_execution_cap.py`：薄 runner，读取既有精确信号、完整 mothers、已验 native cache、经济投影、四个 A OWN summary/daily 和原 bootstrap indices；执行四个 C 账。
- `tools/stage575_open_cap_kernel.py`：复制 131 的 `run_cash_account`，仅插入一个 guard，其余复用原纯函数；没有 monkeypatch。
- `tools/test_stage575_open_execution_cap.py`：7 个小型合成边界测试。

冻结协议 `outputs/stage577_open_execution_cap_protocol/protocol.json`：SHA256 `69b39cd7d330d267d73bd30a8479f05eac4dc6376687d125f69bcda5dc8ff48e`。

原 u 时刻选中的 intent、同 epoch `u_close`、生命周期/K、母域和 u 预算公式不变。D 先完成原有 missing/occupied/lifecycle/stale/risk/qty 检查，原 `execution_quantity` 返回正 qty 后，在 `ledger.enter` 之前比较原 `unit['buy']['fill_price'] <= intent['u_close']`。精确相等通过，不引入经济偏移或容差。超出则只把该单 `D_qty` 置 0，原因为 `execution_price_above_u_close`，不调用 enter。原 qty=0、unknown 原因优先保留。

不裁成交价、不等待 D.low、不改变原 F、`SL0=raw D.open−0.25N`、R0、20low、K、风险、成本、容量或手数公式。同 D 取消金额不重新分配；后续 u 使用 C 自身自然变化的权益/持仓按原规则预算。原核对 D.low 止损与收盘估值的既有使用没有更改；新 cap 谓词不使用 D.high/low/close。

- 新增参数：无可调经济参数；新增一个精确规则 `BUY fill <= u.close`。
- 修改/删除参数：无。
- 窗口：2020-01-01—2026-10-16、2023-01-01—2026-10-16，各 base/stress。
- 初始资金：1,000,000；原单家族风险 0.0025、总风险 0.02、缓冲保证金 cap 0.25/buffer 1.1、成交量参与率 0.01、初损 0.25N，全不变。
- 数据：399,252 原始 mothers，161,014 forward mothers，完整 98/95；直接复用 157 VOLUNTARY_RESELECT 信号，不读取 actions/COMMON、不新训练/查询 SQL/下载。
- root 另授权：从 accepted157 manifest 的四个 OWN 账户精确 fills binding 各读一次小文件，只做 BUY 的 `(event_id, epoch)` 身份外连接，输出 A-only/common/C-only 及各自日期/数量；不新增逐笔反事实 PnL 或可加因果归因。

## 必要验证及 source-ready

7 个新合成测试通过（0.025 秒）：等于上限允许；高于上限取消且不 enter；使用原含滑点/向上 tick quote 而非 raw open；原 qty=0 优先；缺 D 保留 unknown；同 D 取消预算不补其他单；移除唯一 guard 后函数源码与原 131 逐字相同。编译、无金融副作用导入、source-diff 和 `--check-source` 均成功。

测试中只修正了一条不合法的合成价格（极低 u_close 会使旧 adverse SELL quote 非正），改成正常 uclose 配极大 Dopen 验证原 qty=0；没有据历史收益改策略。未为本阶段重放旧书或扩展测试套件。

冻结源：

| 文件 | SHA256 |
|---|---|
| runner | `d80c31df2f319c1d5f6b7409937b050bda05d237c674837607fd817a37d98586` |
| kernel | `09ef1c6de31900006007f8bf83de906f317654bd3ed452c752814ec234f794e6` |
| tests | `88d42e8b3e9e53d118afe0b8d64fefb2e354eb69dcfce7e6e81fb200e53beb58` |

receipt：`outputs/stage575_open_execution_cap/source_ready1/source_ready.json`，明确 `actual_started=false`、fit/cash/SQL/GET=0。独立 reviewer 576 已收到冻结源和 receipt，进行一次 guard/source-diff 定向核验；root 是唯一 actual 执行者。

计划输出：四个新 C 的全 ledger/summary；8 账指标；原固定 252 日 circular block、2,000 次配对 bootstrap 分布与四组 CI；cap 逐单审计；BUY 身份重叠；含零 family-year、年度、sector/variant 和尾部；原 stale/unknown；门判及执行模型披露。四个 A 完全复用 OWN 既有结果，不能误取 157 manifest 中旧 baseline_books。

## 实际结果（06:16 补录）

root `actual_run2` session18121 已 exit0，耗时 **3.984267 秒**，4 cash started/4 completed，0 fit/SQL/GET/A replay。全 98/95、信号、协议、kernel/source 不改。`actual_run1` 的 status 读入适配失败保留，未启动现金账；本阶段合计 **2 次 actual 启动、1 次完成**，不能计成 8 cash。

下表胜率为已平仓净 PnL 胜率，交易数为已平仓笔数；fills 含买卖两边，滑点是原研究账累计 CNY 成本，不能当作点数。

| 窗口/成本 | A 收益 | C 期末权益 | C 收益 | A 最大回撤 | C 最大回撤 | C Sharpe | C 滑点 CNY | C 平仓笔数 / fills | C 胜率 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2020 base | 122.9270% | 1,592,408.39 | 59.2408% | -15.6274% | -13.9982% | 0.7775 | 65,053.27 | 716 / 1,433 | 14.9441% |
| 2020 stress | 52.8420% | 1,421,955.12 | 42.1955% | -11.3593% | -14.9108% | 0.7928 | 89,632.22 | 528 / 1,057 | 13.2576% |
| 2023 base | 82.5437% | 1,637,474.19 | 63.7474% | -9.9021% | -6.0798% | 1.4225 | 30,541.07 | 289 / 579 | 15.5709% |
| 2023 stress | 52.6646% | 1,525,384.59 | 52.5385% | -6.4228% | -5.5859% | 1.5075 | 49,403.63 | 247 / 495 | 15.3846% |

| 窗口/成本 | C−A 收益百分点 | C−A 回撤百分点（正为更浅） | 配对日 log 均值增量 95% CI | cap 拦截 / tested | BUY A-only / common / C-only |
|---|---:|---:|---|---:|---:|
| 2020 base | -63.6862 | +1.6293 | [-0.0003820593, -0.0000355691] | 953 / 1,670 | 804 / 493 / 224 |
| 2020 stress | -10.6465 | -3.5515 | [-0.0001375825, +0.0000541394] | 761 / 1,290 | 590 / 364 / 165 |
| 2023 base | -18.7962 | +3.8223 | [-0.0002868879, +0.0000673991] | 384 / 674 | 293 / 203 / 87 |
| 2023 stress | -0.1261 | +0.8368 | [-0.0000979792, +0.0001010703] | 341 / 589 | 254 / 170 / 78 |

四组 C 自身均正收益、wealth 有效，但收益全部低于 A；主检验 2020 stress 的回撤反而更深，CI 下界也没有大于 0。因此 `continuation_gate.status=unsupported`，return/drawdown/CI 三门失败，`cash_nominal_pass=false`。胜率较高和三组回撤更浅不能替代完整收益/回撤门；2020 base 的 CI 甚至整体在 0 以下。**不支持“拒绝高于昨收的模型化买价可带来稳定增量优势”。**

cap 拦截约 57%—59% 的本来已通过原验证、且有正手数的候选。身份外连接显示 C 并非简单的 A 子集：后续持仓/权益自然不同会出现 C-only，因此这些身份数不能当作逐笔可加 PnL 归因，也不表示同 D 释放预算重新分配。

执行/数据边界继续保留：所有四 C `execution_unknown=true`，容量 unknown roots 为 20/11/4/2；2020 两账另有 entry execution unknown 4/3，2023 两账为 0；2020 有历史 stale，2023 无历史 stale，四账期末 stale positions 均 0。门的 `financial_unknown=true`；不能因期末无 stale 抹掉历史问题，也不因此自动扩大下载或重算范围。`goal_complete/production_qualified/increased_betting_qualified` 均为 false。

本次仅从已落的 terminal、8 账 summaries、comparisons、gate、BUY identity overlap 与 cap audit 取小摘要，未重读 native/行情/mothers/signals，不新计算现金路径；576 正独立全面审查全部四个新账。

固定判据：四个 C 自身正收益且 wealth 有效；primary2020 stress 收益严格更高、回撤严格更浅、配对日 log 增量 CI 下界 >0；其余三组收益/回撤不差。四个 CI 和原执行/估值 unknown 均披露。失败关闭这个精确 cap，不改报价锚、偏移、窗口、品种、止损或加注救参。即使 nominal 通过，也不表示生产资格或完整目标完成。

## 反思与下一步

- 运行前是否过拟合：新规则本轮没有按结果择参；整个长期同史搜索仍有较高选择偏差。本轮固定一个自然锚、四个窗/成本与原置信区间，禁止失败后的邻近参数救参。
- 运行结束是否过拟合：本次没有改参数/窗口/对象救分，但长期同史搜索风险仍高。结果不支持当前规则，不能用胜率、单窗 Sharpe 或回撤较浅事后换成功标准。
- 继续价值：本次固定执行机制验证已完成，有价值；继续扫描同锚偏移或择窗救参的价值为否。该精确 cap 应按冻结失败分支关闭。
- 下一步：576 完成四个新现金账的一次全面独审；不重跑 A、不新下载日线、不追加 cap 参数实验。由 root 合并正式结论，本子任务不自行修改母路线或生产。
- 同线并行纪律：只写本唯一 Stage575；不改 `LINE.md`、registry、根总账、正式策略或部署。

## 06:15 root 首次启动及最小读入适配

root 的 `actual_run1` 保留为失败证据：exit1、约 0.00107 秒、0 cash started/0 completed/0 fit。失败发生在读取小 accepted157 manifest 后，未进入任何大数据或现金账户。组合断言报 `accepted157 own cash required`；实读确认 schema 仍为正确的 `stage157_voluntary_cash_v1`，实际差异是已验收的 `status=completed_with_metadata_continuation`，四账数仍为 4。

只把 runner 的旧 `status == completed` 检查适配为严格允许 `('completed','completed_with_metadata_continuation')` 两值，未泛化任意 success；策略、协议、输入、guard、kernel/tests 均不变。按 root 要求不重跑 7 fixture、不重读大输入、不自行 actual。原 ready1 保留，过渡 ready2（仅接受 metadata 状态）未实际执行并保留；最终 ready3 同时接受上述两值。

最终 runner：15,230B，SHA256 `392672d8fd6ed12732f1eca692814dd450f6ca7a5161bdbfc5ecb78fd4ead5d4`；最终 receipt：`outputs/stage575_open_execution_cap/source_ready3/source_ready.json`。上表旧 runner SHA 是首次启动身份，不覆盖旧证据。root 将使用 ready3 启动 fresh `actual_run2`；576 已收到唯一单行 diff，不重 guard/大数据审查。此适配没有产生历史收益，新财务指标仍 N/A，累计 cash 计数仍为 278 completed +1 旧 partial。
