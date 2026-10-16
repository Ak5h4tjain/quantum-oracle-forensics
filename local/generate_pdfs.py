"""Convert Markdown reports to publication-grade PDFs using Headless Chrome/Edge.
Generates:
1. docs/report/technical-report.pdf (max 3 pages)
2. docs/report/ai-use-disclosure.pdf (exactly 1 page)
"""

import os
import re
import subprocess
from pathlib import Path


def md_to_simple_html(md_text: str, title: str, is_single_page: bool = False) -> str:
    """Lightweight regex-based Markdown to styled HTML converter."""
    html = md_text

    # Escape HTML special chars (except already intentional tags)
    html = html.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # Headers
    html = re.sub(r"^# (.*?)$", r"<h1>\1</h1>", html, flags=re.MULTILINE)
    html = re.sub(r"^## (.*?)$", r"<h2>\1</h2>", html, flags=re.MULTILINE)
    html = re.sub(r"^### (.*?)$", r"<h3>\1</h3>", html, flags=re.MULTILINE)
    html = re.sub(r"^#### (.*?)$", r"<h4>\1</h4>", html, flags=re.MULTILINE)

    # Horizontal rules
    html = re.sub(r"^---$", r"<hr>", html, flags=re.MULTILINE)

    # Bold and italics
    html = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", html)
    html = re.sub(r"\*(.*?)\*", r"<em>\1</em>", html)

    # Inline code
    html = re.sub(r"`(.*?)`", r"<code>\1</code>", html)

    # Code blocks
    html = re.sub(r"```[a-z]*\n(.*?)```", r"<pre><code>\1</code></pre>", html, flags=re.DOTALL)

    # Tables
    lines = html.split("\n")
    in_table = False
    table_lines = []
    new_lines = []

    for line in lines:
        if "|" in line and line.strip().startswith("|") and line.strip().endswith("|"):
            if not in_table:
                in_table = True
                table_lines = []
            table_lines.append(line)
        else:
            if in_table:
                in_table = False
                # Convert table_lines to HTML table
                if len(table_lines) >= 2:
                    t_html = ["<table>"]
                    # Header
                    headers = [c.strip() for c in table_lines[0].split("|")[1:-1]]
                    t_html.append("<thead><tr>" + "".join(f"<th>{h}</th>" for h in headers) + "</tr></thead>")
                    t_html.append("<tbody>")
                    # Skip delimiter row table_lines[1]
                    for r in table_lines[2:]:
                        cells = [c.strip() for c in r.split("|")[1:-1]]
                        t_html.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
                    t_html.append("</tbody></table>")
                    new_lines.append("\n".join(t_html))
            new_lines.append(line)

    if in_table and table_lines:
        t_html = ["<table>"]
        headers = [c.strip() for c in table_lines[0].split("|")[1:-1]]
        t_html.append("<thead><tr>" + "".join(f"<th>{h}</th>" for h in headers) + "</tr></thead>")
        t_html.append("<tbody>")
        for r in table_lines[2:]:
            cells = [c.strip() for c in r.split("|")[1:-1]]
            t_html.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
        t_html.append("</tbody></table>")
        new_lines.append("\n".join(t_html))

    html = "\n".join(new_lines)

    # Unordered lists
    html = re.sub(r"^\* (.*?)$", r"<li>\1</li>", html, flags=re.MULTILINE)
    html = re.sub(r"^- (.*?)$", r"<li>\1</li>", html, flags=re.MULTILINE)
    html = re.sub(r"((?:<li>.*?</li>\n?)+)", r"<ul>\1</ul>", html)

    # Paragraphs
    paragraphs = html.split("\n\n")
    processed_p = []
    for p in paragraphs:
        p_strip = p.strip()
        if not p_strip:
            continue
        if any(p_strip.startswith(tag) for tag in ["<h1", "<h2", "<h3", "<h4", "<table", "<ul", "<pre", "<hr", "<li"]):
            processed_p.append(p)
        else:
            processed_p.append(f"<p>{p_strip}</p>")
    html = "\n\n".join(processed_p)

    font_size = "9.5pt" if not is_single_page else "8.8pt"
    line_height = "1.32" if not is_single_page else "1.25"
    h1_size = "16pt" if not is_single_page else "14pt"
    h2_size = "12pt" if not is_single_page else "11pt"
    margin = "12mm 14mm" if not is_single_page else "10mm 12mm"

    full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{title}</title>
