# Stage231 真实账户定量的发布前环境与退出闭环检查

- line_id：futures_trend_stage819_intraday_rules。
- 开始时间：2026-09-08 16:38；本记录建立于 17:00 后（北京时间）。
- 用户目标：继续朝部署实盘推进；不是扩大 alpha 研究范围。
- 工作区：`.worktrees/live-broker-account-sizing`，分支 `codex/live-broker-account-sizing`。
- 基础提交：`d492ee072aa5a9d71477235d79f17d2a5db59db3`；候选修改尚未提交。
- 是否重要突破：否。执行安全与可复验环境修复。
- 开始反思：不过拟合；不修改策略、风险或压力测试参数，不根据收益筛选版本。继续有价值，必须证明真实定量后仍能安全退出。

## 1. 外部资料与判断

- [Apple 调度与 QoS 说明](https://developer.apple.com/library/archive/documentation/Performance/Conceptual/EnergyGuide-iOS/PrioritizeWorkWithQoS.html)说明调度条件影响 CPU/I/O 等资源分配。结合本地 trusted runner，压力套件的既定启动命令包含 `/usr/sbin/taskpolicy -a`，普通套件逐组独立进程执行。
- Stage230 的 52 组是单个 pytest 进程，并未采用该压力调度命令。此次只做一次保留原始产物的固定参数诊断，不修改 pipeline 或阈值，不反复试到通过。
- [vnpy_ctp 官方 CTP 结构定义](https://github.com/vnpy/vnpy_ctp/blob/main/vnpy_ctp/api/include/ctp/ThostFtdcUserApiStruct.h)分别提供 OpenDate、TradeDate、TradingDay。没有足够证据证明夜盘 OpenDate 必然等于其中任一成交日期，继续否决日期 OR 猜测。
- 数据库隔离使用 [SQLite backup API](https://www.sqlite.org/backup.html)的一致性复制，源连接显式 `mode=ro`；没有复制券商账户状态或凭证。

## 2. 原始测试依赖恢复

- 将原 checkout 中两项已经存在的父级 builder CSV 复制到候选 worktree 的独立、非 symlink `backtest_outputs` 目录；没有覆盖既有文件。
- 结构池 24 行，SHA256 `dc389dce4f6d404061127390deea04e15b7cd641f6bb6c265f9721a7c65fc309`。
- AI eligibility 900 行，SHA256 `63c976a09f035fd1b7e57401de5da2d48c2b9538382ede8fe28fbc71d6017242`。
- 源文件复制前后、目标文件以及测试后字节一致；隔离恢复后 Stage037 两项测试通过，耗时 3.65 秒。测试另生成 19 行 universe、468 行 eligibility，均在隔离目录。
- 这些是原始未冻结测试依赖，不是当前 Top10+fu 正式池的替代资产；不能把复制回执冒充 immutable material 资格。
- 回执：`examples/portfolio_backtesting/backtest_outputs/broker_sizing_test_dependency_copy_audit.json`，由 Git 忽略。

## 3. 一次固定压力诊断

- 运行完成时间：2026-09-08 16:49:25。
- 参数保持 20 品种、2000 tick/s、60 秒、writer delay 25ms；输入共 120000 tick。
- 启动方式采用既定 `/usr/sbin/taskpolicy -a`，直接调用压力测试相同 `run_gate` 入口；不连接 CTP，send/cancel 为 0/0。
- 结果：passed，全部 18 项检查通过。
- ingress P99 `0.066833ms`，最大 `58.803375ms`；durable lag P99 `72.458166ms`，最大 `220.040666ms`；丢 tick、gap、writer fault 均为零，全部持久化。
- 既定 durable lag P99 阈值仍是 `100ms`。Stage230 的失败 `112.661875ms` 保留，不删掉、不覆盖。
- 原始 tick journal、时延 CSV、完整 JSON 和 SHA 清单保存在私有目录：`~/Library/Application Support/qmt-roll-stage179/development-verification/broker-sizing-20260908T1644/`。
- 初始身份命令误写了测试文件名 `test_stage179_performance_gate.py`；实际测试为 `test_stage179_production_performance_gate.py`，随后在 `performance-source-sha256.json` 补充准确的测试与 pipeline/journal 哈希。未更改压力实现。
- 证据边界：这是未提交候选的离线诊断；调度、独立进程和运行时负载均不同，单次通过不能证明此前失败仅由 taskpolicy 导致，也不代替 clean-commit 正式压力资格。

## 4. 精确环境预验收暴露的问题与修复

- 第一轮 51 个非压力套件使用现有 `build_trusted_runner_environment` 的完整白名单，逐组执行 `_trusted_pytest_argv`；外部未注入 `LANGUAGE`、`PYTHONPATH` 或 emergency runtime override。部分测试自身的既有隔离 fixture 设置不在此承诺范围内。
- 共 16 套失败：15 套因候选 `.py311` 指向共享解释器，其 editable 路径和 `sitecustomize` 将 vn.py runtime 绑定到原 checkout；另 1 套的方向/offset 断言写死中文，与正式白名单环境中的英文枚举值冲突。
- 保留失败回执及每套 JUnit/stdout：`~/Library/Application Support/qmt-roll-stage179/development-verification/broker-sizing-20260908T1652/`。
- 只修复 `test_stage905_c9_cycle_intents.py` 两个断言，改为 `Direction.SHORT.value` 和 `Offset.CLOSE.value`，仍要求真实的空方向和平仓 offset，不接受任意字符串；未改变生产交易逻辑。
- 将现有约 2.9GiB Python 环境以 APFS clone 复制到私有 `development-verification/broker-sizing-runtime-20260908T1658/python`；只调整副本的 `_editable_impl_vnpy.pth` 指向候选 worktree。
- 只把候选 `.py311` symlink 原子改指副本；没有改共享 `.py311`、原 checkout 或生产环境。执行仍使用项目 `.py311/bin/python -m pytest`，不调用副本中可能有旧 shebang 的 pip/pytest 脚本。
- 为候选建立独立 `.vntrader`，从原研究行情库 readonly backup 得到 112267264 字节的数据库，`quick_check=ok`，SHA256 `aa16fffb49c92f2af20061ec3e2916c5171f8d90508d5018f3b928e98c6ad283`；目标权限 0600。
- 实测 Python、sitecustomize、vn.py、TRADER_DIR/TEMP_DIR 均绑定候选隔离路径；`assert_project_trader_dir()` 不借 emergency override 通过。
- 这是恢复相同版本的独立环境，不是升级 CTP/runtime；具体二进制比对、symlink 审计和数据库复制回执保存在上述私有 runtime 目录。未准备生产凭证，不能宣称已完成正式 runtime/env 资格。
- 第二轮 51 个非压力套件在修复后的隔离环境、相同 trusted 白名单下逐组运行；最终结果在本记录末尾追加，不能把运行中状态写成全绿。

## 5. 独立评审：跨日正常退出仍是 P1

- reviewer 直接审阅代码后确认：当实际手数不等于 shadow、OpenDate 不等于自然 TradeDate，且缺少独立 `broker_open_date` 证据时，正常全平将确定性被拒绝。不能推断所有夜盘仓位都会出现此问题。
- 当前只有 validator 消费字段，没有在真实新开路径生成、封存并重启恢复该字段的完整生产链；测试手工补字段不代表链路已经实现。
- Stage904 保护性止损不直接依赖该 OpenDate 闸门，但它有入场日、归属、状态和行情条件，不能作为跨日正常退出失败的完整回退。不能据此放开新风险。
- 当前生产历史全 unbound 的旧审计记录不授权自动认领；本轮没有重新查询券商持仓，也不把旧日志称为当前仓位。

### 待确认的最小链路改造范围

1. 只针对未来 owned 新开成交，在其成交 trading day 内封存开仓日；normal fill 和同日恢复路径都要覆盖，回调内不阻塞执行查询。
2. native order 身份、开仓前双向 flat 基线、fresh Order/Trade/PositionDetail/Position 完整查询、同连接交易日及事件水位必须共同绑定。
3. OpenDate 取自精确归属的原始持仓明细，而非 TradeDate/TradingDay 二选一。首版只支持可完整证明、尚未减仓的 lot；不补造旧仓归属或隔日历史证据。
4. 独立 durable sidecar 引用 canonical fill，不修改 canonical fill；同值幂等、冲突拒绝。重启后的 validator 必须实际消费证据，不能仅记日志。
5. 端到端离线验收覆盖夜盘两个日期同/不同、shadow≠actual、次日当日成交查询为空、SHFE/INE 今昨拆单、部分成交、查询缺包/迟到/冲突、重启恢复。
6. 历史无归属仓位保持拒绝接管；无可验证退出闭环前不进入新 release 激活。

- 此范围属于执行链路改造，已向用户说明并请求确认，尚未开始新增实现；同时请求在验收通过后提交本分支的明确授权。

## 6. 生产状态与后续顺序

- 本轮只读复核生产 HEAD 仍为 `d492ee072aa5a9d71477235d79f17d2a5db59db3`，tracked clean；manifest 为 `stage210-m0005-production-d492ee07-20260902`，执行 profile `c9-15w`。
- activation 仍绑定该旧 SHA；最新 daily receipt 的生成时间为 2026-09-08 16:40:15，仍绑定旧 SHA。本候选并未因此获得资格或生效。
- 本轮没有连接 CTP，没有真实下单/撤单，没有 commit/push、正式物料发布、修改 CURRENT/manifest、Stage948 安装/激活或 launchd 重启。
- 后续依次为：获准并补齐 P1 退出证据链 → 独立评审和完整回归 → 明确授权提交并冻结新物料 → clean-commit 正式资格及两次正式只读采集 → 按 Skill 晋升与安装审计。不得借用旧版本资格。
- 参数及回测结果：无新增、修改、删除；期末权益、收益、回撤、Sharpe、交易次数、胜率等均不适用，本轮没有回测。

## 17:09 最终预验收回执与停止脚本修复

- 隔离环境第二轮 51 个非压力套件完成：50 套通过、1 套失败；合计 `1405 passed, 1 failed, 825 subtests passed`。运行前后全部 critical 源码哈希一致。原先 runtime guard 与语言断言导致的 16 套失败不再出现。
- 剩余失败不是策略问题：候选 Python 的真实路径含 `Application Support` 空格，Stage930 supervisor 两处 deadline 命令替换未引用 `${PYTHON_PATH}`，导致 deadline 为空，TERM 升级和重启等待不能正确结束。
- 保留失败原始输出，不通过搬到无空格目录、放宽超时或跳过 lifecycle 套件来掩盖。独立 reviewer 确认根因与两行引号修复范围。
- TDD 先固定含空格的 Python symlink，分别覆盖拒绝 TERM 的父孙进程清理与重启延迟；修复前两项测试均按预期超时失败，`2 failed, 11 deselected`。
- 仅给 supervisor 的两处 Python 路径展开增加引号；没有更改超时、重试次数、PGID 归属或生产启动参数。现有 lifecycle 测试额外缓存已经验证 `child == pgid` 的本测试 PGID，使临时目录删除后 cleanup 仍能清理本测试进程。
- 第二轮首次失败遗留的离线测试 PGID 93600，逐一核验 leader 脚本、私有解释器路径及组内两个成员后才清理；未停止任何生产进程。最终只读进程检查没有 `ignore_term.py` 或 `exit_nonzero.py` 测试残留。
- 最后专项回归覆盖 lifecycle、Stage905、release manifest、Stage945 launcher、Stage948 installer：`147 passed, 70 subtests passed`，耗时 39.66 秒，仍使用正式白名单环境。红/绿原始输出、JUnit 和退出回执保存在 `broker-sizing-20260908T1700/`。
- `bash -n`、`git diff --check` 通过；两条 Direction/Offset 枚举断言和 supervisor 路径修复均获独立只读评审认可，未降低验收。没有在最后源码修改后再冒充重跑全 52 套；正式候选仍须重新绑定 clean commit 做完整资格。
- 候选 Python 副本 1126 个 symlink 均无越界或悬空；Python、vnctpmd/vnctptd、正式 MD/TD framework 共五项二进制 SHA256 与源环境完全一致。源 editable `.pth` SHA 仍为 `d3ab4b13fe1b92d017e3e806c18eb5bc2864f9eed21b8ee9c2648c6351ab861d`，源环境未改。
- 将本任务旧 `.test-output` 中恰好两项已知测试文件移动到私有证据目录并复核哈希一致，未删除内容；避免测试 runtime JSON 混入后续 Git 提交。其他脏文件未清理、未暂存。
- 结束时生产 HEAD 再次只读确认仍为 `d492ee072aa5a9d71477235d79f17d2a5db59db3`，tracked clean。本候选没有部署、激活、下单或撤单。
- 最终状态：`production_release_not_qualified`。依赖、隔离环境及此次停止脚本失败已修复；跨日 OpenDate 证据生产链的 P1 仍未关闭，且候选提交、不可变物料和正式资格尚未完成。等待用户确认新增退出链路范围及提交授权。
- 结束反思：不过拟合，未修改 alpha 或根据收益选择结果；继续有价值，但下一步必须补齐可验证的正常退出链路，而不是把离线测试通过等同于实盘可启用。
