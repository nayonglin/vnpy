# Stage607：WASDE同MY修订报告层检验——接口准备，尚未冻结/实现/actual

- 时间：2026-10-21 08:06（Asia/Shanghai）；`futures_full_market_long_signal_ai`。先读registry/604及旧285/130源码、小manifest和539独审，当前0fit/0cash；累计547fit/286完成cash及1旧partial不变。非重要突破、金融指标全部N/A。
- 任务边界：本次只探schema/已有绑定与readiness，不读新收益、不读全训练标签或OOS标签，不读取COMMON/native/WASDE原件，不重hash旧大输入。仅7个gzip CSV表头探读，未解析任一收益行。没有创建长期模型代码、可训练表、模型或daily join。
- 调研判断沿604真实官方/研究原作者/维护者核验，当前只对既有本地接口核，不追加网络择题。原同MY Production信息区别旧World stocks/use level；科学设计须控制季节与覆盖，不能再复制旧2scalar日复制方案。

## 最小可复用来源

首选已经539独审的538投影，不读原COMMON146,877,351B/原actions334,909,637B。两个main `outputs/stage538_sector_residual_fit/actual_run1/folds/main/{2020-01-01,2023-01-01}/train_compact.csv.gz` 分别29,438,246B与50,602,127B；含原成熟child identity、Y、labelknown、sample_weight及冻结52分数Ahat。原130训练行247,795/445,475、源u日2,411/3,139，family69/77；539已从原raw26/portable/scaler独立重算Ahat，最大差3.55e-15且权重复算通过。**DCE.C新规则下实际支持数尚未读取，不以旧结果填值。**

原两套portable model为2794B/2787B，scaler4691B/4680B，均在130 `folds/main/<cutoff>/`，精确路径/bytes/既存SHA见 `interface_inventory.json`。设计仍原26列标准化＋26非finite missing flags，52coef与原intercept不变；权重/归一只audit，不重训52。26原COMMON列也在inventory完整保存；未来本候选无需读原26数组。

OOS最小完整已验收源为538 `forward_base_compact.csv.gz` 142,867,173B，包含原score、child/mother/u/实际合约、原scope/cutoff与label_state/参与状态/Y/known；旧B_offset/C_offset一律丢弃。原全域1,933,480行，main/held各966,740；旧285 terminal已记录main全部DCE.C为9,640child，含非正分，607目前不重数/不看Y。gzip没有按产品随机索引，未来只能**一次顺序解压、只保留main DCE.C**，这不等于重算全市场政策。其他97产品仍原A fallback，报告试验不缩改母域。

Calendar使用538 `calendar.json` 89,395B/5587日。报告层不需要mothers；未来若门过后另获完整选择资格，可用538 `mothers_forward.csv.gz` 7,903,291B/161,014母体，暂不读取。原130 `child_scores.csv.gz` 124,127,126B没有Y，结合actions反而更多IO。

旧285小文件不能替代完整新对象：`train_offset_2020/2023.csv.gz` 375,550/544,384B虽有w/Y/s52，但已按旧World level可用域筛选；`forward_corn_delta.csv.gz` 749,855B虽保留9640 Corn old_score/身份，却没有Y/known标签。它们最多小对照，不能把旧可用样本域默认为新Production域。

## 605冻结前实质接口建议

Root已改拟定目标为：每u全部已知mature eligible Corn child残差Y−Ahat等权，再报告内u等权，最终报告等权；train/test统一，不重建全局持仓区间权重。原sample_weight只audit。headtrain要求MY_start+1 < cutoff_year，且u/labelknown < cutoff；eval用原部署fold日期、known<=END，未知/未成熟计数保留。此设计在看新Y前更改，未依据新成绩选择权重。

需要由605明确月份均值/中心化x的尺度、未见月fallback、最小支持、MY分组验证与固定门，然后才能写607模型。训练Ahat来自该cutoff原52的训练全集，不能把头的MY交叉验证冒称旧52也完全OOS；真实前向旧score严格来自原部署cutoff。若先做报告层门，失败就不做full-policy选择/现金，物理一次target过滤文件读取不称全政策回放。

未来最小IO：小605+602观察grid/603审查+原模型/scaler+538manifest/calendar；两main compact各一次Corn过滤、forward compact一次main Corn过滤。大表只沿已验收binding核stat/size及读取前后稳定，不额外完整hash，不触raw/SQL/COMMON/native。

## 反思与下一步

新增/修改/删除策略参数与金融结果0；期末权益/收益/DD/Sharpe/滑点/交易数/胜率/CI均N/A。开始/结束本轮按收益调参过拟合：否，未看新Y；长期同史择题风险仍高。继续价值：是，仅先冻结能反证季节/覆盖混杂的单项报告检验；不扩作物、窗口、系数或原门。等待root605冻结才实现，同607阶段后续追加，不改LINE/registry。

## 2026-10-21 08:16 605冻结后实现与source-ready（尚未actual）

完整读取605协议SHA `5cc338a105bb8229456bd64a9c6a250b34ab3875fcdc52636f39419c9c29783d` 后新增唯一隔离607脚本与6行为fixture，未改旧工具。按test-driven-development先RED6（6断言失败/0error），纯核GREEN6，再runner完成后同6项GREEN（.001秒）；不扩旧suite。合成覆盖DST可用时刻/不跨月carry/边界MY、child不等数但u等权、月份中心化且报告权重sum1的Ridge手算、未见月两臂A/零方差unsupported、成熟未知不0、五主MY逐组门。合成每次GREEN只含2个B均值拟合＋1个C solve，不计真实fit。

实现固定2B月份均值＋最多2C scalar，原52/尺度/阈值/lag不动；三compacts各一次顺序过滤保留Corn全部正负/状态，原小cache供608独审。不读COMMON/native/actions/58raw，不hash旧大表。训练MY完整年条件、原成熟时钟、报告等权、同month中心/全局尺度、λ1、原两部署era、5个primaryMY门与描述MY bootstrap2000/seed20261021全部按605；May–Apr预测发布周期与Sep–Aug实际营销年明确区分。数据未知、源缺口、V2、无已知target、边界MY与未见月份分别披露。失败不重选、不现金、不救参数。

源 `29071e66a041ca2a6965035e1b181e5f8517174ce106bb88387f7f9b9207f479`；fixture `711f0ccfbef661cfb352624f1108c7623f792659deeaaa3129bf783c2a92ab6d`；source_ready `698f974aed0039941e6b6da5fce50c2762a877ef71160946606046b479d87236`。绑定receipt及关键小输入，精确CLI已交root；作者真实Y读取/actual/fit/cash/SQL/下载/新金融指标仍0/N/A。root完整读源与608预审后唯一actual，本agent不启动。累计547/286及旧partial1未变。源准备通过不证明alpha；当前固定单项证伪仍值得，长期同史择题风险高。
