# Stage029 m7三测试文件独立源审

时间：2026-11-02T21:51:23.359118+08:00。PASS_WITH_LIMITATIONS，699项只读检查全过，P0/P1/P2=0/0/0。接受当前固定字节的test-only改动及定向原始证据；尚未冻结m7，不是完整CI或生产资格。

tracked diff精确为3个测试文件。默认298关键源仅这3项变化，另外295逐SHA不变；m6的388份顶层只有这3项变化，另外385同R6和实际M6，其中全部276个非测试物料/产品文件逐SHA不变，执行位未改。新增/修改/删除策略参数均无。

weekly19分支按实际活动物料判断，强断言profile/AI关闭/两端None；C9原严格路径与不可变目录/文件检查保留，未知身份失败，没有skip或删除原测试。新增2个隔离子进程测试真实消费hash固定的C9物料；只在lightweight版本或latest-pool输入边界补历史输入，实际Stage945 producer、profile resolver、Stage929 CSV reader/阈值函数未mock。947保留禁止重型导入与control/data分离，补完整五文件active/data/control三份独立夹具，真实路径选择、校验器、source验证与发布执行，检查active五文件SHA不变。

原RED：74项/4失败；第一次GREEN001：76项/1失败（新增C9receipt夹具尚未提供真正的lightweight历史版本输入）；最终GREEN002原XML独算76项/0失败/0错误/0跳过。三份原XML与日志SHA均保留，2个新增测试真实存在，当前源码修改时间均早于最终XML，未改变原失败结论。

原M6完整Q_M仍是96套件2408项/4失败、未qualified。m7必须新source/release，再实际exact R7完整96套件及两份新正式readonly，随后新M7与canonical Q_M7；76项定向通过不能冒全量，不能激活失败M6。根HEAD当前e302803e9f359a651628e56b8cb961fd2d5906c5仅是源审基底，不冒称新m7 source。

源pin、全部298新SHA、原结果SHA及完整检查见同名JSON（SHA256 fbd98698d4b3dd955a180fd9f30cd3f361f6d22529ca9d70c7910857c1f5dbb9）。审查者未执行测试/CTP/TQ/网络/SMTP/金融回放，未改产品代码或Git。

调研与判断：原完整失败、真实产品分流和未修改的resolver输入边界共同支持此最窄三测试文件兼容修复，不通过伪造AI物料或mock校验器处理。过拟合：否，未改策略/风险/参数；继续有价值：是，按新不可变版本走完整资格，原研究NO_PROMOTION保留。
