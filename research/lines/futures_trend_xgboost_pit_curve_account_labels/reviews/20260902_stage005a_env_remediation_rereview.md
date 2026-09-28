# Stage005A 父环境修复独立复审

- 复审时间：2026-09-02 18:54 +0800
- 复审结论：`ALLOW_STAGE005A_SMOKE`
- 严重度：P0=0，P1=0，P2=0，P3=1
- 置信度：98%
- 授权范围：仅允许在 immutable v2 snapshot 上创建一个全新 campaign，并运行原预注册固定 4 个 smoke；不授权 Stage005 270-job 批次

## 证据

- 旧 campaign 为 `abandoned_preworker`，completed/worker/output 均为 0；`job_outputs/` 不存在，`.partial/locks/logs` 文件数均为 0，`reuse_forbidden=true`。
- `_install_parent_environment` 强制设置 QMT runtime guard、`MPLCONFIGDIR` 和 `TMPDIR`；prepare-runtime、prepare-campaign、smoke、worker、preflight 五个入口均在下游模块加载前调用。
- worker 使用显式 `env` 映射启动。
- 授权绑定覆盖 scope core/test、原始预注册、历史 BLOCK/ALLOW/authorization、环境补充预注册和 runtime snapshot receipt。
- runtime receipt SHA256：`f67186f8e1603c81afeb5800e3e742287228862e61e984aac6c843a1a69bf0c2`；SQLite integrity、行数、最大时间、source/clone SHA、大小和独立 inode 全部重新通过。
- 真实 loader 仍只指向 v2 frozen mapping/minute/metadata。
- 限定测试：17 passed；7 个文件 `py_compile` 通过。
- 未运行 prepare、smoke、worker、backtest、CTP 或订单。

## 剩余项

- P3：没有对五个入口逐一做动态调用顺序测试；静态入口调用和 helper/真实 loader 测试已核实，不阻断固定 smoke。

## 判断

- 过拟合：否；补丁只修复父环境传播，没有改变任务、样本、参数、数据或通过条件。
- 继续价值：是，但严格限于新 review/decision/auth 绑定后的新 campaign 固定 4 smoke。
