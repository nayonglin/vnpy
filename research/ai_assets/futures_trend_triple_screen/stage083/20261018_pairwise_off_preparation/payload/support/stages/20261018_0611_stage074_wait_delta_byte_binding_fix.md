# Stage074：修复等待数据增量层的校验与消费字节窗口

- line_id：`futures_trend_triple_screen`；记录时间：2026-10-18 06:11 CST。
- 工作区：`/Users/mac/Desktop/fian`；沿当前研究分支，不创建 worktree 或切换分支。
- 阶段性质：按 root 授权的一次有界修复波次，处理 Stage072 唯一 `P1-001`；不是 alpha 突破，不触发金融 A/B。
- 改动范围：仅 `tools/stage061_accepted_wait_delta.py`、现有 `tools/test_stage061_accepted_wait_delta.py`、本记录及 `outputs/stage074_wait_delta_byte_binding_fix/`。不改旧 021、LINE/registry、Stage069 证据，不 stage/commit/push，不自行另派 reviewer。

## 本地调研与判断

按本次无网络边界，未重新网上/GitHub 调研。完整读取 Stage072 独立 review 与 evidence，并使用 receiving-code-review、systematic-debugging、TDD 和完成前验证流程核对本地根因：原 `_bind` 验路径的 SHA 后，JSON 与 loader CSV 又按路径打开，短暂替换后恢复可令最终 SHA 和 InputRecorder.verify 都通过，却实际消费未签署值。原 021 CSV 已从同一 payload 验 SHA 并解析，但其 receipt 仍按路径重开。

判断：这是真实的来源绑定缺口，应在任何真实 190 包冻结前修复；只加末次 rehash 或拒绝 symlink 无法解决普通文件替换与恢复。

## 修复内容与有界适配

- 新增操作内的 `_payload` / `_bound_payload`：每个实际解析的 JSON/CSV 读取一次 bytes，针对这份 bytes 计算 SHA，后续 JSON 或 `BytesIO` CSV 解析消费完全相同的 bytes。路径发生变化也不能换成另一份未校验内容。
- failure、terminal、context、base manifest、request/fingerprint、response、receipt、delivery CSV、加载 manifest/review 和各 output artifact 均使用该方式绑定。snapshot/deliveries artifact 此前仅验 SHA，仍从一次读取的 bytes 验证；没有在校验后按路径重新解析。
- context 原合同没有外部独立 pin，仍沿 root 批准的同 owner 身份对齐适配；本次对同一 context bytes 生成 snapshot SHA 并解析，消除其读取/指纹分离。
- 叶子 symlink 直接拒绝是额外限制；普通文件的同 bytes 校验与解析才是主要修复。既有冻结末次来源 rehash 仅作附加漂移检测。
- 仅实际解析对象及本层小型 artifacts 缓存 bytes；只为闭包验 SHA 的原始大型行情仍流式处理，不永久缓存190包闭包内的全部原始行情。
- root 已批准在 061 内移植原 021 `_read_delivery` 的私有 bytes parser。依据原 021 SHA `150dd70a264f360046f6d633829a4dff9a81c371c34bad6288e41a081bbb498b`，差异限于 IO 消费方式；保留 schema、QualifiedDelivery 类型、独立 reviewer/P0/P1/qualified、request、accepted 精确范围、complete+daily、路径和 source 绑定、数据唯一性、七值合法性全部检查。原 021、engine 和 gate 均未修改。

## RED → GREEN

仅运行原三个合同函数，在第三函数补充同一个 P1 的有限反例：

```text
.py311/bin/python research/lines/futures_trend_triple_screen/tools/test_stage061_accepted_wait_delta.py -v
```

- RED：exit `1`，`3 tests / 5 failures / 0 errors`。普通 CSV 与 symlink CSV 均读到了 `open=10.25`；manifest 读到了未签 builder；已签 P1=1 的 review 被短暂 P1=0 内容绕过；freeze receipt 把临时未签字段写入产物。五项均有实际行为断言，不是源码文本检查。
- GREEN：exit `0`，`3 tests / 0 failures / 0 errors`，约 `0.146s`。静态 rights 篡改继续拒绝；路径替换与恢复场景只能得到已签 bytes 对应的值或 fail-closed；原 full/anchor 权限、七值逐项冲突、原子性、双记录选择与来源漂移合同仍通过。
- 原 022.configure_runtime 在数值包导入前运行，继续使用既有冻结数值栈；没有重扫旧 suite、重新扫描真实190包或重新解析真实金融结果。
- 实际日志：`outputs/stage074_wait_delta_byte_binding_fix/red.log`、`green.log`；指纹与运行结果：`fix_evidence.json`。

## 前后身份

| 文件 | 修复前 SHA256 | 修复后 SHA256 |
| --- | --- | --- |
| `stage061_accepted_wait_delta.py` | `3f3cf7dfca8af51226271a3db4ea56927c6e8909f9a77ff262a1ea9d30a50e85` | `3570427b8d1543a7fc7dc14e3fb17978f394fb4864b809e85d75fa6609b5a73a` |
| `test_stage061_accepted_wait_delta.py` | `fa0fde4ca859e1a921ec30b4d36bf6eac9678bdc475873c6f473626c282a928c` | `9479ee9d268563dcb49f53baf4f980da49b8b4f7d1372aa287dd1c653c4f8bc8` |

Stage069 implementation evidence 保留，实测 SHA 仍为 `d6a4c9980613e26f5dd0660e737ed3a73d6f1d2d4817595b87e8d2203eb69554`。

## 结果、限界与下一步

新增/修改/删除策略参数、金融结果均 `0`；期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率均 `N/A`。真实190包冻结 `0`；金融回放、模型 load/fit/predict、网络、CTP、订单、原数据修改均 `0`；`production_qualified=false`。

本阶段仅完成作者修复与三个有限合同验证，不能自行关闭独立 P1 或签署数据集资格。下一步由 root 交同一 `accepted_delta_review` 做定向复核；通过前保持真实冻结阻塞。058 历史模型 PIT、066 旧 source859 问题和未来成功账户封存合同不由本修复改变。

运行前与运行后过拟合判断：**否**，修复只决定同一签署 SHA 对应的 bytes 是否真正被消费，不看收益、不改价格、不搜参数。运行前与运行后继续价值判断：**是**，五个反例已证明原完整性边界缺口，修复后可继续进入独立定向复核。
