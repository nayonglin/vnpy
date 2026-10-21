# Stage108：B_OFF 实际等待 batch002 终态及只读运行环境定位

- line_id：`futures_trend_triple_screen`；2026-10-18 07:48 CST 开始记录，07:51 CST 补齐只读定位。
- 分支 `codex/ai-training-data-expansion`；阶段性质：已启动099账户的有界数据操作，不是新金融/AI实验或重要突破。
- root授权：只接管 B_OFF 真实数据等待，自batch002递增；保留1800秒等待、7200秒全程、840秒provider启动余量、每批最多4次连接含daily、每packet唯一attempt。失败立即停止，不修源、不放宽资格、不覆盖旧值、不自动retry。
- 账户run `81ffc8f704ce4c5eb701e97e0397b12a`、PID44392；root独占金融tool session47648，本operator从未poll该handle，也不以provider状态替代金融终态。
- 只使用root签发owner：`outputs/stage087_off_data_scope/B_OFF/81ffc8f704ce4c5eb701e97e0397b12a/owner.json`，SHA `ce61dcf3cbe0696cfbc12f1ebcf0f12436ee0dfb84662623e91fce36ec957efb`；CLI内部按原owner.verify核真实进程及preflight/readiness/source身份，未改owner。

## 实际执行与终态

通过require_escalated真实执行原CLI一次：

```sh
.py311/bin/python research/lines/futures_trend_triple_screen/tools/stage087_off_data_scope.py \
  --role drive \
  --owner /Users/mac/Desktop/fian/research/lines/futures_trend_triple_screen/outputs/stage087_off_data_scope/B_OFF/81ffc8f704ce4c5eb701e97e0397b12a/owner.json \
  --owner-sha256 ce61dcf3cbe0696cfbc12f1ebcf0f12436ee0dfb84662623e91fce36ec957efb \
  --batch-id batch002 --max-connections 4 --budget-seconds 3600
```

工具initial chunk `43b962`、driver session12784；本人仅poll该driver一次，真实terminal chunk `edc3cb`、exit1。输出为blocked，child error `sdk_or_endpoint_changed`，`response_written=false`。journal status=`blocked`、provider_connections=0、events=[]。**失败后未启动batch003、未retry packet、未改变预算或连接方式。**

实际当前request从audit读取：`d3877eb65bfc7f8ac2304141da971ae8012a0fb61cbe1b32722debeece2080be`，request-file SHA `6f1dc34791b0c982e6f3835bbe69bd3d8cec5a4fabb5f678c7323c90b7aee054`，等待从07:46:33开始，要求2020-03-10 `jm2005.DCE` full_session；该request同时列有已有普通anchor订单，未把active_orders与实际缺失requirements混同。操作结束观察该request response不存在。

root batch001曾独立本地qualification/publish首个hc需求。accepted-local分支不追加journal events，故本阶段**不把batch001的events0写成交付0**；本operator未重复处理或覆盖首个response。本次batch002的0连接只是本批真实状态，不是全研究网络/交付总数。

## 精确错误位置与实际比对值

最初即时报告把子进程泛称resolver，现按静态调用及落盘证据更正：本request的 `daily_references.json` 已由resolve生成，随后drive `stage087_off_data_scope.py:689`调用provider `--role prepare`；`stage087_off_data_provider.py:76`进入sdk_preflight，在`:27`比较：

```python
metadata.version('tqsdk') != '3.10.2' or any(os.environ.get(k) for k in m.safety.ENDPOINT_ENV)
```

只读探针仅查询发行版metadata，并在独立短进程复现 `stage022_run_c0_qualified_wait.py:366`的精确sys.path前缀；不调用scope.deps、不import TqSDK、不读取凭据、不启动API、不连接网络、不修改安装包：

| 检查 | 实际值/类型 | expected |
| --- | --- | --- |
| 桌面.py311默认metadata.version | `3.10.2` / `str` | `3.10.2` |
| 精确prepend冻结数值环境后的metadata.version | `3.9.4` / `str` | `3.10.2` |
| `TQ_AUTH_URL`、`TQ_MD_URL`、`TQ_INS_URL`、`TQ_TD_URL` | 四者均不存在，get为`None`/`NoneType`，nonempty均false | 均无非空override |

默认dist-info为 `/Users/mac/Desktop/fian/.py311/lib/python3.11/site-packages/tqsdk-3.10.2.dist-info`；冻结前缀后解析到 `/Users/mac/Documents/Codex/fian-research-20261014/.py311/lib/python3.11/site-packages/tqsdk-3.9.4.dist-info`。证据指向**启动runtime/metadata包身份的解析不一致**，没有endpoint真实变更的证据。此独立metadata探针不是对已退出child内部sys.modules的追溯转储，也没有伪称观察到其全部模块状态。

该错误在provider packet.mkdir(`:78`)和网络运行之前发生；本次没有provider worker的网络terminal。原scope.invoke只把child stdout尾部纳入异常，不保存单独child stderr文件；不得凭空引用一个不存在的provider日志。真实可定位日志/收据为：

- journal：`/Users/mac/Desktop/fian/research/lines/futures_trend_triple_screen/outputs/stage087_off_data_scope/B_OFF/81ffc8f704ce4c5eb701e97e0397b12a/batches/batch002/journal.json`。
- 实际工具终态：`/Users/mac/Desktop/fian/research/lines/futures_trend_triple_screen/outputs/stage108_b_off_wait_operator/batch002_tool_terminal.json`，SHA `aa97ae1017744cc54f44c604bd1c3c74f04be30a1020af8a6d1ed4d441a32e93`。
- metadata探针：同108输出目录 `batch002_runtime_identity_probe.json`，SHA `e2a7d125eb98c97e20ee7c762510cc8c090216cb5486b088054d1bd277a91fb9`。

## 变更、结果、反思与交接

本次仅写本108记录/证据及原CLI自身request-scope/journal产物，原source、策略、数据资格、模型、参数、LINE/registry均未改。provider真实连接0，新金融运行0，fit/predict0；不读取账户中间PnL、不触碰root金融handle。

新增/修改/删除回测成绩均0；本阶段期末权益、收益、DD、Sharpe、滑点、交易次数、胜率均N/A。driver exit1不是金融终态，本operator不越权取消或续金融；已向root报告并遵令保持终态，后续只由root依据真实金融tool/错误证据裁定。

开始与结束新增过拟合：否，只按真实请求补既有数据，不选参数或看收益。继续价值：本次有界操作与精确身份定位有价值；**未经root单独裁定，立即retry无价值且违反唯一attempt/失败停止约束**。本次属于原工具操作/故障定位，不引入外部alpha设计；未新做网络调研。

## 08:02起：root明确恢复后的109/111环境接续

root另行授权：只继续同一个B_OFF进程，从batch004起全部经过`stage109_provider_runtime_launcher.py`与111独立接受的环境；review SHA `394879ddf698d5bb6d20cc54e62fb433e376977f78c70a9e0ecaea72df89bfb0`。保留batch002及root batch003真实失败，不修冻结087源、不重试已有packet；只在真实已交付后观察竞争或正常无wait时核新请求后续新批。原840/1800/7200/570/600/4连接上限均不变。

