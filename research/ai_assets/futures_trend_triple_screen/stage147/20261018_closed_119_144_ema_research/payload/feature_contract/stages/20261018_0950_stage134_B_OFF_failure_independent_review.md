# Stage134：B_OFF真实失败、commit范围与中性审计投影独立复核

- 记录时间：2026-10-18 09:50（Asia/Shanghai）；line_id=`futures_trend_triple_screen`，沿已有本线与root指派。
- reviewer=`accepted_delta_review`。有限失败账户／实际数据消费审计，非重要突破，无新策略或金融运行。
- **P0/P1/P2=0/0/0（限本次审查范围）；金融不接受，完整绩效全部N/A。** 原有预算造成真实失败，不把已守住的预算当待绕过代码bug。11 financial attempts／4 accepted complete ledgers不变；本review新增attempt／训练0。

## 实际失败与身份

真实终态由root session47648／chunk4e198d观察，exit1，最后poll43.012675917秒。本次读取固定证据并核同字节SHA，未自行poll任何句柄：

- `stage133_B_OFF_actual_failure/actual_tool_terminal.json` SHA `8d287ff4d22277c63ed89034fcf553560de10cf9ffb10c8e7b4a6834e9859172`。
- run=`81ffc8f704ce4c5eb701e97e0397b12a`，B_OFF，financial source `4f42805c2c71f8492a44a6876a82672f410f44df`，原启动PID44392；owner SHA `ce61dcf3cbe0696cfbc12f1ebcf0f12436ee0dfb84662623e91fce36ec957efb`。
- context SHA `81c35c8d0230ae2ef8a3ea96339c93ea3755a75dc8ff12a5eb4c3760f0d2e8a7`；preflight SHA `bb6b92db0e897f9ceec1700e364d0efec978db6b04aaefa7dadd05e18163b37f`；run_failure SHA `1308a516f0311d1354f8da0204ea575b2a48684400bc487345057d5bc6dfac0e`。
- failure capture SHA `c0047f6bf2d7dc2bcfd0175da58b4a836e9986fc96f5b570e6d4230725cfc260`／1686556 bytes。terminal／owner／context／preflight／failure／capture的run与源绑定均一致。

真实错误为2025-04-11 bar的 `RuntimeError backtest_bar_failed`，内层确切是 `TimeoutError qualified_data_wait_budget_exceeded`。capture的failures元数据也仅记录该日期与该TimeoutError，phase=`engine_not_returned`，在此是真实而非旧A checkpoint误报。

原022 resolver预算分支检查 `wait>=1800` 或 `run>=7200`，抛出这个明确字符串；不能把它替换叙述为猜测的whole alarm。末等待开始09:31:23.152412、elapsed710.9125895秒，小于1800；结合原context开始07:43:14.055881，推算预算触发时刻09:43:14.065002、whole elapsed7200.009121秒，与真实run7200到限一致。此推算是墙钟元数据校核，不冒称取得内部monotonic纳秒或额外traceback。

## 完整账户缺失及N/A

原raw_account.pkl.gz、validation_seal.json、summary.json、export_success.json均实际不存在。失败payload只有065 partial capture；没有combined、frames、完整参数／spec／实际identity组装／返回elapsed等完整raw合同。本次只看顶层metadata、失败记录与resolver／gate审计，不读取trades／equity／usage数值，不输出或解释partial PnL。

engine没有完成固定终点，不能从partial tables拼出缺失区间或伪造完整frames／seal。期末权益、总收益、最大回撤、Sharpe、滑点总额、交易次数、母链胜率、完整margin与生存比较全部N/A；不能用其中一段或summary替代。没有证明可完整等价恢复账户，也未尝试恢复、重启或export-only伪造接受。

## 从真实capture得到的消费范围

只用原allowlist OwnedAccountUnpickler读取一次已pin失败capture：提取原 `payload.capture.wait_audit`、`resolver_audit`、`input_fingerprints`，另绑定terminal／capture／context／preflight／owner和source upstream身份；没有engine／strategy构造或market／model loader。

真实记录是160个requested、159个pointer accepted、159个 `data_qualified_appended`、1个 `data_gate_failed`。159个commit digest唯一，和159个pointer集合完全相同；receipt/data四个路径／SHA双记录相等，选中request／response／receipt／data均属于原capture的input_fingerprints。159个gate event的old_keys_changed均为整数0，appended_keys与各请求M一致。

此前115＋119＋122的151份，本轮只与真实消费记录对上身份／metadata，没有重新聚合价格或重审其已接受151包。剩余8份现在明确如下，全部是full_session：

| symbol | execution day | R/E/M | request digest |
|---|---|---:|---|
| hc2005.SHFE | 2020-01-15 | 345/0/345 | `46c486f3dba9ce4d0f1bfd6b5838ab13f9e537db9021506be78eaa296075164c` |
| CF005.CZCE | 2020-03-11 | 225/0/225 | `9c776780f23b03cfc899aacb031928c7c4db01fc1195809e5c701df7ad071f27` |
| CF005.CZCE | 2020-03-12 | 225/0/225 | `b03ab9745b6b557205695938c592ebf0710d0a07bb9f409d2d17c6a1c8ca6940` |
| CF009.CZCE | 2020-07-01 | 345/0/345 | `3fbe4a0a1e490607e6e0bdbcf962ab1aa9a0a6effd1277dc7e0826a7f5a7d0bd` |
| CF009.CZCE | 2020-07-09 | 345/0/345 | `d66263228ed7885a886724c899c83277377fbd540162b6926a1f5b58fe551790` |
| CF009.CZCE | 2020-07-22 | 345/0/345 | `a689847f505a0866e74c2a269dddc938bcfd5f2567101c954ea58df67ce36bca` |
| hc2010.SHFE | 2020-08-28 | 345/344/1 | `7d307621ed64f585b31830b222fc64bac60686d3be1e3624c885571815cbcbd7` |
| hc2101.SHFE | 2020-09-08 | 345/344/1 | `50d2fb92ca10a9d2c7515592978f53c460777d5cec527ca64cbef775011a3345` |

