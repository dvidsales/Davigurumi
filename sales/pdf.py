from functools import partial
from html import escape
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
)


def generate_pdf(public, image_bytes=None):
    """Accepts only the public allowlist projection, never model/internal snapshot."""
    output = BytesIO()
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(
        output,
        pagesize=A4,
        title="Orçamento Davigurumi",
        author="Davigurumi",
        leftMargin=42,
        rightMargin=42,
    )
    story = [
        Paragraph("Davigurumi", styles["Title"]),
        Paragraph(
            f'Orçamento {public["number"]} · versão {public["version"]}',
            styles["Heading2"],
        ),
        Paragraph(escape(public["issuer"]), styles["Normal"]),
        Spacer(1, 20),
    ]
    data = [["Descrição", "Quantidade", "Total (R$)"]]
    for item in public["items"]:
        data.append(
            [
                Paragraph(escape(item["description"]), styles["Normal"]),
                str(item["quantity"]),
                item["total"],
            ]
        )
    table = Table(data, colWidths=[340, 65, 65], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#cce9d7")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.extend(
        [
            table,
            Spacer(1, 20),
            Paragraph("Total: R$ " + public["total"], styles["Heading2"]),
            Paragraph(
                "Entrega/retirada: "
                + escape(public.get("delivery_date") or "A combinar"),
                styles["Normal"],
            ),
            Paragraph("Validade: " + escape(public["expires_at"]), styles["Normal"]),
            Spacer(1, 15),
            Paragraph(escape(public["terms"]).replace("\n", "<br/>"), styles["Normal"]),
        ]
    )
    for entry in public.get("images", []):
        raw = (image_bytes or {}).get(entry["id"])
        if raw is None:
            continue
        image = Image(BytesIO(raw))
        ratio = min(400 / image.imageWidth, 300 / image.imageHeight)
        image.drawWidth = image.imageWidth * ratio
        image.drawHeight = image.imageHeight * ratio
        story.extend(
            [Spacer(1, 15), image, Paragraph(escape(entry["label"]), styles["Normal"])]
        )
    doc.build(story, canvasmaker=partial(Canvas, invariant=1))
    return output.getvalue()
