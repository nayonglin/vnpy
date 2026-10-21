# Stage109：外部 provider 真实 SDK 选择启动器的有限实施

- line_id：`futures_trend_triple_screen`。
- 记录/冻结时间：2026-10-18 07:57 CST，精确时间见 implementation receipt。
- 依据：root `20261018_0752_stage109_provider_runtime_selection_contract.md` 全文；Stage108 已证明实际 batch002 在网络前因 SDK 3.9.4 解析失败，packet/network_attempt 均未建、连接 0。
- 阶段性质：数据工具启动环境正确性，不是 alpha 突破；不增加金融 attempt。
- 授权范围：只新增外部启动器、本线专用 sitecustomize、一项有限回归及本实施记录；原 065/087、owner/readiness、099 合同、SDK 安装包、metadata 函数、鉴权/端点/数据资格 guard 均不改。

## 调研判断与执行边界

复用 root 合同已查证的 Python site/importlib.metadata 启动语义，并核对本地实际源码。`scope.numeric_runtime_is_frozen()` 检查五个已加载数值模块属于原 FROZEN_SITE 且该目录仍在 sys.path，不要求它排首位；`scope.invoke` 和 provider 的 worker Popen 使用真实 `sys.executable` 且继承环境，因此仅新进程树的 PYTHONPATH/sitecustomize 可以覆盖所有这些子解释器。没有新增网络调研、没有因为研究时间窗口而降低门。

本轮不读取 B partial PnL、不重启金融、不改等待起点。B 第 2 个 jm 请求原等待始于 07:46:33，原 1800 秒等待与 840 秒启动余量均保留；约 08:02:33 后已不能启动新连接。是否赶得上、是否实际启动 batch003，全由 root 在 Stage111 独立接受后按当时真实余量决定。

## 最小实现

新增两个生产文件：

1. `tools/stage109_provider_runtime_launcher.py`：stdlib 启动，固定当前本线、原 .py311 SDK site、原 018 pin、原 087 scope/provider 与 Stage109 合同。它按同 hash bytes 解析真实 owner 及 context/preflight/readiness/review JSON，绑定新增源码和实际 SDK 路径/字节，创建独立 session sidecar。实际 provider 模式必须有新的独立 runtime review，精确两新源 ABS→SHA+bytes，`independent_review=true`、P0/P1=0；随后仍调用原 `scope.load_owner` 的真实 PID/owner gate。目标只能是原 scope/provider，目标参数里的 owner/path SHA 必须等于启动器参数。原 SDK `sdk_preflight`、端点、鉴权、资格和预算逻辑原样保留，没有任意脚本或多环境选择器。
2. `tools/stage109_provider_runtime/sitecustomize.py`：仅通过新子进程环境的绝对 PYTHONPATH 发现，不写全局 .pth、site-packages、用户环境。启动失败捕获 BaseException 后输出不含环境/凭据值的固定错误并 `os._exit(78)`，防止 Python 默认忽略 sitecustomize 异常后进入 CLI 正文。没有改 `sys.executable`，没有改 metadata.version/distribution。

每个新解释器的启动顺序：

- 核 sidecar manifest 同 bytes SHA、owner 和冻结输入绑定；任一错误 fail-closed。
- 以原 022 `configure_runtime` 在**本 session、每 PID 独立目录**建立空 signal 环境，使用原 ROOT/VENDOR/PROJECT/FROZEN_SITE 路径顺序。
- 由原 FROZEN_SITE 实际加载 numpy/pandas/scipy/sklearn/joblib，核实际 `__file__` 和模块版本等于原 frozen distribution。此时不 import TqSDK。
- 在最终 SDK 路径选择前完成一次原 `scope.deps()` 的 helper 定义初始化。该步骤确有必要：首轮 GREEN 发现这些 helper 首次导入会插入项目目录；这与数值 runtime 重选不同。最终选择前吸收这一次原样初始化，后续真实 deps 调用前后 sys.path 必须完全不变。
- 将真实 `/Users/mac/Desktop/fian/.py311/lib/python3.11/site-packages` 放到前面，原 FROZEN_SITE 仍保留，原 numeric guard 必须为真。
- 使用真实 importlib.metadata 和 find_spec，要求 TqSDK distribution 为 3.10.2、dist-info/package/init 来源均为本机真实路径，并核 api/auth/tqsim/backtest/downloader 五源 SHA 与原 018 preflight（`c178b128b39f0a85999a2992f1730d9737d51cd5b5a0b170c649cc97caa738e9`）完全相等。未先 import SDK 抢占缓存。
- 在 CLI 正文前落该 PID 身份收据：PID/PPID、实际 Python/argv、owner SHA、新/原 review、runtime 源码、五数值包路径与版本、SDK metadata/实际源码 SHA、有限第三方路径。实际子 scope/prepare/run/worker 继承同环境；原金融进程环境不受影响。

## sidecar 边界与局限

sidecar 固定根为 `outputs/stage109_provider_runtime_selection/sessions/<uuid>/`，包括 manifest、每 PID interpreter identity、每 PID 空 signal/runtime 目录和 launcher terminal。manifest 明确 `old_financial_context_includes_this_sidecar=false`。原 087 packet receipt 没有新启动器字段，未改写它，也不声称该启动环境原已包含在旧金融 preflight/source closure。未来独立数据/账户审查必须另绑定这个真实 sidecar。

原金融 owner 内二源 data-scope review 继续保留；Stage111 的 runtime review 是另一个精确二源合同，只包含本次 launcher/sitecustomize，test 可放 integration 字段。实际 provider 模式会要求这一新 review；本阶段 probe 的 runtime_review 为 null，不具备实际执行授权。

