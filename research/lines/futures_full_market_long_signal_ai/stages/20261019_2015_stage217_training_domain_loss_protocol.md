# Stage217：固定可行动域的训练loss单轴实验

- line_id：`futures_full_market_long_signal_ai`；记录 2026-10-19 20:15 CST；协议冻结 2026-10-19T20:13:23.256454+08:00，早于218/219实现及全部新金融结果。
- 工作区 `/Users/mac/Desktop/fian`，分支 `codex/ai-training-data-expansion`；独立全市场long-only研究，非正式A/B/生产，不切分支或工作树。
- 不是重要突破；当前新增实际fit/cash均0，基数427fit/230cash。预算6新fit、最多4新cash不是已跑次数。

## 调研、假说与独立判断

沿用210–216对129原firstexit、130训练、156/157固定K及完整域的源码研究，以及[Shimodaira2000出版页](https://www.sciencedirect.com/science/article/pii/S0378375800001154)、[SPO作者GitHub](https://github.com/paulgrigas/SmartPredictThenOptimize)。作者草稿超时不重试，未安装外部库/优化器或下载行情。

214/215确认六旧成熟训练折中当前不可行动域占约12.47%–14.04%旧loss权重，允许域均非空、日历unknown0；这不是坏标签、旧模型bug或收益损害证明。固定有限线性模型把部分损失投到不用的动作域，给出一个非恒等、可直接证伪的学习分布干预；删域也可能丢有益信息、增加方差。root因此批准仅这一个低先验对照，未开启弱字段、模型或阈值试错。

## 唯一变化与固定项

- 候选DOMAIN52：原成熟训练域中仅保留156日历gate允许的D<K行，原Y不变。W为原old weights总和，W_A为允许域旧权重总和；新权重=旧权重×W/W_A，保持允许域内相对比例和与控制相同的总loss质量。
- 不重算holding uniqueness/等日权重；不谎称新权重逐值等于旧权重。不按分组成绩挑family/year或新权重阈值。
- 原COMMON26+26missing、六原scaler坐标、Ridge alpha1/intercept/cholesky、两cutoff/两held族划分、原firstexit stressR/成熟时钟全固定；q及新missing输入为0。
- 所有六折原训练身份、214支持/质量、X/Y/新权重必须先验核完；任一支持失败则0fit。之后每折一次物理拟合，总6次，原模型0次。
- 完整1,933,480新child模型分数；main/held union各161,014母表，全身份保留。沿156原D<K、score>0母内排序/同分及family顺序，旧156main和205已接受COMMON52 heldK直接复用，控制重预测/重选择0。
- 主选择action/selected/anchor全相同则0cash关闭；已核原131/070的手数和family priority不依赖score大小，改分数但不改动作无法通过严格主收益增量。

## 金融预算与预设门

- 有动作变化才最多四新DOMAIN52自己现金账本：100万元、0.25N初损、单family风险0.25%、总风险2%、buffered margin25%、buffer1.1、1%参与率，原费滑/anchor/K/整数化全固定。
- 2020连续和2023独立起算×base/stress，截至2026-10-16。132原生cache，0SQL、新价格/标签/分钟/下载；旧157四本原件只读，不重放。四raw/checkpoint/financial terminal先于metadata，不自动重跑。
- 2020stress自身正、收益严格增且DD严格变浅；其余三本正且收益/DD不劣；全部四paired原070索引日log CI下界>0。两held原target已知等u增量严格>0且distinctunknown0，其他unknown披露。held并非K/cash目标，现金不能覆盖held失败。
- 全门即使通过也只是同史有限支持，仍需未见样本、多周期和真实执行证据；不完成完整goal或加注/生产资格。
- 六新fit若完成累计433/230；四新cash若完成累计433/234。无动作变化或失败不能伪增次数。

## 实施、审查与停止

218作者、219现金作者、220独立审查并行，仅各自新代码/阶段；root唯一actual。220继承旧COMMON/控制已接受数学，实际新模型/全预测/held与新现金分阶段checkpoint审，不重复已完成phase。所有新回测仍需独立全面review。

任何固定支持、无动作、现金/held门失败关闭本DOMAIN52包，不换K/日期/family/窗口/scale/model/alpha/权重版本/目标/阈值/止损/风险救参。原q/旧log代理不复活。只识别训练loss分布算法干预，不是纯Y效应或市场因果机制。

本阶段新增协议和本记录；未修改旧参数、模型、回测结果，删除0。权益、收益、DD、Sharpe、滑点、交易次数、胜率均N/A，actual尚未启动。

## 反思与后续

开始/结束过拟合风险：是，同史反复择题风险；先冻结不能消除历史所见。本轮尚未见候选收益，未救参。继续价值：是，仅一次有可识别支持、保持其他轴固定的loss-domain反证；继续做盘点/重审旧现金无价值。

TODO：218/219必要新fixtures与220精确源码预审，root单次实际及独立新结果审查，221按固定门决策。总体goal active，不发布、不部署、不加注。普通阶段不追加根memory/back_log。

[完整冻结协议](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage217_training_domain_loss_protocol/protocol.json)，14,895B SHA `b86c21d02b70e55181b7324efc1ebb6b363ee9d842738efe0f2baedfc3747b53`。
