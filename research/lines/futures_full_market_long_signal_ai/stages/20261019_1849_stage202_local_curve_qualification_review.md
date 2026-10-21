# Stage202：局部价格弦线投影的独立有界资格审查

- line_id：`futures_full_market_long_signal_ai`。
- 当前模式：Stage200 冻结协议的独立方法、关键源码与少量新 fixture 审查；不运行 actual，不另开审查代理。
- 开始记录时间：2026-10-19 18:49 CST；工作区 `/Users/mac/Desktop/fian`，沿现有工作区，未切换分支。
- 阶段性质：无标签源资格检查；非重要突破，不触发正式 A/B，不授权金融实验。
- 当前状态：**方法、关键源码、独立小 fixture 与 root 唯一 actual 小输出复核通过；源/几何资格有限接受，剩余核心阻断 0。**
- 本阶段新增 projection / fit / cash / selection / SQL / 下载 / 标签或绩效读取均为 **0**；累计仍 **421 fit / 226 cash**。

## 结论与审查边界

本阶段只接受“在既定输入上按固定规则计算一个局部 log 价格形状”的资格问题。**几何关系有新信息，不代表历史首发 PIT、合理价格、做多可预测性、现金收益或增加投注的资格。** 不因正价/三点覆盖看起来充分而授予这些解释。

已完整读取 `research/registry.md`，确认本线；复用 Stage198/199 本轮已完成的网上、GitHub 与历史有界去重，不重复搜索、克隆或安装。协议路径为 `outputs/stage200_local_curve_qualification_protocol/protocol.json`，独立重算这个 4,439 字节小文件的 SHA256 确认为 `944f1b91312898d55d99b96995d665d737f64f41caa23115fadaf167fb0aa180`。不读取或 hash 旧大 CSV、价格数据库、收益账本或模型。

## 方法与来源预审

1. Stage129 的 `simulate_action()` 先对 invalid-u bar 提前返回，随后写入 `N_u/low20_u/u_close`，再检查 20 日历史、economics 和未来 label。Stage200 只按 finite positive `u_close` 与名义月首晚于 u 选点，因此没有额外用未来成熟、K 或可成交结果筛池；缺失 u_close 仍须保留为未知动作。
2. 每个 exact `product_id/u_date` 的点集必须隔离普通/F。完整 YYYYMM 转成月份坐标，query 只能取正价池中严格相邻的两侧月份，按实际名义月距加权；首尾无两侧、非法价及到月/过月均未知，不外推、不跨品种。同 product/u 出现重复 nominal month，整个组未知，不能挑一条代表。
3. 固定 q 是 `log(Fq) - ((mR-mq)*log(FL)+(mq-mL)*log(FR))/(mR-mL)`。同一正比例换价不改变 q，log 价格对月份为仿射关系时 q=0。它只是名义交割月份上的无量纲价格弦线偏离，不能称为真实到期导数或库存/便利收益测量。
4. 非冗余反例成立：至少四个月，query 为第 2 月，保持 query 自身全部历史与第 1/2 月不变，将第 3 月的整段价格历史同乘常数。原 global front/next 两点 basis、所有 peer 一日 return 及 tenor 摘要、query 自身 history/normalizer/cost 不变，而 query 局部弦线变。该反例证明新 q 不由原 COMMON 唯一决定；没有证明整套模型分数/账户动作相同或新信息有 alpha。

旧一日 basis-momentum 可由前后两日 front/next basis 恢复；旧 `return~tenor` 斜率已试过。它们不因换名获得新信息资格。Stage199 所核 Bianchi 作者论文的曲率 spread 在较高成本下净收益弱/负，多空证据也不能外推到本线单腿 long first-exit。我的判断：一次无标签几何与覆盖核验有价值，直接启动曲率 fit/cash 暂无依据。

## 源码、fixture 与实际小输出复核

已完整核读 Stage201 的 14,274 字节实现及现有四个几何 fixture；独立复核精确 10+7 允许列、母子 event/product/family/u_date/u_index 映射、完整月份解析、池/邻居/q、所有 action/mother 原序、no-child、一次 round_trip CSV 读取、fresh actual_run1 与机械 anchors。源码 SHA256 为 `7258b0233d8ee30db3484aaa65c4799da6a7e3c15ca2860828aa9cd302fe06a6`；现有 fixture 源码 SHA256 为 `6b982a494fd291fe620cd8f5430c48b81fd77754dd8298ba1b5e932a29d4a693`。

独立运行三个新小 fixture，**3/3 通过**：

- 9 个 action / 4 个 mother，普通/F、不同日期的三个独立三点组，各得到自己的不等月距 q；无 child mother 保留，输入 DataFrame 未被修改。
- 最近的 0 价月份不进入正价池，但动作仍保留；query 正确使用其前后严格相邻的有效月份，没有把非法价变成 0 或删行。
- action 的 u_index 与 mother 不一致时直接 ValueError，不能混入同组计算。

现有四个 fixture 已核其逻辑，覆盖不等月距、原身份/no-child、log 仿射零值、单位不变、端点/非正价/到月/全正价重复月及 COMMON 不变 witness；本审查不再次运行它们或旧 suite。独立新 fixture 命令 fresh exit=0。

