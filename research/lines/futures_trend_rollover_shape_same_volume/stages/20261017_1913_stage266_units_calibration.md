# Stage266 六所日线单位语义独立校准

- line_id：futures_trend_rollover_shape_same_volume；时间：2026-10-17 19:13 CST。
- 是否重要突破：否，是全市场清洗的固定输入合同，不是策略alpha突破。
- 范围：目标2010+，六所全部真实合约，含DCE月均价F；只读已有H5、restricted primitive metadata、官方规范表及4,041个旧天勤日CSV，不下载行情、不训练、不回测。
- 开始过拟合判断：否，没有按收益调规则；继续价值：是，必须消除差2倍数量和开收盘OI混淆。

## 交付与批准

输出 `outputs/stage266_clean_daily/unit_contract.json`，`cleaner_rule_approved=true`。只批准 pinned H5：四商品所2010–2019 V/closeOI×0.5，2020+×1；CFFEX全目标期×1，GFEX自2022上市×1。old/recent TQ原生单边×1；官方仅明确unit_regime可接受，unknown排除，DCE年度只作交叉证据而不进优先层。H5 open_interest仅收盘，不把前收OI冒充真openOI，缺失保持null。

合同SHA `2b9d41dffd094457843d791e5d9ca611f6878d569168b1d1c439f31099a3359c`。可执行隔离表 `stage266_units_quarantine.csv` SHA `6272c8a95ccaaa9ab44cc1150326a21c13e643b7a2a5a22cab7f5219953fdd66`，2,294唯一`EXCHANGE.PRODUCT.YYYYMM+trade_date`键，F的PRODUCT加`_F`；所有来源整键排除，无priority例外。

## 证据与判断

网上先查协会官方2020切换FAQ、INE官方2019问答、证监会2010股指材料、CFFEX交易细则、RQ官方字段文档与GitHub、天勤API。制度切换不等于任何历史包已改单位；INE英文历史段落有内在翻译矛盾，因此实际包脚注和固定文件重叠优先。文档链接、局限和中文解释在 `stage266_units_report.md`。

全10,547实际H5 dataset逐所/年及逐dataset审计：四商品所2010–2019共559,375正成交行，V/closeOI均有限整数偶数，516个商品dataset跨2020。2020后各所约一半量仓为奇数，CFFEX前后同样约一半奇数。未发现商品pre2020成片单边混段，但奇偶性本身不作为充分证明。

官方2010+959,576参考行，957,498共同正成交；已明确单位参考按规则转单边后V相等829,109、closeOI相等828,493；127,274共同正成交行官方单位unknown，不用于认证。DCE pre2020共同正成交实际175,905（H5同段所有正成交176,338，二者口径不同），70冲突键/55V/63OI，没有精确2倍或0.5倍异例，因此隔离而不猜分段。

旧天勤和RQ共773,959个共同正成交，其中pre2020四商品所4,211条（SHFE2499、INE366、DCE591、CZCE755）V全部RQ=2×TQ，非零closeOI全部同样，四价全同。2020+769,748共同成交中，RQ OI等同日TQ closeOI768,576、等openOI仅37,050，支持收盘时钟且不能伪造开盘OI。

官方数量冲突1,959参考行、旧TQ1,373参考行，合并2,294键：DCE1195、SHFE689、CFFEX359、INE48、CZCE3。P0=0限本合同；未知单位、无真实openOI和数量冲突已明确隔离/缺失策略。原生数值全部保留，未纠数或拼源。

## 文件与验证

- 工具：`tools/stage266_units_audit.py`、`tools/stage266_units_freeze.py`。
- 证据：`stage266_units_evidence.json`、`stage266_units_dataset_parity.json`、`stage266_units_exceptions.json`、`stage266_units_quarantine.csv`；均在同线 `outputs/stage266_clean_daily/`，前两工具可复现只读统计/合同生成。
- 只使用已验证无GLOBAL的primitive pickle；restricted Unpickler拒绝所有find_class/persistent引用；H5以只读模式打开。主库写入0、下载行情0、天勤订阅0、订单0、训练0、回测0。
- 新增/修改/删除策略参数无；权益、收益、回撤、Sharpe、滑点、交易数、胜率均不适用。
- 冻结后不再修改单位JSON/CSV；root读取合同进行一次全量清洗。
- 结束过拟合判断：否，固定来源和保守冲突排除未使用收益反馈。继续价值：是，进入全量清洗有价值；本次单位研究已完成，不再为少量差异无界追查。
