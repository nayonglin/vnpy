# Stage077：等待数据增量层P1修复的定向独立复核

- line_id：`futures_trend_triple_screen`；记录时间：2026-10-18 06:12 CST。
- 工作区：`/Users/mac/Desktop/fian`，沿`codex/ai-training-data-expansion`；无worktree。
- reviewer：原Stage072独立reviewer `accepted_delta_review`。
- 结论：**原P1-001已关闭；本次剩余P0/P1/P2=0/0/0。经本次审查的新代码可供root执行真实freeze；真实数据集另审。**
- 阶段不是alpha突破，不触发A/B；真实190包freeze仍为0。

## 调研与判断

仅按root授权定向核对Stage074修复、其fix_evidence、原Stage072反例和原021资格parser；无网上/GitHub调研，没有重跑旧suite或扫描真实190包。原069/072证据及原021字节均核SHA保留。

判断：同一bytes验SHA并解析已经关闭原来的路径替换窗口。叶子symlink拒绝只是附加限制；普通文件被替换也不能使解析器消费另一份未签bytes，这才是关闭P1的依据。

## 实现与证据身份

- 新061 SHA：`3570427b8d1543a7fc7dc14e3fb17978f394fb4864b809e85d75fa6609b5a73a`。
- 新test SHA：`9479ee9d268563dcb49f53baf4f980da49b8b4f7d1372aa287dd1c653c4f8bc8`。
- 未变021 SHA：`150dd70a264f360046f6d633829a4dff9a81c371c34bad6288e41a081bbb498b`。
- Stage074 fix_evidence SHA：`240ede69509d7966c38e7cfce60370f1529c0abbf2604949609f83169b8c140f`。
- Stage069 evidence仍为`d6a4c9980613e26f5dd0660e737ed3a73d6f1d2d4817595b87e8d2203eb69554`；Stage072 evidence仍为`40b4dae8e1fba09b45b20044a27ea1d0b0895a03aae2277f2e58a66b90f9002a`。

## 原021与新私有bytes parser逐项对照

| 原资格门 | 新061对应行 | 结论 |
| --- | --- | --- |
| QualifiedDelivery类型、receipt绝对路径与SHA | 126–129、47–60 | 保留；同bytes验证，另加owner与叶子symlink限制 |
| schema、independent、reviewer、qualified、P0/P1 | 130–133 | 相同 |
| request SHA、accepted身份、重复及未知范围 | 134–142 | 相同 |
| accepted=True与完成+daily=True | 143–144 | 相同 |
| accepted时间戳精确等于required，全部要求完整接受 | 145–152 | 相同 |
| full_session/anchor精确权利集合 | 147–150 | 相同，freeze仍拒绝其他kind |
| data绝对路径、source绑定和数据SHA | 153–156 | 保留，同bytes验SHA；owner绑定更严格 |
| CSV字段、键唯一、exact allowed集合 | 157–159 | 相同 |
| 七值finite、OHLC正、volume/OI非负、high/low边界 | 160–166 | 相同 |
| 返回data复制、full/anchor及audit | 167–169 | 相同 |

本地两个小fixture分别覆盖anchor与full；原021和新parser返回的frame、权利集合及audit全部相等。没有为修复降低原schema、完成值、日线或权利门。

## 实际定向验证

1. `.py311/bin/python research/lines/futures_trend_triple_screen/tools/test_stage061_accepted_wait_delta.py -v`：只运行现有三个tests一次，exit0，3 tests、0 failure/error，约0.145秒。第三函数现包含普通CSV/symlink CSV/manifest/review/freeze receipt的同一P1反例。
2. 独立定向反例命令exit0：
   - 重用原072 symlink替换方式：被`consumed_source_absolute_non_symlink_required`拒绝，没有未签重开事件。
   - 对普通文件，在新`_bound_payload`返回后把路径替换成open=10.25，CSV解析后恢复原文件；实际只消费已验bytes的open=10.0，InputRecorder.verify通过且安全。
   - 两个parser fixture的frame/权利/audit等价。
   - 2,320,000字节的非金融closure-only dummy禁止`Path.read_bytes`后仍通过`_bind`；只流式hash，无payload缓存。
3. Stage074声明的文件指纹全部核对通过；原069/072保持原SHA。

manifest/review/failure/terminal/context/base/request/fingerprint/response/receipt均走`_json -> _bound_payload`；delivery CSV和overlay/rights CSV从同份缓存bytes经BytesIO解析。snapshot/deliveries artifact仍仅验字节SHA，不额外重开解析。closure-only大行情只流式哈希，未把原始大型数据常驻payloads。

完整命令、exit与stdout位于`outputs/stage077_wait_delta_fix_independent_review/evidence.json`。

## 资格限界与下一步

本次只签代码修复审查，receipt schema不是`stage061_independent_wait_delta_review_v1`，没有真实manifest SHA，也不赋予builder数据集自审资格。root可使用上述固定SHA执行真实190包freeze；新manifest、四项产物、190选择及数据集资格仍须另行独立审查后才能接入金融runner。

058模型历史PIT两项P1、066旧source859问题和成功账户封存路径限制独立保留。没有修改作者代码、旧021、LINE/registry、069/072；不stage/commit/push，不自行派reviewer。

## 参数、结果与反思

新增/修改/删除策略参数及金融结果均0。期末权益、收益、最大回撤、Sharpe、滑点、交易次数、胜率均N/A。真实freeze、金融回放、模型load/fit/predict、网络、订单、全市场hash和真实190重扫均0；`production_qualified=false`。

开始及结束过拟合判断：**否**，同SHA消费完整性修复不参考收益或改变参数。开始及结束继续价值判断：**是**，原P1已有独立反例关闭，可推进root实际freeze，再按数据集资格合同审查。