这8份仅检查既有独立021 schema／收据、actual021 parse_result accepted、严格gate commit、scope／完成资格／checks、同bytes链接与原值保护语义；没有调用021 parser重新算价格、没有重聚日线、没有查DB或重新认证所有旧市场源。其各receipt／request／response／data SHA及原gate位置完整列入机器可读scope。

精确159份数据权利为：**36391唯一键，full36345，anchor-only46；按061语义full也可作anchor，所以qualified_anchor为36391**。实际159次appended_keys总31703，existing request keys总4688。完整R及accepted timestamps用作未来数据范围，不能只取M而丢full权利；也不能把anchor升full。

old_keys_changed=0来自159次实际原021 gate消费时的检查，不是本审查重建了global engine RAM或重hash旧市场；未来freeze仍须保留equal-only、同字节SHA与冲突拒绝，不得据此覆盖源值。

## 最后CF505明确排除

最后digest `7422216c316b1eeea381af05e31318dfbea8903ffe77c31c6c9b6c7cf2c087eb`：CF505.CZCE／2025-04-11 full_session，request SHA `f6c7c41032809d75fee0917cfef492318b6266a0dee4d86fa1ab995d417ccea7`。它有request／fingerprint及prepared packet manifest／preflight，但没有network_attempt1、terminal_observed、response，更没有commit；resolver最后是wait_budget_exceeded、gate最后是TimeoutError data_gate_failed。

122中已核的provider840余量门未放宽；最终到限只强化它不可被补起的事实。保留该请求失败及所有原终态，不得将其预备目录当数据资格，不延长1800／7200或启动新provider／金融。

## audit-only snapshot及旧061边界

`audit_only_snapshot.json` SHA **`f601f0f32eb258b6cde458754709d2451b433025dbe297619992c59beb42ea18`**，5131992 bytes。它明确采用新 `stage134_audit_only_projection_of_stage065_failed_capture_v1`，包含原字段resolver／gate／input_fingerprints及upstream身份；无partial账户PnL表，不是新的数据资格，不是伪造的Stage063事实。

`committed_scope_audit.json` SHA **`1d8578b14c9adaf16fbdb5b3d5aa519cfa2e1d6690c82e58bb59539324a978cd`**，1878375 bytes；含159精确receipt／key权利／gate index、8份补充身份和失败排除，用于后续独立冻结的审计输入，不是已产出的overlay或seed资格。

原061不能直接freeze本065失败schema：它的 `_terminal_failure` 明确只认063 terminal、B_TS、stage036 context／writer及facts内嵌审计，实际065是B_OFF、partial_failure_capture、failed_partial_no_engine_seal且审计在capture中。原 `load_accepted_delta` 也不接受raw失败或这个audit snapshot，只接受正确manifest、四artifact、精确upstream和独立REVIEW_SCHEMA。此为原模块有意限定范围，不把它列成新增bug，不修改其guard或伪装B_TS。

最小后续中性适配边界仅为：真实065终态／capture身份入口→按原159双记录commit选取→保留原021资格、同bytes／七值equal-only／分权／计数与原子发布→绑定当前016／061／071／两anchor upstream及新的独立dataset review。旧通用数学或manifest reader只有在所有原guard确实满足时才可能复用。本阶段没有给新runner设计、编码或可运行接线，也没有执行freeze或直接认定新seed可用。

## 实际命令、限制及反思

- `.py311/bin/python .../outputs/stage134_B_OFF_failure_independent_review/project_failed_capture_metadata.py`：chunk956d74、真实exit0；原022 frozen数值runtime，仅OUTPUT路由到reviewer自己的目录；SHA／owner核验后唯一一次OwnedAccountUnpickler。
- `.py311/bin/python .../outputs/stage134_B_OFF_failure_independent_review/audit_committed_scope.py`：chunk5d7330、真实exit0，纯metadata／链接与8份原资格身份；不重跑parser或价格。
- 最后pending／snapshot SHA确认chunk9cf379，真实exit0。实际命令／输出及脚本SHA见command_evidence和收据；有限静态源码读取未调用freeze／loader／guard。

最终receipt：`outputs/stage134_B_OFF_failure_independent_review/review_receipt.json`，SHA **`2d6f19e8fbb6f94976380ae114c7ca6cde8c70ea4ad5df3d2f9628aeaa9edd7a`**。审查边界是实际失败、metadata、消费scope与中性投影；7663项源fingerprints只是capture原有事实，不代表重新hash3157或4000市场源。

没有新金融／模型／provider／网络／guard／readiness执行，没有解释partial绩效，没有碰root47648或operator句柄，没有修改作者源、LINE、registry或Git。11attempt／4accepted不变。开始／结束过拟合判断均**否**：只核真实审计而无收益选择。继续价值**是，限于把真实159消费前缀与失败末请求分清，供后续一次有界中性冻结**；不能把它写成B金融通过。
