import requests
import re
from fpdf import FPDF

# 1) Download the text
URL = "https://baseball.pointstreak.com/textstats/reports/seasons/34102/league_summary_full_report.txt"
r = requests.get(URL)
r.raise_for_status()
full_text = r.text

# 2) Define the exact headings you want as page-break boundaries
HEADINGS = [
    "COMPOSITE STANDINGS",
    "TEAM TOTALS BATTING STAT(S)?",   # regex-ish
    "TEAM TOTALS PITCHING STAT(S)?",
    "TEAM TOTALS FIELDING STAT(S)?",
    "LEAGUE TOTALS BATTING STAT(S)?",
    "LEAGUE TOTALS PITCHING STAT(S)?",
    "RELIEF PITCHER POINT STANDINGS",
    # add any other ones you need…
]

# Build a single regex that matches any of them at the start of a line
heading_re = re.compile(
    r"^(?P<hdr>" + "|".join(HEADINGS) + r")\s*$",
    re.IGNORECASE | re.MULTILINE
)

# 3) Slice the full text into { heading → lines[] }
sections = {}
matches = list(heading_re.finditer(full_text))
for i, m in enumerate(matches):
    hdr = m.group("hdr").upper().strip()
    start = m.end() + 1
    end   = matches[i+1].start() if i+1 < len(matches) else len(full_text)
    block = full_text[start:end].strip().splitlines()
    sections[hdr] = block

print("Will render these sections (in order):")
for hdr in sections:
    print(" •", hdr)


# 4) Build the PDF
pdf = FPDF(format="letter")
pdf.set_auto_page_break(True, margin=36)

for hdr, lines in sections.items():
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 20, hdr, ln=True, align="L")
    pdf.ln(4)

    pdf.set_font("Courier", size=9)  # monospaced for columns
    for line in lines:
        # you can wrap/truncate here if you want
        pdf.cell(0, 12, txt=line, ln=True)

# 5) Save
out = "ALPB_2025_report_by_section.pdf"
pdf.output(out)
print("Written:", out)
