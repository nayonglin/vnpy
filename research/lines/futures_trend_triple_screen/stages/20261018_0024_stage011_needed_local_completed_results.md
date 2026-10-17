# Stage011 必要本机完成分钟批量资格结果

- line_id：`futures_trend_triple_screen`；记录时间：2026-10-18 00:24 CST。
- 唯一真实构建：2026-10-18 00:11:39—00:15:05，耗时205.62秒，exit 0；数据准备，非金融回测，非策略突破。
- 冻结依据：`20261018_0005_stage011_needed_local_completed_protocol.md`及Stage010需求；未修改LINE/registry、正式策略、旧工具、原base或Stage002 overlay。

## 调研判断与变更

沿用已核[TqSDK官方API](https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.api.html)及[公开源码](https://github.com/shinnytech/tqsdk-python/blob/master/tqsdk/api.py)完成K线合同，本阶段不连接提供商。只读取当前checkout的Stage459/462/461/456已声明completed来源及Stage008已独立接受的345行，不扩大到备份或forming来源；Stage491沿Stage002复用。

新增`tools/stage011_needed_local_completed.py`及6个有意义合成测试，先RED后GREEN；原Stage002的9个复用测试通过。新增参数仅`--build --demand-dir`数据入口，未新增/修改/删除策略参数。按跨源一致key和既有一致分钟拼成完整session，原CSV七字段及完整网格合格才追加新key；anchor也先验完整session。原键不覆盖，缺CSV不做DB回退，冲突隔离。

## 结果与独立审查

- 906个候选文件各读一次并核SHA，906个均匹配旧manifest声明；新增 **4,646,214** 分钟、**349** 合约，合格 **13,752** session。
- 固定需求 **28,268** session，ready由 **4,959** 增至 **18,711**；剩余 **9,557**，其中 **215 full_session、9,342 anchor**，full尚缺66,571分钟。
- 拒绝：**4,518** 缺七字段日线CSV、**5,036** 分钟不完整、**3** 既有key冲突。4,518恰好对应 **94个缺CSV文件合约**，包含 **159 full、4,359 anchor**；不是已有CSV缺目标日期。排除16个无真实日线carry约束后，Stage013正规日线恢复的真实目标为 **4,502**（159 full、4,343 anchor），仍为94合约。
- 3个既有分钟冲突：FG209.CZCE 2022-05-27（anchor，225个冲突key）；cu2010.SHFE 2020-08-27（full，283个冲突key）；cu2507.SHFE 2025-06-11（full，1个冲突key）。不能把三者都描述为孤立单根误差，也未据此判定哪方正确；全部保留拒绝，不修旧值。
- 新增key与A0全部实际 **106,731** 读取key交集为 **0**，原base/Stage002的当前SHA不变，A0既有回放可沿数据等价证据复用，未重跑。
- 独立review已通过，P0/P1均0：全新增key唯一且与A0读取集独立交集0；抽核8个session、9份来源payload。复用旧资格，不宣称全表逐价格独立认证。receipt：`outputs/stage011_independent_review/review_receipt.json`，SHA256 **8cdfdbba2a15d12e04c6792b9073d53744f4cb0e711f2f67e452fed7705528fa**。
- 新overlay SHA256：`c65ce34e2f02ebfa2af0b6cdfadc4c15ba377458ea61cd8d7ccf4457066908e9`；summary位于`outputs/stage011_needed_local_completed/summary.json`，剩余表为同目录`remaining_demand.csv`。
- remaining表旧`available_minutes/missing_minutes/missing_required_minutes`保留Stage010原值；更新覆盖应读`session_available_before/session_added_minutes/session_missing_after/anchor_present_after/ready_after`。

金融回放、下载、训练、订单、CTP连接均0；权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率全部 **N/A**，没有C0完整结果或alpha改进结论。

## 后续与反思

先恢复94个精确合约缺失日线以解除159个full的资格前提；另将5,036个真实分钟不完整需求（54 full、4,982 anchor）用于有界正规提供商分包。16个carry/no-real约束和3个旧分钟冲突单列，不下载不存在的日线，不使用daily-open fallback，不按截断收益选参，不自动启动C0。

运行前/后过拟合判断均为 **否**：按已冻需求及既定字段核数据，没有看收益调规则；继续价值均为 **是**：本机完成数据已大幅缩小缺口，下一步直接处理明确的数据阻塞。是否能改善收益与回撤仍需真正完整C0对照，不能由本阶段数据量推断。
