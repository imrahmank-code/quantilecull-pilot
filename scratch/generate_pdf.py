import os
import re
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

docs_dir = r"E:\Antigravity Projects\Photo Cleaner App\docs"
md_path = os.path.join(docs_dir, "Pilot_User_Guide.md")
pdf_path = os.path.join(docs_dir, "Pilot_User_Guide.pdf")

# Read Markdown file
with open(md_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

# Set up styles
styles = getSampleStyleSheet()

# Create custom styles
title_style = ParagraphStyle(
    'DocTitle',
    parent=styles['Normal'],
    fontName='Helvetica-Bold',
    fontSize=20,
    leading=24,
    textColor=colors.HexColor('#0F172A'), # Slate 900
    spaceAfter=15
)

h1_style = ParagraphStyle(
    'DocH1',
    parent=styles['Normal'],
    fontName='Helvetica-Bold',
    fontSize=14,
    leading=18,
    textColor=colors.HexColor('#5B4BFF'), # Electric Blue
    spaceBefore=12,
    spaceAfter=6,
    keepWithNext=True
)

h2_style = ParagraphStyle(
    'DocH2',
    parent=styles['Normal'],
    fontName='Helvetica-Bold',
    fontSize=11,
    leading=14,
    textColor=colors.HexColor('#1E293B'), # Slate 800
    spaceBefore=8,
    spaceAfter=4,
    keepWithNext=True
)

body_style = ParagraphStyle(
    'DocBody',
    parent=styles['Normal'],
    fontName='Helvetica',
    fontSize=9.5,
    leading=13,
    textColor=colors.HexColor('#334155'), # Slate 700
    spaceAfter=6
)

bullet_style = ParagraphStyle(
    'DocBullet',
    parent=styles['Normal'],
    fontName='Helvetica',
    fontSize=9.5,
    leading=13,
    textColor=colors.HexColor('#334155'),
    leftIndent=15,
    firstLineIndent=-10,
    spaceAfter=4
)

code_style = ParagraphStyle(
    'DocCode',
    parent=styles['Normal'],
    fontName='Courier',
    fontSize=8.5,
    leading=11,
    textColor=colors.HexColor('#0F172A'),
    backColor=colors.HexColor('#F1F5F9'),
    borderColor=colors.HexColor('#E2E8F0'),
    borderWidth=0.5,
    borderPadding=6,
    spaceAfter=6
)

# Parse MD to Platypus flowables
story = []
in_list = False

# Add a spacer at the top
story.append(Spacer(1, 0.2 * inch))

for line in lines:
    line_str = line.strip()
    if not line_str:
        continue
    
    # Header 1: # Title
    if line_str.startswith("# "):
        # Document Title
        title_text = line_str[2:].replace("**", "").replace("`", "")
        story.append(Paragraph(title_text, title_style))
        story.append(Spacer(1, 0.1 * inch))
        
    # Header 2: ## Section
    elif line_str.startswith("## "):
        h1_text = line_str[3:].replace("**", "").replace("`", "")
        story.append(Paragraph(h1_text, h1_style))
        
    # Header 3: ### Subsection
    elif line_str.startswith("### "):
        h2_text = line_str[4:].replace("**", "").replace("`", "")
        story.append(Paragraph(h2_text, h2_style))
        
    # Bullets: - Item or * Item
    elif line_str.startswith("- ") or line_str.startswith("* "):
        # Replace bold markdown and inline code ticks
        bullet_text = line_str[2:]
        # Simple markdown conversions
        bullet_text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', bullet_text)
        bullet_text = re.sub(r'`(.*?)`', r'<font face="Courier">\1</font>', bullet_text)
        story.append(Paragraph(f"&bull; {bullet_text}", bullet_style))
        
    # Horizontal rule
    elif line_str.startswith("---"):
        # Add a subtle visual line
        story.append(Spacer(1, 0.05 * inch))
        # Draw a table as line
        line_table = Table([[""]], colWidths=[6.5 * inch], rowHeights=[1])
        line_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#E2E8F0')),
            ('PADDING', (0,0), (-1,-1), 0),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
            ('TOPPADDING', (0,0), (-1,-1), 0)
        ]))
        story.append(line_table)
        story.append(Spacer(1, 0.05 * inch))
        
    # Normal Paragraph
    else:
        text = line_str
        text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
        text = re.sub(r'`(.*?)`', r'<font face="Courier">\1</font>', text)
        story.append(Paragraph(text, body_style))

# Setup document
doc = SimpleDocTemplate(
    pdf_path,
    pagesize=letter,
    leftMargin=1 * inch,
    rightMargin=1 * inch,
    topMargin=1 * inch,
    bottomMargin=1 * inch
)

# Build PDF
doc.build(story)
print(f"Generated PDF successfully at {pdf_path}")
