# Goal Admission Tools

这个目录现在只保留仍可单独运行的分析驱动脚本。

- 已移除 rollout / canary / report / rehearsal 类冻结脚本，避免继续扩展二级发布工具链。
- 这些工具不属于默认启动链路。
- 默认启动入口仍然是 `services/core/scripts/start_dev_server.sh`。
- 如果后续重新需要灰度链路，建议在归档需求下重建，而不是继续恢复旧脚本。
