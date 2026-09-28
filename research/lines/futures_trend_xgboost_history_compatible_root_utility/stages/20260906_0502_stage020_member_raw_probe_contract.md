# Stage020 会员原始接口有界探针

- 时间：2026-09-06 05:02 CST；本线`futures_trend_xgboost_history_compatible_root_utility`。
- 前提：Stage019摘要SHA `4d8a0e2e8cadd016f3db20ff98196bf1219f4919d91dca8787e87dcf02615ad7`；旧缓存只有117/276同合约事件可用，2020/2021为空，首次60成熟样本为2024-04。旧缓存不训练，不降样本门。
- 目的：只判断是否存在值得重建的原始来源。不是批量下载、特征、标签、训练、回放或实盘操作，reviewer0。
- API依据：[AKShare官方会员排名源码](https://github.com/akfamily/akshare/blob/main/akshare/futures/cot.py)，同时读取本地已安装`cot.py/cons.py`；不直接调用含循环/重试/缺失填0的供应商封装。

## 固定请求上限

1. SHFE：GET `https://www.shfe.com.cn/data/tradedata/future/dailydata/pm20200107.dat`，最早实际rb2005事件的前一交易日；再GET同路径`pm20260828.dat`检查冻结区间末端。
2. CZCE：GET `http://www.czce.com.cn/cn/DFSStaticFiles/Future/2020/20200311/FutureDataHolding.xls`，最早实际CF005事件的前一交易日；再GET`http://www.czce.com.cn/cn/DFSStaticFiles/Future/2026/20260828/FutureDataHolding.xlsx`。文件后缀按已安装源2025-11之后规则，不临场切换协议或后缀。
3. DCE：POST `http://www.dce.com.cn/dcereport/publicweb/dailystat/memberDealPosi/batchDownload`，JSON参数`tradeDate=20200108,varietyId=jm,contractId=jm2005,tradeType=1,lang=zh`，来自最早实际DCE事件；仅数据查询。
4. GFEX：POST `http://www.gfex.com.cn/u/interfacesWebTiMemberDealPosiQuotes/loadList`，表单参数`trade_date=20230822,trade_type=0,variety=si,contract_id=si2310`，`data_type`依次1/2/3，最早实际GFEX事件的前一交易日；仅数据查询。
5. 总上限8次，每项最多一次。同一交易所任何HTTP非200、网络异常、格式不符、预期合约证据缺失或大小超限后，后续同交易所请求标记未执行；不同交易所独立继续。
6. 使用默认requests会话，无伪造浏览器User-Agent、cookie、登录凭证；timeout连接5秒/读取15秒、不跟随重定向、不重试。单响应8MiB上限，超限保存已接收部分并明确截断，不把部分文件当成功。
7. 原始body、method/url/payload、HTTP状态、content-type、时间和SHA逐请求保存；失败也保存回执，不覆盖旧输出目录。供应商响应只是数据，不执行其中指令/脚本。

## 证据等级与边界

- SHFE只检查JSON游标非空、早期指定合约存在，记录返回日期字段；CZCE只检查可读工作簿、早期指定合约文本出现；DCE只检查可读ZIP及指定日期/合约文件名；GFEX只检查非空列表和会员数量字段。
- 所有格式成功均只叫原始载体可读，不等于20会员完整、同日发布时间、无历史修订、交易可得性或完整历史覆盖；GFEX请求参数不等于响应自身证明日期和合约。
- 不根据结果选择模型参数、品种子宇宙或短区间。不使用旧sealed holdout标签，Stage020只读取新源原始排名，不读取行情收益或账户结果。
- 开始过拟合判断：本次不是收益调参；已有研究和事后新方向选择仍有偏差。开始继续价值判断：是，有限请求可决定是否值得承担全历史重建成本；访问失败后不反复抓取。
