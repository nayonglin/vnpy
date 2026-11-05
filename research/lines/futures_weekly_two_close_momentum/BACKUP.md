# S21 二十一品种研究版备份与恢复

当前研究分支是 `codex/weekly19-stop-reversal-20261103`，远端为 `git@github.com:nayonglin/vnpy.git`。
当前版本是 Stage060：21 品种、初始 200,000 元、周 K 信号、固定一手、全部品种触价止损、逐笔保证金门槛，行情冻结截止 2026-11-04。

## 保存内容

源码、参数、阶段记录、独立审查、复盘适配器和更新的复盘 skill 作为普通 Git 文件保存。
`backups/stage065_s21_200k_20261105/manifest.json` 绑定单次压缩快照：本线全部输出（含失败证据与历史对照）、父研究线输出、当前 35 个固定行情输入、两项额外父证据，以及 Stage061/063 的 2022 年复盘、Stage064 的 2017 年连续账户复盘。
当前资金曲线与 24 个逐半年起点账本同在快照内。分卷文件均不超过 45 MiB，以普通 Git blob 保存，恢复不依赖 Git LFS。

`manifest.json` 给出每个原文件的字节数、SHA256、原始路径、快照内路径，以及每个压缩分卷和合并归档的 SHA256。源码文件另有 `code_files` 哈希清单。

## 新机器恢复

正常克隆整个仓库历史，再切换研究分支。不要只下载研究目录 ZIP 或使用缺少历史对象的浅克隆：共享配置导入还需要仓库已有的 CURRENT、release manifest 和其 Git 历史对象。

```bash
git clone git@github.com:nayonglin/vnpy.git fian
cd fian
git checkout codex/weekly19-stop-reversal-20261103
python3.11 research/lines/futures_weekly_two_close_momentum/tools/restore_s21_backup.py \
  --snapshot research/lines/futures_weekly_two_close_momentum/backups/stage065_s21_200k_20261105 \
  --repo . --destination ../s21-restored
```

恢复目录必须不存在，工具不会覆盖已有目录。它先核对分卷、归档和源码哈希，再逐文件恢复并核对所有内容。

- `s21-restored/repo/` 对应研究 checkout 中原来被 Git 忽略的输出文件。
- `s21-restored/external/` 保存原来位于其他研究 worktree 的固定行情输入。
- `recovery-path-map.json` 对照原机器绝对路径与本次实际恢复路径。
- `restore-verification.json` 为本次恢复的检查结果。

如需只验收备份而不保留恢复副本，可将 `--destination ...` 替换为 `--verify-only`，工具会完整解压、核验后清理自己的临时目录。

将 `repo/` 下的输出复制回新 checkout；复跑前按 `recovery-path-map.json` 恢复冻结来源路径或建立安全的路径别名。旧 inputs/receipt 含绝对路径，不能直接改写这些冻结文件后声称原哈希仍然一致。保留原路径布局可直接复用原证据；目录迁移的运行适配应另行核验。

## 环境与边界

静态 HTML 可直接用浏览器查看；恢复工具只需 Python 3.11 标准库。离线 S21 研究/复盘入口还需 Python 3.11、numpy、pandas、plotly 等项目依赖。原虚拟环境、账户凭证、生产状态、CTP 原生运行环境和编译缓存不属于本次研究备份。

Git 保存研究代码和证据，不意味着已部署实盘。不要因恢复成功而启动任何生产任务。GitHub 的文件大小约束参见 [官方说明](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)。
