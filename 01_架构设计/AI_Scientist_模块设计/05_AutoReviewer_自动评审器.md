# AutoReviewer — 自动评审器

> 模拟审稿人反馈 + 优化建议
> 多维度评分 + 反馈闭环

---

## 模块定位

**输入**：论文草稿 + 原始假设 + 实验数据
**输出**：评审意见 + 评分 + 修改建议 + 修订版本

**核心能力**：
- 模拟审稿人视角（多维度评分）
- 识别论文弱点（创新性、可复现性、实验充分性）
- 生成具体修改建议
- 自动修订（基于反馈）

---

## 独创性设计

### 1. 多维度评审框架

传统方法：单一维度评价（如创新性）

**我们的方法**：5 维度 + 3 层次评审框架

```
评审维度
    ↓
┌──────────────────────────────────────┐
│ 维度 1: 创新性                       │
│   - 与现有工作的差异度               │
│   - 新方法的科学价值                 │
│   - 对领域的推动作用                 │
├──────────────────────────────────────┤
│ 维度 2: 方法论                       │
│   - 实验设计的合理性                 │
│   - 计算方法的准确性                 │
│   - 参数选择的依据                   │
├──────────────────────────────────────┤
│ 维度 3: 结果与讨论                   │
│   - 结果是否充分                     │
│   - 讨论是否深入                     │
│   - 与文献对比是否全面               │
├──────────────────────────────────────┤
│ 维度 4: 可复现性                     │
│   - 代码是否可用                     │
│   - 数据是否公开                     │
│   - 实验描述是否清晰                 │
├──────────────────────────────────────┤
│ 维度 5: 写作质量                     │
│   - 结构是否清晰                     │
│   - 语言是否流畅                     │
│   - 引用是否规范                     │
└──────────────────────────────────────┘
```

**评审层次**：
```
Level 1: 宏观评审（整体结构、贡献明确性）
Level 2: 中观评审（各章节内容完整性）
Level 3: 微观评审（细节问题、语言表达）
```

---

### 2. 量化评分系统

```python
class QuantitativeReviewer:
    """量化评分系统"""

    def __init__(self):
        self.dimensions = {
            "innovation": "创新性",
            "methodology": "方法论",
            "results": "结果与讨论",
            "reproducibility": "可复现性",
            "writing": "写作质量"
        }

        self.scoring_criteria = {
            "innovation": {
                5: "显著推动领域发展，新方法具有重要科学价值",
                4: "有一定创新，对现有工作有明显改进",
                3: "创新一般，主要是现有方法的验证",
                2: "创新性不足，与现有工作重复度高",
                1: "无创新，完全复制现有工作"
            },
            "methodology": {
                5: "实验设计完善，方法严谨，参数选择有充分依据",
                4: "实验设计合理，方法基本正确",
                3: "实验设计基本合理，方法有改进空间",
                2: "实验设计有明显缺陷，方法不够严谨",
                1: "实验设计不合理，方法有严重问题"
            }
            # ... 其他维度
        }

    def score_paper(self, paper: dict, hypothesis: dict, analysis: dict) -> dict:
        """
        量化评分
        """
        scores = {}
        comments = {}

        for dim, name in self.dimensions.items():
            score, comment = self._score_dimension(
                dim, paper, hypothesis, analysis
            )
            scores[dim] = score
            comments[dim] = comment

        # 计算综合评分
        overall_score = sum(scores.values()) / len(scores)

        # 判定接受/修改/拒稿
        decision = self._make_decision(scores, overall_score)

        return {
            "overall_score": overall_score,
            "decision": decision,
            "dimension_scores": scores,
            "dimension_comments": comments,
            "summary": self._generate_summary(scores, comments, decision)
        }

    def _score_dimension(
        self,
        dimension: str,
        paper: dict,
        hypothesis: dict,
        analysis: dict
    ) -> tuple[int, str]:
        """
        评分单个维度
        """
        # 这里用 LLM 进行评分
        prompt = self._build_scoring_prompt(dimension, paper, hypothesis, analysis)
        response = self.llm.chat([Message.user(prompt)])
        result = json.loads(response.content)

        return result["score"], result["comment"]
```

---

### 3. 自动修订系统

评审后自动修订，而非仅提建议。

