# Stage010 到期残仓行情缺口调查与执行专用双源价格overlay

- line_id：`futures_trend_full_market_noai_one_lot`。
- 记录时间：2026-10-18；独立agent只读调查与数据overlay实现。
- 重要突破：否。解决一类确定的数据时点语义问题，尚未形成策略成绩结论。
- 本阶段不跑金融回测、不下载、不改clean库、不改原inputs或训练接受合同。root先前两个实际金融失败包不在本agent工作范围内，本阶段不将它们改写成成功。

## 两个实际残仓的不同原因

### FB201801：没有可恢复的后续真实成交

精确身份`DCE.FB.201801`，native`fb1801`，vendor maturity/delisted为2018-01-15。

`Stage265/rqalpha/futures.h5`的精确dataset`FB1801`：2018-01-02真实OHLC为108.8/109.8/108.8/109.8，源双边V=8，closeOI=0；单边V=4，这条已经在clean接受。**clean并不拒绝closeOI=0**。

随后2018-01-03、04、05、08、09、10、11、12、15九个交易日，源V=0、OI=0，OHLC均109.05，settlement亦109.05。`excluded_observations.csv.gz`以`no_trade`保留，RQ raw row235—243可复查。这些是供应商无成交平价记录，不能授权市场成交，不能用1/15的109.05伪造强平。

clean最后真实成交日正是1/2，并非误删正成交bar。`full_market_contract_inventory.csv`独立统计该epoch244条raw，69条真实成交、175条V0；后续没有正成交恢复空间。当前主`.vntrader/database.db`中native`fb1801`/`FB1801`无任何bar；本机旧下载CSV也未找到该精确native。未下载或跨epoch补齐。

这表明本地市场数据支持“该合约随后极端失去流动性”的判断，不能支持“策略到期后仍可市场平仓”或“自动按缓存价了结”的结论。RQ0 OI说明原市场末尾已经清空，但反事实策略若在当日新开仓，现有全市场历史不能证明其后有可成交退出。应披露未解决残仓与全周期绩效资格受限，不按这一个结果临时筛掉FB。

### IH201812：真实到期OHLCV存在，OI结算时点跨源冲突

精确身份`CFFEX.IH.201812`，native`IH1812`，maturity=2018-12-21。clean最后bar为12/20。

RQ H5 dataset`IH1812`row165的12/21：OHLC=2336.2/2336.2/2275.4/2294.8、V=7126、OI=3497、settlement=2295.05。

官方已存在原zip：

`/Users/mac/Desktop/fian/research/lines/futures_trend_rollover_shape_same_volume/outputs/stage265_deep_daily/other_exchanges/cffex/raw_months/201812.zip`

其member`20181221_1.csv`（GB18030），包含表头第12行/零基csv行11的`IH1812`：同四价、同V=7126，OI=0、持仓变化=-9295，今结算2295.05。已冻结normalized文件`other_exchanges/normalized/CFFEX_futures_options_201812.csv.gz`同原档，SHA=`f9cdaf72e5a95d7cc6cf9789dcbe2f225ddc5c6d5151bd07f6c782465aba644a`。

`stage266_units_quarantine.csv`及两份排除记录证明：12/21因`cross_source_quantity_conflict`整键隔离，源报价没有价格或成交量分歧。这不是“零OI bar一概非法”，而是训练数据原合同保守地隔离所有数量冲突。OI0符合到期结算后的语义，但此事实不能把RQ与官方OI时点强行等同。

## 通用执行专用overlay合同与实现

root授权独立研究源新增overlay；保持clean/训练合同不动。新增：

- `tools/stage010_expiry_execution_overlay.py`。
- `tools/test_stage010_expiry_execution_overlay.py`。
- `outputs/expiry_execution_overlay.csv`。
- `outputs/expiry_execution_overlay_manifest.json`，逐行保留官方normalized与zip/member/原行、RQ H5路径/key/row/native全字段、双方源排除记录、明确合约生命周期和SHA。

固定筛选仅依数据合同：2014—2026-10-16的**整键数量隔离**；精确已知maturity必须等于bar日期；已锁官方与RQ真实OHLC、标准化单边V逐字段完全相同；V>0、正有限价格、OHLC几何合法；唯一RQ正OI与官方OI0分歧；官方数量单位合同已明确。没有按收益、方向、品种或具体IH合约名单筛选。

