# 正式期货策略完整交接：从这里开始

根目录`vnpy_handoff_20261014.zip.part001`起的全部分卷、`vnpy_handoff_20261014.manifest.json`及还原工具是一份完整ZIP，不是多个互不关联的补充包。所有分卷均直接随本仓库master提供；不依赖Git LFS或另一个旧ZIP。

快照源码仍为77538e394167c290d5f2923f4d08931b9bbd7c4f，数据日线截至2026-10-13。master本次只增加交接附件，不升级实盘策略。

## 一条命令还原

在包含全部分卷和清单的目录执行（Python3.11标准库，无需先装vn.py）：

```sh
python3.11 vnpy_handoff_20261014_restore.py --output /path/outside-checkout/vnpy_handoff_20261014.zip
```

Windows使用`py -3.11`。选新的输出路径，工具不会覆盖不同内容的既有ZIP；先核验每个分卷SHA256，再核验合并ZIP SHA256与CRC。`--verify-only`仅检查分卷、不输出ZIP。

Windows另需核对系统和解压工具的长路径支持：包内最长相对路径266字符，单设Git `core.longpaths=true`不足以保证普通解压工具成功。采用短解压根目录；系统/解压器不支持时先报告并修复环境，不能跳过文件后声称包已完整恢复。

将还原ZIP解压到新的短路径，再把`VNPY_HANDOFF_AGENT_PROMPT.md`交给目标agent执行。解压顶层先读`00_AGENT_HANDOFF.md`、`04_CONFIGURATION.md`。包内校验用`tools/verify_bundle.py`，精确数据恢复用`tools/restore_resources.py`。不要直接将包内repo目录当成Git checkout。

## 内容和安全边界

包含冻结正式源码、SQLite、全raw期货CSV、主力映射、合约元数据、正式历史分钟缓存、排序模型与summary、当前m0008AI物料、月更参考源、依赖锁、vendor插件、6个项目Skill和4个金融/通用外部Skill。字节/抖音/飞书40个工作Skill已移除。

新增天勤、CTP、SimNow/券商测试、SMTP以及研究路径安全模板和字段说明。全部真实账号密码、授权码、SSH私钥、生产签名/activation/订单账本和调度状态均不包含。账号需在目标机本地填写，离线回测不需账号。新机默认不连接CTP、不发送邮件、不安装生产任务。

日线最新不代表分钟连续齐全，完整覆盖限制在包内说明。本包只是研究迁移，不把旧机器生产状态复制成新机器授权。

## 分卷原因

GitHub普通Git单文件上限100MiB，因此完整ZIP分成每片90,000,000字节以内的分卷；按清单顺序还原后与原ZIP逐字节一致。来源：[GitHub官方大文件说明](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)。模型行情认证参考：[TqSDK官方TqAuth说明](https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.auth.html)。
