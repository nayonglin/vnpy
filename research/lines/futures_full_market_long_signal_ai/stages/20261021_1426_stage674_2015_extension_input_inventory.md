# Stage674：2015资金曲线延展输入有界盘点

- line_id：`futures_full_market_long_signal_ai`，2026-10-21 14:26 CST；非重要突破，仅补固定区间的材料盘点。先读registry该行；不改LINE、registry、旧代码或其他研究线。
- 本分工新增fit、cash、预测、标签、SQL、下载均0；未读取任何大CSV或NPZ payload，未hash大文件。当前绑定已接受数据快照截止2026-10-16，不能把本快照写成截至10月21日。
- 开始/结束是否新增过拟合：否，只核固定COMMON52+K材料范围、不看收益挑选起点/参数。原同史研究与非PIT认证风险仍存在。继续价值：是，可避免为2015延展重复取源/打标签；无须为身份相同的2020/2023段重新训练和预测。

## 结论与缺口

**现有native缓存按已接受元数据和冻结源码覆盖完整2010起原生源域，2015–2019现金无需新增SQL。** Stage132的`read_native_once`查询2010-01-01至原日历末日，完整断言1,552,456行、9,520 epoch；`persist_native_cache`拼接全部series，未按2020裁剪。157实际恢复同一缓存，其source receipt再次记全部行数/epoch及SQL=0。现有数据库bytes/inode/mtime_ns/WAL/SHM与缓存metadata当前逐字段匹配。

这不是一次新逐bar审计：未打开NPZ payload；阶段总结保留`large_payload_reads=0`。没有发现补native的必要，不应先下载或新查SQL。实际延展在读取缓存时仍应验证准确SHA、完整calendar索引及所需早期epoch/日范围，失败保留原尝试。

129协议scope是2010-01-04至2026-10-16、399,252完整母行、98产品/95家族/6所；actions/common/mothers绑定同一完整域，1,552,456原生子行均映射到母日，孤儿/域外/2010前行均0。因此材料域支持2010–2014成熟训练与2015起前向；本盘点未算2015 cutoff成熟样本数，不能声称已经验证该折样本充足或跑出效果。

130现成main 2020模型训练247,795行、前向366,634子行/71,344母行（2020≤u<2023）；main 2023模型训练445,475行、前向600,106子行/89,670母行（2023≤u≤2026-10-16）。这两段现成分数直接复用；现成六折中没有2015 cutoff模型/2015–2019前向分数。2015不能用2020模型倒打，因为2020模型训练已包含2015–2019标签。

旧156实际入口硬限2020起161,014母行，K边界只对旧forward分数遇到的epoch产生，不可当作全历史K表。延展需使用相同`calendar_boundary`、`D<K`先过滤后argmax、ordinary/F家族优先级，给2015–2019新前向域产生边界。旧157的authorization、四户、窗口和父行数量同样锁旧范围，宜新延展入口复用纯函数，不修改已接受157。

## 精确绑定

绝对路径、完整bytes/SHA、small manifest当次hash、小模型/scaler当次hash和所有引用字段保存于：

- `outputs/stage674_2015_extension_inventory/summary.json`：22,353 bytes，SHA `18a5b35436006f70f10cad15589b0840780320d5d6454531a0d62c2bf407717a`。
- 129 `actual_run1/actions.csv.gz`：334,909,637 bytes，SHA `b5b76bd670e9bd6240ea198da4f854cee61ba5f72fd6762f071345a4c0824e7c`。
- 129 `actual_run1/common26.npz`：146,877,351 bytes，SHA `725643d1643a0ab59ce95f9206fbc90333ee2dea264bd8f392076e45a0a83c18`。
- 129 `actual_run1/mothers.csv.gz`：19,551,936 bytes，SHA `4392e66061d77936aab4ece8aa414291f80da084a0cca0df7ca92a922da48130`。
- 130 `actual_run1/child_scores.csv.gz`：124,127,126 bytes，SHA `e94b4d3d8d076edc7d76af4f219fc2cfc57f52b5e7eafeb8d4dedf98dbae8457`。
- 132 `cash_only1/native_store_cache.json`：948 bytes，SHA `130e340e8c91daadda7a6d9c5dc275c21c222114cfa19ca484bd89dd0eca2685`。
- 132 `cash_only1/native_store_cache.npz`：110,273,488 bytes，SHA `d2976090f9353b071eb62e28eca843b96b4a33a33a4233a508049cfeab9360b7`。

上列大数据SHA沿已接受manifest继承，仅核存在与bytes，未重新hash。全部均在本研究线`outputs/`下；完整绝对路径见summary。日历绑定仍是原`futures_trend_rollover_shape_same_volume/outputs/stage265_deep_daily/rqalpha/trading_dates.npy`，44,824 bytes，SHA `57dd7f539d1cdbefb528978a6c7bd79b118790f933ce63c37b10747b999f9585`；本分工只读其引用、不改其他线。

COMMON26字段及52设计保存summary：11自身价格/量项、13期限结构项及stress_u_cost_R/low20_distance_R；52=26训练统计标准化有限值＋26原nonfinite标记。不能称无缺失模型。动作ID、母ID、原`u_index`、actual/reference/anchor epoch均须保留，不把母日4074索引当作原源日历5587索引。

native缓存结构由persist源码确定：`epochs`、`offsets`、按全部epoch拼接的`days/values/accepted/valid/N/low20/run`；days是原calendar索引，values为OHLCV，指标已有原生同epoch连续性处理。小缓存metadata自身没有日期min/max，日期覆盖结论来自完整query/persist路径、129/128 scope与157恢复receipt，未冒称读取到payload日期统计。

## 调用位置与最小延展

1. `stage130_contract_choice_fit.py:60`的`fold_slices`保留成熟条件：原u可行动、closed_complete、u和label_known_date严格小于cutoff、stress目标有限；同原权重/Ridge/52设计。只需main cutoff2015一折，预测2015≤u<2020，再合并原130 main2020/2023分数。
2. `stage156_voluntary_choices.py:40`纯`calendar_boundary`和`:74`选择函数可复用算法；旧actual`:237`固定2020起与`:105`旧cutoff检查需由新入口明确适配，不改原文件。
3. `stage132_contract_choice_review.py:744`的`restore_native_cache`恢复准确缓存，`:735`是全部epoch持久化；`:183`是完整SQL来源定义。
4. `stage148_fx_cash.py:85`的`CachedMarket`提供`bar/indicator`不变131接口；157`:282`恢复、`:284`包装、`:312`调用`kernel.run_cash_account`。157的`make_voluntary_signals`/`apply_boundaries`继续只改私有signal生命周期副本，并保留source/voluntary/effective lineage。
5. 两种原成本各跑一条2015起连续资金账户时，应保留2015持仓进入2020；已有2020独立冷启动账本只能作原参考，不能把两段权益简单拼接当连续资金曲线。其他执行参数不变。

最小补native方案：当前无需补充。仅在准确缓存校验或实际必要早期覆盖检查失败时，保留失败，并另冻来自同一immutable数据库的最小重建授权；不自动下载、换源或重跑标签。

外网/GitHub调研由root统一执行，本分工只盘点已有接受材料，未引入新外部alpha假设。新增/修改/删除策略参数0，新增/修改/删除回测结果0；权益、收益、回撤、Sharpe、滑点、交易次数、胜率N/A。不代表PIT/OOS认证、正式晋级或加注资格。