109 runtime sidecar是逐批独立的新增外部来源身份，**原金融run_context不包含这些sidecar**，最后应以实际manifest/launcher terminal/每解释器收据另行绑定，不声称原source/data闭包已预含它们。

| 本人批次 | 实际driver tool | 终态与连接 | 本批已知交付/后续 | 109 sidecar SHA |
| --- | --- | --- | --- | --- |
| batch004 | session10768；initial`ade584`；terminal`fd398c` | exit0，stopped_no_current_wait，连接0/events0 | 启动前真实b03…CF005 2020-03-12无response，退出后该response存在；accepted-local不写events，不能报交付0。随后owner.verify通过，新真实22c…hc2005 2020-03-26无response | `3fa13c3a32005cc5cc1518b3f4f0dcd647a22b6f8844b6aa3dc1da4d40913b05` |
| batch005 | session20385；initial`fb274b`；terminal`558f07` | exit0，stopped_no_current_wait，连接1 | journal真实published 22c…hc2005；随后owner.verify仍live，新真实594…FG005 2020-03-31无response | `58e41acb7e8f75e9dc92271e7039a694d404cb62728253b68d3d51c4fc44498e` |

004/005真实terminal保存在本108输出目录`batch004_tool_terminal.json`/`batch005_tool_terminal.json`，分别SHA `0b956c9c38637ec3ed97bdc6b65a1a942f6c10620940def078673aea0801d0b6`、`7f6cd50ab1e126085900f1f64adb236fee222dcd1d4018704e0cf0039088cfea`，每份带绝对sidecar路径与launcher terminal/journal SHA。batch006已针对真实594…新请求启动，own session64940，尚未观察终态，不算成功。本记录不轮询金融47648，也不读取中途账户盈亏。

### 08:07 实际后续终态（仅数据driver）

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch006 | 64940 / e3f12c | 0 / 1 / stopped_no_current_wait | 594e0e258bca973d06e8d9c15f19018b20ad4a132977964eda23209fe3c70a27 | cc36fd5a9015e659dfc6352aa73152a0c3c28338b3c32f926c026319e8822627 |
| batch007 | 50530 / d23844 | 0 / 2 / stopped_no_current_wait | 830c5e86ec465f1dc981e70e1ee8276446cd1ce4a6c643882ee9c5592ba165c0, d13ec013669203496ad03174f609e24f08f63e5af8e6649250ba677a4005eeb4 | 5bb88bf79856c0051f4dd4795f50dd1b284a60bb5e500932baf495323ba69596 |
| batch008 | 33409 / 9d8e3d | 0 / 1 / stopped_no_current_wait | df7e05f132532ed318a5ac13b7661e2a78d15a75781e5a995fe406b1049a44a3 | 699a422a28e8102fbf033e71f836cea8a41ffb3d957aade2782b1e0164cc9e6e |

每批实际工具terminal及sidecar绝对路径/manifest、launcher terminal、journal SHA均在108输出目录同名`batchNNN_tool_terminal.json`内保留。006/007/008退出后均独立通过原owner.verify；不把短暂无wait当金融完成。随后实际新request `2d1679…`为FG009 2020-04-29无response，已用原109/111入口启动batch009，own tool session10409；尚未观察该批终态。无重试/新金融/训练/来源改动。

### 08:09 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch009 | 10409 / a78125 | 0 / 1 / stopped_no_current_wait | 2d1679bf86664b01df63abeb6de5cfefb68e0873365fd5d529b269a85e2fc8ee | be93ee9a742413cb33e377cdc0dd515c2c161db85ac78fdaf1fe95434135d14c |
| batch010 | 68028 / b4d2e2 | 0 / 2 / stopped_no_current_wait | 038e21397ee370b237e7926a47e3464804792446ff7b8bee10c3bc3245995fe9, 4abff8db2a91bdd4359b2fa97be750489f3db392e58986e47f3aa36d299b6ea9 | 1d09736e07f49d7457e5cdcc7d14c8a4e290442a079db428b2945f7156eda3c8 |
| batch011 | 3022 / dc35c9 | 0 / 1 / stopped_no_current_wait | e2e0d5dcc366d60226267f107ba482566635fa4ac6249fbb36a2ab6e6fa62292 | 2ec4c71bfd0ac464966194c0755cb51c32d0acbc9aefc08fc7008d8587e95d75 |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

### 08:11 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch012 | 15875 / e1e4f0 | 0 / 3 / stopped_no_current_wait | e3c318b77123d266fa733559716d41864a1a63f653fd38bbd5ac9bab6445aa2f, 92a5053125ea20929cffa6bedb8ac8932500a28e18135cc85b5a3271d393302c, d4e0b01e58e649f1fe414e1626cadcbdef9933bc34477ea9c707b7e074d9458e | 1972a578c73f616b564cff80bec7284b33203a2cbdf56335ea2d1b8da9b0d377 |
| batch013 | 72796 / 18b4f7 | 0 / 0 / stopped_no_current_wait |  | cb9b5f786a500b8c6f1e1c7ef70e508d76cb132769821bb541ed337c824e814e |
| batch014 | 79202 / 12ab58 | 0 / 0 / stopped_no_current_wait |  | 88ce6f10bdbea379bdfb7edd3c1362b3caa2b86e75d6629c6d52faac001c4003 |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

### 08:12 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch015 | 33536 / e1bca6 | 0 / 0 / stopped_no_current_wait |  | 273d51ed38962173ce9704ca9e6e2f9c4bb77989cb2b06d6fcaacfc52877bf46 |
| batch016 | 70997 / 4d9487 | 0 / 1 / stopped_no_current_wait | 21120a5a9573ba042411c5ca011bfdb6a864eae99bf0a8ca01effa9096af6755 | 7a973d0b790c374bc43d9fc835f4df858be6f0686a4d55719bed302274a7fb54 |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

### 08:14 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch017 | 60197 / 3a7779 | 0 / 2 / stopped_no_current_wait | 8f329df16a2440d2cb043d194491e4ef5bad8b7e715e8659fb89e8dd4be870c4, e599a30e19e3488c6f62ca54d5df9db8199e281955ddce8130b75b5dc602e9bb | ffa57626e6952eeebbbe9797cb7c00a28807d9349ce268666ed00cf7efa476d8 |
| batch018 | 77134 / d4bad3 | 1 / 1 / blocked | 8da10d9b29308eb40dc6d611091fab4a280ce5865c16f1a2de234eaea52fbf85 | 9d5d429e6c7171deacb85cccb5f4066ad13d2841d1dde91ef19e05056715a449 |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

018失败分类：真实error仅request_not_current_owner_wait；其journal已published初始8da…，原response实际存在SHA be3c1bead1c32b4adbb82c5a6db70e01e81ec7b499437ca79c9bf6ef5b8637f9，原minute_packet/terminal_observed.json存在SHA d523b6703fd8ff14aa93656f47e2f2efbe27885bb043d4e107c0c1b62539b737。原owner.verify仍live，实际audit已换为440495…OI101 2020-08-27 anchor且无response。按root事先明确授权的“已交付后观察竞争可核新请求后续新批”，保留018 exit1并新启019（own97300），没有重试已有packet、修改guard或重启金融。

