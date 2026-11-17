"""Regenerate the sample documents for the fictional store "Saffron & Thread".

The generated files are already committed in sample_docs/, so you only need
this if you want to change the policies. Requires: reportlab, python-docx.

    python scripts/make_sample_docs.py
"""
from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.shared import Pt
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

OUT = Path(__file__).resolve().parent.parent / "sample_docs"
NOTE = "Saffron & Thread is a fictional business created for this demo. Any resemblance to a real company is coincidental."

# DejaVu Sans renders the rupee sign; fall back to Helvetica + "Rs." elsewhere.
FONT, BOLD, RUPEE = "Helvetica", "Helvetica-Bold", "Rs. "
for regular, bold in [("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")]:
    if Path(regular).exists() and Path(bold).exists():
        pdfmetrics.registerFont(TTFont("DejaVu", regular))
        pdfmetrics.registerFont(TTFont("DejaVu-Bold", bold))
        FONT, BOLD, RUPEE = "DejaVu", "DejaVu-Bold", "₹"

R = RUPEE

RETURNS = [
    [
        ("title", "Saffron & Thread — Returns & Refunds Policy"),
        ("small", f"{NOTE} Last updated: 1 October 2026. Policy code RF-07."),
        ("h", "Return window"),
        ("p", "Full-price items can be returned within 30 days of delivery for a full refund."),
        ("p", "Items marked “Final Sale” can only be exchanged for a different size or colour within 7 days of delivery. Final Sale items are not eligible for a refund."),
        ("h", "Condition of returned items"),
        ("p", "Items must be unused, unwashed and returned with their original tags and packaging. Bedsheets must be returned together with their matching pillow covers."),
        ("h", "Items that cannot be returned"),
        ("p", "Made-to-order and personalised items, including monogrammed linen and custom-size curtains, cannot be returned unless they arrive damaged or defective. Gift cards are non-refundable."),
    ],
    [
        ("h", "How to start a return"),
        ("p", "Email returns@saffronandthread.example with your order number (it starts with ST-, for example ST-48213) and two photos of the item. We reply within 1 business day with a return label or a pickup date."),
        ("h", "Return shipping costs"),
        ("p", f"For returns within India we arrange a doorstep pickup. A pickup fee of {R}149 is deducted from your refund. The pickup fee is waived if the item arrived damaged or defective."),
        ("p", "International customers ship returns back at their own cost. We recommend a tracked service."),
        ("h", "Refund timelines"),
        ("p", "Once your return reaches our Jaipur warehouse, we inspect it and process the refund within 5–7 business days to the original payment method. Your bank may take a few more days to show the amount."),
        ("p", "Cash on Delivery (COD) orders are refunded by UPI or bank transfer, because there is no card to refund to."),
        ("h", "Store credit"),
        ("p", "Prefer store credit instead of a refund? Choose it when you start the return and we add a 10% bonus to the credit value. Store credit never expires."),
    ],
]

SHIPPING = [
    [
        ("title", "Saffron & Thread — Shipping & Delivery"),
        ("small", f"{NOTE} Last updated: 1 October 2026."),
        ("h", "Shipping within India"),
        ("p", f"Shipping is free on orders of {R}1,999 or more. Orders below {R}1,999 have a flat shipping charge of {R}99."),
        ("p", "Orders are dispatched within 2 business days."),
        ("p", "Standard delivery takes 3–6 business days to metro cities and 5–9 business days to non-metro towns and rural areas."),
        ("h", "Express delivery"),
        ("p", f"Express delivery costs {R}249 and arrives in 1–3 business days. It is available in 12 metro cities: Delhi, Mumbai, Bengaluru, Chennai, Kolkata, Hyderabad, Pune, Ahmedabad, Jaipur, Chandigarh, Lucknow and Kochi."),
        ("h", "Cash on Delivery"),
        ("p", f"Cash on Delivery (COD) is available for orders up to {R}10,000. A COD handling fee of {R}49 applies."),
    ],
    [
        ("h", "International shipping"),
        ("p", "We ship to 28 countries through DHL Express, including the USA, the UK, Canada, Australia, the UAE, Singapore and most of the European Union."),
        ("p", f"International shipping starts at {R}1,850 for parcels up to 1 kg; the exact rate is shown at checkout. Delivery takes 7–12 business days."),
        ("p", "Customs duties and import taxes are not included in our prices and are paid by the customer when the parcel arrives."),
        ("h", "Tracking"),
        ("p", "You receive a tracking link by SMS and email within 24 hours of dispatch. We cannot deliver to PO boxes."),
        ("h", "Lost or damaged parcels"),
        ("p", "If your parcel has not arrived 5 business days after the latest estimated delivery date, write to us. Claims for lost parcels must be raised within 15 days of the estimated delivery date."),
    ],
]

