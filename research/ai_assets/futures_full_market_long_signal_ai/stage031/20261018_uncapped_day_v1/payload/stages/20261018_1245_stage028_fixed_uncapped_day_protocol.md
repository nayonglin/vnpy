# Stage028：全市场DAY去4R顶单项政策协议

line_id=`futures_full_market_long_signal_ai`；2026-10-18 12:45 CST，实际冻结时间自动记录。用户完整目标不变：全市场高质量long、更高净收益低回撤，随后独立验证极窄止损与加注。上一goal轮023/024/025/026产生新矩阵、108fit和独审反证，归档完成，分类progress；原目标仍未完成。当前分支codex/ai-training-data-expansion，沿原checkout，不新branch/worktree。

## 一次固定问题与范围

采用Stage027预结果设计：同一全feature_ready母体、同一D.open入场F、R=.25ATR(u)、SL=F−R、DAY退出，A保留PT=F+4R，B唯一删除PT。是否保留的收盘右尾能抵偿已触PT却回吐和双触达损失？只做独立政策反证，不使用024任何模型/score/mask/排序，不训练，不改horizon/stop/资金/品种池，不重跑旧模型或正式策略，不把它冒充新AI信息。

母体399252行、194709 ready/194168已识别/541未知沿009/011。所有ready机会两边均尝试相同OPEN；全表包括无观察/未就绪/缺D/删失原状态。B与配对只在原identified共同子集评价；未知不填0、不标失败，不按未来数据筛输入。沿六所全部历史产品/真实epoch，不限旧19或正式AI池。数据截止2026-10-16，source grid2010起4074日。

本轮复用007 protocol、009 manifest/feature-label/audit和011接受收据，核小文件与52MB/14MB源SHA；不重hash378MB DB、不SQL/下载/分钟盘点。audit覆盖原observed行，不能错假定只194709ready；按event_id精确对齐原表并验证u/epoch/D/状态，不把无观察原表行当缺失失败。输入只用于诊断policy payoff，不进AI。旧011仅接受固定理想代理，不是B新政策/经济/生产资格；B须本轮独立复算后才能接受计算。

## 路径、精确配对与数值

沿原连续理想价格模型，不声称跳价/tick/排队/费用/限价或真实订单。A完全继承原gross/净区间，不重新用归一化坐标判断触边。B在原state为stop_only或double_touch_interval时gross=-1（原价格已证明D内触SL），day_close继承原gross单值（paired精确0），profit_only的B gross=(D.close−F)/R。按原state决策，不把原价先归一再重判、不加epsilon。对audit原价有限/正R/原低高与Dclose合法、SL/PT/R/原state对应作有界适配验证；若CSV数值微小误差，不能改经济分支，应以原state合同为准并报告误差。仅比较数值一致性可用绝对1e-9/相对1e-12，绝不用于触价或选门。

同路径B−A：stop_only/day_close=[0,0]；profit_only=[closeR−4,closeR−4]；double_touch_interval=[−5,0]；unknown保持unknown。即便本情形的独立界相减得到相同端点，也应依据共享路径证明，不能泛化粗相减方法。双触达A先SL则差0，A先PT则B其后SL、差−5。B已识别结果在连续模型下为单值，不代表真实金融标签无歧义。

两边每个identified事件共同fill，基础研究成本0.2R；stress1R只同mask各再减.8R。配对成本精确取消，不能把节省交易成本当收益。无已识别日为NaN；未就绪和未知不算0，也不以他们的Dclose作评价。无事后机会挑选/重加权。

逐identified事件保存归一A/B gross/net/stress、paired区间、tail_gain=max(closeR−4,0)仅profit_only、giveback=min(closeR−4,0)仅profit_only、ambiguous penalty[−5,0]。三部分逐事件/逐日相加必须等于paired。只用B实际DAY收盘gross>4统计新兑现右尾，禁止D.high/MFE当可兑现收益。导出无绝对OHLC/F/SL/PT/ATR/volume，原始audit不复制入Git。

## 固定统计与11个继续门

日期等权、各u共同identified机会等权；全source grid保留无评价日NaN。报告2010+全段、2020+primary、2010..2026逐年以及sha256(family_id)%2两组异质性和combined（无训练，不能称family训练外留出）。family沿exchange.product去_F，F与原族不分组泄漏。报告全ready与identified/未知覆盖、填数/原状态、>4尾部事件/日期/家族及给回损失。期末权益/总收益/最大回撤/Sharpe/真实总滑点/成交数/真实胜率均N/A，不将事件R累加成账户。

主main两个期间沿60源交易日moving-block bootstrap、2000次、seed20261018、列共用index；固定政策历史不确定性，不包含研究择题/真实成交/账户。B是单值，但共同A/B对照仍有6000原双触达区间；识别界和CI分别报告。

11门全部通过才支持该单项继续：primary B基础净lower的95%CI下端>0；primary paired_lower的95%CI下端>0；primary B同mask1R压力均值>0；全2010 B基础净lower均值>0；全2010 paired_lower均值>0；两个family组primary paired_lower均值各>0（2门）；2020—25完整6年中>=4年paired_lower均值>0；2026部分年B基础净lower>0；primary新兑现gross>4尾部支持>=60个u日且>=8family（2门）。缺失/NaN视未通过。选择11门不是从新B结果反推，没有阈值/horizon搜索。A作为匹配历史政策，不是正式版金融A/B/C。

## 实现、独审与停止

029仅新隔离代码/必要4—5行为tests，先RED→GREEN，实际只一次全表政策计算，0fit/SQL/金融。每个实际过程保存工具句柄/终态/源SHA/inputs，不因观察超时重启；输入错误时保留失败，必要适配不改策略。030独立审查共享路径证明和作者源、全事件/日/annual/两CI/11门，不导入作者计算功能，不重新训练/跑旧回测，不复制raw。必要决策产物显式role/required，root归档并更新LINE/registry。常规负结果不追加根memory/back_log。

失败只否决本全ready OPEN/0.25ATR/DAY去顶包，不否定多日趋势/全市场AI，不扫描5R/8R、20/60日、SL、年份/品种/过滤或成本。正结果仅支持当前理想政策/预算下去顶的继续价值，不支持AI预测、真实净收益/DD或窄损加注；不得拿024失败模型套新目标重训或重评救参。DAY/隔夜/组合资金错配仍在，不将去顶当完整解决标签问题。

开始新增按结果救参过拟合：否；反复观察历史的选择风险有。继续价值：是，限一次低成本、直接可证伪的经济结构问题。当前新fit/金融/SQL/下载0，重要突破否，新增本政策参数PT disabled；旧正式参数与成绩修改/删除0。结果后另由root反思与决定，不提前宣称完成目标。

实际调研Potters/Bouchaud https://arxiv.org/abs/physics/0508104 和Backtrader作者源码 https://github.com/mementum/backtrader/blob/master/backtrader/brokers/bbroker.py 。论文说明正偏/低胜率可由风格而非alpha产生，broker展示stop穿价/触价分支并不替本模型提供成交资格；判断需同时看尾部、回吐、成本和稳定性，不把去顶天然视为改善。未安装/运行外部代码。
