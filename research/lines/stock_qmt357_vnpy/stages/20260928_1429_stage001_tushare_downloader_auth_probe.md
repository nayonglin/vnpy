# Stage001 Tushare股票下载器与认证探针

- line_id：`stock_qmt357_vnpy`
- 当前模式：独立股票数据工程；无策略运行、无收益读取。
- 记录时间：2026-09-28 14:29 CST。
- 工作区：`/Users/bytedance/Desktop/person/vnpy`。
- 阶段性质：迁移输入合同、下载缓存与认证可用性验证。
- 是否重要突破：否。
- 是否触发A/B：否。

## 外部调研与判断

- 参考资料：Tushare官方文档 `index_weight` doc96、`daily` doc27、`index_daily` doc95、`adj_factor` doc28、`stk_limit` doc183、`dividend` doc103、`namechange` doc100。
- 链接：https://tushare.pro/document/2?doc_id=96 、https://tushare.pro/document/2?doc_id=27 、https://tushare.pro/document/2?doc_id=95 、https://tushare.pro/document/2?doc_id=28 、https://tushare.pro/document/2?doc_id=183 、https://tushare.pro/document/2?doc_id=103 、https://tushare.pro/document/2?doc_id=100 。
- 我的判断：历史成分、未复权OHLC、独立因子、历史名称ST、真实涨跌停与现金/送转必须分开取证。月度成分只能在快照日期之后生效；禁止月底名单回填月初。现金采用每股税前`cash_div_tax`，送转倍率为`1+stk_bo_rate+stk_co_rate`。

## 本次变更

- 新增脚本：`examples/stock_backtesting/qmt357/download.py`。
- 新增测试：同目录`tests/test_download.py`。
- 新增参数：下载默认`start=20231001,end=20251231`；按年分段，沪深300权重从2023-09开始按月请求；默认请求间隔0.65秒；瞬时错误最多3次，认证/权限错误不重试。
- 修改/删除策略参数：无。
- 下载文件固定存包内`data/downloads/tushare_<start>_<end>/`，每请求缓存有API名、参数、字段、抓取时间、行数和SHA256；不输出/持久化token。
- source attrs与下载manifest披露：月度滞后成分近似、税前现金在除息日计入而未用派息日应收、送转在除权日增股而未延迟红股上市日、供应商历史版本修订风险。

## 回测/归因参数

- 固定验证区间：2024-01-01至2025-12-31；预热2023-10-01起，成员快照包含2023-09。
- 样本过滤：原策略沪深300成分；剔除300/688前缀；历史ST逐日期取证，缺失即报错。
- 账户规模/成本口径：本阶段未运行回测，不适用。

## 结果

- 期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率：均不适用；未运行策略。
- Tushare轻量网络探针：环境token存在且无首尾空白，7个API各请求1次，全部返回“您的token不对，请确认。”。不是限流或积分不足；没有重复失效token请求。
- 下载状态：未启动全量下载，没有生成Tushare `source_panel.parquet`。
- TDD：初次测试7 failed，全部为明确模块缺失断言；实现后7 passed in 0.30s。
- 独立CLI：`.py311/bin/python -I examples/stock_backtesting/qmt357/download.py --help`通过。
- 独立-I组件测试：73 passed / 10 failed；10失败全部为并行Baostock实现尚在RED阶段的`NotImplementedError`占位，不代表完成版本通过。后续须由合入者复跑完整组件测试。
- 隔离说明：得知仓库`sitecustomize.py`预载期货工具后，后续执行均用`python -I`并只显式添加本库路径；本下载器不导入期货模块、不读取期货配置。

## 输出文件

- quality：`examples/stock_backtesting/qmt357/data/downloads/tushare_probe_20260928.json`。
- report：本阶段记录。
- source_panel/orders/daily/收益summary：未生成。

## 结论

- 本阶段结论：规范化与缓存合同可用；当前Tushare认证被拒，不能称股票数据下载完成。
- 是否进入下一步：可以完成备用源的数据工程验证，须明示与Tushare真实日限价等差异。
- 下一步：父任务与stock_data_audit代理独立验证Baostock历史成分与行情；有效Tushare凭证到位后可重用当前下载器。不得静态成分替代历史，不得静默填ST=False。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：固定两年窗口与原参数，只有认证探针及合成数据规范化测试，没有策略收益或参数筛选。

## 继续价值反思

- 运行前判断：有。
- 运行后判断：有。
- 原因：明确数据来源、时间可得性和现金/股份事件计账是后续复验前提；失效凭证继续重试没有价值，因此停止Tushare网络请求并保留诊断。

## 合入建议

- 本线LINE.md/registry.md：由父任务合入后统一更新，本代理不改。
- 根目录memory.md/back_log.md：不追加；当前不是策略突破或正式候选。
