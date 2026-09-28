# Stage001 正式根事件与决策时点特征资格实施计划

> 执行约束：使用`.py311/bin/python`，按TDD实现；生产目录只读；运行任何正式基准回放后必须拉独立reviewer；任一资格门失败不得同线重跑救援。

## 目标

构建一个一次性、可审计、无结果标签的Stage001 runner，在两个隔离冷进程中从2020年冷启动重建当前m0005 + C9/15万正式基准，并只提取2022年首个真实动态LR快照之后的模型排名层根入场事件；固定`fu.SHFE`卫星保持A，冻结12项决策时点特征，并在任何标签、XGBoost或候选策略运行之前决定该研究对象是否合格。2019-12-31全零分数静态18边界仅用于正式路径冷启动，不属于LR样本。

## 文件职责

- `tools/formal_signal_event_features.py`：纯函数；校验候选快照与正式AI池，生成事件身份和12项特征，不读文件、不运行引擎。
- `tools/stage001_worker_bootstrap.py`：仅标准库的隔离启动入口；核对`-I -S -B`、固定环境、父通道密钥和输入身份，并在第三方/生产导入及capability消费前以真实越界写探针证明OS sandbox生效。
- `tools/stage001_formal_event_feature_qualification.py`：身份合同、冷进程编排、正式基准重建、A1/A2一致性、硬门、原子发布和异常事件账本。
- `tests/test_formal_signal_event_features.py`：特征公式、固定fu cutoff、缺失/无穷/重复/未来列fail-close。
- `tests/test_stage001_formal_event_feature_qualification.py`：身份漂移、隔离目录、禁用操作、A1/A2差异、异常耐久账本和原子发布。
- `stages/20260905_stage001_execution_authorization.json`：用户既有默认授权的机器绑定收据；只绑定唯一Stage001入口和输入SHA，不扩展到标签或训练。

## 任务1：纯特征构造

1. 先写失败测试，覆盖12项公式、long/short方向归一、唯一静态边界、冻结56个动态月份、每月10个模型行、正式rank10 cutoff与固定fu排除。
2. 写失败测试，证明任一源字段缺失、非有限、非正分母、事件键重复和禁止未来列都会抛出稳定错误码。
3. 实现`build_formal_root_event_features(candidates, eligibility, identity)`，只返回固定身份列、12项特征和可追溯列。
4. 运行专项测试并确认通过。

## 任务2：只读正式基准worker

1. 先写失败测试，约束worker只能接受固定起止日、active release、live version和15万元。
2. worker在独立runtime中加载生产`Stage901._run_live_c9`，只保留`entry_candidates`；所有组合收益、交易结果和曲线对象立即释放且不得写出。
3. worker记录PID、解释器、模块真实路径、`cwd`、`sys.path`、数据库、空setting、HOME、TMP和MPL目录、sandbox身份及全部直接输入身份。
4. worker由`.py311/bin/python -I -S -B`进入固定SHA的标准库bootstrap，再经`/usr/bin/sandbox-exec`以deny-default策略启动；不继承任意父环境、不执行site/`.pth`启动钩子。bootstrap必须在导入pandas、vn.py和正式runner前验证stdin一次性父密钥，并证明worker目录外真实写入被OS拒绝；网络对原生库和后代进程一并关闭。Python guard额外拦截并记账敏感导入、fit/predict、标签/holdout、CTP/账户/订单、子进程和越界写入。
5. worker输出临时事件表、特征表和receipt；不写final目录。

## 任务3：父进程资格与耐久审计

