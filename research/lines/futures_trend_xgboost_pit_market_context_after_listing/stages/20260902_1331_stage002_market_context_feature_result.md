# Stage002 上市后PIT市场上下文特征结果

- line_id：`futures_trend_xgboost_pit_market_context_after_listing`
- 完成时间：2026-09-02 13:31 CST
- 决策：`stage002_market_context_features_pass_ready_for_ranker_preregistration`
- 是否重要突破：否；六项独立市场特征通过无标签技术门
- 策略回测/CTP/订单：`0/0/0`

## 技术结果

- 特征矩阵精确328行、43个月、6项；rank10/挑战者为43/285行，每月6至9行。
- 六项特征全部有限；rank10使用同一公式计算后逐位精确为0。
- 每项特征在285个挑战者上均有285个唯一值；总体标准差依次为`0.305611/0.265175/0.495441/0.530449/0.017642/0.291906`。
- 8个fold内每项特征均有非零挑战者值；最少Top9下跌日47，高于预注册20日门。
- 120日窗口、日期上界、future rows used=0、双跑和输入身份门全部通过。
- 未来标签列、未来损益列、sealed holdout文件读取0；训练、回测、CTP、订单均为0。

## 产物身份

- `market_context_feature_panel.csv` SHA256=`3d77c8d1d4d9f95612ca4d9c4e0db1df5bc88a58eb8b0a5968a1eaf6bc7fcaf0`
- `month_feature_audit.csv` SHA256=`673a92b8e4cd1e0de4f4a4868d524db1def5775190a80b604e125dead82bfdf9`
- `feature_diagnostics.csv` SHA256=`b32ac1116a608639e105691b71b7bced89ac554b0919745f2f5cd6aba7e02072`
- `stage002_summary.json` SHA256=`edd2c9e7b5d39811201242d6d8ffb2c5ff60413fa456fe755b833dc09f43912e`
- `artifact_manifest.json` SHA256=`ef60982092f42e127533bc82cf462f68ec1aa0cefd7ed294381c899a850656a5`
- 整线测试10项通过；Stage002没有训练或回测。

## 版本变更与回测记录

- 新增参数：六项冻结市场上下文公式、120日窗口、最少20个Top9下跌日。
- 修改参数：无。
- 删除参数：旧账户上下文的活动重叠和共同亏损率没有迁移到市场收益语义。
- 新增/修改/删除回测结果：均无。
- 期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率：均N/A。
- `back_log.md`未追加；无回测结果，不触发独立reviewer。

## 运行后反思

- 是否过拟合：本阶段**否**；没有读取标签，公式和门在结果前冻结。六项各自唯一不代表预测有效，只证明数据没有退化。
- 是否值得继续：**是，但只值得一次严格堆叠式月分组Ranker检验**。历史development数据已被多轮研究观察，下一阶段必须使用历史OOS的A排序、60日标签可得性purge和固定模型参数，禁止扫描。

