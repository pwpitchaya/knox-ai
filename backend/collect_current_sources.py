"""Bounded official-source collection; never auto-approves any document."""
import concurrent.futures
import hashlib,json
from pathlib import Path
from pypdf import PdfReader
from audit_lock import assert_collection_open
from build_document_library import fetch,read_page

ROOT=Path(__file__).resolve().parent/'data'/'new_sources'
PROJECT_ROOT=Path(__file__).resolve().parent.parent
FILES=[
 ('leave-employees-2569.pdf','https://hr2.kku.ac.th/wp-content/uploads/1-2569-การปฏิบัติงาน-และการลา-พนักงานมหาวิทยาลัย.pdf','leave'),
 ('leave-workers-2569.pdf','https://hr2.kku.ac.th/wp-content/uploads/2-2569-การปฏิบัติงาน-และการลา-ลูกจ้างชั่วคราว.pdf','leave'),
 ('leave-authority-2569.pdf','https://hr2.kku.ac.th/wp-content/uploads/มอบอำนาจ-4163-69-1.pdf','leave'),
 ('salary-table-2569.pdf','https://hr2.kku.ac.th/wp-content/uploads/5-2569-การกำหนดบัญชีเงินเดือนฯ.pdf','compensation'),
 ('salary-increase-2569.pdf','https://hr2.kku.ac.th/wp-content/uploads/6-2569-หลักเกณฑ์การเลื่อนเงินเดือน.pdf','compensation'),
 ('hr-amendment-2568.pdf','https://hr2.kku.ac.th/wp-content/uploads/0-ข้อบังคับการบริหารงานบุคคล2568-ฉบับที่-2.pdf','foundation'),
 ('hr-amendment-2569.pdf','https://hr2.kku.ac.th/wp-content/uploads/1-ข้อบังคับการบริหารงานบุคคล2569-ฉบับที่-3.pdf','foundation'),
 ('welfare-1605-2564.pdf','https://mba.kku.ac.th/th/news/att/20211103112416-a5.pdf','compensation'),
 ('welfare-medical-form.pdf','https://hr.kku.ac.th/wphrdkku/wp-content/uploads/2021/09/4-แบบขอรับเงินด้านการตรวจสุขภาพฯหรือค่ารักษาพยาบาล.pdf','compensation'),
 ('welfare-child-form.pdf','https://hr.kku.ac.th/wphrdkku/wp-content/uploads/2021/09/5-แบบขอรับเงินสนับสนุนการศึกษาบุตรและแนวปฏิบัติ.pdf','compensation'),
]

def download(row):
 name,url,topic=row;record=dict(filename=name,url=url,category=topic,reviewed=False)
 try:
  target=ROOT/name
  if not target.exists():
   data,final,ctype=fetch(url)
   if not data.startswith(b'%PDF'):raise ValueError('Not a PDF')
   target.write_bytes(data)
  data=target.read_bytes();reader=PdfReader(target)
  record.update(downloaded=True,pages=len(reader.pages),sha256=hashlib.sha256(data).hexdigest(),local_source=target.relative_to(PROJECT_ROOT).as_posix(),bytes=len(data))
 except Exception as e:record.update(downloaded=False,error=type(e).__name__)
 print(name,record.get('pages',record.get('error')),flush=True)
 return record

def main():
 assert_collection_open();ROOT.mkdir(exist_ok=True)
 for old,new in [('new-0.pdf','leave-employees-2569.pdf'),('new-1.pdf','leave-workers-2569.pdf')]:
  if (ROOT/old).exists() and not (ROOT/new).exists():(ROOT/old).rename(ROOT/new)
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:records=list(pool.map(download,FILES))
 (ROOT/'manifest.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
 for url in ['https://hr2.kku.ac.th/?page_id=5351','https://hr2.kku.ac.th/?page_id=13038','https://finweb.kku.ac.th/thlaw3/','https://finweb.kku.ac.th/kku_an_625_64/']:
  source,links=read_page(url)
  (ROOT/(hashlib.sha256(url.encode()).hexdigest()[:12]+'.links.json')).write_text(json.dumps(dict(source=source,links=links),ensure_ascii=False,indent=2),encoding='utf-8')
  print('index',url,source.get('error','ok'),flush=True)

if __name__=='__main__':main()
