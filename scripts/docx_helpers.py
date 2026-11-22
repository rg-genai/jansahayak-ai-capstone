"""Shared styling & XML layout helpers for building publication-grade JanSahayak AI Word (.docx) documents."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.shared import Inches, Pt, RGBColor

# Civic GovTech Palette
HEX_NAVY = "0F2942"
HEX_BLUE = "1E4E79"
HEX_ACCENT = "2563EB"
HEX_SAFFRON = "D95D14"
HEX_GREEN = "138808"
HEX_PURPLE = "6D28D9"
HEX_SLATE = "334155"
HEX_MUTED = "64748B"
HEX_ROW_ALT = "F4F7FA"
HEX_LIGHT_BLUE = "EFF6FF"
HEX_LIGHT_SAFFRON = "FFF4EB"
HEX_LIGHT_GREEN = "ECFDF5"
HEX_LIGHT_AMBER = "FEF3C7"
HEX_CODE_BG = "F1F5F9"
HEX_BORDER = "CBD5E1"

RGB_NAVY = RGBColor(0x0F, 0x29, 0x42)
RGB_BLUE = RGBColor(0x1E, 0x4E, 0x79)
RGB_SAFFRON = RGBColor(0xD9, 0x5D, 0x14)
RGB_GREEN = RGBColor(0x13, 0x88, 0x08)
RGB_SLATE = RGBColor(0x33, 0x41, 0x55)
RGB_MUTED = RGBColor(0x64, 0x74, 0x8B)
RGB_WHITE = RGBColor(0xFF, 0xFF, 0xFF)


def _set_cell_shading(cell, fill_hex: str) -> None:
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    tcPr.append(shd)


def _set_cell_margins(cell, top=90, bottom=90, left=130, right=130) -> None:
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement("w:tcMar")
    for m, val in (("top", top), ("bottom", bottom), ("left", left), ("right", right)):
        node = OxmlElement(f"w:{m}")
        node.set(qn("w:w"), str(val))
        node.set(qn("w:type"), "dxa")
        tcMar.append(node)
    tcPr.append(tcMar)


def _set_table_borders(table, border_hex: str = HEX_BORDER) -> None:
    tblPr = table._tbl.tblPr
    borders = parse_xml(
        f'<w:tblBorders {nsdecls("w")}>'
        f'<w:top w:val="single" w:sz="6" w:space="0" w:color="{border_hex}"/>'
        f'<w:bottom w:val="single" w:sz="8" w:space="0" w:color="{HEX_NAVY}"/>'
        f'<w:insideH w:val="single" w:sz="4" w:space="0" w:color="{border_hex}"/>'
        f'<w:left w:val="none"/><w:right w:val="none"/><w:insideV w:val="single" w:sz="4" w:space="0" w:color="{border_hex}"/>'
        f"</w:tblBorders>"
    )
    tblPr.append(borders)


def _add_page_number_field(paragraph) -> None:
    run = paragraph.add_run("Page ")
    run.font.size = Pt(8.5)
    run.font.color.rgb = RGB_MUTED

    fld1 = OxmlElement("w:fldSimple")
    fld1.set(qn("w:instr"), "PAGE")
    paragraph._p.append(fld1)

    run2 = paragraph.add_run(" of ")
    run2.font.size = Pt(8.5)
    run2.font.color.rgb = RGB_MUTED

    fld2 = OxmlElement("w:fldSimple")
    fld2.set(qn("w:instr"), "NUMPAGES")
    paragraph._p.append(fld2)


def create_styled_document(
    header_title: str,
    footer_left: str = "JanSahayak AI | IIT Kharagpur GenAI & Agentic AI Track B Capstone",
    margin_in: float = 0.75,
) -> Document:
    doc = Document()

    for sec in doc.sections:
        sec.top_margin = Inches(margin_in)
        sec.bottom_margin = Inches(margin_in)
        sec.left_margin = Inches(margin_in)
        sec.right_margin = Inches(margin_in)
        sec.different_first_page_header_footer = True

        # Running header (pages 2+)
        hp = sec.header.paragraphs[0]
        hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        hrun = hp.add_run(header_title)
        hrun.font.name = "Calibri"
        hrun.font.size = Pt(8.5)
        hrun.font.color.rgb = RGB_MUTED
        # Subtle bottom border on header
        pPr = hp._p.get_or_add_pPr()
        pPr.append(
            parse_xml(
                f'<w:pBdr {nsdecls("w")}><w:bottom w:val="single" w:sz="4" w:space="4" w:color="{HEX_BORDER}"/></w:pBdr>'
            )
        )

        # Running footer (pages 2+)
        fp = sec.footer.paragraphs[0]
        fp.alignment = WD_ALIGN_PARAGRAPH.LEFT
        frun = fp.add_run(footer_left + "    |    ")
        frun.font.name = "Calibri"
        frun.font.size = Pt(8.5)
        frun.font.color.rgb = RGB_MUTED
        _add_page_number_field(fp)

    # Base Normal style
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(10.5)
    normal.font.color.rgb = RGB_SLATE
    normal.paragraph_format.space_after = Pt(5)
    normal.paragraph_format.line_spacing = 1.15

    return doc


def add_rich_runs(paragraph, text: str, base_size: float = 10.2, base_color: RGBColor = RGB_SLATE) -> None:
    """Parse **bold** and `code` inline tokens cleanly into Word runs."""
    tokens = re.split(r"(\*\*[^*]+\*\*|`[^`]+`)", text)
    for tok in tokens:
        if not tok:
            continue
        if tok.startswith("**") and tok.endswith("**"):
            r = paragraph.add_run(tok[2:-2])
            r.bold = True
            r.font.name = "Calibri"
            r.font.size = Pt(base_size)
            r.font.color.rgb = RGB_NAVY
        elif tok.startswith("`") and tok.endswith("`"):
            r = paragraph.add_run(tok[1:-1])
            r.font.name = "Consolas"
            r.font.size = Pt(max(8.5, base_size - 0.8))
            r.font.color.rgb = RGB_BLUE
        else:
            r = paragraph.add_run(tok)
            r.font.name = "Calibri"
            r.font.size = Pt(base_size)
            r.font.color.rgb = base_color


def add_cover_page(
    doc: Document,
    badge_text: str,
    title: str,
    subtitle: str,
    metadata_rows: list[tuple[str, str]],
    highlights: list[str],
) -> None:
    # Top tricolor-inspired accent bar (Saffron / Navy / Green table)
    bar = doc.add_table(rows=1, cols=3)
    bar.alignment = WD_TABLE_ALIGNMENT.CENTER
    bar.autofit = False
    for idx, color_hex in enumerate((HEX_SAFFRON, HEX_NAVY, HEX_GREEN)):
        cell = bar.cell(0, idx)
        cell.width = Inches(2.33)
        _set_cell_shading(cell, color_hex)
        _set_cell_margins(cell, top=40, bottom=40, left=0, right=0)
        cell.paragraphs[0].paragraph_format.space_after = Pt(0)

    sp = doc.add_paragraph()
    sp.paragraph_format.space_before = Pt(28)

    # Category pill
    p_badge = doc.add_paragraph()
    rb = p_badge.add_run(f"  {badge_text.upper()}  ")
    rb.bold = True
    rb.font.name = "Calibri"
    rb.font.size = Pt(10)
    rb.font.color.rgb = RGB_SAFFRON

    # Main Title
    p_title = doc.add_paragraph()
    p_title.paragraph_format.space_before = Pt(6)
    p_title.paragraph_format.space_after = Pt(8)
    rt = p_title.add_run(title)
    rt.bold = True
    rt.font.name = "Calibri"
    rt.font.size = Pt(26)
    rt.font.color.rgb = RGB_NAVY

    # Subtitle
    p_sub = doc.add_paragraph()
    p_sub.paragraph_format.space_after = Pt(18)
    rs = p_sub.add_run(subtitle)
    rs.font.name = "Calibri"
    rs.font.size = Pt(13)
    rs.font.color.rgb = RGB_BLUE

    # Key Highlights Box
    add_callout(
        doc,
        "At a Glance — Why This Document Matters",
        "\n".join(f"• {h}" for h in highlights),
        accent_hex=HEX_NAVY,
        fill_hex=HEX_LIGHT_BLUE,
    )

    sp2 = doc.add_paragraph()
    sp2.paragraph_format.space_before = Pt(14)

    # Metadata Card Table
    tbl = doc.add_table(rows=len(metadata_rows), cols=2)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = False
    _set_table_borders(tbl, HEX_BORDER)
    for i, (k, v) in enumerate(metadata_rows):
        c0, c1 = tbl.cell(i, 0), tbl.cell(i, 1)
        c0.width = Inches(2.2)
        c1.width = Inches(4.8)
        _set_cell_shading(c0, HEX_ROW_ALT)
        _set_cell_shading(c1, "FFFFFF")
        _set_cell_margins(c0, top=85, bottom=85, left=120, right=120)
        _set_cell_margins(c1, top=85, bottom=85, left=120, right=120)
        p0 = c0.paragraphs[0]
        p0.paragraph_format.space_after = Pt(0)
        r0 = p0.add_run(k)
        r0.bold = True
        r0.font.size = Pt(9.8)
        r0.font.color.rgb = RGB_NAVY
        p1 = c1.paragraphs[0]
        p1.paragraph_format.space_after = Pt(0)
        add_rich_runs(p1, v, base_size=9.8)

    doc.add_page_break()


def add_h1(doc: Document, text: str, page_break_before: bool = False) -> None:
    if page_break_before:
        doc.add_page_break()
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.keep_with_next = True
    r = p.add_run(text)
    r.bold = True
    r.font.name = "Calibri"
    r.font.size = Pt(16)
    r.font.color.rgb = RGB_NAVY
    # Accent underline
    pPr = p._p.get_or_add_pPr()
    pPr.append(
        parse_xml(
            f'<w:pBdr {nsdecls("w")}><w:bottom w:val="single" w:sz="12" w:space="3" w:color="{HEX_SAFFRON}"/></w:pBdr>'
        )
    )


def add_h2(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(11)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.keep_with_next = True
    r = p.add_run(text)
    r.bold = True
    r.font.name = "Calibri"
    r.font.size = Pt(12.5)
    r.font.color.rgb = RGB_BLUE


def add_h3(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.keep_with_next = True
    r = p.add_run(text)
    r.bold = True
    r.font.name = "Calibri"
    r.font.size = Pt(10.8)
    r.font.color.rgb = RGB_SAFFRON


def add_para(doc: Document, text: str, space_after: float = 5.0, size: float = 10.2) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing = 1.15
    add_rich_runs(p, text, base_size=size)


def add_bullets(doc: Document, items: Iterable[str], size: float = 10.0) -> None:
    for item in items:
        p = doc.add_paragraph(style="List Bullet")
        p.paragraph_format.space_before = Pt(1)
        p.paragraph_format.space_after = Pt(3)
        p.paragraph_format.line_spacing = 1.13
        add_rich_runs(p, item, base_size=size)


def add_numbered(doc: Document, items: Iterable[str], size: float = 10.0) -> None:
    for idx, item in enumerate(items, start=1):
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Inches(0.24)
        p.paragraph_format.first_line_indent = Inches(-0.18)
        p.paragraph_format.space_before = Pt(1.5)
        p.paragraph_format.space_after = Pt(3.5)
        p.paragraph_format.line_spacing = 1.13
        rn = p.add_run(f"{idx}. ")
        rn.bold = True
        rn.font.size = Pt(size)
        rn.font.color.rgb = RGB_SAFFRON
        add_rich_runs(p, item, base_size=size)


def add_callout(
    doc: Document,
    title: str,
    body: str,
    accent_hex: str = HEX_BLUE,
    fill_hex: str = HEX_LIGHT_BLUE,
) -> None:
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = False
    cell = tbl.cell(0, 0)
    cell.width = Inches(7.0)
    _set_cell_shading(cell, fill_hex)
    _set_cell_margins(cell, top=110, bottom=110, left=160, right=140)
    tcPr = cell._tc.get_or_add_tcPr()
    tcPr.append(
        parse_xml(
            f'<w:tcBorders {nsdecls("w")}>'
            f'<w:left w:val="single" w:sz="24" w:space="0" w:color="{accent_hex}"/>'
            f'<w:top w:val="single" w:sz="4" w:space="0" w:color="{HEX_BORDER}"/>'
            f'<w:right w:val="single" w:sz="4" w:space="0" w:color="{HEX_BORDER}"/>'
            f'<w:bottom w:val="single" w:sz="4" w:space="0" w:color="{HEX_BORDER}"/>'
            f"</w:tcBorders>"
        )
    )
    p = cell.paragraphs[0]
    p.paragraph_format.space_after = Pt(3)
    rt = p.add_run(title)
    rt.bold = True
    rt.font.name = "Calibri"
    rt.font.size = Pt(10.3)
    rt.font.color.rgb = RGB_NAVY

    for line in body.split("\n"):
        lp = cell.add_paragraph()
        lp.paragraph_format.space_before = Pt(1)
        lp.paragraph_format.space_after = Pt(2)
        lp.paragraph_format.line_spacing = 1.12
        add_rich_runs(lp, line, base_size=9.6)

    sp = doc.add_paragraph()
    sp.paragraph_format.space_before = Pt(0)
    sp.paragraph_format.space_after = Pt(4)


def add_code_block(doc: Document, title: str, code_text: str) -> None:
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = False
    cell = tbl.cell(0, 0)
    cell.width = Inches(7.0)
    _set_cell_shading(cell, HEX_CODE_BG)
    _set_cell_margins(cell, top=90, bottom=90, left=140, right=140)
    tcPr = cell._tc.get_or_add_tcPr()
    tcPr.append(
        parse_xml(
            f'<w:tcBorders {nsdecls("w")}>'
            f'<w:left w:val="single" w:sz="16" w:space="0" w:color="{HEX_NAVY}"/>'
            f'<w:top w:val="single" w:sz="4" w:space="0" w:color="{HEX_BORDER}"/>'
            f'<w:right w:val="single" w:sz="4" w:space="0" w:color="{HEX_BORDER}"/>'
            f'<w:bottom w:val="single" w:sz="4" w:space="0" w:color="{HEX_BORDER}"/>'
            f"</w:tcBorders>"
        )
    )
    p0 = cell.paragraphs[0]
    p0.paragraph_format.space_after = Pt(4)
    rt = p0.add_run(title)
    rt.bold = True
    rt.font.name = "Calibri"
    rt.font.size = Pt(9.2)
    rt.font.color.rgb = RGB_BLUE

    p1 = cell.add_paragraph()
    p1.paragraph_format.space_before = Pt(0)
    p1.paragraph_format.space_after = Pt(0)
    p1.paragraph_format.line_spacing = 1.08
    rc = p1.add_run(code_text.strip())
    rc.font.name = "Consolas"
    rc.font.size = Pt(8.3)
    rc.font.color.rgb = RGB_NAVY

    sp = doc.add_paragraph()
    sp.paragraph_format.space_before = Pt(0)
    sp.paragraph_format.space_after = Pt(4)


def add_styled_table(
    doc: Document,
    headers: list[str],
    rows: list[list[str]],
    col_widths_in: list[float] | None = None,
    font_size: float = 9.0,
) -> None:
    tbl = doc.add_table(rows=len(rows) + 1, cols=len(headers))
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = False
    _set_table_borders(tbl)

    total_w = 7.0
    if not col_widths_in:
        col_widths_in = [total_w / len(headers)] * len(headers)

    # Header row (repeat on page splits)
    hdr_row = tbl.rows[0]
    trPr = hdr_row._tr.get_or_add_trPr()
    trPr.append(parse_xml(f'<w:tblHeader {nsdecls("w")}/>'))
    trPr.append(parse_xml(f'<w:cantSplit {nsdecls("w")}/>'))

    for j, htxt in enumerate(headers):
        cell = hdr_row.cells[j]
        cell.width = Inches(col_widths_in[j])
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        _set_cell_shading(cell, HEX_NAVY)
        _set_cell_margins(cell, top=85, bottom=85, left=100, right=100)
        p = cell.paragraphs[0]
        p.paragraph_format.space_after = Pt(0)
        r = p.add_run(htxt)
        r.bold = True
        r.font.name = "Calibri"
        r.font.size = Pt(font_size)
        r.font.color.rgb = RGB_WHITE

    for i, rdata in enumerate(rows):
        row = tbl.rows[i + 1]
        r_trPr = row._tr.get_or_add_trPr()
        r_trPr.append(parse_xml(f'<w:cantSplit {nsdecls("w")}/>'))
        bg = HEX_ROW_ALT if i % 2 == 1 else "FFFFFF"
        for j, val in enumerate(rdata):
            cell = row.cells[j]
            cell.width = Inches(col_widths_in[j])
            cell.vertical_alignment = WD_ALIGN_VERTICAL.TOP
            _set_cell_shading(cell, bg)
            _set_cell_margins(cell, top=70, bottom=70, left=100, right=100)
            p = cell.paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.10
            add_rich_runs(p, str(val), base_size=font_size)

    sp = doc.add_paragraph()
    sp.paragraph_format.space_before = Pt(0)
    sp.paragraph_format.space_after = Pt(4)


def add_figure(doc: Document, img_path: Path, caption: str, width_in: float = 6.9) -> None:
    if not img_path.exists():
        add_para(doc, f"[Missing diagram: {img_path.name}]")
        return
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.keep_with_next = True
    run = p.add_run()
    run.add_picture(str(img_path), width=Inches(width_in))

    cp = doc.add_paragraph()
    cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cp.paragraph_format.space_after = Pt(8)
    rc = cp.add_run(caption)
    rc.italic = True
    rc.font.name = "Calibri"
    rc.font.size = Pt(8.8)
    rc.font.color.rgb = RGB_MUTED
