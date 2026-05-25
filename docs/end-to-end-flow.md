# Behavior-Psychology Skill — End-to-End Flow

## 完整流程（以一次真实分析为例）

### 场景
用户说：**"我同事在项目会议上打断我三次，而且总是最后才回复我的消息"**

---

## Step 1: 意图检测 & 触发

Agent 检测到触发词（"帮我分析" / "为什么TA会" / 行为描述），进入 behavior-psychology 模式。

---

## Step 2: 行为输入解析（Agent 内部）

Agent 从用户描述中提取：

| 字段 | 提取结果 |
|:---|:---|
| **Observed behavior** | 打断说话 + 延迟回复 |
| **Context** | 项目会议、工作沟通 |
| **Relationship** | 同事 |
| **Frequency** | 模式化（"总是"） |
| **person_key** | `colleague_001`（匿名化） |

---

## Step 3: RAG 检索（调用 rag_retriever.py）

### 3a. 语义搜索历史案例

```bash
python3 scripts/rag_retriever.py search \
  "同事在项目会议上打断我三次，而且总是最后才回复我的消息" \
  --top-k 3 \
  --tags [control,dominance_display]
```

**内部执行：**
1. 调用 OpenAI `text-embedding-3-small` API 生成 1536 维向量
2. 加载 `knowledge_base/cases.json`
3. 计算余弦相似度 + tag 重叠 boost
4. 返回 top-3 案例

**示例输出（假设之前分析过类似案例）：**
```
[Score: 0.78] case_20260520_143000
  Desc: 同事在会议上多次打断我，且回复消息很慢
  Tags: control, dominance_display, status_protection
  Mechanisms: status_protection, emotional_regulation

[Score: 0.62] case_20260521_101500
  Desc: 朋友在群里突然冷淡
  Tags: avoidance, boundary_setting
  Mechanisms: boundary_setting, emotional_regulation

[Score: 0.45] case_demo_001
  Desc: 同事在项目会议上连续打断我三次
  Tags: control, dominance_display, low_priority
  Mechanisms: status_protection
```

### 3b. 检索人物画像

```bash
python3 scripts/rag_retriever.py profile-summary colleague_001
```

**输出（假设是首次分析）：**
```
No profile found for colleague_001
```

**如果是第 N 次分析同一同事：**
```
[历史画像] 该人物已被分析 2 次。
关系类型: colleague
高频行为标签: control, dominance_display
高频心理机制: status_protection, emotional_regulation
```

---

## Step 4: Tag 匹配（Agent 内部）

Agent 读取 `knowledge_base/behavior_patterns.json`，匹配行为标签：

| 行为 | 匹配标签 | 强度 |
|:---|:---|:---:|
| 打断说话 | `[control, dominance_display, impatience]` | medium |
| 延迟回复 | `[low_priority, boundary_setting, status_protection]` | low |

**组合标签：** `[control, dominance_display, status_protection, low_priority]`

---

## Step 5: 机制生成 + RAG 增强（Agent 内部）

Agent 读取 `knowledge_base/psychological_mechanisms.json`，匹配机制：

| 机制 | 普适性 | 置信度 | 匹配理由 |
|:---|:---|:---:|:---|
| `status_protection` | 高 | 0.7 | 打断+延迟都是地位保护信号 |
| `emotional_regulation` | 高 | 0.5 | 可能处于高压期 |
| `control` | 中 | 0.4 | 控制欲或焦虑 |

**RAG 增强注入 prompt：**
> "你之前分析过一个类似案例（case_20260520_143000，相似度 0.78），同事在会议上打断且回复慢。当时分析指向 status_protection（置信度 0.7），实际后续观察发现对方确实在赶 deadline。这提示工作压力是一个常见替代解释。"

---

## Step 6: 替代解释（Agent 内部）

Agent 读取 `knowledge_base/alternative_explanations.json`，拉取该标签组合的替代解释：

**必须输出至少 3 个：**

1. **高可能：** 他当前处于高强度项目期，注意力被 deadline 分散，沟通风格变急促
2. **高可能：** 他的成长/职业环境中，打断是正常讨论方式（并非不尊重）
3. **中可能：** 他对这个项目有不同优先级判断，你的议题在他视角中权重较低
4. **中可能：** 个人沟通风格差异（直接型 vs 委婉型）

---

## Step 7: 结构化输出（Agent → 用户）

```markdown
## 行为观察
同事在项目会议上打断我三次，且总是最后才回复我的消息。

## 可能的心理机制
| 机制 | 普适性 | 置信度 | 解释 |
|:---|:---|:---:|:---|
| status_protection | 高 | 0.7 | 打断+延迟回复可能是维护专业地位的信号 |
| emotional_regulation | 高 | 0.5 | 高压期情绪管理能力下降 |
| control | 中 | 0.4 | 控制讨论节奏或焦虑表现 |

## 替代解释（重要）
1. **高可能：** 他当前处于高强度项目期，deadline 临近导致沟通风格变急促
2. **高可能：** 他的职业环境中，打断是正常讨论方式（并非不尊重）
3. **中可能：** 他对项目有不同优先级判断，你的议题在他视角权重较低
4. **中可能：** 纯粹的性格/沟通风格差异（直接型 vs 委婉型）

## 历史参考
你之前分析过一个相似案例（同事打断+回复慢），后续发现对方确实在赶 deadline。

## 需要更多信息
- 这是最近才有的变化，还是一直如此？
- 不回复之前你们有过什么互动？
- 他对其他人也这样吗？

## 总体评估
- **最可能解释：** status_protection / 工作压力导致的沟通风格变化
- **置信度：** 0.6（中等）
- **建议：** 暂时不急于对抗；如果持续，可以私下温和询问"最近是不是项目压力大？"

---
*This is speculation based on limited information. Only your colleague knows their true reasons.*
```

