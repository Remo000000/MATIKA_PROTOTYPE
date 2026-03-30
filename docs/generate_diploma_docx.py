# -*- coding: utf-8 -*-
"""Build diploma .docx from diploma_matika.md + university BЖ formatting (TNR 14, margins)."""
import re
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.shared import Mm, Pt

BASE = Path(__file__).resolve().parent
MD_PATH = BASE / "diploma_matika.md"
OUT_PATH = BASE / "Дипломка документация.docx"

# Ереже 8.5.1.2: аңдатпа ≤150 таңба; 8.5.1.6: қорытынды ≤700 таңба
ANNOT_KK = (
    "MATIKA (Django): оқу кестесін оңтайландыру; слотқа нейро болжам, greedy/GA; SQLite немесе PostgreSQL. "
    "Мақсат — деректер мен ML кестеге енгізілуі."
)
assert len(ANNOT_KK) <= 150

CONCLUSION_KK = (
    "MATIKA веб-жүйесінің архитектурасы мен іске асырылуы сипатталды: Django, рөлдер, тенант, "
    "кесте генерациясы мен GA, слоттың қолайсыздығын Keras немесе эвристика арқылы есептеу. "
    "Прототип сценарийлер бойынша тексерілді; шектеулер мен даму бағыттары көрсетілді. "
    "Нәтиже ЖОО-да пилот немесе кеңейту үшін негіз бола алады; нақты LMS интеграциясы мен "
    "өндірістік талаптар келесі кезеңде қарастырылады."
)
assert len(CONCLUSION_KK) <= 700


def set_doc_defaults(doc: Document) -> None:
    sec = doc.sections[0]
    sec.left_margin = Mm(30)
    sec.right_margin = Mm(10)
    sec.top_margin = Mm(20)
    sec.bottom_margin = Mm(20)
    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(14)
    pf = style.paragraph_format
    pf.line_spacing_rule = WD_LINE_SPACING.SINGLE
    pf.first_line_indent = Mm(12.5)


