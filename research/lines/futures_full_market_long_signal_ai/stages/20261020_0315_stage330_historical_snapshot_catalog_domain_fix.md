# Stage330：历史快照完整目录域修复

时间2026-10-20 03:15（Asia/Shanghai）；所属`futures_full_market_long_signal_ai`；非重要突破。root授权对327真实接线失败作必要工程修复，禁止alpha/参数救援。326原工具、test/sourcebundle和327失败现场全部保留，不改LINE/registry。新330作者0cache/econ/SQL/fit/cash；只有一个新domain tiny，不重跑旧warmup/caller/320组。

## 失败原因与最小修复

327 actual exit1/0.370523834秒，错误`original complete98/95 domain mismatch`，已load cache1，经济投影0、同日dataSELECT0，源前后stat相同。原004小roster有98产品/95family，但DCE.S的source_observation_rows、qualified_candidate_rows、contracts_with_candidates全0；原004 manifest明确products_with_candidates97/contracts_with_candidates9520。原132cache有9520真实观测epoch，不应被要求覆盖无源目录产品。**这是326新adapter把目录域与有数据域混同的错误，原静态core0未抓住，不能解释成旧模型/源丢失。**

新`stage330_historical_snapshot_domain.py`沿326原链，只新增`catalog_domain(epochs,roster)`并替换loader域门：roster必须恰98唯一产品/95family；contracts_with_candidates>0的预期有源产品恰97，其集合必须等于cache实际产品集；母域products始终完整roster98，receipt显式记录missing_native_products（既有小metadata为DCE.S）。missing/unexpected observed仍报错，不以subset任意放松，不能drop缺源母行。新增auth与source_receipt的schema/path改为330版，source bundle自闭合。

AST对比确认326所有原纯数学/暖机/assemble及辅助函数不变，唯一原函数变化是`load_snapshot`（域门/诊断/身份）；新增函数只有`catalog_domain`。`assemble_snapshot`原已能保留空产品，本次不改。

同日SQL/cache集合相等门仍正确：原132 `read_native_once`仅按2010-01-01至source calendar末日筛日期，无quality/volume过滤；finish保存全部rows，invalid为accepted/valid mask而非drop，persist拼接全部store。固定2026-10-16的同日SQL就是原cache全rows的一部分；004小counts为source_observation_rows1552456/rejected_rows0，与cache1552456一致。因此目录98/observed97与当日allrows/eligible是不同边界，不需再改当日核对，也未新增SQL/epochs-member读取。

## 唯一新tiny与实际边界

新test只有`test_catalog_empty_product_survives_and_native_domain_must_match`一个方法，先RED因330未实现，最终exit0/1test/0.367秒。合成98/95目录中97有源、DCE.S无源；用326原pure assemble的副本及真实320纯函数构造完整98母行，DCE.S候选0/anchor空/no_accepted_observation保留；额外unexpected source、缺少observed source、删掉空目录产品都必须报错。没有实际价格、NPZ、经济投影、SQL或现金。

[新bundle](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage330_historical_snapshot_domain/implementation/source_bundle.json)；[新授权模板](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage330_historical_snapshot_domain/implementation/authorization_template.json)（authorized=False）；[新tiny终态](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage330_historical_snapshot_domain/implementation/fixture_terminal.json)。API仍`load_snapshot(auth,*,output,core=None)`，rootwrapper先载325再注入`caller._components().core`避免跨dynamic module的WilderState类身份不一致。下一次只由root另签精确授权，在fresh输出额外cache1/econ1/daySELECT1，保留前次已消耗cache1与失败终态，不伪装零尝试。

原缓存N/run/lastclose、run头20TR seed、21bar窗口/lowqueue、missing不carry、原26/52/model/scaler与原156/157选择全不变。历史development_only=True、frozen_at=None；D/完成clock无proof仍unknown，无T0/forward或真实D金融推进。新源交328只审delta，不复跑旧suite或重做大源资格。

新增/修改/删除策略参数和金融结果均0；权益/收益/DD/Sharpe/费用滑点/胜率N/A。沿324已核原理，无新金融命题不重复网页/GitHub。开始/结束均判断无新增过拟合搜索；修复有价值在于完成既有因果接线，不能以修复名义救alpha或扩资格循环。
