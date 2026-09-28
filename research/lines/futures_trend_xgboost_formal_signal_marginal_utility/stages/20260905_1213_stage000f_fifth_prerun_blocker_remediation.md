# Stage000F 第五轮独立预审阻断整改

- line_id：`futures_trend_xgboost_formal_signal_marginal_utility`
- 当前模式：`day`
- 改动时间：2026-09-05 12:13-12:22 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：Stage001唯一执行前静态整改
- 是否重要突破：否；只是修复无标签资格运行的恢复真实性与相关性unknown语义，没有产生XGBoost收益或回撤证据
- 是否触发A/B：否；未运行Stage001、候选策略、标签、训练、预测或A/C对照

## 外部调研与判断

- 公开资料：延续Stage000已完成的XGBoost监督学习、meta-labeling、时序外推与金融过拟合资料调研；本阶段没有新增策略资料搜索，因为整改对象是第五轮独立预审定位的本地状态机、证据合同和生产相关性快照语义。
- 独立证据：第五轮只读reviewer session为`01a06f97-558c-76c0-b5b1-31a50ad11b19`，决定`BLOCK_STAGE001_UNIQUE_RUN`，P0=0、P1=1、P2=2、P3=0。
- 我的判断：三项问题都必须在唯一运行前关闭。成功包“哈希自洽”不等于worker确实按固定正式语义完成；相关性默认零也不等于不存在同向仓位。应通过独立重算和当前身份重验来fail-close，而不是接受缺失证据。

## 第五轮阻断与整改

1. R5-P1-001：成功恢复原先没有重验完整worker语义。
   - 成功包现在逐worker重验`status=completed`、每人一次基准回放、零checkpoint、固定2020-01-02至2026-08-28区间、15万元、固定live version、正式材料身份、模块路径、Python/runtime、独立PID和目录、零网络与全部敏感计数、sandbox及sensitive guard。
   - 从持久化的A1/A2事件CSV重新计算frame SHA、逐列容差对比和完整worker isolation；summary必须与重算后的完整字典逐字段相等，内部一致但语义错误的raw/portable回执不能恢复为completed。
2. R5-P2-001：成功恢复没有重新绑定完整输入、authorization/claim和execution event。
   - success bundle精确新增`input_manifest.json`和`execution_event.json`，保存worker实际消费的完整输入manifest和sequence=6的`publishing_success`事件。
   - 恢复前重新构建当前1410项manifest，检查逻辑键、每项path/size/mtime/SHA、runtime、正式身份及文件合同；按claim时间重新验证authorization窗口，并核对当前授权文件bytes、payload、精确bound-file键集合和当前文件SHA。
   - 状态目录event必须与成功包发布事件完全一致，或是由该事件唯一推进出的sequence=7 `published`完成事件；phase、sequence、details、summary/manifest SHA、cleanup状态和零敏感计数均重验。
3. R5-P2-002：生产相关性函数在候选历史不足时可提前返回默认零。
   - research-only instrumentation保留正式方向与入场决策，不修改生产文件；在正式快照外独立枚举当时真实同向持仓，并重算候选收益样本数、最低样本数、有效相关性数量及最大值。
   - 新增显式history availability和trace exact字段；候选历史不足、同向仓位未全部测量、原始快照与独立重算不一致时均fail-close。12项模型特征不增加，`same_direction_correlation`取已验证的重算值。

## 本次变更

- 修改脚本：`tools/formal_signal_event_features.py`，扩展相关性审计trace并对history unavailable、未测同向仓位和source/recomputed不一致fail-close。
- 修改脚本：`tools/stage001_formal_event_feature_qualification.py`，新增research-only相关性instrumentation、完整成功包输入/event持久化、worker语义重算、authorization/claim/current input/current event恢复重验。
- 修改测试：`tests/test_formal_signal_event_features.py`与`tests/test_stage001_formal_event_feature_qualification.py`新增相关性unknown/trace错配、自洽worker语义篡改、输入漂移、授权漂移和当前event替换反例。
- 修改计划：`plans/20260905_stage001_formal_event_feature_qualification.md`同步第五轮整改后的成功恢复与相关性trace合同。
- 新增文件：本阶段记录。
- 删除文件：无。
- 新增参数：无策略或模型参数；只新增审计字段和成功包文件。
- 修改参数：无训练参数、阈值、年份、样本过滤或交易参数变化；冻结输入仍为1410项，逻辑键SHA仍为`a972f46932585adf1ad5bfc4f0c3d76d5b654cd587204b8c4bd0512b791aacd2`。
- 删除参数：无。

