# Stage015 已恢复日线与已验provider分钟的必要资格增量

- line_id：`futures_trend_triple_screen`；记录时间2026-10-18 00:40 CST；数据增量，非金融回放，非alpha突破。
- 冻结合同：`20261018_0031_stage015_daily_recovered_minute_delta_protocol.md`；root确认Stage013独立通过后唯一构建，exit 0，耗时 **28.79秒**。未修改LINE/registry、旧工具、策略参数或原数据。

## 调研判断与实现

复用前阶段已核[TqSDK官方日线接口](https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.api.html)及[公开源码](https://github.com/shinnytech/tqsdk-python/blob/master/tqsdk/api.py)的来源纪律，实际本阶段零连接。新增`tools/stage015_daily_recovered_minute_delta.py`及4个合成契约测试，RED→GREEN；复用Stage011跨源一致拼接、原Stage002完整session与七字段校验，不复制新alpha逻辑。

本阶段只认Stage013独立receipt **194e48847c9e0927772c482cd5bacc3529a625ac76aeec2a157089924177c795**允许的4,500个精确合格目标，不要求把原parent exit 1改成0；原两条无后继拒绝保持。另加入Stage012已独立验收的11个session/2,475分钟。合计 **4,511 session、96合约**，不是重新全验Stage011。

原base、Stage002、Stage011逐文件一次流式读/hash，仅保留scope精确网格的 **1,822** 个既有key；全部新key被证明位于该已核既有范围，且不覆盖既有key。其他日期不在内存中重建，不重聚合原13,752个合格session。新增入口参数为`--build --daily-review-sha`，策略参数无新增/修改/删除。

## 结果与输出

- **1,480** 个增量session完整七字段合格，**3,031** 个因分钟不完整继续拒绝；无新冲突或价格修复。
- 新增 **452,401** 分钟、**56** 合约；overlay SHA256 **5f756b03fd459905e8a4a75057f05be17f767b773a300097ade4b22a62ddc178**。
- 固定总需求 **28,268**，ready **18,711→20,191**；剩余 **8,077**（**135 full、7,942 anchor**）。未受影响的 **23,757** 行ready原值继承；不覆盖Stage011结果。
- 与全部既有可相交scope新key交集 **0**；与A0实际 **106,731** 读取key交集 **0**。原base/Stage002/Stage011 SHA和输入保持不变，A0不重跑。
- Stage013两条无后继anchor、16个无真实日线carry约束及原3个分钟冲突均未进入放行scope；不以新日线匹配授权覆盖旧分钟H/L/C。
- 输出目录：`outputs/stage015_daily_recovered_minute_delta/`；含`overlay.csv`、`source_manifest.json`、`session_manifest.csv`、`quarantine.csv`、完整继承的`demand_readiness.csv`、更新后的`remaining_demand.csv`、`a0_path_equivalence.json`和`summary.json`。
- 当前独立review **pending**，已交相同独立reviewer做新来源/有界样本/继承readiness/A0交集审查，不重洗旧Stage011。实际日志仅有旧helper的pandas FutureWarning；当前版本结果不受影响，不为其改旧代码或重跑。

新增样例：AP005.CZCE 2020-01-10恢复日线后完整225根通过；SH605.CZCE 2026-03-05由344个既有key＋1个新key且两源一致拼齐；rb2010.SHFE 2020-04-01使用已验Stage012来源。拒绝样例AP005.CZCE 2020-01-23仅224/225，anchor需求也不豁免整session资格。

## 金融指标、后续与反思

金融attempt/下载/账户engine/订单/撤单/训练均0，权益、总收益、最大回撤、Sharpe、滑点、交易次数、胜率全部 **N/A**。累计金融attempt仍4、完成仍1；仍没有完整C0结果，数据进展不能代替alpha判断。

下一步只按更新remaining集中规划必要真实分钟补齐，保留两条无后继、16个carry和3个旧冲突的资格边界；本阶段不授权C0新attempt、daily-open fallback、策略优化或生产。

运行前/后过拟合判断均 **否**：按已冻目标和固定源合同验数据，不看收益改阈值；继续价值均 **是**：29秒将1,480个原缺口转为可用资格，直接缩小135个full/7,942个anchor后续数据需求。其余是否可获得、真实C0是否改善收益/回撤仍未知。

## 独立复核补记（2026-10-18 00:48 CST）

first_screen_independent完成有限复审，P0/P1=0；receipt SHA为3512261d2191384f1099e7fbb77eda9622c9610ca855ad1d4607ad33e76552c9。4511范围精确等于013已接受4500＋012已接受11，拒绝2日/16carry/原3冲突未被放行；23,757未受影响readiness行继承一致，全部452,401新增键有序唯一且与A0实际106,731键交集0，180输入SHA均未变。独立价格资格只抽4个真实session，没有重聚合全部旧数据。

20191是继承时间覆盖计数，不是对所有旧源H/L重新资格；已经发现的859四个full需求由Stage016另行处理。本复审只接受本阶段新增delta，不批准C0_attempt3、daily-open fallback或生产晋级。
