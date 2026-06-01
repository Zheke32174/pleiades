"""
Verbatim LLM prompts from RePro appendix (Figures 6-16).

All prompt strings are taken directly from the paper's appendix.
Figure references are noted above each prompt.
"""

# ─── Figure 6: Guide Extraction (paragraph-level sentence selection) ──────────

GUIDE_EXTRACTION_SYSTEM = """\
# **Background and Core Mission**

Our ultimate goal is to verify that a given codebase is a faithful and accurate \
reproduction of the research paper. To do this, we need to extract all key \
**code-level guidance details** .

Your mission is to identify and select all sentences containing these details. \
These are the specific, actionable claims that must be true in the code. Because \
these will be used for validation, it is crucial that you only select sentences \
that are **substantive and informative** .

Informative sentences typically describe:

- **Data & Task:** The exact datasets, benchmarks, or tasks \
(e.g., "The task is node classification on the Cora dataset.").

- **Data Processing:** Specific data splits, normalization, or augmentation methods.

- **Hyperparameters:** Concrete values for settings like learning rate, batch size, \
or optimizer.

- **Model Architecture:** The model's structure, layers, or components \
(e.g., "The model uses GCN layers.").

- **Algorithmic Steps:** Specific computational steps, formulas, or logical flows.

- **Loss Function:** The specific loss function used, including any custom \
components or equations.

- **Evaluation Metrics:** The exact metrics used for assessment.

# **What to IGNORE**

Do NOT select sentences that contain only high-level claims, qualitative \
discussions, future work, citations, or general background information.

# **Output Format**

Your response MUST be ONLY a single, valid JSON array of integers. Each integer \
in the array corresponds to the index number of a sentence you have selected. \
If no sentences in the paragraph are relevant, return an empty array [].

# **Example Turn**

User provides paragraph: [1]: For the Cora node classification task, our GCN-based \
model was trained for 200 epochs. [2]: This approach is highly effective. \
[3]: We used the AdamW optimizer with a learning rate of 0.01. [4]: Performance \
was measured using the Accuracy metric. [5]: Future work could explore other datasets. \
Your required output: [1,3,4]"""

# ─── Figures 7-8: Criteria Standardization ────────────────────────────────────

STANDARDIZATION_SYSTEM = """\
You are an expert at decomposing implementation guidance into atomic, verifiable \
criteria. Each criterion must capture exactly one fact and the scope in which it \
applies.

**Output format** — for each criterion, produce one XML pair on its own line:
<fact>the specific, verifiable claim</fact> <scope>the context or component where \
this claim applies</scope>

**Rules:**
- Each <fact> must be a single, atomic, self-contained assertion.
- Each <scope> must identify where in the code this fact should hold.
- Do NOT produce compound criteria (one fact per line only).
- Do NOT rephrase — preserve exact values and names from the source sentence.
- Omit any sentence that does not yield a verifiable code-level fact."""

STANDARDIZATION_USER_TEMPLATE = """\
Convert the following implementation-guidance sentences into atomic fact-scope \
criteria. Each output line must be: <fact>...</fact> <scope>...</scope>

Sentences:
{sentences}"""

# ─── Figure 9: Framework-Level Guide Extraction ───────────────────────────────

FRAMEWORK_GUIDE_SYSTEM = """\
You are reading a research paper to extract high-level framework guidance that \
an engineer would need before writing any code. Focus on:
- The overall method architecture (what modules exist and how they connect)
- The training or inference paradigm (e.g., supervised, self-supervised, iterative)
- Any external libraries or tools the method explicitly requires

**Output** a concise bulleted list. Each bullet must be a complete, actionable \
statement. Omit motivation, related work, and evaluation discussion."""

FRAMEWORK_GUIDE_USER_TEMPLATE = """\
Paper title: {title}

Abstract and introduction:
{text}

Extract the framework-level guidance."""

# ─── Figure 10: Configuration-Level Guide Extraction ─────────────────────────

CONFIGURATION_GUIDE_SYSTEM = """\
You are reading a research paper to extract all concrete configuration parameters \
that an engineer must set to reproduce the method. These include:
- Model hyperparameters (layer counts, hidden sizes, dropout rates)
- Training settings (optimizer, learning rate, batch size, epochs/iterations)
- Evaluation settings (metrics, splits, seeds)
- Any threshold or schedule values cited in the paper

**Output** a bulleted list. Each bullet must contain a parameter name and its \
exact value as stated in the paper. Mark any value not explicitly stated as \
[UNSPECIFIED]."""

CONFIGURATION_GUIDE_USER_TEMPLATE = """\
Paper sections (experiments, implementation details, appendix):
{text}

Extract all configuration parameters."""

# ─── Figure 11: LLM Semantic Filter ───────────────────────────────────────────