## 回测/归因参数

- 数据区间：计划仍固定`2020-01-02 -> 2026-08-28`，本阶段未运行。
- 账户规模：计划仍为15万元，本阶段未运行。
- 成本口径：不适用；未生成收益或交易结果。
- 样本过滤：未改变，仍只允许56个动态LR快照对应的模型排名层正式根入场，固定`fu.SHFE`排除。
- 策略/归因口径：active m0005逻辑回归选品 + C9/15万，仅做无标签资格合同。

## 回测结果

- 新增的回测结果：无。
- 修改的回测结果：无。
- 删除的回测结果：无。
- 期末权益：不适用，未运行回测。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：0个新回测交易。
- 胜率：不适用。

## 验证结果

- 本线专项：`132 passed`。
- 全部27条XGBoost/PIT相关研究线按独立pytest进程运行：`864 passed`。
- 单一共享pytest进程曾得到`862 passed, 2 failed`；两项均因旧线同名`qmt_roll_official_live_config`模块缓存串用，分别隔离复跑均通过，分线全量也通过。未修改其他研究线。
- `py_compile`：三个本线工具脚本通过。
- lint：`.py311`未安装ruff，`python -m ruff --version`返回`No module named ruff`，未宣称lint通过。
- 输入合同：1410项；logical-key SHA为`a972f46932585adf1ad5bfc4f0c3d76d5b654cd587204b8c4bd0512b791aacd2`；file contract SHA为`cf458522e330770ec039aa29772deac6bc99e09d11a92459145d8d0b9178d901`；runtime contract SHA为`04396eb74da1ed4812b0eabcc94e28cd2a64f90a1839d08ace6630faf2149e1e`；探针前后生产模块导入集合均为空。
- 生产只读身份：目录干净，detached HEAD为`d492ee072aa5a9d71477235d79f17d2a5db59db3`；active材料仍为`m0005_20260901T165450+0800_1961d98ccb2b` / `ai_top10_plus_fu_official_live_v1` / `official_live_stage847_c9_15w_stage819_05r_stop_retry_once` / 15万元。
- 唯一运行状态：authorization、claim/event状态目录、success final和failure final均不存在；Stage001未执行，唯一机会未消费。

## 输出文件

- report：本记录。
- summary：无；Stage001未运行。
- orders：无。
- daily：无。
- quality：第五轮三项阻断的代码、测试、输入合同和生产只读证据。

## 结论与TODO

- 本阶段结论：`stage000f_fifth_prerun_blockers_remediated_pending_sixth_review`。
- 是否进入下一步：是，但下一步仅允许第六轮独立只读预审。
- TODO：第六轮reviewer必须逐项确认R5-P1-001、R5-P2-001、R5-P2-002关闭，并给出机器可读决定。只有决定精确为`ALLOW_STAGE001_UNIQUE_RUN`且P0/P1/P2均为0，才允许创建一次性authorization；否则继续整改，不运行Stage001。

## 过拟合反思

- 运行前判断：否；整改只涉及无标签证据和状态机，不读取收益或回撤结果。
- 运行后判断：否；没有运行基准、标签、训练、预测、候选策略、阈值扫描、年份选择或特征结果筛选，固定12特征未增加。
- 剩余结构性风险：是且仍高；历史区间被反复观察，未来树模型面对百余事件仍可能过拟合。这个风险只能由后续purged walk-forward与2026-09-05之后至少9个月/60个闭合事件前向OOS约束，不能由本阶段测试消除。

## 继续价值反思

- 运行前判断：是；第五轮问题会让唯一Stage001产物即使“自洽”也不具备可审计真实性。
- 运行后判断：是，但仅限第六轮预审；三项已得到反例测试与跨线回归支持，值得让独立reviewer复核。
- 原因：现在可以区分真实零与unknown，并要求恢复重演首次发布的完整语义；这提高Stage001一次性运行的证据价值，但仍不是XGBoost提升收益或降低回撤的证据。

## 合入建议

- 是否更新本线`LINE.md`：是，更新为Stage000F已整改、等待第六轮预审。
- 是否更新`research/registry.md`：否，研究线目标和阶段方向未改变。
- 是否追加根目录`memory.md/back_log.md`：否，尚无回测、正式候选或跨线突破。
