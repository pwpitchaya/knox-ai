"""Build page-preserving OCR sidecars; does not approve documents."""
import json
from pathlib import Path
from provenance import extract_sections

ROOT = Path(__file__).resolve().parent / 'data' / 'candidates'


def main():
    names = ['hr-2565.pdf', 'leave-employees-2565.pdf', 'leave-workers-2565.pdf',
             'travel-2594-2563.pdf', 'leave-employees-2559.pdf',
             'hr-text-2565.pdf', 'salary-increase-2566.pdf', 'study-leave-2566.pdf']
    for name in names:
        path = ROOT/name
        if not path.exists():
            continue
        print('PROCESS', name, flush=True)
        sections = extract_sections(str(path), 'pdf')
        out = path.with_suffix('.sections.json')
        out.write_text(json.dumps(sections, ensure_ascii=False, indent=2), encoding='utf-8')
        print('DONE', name, 'pages', len(sections), 'chars', sum(len(s['text']) for s in sections),
              'ocr_pages', sum(s.get('method') == 'tesseract-tha-eng' for s in sections), flush=True)


if __name__ == '__main__':
    main()
