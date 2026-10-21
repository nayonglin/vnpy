# Stage114：非经纪类别gross净构成的独立审查

- line_id：`futures_full_market_long_signal_ai`；开始2026-10-18 19:47 CST。仅本研究线114自有文件，不改LINE/registry、作者或历史产物。
- 当前阶段：110有限科学预审与113最终现金接线预审C/I=0；111/112最终freeze已一次通读，完整包预审C/I=0，独审harness已准备；actual未授权/未启动，不能将本结论称为actual通过。重要突破：否。

## 一手调研、判断与边界

先读registry/LINE确认本线及完整全市场long目标；实读110协议及收益前澄清、113 final源码/测试与freeze，读取作者6新fixtures证据而不重跑。未读111/112半成品，不poll或重发109。

实读[SHFE官方2013披露文件](https://www.shfe.com.cn/content/cxxc/7wsxx.pdf)、[2026交易管理办法](https://www.shfe.com.cn/regulation/exchangerules/otherrules/202609/t20260914_833388.html)与[AKShare维护者源码](https://raw.githubusercontent.com/akfamily/akshare/main/akshare/futures/cot.py)。官方区分活跃月份两类会员总量与前20排名；AKShare的rank>0过滤会丢掉类别层，故不用其封装替代原表，也未运行其采集器。新境外类别版本可以映射功能角色，但不声称是历年稳定同一人群；不能由非经纪标签推出都在套保或更聪明。

收益前已从未实测的own ratio收敛为唯一s=(LN−SN)/(LN+SN+LF+SF)。它是旧总OI不能重建的类别构成观测；平衡Lsum=Ssum时|s|<=.5，真实全0保留observed1/s0。只解释当期披露scope，不是全月份OI、市场净需求或因果溢价。all唯一完整优先、不fallback；无all时必须从整份原表的所有真实contract ID核全集，不能从只保留类别行的normalized表推断完整性。

v必须是070全399252母体4074唯一u_date序列的严格紧前日；不找最近有表日，不把原u_index偷当此lag索引。原native现金与标签时钟不变。接受归档重建＋一完整source日lag的有限研究假设，不新增首发PIT资格流水线，也不伪称已取得当年发布字节。

## 静态发现与独审准备

目前科学/113代码C/I=0，精确收据见`outputs/stage114_member_category_review/protocol_cash_preflight.json`。113两主臂共享external_missing且不动作过滤，只沿原070分配、.25N/20low退出、既有风险与费用；held只作已识别机会诊断。主stress收益差严格>0，另三>=0，四DD不深、NFC自身四正/全账户正财富、主CI低>0及两held>=0；空DD N/A与actual财务未知/潜在未成交标签未知分离，名义失败不被unknown遮盖。

新独审只补6个必要源边界fixture：全0/严格整数，all优先且残缺无fallback，普通rank行也贡献完整contract全集，四量先sum后ratio，逐scope平衡及标签/rank精确，紧前母体日不等于最近表日。先RED（模块缺失）后GREEN；0真实数据/SQL/fit/cash，未重旧suite。真实raw/399252投影/模型/账本只等root精确终态授权后一次全核，失败保存，不自修重启。独立现金算术承接已冻结102自有纯核，不import111/112/113作者计算core。

## 反思与记录要求

开始过拟合判断：**仍有实质多轮历史选择风险**；新增观察类别有真实不同的信息内容，但这不保证能被固定模型利用或改善窄损现金。收益前只冻结一个gross scalar/lag/Ridge/NARROW包，无own-vs-gross赛马，无方向/窗口/阈值/风险扫描。Polanyi式经验直觉仅提示区分类别持仓与排名、重视披露范围改变，不能当资金动机与盈利证据。

继续价值：**有条件值得一次有限反证**，不是自动接近用户终点；失败应停本固定包，不以补品种/删缺失/调分母/换模型救参。正式、生产、加注资格和完整目标均未达到。

参数/结果：当前114新增仅独审代码、6个边界fixture与静态记录；研究参数、旧金融结果修改/删除均0。尚无114actual，期末权益/收益/DD/Sharpe/滑点/次数/胜率N/A。后续仅追加本次真实终态，root另做决策；不改其它stage。

## 20:04完整实现预审与harness交接

111 final源18453B SHA`81e0210d0abf25be6d73f461403a97fab00514b31d874fbf4569a0fa986ae6bb`；112 final源30265B SHA`acb0cdb3373f8110b77fbaa54fd71af845756e6a1c1e691c91dc4c00a7cf90c0`；113 final源27190B SHA`35c365e16c7c5853aedefeb493211c1af65879db593c9755132f91c394308131`。作者8个源/模型新fixture与6个现金新fixture证据已读，0实际/0model fixture fit；未重跑作者tests或旧suite。112工具输出截断处仅补读未显示头段，未重复全扫。

全包C/I=0收据：`outputs/stage114_member_category_review/code_preflight.json`4966B SHA`904ca8aa50936cd594355fab94cc2fa9007703101aa1fa0c6f31a6d24871aedf`。111的同scope类别对及跨contract人口版本冲突保守missing、无确定scope不参与数值，仍保留整母体；这不把未知当0或变成训练/动作删行。独审器据此补版本/未识别scope边界，准备期RED/GREEN现场保留。最终为6个源边界先RED后GREEN，另1个纯现金门边界fixture验证primary base=0合法、stress=0失败、名义失败不被held/stale未知遮盖；共7项GREEN/0.081秒，未读取真实109或金融输入。

独占单文件`tools/stage114_member_category_review.py`已实现postrun harness：109 completion/date_manifest/root source_acceptance精确闭包，13旧cache按108原SHA、其余日期URL/状态验证；实际授权后只单遍读原raw/hash/解压，原表全部contract清单、四LS与raw/type/label/版本/逐scope平衡、all选择及非选QA均独立核；所有399252投影及4074 lag/共享missing/零值/精确SHFE映射逐项核。真实原量推导与模型数值路径分离：原量算s后逐值比较投影，模型输入采用同一已验投影文本的pd.to_numeric解析，防末位CSV表示差异误报模型bug。

模型部分独立复算六cell严格成熟、family隔离、concurrency/equal_u权重、COMMON与scalar train-only stats，先验证六cell有效变异，再重构54头、12个55维含截距正规方程与644056全预测；核held已知域u等权增量、原unknown/取消状态、年度/family诊断。若support不足则只接受科学停止0fit/cash0，不强跑金融。现金部分继承冻结102自有独立纯核（6文件SHA绑定，不import作者core），新单文件完成8本原070预算/逐笔/费用/滑点/权益/summary/年度/all95family归因、确定性首次native分支证据、4组既有indices CI/held/门与未知披露。无完整native策略重放、旧模型复核或旧金融成绩择门。

审计CLI与真实schema分型见`outputs/stage114_member_category_review/audit_input_schema.json`2862B SHA`acf0999454ac0e012ae3608c5f96087dc46856447332fa85811c78da5dfbad07`：111没有假设通用artifacts列表；112正常artifacts为dict、support停止另分支；113为list。入口需root最终111/112/113 manifest及各terminal精确SHA；现金仅在112正常分支提供。现未获actual授权、未执行全核，source109仍由原单遍owner运行，不读部分数据/不poll/不先训前缀。代码/测试/输入schema及独立helper绑定见checker_freeze.json；实际失败必须保留并先报root，不能自动修复再跑。

本轮结束反思：**新增按成绩调参否，历史多轮择题风险仍是；继续这一次固定新信息反证有条件价值，但当前只有静态实现支持，无新alpha/现金证据。** 全市场高质量long、更高净收益与更低回撤、极窄初损/未来加注目标均active且未完成。预审至此交接并释放槽；本唯一中文stage待root精确授权后的真实总审终态再追加。