### 08:16 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch019 | 97300 / fd220e | 0 / 1 / stopped_no_current_wait | 440495c8e0005c1330f0967676c541e5916207ad7e88f0fb045ff8e12b9ac9ea | 5bbbca4d0c41b269317f7bba924f2d0cc24de02be09aff78e96ee5298978ce5a |
| batch020 | 89150 / 560f8a | 0 / 1 / stopped_no_current_wait | 1be52b026b0e9880f69875edc8ed6fb094ff5916356cea5072552c8355a5a442 | a58afcf79762d850c83d0c52801767873f2555dc545875426299e9770790ae4a |
| batch021 | 41854 / 384822 | 0 / 1 / stopped_no_current_wait | feaae15daeadec778c4c496f204ed9b2225474cb3686d5c3ee7a9af11a0c6aa9 | 2ad8f7beef3b6b37e9db4f570e4840c0fe47cc6398547a3ff965ccfe8618a335 |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

### 08:19 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch022 | 85181 / 25720f | 0 / 1 / stopped_no_current_wait | 45229d6554ef9dd4b73c7ce1b8ef16ccdfa41be3900377abe6494a56b9618378 | ec8709f477473e250e8ff8a871bf8b7bd1e8500411e465292edbd5621cb5d40b |
| batch023 | 35646 / 4f3ca7 | 0 / 2 / stopped_no_current_wait | ba4702581c1ad405fed2fc893b5e970dfd28e77f968bb336b1d0922eaaaad334, ff307fb2b454d78da964ed564cfc7219efc192a15c243a644c8bc4227e6dd154 | 736c005a6cc70a4094b4061a1ee5295c4fc2573a011ae781843d1d150dd59f44 |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

### 08:22 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch024 | 31658 / 68f739 | 0 / 1 / stopped_no_current_wait | 5b60c5ba09d2def8b5cb0317d20acfffb6700dd60597c026cdf021795db5b964 | 0bc9b7afb296fc183ebfd1acb770b689ce6f26ea56dc7f17f2e9fc22248b454f |
| batch025 | 52175 / 332a79 | 0 / 1 / stopped_no_current_wait | 4086d30c623c2050eefb0235d824e9941053cb3b92e1f71fbd1dc64566dbcfa1 | 48fe9aae87a85d3161532940902c1cb2ab4ace19eedd738bd5300573343f483a |
| batch026 | 28677 / 9d7b17 | 0 / 1 / stopped_no_current_wait | b68b0d420bb109644528eb9aff5f6b580bb7fdf4223d366158503d22b5915d42 | e3c13b328d5f467f58aefb48631ca4ce285e8c13673ce245518bf4117c1001e5 |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

### 08:23 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch027 | 93599 / d45b9c | 0 / 1 / stopped_no_current_wait | fc6f4e7929dc6085572ed9c1edd4abcc4a00b6ea46239e7c47cdcbd8ad947fd6 | 0adc579f2fb992015cf9a6821e9223e1a2ccb55b3aa126956079e0bfae5b44a0 |
| batch028 | 73892 / a529e3 | 0 / 1 / stopped_no_current_wait | 67a125af8b868e602ff3c5c9efc270e1b1b0bb5abf705c9df2d40ea57302a1c1 | 1f745c1b245c20586db4af021291bba854890c5094d88ffe0820967d1ff3688f |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

### 08:26 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch029 | 30682 / 3305c8 | 0 / 1 / stopped_no_current_wait | bed6f6c35962f0b1e2a07c49eda9a675e7ff684273453cc46e48aa774fe6088b | 69cbc04143a7786dbbecfe010f8834f3a8bef00327253cf741bc084c9ddb95c6 |
| batch030 | 88073 / 9c5cfb | 0 / 1 / stopped_no_current_wait | f1b63a52ff9916a9a4a17def87a75407da693a196c77c0e03b23112bb4bb4883 | 17f17e9cbe0f8449a8d3d45e93f11652d83a3ef2b40841789a1e3622d86cf3b7 |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

### 08:28 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch031 | 58840 / 390754 | 0 / 1 / stopped_no_current_wait | f1633d048d32ba5103c10511d87be5468a980cc9fa2a41bea06e15afefc8dc60 | c1d4550325e9c9141aef8e1fb9f3b92ba5703450fcf62cd6772a6c1df3741ab6 |
| batch032 | 26074 / 761bc8 | 0 / 1 / stopped_no_current_wait | 3308c752b42170a9667ce916bd9a11cbc80a803b5c808e703d629e10b1cde7a1 | 3c2e9a200b82dc952b2fa1c24b0390956cb8749e9cced24035b3f089cc2c728d |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

### 08:30 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch033 | 32559 / 0fc66d | 0 / 1 / stopped_no_current_wait | 685f89706bf16736124255c4d3e548e25edc53132d8c97b85690f1c5af299759 | ef7695a4c62df1b454f222624468a4d29e49f67a5385959faa7fc006fbea708a |
| batch034 | 17954 / c128b0 | 0 / 1 / stopped_no_current_wait | 27f27fa9e7a1fc499fca5bdf4ecee6ec03fffcbc715bbc47205511042ec413a6 | d9184569fe16de80b980063759d0ebf0d9f8fddd9359c3d936807e1e9f25374c |
| batch035 | 39657 / 646c18 | 0 / 1 / stopped_no_current_wait | 82826a45cec017762d5a65e0d409a46c3d1c00e9018a786774903d0539fb689b | 3cd74bcf860879ae07ce8c046cbfc2abdb3ce618c04c86b6063b84946717ffbf |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

### 08:33 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch036 | 49362 / a2fd70 | 0 / 0 / stopped_no_current_wait |  | d29405b06486b33ea7606439366ed492c3ec5cac4691abd937c2f61bbb534442 |
| batch037 | 97612 / 7b25bc | 0 / 1 / stopped_no_current_wait | e83c2d61178821224cc02574df08eba0c5d2cf22f02c7d5e1de7ff8b95715da4 | cdde427dd6ebd32908b042bf7a9f343c8aa2ee313c2674d0cf829de76e70fda3 |
| batch038 | 85649 / f25e91 | 1 / 2 / blocked | a37a78f4897cb690a8bc70d761e67e36398d7b0a70891d1bb0e3bf5b04723a9c, 35309f41aeb5d05cd22b91bb1efd6a013cde476586e7e2eb587e789eac4b87fd | ba806ce693247e0d137a246f91f6d5b71c672274fd969991ae8b70a83610ee72 |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

038真实exit1仅request_not_current_owner_wait；两已published旧请求response及packet terminal均独立确认存在，原owner.verify继续通过，新actual audit为MA209 2022-07-19 anchor a0e120…无response。完整只读观察证据在108输出batch038_post_delivery_observation.json；按root事先授权仅新启039接新请求，保留038失败、不改guard、不重试已有packet。

### 08:34 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch039 | 52426 / c35d3f | 0 / 1 / stopped_no_current_wait | a0e120f117f088eeb8f87e4af90c3bf8c64c0b2f96cda694e750731713b81174 | dbf65300cdefbe973f96d8a6bff4b9a10e69671753fe97c2ac6f123cecd3c3ed |
| batch040 | 85660 / 484edf | 0 / 1 / stopped_no_current_wait | 95acad593299babfae329c195d6f6ef11ca64cf087aeac5763b0b9fe4ecce76d | 2bffb5cfc64c93780477c424756afa711d8f697a9a631444986e17765a201515 |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