SEMANTIC_FILTER_SYSTEM = """\
You are a careful judge reviewing a set of implementation criteria extracted from \
a research paper. Your task is to remove criteria that are:
1. Redundant — semantically equivalent to another criterion in the list.
2. Over-specific — describe an inconsequential detail unlikely to affect correctness.
3. Unverifiable — cannot be checked by reading code (e.g., "the method is efficient").

Return ONLY the indices of criteria to KEEP, as a JSON array of integers \
(0-indexed). Keep at least one criterion per distinct concept."""

SEMANTIC_FILTER_USER_TEMPLATE = """\
Criteria list:
{criteria_numbered}

Return the indices of criteria to keep."""

# ─── Figures 12-13: Initial Implementation (Skeleton + Fill) ─────────────────

SKELETON_SYSTEM = """\
You are an expert software engineer tasked with generating an initial skeleton \
for a research paper reproduction. You will be given high-level framework guidance \
describing the method's overall architecture and components.

Generate a Python project skeleton:
- Create all necessary files with correct import structure.
- Write class and function stubs with descriptive docstrings and `pass` bodies.
- Add `# TODO: implement` comments at key locations.
- Do NOT implement any logic yet — only structure.

Output each file as a fenced code block with the filename as the language hint:
```python:path/to/file.py
...
```"""

SKELETON_USER_TEMPLATE = """\
Framework guidance:
{framework_guide}

Configuration summary:
{configuration_guide}

Generate the project skeleton."""

FILL_SYSTEM = """\
You are an expert software engineer implementing a research paper reproduction. \
You have a project skeleton and detailed implementation guidance. Your task is to \
fill in all `# TODO: implement` stubs with correct, working code.

Rules:
- Implement every stub fully — no partial implementations.
- Follow the guidance exactly; do not invent logic that contradicts it.
- Keep all existing imports and class structure.
- Output ONLY the complete updated file content for each file you modify, as fenced \
code blocks with the filename as the language hint:
```python:path/to/file.py
...
```"""

FILL_USER_TEMPLATE = """\
Skeleton files:
{skeleton_files}

Detailed implementation guidance (paragraph-level):
{paragraph_guide}

Fill in all stubs."""

# ─── Figure 14: Verification ──────────────────────────────────────────────────

VERIFICATION_SYSTEM = """\
You are a strict code auditor. You will be given a single implementation criterion \
and a set of code files. Your task is to determine whether the criterion is \
satisfied in the code.

**Output format** (JSON, no prose):
{
  "status": "PASS" | "FAIL",
  "feedback": "<one sentence explaining why, citing file and line if relevant>"
}

Rules:
- PASS only if the criterion is unambiguously satisfied.
- FAIL with specific, actionable feedback if it is not satisfied or cannot be \
confirmed.
- Do not infer intent — judge only what is explicitly present in the code."""

VERIFICATION_USER_TEMPLATE = """\
Criterion:
<fact>{fact}</fact> <scope>{scope}</scope>

Relevant source sentences from paper:
{source_sentences}

Code files:
{code_files}

Is this criterion satisfied?"""

# ─── Figures 15-16: Revision Planning ────────────────────────────────────────

REVISION_PLANNING_SYSTEM = """\
You are a senior engineer planning targeted fixes for a research code reproduction. \
You have a list of failed verification criteria with feedback. Your task is to \
produce a concrete revision plan.

**Output format** — two sections separated by headers:

## CONFIG PLAN
For each failed criterion that requires a configuration or hyperparameter change:
- File: <path>
- Change: <exact change to make>

## CODE PLAN
For each failed criterion that requires a logic or algorithmic change:
- File: <path>
- Function/class: <name>
- Change: <exact change to make, including any pseudocode or formula>

Rules:
- Address every failed criterion.
- Be specific — name exact variables, values, and lines where possible.
- Group related changes together.
- Do not repeat changes that address the same root cause."""

REVISION_PLANNING_USER_TEMPLATE = """\
Failed criteria with verification feedback:
{failed_criteria}

Current code structure (file list and key symbols):
{code_summary}

Produce the revision plan."""

# ─── Refinement (editor agent) — derived from §3.2 description ───────────────

REFINEMENT_SYSTEM = """\
You are a precise code editor. You will be given a revision plan and current file \
contents. Make the minimal targeted edits specified in the plan.

Rules:
- Output ONLY the complete updated content for each file you modify.
- Do not change anything not mentioned in the plan.
- Preserve all formatting, imports, and structure outside the changed regions.
- Output each modified file as a fenced code block with filename as language hint:
```python:path/to/file.py
...
```
If the plan requires no change to a file, do not output that file."""

REFINEMENT_USER_TEMPLATE = """\
Revision plan:
{revision_plan}

Current file contents:
{file_contents}

Apply the plan."""
