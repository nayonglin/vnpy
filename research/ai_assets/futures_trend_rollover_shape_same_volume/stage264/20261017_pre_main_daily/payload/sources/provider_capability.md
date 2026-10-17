# Stage264：旧合约完整日线行情源能力核查

记录时间：2026-10-17 17:25 CST；研究线 `futures_trend_rollover_shape_same_volume`。本文件是独立文档与本机静态核查，不是下载验收。已读 Stage263 结果、独立模型复审及补数可行性报告；Stage263 的缺口是成为主力前的同代合约历史，不能以主连长历史替代。

## 结论与最短顺序

1. **先用本机已有 TqSdk 普通日线接口验证具体退市合约。** 本机确认为 `tqsdk` provider，用户名/密码键均有值；本报告不展示值。本机已装 `tqsdk 3.10.2`、`pandas 2.2.3`、`vnpy 4.3.0`。普通 `get_kline_serial(symbol, duration_seconds=86400, data_length=1000)` 是本轮首选的小样本调用；是否覆盖完整上市寿命，要以实际返回边界及 manifest 核对为准。
2. **若特定合约不可用，优先公开交易所历史日报，其次 Sina 具体合约日线。** 按交易日取全部挂牌合约能自然涵盖 pre-main，并用日期消歧郑商所三位代码。Akshare 只是封装，当前根环境未安装；不为核查安装包。先小样本、后确定批次，保留原始响应及哈希，空数据和 HTTP 拒绝均不算“无历史交易”。
3. **信易 EDB 免费日线可作一次公开补充探针，但不能预设能补 2014—2019。** 官方文档一面允许免 token 任意历史区间日线，另一面写历史范围预计自 2021-01-01 起；早期资料是否存续仍待实测。
4. **RQData 为有权限时的备选接口说明，本机不是该身份。** `rqdatac` / `vnpy_rqdata` 未安装、对应配置键未见值；不把 TqSdk 账号当 RQData 或 Tushare 账号。`akshare`、`tushare` 同样未安装，Tushare token 键未见值。现有状态不足以把 RQData/Tushare 列为可直接执行路线，也无需购买或申请付费试用来完成本轮判断。

## TqSdk：基础接口与专业版的边界