### 08:36 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch041 | 40261 / f7d4cc | 0 / 2 / stopped_no_current_wait | 8d8cdb264c7c8262fb32d822a8f474916c7b1256c1bf1cdf0ce5c4ca221a3594, 24f9f4dc92ecd63477ee7f41fd0e9c0beca7da16b83a1031ddc0a38e4604923d | 17a9d797200e174b05b8cfcf9953a3ef164ead4369da9e3ae94f3037e4c3da09 |
| batch042 | 45767 / b828aa | 0 / 1 / stopped_no_current_wait | 554911de9bdbe4efb9a15fe82188f72324ee64fbf4158238cde5e23a0d9ffa83 | 8d16ad2377b04ae337ec0c32df18e5ccbbb96dbc5512e60503904937cf50ee13 |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

### 08:37 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch043 | 17388 / f8539a | 0 / 1 / stopped_no_current_wait | 49e9542f1c1edf4f7883ed27866ec48a63a4c6684276f520744fcc9e955cbba1 | 0eed2dee2c8a060e57606b3e16f29f1983f09d807f4e7f2978f9116c04c8fb4f |
| batch044 | 97505 / 5f247f | 0 / 1 / stopped_no_current_wait | 223719a850e1f833986ded601e47a9cb03aefa70a4d6be93a9188b3f65f84bdc | df70c7fd55eedbfce5f280a4ff9177f8199d2763614c6ef80a784724261b1bbf |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

### 08:38 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch045 | 52848 / 87c66c | 1 / 1 / blocked | a26ef32a22ad383c18888766f787a5e2943e645ea988b8bbdbf71c34f73e6d2f | bbda8a17a9bb5e37b9253ebb510362c99174b20cc1b42609f567b5dfff2a7b5c |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

045真实exit1仍仅request_not_current_owner_wait；a26…实际已published，旧response及minute packet真terminal存在，owner.verify通过而新actual audit为SA301 2022-08-10 full_session af627…无response。只读闭包在batch045_post_delivery_observation.json。按root已授权的新请求续接规则新启046，未重试旧packet、修改guard或新增金融attempt。

### 08:40 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch046 | 68713 / 7e3933 | 0 / 0 / stopped_no_current_wait |  | 332c82550a852757e17f6c478183e50772e07811f28523a70831f72f3fe304df |
| batch047 | 23202 / 5ed583 | 0 / 1 / stopped_no_current_wait | cf4326e511372e3f55fe17a3e57f01714cdd3bcc503b2c6c014ff01208a0b366 | 72e4213dce3f80793ffc1db2117d9213df43ebe85cd0d1ea1a0ebd4dbb9b906c |
| batch048 | 83004 / 2a204b | 1 / 1 / blocked | a9861c0a08cdba12a385626d98b3265269a6bf429cd9b1ecb7474e4f82202dea | 25b4e38e45b1f422275efbde7a57b33b4cb184d14278c1819ef356ff55526e62 |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

048真实exit1仅request_not_current_owner_wait；a986…已published、旧response/packet terminal存在，原owner.verify通过，新actual audit为jm2209 2022-08-19 full_session 182644…无response。证据保存在batch048_post_delivery_observation.json。依据root原授权只新启049接新请求，不重试既有packet、不改guard或金融。

### 08:41 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch049 | 45367 / 501e8d | 0 / 1 / stopped_no_current_wait | 182644fba24571c2e3ad8d26bc0927c61040f4bad785584c1993937fb3102f99 | 8a8ce467da866d2d53ce6e92facad0421f1bf30ec021d839f2ac68cdd55a1de2 |
| batch050 | 28757 / 83b906 | 0 / 0 / stopped_no_current_wait |  | 9b39f0f6b107e758d562cb1c09819d9e08f0236966ed882158263b089850b426 |
| batch051 | 49924 / 5ac9cf | 0 / 0 / stopped_no_current_wait |  | d27ec47ccaf9adaaeb3dd7a22bab9322de43124204d41a4e6cc599d8c3d4c779 |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

### 08:42 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch052 | 48674 / 4e78a1 | 0 / 0 / stopped_no_current_wait |  | 5c3dbf0db06736f2c7bcc7681cb29bbe7f4a4d6a6094674d7e66a7eead2270ae |
| batch053 | 92010 / ac7f10 | 0 / 1 / stopped_no_current_wait | ae0c6fe7affeb60671b16b509d42900f6ada8ded7e8a747d0456c0389e6f5fc5 | eb0db24eab7e430435b2777d95f67a4ee29062933d1b7972f6998327a47d930f |
| batch054 | 71284 / c7ea53 | 0 / 0 / stopped_no_current_wait |  | e63426175a99fff41fa2257a161ccfc06b5ebaef327e2d6071767e927833eeae |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

### 08:43 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch055 | 80735 / 81e595 | 0 / 0 / stopped_no_current_wait |  | 1ef75d0e7115ca760cb9ec1d0d083189d4a191a3dee4b1717e7ef770d2fcc184 |
| batch056 | 11796 / 69e00a | 0 / 1 / stopped_no_current_wait | 63d342a377d62ade4a84c2b887f4c352a10be15738e24b93ebc33f33456a2ea9 | 136d6f87792aaae74b6ac191d7c958ba11c7c2528b5079db3d06be8a1d0000d1 |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

### 08:44 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch057 | 30201 / 03059a | 0 / 1 / stopped_no_current_wait | 26d1cc232962f5a87e0648ad67c5dfbd2cd925783f49ec60004920b0ccec4e2c | e23fc0f5aabc63f01119da854dc71ab099026905b8fc1e4b1859e5e538f353b1 |
| batch058 | 10498 / e4b837 | 0 / 1 / stopped_no_current_wait | 59376f46cf12f9c2937281c222b13e1b889e5356c9c5e2ea2a9c561049eddbdd | 70a1ec7325b22490330a8cb2ba2475b7afab8289d832e3bab15c60c2019c39d5 |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

### 08:46 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch059 | 26051 / 130bfb | 0 / 2 / stopped_no_current_wait | 770dac2b66f0c070b5a6e5c9c1b1b0e24dc767f413af094f69a725b399f2c885, db7701a354b14bda6c85e088ae5260165f03c7e0baab0d6aa823cd19a8ad9d85 | c9dfff905f57f7b6af31702b4d48627e60e6fcff833e34e9049e841fa11e6e02 |
| batch060 | 41000 / db91e7 | 1 / 1 / blocked | 4f1e1f996858433003da5bda05cceb329ce252d2f40f32262a196894db1dace0 | 3e9078375217eb3de8dbe28e843c9d5858bafc9bc4503b78a8349d5fd98bc8ec |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

060真实exit1仅request_not_current_owner_wait；4f1e…已published，旧response/packet terminal存在且owner.verify通过，新actual audit为MA305 2023-03-14 full_session 179ac…无response。证据在batch060_post_delivery_observation.json；按root既有授权只新启061接新request，不重试已有packet、不修改guard或金融。