---

## Step 8: 用户反馈 & 归档

### 情况 A：用户确认并补充信息
用户说：**"后来他确实跟我道歉了，说最近在赶一个大项目"**

→ Agent 归档案例 + 更新画像

```bash
# 8a. 写入案例库
python3 scripts/rag_retriever.py add-case \
  "同事在项目会议上打断我三次，而且总是最后才回复我的消息" \
  --tags [control,dominance_display,status_protection] \
  --mechanisms '[{"name":"status_protection","confidence":0.7},{"name":"emotional_regulation","confidence":0.5}]' \
  --alternatives ["工作高压期","沟通风格差异","优先级不同"] \
  --outcome "user_confirmed_work_stress"

# 8b. 更新人物画像
python3 scripts/rag_retriever.py update-profile colleague_001 \
  --tags [control,dominance_display,status_protection] \
  --mechanisms '[{"name":"status_protection","confidence":0.7}]' \
  --confidence 0.7
```

**cases.json 新增条目：**
```json
{
  "id": "case_20260524_131800",
  "timestamp": "2026-05-24T13:18:00+08:00",
  "user_description": "同事在项目会议上打断我三次...",
  "behavior_tags": ["control", "dominance_display", "status_protection"],
  "mechanisms": [
    {"name": "status_protection", "confidence": 0.7},
    {"name": "emotional_regulation", "confidence": 0.5}
  ],
  "alternatives": ["工作高压期", "沟通风格差异", "优先级不同"],
  "embedding": [0.023, -0.015, ...],
  "outcome": "user_confirmed_work_stress",
  "notes": ""
}
```

**user_profiles.json 更新：**
```json
{
  "colleague_001": {
    "relationship": "colleague",
    "analysis_count": 1,
    "recurring_tags": ["control", "dominance_display", "status_protection"],
    "recurring_mechanisms": ["status_protection", "emotional_regulation"],
    "confidence_trend": [
      {"timestamp": "2026-05-24T13:18:00+08:00", "confidence": 0.7}
    ],
    "user_notes": ""
  }
}
```

### 情况 B：用户不确认，无后续
→ 仍然写入 cases.json，但 outcome 为空。画像不更新或标为 `uncertain`。

---

## Step 9: 写入备忘录（可选，由 Agent 自动执行）

Agent 调用 `memo_cli.py` 写入摘要：

```bash
python3 ~/.openclaw/workspace/skills/personal-memo/scripts/memo_cli.py add \
  "行为心理分析：同事打断+延迟回复 → status_protection（置信度0.7），实际为工作高压" \
  --category note \
  --tags ["behavior-psychology","colleague_001","status_protection"]
```

---

## Step 10: 下次分析同一同事时

用户说：**"那个同事今天又打断我了，而且这次是在老板面前"**

→ Step 3b 检索画像时输出：

```
[历史画像] 该人物已被分析 1 次。
关系类型: colleague
高频行为标签: control, dominance_display, status_protection
高频心理机制: status_protection, emotional_regulation
置信度趋势: [0.7]
上次结果: user_confirmed_work_stress
```

→ Agent 在分析中注入：
> "这个同事（colleague_001）你之前分析过，当时指向 status_protection，后续确认为工作压力。今天是同一行为模式但在老板面前发生，可能说明压力源变化（如需要在老板面前表现），建议关注是否有竞争/晋升相关情境。"

---

## 数据流向图

```
用户输入
    ↓
[Agent] 解析行为输入
    ↓
[rag_retriever.py search] 生成 embedding → 查 cases.json → 返回 top-3 相似案例
[rag_retriever.py profile-summary] 查 user_profiles.json → 返回人物画像
    ↓
[Agent] 读 behavior_patterns.json → 匹配标签
[Agent] 读 psychological_mechanisms.json → 匹配机制
[Agent] 读 alternative_explanations.json → 拉替代解释
    ↓
[Agent] 把检索结果注入 prompt → 调用 LLM → 生成结构化报告
    ↓
用户看到分析结果
    ↓
用户反馈 / 确认 / 补充
    ↓
[rag_retriever.py add-case] 写入 cases.json（含 embedding）
[rag_retriever.py update-profile] 更新 user_profiles.json
[memo_cli.py add] 写入 memo.md（可选）
```

---

## 依赖条件

| 依赖 | 说明 |
|:---|:---|
| `OPENAI_API_KEY` | 环境变量或 `~/.openclaw/openclaw.json` 中配置，用于 embedding API |
| Python 3.8+ | `rag_retriever.py` 运行环境 |
| 网络 | 首次生成 embedding 需要联网调用 OpenAI API |

---

## 性能预期

| 环节 | 耗时 | 说明 |
|:---|:---|:---|
| Embedding 生成 | ~500ms | OpenAI API 调用 |
| 向量检索 | ~10ms | 本地 JSON，case 数 <1000 时极快 |
| 文件读取 | ~5ms | JSON 文件很小 |
| LLM 生成分析 | 2-5s | 取决于模型和输出长度 |
| **总计** | **~3-6s** | 从用户输入到输出报告 |

---

## 当前案例库状态

```bash
python3 scripts/rag_retriever.py list-profiles
```

**输出：**
```
（空 — 尚无分析记录）
```

因为还没有真实运行过，cases.json 只有 3 条演示案例，user_profiles.json 为空。

**首次实际分析后，案例库开始自动累积。**
