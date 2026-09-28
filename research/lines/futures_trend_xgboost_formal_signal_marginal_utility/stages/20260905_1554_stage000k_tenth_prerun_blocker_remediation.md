# Stage000K 第十轮独立预审阻断整改

- line_id：`futures_trend_xgboost_formal_signal_marginal_utility`
- 当前模式：`day`
- 改动时间：2026-09-05 15:33-16:07 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：Stage001唯一执行前静态整改
- 是否重要突破：否；只关闭event无覆盖提交、哈希链读取和worker绑定问题，没有产生XGBoost效果证据
- 是否触发A/B：否；未运行Stage001、候选策略、标签、训练、预测或A/C对照

## 调研与判断

- 公开资料：Python 3.11官方`os`文档确认`os.link`支持`src_dir_fd`、`dst_dir_fd`和`follow_symlinks=False`，而`os.replace`在目标存在时会静默替换；POSIX `link()`规范确认目录项创建是原子的，目标已存在返回`EEXIST`。来源：<https://docs.python.org/3.11/library/os.html>、<https://pubs.opengroup.org/onlinepubs/009695399/functions/link.html>。
- 本机实证：`.py311`在macOS临时目录中通过目录fd成功执行`os.link`，第二次链接到同名目标稳定返回errno 17，即`EEXIST`。
- 独立证据：第十轮reviewer session为`01a0706f-a29b-7d83-8a48-e02f3ec9ea71`，决定`BLOCK_STAGE001_UNIQUE_RUN`，P0=0、P1=0、P2=1、P3=0。
- 我的判断：R10-P2-001成立。只在覆盖式rename前增加校验无法消除最终校验到提交之间的lost update；正确边界不是继续给可变单文件叠加检查，而是让每次状态变化成为不可覆盖的新目录项。

## R10整改

- `event.json`固定为不可变sequence 1基准；每次更新创建`event.seq-{20位序号}.prev-{前一条原始bytes SHA256}.json`，文件名直接承载链关系，不改变冻结event payload schema。
- writer在同一锁定状态目录fd中以`O_EXCL`创建0600临时文件，完整写入并fsync后，再核对目录锚点、claim原始bytes、当前event payload、当前原始bytes和当前条目名。
- 最终提交改为目录fd相对`os.link`。从同一前态出发的writer计算出同一目标名，只允许一个创建成功；目标已存在时旧writer以`execution_event_compare_and_swap_mismatch`失败，绝不覆盖竞争条目。
- 提交后fsync目录并重新遍历完整链，校验本次payload、原始bytes和条目名。reader拒绝非法文件名、序号重叠、序号缺口、前序SHA错误、不可变字段漂移、非法状态迁移和敏感计数回退。
- 所有当前状态读者均迁移到链末端，包括耐久门、reconcile、failure counter持久化、success publish和sequence 7完成；sequence 1仅用于状态目录初始原子发布与故障恢复。
- worker capability在持有event锁时签发，并预先绑定注册该capability的下一条不可变event路径；capability文件身份写入该条event后才释放锁和启动worker。worker只读取这一条不可变注册事件，portable成功包按A1 sequence 3、A2 sequence 5校验路径。

## 本次变更

- 修改脚本：`tools/stage001_formal_event_feature_qualification.py`，新增不可变event哈希链、无覆盖提交、链末端读取、全读者迁移和具体event条目capability绑定。
- 修改测试：`tests/test_stage001_formal_event_feature_qualification.py`新增真实提交边界竞争、当前条目改写不覆盖、非规范初始原始bytes贯穿和两次追加链测试；旧单文件fixture迁移为追加式历史。
- 修改计划与状态：`plans/20260905_stage001_formal_event_feature_qualification.md`、`LINE.md`同步第十轮结论和Stage000K合同。
- 新增文件：第十轮blocked review/decision与本阶段记录。
- 删除文件：无。
- 新增参数：无策略或模型参数；仅新增内部event序号、前序SHA和当前条目名提交参数。
- 修改参数：无训练参数、阈值、年份、样本、特征或交易参数变化；冻结输入逻辑键仍不变。
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