### 08:48 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch061 | 86347 / 71054e | 0 / 3 / stopped_no_current_wait | 179ac174b169636576714bbe4f20d1d649857b4b08a442488ae97e8f9c132097, bd024c6c432149085a7de13aefcc8cbbf04f505ae2f2611251d811458ae34edf, 1852d3d9b767c214456334183c36e4abe37fb3006fb456ee4a7b1c578b6348dd | fc1c9b3d101503d345452744189e93f880c998ed666858c8e19bc568097f839d |
| batch062 | 70308 / 8b4201 | 0 / 0 / stopped_no_current_wait |  | 154ffae1f6b50ead2ef89508336a1373449c8ca4158c0398905a70fc759585ca |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

### 08:49 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch063 | 33853 / 86f79b | 0 / 1 / stopped_no_current_wait | 1adb608ddf3e473a9b86108d94a243a864631798ded0b9eb73547398e8585db6 | 262382555828d2ce448eed0a7a113c0bdded57eb0aa1181965f3a826f068a063 |
| batch064 | 97152 / ed0304 | 0 / 0 / stopped_no_current_wait |  | 80f8af2986c7aa046f55a48d50cae4d2e36a76af19dda02e799ccc5b0b657fde |
| batch065 | 68353 / a3db7a | 0 / 0 / stopped_no_current_wait |  | 961c6335bacadaa9cb759a990ca617a746451ca0c51c3d54a37df206de404d3e |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

### 08:51 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch066 | 96843 / 598ced | 0 / 1 / stopped_no_current_wait | 1d31d2019ff4852df8fe588f437af253604220e50989e992d5148ec6a2d565ba | 38d63a46deb94a17624a6a0522bb3ab572144c6c995dfd44ecdd95621a65b331 |
| batch067 | 71441 / dfd13e | 0 / 1 / stopped_no_current_wait | 969e86c18930c903ef8457761dc3f616bbac64af22779d7ddbff5fd5f3388b10 | dcdf7693ebca09cc678002a404a3fabd13e89f38a5f139c962afa0f8dd605d92 |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

### 08:52 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch068 | 59368 / c88159 | 0 / 0 / stopped_no_current_wait |  | 9a127cb0b031b7c206b7432683506f28dd2a62e7473747b2b879bc229af6b473 |
| batch069 | 67207 / 0b7eb9 | 1 / 1 / blocked | e8b6fa2bbc2b97bc1b9b84a40c082ad1372437e5989faee92a79f8f208d3e316 | fe2596d27b5b794223e43c81300b43b9473007dd0c26f25dd68f01d77aac6014 |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

069真实exit1仅request_not_current_owner_wait；e8b6…已published，旧response/packet terminal存在且owner.verify通过，新actual audit为FG309 2023-05-23 full_session 9a155…无response。证据在batch069_post_delivery_observation.json；按root既有授权只新启070接新request，未重试packet、改guard或新增金融。

### 08:53 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch070 | 11600 / 1ad8fd | 0 / 1 / stopped_no_current_wait | 9a155fa052bf48034b44b64da5eababa33158e3106f7642adcbe60d98ed164e0 | 1e1e6b224d0a5fe8f12619ca8a4da9df0132436df821cbf00fd09ea55a74df0b |
| batch071 | 43584 / 1eb100 | 0 / 1 / stopped_no_current_wait | fc0737c7abcebee7d93b66d7004d4117845c4f9bcecd37d744b3cb0258f2eec9 | c4ee0522ce006219eb275398dfd8b5d013a426c3086ab786977120ac9bcc449f |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

### 08:54 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch072 | 30147 / 60b301 | 0 / 0 / stopped_no_current_wait |  | d65276771d70a13094d8b813974c05c0289f759e950ba7e851107c96c593e1b3 |
| batch073 | 15309 / de17f8 | 0 / 1 / stopped_no_current_wait | 7c6e26c955dcb10df7368968063feda79cfb5fcb1be486cdd9022c039b302e5b | 65e13f0ce6bb3554878fb1b1d28c33c81d216a3813490abb0d1508d10699323f |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

### 08:55 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch074 | 67101 / ab4f6c | 0 / 1 / stopped_no_current_wait | 1777f0725ee1a69d6ee6a2a886e6a4ef9b98cb2e9bd1083cf9361a0995b8941d | 6e6445c0b8d4263959115a4ca9cf07ed6ad3e6f01c3e81a631895220b9020791 |
| batch075 | 37833 / ff8bce | 0 / 1 / stopped_no_current_wait | 10f2bbec540c701116577b5951aef2e742a4367fc8dbde41b17002f8caca3794 | 56e55f269ecd56f6db1e6464c07b365ad3333c6265b0dbbb547bfcd459e3358f |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

### 08:57 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch076 | 83435 / 303fc8 | 0 / 2 / stopped_no_current_wait | afe11f98a5e6825646581d8ac2b41f209a766ccd4f6bb75f02101c7549511090, 2cfcec0bbbe2e197927f5ad33500baa7feaa2cb86b28da8c55d97329ab5f5171 | 3b4b462c01d5af983c05d6da811bb675cc36b5001afea1d16f705b38a9adddc2 |
| batch077 | 46224 / fd6151 | 0 / 0 / stopped_no_current_wait |  | 67fc0db90cc8978fa55cc324bc9914e90f4d6da376b69ed4f4fddf087d2d10f4 |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

### 08:58 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch078 | 19601 / 0c3ebf | 0 / 1 / stopped_no_current_wait | 371a84e409c7f6c5d8da47069365c17a005cbf07eb6a6bc3694e85fb9607dece | 77e20d4bbcfc780eeb8a08480e051172bee858317d8cadcda21afe5291496a52 |
| batch079 | 76868 / 5a9da1 | 0 / 0 / stopped_no_current_wait |  | 8f36c7ec7bfc069d7034e0a3f5ba1471413182bf72b371740a15a066620f1f2f |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

### 09:00 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch080 | 81486 / c3a7fc | 0 / 1 / stopped_no_current_wait | 5ed3fa0023716c797fee76bd9c09363e9c5803d0397d63c737fe899d9f8b6ea2 | 1edf5eb0aec47faabe77c916e9a9d3c4e8d9d4b7729cc3bee65e51584a66ab5d |
| batch081 | 91348 / 11f6e9 | 0 / 3 / stopped_no_current_wait | dfb1a338c3f396e152ab92b16b3f8c6c0a4fd76b7bc338261f6b31dc97265b3b, 208af8e28269d969748d9941662dfc5464802595a19ae49def0b2a7009d00d4c, 332d347f840ee0c0370a49900bce673366c3f72b6778cfd5f5271fa7fb697843 | 96a3b0377a70e6dd11bffd076e13a88982da6f484a58884f0d7370ff0f78fa19 |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

### 09:03 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch082 | 89035 / c57627 | 0 / 1 / stopped_no_current_wait | c9670ecfcc234d3bde104323f7ff7d424cef9c08286acfc1a0d713a75afd210c | c3c0905ddab3541ed0d32164418f2e2ff5ed3f71f160dd31d13adbfaa1f158ce |
| batch083 | 77897 / c2aff1 | 0 / 4 / stopped_no_current_wait | 8f8e7c7db0b492e200911f30698c2a6aa6a243efa1f9ceb952ad39b461fa5d42, bf66b9aa700ec026e3c04d681adec83de822c8f3bb170d2b45af0ffae5e33833, 398b2b30207cab881376a770c35ba5c15538f9d3f85e669b9689c759879a3a60, e46f1cb87c6c002e1e9076bd85727219f41481cf175c4436fabef8960c116a0b | d68eab1c08710694462bc573fdfb73032845616eba0a3d4d752218ef4ae3344a |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

