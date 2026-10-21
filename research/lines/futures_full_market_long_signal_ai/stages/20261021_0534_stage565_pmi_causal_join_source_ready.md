# Stage565：PMI 原公告到完整 source-u 的因果连接器已就绪

- line_id：`futures_full_market_long_signal_ai`；时间：2026-10-21 05:34 CST；day；非重要突破。
- 阶段为564冻结协议的来源连接实现，**尚未实际运行**，不是训练/资金回测。root唯一执行actual。
- 开始/结束过拟合反思：本次未按新收益调参，**否**；同史长期自适应选题风险仍**是且高**。继续价值：**是**，把已验源的164双值月变成真正当时可用的状态才能检验新信息；尚无盈利优势。

## 564 收益前问题与最小输入

564原问题是冻结COMMON52后，NO/FG月公共调查状态能否超过同支持同权重的残差常数校准，跨期跨family改善 `score>0` 参与。B/C未来各自用原538 mature缓存、原sample_weight/Ahat等聚合报告，>=36有效成熟报告月才允许fit；0.25N止损、母域98产品/95family、完整正负分child与正式版隔离不变。**565只做时钟连接，不读成熟训练或表现，不以83/119来源上限冒充训练数。**

只读564绑定的三份小源：561 `article_extracts.json`（704417B）、562 `acceptance_summary.json`（6239B）、已验538 `calendar.json`（89395B、5587个source日期）。不读230raw、SQL、行情、旧COMMON、母/child/训练或资金曲线，不新增GET。互联网/GitHub调研与判断沿用543/548—563真实来源及AKShare维护者原码结论，本轮没有新增外部信息或借用第三方重印补缺。

source-u统一采用既有484 `event_clocks`的 **15:15 Asia/Shanghai** 研究界（原实现68—71行；288—289行已声明conditional）。该约定覆盖常规六所共同完成的信息时刻，不宣称已核齐全史特殊延时/停市或原网页first-vintage，亦不猜夜盘00点归日。

## 精确连接政策

- minute署时的公开上界=打印分钟结束（+1分钟）；用 `bisect_right` 找第一个 **close严格大于upper** 的source-u。09:30公告可影响同日15:15形成的u；15:14公告上界15:15与close相等，必须移至下一u。
- D是原日历 `u_index+1`，不是公历日期+1；周末/节假日自然跳到下一已有session。显式publication_date只给次日00点界；成文proxy/unknown不能激活。
- 所有URL保留各自激活事件；当前参考月为已经激活版本的最大report_month，后来的旧月副本不能盖过新月。不得从future未激活版本提前取值。
- 完整pair必须来自**同一原文章版本**；NO-only和FG-only跨URL不能凑成pair。当前月已激活版本的已知数值或原字段有冲突时missing，不平均、不挑最好结果。当前月存在完整同值pair时保留其own可得界。
- 更高参考月已激活但没有完整pair，立即清掉前月。仅允许参考月m及m+1使用该报告，m+2首个u起强制missing，防完全缺原月时无限携旧。过期规则由已知参考月与事前约定决定，不用未来报价或后月滚动行。
- 只生成全5587日历行，不展开每日×98伪造宏观样本。下游merge所有母/child保留，macro_available=0时精确原A fallback，不能dropna删母域。

## 新实现、有限检查与接口

新增 `tools/stage565_pmi_causal_join.py`，10405B / SHA256 **`d543465dfe30a0330826192eec17011d319e8601248eb34f88948677a7cc35e1`**。协议564 SHA **`38ccfa3add609a40c969eeb4e16d625fcf91d09b853417a1a3b7fe2f2c650cb6`**。

纯小边界检查覆盖7个必要谓词：严格等upper转下一u、早盘到同日并D下一source日、周末到下一已有u、m+2过期、新不完整清旧、旧副本不盖新、跨URL不能拼pair。未造大测试套件、未运行真实输入连接，`source_check/source_ready.json` 已冻结实现和协议。

root唯一actual CLI：

```sh
.py311/bin/python research/lines/futures_full_market_long_signal_ai/tools/stage565_pmi_causal_join.py --protocol research/lines/futures_full_market_long_signal_ai/outputs/stage564_pmi_incremental_protocol/protocol.json --output research/lines/futures_full_market_long_signal_ai/outputs/stage565_pmi_causal_join/actual_run1
```

输出 `calendar_u_macro.csv.gz` 固定10列：`u_index,u_date,macro_available,report_month,NO,FG,reason,pair_source_id,publication_upper,eligible_u_index`；u_index原日历下标，缺值留空。`source_months.json` 保留201月逐版本事件/激活/D/有效u统计和未解析身份，另有summary/terminal/manifest及绑定。summary截点统计仍只计因果来源支持，**不作成熟训练数**。568独审已收到代码和接口，将只针对新join/后续567报告/头/完整选取，不重审230raw或旧52模型。

## 参数、财务与后续

当前实际GET/fit/cash/SQL均0；累计仍523fit/278完成cash和1旧partial。新增来源连接规则实现，已生效策略参数/回测结果新增修改删除均0；期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率全部 **N/A**。

后续root一次actual565，小摘要结论和绑定确认后直接接567固定增量实验，不反复重跑旧源、旧A、旧资金或为小元数据无限修补。未达最低支持则0fit关闭精确包，不降36门槛。完整高收益低回撤、全市场高质量long与极窄损加注目标未完成，不改生产/CTP、LINE/registry、Git或其他研究线。

## 05:35 CST 追加：root 唯一 actual565 已完成

更正阶段前半的准备状态：root随后已唯一执行565，**actual_run1/terminal.json为 completed / exit0**，耗时 **0.087921416秒**。本agent只读取该小terminal、summary和manifest链接补录，未重读来源CSV/230raw、未重跑连接或GET。

全 **5587条source日历行** 保持，**3319条u状态可用**，对应 **164个独立参考报告月**；其他行：无已激活报告1235、不完整pair678、参考月过期/未来333、已知来源值冲突22。最后22行继承2011Oct总体与小型企业词面误入的保守null限制，不把它升级为官方总体矛盾；缺值行均为下游精确A fallback，不删母/child。

因果来源截点支持为：2020-01-01前 **83个来源报告月/1668个u**；2023-01-01前 **118个来源报告月/2396个u**。这已不同于先前119个仅声明分钟上界的来源上限，说明周末/完整u映射等时序不能省略；**83/118仍没有连接标签成熟或训练权重，不是最终成熟训练月数**。565训练行读取0、mature_label_join_performed=false。

固定接口已落：`calendar_u_macro.csv.gz` **31961B** / SHA256 `b3d5c18ab3d784092b9ada8aea15105de60d8e12db1242568de92ecfd12f5890`；`source_months.json` **170425B** / SHA256 `572a1e1ec8b96b8630c666ecd961157b80ee0d27c09bb71e83e5dd2af2b012f2`。root已通知567消费此接口；568等待567终态，对新join+报告/模型/完整选择做**同一轮独立审查**，不另开重复join审。当前不能提前宣称全面独审通过。

实际新增 **fit/cash/SQL/GET均0**，累计523fit/278完成cash和1旧partial不变。策略参数/金融结果新增修改删除仍0，权益/收益/DD/Sharpe/滑点/次数/胜率全N/A。运行前后未按收益调参，历史择题风险仍在；完成真正因果连接有继续固定增量检验的价值，仍没有高收益低回撤或加注资格结论。
