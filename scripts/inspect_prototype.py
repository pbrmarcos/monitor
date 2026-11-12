"""Read-only PDF reference inspection; writes temporary page previews."""
from pathlib import Path
import pymupdf

root = Path(__file__).resolve().parents[1]
out = root / 'tmp' / 'prototype'
out.mkdir(parents=True, exist_ok=True)
doc = pymupdf.open(root / 'Monitor — Protótipo.pdf')
print(f'Prototype: {len(doc)} pages')
for index, page in enumerate(doc):
    print(index + 1, page.get_text()[:350].replace('\n', ' '))
    page.get_pixmap(matrix=pymupdf.Matrix(0.8, 0.8)).save(out / f'page-{index+1}.png')
