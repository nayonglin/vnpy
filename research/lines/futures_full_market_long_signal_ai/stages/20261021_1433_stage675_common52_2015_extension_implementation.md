# Stage675 COMMON52＋K固定规则2015起历史延展实现

- line_id：`futures_full_market_long_signal_ai`；day；记录时间：2026-10-21 14:33 CST。
- 当前工作区：`/Users/mac/Desktop/fian`；不新建分支/工作树，不暂存/提交/推送Git。
- 阶段性质：沿Stage673冻结协议的历史扩窗/资金展示，非重要突破；不涉及新alpha、正式策略接入或A/B/C晋级。

## 外部调研与判断

本阶段遵循673已完成的官方scikit-learn TimeSeriesSplit文档及GitHub原实现调研，不重复网上扫描。判断：时间顺序仅是必要条件，还须`u_date`与`label_known_date`双时钟均早于训练截点；保持既有特征、规则、原始数据与旧模型段才符合用户“同参数延展”意图。最终历史重构不等同严格PIT或独立OOS证明。

## 本次变更与固定参数

仅新增`tools/stage675_common52_2015_extension.py`、5个合成fixture及本唯一stage；未修改130/156/157或其它原源码。

新增一个`main/2015-01-01`训练折，直接调用未改动130.fit_cell；训练为完整129 actions中eligible、closed_complete、finite net_R_stress且u和label_known均严格早于2015的样本。COMMON26＋26原缺失标记、原2N特征量纲、训练集加权scale、Ridge alpha1/cholesky/intercept、family-u interval union uniqueness后分摊动作再equal-u均不变。2015–2019完整预测保留未知/未成熟标签；2020–2022和2023起至2026-10-16逐值复用旧130 main分数，不新增held或重训旧折。

156先在完整2015起母体上执行D<K和原正分/eligibility，再按原产品/普通优先F/族规则选择。新历史epoch全部重新套同一calendar K。只在wrapper显式校验并规范三段cutoff元数据，旧156源码不变；2020起选择、完整母体身份及精确score与旧156核对。原完整399252母表持续供应全部canonical，不能由选中子集反推。

现金只调用157.make_voluntary_signals与原131/070/042内核：100万元、单族0.25%、总2%、保证金25%与1.1、0.25N初始止损、原非单调20low、anchor/source lifecycle/K有效最小边界、D开盘、1%往返容量与半容量入场、原费用/滑点均不变。无止盈/加仓/新阈值。两本为all_2015_base/all_2015_stress，从首个源日>=2015-01-01连续运行至2026-10-16，不拼接旧净值，不重跑旧2020/2023四本，不做新bootstrap或晋级门。

新增参数仅历史起点和更早训练截点；修改/删除策略参数0。一次只读完整actions时保留cash必要字段，large payload read_bound hash后BytesIO内解析，避免为selected再次扫描原334MB。精确132 native cache复用一次，数据库stat前后守卫，SQL/下载/新标签0。

## 有限验证与交付接口

测试先执行缺实现RED：5个fixture均失败于Stage675 implementation missing；实现后最终5/5通过，1.060秒。覆盖训练两时钟严格边界与未知预测保留、2015/2020/2023固定schedule及held拒绝、新历史K的D==K拒绝但母体保留、2015输出cutoff纠正、旧选择重叠身份变化拒绝、union权重/逐日质量、原action-parent schema和COMMON维度、完整母表canonical。

CLI help通过；小metadata/symbol预检确认673 SHA、14roles、execution top-level anchor、safe/cache/cash函数、导入SQL0、旧CUTOFFS/ARMS不变和唯一actual输出未存在。未跑旧全套fixture或真实模型/现金，也未安装依赖。预检纠正了exclusive cash_progress重复写调用与safe符号引用，均发生在实际执行前，不涉及收益救参。

source_ready：`outputs/stage675_common52_2015_extension/source_ready.json`，11505字节，SHA256 `7006fb6e60fb59d3418d90a36c5b7934aa6396bde24020b2b89532f744c5cf62`；23项source bundle、14项inputs、fixture及schema全绑定。676独立静态审后由root签唯一actual；作者未运行actual。

预期manifest `stage675_common52_2015_extension_v1`含fold2015原130训练/权重/scaler/portable/model/normal equations绑定、新与combined child scores、完整母体/choices/K/signals/lineage/重叠凭证、两账户各9ledger及summary、annual/95族含零网格/diagnostics。plain curve CSV为`equity_and_drawdown.csv`，字段`date/base_equity/base_drawdown_pct/stress_equity/stress_drawdown_pct`；原daily保留全部原账本字段。绘图由root/677独立处理。

## 结果与反思

本阶段新增actual fit/cash/SQL/下载/标签均0，累计仍为旧587fit/294cash及1旧partial。新增/修改/删除回测结果均0；期末权益、收益、最大回撤、Sharpe、总滑点、交易次数、胜率均N/A，不能把合成fixture当金融结果。

开始/结束过拟合判断：按新结果调参**否**，经济/选择/训练参数沿事前冻结合同不变；长期同史适应性风险仍**高**，扩窗并不清除非PIT及选择偏差。继续价值开始/结束均**有**：唯一更早折和两本连续账能回答用户历史曲线与周期暴露；反复扫alpha/窗口或只保留好结果无价值。

后续：676静态审、root精确授权唯一1fit/2cash、676完整独审新训练/选择/财务/置信度/bug，之后root生成并视觉检查曲线。失败保留，不自动重跑；不据此正式晋级、加注或声称goal complete。普通stage不修改LINE/registry/根总账，由root收口。
