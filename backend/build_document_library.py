"""Collect public institutional evidence only. No LLM/API calls or auto-approval."""
import concurrent.futures
import hashlib
import html
import json
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag, quote, unquote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent / 'DOCUMENT_LIBRARY'
TOPICS = {
    'foundation': ['การบริหารงานบุคคล','มอบอำนาจให้ปฏิบัติ','การงบประมาณ การเงิน'],
    'leave': ['ลาป่วย','ลากิจ','ลาคลอด','ลาพักผ่อน','การลา','ใบลา','ลาไป','ลาศึกษา','ลาติดตาม','ยกเลิกวันลา','วันเวลาปฏิบัติงาน','วัน เวลาปฏิบัติงาน','วัน เวลาการปฏิบัติงาน'],
    'travel': ['เดินทาง','ค่าพาหนะ','เบี้ยเลี้ยง','ค่าที่พัก','ค่าเช่าที่พัก','รถยนต์','ยืมเงิน','เงินยืม','ทดรอง','ใบเบิก','ใบสำคัญรับเงิน','รับรองแทนใบเสร็จ','หลักฐานการจ่าย','ส่งใช้เงิน'],
    'compensation': ['เงินเดือน','ค่าจ้าง','ค่าตอบแทน','สวัสดิการ','สิทธิประโยชน์','รักษาพยาบาล','ศึกษาบุตร','สำรองเลี้ยงชีพ','โบนัส','เงินรางวัล','ประกันสังคม','ค่าชดเชย','เงินประจำตำแหน่ง'],
}
SEEDS = [
    'https://hr2.kku.ac.th/', 'https://finance.kku.ac.th/',
    'https://is.kku.ac.th/nkc2021/site/view?id=25',
    'https://is.kku.ac.th/nkc2021/site/view?id=1688',
    'https://is.kku.ac.th/nkc2021/personal',
    'https://is.kku.ac.th/nkc2021/plan/documents/index?parent=195',
    'https://hr.kku.ac.th/wphrdkku/?page_id=6697',
    'https://hr.kku.ac.th/wphrdkku/?page_id=2465',
    'https://hr.kku.ac.th/wphrdkku/?p=12238',
] + [f'https://hr.kku.ac.th/wphrdkku/?page={n}&page_id=1514' for n in range(3,14)]


def official(url):
    host = urlparse(url).hostname or ''
    return host == 'kku.ac.th' or host.endswith('.kku.ac.th')


def topics(text):
    text = unquote(text).replace('\u200b','')
    return [name for name, words in TOPICS.items() if any(word in text for word in words)]


def attachment(url):
    return bool(re.search(r'\.(pdf|docx?|xlsx?|zip)(?:$|[?#])',url,re.I)
                or re.search(r'/(?:document/download|file/download|downloadfile)',url,re.I)
                or 'ViewDocFile' in url)


class Parser(HTMLParser):
    def __init__(self, base):
        super().__init__();self.base=base;self.links=[];self.current=None;self.row=None
    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs)
        if tag=='tr':self.row={'text':[],'links':[]}
        if tag=='a' and attrs.get('href'):
            self.current={'url':urldefrag(urljoin(self.base,attrs['href']))[0],'parts':[],'context':''}
    def handle_data(self,data):
        if self.current is not None:self.current['parts'].append(data)
        if self.row is not None:self.row['text'].append(data)
    def handle_endtag(self,tag):
        if tag=='a' and self.current is not None:
            self.current['label']=' '.join(''.join(self.current.pop('parts')).split())
            self.links.append(self.current)
            if self.row is not None:self.row['links'].append(self.current)
            self.current=None
        if tag=='tr' and self.row is not None:
            context=' '.join(' '.join(self.row['text']).split())
            for link in self.row['links']:link['context']=context
            self.row=None


def fetch(url, limit=25*1024*1024):
    url=quote(url,safe=':/?=&%+#')
    with urlopen(Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=20) as response:
        final=response.geturl()
        if not official(final):raise ValueError('Redirected outside official KKU hosts')
        content=response.read(limit+1)
        if len(content)>limit:raise ValueError('File exceeds collection size limit')
        return content,final,response.headers.get('Content-Type','')


def read_page(url):
    record={'url':url,'retrieved_at':datetime.now(timezone.utc).isoformat()}
    try:
        content,final,ctype=fetch(url,5*1024*1024)
        if b'%PDF'==content[:4]:return dict(record,error='PDF instead of index'),[]
        name=hashlib.sha256(url.encode()).hexdigest()[:16]+'.html'
        (ROOT/'pages'/name).write_bytes(content)
        parser=Parser(final);parser.feed(content.decode('utf-8',errors='replace'))
        record.update(final_url=final,archive='pages/'+name,sha256=hashlib.sha256(content).hexdigest(),links=len(parser.links))
        return record,parser.links
    except Exception as error:
        name=hashlib.sha256(url.encode()).hexdigest()[:16]+'.html'
        cached=ROOT/'pages'/name
        if cached.exists():
            content=cached.read_bytes();parser=Parser(url);parser.feed(content.decode('utf-8',errors='replace'))
            return dict(record,archive='pages/'+name,sha256=hashlib.sha256(content).hexdigest(),
                        links=len(parser.links),latest_fetch_error=type(error).__name__,used_prior_snapshot=True),parser.links
        return dict(record,error=type(error).__name__),[]