透明保留一个非阻断语义边界：实现检测的是**正价且名义月首晚于 u 的 pool 内重复月**。诊断 fixture 中同月一条正价一条 0 价，结果保留正价 query ready，而不是全组 unknown；Stage200 “同 product/u 重复 nominal month”文字未显式写 pool 限定。本次不把它隐藏为全部重复情况均已验证。接受这一点的范围限于已冻结 Stage129 来源：`context()` 每个 canonical epoch 在同一 u 只产生一条 action，exact product 的 epoch 直接编码唯一 YYYYMM，所以池外同月重复不可达。未来更换来源必须重审，不能沿用本接受结论。已将边界同步 root/实现者；未改冻结协议或源码。

核心阻断 **0**；已通知 root 可以唯一执行一次 actual。actual 只能由 root 运行；本审查不建 observer/wrapper，不读 actual 大表进行二次投影。

root 随后执行唯一 actual，terminal `completed`，耗时约 44.22 秒。本审查独立核读 `summary.json`、`terminal.json`、`manifest.json`、三张小 coverage 表和 `anchors.json`；另运行纯小输出断言与重算命令，fresh exit=0，并生成本阶段小 receipt。没有读取 `action_projection.csv.gz`、`mother_projection.csv.gz`、`q_vector.npz`，没有重算它们的 hash，也没有重复读取旧 CSV 或运行 actual。

| 有界核验项 | 结果 |
| --- | --- |
| action 完整域 | `1,552,456`，四状态计数之和与冻结 domain 相同 |
| mother 完整域 | `399,252`，三状态计数之和与冻结 domain 相同 |
| 有 q 的 action | `1,082,980 / 1,552,456 = 69.7591%` |
| action 未知 | no-lower `212,702`、no-upper `203,068`、nominal-month-not-after-u `53,706`，全部计入完整域 |
| mother 状态 | source-ready-some `193,129`、source-ready-none `19,723`、no-child `186,400` |
| mother 宇宙 | `98` code / `95` family / `6` 所；完整保留不依赖 q 可用性 |
| 小覆盖表 | 17 年、97 个有 action 的 code、4 状态；每表 action 总和 `1,552,456`，ready 总和 `1,082,980` |
| 16 个机械 anchors | sequence 唯一且递增，三 epoch 与 exact product、完整月份坐标相符；正价、名义月首 > u、lower < query < upper 全通过；独立 `math.log` 公式重算最大绝对误差 `0.0` |
| 绑定和读数收据 | protocol/source SHA 与预审一致，manifest input bindings 与冻结协议一致；源 before=after；1 projection / 1 action read / 1 mother read，无大输入再 hash |
| 金融计数 | 本 actual `fit/cash/selection/SQL/downloads=0`；累计仍 `421/226` |

`coverage_by_product_id.csv` 只描述实际有 action 的 97 个 code；summary 的 98 个 code 来自完整 mother 域，不能把这一区别误报为删品种，也不为补展示而重跑。97 个有 action 的 code 均至少有一个 ready；这只证明支持不限于少数 code，**不证明每 code 流动性或经济可比**。小表的金融期货 action ready 比例约 `32.0083%`，其他期货约 `71.4710%`，说明覆盖明显不均匀，不可把全域平均可用率当成统一预测资格。

小 anchors 可以机械复核价格关系和身份，但未独立遍历全投影证明每个邻居的实际全池相邻性；该性质依赖本次已核的统一源码及固定/独立小 fixture。对新投影的大文件 hash 仅沿用 manifest，未在本审查重算；对旧输入 SHA 继承已接受来源链与 stat 一致性，不声称本次重新字节认证了大文件。

最终接受结论为 `source_geometry_qualification_accepted_only`，**剩余核心问题 0**。预测效果、流动性/可成交价格、真实法律到期与严格 release-vintage PIT 均不在已通过范围内；不能把这些未认证问题隐藏为“数据全部通过”，也不能因此自动发起新 fit/cash 或增加投注。

## 本次变更、结果与后续

- 新增：本唯一 Stage202 及 `outputs/stage202_local_curve_qualification_review/review_receipt.json` 小复核收据。
- 新增/修改/删除交易参数：0；修改/删除既有脚本或结果：0。
- 数据区间、账户规模、成本口径：N/A，本阶段不定义或运行金融回测。
- 期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率：全部 **N/A**，未回测，不能写作 0。
- 不改 Stage198/199/200/201、`LINE.md`、registry、memory 或 back_log；由 root 合入。
- 下一步：本次资格审查收口，不补做 observer、wrapper、复扫大表或第二次实际投影。只有 root 另行冻结完整单假说金融协议后才可讨论 fit/cash；该新授权与本接受结论不同。

## 开始与结束反思

- 开始是否新增收益驱动过拟合：**否**；不读新收益、不拟合/搜索或按效果选月份。已有 421 fit / 226 cash 及多轮同史择题风险仍然存在。
- 开始继续价值：**是，限一次无标签源资格核验**；可避免在错误月份/身份/样本收缩上建立后续假说。
- 结束是否新增收益驱动过拟合：**否**；实际仅计算固定价格几何，没有读标签/收益、改方向/阈值/月份或按效果筛选。历史择题风险仍为**是**，几何新信息不能抵消累计选择偏差。
- 结束继续本审查的价值：**否，既定资格问题已收口**；不因还有更多可统计项就扩大工程。完整全市场高质量做多目标仍有价值，但本阶段给直接曲率训练/加注的依据仍为**不足**；应由另一个完整、可证伪的金融协议决定是否继续。
