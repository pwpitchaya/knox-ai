"""Fetch selected public KKU candidates; never auto-approve applicability."""
import json
from pathlib import Path
from urllib.request import Request, urlopen

SOURCES = [
    {'filename': 'travel-report-guide.pdf', 'title': 'คู่มือการเขียนรายงานการเดินทางไปราชการในราชอาณาจักร',
     'category': 'travel', 'url': 'https://qm.kku.ac.th/files/13-25601026214550-sokanni-1.pdf'},
    {'filename': 'travel-2594-2563.pdf', 'title': 'ประกาศ มข. ฉบับที่ 2594/2563 หลักเกณฑ์และอัตราการเบิกค่าใช้จ่ายในการเดินทางไปปฏิบัติงาน',
     'category': 'travel', 'url': 'https://dms.kku.ac.th/file/download/pub/51807'},
    {'filename': 'hr-2565.pdf', 'title': 'ข้อบังคับมหาวิทยาลัยขอนแก่นด้านการบริหารงานบุคคล (ต้องตรวจชื่อและขอบเขตจากต้นฉบับ)',
     'category': 'leave', 'url': 'https://www.ic.kku.ac.th/wp-content/uploads/2022/12/HR2565.pdf'},
]


def main():
    root = Path(__file__).resolve().parent / 'data' / 'candidates'
    root.mkdir(parents=True, exist_ok=True)
    results = []
    for source in SOURCES:
        result = dict(source, review_status='pending')
        try:
            with urlopen(Request(source['url'], headers={'User-Agent': 'Mozilla/5.0'}), timeout=25) as response:
                content = response.read(20 * 1024 * 1024 + 1)
            if not content.startswith(b'%PDF') or len(content) > 20 * 1024 * 1024:
                raise ValueError('Not a supported PDF response')
            (root / source['filename']).write_bytes(content)
            result.update(downloaded=True, bytes=len(content))
        except Exception as error:
            result.update(downloaded=False, error=type(error).__name__)
        results.append(result)
        print(source['filename'], result['downloaded'])
    (root / 'catalog.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