def heading_center(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(text)
    r.bold = True
    r.font.name = "Times New Roman"
    r.font.size = Pt(14)


def add_para(doc: Document, text: str, bold: bool = False) -> None:
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.bold = bold
    r.font.name = "Times New Roman"
    r.font.size = Pt(14)


def page_break(doc: Document) -> None:
    doc.add_page_break()


def _set_cell_run(cell, text: str, *, bold: bool = False, size_pt: int = 12) -> None:
    cell.text = ""
    p = cell.paragraphs[0]
    run = p.add_run(text)
    run.font.name = "Times New Roman"
    run.font.size = Pt(size_pt)
    run.bold = bold


def add_table_caption(doc: Document, caption: str) -> None:
    """Ереже 8.6.1.11: кесте нөмірі мен қысқа атау сол жақта, абзац шегініссіз."""
    p = doc.add_paragraph()
    p.paragraph_format.first_line_indent = Mm(0)
    p.paragraph_format.left_indent = Mm(0)
    r = p.add_run(caption)
    r.bold = True
    r.font.name = "Times New Roman"
    r.font.size = Pt(14)


def add_data_table(doc: Document, caption: str, headers: list[str], rows: list[list[str]]) -> None:
    add_table_caption(doc, caption)
    tbl = doc.add_table(rows=1 + len(rows), cols=len(headers))
    tbl.style = "Table Grid"
    hdr = tbl.rows[0].cells
    for i, h in enumerate(headers):
        _set_cell_run(hdr[i], h, bold=True, size_pt=12)
    for ri, row in enumerate(rows):
        for ci, val in enumerate(row):
            _set_cell_run(tbl.rows[ri + 1].cells[ci], val, bold=False, size_pt=12)
    doc.add_paragraph()


def _split_md_table_row(line: str) -> list[str]:
    line = line.strip()
    if not line.startswith("|"):
        return []
    parts = [p.strip() for p in line.split("|")]
    if parts and parts[0] == "":
        parts = parts[1:]
    if parts and parts[-1] == "":
        parts = parts[:-1]
    return parts


def _is_md_table_separator_row(cells: list[str]) -> bool:
    if not cells:
        return False
    for c in cells:
        t = re.sub(r"\s+", "", c.strip())
        if not t:
            return False
        if not re.match(r"^:?-+:?$", t):
            return False
    return True


def _parse_md_table_at(lines: list[str], start: int) -> tuple[list[str], list[list[str]], int]:
    if start >= len(lines) or not lines[start].strip().startswith("|"):
        return [], [], start
    hdr = _split_md_table_row(lines[start])
    i = start + 1
    if i < len(lines):
        sep = _split_md_table_row(lines[i])
        if sep and _is_md_table_separator_row(sep):
            i += 1
    rows: list[list[str]] = []
    while i < len(lines):
        s = lines[i].strip()
        if not s.startswith("|"):
            break
        rows.append(_split_md_table_row(lines[i]))
        i += 1
    return hdr, rows, i


def strip_md_inline(s: str) -> str:
    s = re.sub(r"`([^`]+)`", r"\1", s)
    return s


def parse_md_body(md: str) -> str:
    """Кіріспеден Қорытындыға дейін (қоспай)."""
    start = md.find("## Кіріспе")
    end = md.find("## Қорытынды")
    if start == -1 or end == -1:
        raise ValueError("MD: Кіріспе/Қорытынды бөлімдері табылмады")
    return md[start:end].strip()


def md_blocks_to_doc(doc: Document, body: str) -> None:
    """## / ###, markdown кестелері және абзацтарды Word-қа шығарады."""
    lines = body.splitlines()
    i = 0
    first_h2 = True
    while i < len(lines):
        line = lines[i].rstrip()
        if not line:
            i += 1
            continue
        if line.startswith("## ") and not line.startswith("###"):
            title = line[3:].strip()
            if not first_h2:
                page_break(doc)
            first_h2 = False
            heading_center(doc, title.upper())
            i += 1
            continue
        if line.startswith("### "):
            add_para(doc, line[4:].strip(), bold=True)
            i += 1
            continue
        if line.strip() == "---":
            i += 1
            continue
        # **Кесте N** — тақырып + markdown кесте
        if line.startswith("**Кесте") and "—" in line:
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines) and lines[j].strip().startswith("|"):
                caption = strip_md_inline(line.replace("**", "").strip())
                hdr, rows, new_i = _parse_md_table_at(lines, j)
                if hdr and rows:
                    add_data_table(doc, caption, hdr, rows)
                    i = new_i
                    continue
            # кесте жоқ — төмендегі абзац жинақтауға өтеді
        # Кесте тақырыпсыз | жолы
        if line.strip().startswith("|"):
            hdr, rows, i = _parse_md_table_at(lines, i)
            if hdr and rows:
                add_data_table(doc, "Кесте", hdr, rows)
            continue
        # жинақта абзац (келесі ### немесе ## дейін)
        buf = [strip_md_inline(line)]
        i += 1
        while i < len(lines):
            n = lines[i].rstrip()
            if not n:
                i += 1
                break
            if n.startswith("#"):
                break
            if n.startswith("**Кесте") and "—" in n:
                break
            if n.strip().startswith("|"):
                break
            buf.append(strip_md_inline(n))
            i += 1
        text = " ".join(buf).replace("  ", " ").strip()
        if text:
            add_para(doc, text)


def parse_references(md: str) -> list[str]:
    sec = md.find("## Пайдаланған әдебиеттер")
    if sec == -1:
        return []
    rest = md[sec:].split("---", 1)[0]
    out = []
    for line in rest.splitlines():
        m = re.match(r"^\s*(\d+)\.\s+(.+)$", line)
        if m:
            t = m.group(2).strip()
            if t.startswith("(") and "PDF" in t:
                continue
            out.append(t)
    # толықтырулар (жартылай атаулар)
    fix = {
        "Predicting the Performance of Students Using Deep.": "Predicting the Performance of Students Using Deep Learning.",
        "Enhancing Student Performance Prediction on Learnersourced Questions with.": (
            "Enhancing student performance prediction on learner-sourced questions with deep learning."
        ),
        "Graph Neural Network Heuristic for.": (
            "Graph neural network heuristic for the construction of initial solutions to educational timetabling problems."
        ),
        "Using Deep Learning in Student Performance.": "Using deep learning in student performance prediction.",
    }
    return [fix.get(x, x) for x in out]


