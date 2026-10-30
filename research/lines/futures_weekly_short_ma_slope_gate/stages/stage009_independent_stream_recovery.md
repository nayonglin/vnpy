# Stage009 独立审计串行进程停止后的纯审计恢复

- 2026-10-30 15:45：只读 `ps -p 12876` 无进程，`os.kill(12876,0)` 返回 `ProcessLookupError`；`ps -ax` 未找到任何 Stage009 independent stream/window。最后流日志在15:40:40为11/46；2017-06-01_C.log于15:40:55创建、0字节、无对应收据。
- 原窗口审计源码SHA保持 `63e9ba6821b3b4c377ed7b67ca035b4daa4fc9ddd8bb824141047f280e237ac9`。旧11份收据及所有日志原样保留；未改金融源、未新增金融回放。
- 新增stream_v2，最大2个纯审计子进程；新独有attempt日志，临时收据在校验后原子发布。全局flock由子进程继承，父进程意外停止时，活着的孤儿审计仍持锁，禁止新supervisor重复签名。
- 新supervisor先确认旧PID不存在，再逐份复验已有收据与全部输出SHA。唯一未签窗口重新执行纯审计，无金融重跑。
- 安全停止派发：创建`stages/stage009_independent_stream_v2.stop`，现有审计完成并签收后退出；不kill正在写收据的子进程。
- 由root启动长会话，避免独立agent因模型capacity失败时清理其exec session导致审计再停。本agent尚未启动v2。
