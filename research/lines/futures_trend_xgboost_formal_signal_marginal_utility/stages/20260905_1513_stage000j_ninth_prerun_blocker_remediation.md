# Stage000J 第九轮独立预审阻断整改

- line_id：`futures_trend_xgboost_formal_signal_marginal_utility`
- 当前模式：`day`
- 改动时间：2026-09-05 14:56-15:17 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：Stage001唯一执行前静态整改
- 是否重要突破：否；只关闭event落盘原子边界和失败诊断问题，没有产生XGBoost效果证据
- 是否触发A/B：否；未运行Stage001、候选策略、标签、训练、预测或A/C对照

## 调研与判断

- 公开资料：延续Stage000既有XGBoost与金融过拟合调研；本阶段问题来自第九轮对本地文件系统原子边界的独立静态审查，不新增alpha假设。
- 平台实证：本机临时目录探针确认`.py311`在macOS支持`os.open/stat/replace`的`dir_fd`参数及目录fd fsync，可把最终event提交绑定到同一锁定目录inode。
- 独立证据：第九轮reviewer session为`01a07048-afd1-7490-9595-fa11d4044eef`，决定`BLOCK_STAGE001_UNIQUE_RUN`，P0=0、P1=0、P2=1、P3=2。
- 我的判断：R9-P2-001成立。原实现虽然锁住旧状态目录inode，但最后仍按路径创建临时文件并rename；当前路径在校验后被替换时，验证对象与写入对象可能分离。两项P3也成立，分别削弱进程锁证据和唯一运行失败诊断。

## R9整改

- claim和event在锁内均通过目录fd相对`open/stat`读取并禁止符号链接；读取前后两次`fstat`再与目录fd相对路径`stat`比较类型、device/inode、size、mtime_ns及ctime_ns，捕获同inode原地改写和读中漂移。
- event临时文件通过锁定目录fd相对`O_EXCL`创建，写入、权限、文件fsync完成后，重新核对目录锚点、claim原始bytes/payload和expected event原始bytes，再以同一目录fd执行相对`os.replace`并直接fsync该目录fd；writer不再重建父目录。
- 提交后再次核对当前目录锚点、claim原始bytes与已提交event原始bytes；在rename调用瞬间整个状态目录被替换时，写入只落到旧fd指向的脱离目录，当前路径event保持不变并fail-close。
- 双进程测试在真实`flock(LOCK_EX)`调用前后分别写attempted/entered握手，父进程确认B已尝试但尚未进入后才释放A，不再依赖固定sleep推断调度状态。
- 非final-success失败路径分别捕获failure publish和event update异常；任一二次异常都以单一Stage001Error保留initial、failure_publish与event_update三段诊断，并以最后发生的二次异常为cause。

## 本次变更

- 修改脚本：`tools/stage001_formal_event_feature_qualification.py`，新增目录fd相对安全读取与提交原语、读前后文件身份校验、提交后绑定复核及三重失败诊断。
- 修改测试：`tests/test_stage001_formal_event_feature_qualification.py`新增同inode claim漂移、提交前claim/event/目录漂移、rename瞬间目录替换、提交后claim漂移和三重错误保留测试；双进程测试增加确定性握手。
- 修改计划与状态：`plans/20260905_stage001_formal_event_feature_qualification.md`、`LINE.md`同步第九轮结论和Stage000J合同。
- 新增文件：第九轮blocked review/decision与本阶段记录。
- 删除文件：无。
- 新增参数：无策略或模型参数；仅新增内部目录fd、expected claim bytes与故障注入钩子参数。
- 修改参数：无训练参数、阈值、年份、样本、特征或交易参数变化；冻结输入仍为1410项，逻辑键SHA不变。
- 删除参数：无。

## 回测/归因参数

- 数据区间：计划仍固定`2020-01-02 -> 2026-08-28`，本阶段未运行。
- 账户规模：计划仍为15万元，本阶段未运行。
- 成本口径：不适用；未生成收益或交易结果。
- 样本过滤：未改变，仍只允许56个动态LR快照对应的模型排名层根入场事件，固定`fu.SHFE`排除。
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

