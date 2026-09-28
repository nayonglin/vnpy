# Stage000I 第八轮独立预审阻断整改

- line_id：`futures_trend_xgboost_formal_signal_marginal_utility`
- 当前模式：`day`
- 改动时间：2026-09-05 14:16-14:35 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：Stage001唯一执行前静态整改
- 是否重要突破：否；只关闭claim锁和异常诊断问题，没有产生XGBoost效果证据
- 是否触发A/B：否；未运行Stage001、候选策略、标签、训练、预测或A/C对照

## 调研与判断

- 公开资料：延续Stage000既有XGBoost与金融过拟合调研；本阶段不搜索策略alpha，问题来自第八轮对本地event锁与恢复异常链的静态审查。
- 平台实证：本机只读临时目录探针确认macOS支持对目录文件描述符执行`flock`，因此可用一次创建后不再替换的执行状态目录作为稳定锁锚点。
- 独立证据：第八轮reviewer session为`01a0701b-c33b-7fc3-8637-557735b01a81`，决定`BLOCK_STAGE001_UNIQUE_RUN`，P0=0、P1=0、P2=1、P3=1。
- 我的判断：R8-P2-001成立。claim既是待保护对象又被用作锁文件，缺失时静默无锁会破坏fail-close；应锁稳定状态目录，并把当前claim作为锁内必须重复验证的数据。R8-P3-001也成立，吞掉reconcile异常不改变安全结果，但会破坏唯一运行的可诊断性。

## R8整改

- `_execution_event_lock`改为对event父级执行状态目录加进程级`flock`并叠加线程锁；锁内核对目录文件描述符与当前路径的device/inode及目录类型，目录缺失、替换或锁失败均fail-close。
- 新增当前claim的安全读取：禁止跟随符号链接，核对打开文件与当前路径的device/inode、普通文件类型和完整读取长度；claim缺失、不可读、读取期间替换、schema或基础绑定异常均阻断。
- 通用event writer在构造新event后、原子替换紧前再次核对当前claim的nonce/lease；成功完成原语在加锁时和CAS紧前两次要求当前claim bytes/payload与调用方冻结claim精确一致，因此同时绑定authorization SHA和输入file contract。
- 新增真实双进程writer竞争测试：进程A持有状态目录锁时进程B通过真实`update_execution_event`阻塞；释放后两个真实writer串行推进，最终sequence从1精确变为3，无丢失更新。
- 新增claim缺失、claim与event错绑、锁内初验后claim替换、reconcile cleanup期间删除/替换claim反例；所有失败均保持event原bytes。
- final已rename异常分支不再吞掉reconcile错误；最终Stage001Error同时记录initial和reconcile错误，并以reconcile错误为cause。

## 本次变更

- 修改脚本：`tools/stage001_formal_event_feature_qualification.py`，新增状态目录锁锚点验证、当前claim安全读取/重复绑定和双异常保留。
- 修改测试：`tests/test_stage001_formal_event_feature_qualification.py`新增claim漂移、真实双进程writer及final已rename诊断反例，并为既有独立event测试补当前claim。
- 修改计划与状态：`plans/20260905_stage001_formal_event_feature_qualification.md`、`LINE.md`同步第八轮结论和Stage000I合同。
- 新增文件：第八轮blocked review/decision与本阶段记录。
- 删除文件：无。
- 新增参数：无策略或模型参数；仅新增内部锁与claim校验参数。
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

- RED：5个测试结果失败，覆盖无claim、claim/event错绑、cleanup后删除claim、cleanup后替换claim及final已rename双异常丢失；真实双进程竞争测试在旧实现下通过，用于补足进程级实证而非声称RED。
- GREEN：7项R8专项场景通过；runner专项`121 passed`。
- 本线：`152 passed`；其中runner专项`121 passed`。
- 全部27条XGBoost/PIT相关研究线按独立pytest进程运行：`884 passed`。
- `py_compile`：三个本线工具脚本通过。
- lint：`.py311`未安装ruff，不宣称lint通过。
- 输入合同：1410项；logical-key SHA为`a972f46932585adf1ad5bfc4f0c3d76d5b654cd587204b8c4bd0512b791aacd2`；file contract SHA为`b51f0b1c3d43f607952012102ab08486f714511bc2c48394d19ff35470a4906f`；runtime contract SHA为`04396eb74da1ed4812b0eabcc94e28cd2a64f90a1839d08ace6630faf2149e1e`；探针前后生产模块导入集合均为空。
- 生产只读身份：生产目录干净，detached HEAD为`d492ee072aa5a9d71477235d79f17d2a5db59db3`；active m0005、正式策略、C9-15万执行版本和材料manifest均匹配冻结值；本阶段未写生产目录。
- 唯一运行状态：authorization、claim/event状态目录、success final、failure final及隐藏staging/publish均不存在；Stage001未执行，唯一机会未消费。

## 输出文件

- report：本记录。
- summary：无；Stage001未运行。
- orders：无。
- daily：无。
- quality：R8 claim锁/绑定、真实双进程writer、异常诊断RED/GREEN、跨线回归、最终输入合同和生产只读核验。

## 结论与TODO

- 本阶段结论：`stage000i_eighth_prerun_blocker_remediated_pending_ninth_review`。
- 是否进入下一步：是，但下一步仅允许第九轮独立只读预审。
- TODO：第九轮reviewer必须静态复核状态目录锁锚点、当前claim双重绑定、真实双进程writer反例和final已rename双异常诊断。只有决定精确为`ALLOW_STAGE001_UNIQUE_RUN`且P0/P1/P2均为0，才允许创建一次性authorization；否则继续整改，不运行Stage001。

## 过拟合反思

- 运行前判断：否；整改对象是无标签锁、claim绑定和异常诊断。
- 运行后判断：否；没有读取标签、收益、回撤或交易结果，没有运行策略、训练或预测，也没有调整固定12特征、模型参数、0阈值、年份或样本。
- 剩余结构性风险：仍高；未来XGBoost的小样本和历史重复观察风险未被本阶段降低，后续仍必须依赖purged walk-forward及至少9个月/60个闭合事件的前向OOS。

## 继续价值反思

- 运行前判断：是；R8-P2-001可让claim漂移后仍完成唯一Stage001，必须在运行前关闭。
- 运行后判断：是，但仅限第九轮预审；锁与诊断修复不等于XGBoost值得接入。
- 原因：整改关闭已知claim锁绕过并提高失败可诊断性，但仍没有任何收益提高或回撤下降证据。

## 合入建议

- 是否更新本线`LINE.md`：是，更新为Stage000I已验证、等待第九轮预审。
- 是否更新`research/registry.md`：否，研究线目标和阶段方向未改变。
- 是否追加根目录`memory.md/back_log.md`：否，尚无回测、正式候选或跨线突破。
