# Stage613：D日有效条件限价的接口设计（未实现、未actual）

- 时间：2026-10-21 08:34 CST；先读registry及609/610，所属全市场long-only研究线。当前只读小源码/manifest，0fit/0cash/SQL/行情/大cache读取；551fit/286完成cash及1旧partial不变。重要突破否，全部财务指标N/A。
- 609已关闭报告/MOY控制Production修订包，本阶段不救其数据/月份/头。610真实交易所/CME、vn.py/Backtrader/HftBacktest资料支持条件触达研究，不认证日线足量成交或经济上下界；本阶段沿其方法核，不重复网络。

**接口可最小隔离实现，但须等611冻结；当前不写策略或runner。** 复制原131 `run_cash_account`，保留原070/042纯函数。只给新entry增加612反解的理想触发计划，并把原循环拆开D事件；不修改market.bar或伪写Dopen，不叠加597赢家加仓。

原042为Qbuy(p)=t×ceil(max((1+b)p,p+n×t)/t)，base的b=.0001/n=1，stress的b=.0003/n=3。按root/612建议：L=同actual epoch的u.close，j=floor(L/t)，k*=min(floor(j/(1+b)),j−n)，F*=k*×t。先原Q(O)<=L则rawF=O开盘成交；否则等真实Dlow<=F*时按理想首触rawF*入场，仍用原execution_quantity(F*)/adverse_quote，要求原Q(F*)<=L；不是rawF=L后clip报价，也不改费用/滑点科目。缺tick可按原连续Q推F*=L/(1+b)，原tickized=false/未知保留，不造假tick；无合法正触发价和数值边界由611明确。SL0保持**原rawF−.25N**，不改为实际含滑点fill−.25N。最初rawF=L可能超限的草案已被此反解替代，尚未实现任何一版。

建议事件序为：①旧仓missing/force/reduce/gap按真实Dopen；②原Q(O)<=L的新开盘BUY；③旧仓及开盘新仓按各自边界触发日内stop；④等待单到F*理想BUY及自己的更低初损；⑤幸存仓Dclose估值、原canonical/20low/K/次u预算。旧missing只mark一次。原u occupied排除＋无add保证旧仓与新pending家族/actualepoch不重叠；共同预算在u冻结、无D总量新gate或资金再分时，跨家族③④记账先后不改变q、终日现金或同epoch gross。代码应断言此前提，而不把旧Dlow作为取消已执行开盘BUY的新经济条件。新盘中单的触发价高于其初损，连续首触全填模型内触发先于更低stop；真实跳价/排队/部分成交仍不识别。

u `reserve_capped`/共同缩放/生命周期与选择不变，C次u用C真实条件账户状态；不得用A未来预算。执行数量仍原own allocation只能减或cancel，不复用当天退出/未成交资金。不要在u新加F*可行性预过滤来释放预算。未触及D单到close失效；后继u照原C状态产生新预算。旧保护退出不硬截容量，原u-volume1%/往返cap与capacity unknown保留。旧actual与canonical anchor可不同，不能重添597曾发现的额外等式。

小manifest已定位157 accepted状态 `completed_with_metadata_continuation`/4OWN；原A四summary/daily/bootstrap复用、不回放。signals583263B、mothers19551936B（399252母体/98/95、161014 forward）、native cache110273488B仅未来actual一次恢复及原经济投影，0actions/COMMON/SQL。确切原路径/SHA及4A绑定在本目录 `interface_decision.json`；本次未读取这些大文件或A收益账。runner可薄改575的输入恢复、原157报告/pairedCI/固定gate，只替换cap审计为limit审计，无需通用引擎或多账户分支框架。

新增/修改/删除策略参数、脚本、金融结果均0；本轮只新增本stage和小interface JSON。未来候选若611冻结才实现独立kernel/runner与必要合成fixture，root唯一actual最多4C/0fit，不能以此设计签收益。开始/结束新增收益调参过拟合否；长期同史择题风险高。继续价值有条件是，仅一次精确条件报价的证伪；真实成交/保守经济界资格否。不扩分钟工程、不改LINE/registry/正式或生产。

