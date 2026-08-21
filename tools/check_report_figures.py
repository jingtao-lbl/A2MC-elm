#!/usr/bin/env python3
"""Report figure-caption linter. Catches the duplicated-caption footgun: a markdown image whose
ALT TEXT carries a "Figure N" label while an explicit bold `**Figure N ...**` caption paragraph is
also present. Pandoc's implicit_figures turns the alt text into a <figcaption>, so the label then
renders twice ("Figure 1: Figure 1"). The fix is an EMPTY alt text `![](fig.png)` when you write a
separate bold caption (the write-report convention).

Flags any image embed `![<alt>](...)` whose <alt> begins with "Figure" (case-insensitive). Empty alt
text (`![](...)`) and non-label alt text pass.

Usage:
    python3 tools/check_report_figures.py <report.md | reports_dir | use_cases/<site>/reports>
Exit 0 = clean; exit 1 = one or more labelled-alt images found. Dependency-free (stdlib only).
"""
import re
import sys
from pathlib import Path

# ![alt](path)  -- capture the alt text; ignore reference-style / html
IMG_RE = re.compile(r'^!\[([^\]]*)\]\([^)]+\)', re.M)
LABEL_RE = re.compile(r'^\s*figure\b', re.I)


def check_file(path):
    text = path.read_text(encoding="utf-8", errors="replace")
    hits = []
    for m in IMG_RE.finditer(text):
        alt = m.group(1).strip()
        if alt and LABEL_RE.match(alt):
            line = text.count("\n", 0, m.start()) + 1
            hits.append((line, m.group(0)[:60]))
    return hits


def gather(target):
    p = Path(target)
    if p.is_file():
        return [p] if p.suffix == ".md" else []
    if p.is_dir():
        return sorted(p.rglob("*.md"))
    return []


def main(argv):
    if not argv:
        print("usage: check_report_figures.py <report.md | reports_dir>")
        return 2
    files = gather(argv[0])
    total = 0
    for f in files:
        hits = check_file(f)
        for line, snippet in hits:
            total += 1
            print(f"  [dup-caption] {f}:{line}: image alt text is a 'Figure' label -> "
                  f"empty it (`![](...)`) so the bold caption doesn't render twice: {snippet}")
    if total:
        print(f"\n✘ {total} labelled-alt image(s) -> pandoc implicit_figures will duplicate the "
              f"caption. Use empty alt text + a separate bold **Figure N.** caption (write-report).")
        return 1
    print(f"✔ report figures: {len(files)} file(s) checked, no duplicated-caption alt text.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