### 09:04 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch084 | 76931 / 37e5c4 | 0 / 1 / stopped_no_current_wait | 621ddaf5046183c6dc38e31d7cc547b28e6a07e865f995c545b6110512268a4b | 1c7e455f5a7cd154d6c9f95ad9f4464354e279d011c709a168c9d0c4e47b8fa0 |
| batch085 | 6873 / f071e6 | 0 / 1 / stopped_no_current_wait | 00a26955336fe5f267422539408118179e209ddf9492770945db1789f8352d9a | 04a08e3c4ed786dc96a69aae49946e6b45bfd15a27110aee3ec008fbf82ac18e |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

### 09:05 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch086 | 85508 / 22c4dd | 0 / 1 / stopped_no_current_wait | c0954aab9bc8a0361710fca23c37eadab909b484b40c34a66267369688be59e9 | 9b32c00847614b7b6a9da95602da73abc8f00eff92dd1ec00d711553bdec33b5 |
| batch087 | 85498 / 937fb4 | 0 / 1 / stopped_no_current_wait | 7e2ec7fd6184727d39796626e6c9b24a8b1812032a9ca1f719f863a4ccc622a6 | 8c24a11933d330f1048ac20aae82d059ad0c81d54b6645b4a41a1e6b32b83a33 |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

### 09:06 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch088 | 59290 / d0f705 | 0 / 1 / stopped_no_current_wait | ddb50fa5ce3882fa65c3b79becdbcb4d3c9ce8c31a899d78bfcd12c9fb713e87 | e772749c8ad9007c486cf4f7eb72b56b558eead18c89234e18ca921b9127a0bd |
| batch089 | 35696 / 03a949 | 1 / 0 / blocked |  | ee075dcb42adee373b8596673bc59eceddc7c7f92cddf148e88a95304920934d |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

089真实exit1仅request_not_current_owner_wait且0连接/events0。独立核初始jm2401 e2f68…response实际存在，SHA32378084dab76a91ff9075585986fc527908425281f839674cf2e8bd366527e5；accepted-local不写events，不能判交付0。原owner.verify通过，新actual wait为lh2401 2023-11-30 full_session 2ba07…无response。观察证据在batch089_initial_local_delivery_observation.json及实际tool chunk3fdcb4；按root既有授权新启090接新request，保留失败，不重试packet或改guard。

### 09:07 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch090 | 99795 / e8ee22 | 1 / 1 / blocked | 2ba07c7c7f6f2f1401567fe26ac2570f5052485ba96f100b2115b7ac51ebea67 | b93d1d6febaa5355f161a394dbe25315ad31359fbbc8066876de98870934b885 |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

090真实exit1仍仅request_not_current_owner_wait；2ba07…已published、旧response/packet真terminal存在、owner.verify通过；新actual audit为CF401 2023-12-01 anchor d6d0…无response。闭包在batch090_post_delivery_observation.json，按root既有授权只新启091接新request，保留失败，不重试旧packet/改guard或新增金融。

### 09:08 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch091 | 72879 / 1c2c81 | 0 / 1 / stopped_no_current_wait | d6d0be9292e7ecfb51956d45237e65fa19a79466d52a719761009b7b1e97d0df | 8e350de08a584672eeab439b195e4aff3379f0ec81109faf64da265c1266a03e |
| batch092 | 6373 / c926c4 | 0 / 1 / stopped_no_current_wait | 65504b43ce6d662de27a59113b82d16db1d677d20031bf455b22cf0bdcb3fa2a | 7ef3224a3d784834f970cfd5ae58095ee38fc27d53bc2bfa2ac8fd5bd298d635 |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

### 09:10 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch093 | 43032 / dd2f0f | 0 / 1 / stopped_no_current_wait | 0c9cad5ca55b10e06a62dc3f88af2a7895ab9c6da1711fc2a0b5736fb1df4d53 | b6dae7afee391f2f063bda85ef44f05fb6611416500804c21e15c8cf99828b37 |
| batch094 | 62462 / 78d691 | 0 / 1 / stopped_no_current_wait | 35cbc94631e7a8cf65fd8cd7de027f8d511f38f55883f391f4eae35fdd6dd72b | 238058860e651601cea13ab31715243afd0e6ddbb526ab344edbecedb6d12044 |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

### 09:11 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch095 | 42215 / a245d2 | 0 / 1 / stopped_no_current_wait | 34e3d9300cd801ec35be516c6465f4accc6c9a3c0a7ea8f22bc05fe0b2695afc | 366de45a28916bc72bb13084e3bfa08cc9798a7c34b946e1b70024ff71c1c3c3 |
| batch096 | 17232 / 7f4038 | 0 / 1 / stopped_no_current_wait | 4b36260cf34c7d976e617c618bdbadc257628201cfc87e10db139297d8938b56 | b1330557882b366c837aed1d9cc8aa8f9f36c969aa8e6d2f9201005f9ddc237e |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

### 09:12 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch097 | 84608 / 558463 | 0 / 0 / stopped_no_current_wait |  | ad706a3f33620f708d557133b067d9ef775668a928b47fccaa234bf7d0be8527 |
| batch098 | 22751 / 548275 | 0 / 1 / stopped_no_current_wait | 4bf8f96381f3852be726ea1b68b196f94b817981a918bf2db43b9fd613f97c43 | ae10efc74472f6f6add63b5ab9e96b45f7ba80f4d1174c82c7dc0e35467b04f0 |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

### 09:13 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch099 | 37415 / d639c6 | 0 / 1 / stopped_no_current_wait | 6a434080c1f5ca99c2431131beab2319e0a0161455d882e358bf3260f86f179e | ab40c5a9f6a547ea4513ceb684755be868c2fbaeb95110c54ac6f16fa0611523 |
| batch100 | 99638 / c4e040 | 0 / 1 / stopped_no_current_wait | ca5c9bc82dea305604486f2843a2573113e31cbf33f5ee3f7ac7955e111b6441 | 279adac143f65ca8bb4c2634d2beaa8633936d7742a6c4c5c62dd4835a996cb9 |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

### 09:14 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch101 | 65065 / 76bce4 | 1 / 1 / blocked | 245b4c1af08a28fc5190ff6b7acc656dd45e9a781393ef7c60eeef4b50653285 | 9fbbb7b9a8e4bb5cf1f07fa4d1ca596569ed03598e4ef2a685bb51128e2e1d51 |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

101真实exit1仍仅request_not_current_owner_wait；245b…MA405 Apr12已published、旧response/packet真terminal存在、owner.verify通过，新actual audit为fu2405 2024-04-17 anchor 5d6…无response。证据在batch101_post_delivery_observation.json；按root既有授权只新启102接新request，不重试packet、改guard或新增金融。

