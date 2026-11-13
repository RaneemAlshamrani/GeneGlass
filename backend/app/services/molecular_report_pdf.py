"""Generate a two-page molecular report with vector chromatograms."""

from __future__ import annotations

from datetime import date
from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas

from app.models.analysis import Analysis
from app.models.molecular_report import MolecularReport
from app.models.user import User
from app.services.ab1_reader import read_chromatogram
from app.services.variant_detector import find_jak2_v617f_position

PAGE_WIDTH, PAGE_HEIGHT = letter
MARGIN = 42
TRACE_COLORS = {
    "A": colors.HexColor("#18a66a"),
    "C": colors.HexColor("#278ed5"),
    "G": colors.HexColor("#252525"),
    "T": colors.HexColor("#df4b4b"),
}
LOGO_PATH = Path(__file__).resolve().parents[3] / "assets" / "geneglass-logo.png"


def _clean(value: object | None, fallback: str = "-") -> str:
    text = str(value).strip() if value is not None else ""
    return text or fallback


def _age_on(dob: date | None, reference: date | None) -> str:
    if not dob:
        return "-"
    reference = reference or date.today()
    years = reference.year - dob.year - (
        (reference.month, reference.day) < (dob.month, dob.day)
    )
    return f"{max(0, years)} years"


def _wrapped_lines(text: str, max_chars: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = " ".join([*current, word])
        if current and len(candidate) > max_chars:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    return lines or ["-"]


def _draw_header(pdf: Canvas, title: str, page_number: int) -> None:
    if LOGO_PATH.is_file():
        logo_y = PAGE_HEIGHT - 75
        pdf.drawImage(
            ImageReader(str(LOGO_PATH)),
            MARGIN,
            logo_y,
            width=118,
            height=42,
            preserveAspectRatio=True,
            mask="auto",
        )
        # The source logo has white brand lettering designed for a dark
        # background. Replace only that small lettering area so the name
        # remains legible on the report's white page.
        pdf.setFillColor(colors.white)
        pdf.rect(MARGIN + 22, logo_y, 76, 13, stroke=0, fill=1)
        pdf.setFillColor(colors.HexColor("#0b5f67"))
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawCentredString(MARGIN + 60, logo_y + 2, "GeneGlass")
    pdf.setFillColor(colors.HexColor("#0b777b"))
    pdf.setFont("Helvetica-Bold", 22)
    pdf.drawRightString(PAGE_WIDTH - MARGIN, PAGE_HEIGHT - 48, title)
    pdf.setFillColor(colors.HexColor("#506b70"))
    pdf.setFont("Helvetica", 8)
    pdf.drawRightString(
        PAGE_WIDTH - MARGIN,
        PAGE_HEIGHT - 63,
        f"GeneGlass Molecular Laboratory Report | Page {page_number}",
    )
    pdf.setStrokeColor(colors.HexColor("#0b777b"))
    pdf.setLineWidth(1.2)
    pdf.line(MARGIN, PAGE_HEIGHT - 82, PAGE_WIDTH - MARGIN, PAGE_HEIGHT - 82)


def _draw_field(
    pdf: Canvas,
    label: str,
    value: object | None,
    x: float,
    y: float,
    width: float,
) -> None:
    pdf.setFillColor(colors.HexColor("#61777c"))
    pdf.setFont("Helvetica", 8)
    pdf.drawString(x, y, label.upper())
    pdf.setFillColor(colors.HexColor("#17393e"))
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(x, y - 14, _clean(value)[:45])
    pdf.setStrokeColor(colors.HexColor("#d7e5e6"))
    pdf.line(x, y - 20, x + width, y - 20)


def _draw_text_section(
    pdf: Canvas,
    title: str,
    text: str | None,
    y: float,
    max_lines: int = 4,
) -> float:
    pdf.setFillColor(colors.HexColor("#17393e"))
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(MARGIN, y, title)
    pdf.setFont("Helvetica", 9)
    y -= 15
    for line in _wrapped_lines(_clean(text), 100)[:max_lines]:
        pdf.drawString(MARGIN, y, line)
        y -= 12
    return y - 8


def _draw_chromatogram(
    pdf: Canvas,
    trace: dict,
    *,
    x: float,
    y: float,
    width: float,
    height: float,
    title: str,
    sample_label: str,
) -> None:
    sequence = trace["sequence"]
    positions = trace["base_positions"]
    channels = trace["channels"]
    target = find_jak2_v617f_position(sequence)
    if not target.get("found") or target.get("ab1_base_index") is None:
        raise ValueError("JAK2 V617F target is not covered by this AB1 read")

    target_index = int(target["ab1_base_index"])
    start_base = max(0, target_index - 8)
    end_base = min(len(sequence), target_index + 9)
    signal_start = positions[start_base]
    signal_end = positions[end_base - 1]
    if signal_end <= signal_start:
        raise ValueError("Chromatogram window is invalid")

    pdf.setFillColor(colors.HexColor("#17393e"))
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(x, y + height + 28, title)
    pdf.setFillColor(colors.HexColor("#61777c"))
    pdf.setFont("Helvetica", 8)
    pdf.drawString(
        x,
        y + height + 15,
        f"{sample_label} | {target['direction']} | JAK2 c.1849G>T (p.V617F)",
    )

    pdf.setFillColor(colors.HexColor("#fbfefe"))
    pdf.setStrokeColor(colors.HexColor("#d7e5e6"))
    pdf.roundRect(x, y, width, height, 8, stroke=1, fill=1)
    plot_x = x + 12
    plot_y = y + 28
    plot_width = width - 24
    plot_height = height - 42

    target_position = positions[target_index]
    left_position = positions[max(start_base, target_index - 1)]
    right_position = positions[min(end_base - 1, target_index + 1)]
    target_left = (left_position + target_position) / 2
    target_right = (target_position + right_position) / 2

    def map_x(signal_index: float) -> float:
        return plot_x + (
            (signal_index - signal_start) / (signal_end - signal_start)
        ) * plot_width

    pdf.setFillColor(colors.Color(0.0, 0.56, 0.59, alpha=0.10))
    pdf.rect(
        map_x(target_left),
        plot_y,
        max(4, map_x(target_right) - map_x(target_left)),
        plot_height,
        stroke=0,
        fill=1,
    )
    pdf.setStrokeColor(colors.HexColor("#00949a"))
    pdf.setDash(3, 2)
    pdf.line(
        map_x(target_position),
        plot_y,
        map_x(target_position),
        plot_y + plot_height,
    )
    pdf.setDash()

    maximum = max(
        max(channel[signal_start : signal_end + 1])
        for channel in channels.values()
    )
    maximum = max(maximum, 1)
    step = max(1, (signal_end - signal_start) // 850)
    for base in "ACGT":
        channel = channels[base]
        path = pdf.beginPath()
        for offset, signal_index in enumerate(
            range(signal_start, signal_end + 1, step)
        ):
            point_x = map_x(signal_index)
            point_y = plot_y + (channel[signal_index] / maximum) * plot_height
            if offset == 0:
                path.moveTo(point_x, point_y)
            else:
                path.lineTo(point_x, point_y)
        pdf.setStrokeColor(TRACE_COLORS[base])
        pdf.setLineWidth(0.9)
        pdf.drawPath(path, stroke=1, fill=0)

    for base_index in range(start_base, end_base):
        base = sequence[base_index].upper()
        pdf.setFillColor(TRACE_COLORS.get(base, colors.grey))
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawCentredString(map_x(positions[base_index]), y + 10, base)
        if base_index == target_index:
            pdf.setFillColor(colors.HexColor("#17393e"))
            pdf.setFont("Helvetica", 6)
            pdf.drawCentredString(
                map_x(positions[base_index]), y + 2, str(base_index + 1)
            )


def build_molecular_report_pdf(
    report: MolecularReport,
    analysis: Analysis,
    author: User,
) -> bytes:
    if not analysis.stored_file_path or not report.normal_control_file_path:
        raise ValueError("Patient and normal-control AB1 files are required")

    patient_trace = read_chromatogram(analysis.stored_file_path)
    control_trace = read_chromatogram(report.normal_control_file_path)
    buffer = BytesIO()
    pdf = Canvas(buffer, pagesize=letter, pageCompression=1)
    pdf.setTitle(f"Molecular Report {_clean(report.report_number)}")

    _draw_header(pdf, "Molecular Report", 1)
    field_width = 160
    columns = [MARGIN, 226, 410]
    rows = [682, 638, 594]
    fields = [
        ("Patient Name", report.patient_name),
        ("Gender", report.gender),
        ("Report Number", report.report_number),
        ("Medical Record Number", report.medical_record_number),
        ("Age", _age_on(report.date_of_birth, report.submitted_date)),
        ("Received", report.received_date),
        ("Physician", report.physician_name),
        ("Date of Birth", report.date_of_birth),
        ("Submitted", report.submitted_date),
    ]
    for index, (label, value) in enumerate(fields):
        _draw_field(
            pdf,
            label,
            value,
            columns[index % 3],
            rows[index // 3],
            field_width,
        )

    y = _draw_text_section(pdf, "Clinical History", report.clinical_history, 548, 3)
    y = _draw_text_section(pdf, "Specimen Type", report.specimen_type, y, 1)
    y = _draw_text_section(
        pdf,
        "Testing Method",
        "Genomic DNA extracted from the submitted specimen was amplified by PCR and analyzed by Sanger sequencing for JAK2 c.1849G>T (p.V617F).",
        y,
        3,
    )

    pdf.setFillColor(colors.HexColor("#eaf7f7"))
    pdf.roundRect(MARGIN, y - 54, PAGE_WIDTH - (2 * MARGIN), 54, 8, stroke=0, fill=1)
    pdf.setFillColor(colors.HexColor("#17393e"))
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(MARGIN + 14, y - 18, "SPECIALIST REVIEW DECISION")
    pdf.setFont("Helvetica-Bold", 17)
    decision = _clean(report.final_decision).upper()
    pdf.setFillColor(
        colors.HexColor("#b83c3c")
        if decision == "POSITIVE"
        else colors.HexColor("#087d72")
    )
    pdf.drawString(MARGIN + 14, y - 40, decision)
    pdf.setFillColor(colors.HexColor("#17393e"))
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(250, y - 31, "JAK2 Exon 14 c.1849G>T (p.V617F)")
    y -= 78
    y = _draw_text_section(pdf, "Interpretation", report.interpretation, y, 7)

    pdf.setStrokeColor(colors.HexColor("#d7e5e6"))
    pdf.line(MARGIN, 118, PAGE_WIDTH - MARGIN, 118)
    pdf.setFillColor(colors.HexColor("#17393e"))
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(MARGIN, 98, "Reported and finalized by")
    pdf.setFont("Helvetica", 9)
    pdf.drawString(MARGIN, 82, _clean(author.full_name))
    pdf.drawString(MARGIN, 68, _clean(author.department, "Laboratory Specialist"))
    pdf.setFont("Helvetica", 7)
    pdf.setFillColor(colors.HexColor("#61777c"))
    pdf.drawRightString(
        PAGE_WIDTH - MARGIN,
        68,
        f"Version {report.version} | Finalized {_clean(report.finalized_at)}",
    )
    pdf.showPage()

    _draw_header(pdf, "Chromatogram Evidence", 2)
    _draw_chromatogram(
        pdf,
        patient_trace,
        x=MARGIN,
        y=425,
        width=PAGE_WIDTH - (2 * MARGIN),
        height=215,
        title="Patient Sample",
        sample_label=_clean(report.report_number, "Patient sample"),
    )
    _draw_chromatogram(
        pdf,
        control_trace,
        x=MARGIN,
        y=145,
        width=PAGE_WIDTH - (2 * MARGIN),
        height=215,
        title="Normal Control",
        sample_label="Control uploaded for this report",
    )
    pdf.setFillColor(colors.HexColor("#61777c"))
    pdf.setFont("Helvetica", 7)
    pdf.drawString(
        MARGIN,
        68,
        "Chromatograms were rendered from the original AB1 fluorescence traces. The final decision above was entered by the specialist.",
    )
    pdf.save()
    return buffer.getvalue()