```python
class AutoRevisionSystem:
    """自动修订系统"""

    def __init__(self, llm: LLMInterface):
        self.llm = llm

    def revise_paper(
        self,
        paper: str,
        review_comments: dict
    ) -> dict:
        """
        根据评审意见自动修订论文
        """
        revisions = {}

        # 1. 按章节分组修订意见
        by_section = self._group_by_section(review_comments)

        # 2. 逐章修订
        for section, comments in by_section.items():
            section_content = self._extract_section(paper, section)

            if not comments:
                revisions[section] = {"status": "no_change"}
                continue

            # 生成修订版本
            revised_content = await self._revise_section(
                section_content, comments
            )

            # 记录修订
            revisions[section] = {
                "status": "revised",
                "comments_count": len(comments),
                "changes_made": [c["type"] for c in comments],
                "revised_content": revised_content
            }

        # 3. 拼接修订后的论文
        revised_paper = self._assemble_revised_paper(paper, revisions)

        return {
            "revised_paper": revised_paper,
            "revision_summary": {
                "total_comments": len(review_comments),
                "sections_revised": len([r for r in revisions.values() if r["status"] == "revised"]),
                "sections_unchanged": len([r for r in revisions.values() if r["status"] == "no_change"])
            }
        }

    async def _revise_section(
        self,
        section_content: str,
        comments: list[dict]
    ) -> str:
        """
        修订单个章节
        """
        prompt = f"""
你是论文修订专家。

# 原始章节内容
{section_content}

# 修订意见
{json.dumps(comments, indent=2, ensure_ascii=False)}

# 任务
根据修订意见修改章节内容，保持原有风格。

# 输出格式
直接输出修订后的 LaTeX 内容。
"""

        response = await self.llm.chat([Message.user(prompt)])
        return response.content
```

---

## 核心流程

```
输入：论文草稿 + 假设 + 实验数据
         ↓
┌──────────────────────────────────────┐
│ Step 1: 多维度评分                   │
│   - 5 个维度评分                     │
│   - 3 个层次评审                     │
│   - 量化评分输出                     │
└──────────────────┬───────────────────┘
                   ↓
┌──────────────────────────────────────┐
│ Step 2: 生成评审意见                 │
│   - 识别论文弱点                     │
│   - 生成具体修改建议                 │
│   - 判定接受/修改/拒稿               │
└──────────────────┬───────────────────┘
                   ↓
┌──────────────────────────────────────┐
│ Step 3: 自动修订                     │
│   - 按章节分组修订意见               │
│   - 逐章自动修订                     │
│   - 生成修订版本                     │
└──────────────────┬───────────────────┘
                   ↓
┌──────────────────────────────────────┐
│ Step 4: 修订验证                     │
│   - 验证修订是否解决原问题           │
│   - 检查是否引入新问题               │
│   - 生成修订报告                     │
└──────────────────┬───────────────────┘
                   ↓
输出：评审报告 + 修订论文 + 修订报告
```

---

## Prompt 模板

```python
REVIEW_PROMPT = """
你是一名高超声速气固界面耦合领域的审稿人。

# 待评审论文
{paper_content}

# 原始假设
{hypothesis}

# 实验数据
{experiment_data}

# 评审任务
1. 从 5 个维度评分（创新性、方法论、结果与讨论、可复现性、写作质量）
2. 识别论文的 3-5 个主要问题
3. 针对每个问题给出具体修改建议

# 评分标准
创新性：
- 5: 显著推动领域发展，新方法具有重要科学价值
- 4: 有一定创新，对现有工作有明显改进
- 3: 创新一般，主要是现有方法的验证
- 2: 创新性不足，与现有工作重复度高
- 1: 无创新，完全复制现有工作

方法论：
- 5: 实验设计完善，方法严谨，参数选择有充分依据
- 4: 实验设计合理，方法基本正确
- 3: 实验设计基本合理，方法有改进空间
- 2: 实验设计有明显缺陷，方法不够严谨
- 1: 实验设计不合理，方法有严重问题

结果与讨论：
- 5: 结果充分，讨论深入，与文献对比全面
- 4: 结果较充分，讨论基本完整
- 3: 结果基本充分，讨论不够深入
- 2: 结果不够充分，讨论缺失关键点
- 1: 结果严重不足，讨论缺失

可复现性：
- 5: 代码可用，数据公开，实验描述清晰
- 4: 代码可用，实验描述基本清晰
- 3: 代码基本可用，实验描述有改进空间
- 2: 代码不可用或实验描述不清晰
- 1: 无代码或实验描述严重缺失

写作质量：
- 5: 结构清晰，语言流畅，引用规范
- 4: 结构基本清晰，语言基本流畅
- 3: 结构一般，语言有改进空间
- 2: 结构混乱，语言表达不清
- 1: 结构严重混乱，语言错误多

# 接受/修改/拒稿判定
- 接受：综合评分 ≥ 4.0
- 小修：3.5 ≤ 综合评分 < 4.0
- 大修：3.0 ≤ 综合评分 < 3.5
- 拒稿：综合评分 < 3.0

# 输出格式（JSON）
{
  "overall_score": 4.2,
  "decision": "accept",
  "dimension_scores": {
    "innovation": 4,
    "methodology": 4,
    "results": 4,
    "reproducibility": 5,
    "writing": 4
  },
  "dimension_comments": {
    "innovation": "评论",
    ...
  },
  "major_issues": [
    {
      "issue": "问题描述",
      "severity": "major/minor",
      "location": "章节/段落",
      "suggestion": "修改建议"
    }
  ],
  "summary": "评审总结"
}
"""
```

