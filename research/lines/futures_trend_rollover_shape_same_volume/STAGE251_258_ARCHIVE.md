# Stage251—258 离线研究归档

- 运行正确性修复独立提交为40570be4b，已本地快进合入master；正式0.5R和AI默认参数没有随研究改变。
- 本目录Stage251—257脚本、实验记录及轻量证据属于历史离线研究，不是生产启动入口。
- 多个历史runner故意锁定旧HEAD 0e9d34b72、原分支、冻结基线checkout、原模型/数据SHA及本机vendor路径；本归档提交之后不能原样作为通用runner启动，也不通过删除身份校验来伪称重现。
- 重现材料的具体来源和SHA保留在原manifest/stage记录；数据库、完整分钟输入、1955逐户原始输出和大型HTML/图片仍在本机被忽略的outputs路径，不作为普通Git源码提交。
- evidence/stage259_merge只保存既有验收JSON、33窗/分组CSV和独立复核说明，全部保持原数值与来源说明。它不是新生产qualification。
- Stage257主要随机检验未过强排名门；六组收益差中位均正但高度重叠；不据此关闭正式AI或宣称通用优势。
- Stage258仅训练样本盘点：没有训练新模型。
- 其他任务的personal_knowledge_management、registry改动、邮件查询记录及原始行情不混入本归档。