CARE = [
    [
        ("title", "Saffron & Thread — Product Care Guide"),
        ("small", NOTE),
        ("h", "Handloom cotton"),
        ("p", "Wash new handloom cotton separately in cold water for the first two washes; natural dyes may release a little colour."),
        ("p", "Use a mild liquid detergent. Never use bleach."),
        ("p", "Dry in the shade, because strong sunlight fades vegetable dyes. Iron on medium heat on the reverse side."),
        ("p", "Handloom cotton may shrink by up to 3% after the first wash. This is normal and has been allowed for in our sizes."),
    ],
    [
        ("h", "Block-printed and Dabu fabrics"),
        ("p", "Hand wash is recommended for the first three washes."),
        ("h", "Silk"),
        ("p", "Silk cushion covers are dry clean only."),
        ("h", "Jute rugs"),
        ("p", "Do not machine wash or soak jute rugs. Spot clean with a damp cloth and mild soap, and rotate the rug every 3 months for even wear."),
        ("h", "Storage"),
        ("p", "Store linen folded with neem leaves or cedar blocks to keep insects away."),
        ("h", "Warranty"),
        ("p", "Curtains and cushion covers carry a 6-month warranty against manufacturing defects such as broken zips, loose seams and faulty eyelets. The warranty does not cover fading, normal wear, or damage from washing against these instructions."),
        ("p", "To claim, email support@saffronandthread.example with your order number and photos."),
    ],
]

FAQ = [
    ("title", "Saffron & Thread — Frequently Asked Questions"),
    ("p", NOTE),
    ("h", "Orders & payment"),
    ("p", f"We accept UPI, credit and debit cards, net banking and Cash on Delivery. No-cost EMI is available on credit cards for orders above {R}5,000."),
    ("p", "You can change or cancel an order within 12 hours of placing it, as long as it has not been dispatched."),
    ("h", "Gift wrapping"),
    ("p", f"Gift wrapping costs {R}99 per item and includes a handwritten note at no extra charge."),
    ("h", "Bulk and corporate orders"),
    ("p", "For corporate gifting and bulk orders of 25 units or more we offer a 12% discount. Write to wholesale@saffronandthread.example with the quantity and the delivery date you need."),
    ("h", "Custom sizes"),
    ("p", "Curtains can be made to custom sizes. Custom orders take an extra 10–12 business days before dispatch and cannot be returned unless defective."),
    ("h", "Visit our studio"),
    ("p", "Our experience studio is at C-Scheme, Jaipur. It is open Monday to Saturday, 11 am to 8 pm, and closed on Sundays and national holidays."),
    ("h", "Thread Circle loyalty programme"),
    ("p", f"You earn 1 point for every {R}100 spent. 100 points can be redeemed for {R}100 off your next order. Points expire 12 months after they are earned."),
    ("h", "Product codes"),
    ("table", [
        ("Code", "Product", "Size / notes"),
        ("SNT-BD-114", "Indigo Dabu king bedsheet", "108 x 108 inches, with 2 pillow covers"),
        ("SNT-CC-031", "Raw silk cushion cover", "16 x 16 inches, dry clean only"),
        ("SNT-CR-220", "Block-print cotton curtains (pair)", "7 ft x 4.5 ft each, eyelet top"),
        ("SNT-RG-502", "Hand-braided jute rug", "4 x 6 ft"),
        ("SNT-TL-019", "Kantha table runner", "14 x 72 inches"),
    ]),
]


def write_pdf(name: str, pages: list[list[tuple[str, str]]]) -> None:
    base = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle("t", parent=base["Title"], fontName=BOLD, fontSize=18, spaceAfter=6),
        "small": ParagraphStyle("s", parent=base["Normal"], fontName=FONT, fontSize=8.5, textColor="#666666", spaceAfter=10),
        "h": ParagraphStyle("h", parent=base["Heading2"], fontName=BOLD, fontSize=12.5, spaceBefore=10, spaceAfter=4),
        "p": ParagraphStyle("p", parent=base["Normal"], fontName=FONT, fontSize=10.5, leading=15, spaceAfter=6),
    }
    story = []
    for i, page in enumerate(pages):
        if i:
            story.append(PageBreak())
        for kind, text in page:
            story.append(Paragraph(text.replace("&", "&amp;"), styles[kind]))
        story.append(Spacer(1, 4 * mm))
    SimpleDocTemplate(str(OUT / name), pagesize=A4, title=name, author="Saffron & Thread (fictional)",
                      leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm, bottomMargin=18 * mm).build(story)


def write_docx(name: str, blocks: list) -> None:
    doc = Document()
    doc.styles["Normal"].font.size = Pt(11)
    for kind, content in blocks:
        if kind == "title":
            doc.add_heading(content, level=0)
        elif kind == "h":
            doc.add_heading(content, level=1)
        elif kind == "p":
            doc.add_paragraph(content)
        elif kind == "table":
            table = doc.add_table(rows=0, cols=len(content[0]))
            table.style = "Table Grid"
            for row in content:
                cells = table.add_row().cells
                for cell, value in zip(cells, row):
                    cell.text = value
    doc.save(OUT / name)


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    write_pdf("returns_and_refunds_policy.pdf", RETURNS)
    write_pdf("shipping_and_delivery.pdf", SHIPPING)
    write_pdf("product_care_guide.pdf", CARE)
    write_docx("faq.docx", FAQ)
    print("wrote", sorted(p.name for p in OUT.iterdir()))
