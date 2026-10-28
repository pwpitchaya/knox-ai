"""Discover PDF links from inspected official HR indexes; preserve catalog."""
import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, quote, unquote
from urllib.request import Request, urlopen

BASE = 'https://hr.kku.ac.th/wphrdkku/'
ROOT = Path(__file__).resolve().parent / 'data' / 'candidates'


class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.href = None; self.text = []; self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.href = dict(attrs).get('href'); self.text = []

    def handle_data(self, text):
        if self.href:
            self.text.append(text)

    def handle_endtag(self, tag):
        if tag == 'a' and self.href:
            self.links.append((''.join(self.text).strip(), urljoin(BASE, self.href)))
            self.href = None


def fetch(url):
    url = quote(unquote(url), safe=':/?=&%')
    with urlopen(Request(url, headers={'User-Agent':'Mozilla/5.0'}), timeout=40) as r:
        return r.read(25 * 1024 * 1024)


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    selections = [
        ('?page=11&page_id=1514', '6/2565', 'leave-employees-2565.pdf', 'leave', 'พนักงานมหาวิทยาลัย', '2022-10-27'),
        ('?page=11&page_id=1514', '7/2565', 'leave-workers-2565.pdf', 'leave', 'ลูกจ้างของมหาวิทยาลัย', '2022-10-27'),
        ('?page=4&page_id=1514', '(ฉบับที่ 2/2559)', 'leave-employees-2559.pdf', 'leave', 'พนักงานมหาวิทยาลัย', ''),
        ('?page=12&page_id=1514', '8/2566', 'salary-increase-2566.pdf', 'compensation', 'พนักงานมหาวิทยาลัย', ''),
        ('?page=12&page_id=1514', '10/2566', 'study-leave-2566.pdf', 'leave', 'พนักงานมหาวิทยาลัย', ''),
        ('?p=11766', 'ข้อบังคับมหาวิทยาลัยขอนแก่น ว่าด้วยการบริหารงานบุคคล พ.ศ. 2565', 'hr-text-2565.pdf', 'leave', 'ทุกประเภท', '2022-05-07'),
    ]
    cache = {}; catalog = []
    for page, label, filename, category, personnel, effective in selections:
        if page not in cache:
            parser = Links(); parser.feed(fetch(BASE+page).decode('utf-8', errors='replace')); cache[page] = parser.links
        matches = [(t,u) for t,u in cache[page] if t.strip() == label and '.pdf' in u.lower()]
        item = dict(filename=filename, category=category, personnel=personnel,
                    effective_from=effective, index_url=BASE+page, review_status='pending')
        try:
            if not matches:
                # Some links use a longer title; only accept the unique match.
                matches = [(t,u) for t,u in cache[page] if label in t and '.pdf' in u.lower()]
            urls = list(dict.fromkeys(u for _,u in matches))
            if len(urls) != 1:
                raise ValueError('Ambiguous/missing official link')
            item['url'] = urls[0]
            item['title'] = label
            content = fetch(urls[0])
            if not content.startswith(b'%PDF'):
                raise ValueError('Not a PDF')
            (ROOT/filename).write_bytes(content)
            item.update(downloaded=True, bytes=len(content))
        except Exception as error:
            item.update(downloaded=False, error=type(error).__name__)
        catalog.append(item)
        print(filename, item['downloaded'], flush=True)
        (ROOT/'hr-catalog.json').write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