官方当前 API 说明普通 `get_kline_serial` 从该合约最新一根向前取，单序列最多 10000 根；`data_length` 是根数，不是起始年份。典型期货合约存续日数远小于这个上限，因此“当前年份很晚”本身不能推出老合约的日线超长；真正问题是供应商是否保留了正确同代合约。`query_quotes(ins_class="FUTURE", expired=True)` 可查询已下市合约，但“能列出合约”不证明其 K 线完整。接口说明不承诺每个 2014—2019 退市合约均有完整数据。[TqApi 官方文档](https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.api.html)、[官方 GitHub](https://github.com/shinnytech/tqsdk-python)

`get_kline_data_series(symbol="SHFE.rb1505", duration_seconds=86400, start_dt=date(2014,1,1), end_dt=date(2015,5,31))` 和 `DataDownloader(api, symbol_list="SHFE.rb1505", dur_sec=86400, start_dt=..., end_dt=..., csv_file_name=...)` 属专业版；`date` 参数表示交易日，`datetime` 表示具体时间。root 已反馈三只小样本整段接口均 `permission_denied`，与权限文档一致；不应重复认证或改私有属性绕过权限。[专业版官方说明](https://doc.shinnytech.com/tqsdk/latest/profession.html)

现有 `examples/portfolio_backtesting/download_tqsdk_all_futures_daily_csv.py` 以 `expired=True` 枚举，调用普通日线序列并筛时间。它的文件存在即跳过、非空即下载成功，均不能作为本轮“完整寿命”验收。`vnpy_tqsdk/tqsdk_datafeed.py` 将 `open_interest` 填为 `open_oi`；补数不可悄悄换成 `close_oi`。研究线 Stage249 下载器已有只记录错误类型、超时、首次失败停止的安全模式，但分钟快照和指定任务范围不能直接冒认为完整旧日线下载器。

## 公开备用接口与历史深度

Akshare 官方说明 `futures_zh_daily_sina(symbol="RB1505")` 返回该具体 symbol 的所有可得日线；连续合约是 `RB0`，不能给 `rb1505` 预热。官方示例的 RB0 可追溯到 2009 年，但这是连续序列示例，不能推出全部旧具体合约保留期限。Sina 适配源码用公开 `InnerFuturesNewService.getDailyKLine`，参数为具体 symbol；没有逐日起止或可用历史起点保证。空响应、改版、代码不匹配均需区分。[Akshare 官方文档](https://akshare.akfamily.xyz/data/futures/futures.html#id74)、[Sina 适配官方源码](https://github.com/akfamily/akshare/blob/main/akshare/futures/futures_zh_sina.py)

`ak.get_futures_daily(start_date="20140102", end_date="20140102", market="SHFE")` 返回交易所该期间全部合约，字段含交易日、OHLC、volume、open_interest、settle；逐日取后按 manifest 筛具体合约。官方源码有 CFFEX 自 2010-04-16、CZCE 不同年代格式分支，可作为实现参考；这不证明旧端点今日均可达。代码中的 DCE 请求地址及格式已变更过，不能复制旧 endpoint 后把失败认作历史无数据。公开网站的可达性、格式、缺日和零交易日需逐项验收。[交易所日报适配官方源码](https://github.com/akfamily/akshare/blob/main/akshare/futures/futures_daily_bar.py)

EDB 的免认证参数示意：`GET https://edb.shinnytech.com/md/kline`，`period=86400`、`symbol=SHFE.rb1505`、`start_time=2014-01-01 00:00:00`、`end_time=2015-05-31 23:59:59`、`col=open,high,low,close,volume,open_oi,close_oi`；**不传 token、不请求 token 服务**。其 `86400` 按交易日返回，`datetime_nano` 是 Unix ns；文档的预计 2021 起点使其本轮用途仅为公开实存探针。[EDB 官方文档](https://doc.shinnytech.com/edb/latest/md_server.html)

## RQData：离线参考调用规格

仅在以后已有本地 RQData 权限时使用以下参数；本轮未 import、init 或调用：

```python
# 接口规格示意，未执行，不含初始化或凭证。
rqdatac.get_price(
    order_book_ids=["RB1505", "JM1505", "CF1505"],
    start_date="20140101", end_date="20150531", frequency="1d",
    fields=["open", "high", "low", "close", "volume", "open_interest", "settlement"],
    adjust_type="none", expect_df=True,
)
# 合约清单与边界先查 all_instruments(type="Future") / instruments("CF1505")。
# 历史挂牌切片用 futures.get_contracts("CF", date="20141201")，不能只查今天。
```

RQData 使用大写产品与四位年月，例如 `CF1505`；官方把郑商所三位数字补全年份，`listed_date/de_listed_date/exchange` 可帮助验证身份；股票式交易所后缀不适用期货。官方例子可查询旧合约行情，但文档不替代账号实际数据权限和具体寿命覆盖验收。[通用 API 官方说明](https://www.ricequant.com/doc/rqdata/python/generic-api)

RQData 的郑商所日线由 tick 合成，未包含盘后交易成交；不能与交易所日报所有字段天然视为相同。官方明确旧新产品代码存在乘数变化：`ME` 的 1505 及以前与后来的 `MA`，`TC` 的 1604 及以前与后来的 `ZC` 应隔离。跨制度合约不能仅换名称以填满 AM120。[RQData 期货数据约定](https://www.ricequant.com/doc/rqdata/python/futures-mod)

## 日期、交易量与验收合同

- 原始 Unix ns 应先按 UTC 解释，再转 `Asia/Shanghai`；不得把 ns 直接本地化后再次加八小时。保留 `raw_datetime_ns` 和供应商时间语义。
- 日 K 的 86400 是交易日聚合，不能机械等同自然日 24 小时。部分供应商会以交易日午夜标记；若如此上海日期本身可正确。必须用实际样本和原始交易日字段核对，不能统一将所有日 K 夜盘“加一天”。分钟夜盘、周末和节假日另需交易日日历；本报告没有认定旧下载器日期一定错误。
- 郑商所 `CF505` 可属于 2015 或 2025。验收主键至少为 `(exchange, product, delivery_year_month, trading_day)`，必须核对 expected epoch 和上市/最后交易日；不能按字符串 CF505 合并或让 2025 bars 进入 2015 的 AM120。
- OHLC 和 close/settlement 分开；OI 的开盘值与收盘值分开。保留 raw volume/OI、来源及待认定的单/双边口径，不静默补零、不补不存在的开盘持仓。
- 商品期货在 2020 前后有统计口径变化。当前上期所日报说明成交量/OI为单边，但本次未获得足以认证所有供应商已统一调整历史的证据。应固定数个真实日期与原始交易所值比对再决定是否换算，不能对所有 2020 前数值无条件除二。[上期所日报说明](https://www.shfe.com.cn/reports/tradedata/dailyandweeklydata/?query_params=kx)
- 上市到最后交易日“理论交易日集合”、实际 bar 集合、有效 OHLC、零成交真实日、供应商缺日和主力前 AM120 就绪度分别报告。普通序列前端 padding 的 `id<0` / `datetime<=0` / NaN 行不能计为历史。
- 不将价格形态平滑主连、跨代同名合约、未来最后交易日作为当时信号；完整寿命边界在此只用于数据质量审计。重跑模型之前重新冻结数据版本，避免按扩样后结果选供应商或日期。

以下是可离线执行的客户端消费例子，只读已经落地且通过身份/交易日审核的标准化文件；它不建 TqApi，不触网：

```python
from pathlib import Path
import pandas as pd

def load_accepted_daily(path: Path, expected_epoch: str) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"contract_epoch": "string", "trading_day": "string"})
    if set(df["contract_epoch"].dropna()) != {expected_epoch}:
        raise ValueError("contract_epoch_mismatch")
    key = ["contract_epoch", "trading_day"]
    if df.duplicated(key).any():
        raise ValueError("duplicate_daily_key")
    prices = df[["open", "high", "low", "close"]].apply(pd.to_numeric, errors="coerce")
    invalid = prices.isna().any(axis=1) | (prices <= 0).any(axis=1)
    invalid |= prices.high < prices[["open", "low", "close"]].max(axis=1)
    invalid |= prices.low > prices[["open", "high", "close"]].min(axis=1)
    if invalid.any():
        raise ValueError("invalid_ohlc")
    return df.sort_values("trading_day").reset_index(drop=True)
```

该片段只示意离线消费，**不独立证明寿命完整、交易日准确、数据使用许可或历史 PIT**；这些应由先验 manifest 与覆盖报告审核。

## 安全与本次行为边界

本机检查只输出 provider 名、所需键有值布尔及包版本，没有输出账号、密码、token；没有连接 CTP/broker/SMTP，没有发送任何带凭证认证请求，没有安装、下载或修改环境。root 单独执行的小样本不能算成本 agent 的已验收数据。

未来实际探针应使用研究输出目录和显式模拟账户对象，不实例化交易账户；设置超时、小并发、首个权限失败即停止。对外仅记录 provider、symbol、HTTP 状态或自定义错误码与异常类型；不输出 `str(exc)`、`repr(exc)`、traceback、响应正文、带认证的 URL/headers。旧全量下载器 `repr(exc)` 与 datafeed 的完整 traceback 不宜用于本轮真实认证日志，需在研究层做安全封装。

开始/结束判断：本次没有调模型、经济参数或按收益筛选历史，不构成新增过拟合；仍不能证明现有策略无后验风险。继续补数有条件有价值：先证明同代合约 pre-main 真历史与 AM120 资格改善，再冻结一次扩样协议；当前不能由文档直接宣称五年有效训练样本已恢复。
