# Stage000G 第六轮独立预审阻断整改

- line_id：`futures_trend_xgboost_formal_signal_marginal_utility`
- 当前模式：`day`
- 改动时间：2026-09-05 12:55-13:01 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：Stage001唯一执行前静态整改
- 是否重要突破：否；只关闭首次成功发布的当前绑定窗口，没有产生XGBoost效果证据
- 是否触发A/B：否；未运行Stage001、候选策略、标签、训练、预测或A/C对照

## 调研与判断

- 公开资料：延续Stage000对XGBoost监督学习、meta-labeling、时序外推与金融过拟合的既有调研；本阶段没有新增策略搜索，因为唯一问题来自第六轮对本地成功发布状态机的静态审查。
- 独立证据：第六轮reviewer session为`01a06fcf-7abc-7742-9e96-74bba42905d4`，决定`BLOCK_STAGE001_UNIQUE_RUN`，P0=0、P1=0、P2=1、P3=0；第五轮worker恢复与相关性unknown问题已确认关闭。
- 我的判断：reviewer指出的R6-P2-001成立。恢复路径严格并不能证明首次发布严格；授权/输入在最初校验后漂移时，旧内存对象仍可能形成completed。必须让正常发布、恢复和完成事件共用同等级的当前重验。

## R6-P2-001整改

- 新增`_read_json_mapping_bytes_once`：authorization只读取一次bytes，由同一份bytes同时解析payload并计算claim SHA，消除初始payload/SHA双读TOCTOU。
- `_validate_success_bundle`的当前输入和当前authorization重验改为安全默认开启。
- `_publish_success_bundle`在success staging的atomic rename前、final rename后和attempt cleanup后三次显式强制重建当前1410项输入/runtime/生产身份，并重验当前authorization bytes、payload、精确bound-file键集合和当前文件SHA。
- 新增`_complete_success_publication`：写`completed sequence=7`前再次强制完整success bundle与当前绑定重验，确认状态目录仍精确等于持久化`publishing_success sequence=6`事件；完成后再验证唯一派生的published事件。
- 新增调用链反例：`input_after`后输入漂移、authorization漂移、bound file漂移均不能在rename前形成final；rename后输入漂移会留下不可完成的final；cleanup后到sequence=7之间输入或authorization漂移时event保持running sequence=6。

## 本次变更

- 修改脚本：`tools/stage001_formal_event_feature_qualification.py`，新增单次authorization读取、安全默认当前重验和统一success completion函数。
- 修改测试：`tests/test_stage001_formal_event_feature_qualification.py`新增7条首次发布/完成窗口反例与单次读取测试。
- 修改计划与状态：`plans/20260905_stage001_formal_event_feature_qualification.md`、`LINE.md`同步第六轮结论和Stage000G合同。
- 新增文件：第六轮blocked review/decision与本阶段记录。
- 删除文件：无。
- 新增参数：无策略或模型参数；仅新增内部校验函数和测试夹具。
- 修改参数：无训练参数、阈值、年份、样本、特征或交易参数变化；冻结输入仍为1410项，逻辑键SHA不变。
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

- RED：5条核心反例在修复前全部失败，分别证明单次读取helper缺失、rename前输入/authorization/bound-file漂移未阻断及sequence=7前重验缺失。
- GREEN：runner专项`108 passed`；本线`139 passed`。
- 全部27条XGBoost/PIT相关研究线按独立pytest进程运行：`871 passed`。
- `py_compile`：三个本线工具脚本通过。
- lint：`.py311`仍未安装ruff，未宣称lint通过。
- 输入合同：1410项；logical-key SHA为`a972f46932585adf1ad5bfc4f0c3d76d5b654cd587204b8c4bd0512b791aacd2`；file contract SHA为`7f4526599b7f241b6946f9c398d35c1ab4774dee3048ed44b5b16c5745dc59e2`；runtime contract SHA为`04396eb74da1ed4812b0eabcc94e28cd2a64f90a1839d08ace6630faf2149e1e`；探针前后生产模块导入集合均为空。
- 生产只读身份：第六轮已复核生产目录干净，HEAD为`d492ee072aa5a9d71477235d79f17d2a5db59db3`，active材料及C9-15万执行身份未变；本阶段未写生产目录。
- 唯一运行状态：authorization、claim/event状态目录、success final和failure final均不存在；Stage001未执行，唯一机会未消费。

## 输出文件

- report：本记录。
- summary：无；Stage001未运行。
- orders：无。
- daily：无。
- quality：R6-P2-001的RED/GREEN、跨线回归、输入合同和状态机证据。

## 结论与TODO

- 本阶段结论：`stage000g_sixth_prerun_blocker_remediated_pending_seventh_review`。
- 是否进入下一步：是，但下一步仅允许第七轮独立只读预审。
- TODO：第七轮reviewer必须确认R6-P2-001关闭并检查无新增P0/P1/P2。只有决定精确为`ALLOW_STAGE001_UNIQUE_RUN`且P0/P1/P2均为0，才允许创建一次性authorization；否则继续整改，不运行Stage001。

## 过拟合反思

- 运行前判断：否；整改对象是授权读取与发布状态机，不接触结果变量。
- 运行后判断：否；没有读取标签、收益、回撤或交易结果，没有运行策略、训练或预测，也没有调整固定12特征、模型参数、0阈值、年份或样本。
- 剩余结构性风险：仍高；未来XGBoost的小样本和历史重复观察风险未被本阶段降低，后续仍必须依赖purged walk-forward及至少9个月/60个闭合事件的前向OOS。

## 继续价值反思

- 运行前判断：是；R6-P2-001会让首次成功与恢复成功采用不同证明标准。
- 运行后判断：是，但仅限第七轮预审；正常发布、恢复和sequence=7现在都要求当前绑定，值得独立复核。
- 原因：整改提高唯一Stage001资格运行的真实性，但仍没有任何收益提高或回撤下降证据。

## 合入建议

- 是否更新本线`LINE.md`：是，更新为Stage000G已整改、等待第七轮预审。
- 是否更新`research/registry.md`：否，研究线目标和阶段方向未改变。
- 是否追加根目录`memory.md/back_log.md`：否，尚无回测、正式候选或跨线突破。
