# 第三方来源与许可边界

自有代码、文档和设计采用MIT；以下依赖仍保留原协议，不被项目根许可覆盖：

- ST官方HAL、CMSIS Device和CMSIS Core，通过 `firmware/sources.lock.json` 与bootstrap固定来源和校验。依赖不直接打包；下载后应保留其LICENSE及文件头，HAL与CMSIS各自许可不能互相替代。
- `firmware/platform`中沿用厂商模板的文件保留现有文件头。自有MIT不覆盖原作者声明。
- 嘉立创EDA、KiCad、Arm GNU工具链、build123d/cadgen等工具不随项目发布，各自按其工具或依赖许可使用。
- WeAct开发板、DFRobot麦克风等官方参考资料并未因下载到本机就获得本项目的再许可。原始参考模型与包含参考实体的完整装配未再分发；自有零件及源码中的尺寸/接口依据应结合官方资料复核。

浏览器截图和候选结构渲染是本工程输出，展示设计状态，不构成厂商背书、实测结果或制造放行。
