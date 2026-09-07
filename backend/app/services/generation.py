"""Prompt builders for worksheets, tests, answer keys and marking schemes.

Adapted from the TeachAssist exam generation prompts, retargeted for
Pakistani school classrooms (classes, subjects, terms) and bilingual output.
"""

from typing import Optional

from ..schemas import QuestionCounts

LANGUAGE_INSTRUCTIONS = {
    "en": "Write the content in clear, simple English suitable for Pakistani school students.",
    "ur": "Write the content in Urdu (اردو رسم الخط) suitable for Pakistani school students. Keep subject terms that are commonly used in English (e.g. Math/Science terms) as-is when that is normal in Pakistani classrooms.",
    "roman_urdu": "Write the content in Roman Urdu (Urdu written with English letters) suitable for Pakistani school students.",
}

TEST_TYPE_LABELS = {
    "weekly": "Weekly Test",
    "monthly": "Monthly Test",
    "mid_term": "Mid Term Paper",
    "final_term": "Final Term Paper",
}

DIFFICULTY_LABELS = {
    "easy": "easy (recall level, for average and weak students)",
    "medium": "medium (mix of recall and understanding)",
    "hard": "hard (application and analysis for strong students)",
}


def _question_block(counts: QuestionCounts) -> str:
    parts = []
    if counts.mcq:
        parts.append(f"- SECTION A - Multiple Choice Questions: EXACTLY {counts.mcq} questions")
    if counts.short:
        parts.append(f"- SECTION B - Short Answer Questions: EXACTLY {counts.short} questions")
    if counts.long:
        parts.append(f"- SECTION C - Long Answer Questions: EXACTLY {counts.long} questions")
    if not parts:
        parts.append("- Multiple Choice Questions: EXACTLY 5 questions")
        parts.append("- Short Answer Questions: EXACTLY 3 questions")
    return "\n".join(parts)


def _language_instruction(language: str) -> str:
    return LANGUAGE_INSTRUCTIONS.get(language, LANGUAGE_INSTRUCTIONS["en"])


def _counting_rules() -> str:
    return """
COUNTING RULES (ABSOLUTE):
- Follow the exact question counts above. Never add or remove questions.
- If a section is missing from the configuration, its count is ZERO: skip it entirely.
"""


def _output_contract(document_label: str) -> str:
    return f"""
OUTPUT FORMAT (MANDATORY):
Return the document in exactly three parts using these markers, and nothing else:

==={document_label}===
<full document: heading, school-style instructions for students, sections and questions>

===ANSWER KEY===
<answers in the same order as the questions>

===MARKING SCHEME===
<marks breakdown per question and section: how many marks per part, what earns or loses marks>
""".strip()


def build_worksheet_prompt(
    *,
    class_name: str,
    subject_name: str,
    topic: str,
    counts: QuestionCounts,
    difficulty: str = "medium",
    language: str = "en",
    instructions: Optional[str] = None,
    school_name: str = "",
) -> str:
    teacher_block = ""
    if instructions and instructions.strip():
        teacher_block = f"""
TEACHER INSTRUCTIONS (follow, but never break counting rules):
{instructions.strip()}
"""
    return f"""
You are an expert Pakistani school teacher creating a WORKSHEET (practice sheet / homework).

TARGET AUDIENCE: {class_name} students of a Pakistani school.
SUBJECT: {subject_name}
TOPIC / FOCUS: {topic}
DIFFICULTY: {DIFFICULTY_LABELS.get(difficulty, DIFFICULTY_LABELS["medium"])}
LANGUAGE: {_language_instruction(language)}

QUESTION CONFIGURATION (obey exactly):
{_question_block(counts)}
{_counting_rules()}
{teacher_block}
{_output_contract("WORKSHEET")}

QUALITY RULES:
- Age-appropriate wording for {class_name}.
- Stay strictly on the topic: {topic}.
- MCQs must have 4 options (A-D).
- Include a short "Instructions for students" line under the worksheet heading.
- School name to print on the sheet: {school_name or "School"}.
""".strip()


def build_test_prompt(
    *,
    test_type: str,
    class_name: str,
    subject_name: str,
    topic: Optional[str],
    total_marks: int,
    duration_minutes: Optional[int],
    counts: QuestionCounts,
    difficulty: str = "medium",
    language: str = "en",
    instructions: Optional[str] = None,
    school_name: str = "",
) -> str:
    label = TEST_TYPE_LABELS.get(test_type, "Test")
    teacher_block = ""
    if instructions and instructions.strip():
        teacher_block = f"""
TEACHER INSTRUCTIONS (follow, but never break counting rules):
{instructions.strip()}
"""
    duration_line = f"TIME ALLOWED: {duration_minutes} minutes" if duration_minutes else "TIME ALLOWED: decide sensibly and print it on the paper"
    return f"""
You are an expert Pakistani school teacher setting a {label.upper()} paper.

TARGET AUDIENCE: {class_name} students of a Pakistani school.
SUBJECT: {subject_name}
{f"SYLLABUS / TOPICS COVERED: {topic}" if topic else "SYLLABUS: recent chapters of the subject for this class"}
TOTAL MARKS: {total_marks} (questions must sum to exactly this total)
{duration_line}
DIFFICULTY: {DIFFICULTY_LABELS.get(difficulty, DIFFICULTY_LABELS["medium"])}
LANGUAGE: {_language_instruction(language)}

QUESTION CONFIGURATION (obey exactly):
{_question_block(counts)}
{_counting_rules()}
{teacher_block}
{_output_contract("PAPER")}

QUALITY RULES:
- Age-appropriate wording for {class_name}.
- Marks per question must add up to exactly {total_marks}.
- MCQs must have 4 options (A-D).
- Print a proper paper header: school name, subject, class, {label}, total marks, time allowed.
- School name to print on the paper: {school_name or "School"}.
""".strip()


def split_generated_sections(raw: str) -> dict:
    """Split the model output into content / answer_key / marking_scheme."""
    import re

    text = raw or ""
    markers = {
        "content": r"={2,}\s*WORKSHEET\s*={2,}|={2,}\s*PAPER\s*={2,}|={2,}\s*DOCUMENT\s*={2,}",
        "answer_key": r"={2,}\s*ANSWER KEY\s*={2,}",
        "marking_scheme": r"={2,}\s*MARKING SCHEME\s*={2,}",
    }

    positions: dict[str, tuple[int, int]] = {}
    for key, pattern in markers.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            positions[key] = (match.start(), match.end())

    def section(key: str, next_keys: list[str]) -> str:
        if key not in positions:
            return ""
        _, start = positions[key]
        end = len(text)
        for other_key in next_keys:
            if other_key in positions and positions[other_key][0] > start:
                end = min(end, positions[other_key][0])
        return text[start:end].strip()

    content = section("content", ["answer_key", "marking_scheme"])
    answer_key = section("answer_key", ["marking_scheme"])
    marking_scheme = section("marking_scheme", [])

    if not content and not answer_key:
        content = text.strip()

    return {
        "content": content,
        "answer_key": answer_key,
        "marking_scheme": marking_scheme,
    }
