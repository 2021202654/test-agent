# PaperWriter — 论文生成器

> 从实验结果到完整 LaTeX 论文
> 7 章结构自动生成 + 图表自动插入

---

## 模块定位

**输入**：假设 + 实验数据 + 分析结果 + 文献引用
**输出**：完整 LaTeX 论文（含图表 + 参考文献）+ 可复现代码包

**核心能力**：
- 7 章标准结构自动生成
- 图表自动插入与引用
- 参考文献自动管理（BibTeX）
- 可复现代码包生成

---

## 独创性设计

### 1. 领域专属 LaTeX 模板

通用模板缺少气固热物理领域的特定结构。

**我们的方法**：定制化领域模板

```latex
% 气固热物理领域专属模板
\documentclass[10pt,a4paper]{article}

% 宏包
\usepackage{amsmath,amssymb,amsthm}
\usepackage{graphicx}
\usepackage{booktabs}
\usepackage{physics}  % 物理符号
\usepackage{siunitx}  % 单位
\usepackage{hyperref}

% 气固热物理专用命令
\newcommand{\heatflux}{\dot{q}_w}       % 驻点热流
\newcommand{\knudsen}{Kn}               % 克努森数
\newcommand{\catalytic}{\gamma}         % 催化效率
\newcommand{\slipcoef}{\sigma_v}        % 滑动系数
\newcommand{\tempjump}{\sigma_T}        % 温度跳跃系数
\newcommand{\fayriddell}{\dot{q}_{FR}   % Fay-Riddell 公式

% 7 章标准结构
\begin{document}

\title{论文标题}
\author{作者}
\date{\today}

\maketitle

\section{Introduction}
% 研究背景 + 问题陈述 + 贡献

\section{Theoretical Framework}
% 物理方程 + 模型假设 + 理论推导

\section{Methodology}
% 实验设计 + 计算方法 + 参数设置

\section{Results}
% 实验结果 + 数据分析 + 可视化

\section{Discussion}
% 结果解释 + 与文献对比 + 局限性

\section{Conclusions}
% 结论 + 未来工作

\bibliography{references}
\bibliographystyle{aiaa}

\end{document}
```

---

### 2. 图表自动插入系统

传统方法：手动插入图片，容易出错

**我们的方法**：基于分析结果自动生成图表引用

```python
class AutoFigureInserter:
    """图表自动插入器"""

    def __init__(self):
        self.figure_registry = {
            "parameter_scan": "fig_parameter_scan",
            "phase_diagram": "fig_phase_diagram",
            "consistency_comparison": "fig_consistency",
            "error_analysis": "fig_error_analysis"
        }

        self.table_registry = {
            "parameter_table": "tab_parameters",
            "results_summary": "tab_results",
            "comparison_table": "tab_comparison"
        }

    def insert_figures(self, analysis: dict, tex_content: str) -> str:
        """
        根据分析结果自动插入图表
        """
        # 1. 识别需要插入的图表
        required_figures = analysis.get("visualization_specs", [])

        # 2. 在 Results 章节插入图表
        results_section = self._extract_section(tex_content, "Results")

        for fig_spec in required_figures:
            fig_code = self._generate_figure_code(fig_spec)
            results_section = self._insert_at_position(
                results_section,
                fig_code,
                position="after_subsection"
            )

        # 3. 在 Discussion 章节插入图表引用
        discussion_section = self._extract_section(tex_content, "Discussion")

        for fig_spec in required_figures:
            fig_ref = self.figure_registry.get(fig_spec["type"], "")
            discussion_section = self._insert_figure_reference(
                discussion_section,
                fig_ref,
                context=fig_spec.get("description", "")
            )

        # 4. 拼回完整文档
        tex_content = self._replace_section(
            tex_content,
            "Results",
            results_section
        )
        tex_content = self._replace_section(
            tex_content,
            "Discussion",
            discussion_section
        )

        return tex_content

    def _generate_figure_code(self, fig_spec: dict) -> str:
        """生成 LaTeX 图表代码"""
        return f"""
\\begin{{figure}}[htbp]
\\centering
\\includegraphics[width=0.8\\textwidth]{{{fig_spec['filename']}}}
\\caption{{{fig_spec.get('caption', 'Figure')}}}
\\label{{fig:{fig_spec['type']}}}
\\end{{figure}}
"""
```