def main() -> None:
    md = MD_PATH.read_text(encoding="utf-8")
    body = parse_md_body(md)
    refs = parse_references(md)

    doc = Document()
    set_doc_defaults(doc)

    heading_center(doc, "«ҚАЗАҚ ҰЛТТЫҚ ҚЫЗДАР ПЕДАГОГИКАЛЫҚ УНИВЕРСИТЕТІ» КеАҚ")
    doc.add_paragraph()
    heading_center(doc, "БІТІРУ ЖОБАСЫ")
    doc.add_paragraph()
    add_para(
        doc,
        "Тақырыбы: нейрондық желілермен деректерді талдау негізінде сабақтардың оңтайлы уақыт "
        "аралықтарын болжай отырып, оқу жоспарлары мен кестелерді басқаруға арналған веб-жүйені "
        "әзірлеу (MATIKA)",
    )
    doc.add_paragraph()
    add_para(doc, "Орындаушы: _________________________________")
    add_para(doc, "Ғылыми жетекші: _________________________________")
    add_para(doc, "Кафедра / білім беру бағдарламасы: _________________________________")
    add_para(doc, "Алматы, 2026 ж.")
    page_break(doc)

    heading_center(doc, "АҢДАТПА")
    add_para(doc, ANNOT_KK)
    page_break(doc)

    heading_center(doc, "АННОТАЦИЯ (орысша)")
    ru = re.search(
        r"## АННОТАЦИЯ.*?\n\n(.+?)\n\n---",
        md,
        re.DOTALL,
    )
    if ru:
        add_para(doc, ru.group(1).strip().replace("\n", " "))
    page_break(doc)

    heading_center(doc, "ANNOTATION (English)")
    en = re.search(
        r"## ANNOTATION.*?\n\n(.+?)\n\n---",
        md,
        re.DOTALL,
    )
    if en:
        add_para(doc, en.group(1).strip().replace("\n", " "))
    page_break(doc)

    heading_center(doc, "МАЗМҰНЫ")
    for line in (
        "Кіріспе ..........................................................................",
        "1 Пәндік саланы талдау ......................................................",
        "2 Жобалау және әзірлеу ........................................................",
        "Қорытынды ......................................................................",
        "Пайдаланған әдебиеттер ......................................................",
        "Қосымшалар .....................................................................",
    ):
        add_para(doc, line)
    add_para(
        doc,
        "Ескерту: Word-та «Мазмұн» өрісін қолданып бет нөмірлерін жаңартыңыз (Ереже 8.5.1.3).",
    )
    page_break(doc)

    # Негізгі мәтін: кіріспе + 1 + 2 бөлім (кестелер тараулар ішінде)
    md_blocks_to_doc(doc, body)

    page_break(doc)
    heading_center(doc, "ҚОРЫТЫНДЫ")
    add_para(doc, CONCLUSION_KK)
    page_break(doc)

    heading_center(doc, "ПАЙДАЛАНҒАН ӘДЕБИЕТТЕР")
    add_para(
        doc,
        "Тізім реттік нөмірмен рәсімделеді (Ереже 8.5.1.7). APA толық сипаты үшін 3-қосымшаны "
        "қолданып, автор, жыл, басылым, DOI қосыңыз.",
    )
    for i, r in enumerate(refs, start=1):
        add_para(doc, f"{i}. {r}")

    page_break(doc)
    heading_center(doc, "ҚОСЫМША А")
    add_para(doc, "UML: `docs/plantuml/` немесе PNG/SVG экспорт.")
    page_break(doc)
    heading_center(doc, "ҚОСЫМША Б")
    add_para(
        doc,
        "Скриншоттар, кесте мысалы, код үзінділері (кафедра талабына сәйкес).",
    )

    doc.save(OUT_PATH)
    print("OK:", OUT_PATH)


if __name__ == "__main__":
    main()
