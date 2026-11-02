# Stage025 最小修复源码独立预审

PASS_WITH_LIMITATIONS，源码条件接受；剩余实现P0/P1/P2为0，完整CI待绑定。2个实现文件共3行：expected生产路径resolve(strict=False)，实际repo构造仍strict=True；Friday初次独占创建ENOENT加入原8次重试，最后一次仍沿旧raise/外层outbox_open_failed，不改其他闸门。2个回归测试文件新增3例。其余294critical同R4，全部298测试前后SHA无漂移。

真实方法的原路径7例全过。原Friday7例保留断言为6过1失败，唯一差异是原型AST返回race_exhausted而实际保留last-raise返回open_failed，不能假写7/7原样绿；新增实际语义2例均过，确证恰8次、0sender、ReportError原因ENOENT，且existing-inode消失也有边界。权限/软链仍阻断，sending/unknown与发送后落盘异常不盲重试。

原Q_R Friday失败根因仍UNKNOWN：原每suite原始轨迹被runner finally删除。独立注入只能证明另一个确定性恢复缺口，不能认定已解释原失败，也不为过绿修改断言或放宽资格。未来新source需新物料和完整资格，m4冻结证据不改。

未CTP/SMTP、金融回放、订单/撤单、生产或Git index修改。无alpha/本金/备用金/委托策略改变。过拟合：否；继续有价值：是，等待完整CI和随后真实资格。