- RED：修正测试夹具后5项行为反例稳定失败，覆盖同inode claim漂移、提交前claim/event/状态目录漂移和三重异常丢失；随后新增提交后claim漂移反例稳定失败。确定性双进程握手在旧锁实现上通过，只增强证据而不冒充RED。
- GREEN：9项R9专项场景通过；runner专项`128 passed`。
- 本线：`159 passed`；其中runner专项`128 passed`。
- 全部27条XGBoost/PIT相关研究线按独立pytest进程运行：`891 passed`，27个进程退出码均为0。
- `py_compile`：三个本线工具脚本通过。
- lint：`.py311`未安装ruff，不宣称lint通过。
- 输入合同：1410项；logical-key SHA为`a972f46932585adf1ad5bfc4f0c3d76d5b654cd587204b8c4bd0512b791aacd2`；file contract SHA为`8bc5f42cd551ad113f475b20bcaf654743759ce2b07d71a067a3868118fc0dba`；runtime contract SHA为`04396eb74da1ed4812b0eabcc94e28cd2a64f90a1839d08ace6630faf2149e1e`；探针前、runner导入后及manifest重建后的生产模块导入集合均为空。
- authorization精确绑定共32项，当前仅最终`prerun_review`与`prerun_decision`按计划缺失，其余30项存在。
- 生产只读身份：生产目录干净，detached HEAD为`d492ee072aa5a9d71477235d79f17d2a5db59db3`；active m0005、正式策略、C9-15万执行版本和材料manifest均匹配冻结值；本阶段未写生产目录。
- 唯一运行状态：authorization、claim/event状态目录、success final、failure final及隐藏staging/publish均不存在；Stage001未执行，唯一机会未消费。

## 输出文件

- report：本记录。
- summary：无；Stage001未运行。
- orders：无。
- daily：无。
- quality：R9目录fd提交、claim/event读中漂移、rename边界、真实双进程握手、三重异常RED/GREEN及待完成的跨线回归。

## 结论与TODO

- 本阶段结论：`stage000j_ninth_prerun_blocker_remediated_pending_tenth_review`。
- 是否进入下一步：是，但下一步仅允许第十轮独立只读预审。
- TODO：第十轮reviewer必须静态复核目录fd相对操作、rename前后claim/event原始bytes、同inode漂移、rename瞬间目录替换、确定性双进程握手和三重异常诊断。只有决定精确为`ALLOW_STAGE001_UNIQUE_RUN`且P0/P1/P2均为0，才允许创建一次性authorization；否则继续整改，不运行Stage001。

## 过拟合反思

- 运行前判断：否；整改对象是无标签文件系统原子性、锁和异常诊断。
- 当前判断：否；没有读取标签、收益、回撤或交易结果，没有运行策略、训练或预测，也没有调整固定12特征、模型参数、0阈值、年份或样本。
- 剩余结构性风险：仍高；未来XGBoost的小样本和历史重复观察风险未被本阶段降低，后续仍必须依赖purged walk-forward及至少9个月/60个闭合事件的前向OOS。

## 继续价值反思

- 运行前判断：是；R9-P2-001可能让唯一Stage001的终态与当前claim不一致，必须在运行前关闭。
- 当前判断：是，但仅限最终验证和第十轮预审；状态机整改不等于XGBoost值得接入。
- 原因：目录fd提交关闭了已知路径重定向问题并提高失败证据质量，但仍没有任何收益提高或回撤下降证据。

## 合入建议

- 是否更新本线`LINE.md`：是，更新为Stage000J整改完成、等待最终验证及第十轮预审。
- 是否更新`research/registry.md`：否，研究线目标和阶段方向未改变。
- 是否追加根目录`memory.md/back_log.md`：否，尚无回测、正式候选或跨线突破。