- RED：旧实现下4项新反例稳定失败，分别证明event仍被覆盖写、竞争提交没有`EEXIST` CAS、提交时当前条目可能被覆盖、首次读取的非规范原始bytes未贯穿。
- GREEN：4项核心新场景通过；runner专项`132 passed`。
- 本线：`163 passed`；其中runner专项`132 passed`。
- 全部27条XGBoost/PIT相关研究线按独立pytest进程运行：`895 passed`，27个进程退出码均为0。
- `py_compile`：三个本线工具脚本通过。
- 输入合同：1410项；logical-key SHA为`a972f46932585adf1ad5bfc4f0c3d76d5b654cd587204b8c4bd0512b791aacd2`；file contract SHA为`b7b0dc8457e916fcaca8a7dd3b28f5ba932cbed84d41cd05b24278bf26a24fd8`；runtime contract SHA为`04396eb74da1ed4812b0eabcc94e28cd2a64f90a1839d08ace6630faf2149e1e`；探针前、runner导入后及manifest重建后的生产模块导入集合均为空。
- authorization精确绑定共35项，当前仅最终`prerun_review`与`prerun_decision`按计划缺失，其余33项存在。
- 生产只读身份：生产目录干净，detached HEAD为`d492ee072aa5a9d71477235d79f17d2a5db59db3`；active m0005、正式策略、C9-15万执行版本、15万元资金和材料manifest均匹配冻结值；本阶段未写生产目录。
- lint：`.py311`未安装ruff，不宣称lint通过。
- 唯一运行状态：authorization、claim/event状态目录、success final和failure final均未创建；Stage001未执行，唯一机会未消费。

## 输出文件

- report：本记录。
- summary：无；Stage001未运行。
- orders：无。
- daily：无。
- quality：R10不可变哈希链、无覆盖`linkat`提交、真实提交边界竞争、全读者与worker capability迁移的RED/GREEN、本线163项及跨线895项回归。

## 结论与TODO

- 本阶段结论：`stage000k_tenth_prerun_blocker_remediated_pending_eleventh_review`。
- 是否进入下一步：是，但下一步仅允许第十一轮独立只读预审。
- TODO：由第十一轮reviewer静态复核R10-P2-001及全部历史开放项。只有决定精确为`ALLOW_STAGE001_UNIQUE_RUN`且P0/P1/P2均为0，才允许创建一次性authorization并执行一次Stage001；否则继续整改，不运行Stage001。

## 过拟合反思

- 运行前判断：否；整改对象是无标签文件系统提交语义和证据链。
- 当前判断：否；没有读取标签、收益、回撤或交易结果，没有运行策略、训练或预测，也没有调整固定12特征、模型参数、0阈值、年份或样本。
- 剩余结构性风险：仍高；未来XGBoost的小样本和历史重复观察风险未被本阶段降低，后续仍必须依赖purged walk-forward及至少9个月/60个闭合事件的前向OOS。

## 继续价值反思

- 运行前判断：是；R10-P2-001会让唯一Stage001证据发生不可检测的lost update，必须在运行前关闭。
- 当前判断：是，但仅限完整验证和第十一轮预审；账本整改不等于XGBoost值得接入。
- 原因：无覆盖提交让并发状态演进可以被文件系统原子语义证明，恢复与worker绑定也回到同一不可变证据链，但仍没有收益提高或回撤下降证据。

## 合入建议

- 是否更新本线`LINE.md`：是，更新为Stage000K整改完成、等待完整验证及第十一轮预审。
- 是否更新`research/registry.md`：否，研究线目标和阶段方向未改变。
- 是否追加根目录`memory.md/back_log.md`：否，尚无回测、正式候选或跨线突破。
