---
name: ack-pod-triage
description: Triage Kubernetes Pod failures using read-only observations.
---

# ACK Pod 故障初排

1. 收集命名空间、Pod 状态和事件。
2. 阅读日志并区分调度、镜像和应用错误。
3. 先提供证据，不直接修改生产配置。

只使用已授权的数据和工具；不要自动执行生产变更。