## 2026-10-21 08:38 root接口收敛：不拆原D循环

根与独立审查确认原u新旧family/epoch分离、D独占预算及无重分/全局cash gate时旧仓和新单记账可交换。故上文事件阶段拆分仅为已废弃设计建议，最终将**保留原131旧仓完整先记账循环**，只在新entry解析处hook；原旧仓Dlow/close记账不声称真实先后，也不用于新单qty或触发条件。不实施597多root、共享add预算或新Dgate。

只读原Q函数补一个数值界面风险：若612为使原Q(F)<=L以nextafter保守编码DecimalT，触达判断仍应使用语义T，不能让原Dlow恰等于T因编码下调一ULP而变成不触达。建议审计semanticT与encodedF分开，具体遵611/612冻结版本；没有触达/quote参数扫描、代码或实际测试。当前继续待611，0实现/actual。

## 2026-10-21 08:45 611冻结后的隔离实现与source-ready（未actual）

已完整读取611（19831B，SHA19c23d804c086a6d229cb2b96459e851549223916222646e1a3e354fac16992b）。仅新增独立613kernel/runner/7项必要合成fixture。先7项正常断言RED、0errors；内核后GREEN7，runner后同7GREEN（最后.003秒）。每个GREEN有2次原核和6次候选**合成**微型账本调用，非历史A/C回放，不计实际cash。无旧suite或真实行情预试。原131函数剥离明确entry/audit/disjoint marker后逐字恢复，证明旧仓循环、u挑选与共同预算、下一u及日线权益算术未改；没有事件阶段重构或赢家加仓。

611单一价格合同已落实：开盘原Q(O)<=L用O；否则精确Decimal反解语义T、一次有条件nextafter保守float编码F，触达始终按Decimal(Dlow)<=T，原Q(F)不得超过L；qty/quote/SL0共用F，SL0=rawF−.25N。无clip/搜tick/第二次修正。缺tick沿原连续报价与tickized=false。numeric_inverse_unknown加入原entry_execution_unknown，使原execution_unknown合并；未触达/非正触发/原stale/qty0/lifecycle独立取消。每个qtycap>0的pending从原budget提取limit_audit并检查状态闭合，最终真实BUY再硬核Decimalfill<=L。

runner薄复用575输入恢复和原157纯报告/pairedCI/fixed_gate，已保留正确2020STRESS CI门；不是575的开盘cap策略。限定全98/95、原signals/mothers/native恢复一次、4A复用0A回放、最多4新C/0fit；无新cashgate/D资金再分。入场组PnL仅账本分解，不作逐笔因果或实单认证。正式C9/旧工具/LINE/registry未改。

source_ready：`outputs/stage613_conditional_limit_cash/source_ready.json` SHA0a795432bb2511ed3572104f9bd652b8c1688c96f8d93a41768c4202244d3702，fixture_receipt SHA4d3b8caf7b89ad6d7c6f44b51562a7caba759dec343c1b004389b22947721336；kernel SHA04e648ee00c750b96f896d2e801f0b4bd6d4cda208eceb15ebafe2874d18eac3、runner SHAb1762d036f8acd7cb6e603171bf38dc9cd33e0b57d0649317b075175f3bf2625、fixture SHA1f0503f762349dd66aa963e886ddfb357b334c66926062fbeec2959ea0199d67。准确CLI已交root与614；冻结源不再编辑。作者0actual/真实cash/fit/SQL/下载/历史输入读取，财务结果仍N/A，累计551fit/286完成cash及旧partial1未变。

本次没有新增经济参数或收益后选择，过拟合新增否、长期适应性风险高。值得完成一次冻结条件账本反证，非保证更高收益/更小DD；等待614源审后root唯一actual，不据合成结果宣称目标完成。