### 09:16 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch102 | 90213 / e9d1ee | 0 / 1 / stopped_no_current_wait | 5d6dee57594724d1c15c50c7184f1ad543fc7691fb592e56b6c21a4af1f3141c | afb1ee5fdf67a95ec5d22cfc9ebcabfcf533dc99933a29390d553f3353b83c74 |
| batch103 | 14420 / bafb35 | 0 / 1 / stopped_no_current_wait | 7f423de04e6f86b14d85c509dd89d2bf543f72148955793999cb3858e5d63de1 | c559d4065558001258ca51984a2439fa9842c821a19aba71f4de1002b41b7908 |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

### 09:17 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch104 | 7393 / 7f5329 | 0 / 0 / stopped_no_current_wait |  | 6d27b843c00d0a2b5fb1fad012b59e329ee9329a391c4535f3eee5eecc375b39 |
| batch105 | 64001 / bc23fc | 0 / 1 / stopped_no_current_wait | c30bb5c4a029be9348cff726687b86af63cd2c96acfb9ebe67269ba211a350fc | 000cb227b43c3e21087f0be803c5e55bcf433a9cac1dc932c2db6b68e458de2d |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

### 09:17 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch106 | 15589 / 4c43ba | 1 / 1 / blocked | 140c4f1deb4302eed495e278aa190a90671425cd35a3f802057275ba2113af37 | 299a5d8a7c1fca69b783d31cad13e9174ba226c4763899d42b403a7af2b0fdec |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

106真实exit1仍仅request_not_current_owner_wait；140c…cu2407 Jun21 anchor已published、旧response/packet真terminal存在、owner.verify通过，新actual audit为lc2411 2024-07-03 full_session b60…无response。证据在batch106_post_delivery_observation.json；按root既有授权只新启107接新request，不重试旧packet/改guard或新增金融。

### 09:18 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch107 | 34003 / cd493e | 0 / 0 / stopped_no_current_wait |  | ab368ab7e2a90623339403def75ec91f4b8943034b5feb2521534baa20768979 |
| batch108 | 74871 / 0ff7b9 | 1 / 0 / blocked |  | c5b7c52fe65b0abd503595959e049fbcc30d030c7a3b4339be1c615b6fb1a139 |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

108批真实exit1仅request_not_current_owner_wait且0连接/events0；初始lc2411 Jul04 ef2…response本地已存在，SHA5e9e728ba1cae9cd319143bee43ff451714ce3dbdd389452a767bebf799a3a8d。owner.verify通过，新actual audit为FG409 2024-07-08 full_session e93…无response。证据在batch108_initial_local_delivery_observation.json及post_delivery文件；按root原授权新启109只接新request，保留失败，不重试packet/改guard或金融。

### 09:20 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch109 | 50568 / 761214 | 0 / 1 / stopped_no_current_wait | e93ae1cb5f4b93764a3d20fcf7862e1e0e354650fe45e72a92bd15d0b16fc243 | a48a7005abcd41e5079d00c34cc61e43b8160ec0810ac91bfbcade9e3ce185cb |
| batch110 | 23575 / 80a2a7 | 1 / 2 / blocked | 6aeaadffd3bea86fe651659b3a528b847aeb5199e8eb94722fd8a1e1812fe577, ce2b2a5ef8ced4a12f6a1ecc816c9e2a4db6519e1e8afaafafe86b8568f6fb05 | 68e7bdb78ff9ebe384392c4a72abd7c0de0e3434f56a51dacf2a3bc4507f6fd4 |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

110批真实exit1仍仅request_not_current_owner_wait；6aea…与ce2…两request已published、各旧response/packet真terminal均存在、owner.verify通过，新actual audit为OI409 2024-08-14 full_session 4c7…无response。闭包在batch110_post_delivery_observation.json；按root既有授权只新启111接新request，不重试packet/改guard或新增金融。

### 09:21 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch111 | 57143 / 100d6a | 0 / 1 / stopped_no_current_wait | 4c7de304e414ef85624e2ff026e13a572120b44d9c3e5f794cf4cfd81f18dced | da0503f6ef8008cba280656520a6c0872125166417f91655a9369baa74ba1669 |
| batch112 | 55070 / 7e2377 | 0 / 1 / stopped_no_current_wait | d06f0d8a7bb8d72b3592c7a21a6744c5c4c636d588e21d18d2d502a797c648cc | a9e3fd3448237b32ae57c7f0710af47e176c8586d687449e4e3f16bd61ebf4d5 |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

### 09:22 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch113 | 15641 / f61e19 | 0 / 0 / stopped_no_current_wait |  | 4d7f96a575b57db72ee15908774495eaae72d6998f02ab25bdb90a40e25912fd |
| batch114 | 46333 / 7a3cdc | 0 / 1 / stopped_no_current_wait | 85fa4987c84a534d4a621cea7f640ff5fce659dbb110e8941a0695087d61e477 | f4a410467480e6bc9fe8bcbb43726ee98b06e7c244c30942549b141f20f08ea7 |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

### 09:23 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch115 | 34481 / b8644c | 1 / 0 / blocked |  | 5cb120ee4886769940b06466ed0075f6e698e4bef3104510495a6ed60e608f42 |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

115批真实exit1仅request_not_current_owner_wait且0连接/events0；初始si2412 Oct24 0763…response本地存在，SHA6a4f8dfa7d212f95e5dc49c41b2d7fa9430f00b0984cb98cd5533a828a52acc6；owner.verify通过，新actual audit为FG501 2024-12-12 full_session 6ebd…无response。local-delivery证据在batch115_initial_local_delivery_observation.json；按root既有授权新启116只接新request，保留失败，不重试packet/改guard或新增金融。

### 09:24 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch116 | 79721 / ecfaf0 | 1 / 1 / blocked | 6ebd3d609d8232a7cab3dc6a5e7c9022f77d523c691b9df72a2e28634d832209 | 0840fb4fcb75212148f4450120056cecbc7e6dcbfd4d7d64f754bd1a43e957e6 |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

116真实exit1仍仅request_not_current_owner_wait；6ebd…FG501 Dec12已published、旧response/packet真terminal存在、owner.verify通过，新actual audit为sp2501 2024-12-13 full_session d55…无response。闭包在batch116_post_delivery_observation.json；按root既有授权只新启117接新request，不重试packet/改guard或新增金融。

### 09:26 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch117 | 53574 / 24d537 | 0 / 1 / stopped_no_current_wait | d55da0c3bdd3c2c157e37a33e38057d8d07f31464209356e2e8ec55726bf82a2 | 6559390f473b554ed2e8f03ecd6ad23d16e5298c5a469aee2851dca2af943d51 |
| batch118 | 16709 / 0af7dd | 1 / 2 / blocked | e76422007bd2231c7554cac42a0d46aed9988af0b71754b833593dc314578214, 1efef4a51fd1043011ce5116dc29ba4e5cc068569988c9e39b03e32fc8b7ac53 | 411efd8cda48d7bc460f21936fd814ff0c6b8b5b59a2b3d81941fa27971fc52a |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

### 09:27 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch119 | 28925 / dc18f5 | 0 / 2 / stopped_no_current_wait | 4d76f40fad99baa2f3513af7c8e203886109a869d2a6e1ad1be484244967e203, b5392db97ecc61b153dd4c2cde210f84dd5d1e7170bd57fc2f103f9ed1053f81 | 048297542b649cfbffc915e56676c20b85e733032d2ea73990c5cd3155e5290d |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