---

## 核心流程

```
输入：假设 + 实验数据 + 分析结果 + 文献
         ↓
┌──────────────────────────────────────┐
│ Step 1: 结构生成                     │
│   - 7 章标准结构                     │
│   - 领域专属模板加载                 │
└──────────────────┬───────────────────┘
                   ↓
┌──────────────────────────────────────┐
│ Step 2: 内容生成                     │
│   - Introduction：背景 + 问题 + 贡献 │
│   - Theory：物理方程 + 模型推导      │
│   - Method：实验设计 + 计算方法      │
│   - Results：结果描述 + 数据分析    │
│   - Discussion：解释 + 对比 + 局限  │
│   - Conclusion：结论 + 未来工作      │
└──────────────────┬───────────────────┘
                   ↓
┌──────────────────────────────────────┐
│ Step 3: 图表插入                     │
│   - 根据分析结果生成图表代码         │
│   - 自动插入 LaTeX 文档             │
│   - 生成图表引用                     │
└──────────────────┬───────────────────┘
                   ↓
┌──────────────────────────────────────┐
│ Step 4: 参考文献管理                 │
│   - BibTeX 文件生成                  │
│   - 引用自动插入                     │
│   - 格式统一                         │
└──────────────────┬───────────────────┘
                   ↓
┌──────────────────────────────────────┐
│ Step 5: 可复现代码包生成             │
│   - 代码整理 + 注释                  │
│   - 环境配置文件                     │
│   - README 生成                      │
└──────────────────┬───────────────────┘
                   ↓
输出：完整 LaTeX 论文 + 代码包
```

---

## Prompt 模板（分章节生成）

```python
# Introduction 章节生成
INTRODUCTION_PROMPT = """
你是一名高超声速气固界面耦合领域的论文写作专家。

# 待写作章节：Introduction

# 研究背景
{research_background}

# 研究问题
{research_problem}

# 主要贡献
{main_contributions}

# 文献综述（简要）
{literature_summary}

# 写作要求
1. 开篇：高超声速再入热防护的重要性
2. Gap：现有研究在{gap_area}的不足
3. 本工作：提出{innovation}解决上述问题
4. 贡献：列出 3-4 条具体贡献
5. 结构：后续章节安排

# 输出格式（LaTeX）
\\section{Introduction}
... （约 800-1200 词）
"""

# Theory 章节生成
THEORY_PROMPT = """
# 待写作章节：Theoretical Framework

# 核心物理方程
{physics_equations}

# 模型假设
{model_assumptions}

# 理论推导
{theoretical_derivation}

# 写作要求
1. Fay-Riddell 公式及其适用范围
2. 催化复合系数的物理意义
3. 滑动边界条件（Maxwell 滑动模型）
4. Knudsen 数对流动的影响

# 输出格式（LaTeX）
\\section{Theoretical Framework}
... （包含数学公式）
"""
```

---

## 与现有工具的集成

