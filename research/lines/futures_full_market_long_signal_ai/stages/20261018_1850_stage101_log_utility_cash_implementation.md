# Stage101 L/G计划风险效用代理：现金适配冻结

- line_id：`futures_full_market_long_signal_ai`；2026-10-18 18:50 CST。重要突破否；实现完成、actual0，当前357fit/86cash、goal active。
- 已读本线registry、099协议与中文设计。继承098/099的Kelly及风险约束Kelly/SPO主文献判断：本实验只隔离同风险单位目标的曲率；不是新增信息，不把孤立事件log代理称为实际重叠组合财富log或回撤保证。

## 具体变更

新增`stage101_log_utility_cash.py`及小测试。从095最小适配L/G，删去sequenceMissing/外部数据接线与held输入，不使用RFF/OI/080，不改070原报价/预留/资金规则。100主分数是唯一交易分数，完整每臂161014，动作仍ready20且finite score>0；未来label/domain不做逐笔门。

cash前整候选门只accept100 completed actual4fit、322028主预测、0native/0cash、domain_pass/cash_eligible true，且domain_report为valid、已核OOS、双true。100若训练或closed-known OOS domain_failure，101拒绝、cash0；不clip/drop/epsilon/换f/恢复旧模型。domain_report替代held，不编造family留出或泛化证据。

8现金为L/G×2020连续/2023冷启×base/stress，同070原100w、单.25%/总2%、bufferedmargin25%/1.1、.25Wilder20N/20low、u预留D只减、gap/roll/缺价/破产。交易参数新增/修改/删除0。

## 新门与产物

G−L 2020stress收益严格>0/DD不更深/旧252源日块2000次同seed indices CI低端>0；其它三收益差>=0/DD不更深。另要求G四收益均>0、全部8账本日权益finite且>0并无ever_insolvent。空L DD保留NA。名义失败先unsupported，不能用unknown遮掩；实际historical stale与未成交潜在label unknown分离。仅后者不虚构现金暴露。无family held，不称泛化/加注/正式资格。

完整8账本、费用滑点、年度、全95family含零、风险/未知/有限native案例/paired CI/门、显式本地asset role沿095保留。只root可唯一actual runner，fresh outputs/stage101_log_utility_cash/cash，8cash共享一次native SQL；0fit/label/旧金融重放/download/大库hash。102一次预审与实际后全面独审。

## 必要新测试与冻结

6项新schema/行为测试先RED（101模块缺失）后GREEN：mainonly且未知标签不门控、无外部槽、主stress严格且其它三差可0、无fakeheld、G自身正收益与全部账本正财富、实际unknown和未成交label unknown分离、空L DD未知、domainfailure拒绝且native计数0。未运行旧suite或旧资格。

- source `25327` bytes SHA `3cd20421faf99950292e06679aac99d805a0bb76825b6b8756f0588d625bef89`。
- tests `4183` bytes SHA `b6db467d6736f3970174d33f52e589958ffbe25380432ce4392ebde83675a9b3`。
- freeze `3495` bytes SHA `455b78226e7612466a97ee00beae41d5d0d918bcd48ca7818b0db5a846fca0a7`。

## 结果、反思与TODO

本阶段actual0：新增/修改/删除回测结果均0；期末权益/总收益/最大回撤/Sharpe/总滑点/交易次数/胜率均N/A。synthetic fixture不计研究fit或现金结果。

是否过拟合：总体存在多轮历史选择风险，是；本阶段按本包收益调参否，仍无成绩且只实现099固定合同。继续价值：仅一次曲率代理与同单位控制的有限反证，有；门或domain失败便停止该固定目标，不扫其它效用/风险/模型。

TODO：102有限源码预审；100唯一次模型/定义域完成后root决定是否有cash资格；若有，由root唯一8现金；102全面独立review；不改正式版、LINE、registry或Git。
