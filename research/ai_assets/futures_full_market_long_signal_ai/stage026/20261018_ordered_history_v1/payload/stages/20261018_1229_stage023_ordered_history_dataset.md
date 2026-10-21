# Stage023：一次构建全市场20bar因果序列表示

line_id=`futures_full_market_long_signal_ai`。记录时间2026-10-18 12:29 CST；沿用`codex/ai-training-data-expansion`，未创建分支/工作树。重要突破版本：否；本阶段仅实现Stage022冻结表示合同，没有训练、绩效或候选晋级结论。

## 合同与研究判断

实施前已读取本线registry、LINE、022 spec和protocol，以及009接受的窗口源码/011独审收据。022协议SHA为`ae0708cb9eb232d5c5d7936fc705f77b2f361e4b039442e707b82c828b27f99a`。本次沿用022已查Lo/Mamaysky/Wang与随机特征原论文的研究判断：摘要之外的历史表示可以提出可检验的信息问题，不能预设能够赚钱；本阶段不新增论文、模型或窗口选择。

开始过拟合判断：新增选参否。严格按022一次构建，固定20bar、4通道、float32；不因D结果删除ready行，不读D作特征。研究选择及多次历史探索的风险仍存在。继续价值：是，给下一项预冻结AI信息对照提供真实输入，避免把摘要指标称为已经验证的时序信息。

## 新增与未修改项

- 新增`tools/stage023_ordered_history_dataset.py`和六个行为测试，输出`ordered[N,20,4]`与按009原ready顺序的`sequence_index,event_id`映射。
- 每一window只使用同一reference epoch、到u为止的21根连续有效正量bar；ATR与S11复用009公式并逐行核对。输出j1..20分别为相邻收盘差/ATR、振幅/ATR、收盘位置（平价0.5）、log(当日量/窗口V0..19均量)。先float64计算，统一量化为little-endian float32。
- NPZ唯一键`ordered`；不保存原始绝对OHLC、volume、ATR。BAG不重复保存，消费端按量化后的四元组收益→振幅→位置→相对量完整字典序排序，字段整体移动，不加日期/index平局键。
- 修改/删除既有策略参数、标签、暖机、ready状态、旧成绩：均0；没有新setup、C9、AI池或D可评价过滤。

## 行为验证与真实运行

仅运行六个新行为测试：首次真实RED为tool chunk`c80d1b` exit1，六项明确缺实现断言失败，无错误；实现后GREEN为`328156` exit0，6/6通过。覆盖公式及平价、短/跨epoch/日历缺口拒绝、未来D毒值不影响及未知ready保留、父S11冲突拒绝、float32-only存储、完整四元组BAG。用户要求避免反复旧检测，本次不跑旧suite。

唯一全构建真实tool起点`13595e`，session`88878`；`4f3114`仍运行，最终`f84f0b` exit0。实际开始`2026-10-18T12:28:36+08:00`，结束`2026-10-18T12:29:03+08:00`，27.607751458秒。协议文件名的12:29是root冻结记录标签；实际运行时间保留原样，没有改写时间。完整构建1次/启动1次，输入失败0，重跑0。

一次只读SQL扫描使用与009完全相同的BAR_FIELDS和`ORDER BY contract_epoch_id,trade_date`，得到1,552,456行/9,520 epochs。源库378,552,320字节，before/after路径、尺寸、mtime、inode、WAL/SHM状态一致。继承源SHA`a63f92ce7e1d51080ba92f7214fc493f1e6a69aa0079d6ecef7190eea9b58711`，未重hash全库；没有额外SQL探针、下载或provider连接。

## 结果与边界

- 父母表399,252行不变；194,709个feature_ready全部有序列，其中194,168已知标签、541未知标签，均保留。没有把未知转0或负类。
- 序列shape`[194709,20,4]`、15,576,720个有限标量、dtype`<f4`。映射194,709行，ID唯一，sequence_index恰0..N-1。
- 逐行父ATR最大绝对差`1.1368683772161603e-13`，S11最大绝对差`1.7763568394002505e-15`，为已保存CSV数值解析的浮点差，未更改公式或特征；冲突超过预定数值容差则立即失败。
- `export/manifest.json` SHA：`3b8da3d7e94a9e3e3fc755b233d2bb93ef6ebf6813a66a0a0a913052eb8bf64a`。
- `ordered_history.npz`：43,546,129字节，SHA`7f8994108482597e66e7e4cb379f46a86a89976dff035e7d68cb8616bdca3ea3`。
- `event_ids.csv.gz`：8,193,711字节，SHA`b829623c1c1d716a7af3cdc21a0dc0cbab3adba9ae85dfc98fe7ada93e98963d`。
- 源码SHA`0544681ca1396d1b0eb4bc219d30b0bcb008998513bb7ba238a2292c37cd6ae0`；测试SHA`d707ab7914bf0184ff852acd51e36c465574f55d76eaebd8c1783ba172daf711`。
- 最终本地读取核对tool`1fcddf` exit0，仅读新NPZ/ID/manifest，未追加SQL、fit或金融运行。

manifest绑定022、009 manifest/feature labels、011独审、009源码、source calendar、scope dates、DB状态、当前代码/测试/实际终态。实际tool句柄另存`tool_execution_receipt.json`，有界测试日志及收据保留。新资产inventory显式角色和reproducibility_required；原库、父原价CSV与秘密均不是本次复制输出。独立Stage025尚待完成，不提前宣布新表示已经独立验收。

## 财务记录与后续

新增模型fit0、金融回测0、下载0。期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率：全部N/A。没有账户、真实成交、执行容量、小止损或加注生存证据。

结束过拟合判断：新增选参否，未看模型结果、未修改协议，但新表示本身仍有研究选择风险。继续价值：是，供024按冻结108fit完成ORDER/BAG/S对照，再由025独立验算；本阶段不给任何盈利结论，不追加其他研究。用户的全市场高质量做多、更高收益/更低回撤完整目标仍未达成。
