# Stage265 全市场期货日线数据入口

更新时间：2026-10-17；统一目标：2010-01-01—2026-10-16。包含六所全部可识别真实期货交割合约、历史退市代码及大商所月均价F合约；未下载新分钟数据。

这是一套已落盘的原始与隔离规范资料库，尚不是已统一量仓单位、可直接训练或导入正式数据库的成品。原始OHLC、成交量、收盘持仓保留供应商/官方语义，不拼接争议值。

|交易所|历史真实合约文件|2010至9月底原始合约日|当前合约目录|
|---|---:|---:|---:|
|SHFE|3,260|666,662|238|
|INE|394|101,251|63|
|DCE|3,221|685,809|250|
|CZCE|2,841|609,165|243|
|CFFEX|692|68,736|28|
|GFEX|139|25,581|48|

历史骨架共10,547个合约、97个有数据的历史品种代码、2,157,204条2010年起原始合约日，截止2026-09-30。另一个S代码只在2003年元数据中出现，没有H5行情，不计入97。当前870个合约全部有近期来源状态；另保留10月14日退市ZC610。数量不与官方/备份层相加，后者高度重叠。

## 从这里读取

- [机器可读总清单](research/lines/futures_trend_rollover_shape_same_volume/outputs/stage265_deep_daily/data_catalog.json)
- [当前870合约及一个近期退市合约的来源状态](research/lines/futures_trend_rollover_shape_same_volume/outputs/stage265_deep_daily/current_contract_source_census.csv)
- [历史逐合约生命周期/覆盖清单](research/lines/futures_trend_rollover_shape_same_volume/outputs/stage265_deep_daily/rqalpha/full_market_contract_inventory.csv)
- [完整研究元数据JSON](research/lines/futures_trend_rollover_shape_same_volume/outputs/stage265_deep_daily/rqalpha/futures_metadata.json)
- [六所历史日线H5](research/lines/futures_trend_rollover_shape_same_volume/outputs/stage265_deep_daily/rqalpha/futures.h5)
- [官方SHFE/INE/CFFEX原包与规范层目录](research/lines/futures_trend_rollover_shape_same_volume/outputs/stage265_deep_daily/other_exchanges/official_reference_catalog.json)
- [大商所2006—2022逐合约日线](research/lines/futures_trend_rollover_shape_same_volume/outputs/stage265_deep_daily/dce/official_fullmarket_daily.csv)
- [大商所/郑商所/广期所近期日线下载清单](research/lines/futures_trend_rollover_shape_same_volume/outputs/stage265_deep_daily/tq_latest/recent_download_status.json)
- [主库与映射未变证据](research/lines/futures_trend_rollover_shape_same_volume/outputs/stage265_deep_daily/primary_integrity.json)

H5以厂商order_book_id为键（如RB1505、CF1505、L2605F）；CZCE的CF1505映射到交易所CF505时必须使用明确交割年月，不能丢失十年身份。datetime是YYYYMMDD000000；open_interest为日终持仓。含连续/指数的数据集不能直接使用，真实合约以逐合约清单筛选。

```python
import h5py
with h5py.File('research/lines/futures_trend_rollover_shape_same_volume/outputs/stage265_deep_daily/rqalpha/futures.h5', 'r') as data:
    raw = data['RB1505'][:]  # 只读原始层；不代表所有行可训练
```

## 近期补尾与非成交状态

SHFE/INE使用官方10月8、9、12—16日逐日数据；CFFEX使用包含10月16日的10月官方包。DCE/CZCE/GFEX使用天勤普通日线542个符号，未请求专业区间接口。星期五夜盘产生的10月19日未完成K线364条已排除。

5个空序列：CZCE.CY708、JR611、JR707、PM703、RS706。它们是已上市的真实合约；本次只读quote在等待真实行情消息后，last_price仍为空、V=0/OI=0（pre_close/pre_settlement有效），9月底历史也全为零成交。只记为本次可观测无成交价，不推断10月每天零成交，不伪造OHLC。ZC610最后10月14日与元数据退市日一致。

10月16日官方层包含SHFE238（214有价格、24零成交缺价）、INE63（50有价格、13零成交缺价）、CFFEX28。冷门合约没有成交不意味着下载失败；完整性应同时查看原始源、生命周期和非成交记录。

## 质量边界

- 2010年起607,134条V=0记录不计作真实成交日或AM120前史；其中厂商可能写正价格平价K线。
- 807条正成交量但OHLC几何错误、695条候选上市日期冲突已逐行列出；不自动修价。695条中仅3条有正成交量，仍需来源核对。
- 2010年前另有一条Y0607异常，因此全历史异常为808；107个合约在2006-01-26/27的214原始记录不在厂商交易日历，单列日历争议。
- 量仓单位不能全期统一除2。官方与RQ历史重叠存在来源/时期差异，收盘OI也不能替换旧库开盘OI；unknown单位及争议行保留。
- 逐合约2010年起相对于厂商生命周期/日历的原始行缺口为0，这不等于交易所已认证每一笔上市资料，也不把无成交填充行当真实成交。
- 档案是事后快照，不能证明当时可见的PIT字节；公开可下载不等于允许商业使用或再分发。原始文件仅保留本机ignored目录。

## 下载来源与判断

- [RQAlpha官方下载实现](https://github.com/ricequant/rqalpha/blob/master/rqalpha/cmds/bundle.py)提供公开月度包地址；已下载202610固定原包1,044,966,957字节，SHA与成员SHA见receipt。仅提取期货与元数据，未安装/执行第三方回测策略。
- 交易所官方SHFE2002—2026与INE2018—2026共34年度源（复用上次6包），CFFEX2010-04—2026-10共199月，合计233档案及14尾部JSON。
- DCE历史公开静态包229份（2006—2022）保存50,815,751字节；后续年份由全市场骨架与近期补尾覆盖，官方交叉层不伪称含2023以后。
- GitHub Work固定2018-04-26快照126文件仅作CZCE2015—2018的交叉证据，不冒充完整2026资料。
- 没有发现一键技能能免去历史身份/非成交/量仓审查；本次采用已有研究脚本和直接数据源，没有安装不必要的外部技能或付费套餐。

无新增选参型过拟合；仍有价值：是，全市场与退市记录能减少只研究当前池的幸存者偏差。下一步应先冻结统一研究读取与单位合同，再扩样一次；本轮模型训练、财务回测、订单API均为0。

**SHFE 有行情历史代码（20）：** AD, AG, AL, AO, AU, BR, BU, CU, FU, HC, NI, OP, PB, RB, RU, SN, SP, SS, WR, ZN

**INE 有行情历史代码（5）：** BC, EC, LU, NR, SC

**DCE 有行情历史代码（26）：** A, B, BB, BZ, C, CS, EB, EG, FB, I, J, JD, JM, L, LG, LH, L_F, M, P, PG, PP, PP_F, RR, V, V_F, Y

**CZCE 有行情历史代码（33）：** AP, CF, CJ, CY, ER, FG, JR, LR, MA, ME, OI, PF, PK, PL, PM, PR, PX, RI, RM, RO, RS, SA, SF, SH, SM, SR, TA, TC, UR, WH, WS, WT, ZC

**CFFEX 有行情历史代码（8）：** IC, IF, IH, IM, T, TF, TL, TS

**GFEX 有行情历史代码（5）：** LC, PD, PS, PT, SI
