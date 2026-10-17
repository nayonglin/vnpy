# Stage263 AM口径事实纠正（回放后描述性诊断）

- 初始协议和可行性讨论误写AM140。当前master的`array_manager_size_floor=120`，源设置`ma_extra_long=40`、`donchian_entry_period=20`，故实际AM尺寸是`max(40+20+20,120)=120`。
- 研究子类始终以`type(old)(size=old.size)`重建原尺寸，没有设置140、缩短窗口或更改经济规则。本次accepted源实际使用120，原始源CSV与其SHA不变，不因此重跑源。
- 初次描述性AM140诊断已归档为superseded；后续按源代码真实120计算准备率。早期无成交不能归咎于本研究新增了140门槛。
- 原始生成前协议保持字节及SHA不变，使用时应同时读取本事实纠正；这是错误更正，不是看到收益后更改实验参数。