### 09:27 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch120 | 55842 / 42f2a4 | 0 / 1 / stopped_no_current_wait | 9e206378affdba39090408f4b9286d812586b1a7452be0bf91dfd02c713f7870 | d3f4e3f564e301e7c3918e1204422d76daab361f9bcd82dc728877c00deca902 |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

### 09:28 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch121 | 41159 / f157cc | 0 / 0 / stopped_no_current_wait |  | a71478771d34dcac9638bf0acba646131da6ae0461609662c8550de9bac55c1e |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

### 09:28 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch122 | 5664 / 3f1d28 | 0 / 1 / stopped_no_current_wait | 3d059691435c55921aa148d9ddc823ebc08884e98b0d90024989604df05e46cd | 3c8eb5f244dc249554427598d4447eb7554b3c82a8f1daf34ed3a7f84f36df88 |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

### 09:30 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch123 | 41314 / 0ea309 | 0 / 1 / stopped_no_current_wait | 9b86556b89c58e9f0e4271a4d97b81bebf45295ea72066b7d7c416fc768d0ba4 | 7f97e8c6036b41dc8cc0ced7f730d926be0c541ff02ea33c27ba8d44f78c3780 |
| batch124 | 58898 / 101367 | 0 / 0 / stopped_no_current_wait |  | 0cb30d91228a3d1515b47b87cfe605fcabcc5d70ebc7f8a6b7faf2b236b8f9e4 |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

### 09:30 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch125 | 54603 / d4309d | 0 / 0 / stopped_no_current_wait |  | 9b1d511c85404780709659936ee18e39170c3994b445f58d9b9cd3f721a808f2 |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

### 09:30 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch126 | 77898 / 80ce4a | 0 / 0 / stopped_no_current_wait |  | bc7d7f1859a386104b9dcb13819c1d77cc810a33716d0c0d10d22426f6e9c994 |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

### 09:31 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch127 | 98712 / fdbb34 | 0 / 0 / stopped_no_current_wait |  | 5f9fcec0dfa5b707f2b645f21ec00bf28fca39705af477e0b7d26a239e183fd7 |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

### 09:31 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch128 | 49251 / af5484 | 0 / 0 / stopped_no_current_wait |  | 0f4c0d4fb8846063d4c915755304558aac74c9e9f8ad7ffe65907a3a31b86be7 |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。

### 09:33 已观察driver终态追加

| 批次 | tool session/terminal chunk | exit / 连接 / 状态 | published request SHA | 外部runtime sidecar SHA |
| --- | --- | --- | --- | --- |
| batch129 | 58492 / 0f6552 | 0 / 0 / paused_budget_or_four_connections |  | f1486ef0e5d6f099f7e95e1d57785543d08ba52774b0b7bc995b3a774c917c81 |

以上仅计已真实观察的各driver终态；完整tool证据和外部sidecar binding位于108输出目录同名JSON。未轮询root金融handle、未开新金融/训练、未改源或资格、未重试packet；后续仅按真实owner/audit继续新的未交付请求。


### 2026-10-18 09:32：原预算暂停后的操作员收口

- 最终实际终端为 **batch129**：自有 tool session `58492`，initial chunk `d352b5`，terminal chunk `0f6552`，真实 `exit 0`；journal 为 `paused_budget_or_four_connections`，provider 连接 `0/4`，events 为空。该批针对真实未响应请求 `7422216c316b1eeea381af05e31318dfbea8903ffe77c31c6c9b6c7cf2c087eb`（`CF505.CZCE`，2025-04-11，`full_session`），未签发 response，已准备 minute packet，未启动 provider、无 `terminal_observed.json`。停止全部新 driver，**batch130 未启动**。
- 原金融 run `81ffc8f704ce4c5eb701e97e0397b12a` 始于 `07:43:14.055881+08:00`，7200 秒总期限为 `09:43:14.055881+08:00`；840 秒完整 provider 启动余量边界为 `09:29:14.055881+08:00`。`stage087_off_data_scope.py:656` 的剩余时间取单次等待 1800 秒与全程 7200 秒的较小值，`:693` 的 `remaining<840` 在 provider 连接前暂停。129 为零连接，因而不是四连接上限导致暂停。未修改这些限额，也不通过新 batch 绕过。
- 边界后 batch124–128 都是 `exit 0 / provider 0 / events=[]` 的本地已接受交付：分别保留初始请求真实 response 文件及 SHA 的独立观察记录。原 driver 的 accepted-local 路径不追加 events，不能将 events 空记为未交付。最终129则仍无 response，应严格区分。
- batch118 实际 `exit 1` 与两次 published 结果一并保留；两个 response 与对应 packet 真终态均在，原 owner.verify 通过，真实 audit 已换新 request，故按 root 已授权的“已交付后观察切换”口径续新 batch，未重试旧 packet、未覆盖失败。
- 最终 closed 范围：本操作员拥有 `batch002` 与 `batch004–batch129`，共 **127** 个真实终态文件；其中 `exit 0` 111 个、`exit 1` 16 个。`batch001`、`batch003` 为 root 所有，不将其 tool 终态冒认为本操作员观察。本操作员 journal 连接总数 **114**，全 run 129 个 journal 总连接 **116**；全部 recorded journal SHA 复核一致。
- 全 B 数据等待目录实存 **159** 个 response，且 159 个 receipt 指针 SHA、owner run、qualified_research_data 均一致；当前未响应请求仅 1 个。所有 batch journal 合计 **116** 个唯一 published event，本操作员范围为114；159 是整个 run 的真实响应总数，不冒认为操作员独占归因。43 个响应不在 journal published event 集合内，不能用事件数替代交付总数。全 run117个 packet manifest中116个已有真实 terminal；仅最终129所需packet未执行。
- inventory：`../outputs/stage108_b_off_wait_operator/final_closed_batch129_inventory.json`，SHA256 `3b3ce5a440b12a21c4f01690eadf933a0ad2e679c3dd03beed461b82c282d2f3`，逐个绑定 original journals、实际 tool terminal、外置109 sidecar、response/receipt 与 packet 元信息。109 sidecar 为新增外置来源证明，**不声称原 financial context 已含这些 sidecar**。
- observer 优化记录：root 允许在无新 wait 时以最多50秒的只读 audit mtime/内容变化等待替代盲等；仅准备过 inline 模板，**未实际执行**，因为每次真实终态后都发现真实新 wait。不修改仓库 observer 源码、策略或历史时钟；实际新 batch 均先完整核验 owner.verify 与最新未响应 request，未空启 driver。
- 最新 owner.verify 在129收口时仍通过 `passed_live_identity`。操作员从未 poll 金融 session47648，也没有读取金融中间收益；driver预算暂停不等于金融成功或失败，原金融终态由 root 独占观察。本操作员新金融运行=0、新训练=0、源码/策略/数据资格修改=0；不修改 LINE 或 registry。
- 本次是否过拟合：**否**，只按固定数据资格和预算补当前原进程真实缺项，未根据收益选择数据或调整模型。继续操作是否有价值：现已**不应继续启动 driver**，因实际 provider 余量硬闸触发；保留已交付数据和未完成请求供后续合法资格审查，不把不完整过程作为可训练或可发布结果。期末权益、收益、回撤、Sharpe、滑点、交易次数、胜率均不适用，本操作员不新跑、不读取该金融中间指标。