def main():
    from audit_lock import assert_collection_open
    assert_collection_open()
    (ROOT/'files').mkdir(parents=True,exist_ok=True);(ROOT/'pages').mkdir(exist_ok=True)
    sources=[];found={};external=[];seen=set();queue=list(SEEDS)
    # One bounded discovery pass beyond seed indexes. Never enter sign-in systems.
    for depth in range(2):
        pending=[url for url in dict.fromkeys(queue) if url not in seen][:60]
        queue=[]
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            results=list(pool.map(read_page,pending))
        for source,links in results:
            seen.add(source['url']);sources.append(source)
            for link in links:
                url=link['url'];text=link['label']+' '+link['context']+' '+unquote(url)
                kinds=topics(text)
                if attachment(url) and (kinds or ('is.kku.ac.th' in source['url'] and '1688' in source['url'])):
                    if not official(url):
                        external.append(dict(link,index_url=source['url']));continue
                    item=found.setdefault(url,{'url':url,'labels':[],'contexts':[],'index_urls':[],'topics':[]})
                    for key,value in [('labels',link['label']),('contexts',link['context']),('index_urls',source['url'])]:
                        if value and value not in item[key]:item[key].append(value)
                    item['topics']=sorted(set(item['topics']+kinds))
                elif depth==0 and official(url) and not attachment(url):
                    if any(term in text for term in ['สวัสดิการ','ระเบียบ','ประกาศ ก.บ.ม.','บริหารงานบุคคล','แบบฟอร์ม','ลาศึกษา','คู่มือบุคลากร','เดินทาง','การเงิน','การคลัง','เงินเดือน','ค่าตอบแทน','การลา']):
                        if not any(term in url for term in ['/feed','wp-login','logout','?s=','/tag/']):queue.append(url)
        print('Indexes checked',len(sources),'attachment links',len(found),flush=True)
        (ROOT/'source_pages.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2),encoding='utf-8')
    items=list(found.values())
    # Prioritize current HR, faculty workflow, and specific documents over bundles.
    def priority(item):
        u=item['url'];return (0 if 'is.kku.ac.th' in u else 1 if 'hr2.kku.ac.th' in u else 2,
                            1 if 'รวม' in ' '.join(item['labels']) else 0,u)
    items.sort(key=priority)
    for index,item in enumerate(items,1):item['id']=f'KKU-{index:03}'
    def download(item):
        item=dict(item);item['retrieved_at']=datetime.now(timezone.utc).isoformat()
        item['review_status']='source_download_only_not_verified_current'
        text=' '.join(item['labels']+item['contexts'])
        item['document_type']='form' if any(w in text for w in ['แบบฟอร์ม','แบบใบ','สัญญายืม','ใบสำคัญ','ใบเบิก']) else 'regulation_or_guidance'
        item['institution_scope']='IS_NongKhai' if any('is.kku.ac.th' in u for u in item['index_urls']) else 'KKU_scope_requires_content_check'
        try:
            data,final,ctype=fetch(item['url'])
            if data.startswith(b'%PDF'):extension='pdf'
            elif data.startswith(b'PK'):extension='docx' if '.docx' in item['url'].lower() else 'zip'
            elif data.startswith(bytes.fromhex('d0cf11e0a1b11ae1')):extension='doc'
            else:raise ValueError('Not a document response (may be login/HTML)')
            digest=hashlib.sha256(data).hexdigest()
            filename=f"files/{item['id']}-{digest[:10]}.{extension}"
            (ROOT/filename).write_bytes(data)
            item.update(downloaded=True,local_file=filename,sha256=digest,bytes=len(data),final_url=final,format=extension)
            if extension=='pdf':
                from pypdf import PdfReader
                reader=PdfReader(ROOT/filename)
                item['pages']=len(reader.pages)
                texts=[p.extract_text() or '' for p in reader.pages]
                item['extractable_characters']=sum(len(t) for t in texts)
                item['pages_needing_text_review']=[i for i,t in enumerate(texts,1) if len(t.strip())<20 or '\ufffd' in t or any('\ue000'<=c<='\uf8ff' for c in t)]
                (ROOT/(filename+'.pages.json')).write_text(json.dumps([{'page_number':i,'text':t} for i,t in enumerate(texts,1)],ensure_ascii=False),encoding='utf-8')
        except Exception as error:item.update(downloaded=False,error=type(error).__name__)
        print(item['id'],item['downloaded'],flush=True)
        return item
    # Preserve all discovery links; download up to 100 relevant documents per run.
    records=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        for item in pool.map(download,items[:100]):
            records.append(item)
            (ROOT/'catalog.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    for item in items[100:]:records.append(dict(item,downloaded=False,error='Not downloaded in bounded first pass'))
    fingerprints={}
    for item in records:
        digest=item.get('sha256')
        if digest:
            if digest in fingerprints:item['duplicate_of']=fingerprints[digest]
            else:fingerprints[digest]=item['id']
    (ROOT/'catalog.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'external_references_not_collected.json').write_text(json.dumps(external,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Downloaded',sum(r.get('downloaded',False) for r in records),'unique file contents',len(fingerprints),'all links',len(items),flush=True)


if __name__=='__main__':main()
