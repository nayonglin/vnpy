# Stage136 AP010 canary 成交窗口原子补数预声明

- 时间：`2026-07-11 19:30 CST`
- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 性质：Stage135 canary 的固定数据阻塞修复，不改策略、不读取收益、不连接 CTP、不调用订单 API。

## 根因

- 当前 15万 Stage101 scale 只在 `2020-09-02/03` 达到 `>=0.5`，产生一组历史 Stage208 未曾要求过的成交窗口。
- 固定 5 个开仓合约中 4 个已有真实窗口；仅 `AP010.CZCE` 缺 `2020-09-01 21:00-21:05` 和 `2020-09-02 09:00-09:05`。
- Stage049 旧审计只证明 AP010 存在某份分钟文件，Stage134 的 `39/39` 不含 AP010 这一个新增真实下单日期；因此不能把 contract-level file exists 等同 order-date fill ready。

## 固定修复

- 合约：`AP010.CZCE`。
- 下载边界：`2020-09-01 20:55:00 <= bar_datetime < 2020-09-02 15:15:00`。
- 成交要求：夜盘窗口或当日日盘窗口至少一个存在；苹果该时期允许无夜盘，但必须有 `2020-09-02 09:00-09:05`。
- 严格检查：单一 vt_symbol、边界、交易日、OHLC、volume/OI、重复键、单调时间、负值和 SHA。
- 发布：先写本线 temp；严格通过后才同设备 `os.replace` 到共享 minute root。若目标已存在，先做 SHA 一致备份；失败文件只进本线 quarantine。
- 不允许用日线 close、旧 fallback anchor 或相邻日期价格替代。

## 闸门

- `downloaded=1/1`、temp strict `1/1`、publish `1/1`、post audit `1/1` 才恢复 Stage135 canary。
- 任一步失败就保持 Stage135 阻塞，不继续收益回测。

## 反思

- 运行前过拟合判断：否。窗口由预声明规则在真实第一笔失败处机械产生，和收益好坏无关。
- 运行前继续价值判断：有。只缺固定一个 order-date window，补齐后可公平完成 Stage135 一次性证伪。