```python
class PaperWriter(Action):
    """论文生成器工具"""

    name = "write_paper"
    description = "生成完整的 LaTeX 论文"
    parameters = {
        "type": "object",
        "properties": {
            "hypothesis": {"type": "string", "description": "JSON 格式的假设信息"},
            "analysis": {"type": "string", "description": "JSON 格式的分析结果"},
            "literature": {"type": "string", "description": "JSON 格式的文献引用"}
        },
        "required": ["hypothesis", "analysis"]
    }

    def __init__(self, llm: LLMInterface):
        self.llm = llm
        self.template_loader = LaTeXTemplateLoader()
        self.figure_inserter = AutoFigureInserter()
        self.bib_manager = BibTeXManager()

    async def run(self, hypothesis: str, analysis: str, literature: str = None) -> str:
        # 1. 解析输入
        hyp = json.loads(hypothesis)
        ana = json.loads(analysis)
        lit = json.loads(literature) if literature else {}

        # 2. 加载模板
        template = self.template_loader.load_template(
            "gas_solid_thermal_template.tex"
        )

        # 3. 逐章生成内容
        sections = {}
        sections["Introduction"] = await self._generate_introduction(hyp, lit)
        sections["Theoretical Framework"] = await self._generate_theory(hyp)
        sections["Methodology"] = await self._generate_methodology(hyp, ana)
        sections["Results"] = await self._generate_results(ana)
        sections["Discussion"] = await self._generate_discussion(ana, lit)
        sections["Conclusions"] = await self._generate_conclusions(hyp, ana)

        # 4. 填充模板
        tex_content = self._fill_template(template, sections)

        # 5. 插入图表
        tex_content = self.figure_inserter.insert_figures(ana, tex_content)

        # 6. 生成参考文献
        bib_file = self.bib_manager.generate_bibtex(lit)
        tex_content = self._add_bibliography(tex_content, bib_file)

        # 7. 保存论文
        paper_path = self._save_paper(tex_content)

        # 8. 生成可复现代码包
        code_package = self._generate_code_package(ana)

        return json.dumps({
            "paper_path": paper_path,
            "bib_file": bib_file,
            "code_package": code_package,
            "word_count": self._count_words(tex_content)
        }, indent=2, ensure_ascii=False)

    async def _generate_introduction(self, hypothesis: dict, literature: dict) -> str:
        """生成 Introduction 章节"""
        prompt = INTRODUCTION_PROMPT.format(
            research_background=literature.get("background", ""),
            research_problem=hypothesis.get("problem", ""),
            main_contributions=hypothesis.get("contributions", []),
            literature_summary=literature.get("summary", ""),
            gap_area=hypothesis.get("gap", "")
        )

        response = await self.llm.chat([Message.user(prompt)])
        return response.content
```

---

## 可复现代码包生成

```python
class ReproducibilityPackageGenerator:
    """可复现代码包生成器"""

    def generate_package(self, analysis: dict) -> dict:
        """
        生成完整的可复现代码包
        """
        package = {
            "code/": {
                "main.py": self._generate_main_script(analysis),
                "config.yaml": self._generate_config(analysis),
                "requirements.txt": self._generate_requirements(),
                "utils/": self._generate_utils()
            },
            "data/": {
                "sample_data.csv": "示例数据",
                "results/": "结果目录"
            },
            "README.md": self._generate_readme(),
            ".gitignore": self._generate_gitignore()
        }

        # 保存为 zip
        zip_path = self._save_as_zip(package)

        return {"zip_path": zip_path, "contents": package}

    def _generate_main_script(self, analysis: dict) -> str:
        """生成主执行脚本"""
        return """
#!/usr/bin/env python3
"""
可复现实验主脚本

运行方法：
    python main.py --config config.yaml

预期结果：
    与论文中的 Figure X、Table Y 一致
"""

import argparse
import yaml
from utils.experiment import run_experiment
from utils.analysis import analyze_results

def main():
    parser = argparse.ArgumentParser(description="Reproduce experiments")
    parser.add_argument("--config", default="config.yaml", help="配置文件")
    args = parser.parse_args()

    # 加载配置
    with open(args.config, 'r') as f:
        config = yaml.safe_load(f)

    # 运行实验
    results = run_experiment(config)

    # 分析结果
    analysis = analyze_results(results, config)

    # 保存结果
    analysis.save_to_csv("results/experiment_results.csv")

    print("实验完成！结果已保存到 results/ 目录")

if __name__ == "__main__":
    main()
"""
```

---

## 评测指标

| 指标 | 定义 | 目标值 |
|------|------|--------|
| **结构完整性** | 7 章结构完整性 | 100% |
| **图表插入正确率** | 图表引用与插入一致性 | ≥ 95% |
| **参考文献格式正确率** | BibTeX 格式正确率 | ≥ 98% |
| **代码可复现性** | 代码包可一键运行 | 100% |
| **LaTeX 编译成功率** | 首次编译无错误 | ≥ 90% |

---

## 参考文献（设计参考）

- [AutoGPT-Scientist](https://github.com/koenvo/AutoGPT-Scientist) — 自动化论文生成流程
- [OpenResearch: Paper Generation](https://github.com/openresearch/open-research) — LaTeX 模板管理
- [The AI Scientist: Paper Writing](https://sakana.ai/ai-scientist/) — 端到端论文生成架构