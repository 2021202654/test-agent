# 04 记忆系统

## 状态：✅ 已实现

### 三层记忆

| 层 | 文件 | 说明 |
|------|------|------|
| **短期记忆** | `../core/memory.py -> ShortTermMemory` | 滑动窗口对话队列，自动按 token 截断 |
| **工作记忆** | `../core/memory.py -> WorkingMemory` | 当前研究任务上下文（检索词/已读论文/中间结果） |
| **长期记忆** | `../core/memory.py -> Memory`（预留接口） | 用户偏好、高频查询缓存 |

### 使用示例

```python
from core.memory import Memory

mem = Memory()

# 短期：自动管理对话
mem.short.add(Message.user("你好"))

# 工作：存储任务状态
mem.working.set("task_state", "searching")
mem.working.append("search_keywords", "SBLI")
mem.working.append("read_papers", "10.1063/5.0294696")

# 快照
snapshot = mem.working.snapshot()
```
