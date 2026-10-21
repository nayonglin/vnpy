# Stage139：EMA日线源的研究级继承与规范化边界

line_id=futures_trend_triple_screen；2026-10-18 10:02 CST；root裁决。新增策略参数/回测/训练0，绩效全部N/A；非重要突破。

本线与已接受A_OFF继续使用同一冻结原合约DB（SHA273f0bc18de3070e4e085e4d6585fba71d6e1bb1256e3c7fb5adfc6532836a54），不替换行情。138确认116394行/533合约/1786日，OHLCV完整且唯一合法，实际carry由native缺日后生成而非这16个DB缺失键。0134500 exact-key资格不外推；后续通过一次独立新审查，明确按“已接受基准同源继承＋无损规范化＋有限跨源样本”接受研究级日线输入，不声称116394行均重聚分钟或全市场独立价格认证，不因此授予生产资格。

保留原厂商零V记录，不新建按零V删bar、补价、前向填充、拼接或调整价格规则。也不以同合约最后一条是否存在未来后继而事后筛掉某日交易机会。既有缺session按124/127重暖，源/价格置信度的继承限制公开保留；遇真实异常只报告，不默修以求过门。

141作者仅做一次规范化导出：DB单次bytes读取且SHA核对，从该bytes的sqlite deserialize只读query_only快照查询原027区间/真实metadata合约，导出date,vt_symbol,open,high,low,close,volume七列CSV（浮点17位round-trip）和精确keys文件；绑定原A_OFF参数metadata、原calendar、原DB/producer与138证据。验证行数/唯一性/真实合约/合法OHLCV/日期与原schema；不构建特征/账户、不复制全history进Git、不重hash7663旧源。输出outputs/stage141_ema_daily_normalized_source/，候选manifest保持pending，不自签资格；导出是可逆低风险数据工作，只做有意义的实际一致性检查，不写镜像实现单元测试或旧suite。

随后142独立数据审查（另派，非141作者）一次验证新CSV/keys与同源DB逐值无损、源级边界、有限原CSV样本，真正签研究级exact-key qualifier。独立资格后才调用127 load_bound_daily_csv/build_ema_rows一次生成固定13/26 feature cache；该步骤可由142在已接受model源上执行，另以有限标量复算核实际接合，不重复旧suite。features仅序列化标量列/一个source_ref，source_bindings及116394-key集合只在manifest中保存一份，不能把全keys嵌进每个feature行。无新公式/参数/金融readiness。

execution_tick在u冻结已知D有效规则，lc的20变更于2024-12-06已公开，u12/17可知D12/18的20；原风险/成本tick不改。原GFEX直连400 timeout，依据交易所署名337号原文的南华转发（发布时间12/6 16:56:08）：https://www.nanhua.net/news/2024/12/b0c7febb-514a-422c-8b9c-386f640b37a1.html?updatetime=short 。这只是PIT时点接合，不是新alpha。其余规则沿原effective_pricetick，未来实际输入须绑定规则源SHA及公告证据。

开始/结束新增过拟合：否，来源、全量零V及无损规则在未知EMA收益前固定；继续价值：是，以可说明的同源数据置信度推进真实实验，停止无限逐日重资格。目标active未达成，production_qualified=false。
