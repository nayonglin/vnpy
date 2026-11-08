# Stage005 基本面 Skill Git 入库与 master 发布

- line_id：`futures_fundamental_data_sources`
- 时间：2026-11-08 17:53开始整理（北京时间；具体操作时间以Git记录为准）。
- 用户明确授权：保存到仓库、与其他Skill放在一起、合入master并推送远端。
- 原状态：`skills/futures-fundamental-bias/`及发现链接在本地但未跟踪、未提交；当前研究分支有其他工作，不整体合并。
- 阶段性质：工具物料入库，不是策略alpha晋级或生产部署；不触发A/B。

## 本次发布范围

1. 原创Skill七文件：入口、UI元数据、三份参考、证据审计脚本及边界测试。
2. `.agents/skills/futures-fundamental-bias -> ../../skills/futures-fundamental-bias` 相对符号链接。
3. `skills/README.md`与`skills/HANDOFF_MANIFEST.json`仅增加本Skill相关条目；其他Skill的未提交改动不带入。
4. 本研究线的公开调研、事实包、审计和独立审阅；`research/registry.md`只增加本线一行，不覆盖其他线。

远端初次核对master为`491d13617f61cac88b94476dc36171dc81691f30`，已领先本地研究分支。所有远端更新以实时复核的master为基础，使用非强制快进与expected head检查，禁止覆盖并发提交。

## 验证与边界

- `.py311/bin/python -m unittest discover -s skills/futures-fundamental-bias/tests -v`：18项通过。
- 独立包审：七文件哈希、发现链接、32份既有公开研究文件、12 JSON、5套证据审计重算及6份artifact摘要核对通过；未发现凭证或私有运行状态。
- 宿主官方quick_validate原有PyYAML缺失限制保留；不声称它已成功运行。Skill本身仅依赖Python标准库与宿主搜索。
- 普通完整Git fetch卡住后终止；GitHub连接可读但Git对象写入返回403，未修改远端。随后本机Git已成功核验master，并在临时裸对象库以浅层、blob过滤方式读取同一远端基准，后续使用本机Git构造与推送非强制快进提交，不改变当前研究工作区。
- 现货/定价为固定检查维度，无固定权重；输出首行看空/中性/看多，证据不足归中性并说明未知。
- 不修改正式策略、生产物料、activation、CTP、邮件或定时任务，不安装依赖，不运行收益回测。

## 记录口径

本文件初版固化提交前的发布范围和检查，最终发布提交及远端校验另在完成记录中填写；不能仅凭准备记录视为已经推送。

回测财务指标：权益、收益、回撤、Sharpe、滑点、交易笔数、胜率均不适用；没有修改既有回测结论。

开始/结束过拟合判断：否，本轮仅版本备份和发布；继续价值：是，避免Skill仅存在未跟踪工作区并保留可复验版本。无策略调参。
