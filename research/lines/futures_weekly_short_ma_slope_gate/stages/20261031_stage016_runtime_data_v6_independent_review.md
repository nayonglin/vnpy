# Stage016 runtime/data/updater与现金V6独立复审

- 时间：2026-10-31；精确时刻与全SHA见JSON。仅新独审工具/记录；旧V5的331测试/receipt、Stage014及旧失败尝试原样保留。
- 结论：修复两项P1后，离线组件条件接受；开放P0/P1/P2均0。锁源目标333项调用及新增独立28项调用全部通过，共361次成功测试调用，明确不称全局去重unique。
- 真实来源、银行到账E2E、生产资格、master晋升、安装均false。未CTP/银行/SMTP/原生下单，未金融回放，未Git index/commit。

## 独立发现与修复

1. P1：旧runtime仅绑定source.close，NaN/Inf volume与错误OHLC/OI可进入AM。纯验证器旧源RED保存；新runtime逐项核有限OHLCV/closeOI与不可变源一致、合法OI0保留，额外未来日/15:00前forming拒绝。独立7例GREEN，旧工具未改，仅新v2适配approved_bar_lookup内部结构。
2. P1：旧updater仅legacy seed核quote交割月，已知explicit registry的AP612可把2036报价写入202612epoch。完整19产品/SQL fixture复现并保存RED；新updater逐新增bar核真实quote YYYYMM与选中epoch，跨十年同VT拒绝发布、匹配正例仍通过。独立2例GREEN，旧prefix不改。

## 数据、原策略与异步状态

- 不只调用被审assert：31原文件逐一对Stage014冻结HEAD 688754的Git blob原字节，再把原文件与frozen副本的565个class/function AST逐一比较，全同。170个策略setting在四个路径迁移后相同；原actual记录另有account_capital/c3_capital两个明确non_strategy字段，各150000，资产包只剔除此二字段，真实E仍来自broker Balance。
- 独立严读392382条已批准SQL DTO，另对原SQL抽核234个OHLCV/closeOI字段。future物理/SQL行不进入已完成输入；零量/非有限数据拒绝，OI0作为实际观察保留，不用open_oi补。
- 指标纯预热覆盖2093 AM，patch禁止on_bars/send_order被调用，无历史仓位/目标/层/补资；完整compact state恢复逐字段及SHA一致。实际single-state为5086416 bytes，T=0、R=150000元不变。本机峰值RSS约3.035GB、warmup约37.9秒、restore约27.3秒，只是技术量测，不保证service deadline或生产容量。
- 独立压缩反例覆盖输出限额、zlib bomb、拼接/截断/错误hash/base64、sharedref上下文与未知对象；64,000,000字节写限额在临时写/replace前拒绝，旧bundle保持。
- 新contract真实id0连续available history、合法listing未知单列；accepted旧scope不回写，只新AM预热。cash缺证保留已有close保护，recovery先真实fills后累计orders/positions；排队receipt与E自然恢复不虚拟加T，原admission不新增债务。相关锁源runtime用例已复跑。

## V6边界

- 完整private typed ledger来自0700/0600/noFollow/SHLOCK reader。独立重算逐record checksum/rawSHA，完整prefix usage参与24hex quota ID；caller名单/重hash命名不能代替quota+beforeinsert，未发送第二child没有伪造brokerID但完整父名单保留。
- parent计划量、物理child量及实际fill量分开。query与native callback语义保持，typed对象的JSON复制/嵌套篡改拒绝；首child终态不提前结束父，累计状态在真实fill后应用，跨重启及重复事件幂等。CAP6/AUTH13源门保留。
- 1835之后931确有root授权变更；旧7c888整文件与当前字节不等，没有旧snapshot/AST等价证明。JSON分别绑定旧pin与本次受测依赖，绝不把新整931/服务/quote/root桥/CIlegacy签成已审或生产。

## 限制与反思

真实registry、native/account/TransferSerial正样本、最终现金日结statement parser仍缺；HMAC/逐record checksum不是同OS owner对抗认证或hash-chain。没有真实来源/生产正例。原Stage014经济NO_PROMOTION和PIT/零成本/静态margin/容量限制不改。

是否过拟合：否，只修数据因果、现金真实性与恢复边界，不改alpha/风险率或扫描历史。是否有价值继续：是，两P1会直接改变风险输入/epoch；真实资格与完整执行接缝仍须另审。调研依据官方vnpy_ctp的原生query/push语义（https://github.com/vnpy/vnpy_ctp/blob/main/vnpy_ctp/gateway/ctp_gateway.py）及本地source，资料不能授予真实来源资格。

所有RED、准入拒绝、GREEN、实际数据技术验证及精确hash独立保留。本批receipt封存后不改；新依赖需新审。