---

## 与现有工具的集成

```python
class AutoReviewer(Action):
    """自动评审器工具"""

    name = "review_paper"
    description = "模拟审稿人评审论文并生成修订版本"
    parameters = {
        "type": "object",
        "properties": {
            "paper_path": {"type": "string", "description": "论文文件路径"},
            "hypothesis": {"type": "string", "description": "JSON 格式的假设信息"},
            "analysis": {"type": "string", "description": "JSON 格式的分析结果"}
        },
        "required": ["paper_path"]
    }

    def __init__(self, llm: LLMInterface):
        self.llm = llm
        self.quantitative_reviewer = QuantitativeReviewer()
        self.auto_revision = AutoRevisionSystem(llm)

    async def run(self, paper_path: str, hypothesis: str = None, analysis: str = None) -> str:
        # 1. 加载论文
        paper_content = self._load_paper(paper_path)

        # 2. 解析输入
        hyp = json.loads(hypothesis) if hypothesis else {}
        ana = json.loads(analysis) if analysis else {}

        # 3. 量化评分
        review_result = self.quantitative_reviewer.score_paper(
            paper_content, hyp, ana
        )

        # 4. 生成评审意见
        review_comments = await self._generate_review_comments(
            paper_content, hyp, ana
        )

        # 5. 如果需要修订
        revised_paper = None
        if review_result["decision"] in ["major_revision", "minor_revision"]:
            revision_result = self.auto_revision.revise_paper(
                paper_content, review_comments
            )
            revised_paper = revision_result["revised_paper"]

        # 6. 生成评审报告
        review_report = self._generate_review_report(
            review_result, review_comments, revision_result
        )

        # 7. 保存结果
        output_paths = self._save_results(
            review_report,
            revised_paper,
            review_result["decision"]
        )

        return json.dumps({
            "review_result": review_result,
            "review_comments": review_comments,
            "revised_paper_path": output_paths["revised"],
            "review_report_path": output_paths["report"]
        }, indent=2, ensure_ascii=False)
```

---

## 评测指标

| 指标 | 定义 | 目标值 |
|------|------|--------|
| **评审一致性** | 与人工审稿人评分的相关性 | ≥ 0.8 |
| **修订有效性** | 修订后解决原问题的比例 | ≥ 70% |
| **建议可执行性** | 修改建议可被执行的比例 | ≥ 80% |
| **接受判定准确率** | 接受/修改/拒稿判定准确率 | ≥ 75% |

---

## 反馈闭环

```
论文草稿
    ↓
AutoReviewer 评审
    ↓
[判定：修改]
    ↓
自动修订
    ↓
修订版本
    ↓
AutoReviewer 再评审
    ↓
[判定：接受] → 论文完成
    ↓
[判定：修改] → 循环
```

---

## 参考文献（设计参考）

- [Nature: Peer Review Automation](https://www.nature.com/articles/s42256-024-00837-w) — 自动化评审框架
- [OpenResearch: Auto-Reviewer](https://github.com/openresearch/open-research) — 审稿人模拟系统
- [The AI Scientist: Automated Peer Review](https://sakana.ai/ai-scientist/) — 自动评审闭环