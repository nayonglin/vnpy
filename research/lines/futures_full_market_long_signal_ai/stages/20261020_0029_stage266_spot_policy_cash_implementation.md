# Stage266：固定现货参与过滤的最小现金薄封装，未运行actual

- line_id：`futures_full_market_long_signal_ai`；2026-10-20 00:29 CST；非重要突破、非新金融结果。
- 原研究仍独立于正式C9/月度池。本阶段新增fit/cash/SQL/网络/预测/标签/选择/生产均 **0**；累计 **439 fit / 234 cash**。

## 实现与固定接口

按root已经冻结的264协议（SHA `d18b82b34719425439a7190325fa692c912c93aa42db7d0d46493f2544013d42`）新增[薄封装](../tools/stage266_spot_policy_cash.py)和[2个mock fixture](../tools/test_stage266_spot_policy_cash.py)。未改旧157/任何kernel，未调用旧CLI、选择器或读取actions/score/model；未读取实际大data/native/SQL或新金融结果。

与265实现方事先固定`signal_map.csv.gz`：`signal_row`和原`event_id,mother_event_id,product_id,family_id,u_date,u_index,reference_epoch,anchor_epoch`逐行对应原4365信号；`available,keep_entry,action,reason`只决定原动作保留/取消。无S必须继承，不重选、不改分数/风险/边界、不扩成原成交子集。265 manifest/coverage协议固定且已交267。

actual入口在单一root授权中绑定264、265manifest、267receipt、新source/fixture与fresh output/max4。265须completed、total_signals4365、core_blockers0且cancel_count>0；267须completed、core_blockers0并精确覆盖新266源。取消数为0在原大数据与资金读取前结束。**只是研究执行身份门，不是生产资格认证。**

通过上述门后才lazy读取原157完整4365 signals、完整399252 mothers身份列；132恢复冻结cache → 148 CachedMarket → 131 `organize(filtered_signals,完整mothers,dates)` → 原131 `run_cash_account`。保留全canonical、原K/退出/手数/风险/容量/成本；旧四控制仅引用157，不重放。实际只允许2020连续/2023冷启×base/stress共四候选。每本在原核调用前写started、原核返回后写completed；失败不重试，保留fresh目录、progress/terminal/manifest和已完成账本。

输出沿原口径完整fills/daily/reservations/rejections/positions/closed/open/capacity/entry未知账本；候选summary、费用/滑点金额及可计算tick-lot量、已平仓根胜率、closed根数/fills/数量不同口径、年度收益/DD、family-year含零、原sector归因。原summary/diagnostics helpers复用，不重新发明现金算术。候选减控制权益/收益/DD、两stress固定主效应只按264声明，**不新建CI或放宽旧门**；全部未知/开放仓和历史stale保留。

## 有限TDD与交付

使用test-driven-development与writing-plans流程，先写两个fixture并观察缺实现导致2个明确FAIL；实现后最终 **2/2 GREEN，0.015s，exit0**。fixture仅检查新掩码/身份/缺失继承，以及研究gate、四账户启动完成/失败保留/fresh拒绝；现金callbacks为合成替身，未import/运行旧核或旧suite。root明确限制只做最多2个fixture，覆盖skill默认全suite建议。CLI `--help`通过，没有启动actual。

| 冻结文件 | bytes | SHA256 |
| --- | ---: | --- |
| stage266_spot_policy_cash.py | 18043 | c84e36ccc6220c027ae41a12ee8472a94c5c57b5612964a61c8a1c1d05138aed |
| test_stage266_spot_policy_cash.py | 4849 | 172617610608732f0bbef52f4480a4836ebaa09178a163c918db85b80c7ba6f4 |

[实施计划、RED/GREEN证据与source bindings](../outputs/stage266_spot_policy_cash/implementation/)已经归档；[单授权模板](../outputs/stage266_spot_policy_cash/implementation/authorization.template.json)已填准确265manifest和新源，267通过后由root填写其receipt bytes/SHA。源码已直接通知267独立源审，当前止步等待；未来每次真实金融批次完成后仍需独立agent审结果/数据/逻辑/置信度/bug，不能用本源审替代。

准确CLI（本阶段未执行）为：

```sh
.py311/bin/python -B research/lines/futures_full_market_long_signal_ai/tools/stage266_spot_policy_cash.py --protocol research/lines/futures_full_market_long_signal_ai/outputs/stage264_spot_participation_protocol/protocol.json --protocol-sha256 d18b82b34719425439a7190325fa692c912c93aa42db7d0d46493f2544013d42 --authorization <filled.json> --authorization-sha256 <filled_SHA> --output research/lines/futures_full_market_long_signal_ai/outputs/stage266_spot_policy_cash/actual_run1
```

原157终端记载四现金已完成，进程22.5037秒后停于历史metadata KeyError。本批按同核和新增导出估计30—90秒，未做probe、未修旧问题，也不是耗时保证。

## 调研与反思

先复读registry/264及263已闭包的接口，外部依据复用251/264原调研；本阶段遵守0网络，不重复源资格工程。判断：原核和原控制足够，薄封装只实现已批准的一次有限证伪；无需重新训练、读取旧标签或对照重放。开始/结束新增按成绩调参过拟合：**否**，无新成绩参与实现；长期同史选题风险仍是**是**。继续价值：**是，仅限267独审后由root一次执行四本**，本实施不证明经济改善、PIT、晋级或goal完成。参数新增/修改/删除与金融结果新增/修改/删除均0，权益/收益/DD/Sharpe/滑点/交易数/胜率均N/A。不改LINE/registry/他线/生产。