SDK site 前置只保证被明确预载并核验的五个数值根包来自原 FROZEN_SITE。requests/aiohttp/websockets/certifi/jwt/psutil/packaging/threadpoolctl 等其他依赖，可能来自启动前已经导入的包或新路径解析；收据如实记录 preloaded/实际 file/selected origin，并标记 `unpreloaded_third_party_not_covered_by_numeric_freeze=true`。未声称整个环境与原冻结环境逐文件等价，未承诺远程数据一定成功或整个 SDK 依赖兼容。原 SDK 身份/认证/网络/数据资格仍须实际 provider 原样验证。

## 唯一有限 RED → GREEN

唯一新 test：`tools/test_stage109_provider_runtime.py` 的 `test_three_generations_real_identity_and_fail_closed_inputs`。不运行旧 suite、旧三测或全市场 preflight。

```sh
PYTHONDONTWRITEBYTECODE=1 .py311/bin/python research/lines/futures_trend_triple_screen/tools/test_stage109_provider_runtime.py
```

- 测试先于实现。真实未选择环境由原 022 初始化，观察 metadata **3.9.4**、SDK 未 import；随后因专用 selector 尚未实现产生有效 RED。工具 chunk `9b7cf2`，exit `1`，`Ran 1 test in 0.069s`，1 failure、0 errors。`red.log` 保留完整证据。
- 首轮 GREEN（非最终）实际失败，错误 `stage109_deps_reordered_runtime`。原因是原 helper 首次 import 插入项目目录；日志单独保存 `first_green_path_initialization_failure.log`。只增加“最终 SDK 选择前完成原样 deps 定义初始化”这一必要动作，没有放宽数值、SDK、端点或 path-stability 门。
- 最终 GREEN：工具 chunk `e441dd`，exit `0`，`Ran 1 test in 3.894s`，`OK`。完整证据为 `green.log` 与 `finite_test_evidence.json`；没有因通知再跑验证。

三代真实解释器通过原 `scope.invoke` 继承 env，实际 PID/PPID 为：

| generation | PID | PPID | SDK | 原 numeric guard | deps 前后 sys.path |
| ---: | ---: | ---: | --- | --- | --- |
| 0 | 46008 | 46007 | 3.10.2 | true | 完全相等 |
| 1 | 46009 | 46008 | 3.10.2 | true | 完全相等 |
| 2 | 46010 | 46009 | 3.10.2 | true | 完全相等 |

三代实际冻结版本一致：numpy **2.4.4**、pandas **2.3.3**、scipy **1.17.1**、sklearn **1.8.0**、joblib **1.5.3**，每个实际模块 file 均在原 FROZEN_SITE；SDK find_spec 和 metadata 均真实指本机 3.10.2，五源码匹配原 018。完整 ABS 路径和 SHA 位于真实收据，不用模拟值冒充。

离线 probe **直接进入原 `provider.sdk_preflight`**：原版本/端点 guard 实际执行通过后，使用仅该 probe 的 trace 在 `load_credentials` 所在行执行前立即停止。没有读取凭据、没有 import SDK/构造 API/联网。收据明确 `original_version_endpoint_guard_passed=true`、`full_sdk_preflight_completed=false`；这只证明原版本/端点条件，不是凭据、auth 或完整 SDK 预验通过。实际 provider 模式不存在该 probe trace，会原样执行完整 sdk_preflight。

同一测试还证明错误 endpoint 和 owner SHA 非零退出；带错误 endpoint 的真实 sitecustomize 启动以 **78** 退出，Python main sentinel 没有运行。未通过把错误异常吞掉来伪造通过。

## 冻结源码与收据

源码与测试已在补文档前交 root 安排 Stage111 一次独立定向审查：

| 文件 | SHA256 | bytes |
| --- | --- | ---: |
| `tools/stage109_provider_runtime_launcher.py` | `544809b18c6e8d1d74efd708cfec600b781b97da6bebd95d9e340e077f0ad93c` | 12742 |
| `tools/stage109_provider_runtime/sitecustomize.py` | `ba9ae3352dd5c20cf6f6a6e7c09de5dda174f1cb397c5f9c8fd460557f112bc5` | 628 |
| `tools/test_stage109_provider_runtime.py` | `1ab6480cd70009f1bf618878700accab6ca7bab9afd52b472f91ea74fc055a08` | 5157 |

三文件均做 Python 内存 compile，不生成 pyc。`outputs/stage109_provider_runtime_selection/implementation_receipt.json` 是本作者实施收据，**不是独立 review**；真实三代 session manifest 路径/SHA 在其中及 finite_test_evidence 内。原 065/087、SDK/数值安装包、metadata 函数、owner/readiness 和失败 batch002 未改；没有另派 agent，没有修改 LINE/registry 或 Git。

## 结果与反思

新增/修改/删除 alpha、日期、本金、成本、限额参数均 0；本次 financial run、API/网络连接、凭据读取、packet 创建和训练均 **0**，没有新回测成绩。原每批 4 连接（含 daily）、每 packet 一次网络 attempt、570/600、840 余量及金融 1800/7200 全部保持。依据 root 07:52 合同，当时全研究 11 attempt/3 accepted、A 等待独立接受；本实施不重置或新增这些次数。

期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数与胜率均 N/A；不作 alpha 改善或生产完成声明。开始与结束过拟合判断均否：只修数据工具环境选择，没有按收益调参。继续价值均是：有机会让现有合法 provider 使用原已接受 SDK，避免因本地包解析错误重跑金融，但必须承认当时原时限及数据资格仍可能使其无法启动/成功。

本作者交付后冻结新源，等待 root 的 Stage111 独立定向接受；未实际运行 batch003，也不延长当前 B 等待。