<style>
    @page {{
        size: A4;
        margin: {margin};
    }}
    body {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        font-size: {font_size};
        line-height: {line_height};
        color: #1a1a1a;
        background: #ffffff;
        margin: 0;
        padding: 0;
    }}
    h1 {{
        font-size: {h1_size};
        color: #0b2545;
        border-bottom: 2px solid #134074;
        padding-bottom: 4px;
        margin-top: 0;
        margin-bottom: 8px;
    }}
    h2 {{
        font-size: {h2_size};
        color: #134074;
        border-bottom: 1px solid #8da9c4;
        padding-bottom: 2px;
        margin-top: 10px;
        margin-bottom: 6px;
    }}
    h3 {{
        font-size: 10pt;
        color: #0b2545;
        margin-top: 8px;
        margin-bottom: 4px;
    }}
    p {{
        margin-top: 3px;
        margin-bottom: 6px;
        text-align: justify;
    }}
    hr {{
        border: 0;
        border-top: 1px solid #ccc;
        margin: 8px 0;
    }}
    table {{
        width: 100%;
        border-collapse: collapse;
        margin: 6px 0;
        font-size: 8.5pt;
    }}
    th, td {{
        border: 1px solid #c9d6df;
        padding: 4px 6px;
        text-align: left;
    }}
    th {{
        background-color: #eef4f8;
        color: #0b2545;
        font-weight: 600;
    }}
    tr:nth-child(even) {{
        background-color: #fbfcfd;
    }}
    code {{
        font-family: "Consolas", "Courier New", monospace;
        font-size: 8.5pt;
        background-color: #f0f4f8;
        padding: 1px 3px;
        border-radius: 3px;
        color: #8b0000;
    }}
    pre {{
        background-color: #f6f8fa;
        padding: 6px;
        border-radius: 4px;
        border: 1px solid #d0d7de;
        overflow-x: auto;
        font-size: 8pt;
        margin: 6px 0;
    }}
    ul {{
        margin-top: 3px;
        margin-bottom: 6px;
        padding-left: 18px;
    }}
    li {{
        margin-bottom: 2px;
    }}
</style>
</head>
<body>
{html}
</body>
</html>
"""
    return full_html


def convert_file(md_path: Path, pdf_path: Path, title: str, is_single_page: bool = False):
    print(f"Converting {md_path.name} to {pdf_path.name}...")
    with open(md_path, "r", encoding="utf-8") as f:
        md_content = f.read()

    html_content = md_to_simple_html(md_content, title=title, is_single_page=is_single_page)
    temp_html = md_path.with_suffix(".html")
    with open(temp_html, "w", encoding="utf-8") as f:
        f.write(html_content)

    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]

    browser_bin = None
    for p in chrome_paths:
        if os.path.exists(p):
            browser_bin = p
            break

    if not browser_bin:
        print("Error: Chrome or Edge binary not found!")
        return

    abs_html_uri = temp_html.resolve().as_uri()
    cmd = [
        browser_bin,
        "--headless",
        "--disable-gpu",
        "--no-pdf-header-footer",
        f"--print-to-pdf={pdf_path.resolve()}",
        abs_html_uri,
    ]

    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0 and pdf_path.is_file():
        size_kb = pdf_path.stat().st_size / 1024.0
        print(f"SUCCESS: Generated {pdf_path} ({size_kb:.1f} KB)")
    else:
        print(f"FAILED: {res.stderr}")


def main():
    report_md = Path("docs/report/technical-report.md")
    report_pdf = Path("docs/report/technical-report.pdf")
    convert_file(report_md, report_pdf, title="Quantum Oracle Forensics — Technical Report", is_single_page=False)

    disclosure_md = Path("docs/report/ai-use-disclosure.md")
    disclosure_pdf = Path("docs/report/ai-use-disclosure.pdf")
    convert_file(disclosure_md, disclosure_pdf, title="AI-Use Disclosure — Quantum Oracle Forensics", is_single_page=True)


if __name__ == "__main__":
    main()