1. 先写失败测试，覆盖A1/A2事件差异、特征差异、输入漂移、已有claim、并发claim和worker异常。
2. 父进程claim前的正式身份、1410项输入、Git和runtime信息发现只允许直接文件读取、`os.uname()`及Python运行时属性，不允许生产模块导入、网络或任何子进程；第1410项仅为worker bootstrap代码。authorization必须单次读取bytes，并从同一份bytes解析payload和计算claim SHA。随后在同级临时目录中用`O_CREAT|O_EXCL`创建0600 claim和execution event，完整fsync后一次rename为固定状态目录。同一授权lease只能进入核心一次，任何中断状态只恢复为技术失败，不允许重放。
3. 顺序运行A1、A2，禁止checkpoint；父进程在锁内把一次性capability绑定到即将注册它的具体不可变event条目，并同时绑定固定claim、nonce/lease、worker ID、bootstrap/runner、隔离解释器、固定环境、sandbox、stdin父通道密钥哈希和全部路径/SHA。只有该event条目无覆盖提交成功后才允许启动worker；worker只有在bootstrap完成真实sandbox证明后、任何输出和生产导入前才原子消费。成功receipt必须按固定schema与磁盘真实文件逐项交叉验证，再执行Stage000的13项硬门。
4. 成功时复制A1/A2原始worker receipt、已消费capability、事件CSV、空setting、sandbox profile、完整输入manifest及`publishing_success` execution event；portable receipt不得引用失效worker绝对路径，也不得发布worker日志。完整产物在原子rename前后各复核一次，再清理临时目录。
5. 若创建状态目录时发生硬崩溃，完整nonce与lease由staging目录名恢复；empty、claim-only、event-only、truncated-event和完整pre-rename状态都必须先固定为不可重放账本，再发布技术失败。状态目录发布后的序号1`event.json`不得改写，所有状态变化写入逐序号、以前一条原始bytes SHA命名的不可变条目。failed bundle同样使用完整nonce/lease绑定的可恢复staging，目录创建、receipt、manifest或rename前中断均只允许恢复为failed终态。若终态事件追加中断，由final/failed bundle单向恢复账本，不能重放或同时发布互相矛盾的终态；final已rename后的恢复失败必须同时保留初始错误与reconcile错误。
6. 首次成功发布与成功恢复必须执行同等级的语义校验：两名worker均为completed、每人且仅一次正式基准回放、固定版本/资金/区间、全部敏感计数为零、sandbox与sensitive guard成立、A1/A2事件表独立重算一致；当前authorization、1410项输入/runtime/正式材料身份和状态目录event链末端也必须与成功包逐项一致，任何unknown或漂移均fail-close。首次路径在final rename前、rename后、attempt cleanup后及追加`completed sequence=7`前分别重验当前绑定；恢复路径在cleanup后复用同一成功完成原语。所有event更新由不变的执行状态目录锁串行化，claim/event/temp读取、临时文件写入、无覆盖`linkat`提交和fsync只允许以该锁定目录fd相对操作完成，writer不得重建父目录。读取端必须拒绝重号、缺号、坏前序SHA、非法状态迁移、敏感计数回退和不可变字段漂移；锁锚点路径/inode、claim原始bytes/payload、当前event原始bytes及当前条目名在提交紧前及提交后再次核对。claim缺失、替换、同inode读中漂移、目录替换或目标条目已存在均失败；成功完成还要求nonce/lease、authorization SHA及输入合同与成功包精确一致。完成更新必须从完整`publishing_success sequence=6`条目无覆盖追加唯一sequence=7，精确completed只能幂等读取且不得递增。
7. 对同向相关性额外记录候选收益样本可用性，并在生产快照之外独立枚举真实同向持仓、重算有效相关性数量及最大值；候选历史不足、同向持仓未测全或原始快照与独立trace不一致时，不得生成合格事件。

## 任务4：执行前验证与独立预审

1. 运行新线专项测试、全部PIT XGBoost相关测试和`py_compile`。
2. 校验生产目录`git status`、HEAD、active material、release manifest和配置SHA均未被修改。
3. 拉独立reviewer检查PIT、事件语义、未来列屏蔽、异常耐久性、相关性unknown语义、成功恢复完整重验和一次性授权边界。
4. 只有reviewer明确`ALLOW_STAGE001_UNIQUE_RUN`才执行一次；运行产出属于正式基准回放数据，完成后再拉独立结果reviewer。

## Stage001之外

Stage001不得实现事件屏蔽器、反事实标签、XGBoost模型、阈值、A/C候选或前向shadow。上述工作只有在Stage001全部硬门与独立复核通过后，另写Stage002标签前预注册与计划。
