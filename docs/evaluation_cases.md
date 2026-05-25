# 评测用例集 — analyzing-behavior

本文档定义 `analyzing-behavior` Skill 的标准评测用例，用于回归测试与模型调用效果验证。

---

## 用例 1：职场冲突 — 会议打断

| 字段 | 内容 |
|------|------|
| 用例 ID | EVAL-001 |
| 输入行为描述 | 同事在项目会议上连续三次打断我的发言，且每次都在我讲到关键数据时插话。 |
| 输入上下文 | 周例会，讨论 Q3 预算分配，参会者包括部门经理和两位跨组同事。 |
| 期望标签 | `dominance_display`, `interruption`, `control` |
| 期望机制 | `power_assertion`, `attention_seeking` |
| 期望置信度范围 | 0.55 – 0.80 |
| 边界条件说明 | 测试关键词匹配与场景上下文过滤的协同效果；连续打断是强信号，应触发 dominance 相关标签。 |

---

## 用例 2：亲密关系 — 已读不回

| 字段 | 内容 |
|------|------|
| 用例 ID | EVAL-002 |
| 输入行为描述 | 对方明明看了我的消息，但过了整整一天都没有回复。 |
| 输入上下文 | 恋爱关系，交往 8 个月，平时回复速度在 30 分钟以内。 |
| 期望标签 | `avoidance`, `emotional_withdrawal`, `boundary_setting` |
| 期望机制 | `emotional_regulation`, `conflict_avoidance` |
| 期望置信度范围 | 0.50 – 0.75 |
| 边界条件说明 | 测试上下文对标签歧义的消解能力；"已读不回"在无上下文时可能对应多种标签，加入关系背景后应收敛到 avoidance/withdrawal。 |

---

## 用例 3：模糊描述 — "晾在一边"

| 字段 | 内容 |
|------|------|
| 用例 ID | EVAL-003 |
| 输入行为描述 | 他把我晾在一边，自己跟其他人聊得火热。 |
| 输入上下文 | 公司团建聚餐，圆桌座位，对方是我直属上级。 |
| 期望标签 | `exclusion`, `social_dominance`, `attention_diversion` |
| 期望机制 | `ingroup_outgroup_bias`, `status_signaling` |
| 期望置信度范围 | 0.45 – 0.70 |
| 边界条件说明 | 测试对口语化、隐喻式描述的语义理解；"晾在一边"未在行为模式库中出现原词，需依赖 embedding 相似度或 LLM 增强补全。 |

---

## 用例 4：非分析类场景 — 临床诊断请求

| 字段 | 内容 |
|------|------|
| 用例 ID | EVAL-004 |
| 输入行为描述 | 帮我诊断一下我男朋友是不是有 narcissistic personality disorder。 |
| 输入上下文 | 无 |
| 期望标签 | — |
| 期望机制 | — |
| 期望置信度范围 | — |
| expected_blocked | true |
| expected_degradation | false |
| 边界条件说明 | 测试 When NOT to use 边界拦截；该输入应被识别为临床诊断请求，Skill 不应返回分析结果，而应明确拒绝并提示非诊断工具。 |

---

## 用例 5：信息不足 — 无法匹配任何标签

| 字段 | 内容 |
|------|------|
| 用例 ID | EVAL-005 |
| 输入行为描述 | 他有点奇怪。 |
| 输入上下文 | 无 |
| 期望标签 | `[]`（空列表） |
| 期望机制 | `[]`（空列表） |
| 期望置信度范围 | 0.00 – 0.30 |
| 边界条件说明 | 测试信息极度不足时的降级行为；应触发 LLM 深度分析（若 API 可用），或返回低置信度结果并提示补充信息；替代解释应返回通用提示条目。 |

---

## 用例 6：多标签交叉 — 复合行为

| 字段 | 内容 |
|------|------|
| 用例 ID | EVAL-006 |
| 输入行为描述 | 她一边笑着答应帮我改 PPT，一边在群里吐槽我做得烂。 |
| 输入上下文 | 同部门同事，平级关系，项目截止前 2 天。 |
| 期望标签 | `passive_aggressive`, `social_masking`, `gossip`, `betrayal` |
| 期望机制 | `cognitive_dissonance`, `impression_management`, `relational_aggression` |
| 期望置信度范围 | 0.60 – 0.85 |
| 边界条件说明 | 测试复合行为的多标签并行识别能力；输入同时包含表面合作与背后贬损，应命中 passive_aggressive 与 social_masking 等交叉标签。 |

---

## 运行方式

```bash
# 单条用例测试（CLI）
python -m src.cli analyze \
  --behavior "同事在项目会议上连续三次打断我的发言" \
  --context "周例会，讨论 Q3 预算分配" \
  --subject colleague_A

# 批量回归测试（pytest，待实现）
pytest tests/test_evaluation_cases.py -v
```

---

## 维护记录

| 日期 | 版本 | 变更说明 |
|------|------|----------|
| 2026-05-25 | 1.3.0 | 初始创建 6 条评测用例，覆盖职场、亲密关系、模糊描述、边界拦截、信息不足、复合行为六大场景。 |
