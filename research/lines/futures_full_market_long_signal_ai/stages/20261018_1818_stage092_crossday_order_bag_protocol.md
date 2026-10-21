# Stage092 当前跨日目标中的时间位置：ORDER/BAG固定新桥接

- line_id：`futures_full_market_long_signal_ai`；2026-10-18 18:18 CST；现checkout/分支，不建worktree或新分支。
- 完整目标：全市场全品种高质量做多、极窄止损的可生存性、成本后更高收益且更低回撤。此处只检验一种输入位置结构，不做正式晋级/加注/生产操作。
- 阶段性质：收益前科学合同；重要突破否。当前累计345研究fit/78cash；本合同下新增actual0，目标active未完成。

## 调研、旧停止与为何只保留这一次

090基于[Deep Sets论文](https://arxiv.org/abs/1703.06114)与[作者仓库](https://github.com/manzilzaheer/DeepSets)、路径表示文献及本仓公式，区分共同摘要、集合与时间位置。common26不可逆恢复过去20bar四通道的位置；同common/BAG可有不同ORDER。文献不证明期货预测力或更大模型需要。

旧024/026已经否决特定DAY/4R＋表示/学习器/OPEN包，027当时否决立即改目标继续同OHLC循环。这些停止不撤销。当前070跨日first-exit目标在本提案以前已独立固定，与DAY标签并非正单位变换：同一D日可有不同后续首次退出路径、经济净收益和成熟日。此处允许的仅是**已固定的新经济对象的一次目标迁移检验**，不是为了让旧成绩通过才改目标，不从087最新cash成绩挑窗口/映射/参数。090已披露历史暴露，不能称严格全盲。

083换分母被否决、089固定OI包停止，不因此凭空允许无限模型试验。本合同仅一次ORDER−BAG；若不支持即停止这个20bar4通道/固定RFF181桥接/当前NARROW包，不扩window/channel/kernel/seed/容量/阈值/目标/stop/风险救援。

## 纯X复用，完整母体与共享缺失

1. 仅复用023已接受`ordered_history.npz`的`ordered[194709,20,4]` float32与194709个event_id；不重建tensor、不SQL/下载/原raw资格工程。只读旧ID表event_id用于映射，不消费旧DAY y/identified/known-date/feature-ready/mask/scores。旧subset sequence_index绝不是当前full sequence_index。
2. 新093只按event_id与当前070完整399252母体连接，导出legacy_tensor_index（缺失−1）、共享sequence_missing、当前身份与order hash；不复制完整tensor。索引/缺失准备0SQL、0fit、0labels。旧tensor的21bar资格不能变成当前20ready动作门。
3. 完整2020+每臂161014=98×1643预测（含no-reference/notready/unknown）必须保留；tensor缺失不删训练/预测行、不硬拒绝交易、不当负类。动作仍只按原当前ready20、finite score>0及原070经济/生命周期/资金规则。
4. 四通道原样为简单20TR均值ATR归一的收盘差、振幅、close-location、log相对量；不是Wilder N，不含open或绝对价格。保持旧float32量化，不改scale为新止损N。当前common26前11也从009 OWN按event_id取得，是同旧S11定义，直接复用。新Y与stop仍是070自身Wilder20 N。
5. BAG对原量化的完整四元组按收益/振幅/位置/量lexsort一起移动，不分列排序、不重算相邻收益、不用日期/index打平局。它仅去掉这些派生四元组所在时间位置，不等于没有任何路径信息。

## 唯一181项桥接，不称旧139头未变

两臂只有ORDER/BAG，无新COMMON臂。共同线性背景为common26标准化值＋26个missing＋共享sequence_missing=53项；再接128项RFF，**共181项**，另Ridge intercept。旧头139→181增加42项，这些是两臂完全相同的当前共同背景与缺失控制；这是新桥接内同容量，绝不是旧模型未变。没有无信息padding冒充有效容量一致。

RFF输入严格沿旧91维：S11标准化＋20×4；source024 `make_mapping`相同rng20261018生成W_base(91,128)、b(128)，两臂同W/b，`phi=sqrt(2/128)*cos(z@(W_base/sqrt(91))+b)`。不选seed/带宽/核/宽度，不扩W吃common26。common新增部分在线性头共享，不单边给ORDER。允许直接引用旧pure canonical_bag/make_mapping/feature_head的RFF部分，不调用旧fit/training/date_weights/预测mask/报告入口。

common26的mean/population-std与26missing沿当前071定义，仅本fold成熟训练、当前权重；S11用前11列相同统计，缺S列归训练均值。sequence四通道均值/总体std只从本fold成熟训练中可观察tensor计算，每事件权重均分到20位置，所有位置pooled、ORDER/BAG相同，不学各位置独立scaler、不沿用旧DAY统计。全missing/var0固定mean0/std1（var0但有值mean为实训mean），记录finite_count。

缺tensor时直接令标准化后的80维为共同0（等价于raw填pooled mean），共享missing=1；两臂RFF输入和输出必须完全相同，不能先给raw0再标准化成假历史。可观察tensor仍原float32转float64后按共同通道stats缩放，BAG排序原量化四元组。

Ridge alpha1/intercept/cholesky/单线程。只检验固定有限RFF对有序/集合布局的利用，**表示几何偏好仍在**；正结果不是模型无关的信息论优势或因果顺序效应。没有新COMMON对照，不能据ORDER胜BAG宣称优于当前COMMON/正式版；两个臂可能都更差。

## 训练、时间、held与12fit

cutoff2020-01-01/2023-01-01；main/holdout0/holdout1，组沿既定完整SHA256(family_id)整数mod2。训练只当前NARROW closed_complete_bar_model、u<cutoff且非空label_known_date<cutoff；held训练排除对应组，fold内family并发唯一性→u日期等质量→均值1权重。不能沿旧DAY资格/成熟/权重，也不借WIDE标签。

2cutoff×3scope×2arm=12新fit。main2020预测20—22，2023预测23+至2026-10-16；held同一母体仅按组划分预测、各臂合并held仍161014，不拼held模型进入主现金。共644056预测；未知/取消/未成熟/开放不作0或负类。

## 8现金、证据与冻结门

main ORDER/BAG×2020连续/2023独立冷启×base/stress=8新现金，均至2026-10-16。accepted070原run_cash_account/reserve/quote/ledger，不用080预过滤或OI；100w/单family.25%/总2%/buffered margin25%/buffer1.10、.25N/Wilder20/maxSL0因果20low、u预留/D只减不回收、原gap/换约/期限/缺价延期/超额破产不变。无PT/DAY强平/持有期上限/retry/加注。

主对比ORDER−BAG：2020stress收益差>0、DD不更深且共同252源日块/2000次/seed20261018配对日log差CI下端>0；base同方向，2023两成本收益差>=0/DD不更深。另要求ORDER自身四组合净收益均>0，防止把两个亏损臂的较小损失当作目标实现。空BAG的DD为NA/unidentified，不机械取0比较。现有两个窗口indices直接复用，不重造seed/块长。

held两组各报告closed且known_date<=end、ready20共同域的`(I_ORDERpos-I_BAGpos)*net_R_stress`，每u已知事件均值再u等权（同动作0保留），两个组2020连续前向名义均>=0才支持继续；年度/2023视图、所有label状态/未知动作差异全部报，不将known-only指标当现金或全机会价值。未知不填0，正常open close mark与真实缺价stale/无法辨识执行分离。

任一名义收益/DD/CI/held门不支持，则停止固定包不救参数；名义通过但差异未决能翻转只给unknown。任何通过也只有进一步研究资格，不自动晋级、不加注、不宣称达到完整goal。

## 实现预算、复核与保存

093只准备既有X的ID映射；09412fit/644056；0958cash共享唯一native SQL；096实际后一次独立全面核。预算：准备0SQL/模型0SQL/现金1SQL/独审0新SQL，0新label/行情下载/旧金融重跑/大DB-H5hash/重新tensor资格。只测试新event_id接线、共享missing/RFF181、fold无泄漏、下游新schema；既有071成熟/权重与070报价/现金定义接受引用，不重复旧suite。

不保存巨大重复181列头缓存；保存旧纯X与当前common/标签的精确引用、全训练身份/权重/scaler、一次W/b、每个model/portable系数/标准方程、main与held预测、所有状态/年度/family含零/8完整逐笔现金/费用暴露/集中/unknown/零价情景/CI/门。头矩阵可由这些输入确定性便宜重建，独审核全模型与预测。旧raw DB/OHLC不复制进AI资产；新产物显式声明角色。

源码/新tests/最小具体manifest/命令freeze→一次有限code preflight→root精确授权每phase fresh output唯一actual，失败保存先报root不自动修复重跑；不向用户重复询问已授权研究权限。实际后独立agent完整review数据、模型、资金、置信度与bug。

## 反思

开始是否新增按本实验收益调参过拟合：否，当前没有本桥接成绩，W/b/窗口/目标/风险单点冻结；但先前DAY失败和多轮历史曝光是实质负先验，不能称新盲OOS。继续价值有，限一次已固定经济目标中的时间位置对照；若只是用更多容量救旧DAY应否决。新增/修改/删除交易参数0，新增共同背景桥接明确181项（非旧139），金融指标当前N/A。新actual尚未授权，goal active未达成。