逐条实际复核官方normalized源文件SHA，与真实zip/member原行互相核对，并核RQ H5源SHA和精确row日期。当前实际符合结构的官方原档均为CFFEX CSV zip；其他未知原档格式不猜测，不生成。

输出与market_daily兼容，另有`execution_only=True`、`allow_new_open=False`、`evidence_id`、`settlement`与`settlement_is_executable_close=False`。**只可供已有持仓的真实报价平单/估值；不准作为新开仓、AM预热、信号或训练资格。** root必须用旗标禁止new opens，不能只把OI0塞进普通行情继续让策略开仓。

settlement与市场close明确分开。IH最后close2294.8与交割结算2295.05不同；现金交割需单独事件/费用模型，不能拿settlement伪装可交易tick价格。overlay还包含T/TF国债期货，不能把所有expiry的settlement一律当股指现金了结。

## 全结构扫描结果与验证

- 成熟日数量隔离键198，全部扫描；155有完整双源、真实原档和成熟身份链，43缺唯一双源观察，拒绝恢复。
- 155条来自CFFEX.IC、IF、IH、IM、T、TF；133条属于原研究已物化4,328个epoch。
- 全155 closeOI=0且V>0，已有accepted clean bar的重复键=0。
- 全155 `execution_only=True/allow_new_open=False`；逐条额外核RQ symbol完整YYMM、exchange/product/maturity、官方member自然日期与RQ row交易日一致，未跨epoch同名混入。
- 5项fixture先RED、实现后GREEN：结构符合接受；非成熟日/未知成熟日拒绝；任何OHLC/V不等拒绝；V0/官方OI不为0/不存在OI冲突拒绝；非法几何/非有限价格拒绝。
- 没有重跑金融；clean前后完整指纹一致。原inputs未更改。

CSV SHA256：`7a9916c55da85daf9eb58cc753fe8be3f6af6a0a78b5eec33a7ee93e3be173cc`，32,002字节。

manifest SHA256：`104a5b9d43bea5908d519f466507b275dfc4fbcab434afe2b1b029e699ca4429`。

IH201812/2018-12-21已包含于155条通用结果中。FB201801/1月3—15日V0不符合结构，没有恢复。

## 资料调研、判断和下一步

查阅[中金所结算细则官方PDF](https://www.cffex.com.cn/u/cms/www/202003/27161736r3ck.pdf)检索结果：股指期货最后交易日收市后按交割结算价了结未平仓；文档原文抓取遇到超时，未把此次抓取称为完整历史法律版本验证。直接原档中官方OI=0、RQ正OI和相同OHLCV才是本次overlay的逐条证据。另查[大商所2019年4月官方月报](https://www.dce.com.cn/dalianshangpin/resource/cms/2019/05/2019051410181769090.pdf)，列示纤维板实物交割；不把2019或现代规格机械套为2018年FB1801现金结算规则。未找到能证明FB1801后续市场成交的本地证据。

判断：将已证实的到期OI时点冲突与已有仓位的OHLCV执行资格分开有价值；原训练clean的整键保守隔离无需因此修改。FB则是真实流动性与反事实退出边界，不能靠平价结算bar包装成有效市场成交。

本阶段新增/修改alpha参数无；新增数据合同是通用expiry执行overlay，不是盈利过滤。新增/修改/删除金融结果无。权益、收益、最大回撤、Sharpe、滑点、交易次数、胜率均N/A；金融回测、模型拟合、数据下载、CTP与订单API均0。

开始与结束过拟合判断：**否（数据修复本身未按收益择优）**，依据合约生命周期和双源逐字段一致性，覆盖所有符合结构记录；这是发现残仓后的合同修订，后续结果必须标注该修订，不能声称先验完全冻结。继续价值：**是**，可恢复IH这类真实执行价格并明确FB未知边界。若仍有FB过期残仓，全周期收益不得标作已验证完整可实现成绩。root应完成其持仓账本修复、执行专用flag和费用处理，并在下一次实际回测后独立review；本agent没有替root跑回测。
