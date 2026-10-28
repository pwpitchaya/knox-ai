"""Build an offline, searchable evidence catalog. Never calls an AI service."""
import hashlib
import html
import json
import shutil
from pathlib import Path
from urllib.parse import unquote

import build_document_library as lib

ROOT = lib.ROOT
HR = 'https://hr2.kku.ac.th/'
LATEST = [
 ('1-2569-การปฏิบัติงาน-และการลา-พนักงานมหาวิทยาลัย.pdf','ประกาศ ก.บ.ม. 1/2569 การปฏิบัติงานและการลา พนักงานมหาวิทยาลัย','leave'),
 ('2-2569-การปฏิบัติงาน-และการลา-ลูกจ้างชั่วคราว.pdf','ประกาศ ก.บ.ม. 2/2569 การปฏิบัติงานและการลา ลูกจ้างชั่วคราว','leave'),
 ('มอบอำนาจ-4163-69-1.pdf','คำสั่ง มข. 4163/2569 การมอบอำนาจเกี่ยวกับการลา','leave'),
 ('6-2569-หลักเกณฑ์การเลื่อนเงินเดือน.pdf','ประกาศ ก.บ.ม. 6/2569 หลักเกณฑ์การเลื่อนเงินเดือน','compensation'),
 ('5-2569-การกำหนดบัญชีเงินเดือนฯ.pdf','ประกาศ ก.บ.ม. 5/2569 การกำหนดบัญชีเงินเดือนและค่าตอบแทน','compensation'),
 ('7-2569-หลักเกณฑ์และวิธีการปรับระดับตำแหน่ง.pdf','ประกาศ ก.บ.ม. 7/2569 หลักเกณฑ์และวิธีการปรับระดับตำแหน่ง','compensation'),
 ('1-ข้อบังคับการบริหารงานบุคคล2569-ฉบับที่-3.pdf','ข้อบังคับการบริหารงานบุคคล (ฉบับที่ 3) พ.ศ.2569','foundation'),
 ('0-ข้อบังคับการบริหารงานบุคคล2568-ฉบับที่-2.pdf','ข้อบังคับการบริหารงานบุคคล (ฉบับที่ 2) พ.ศ.2568','foundation'),
]
NAMES = {'leave':'การลา','travel':'เดินทางและเบิกจ่าย','compensation':'เงินเดือนและสวัสดิการ','foundation':'ข้อบังคับพื้นฐาน'}

def key(url):
 return unquote(url).replace('\u200b','')

def main():
 from audit_lock import assert_collection_open
 assert_collection_open()
 sources=json.loads((ROOT/'source_pages.json').read_text(encoding='utf-8'))
 found={}
 for source in sources:
  path=ROOT/'pages'/(hashlib.sha256(source['url'].encode()).hexdigest()[:16]+'.html')
  if not path.exists():continue
  source.update(archive='pages/'+path.name,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
  if source.pop('error',None):source['latest_fetch_failed']=True
  parser=lib.Parser(source.get('final_url',source['url']))
  parser.feed(path.read_text(encoding='utf-8',errors='replace'))
  source['links']=len(parser.links)
  for link in parser.links:
   kinds=lib.topics(link['label']+' '+link['context']+' '+unquote(link['url']))
   if not (lib.official(link['url']) and lib.attachment(link['url']) and kinds):continue
   item=found.setdefault(key(link['url']),dict(url=link['url'],labels=[],contexts=[],index_urls=[],topics=[],downloaded=False))
   for field,value in [('labels',link['label']),('contexts',link['context']),('index_urls',source['url'])]:
    if value and value not in item[field]:item[field].append(value)
   item['topics']=sorted(set(item['topics']+kinds))
 for filename,title,topic in LATEST:
  url=HR+'wp-content/uploads/'+filename
  item=found.setdefault(key(url),dict(url=url,labels=[],contexts=[],index_urls=[],topics=[],downloaded=False))
  item.update(priority='ตรวจฉบับล่าสุดก่อน',discovery_method='official_index_read_in_browser_tool_2026-10-27')
  item['labels']=[title];item['topics']=sorted(set(item['topics']+[topic]))
  if HR+'?page_id=5351' not in item['index_urls']:item['index_urls'].append(HR+'?page_id=5351')
  item['contexts'].append('พบจากสารบัญทางการ; ยังไม่ตรวจวันมีผลและเนื้อหา PDF')
 # Keep procurement inventory outside the personnel knowledge scope.
 excluded=[]
 for k,item in list(found.items()):
  text=' '.join(item['labels'])
  if any(w in text for w in ['ใบเบิกวัสดุ','บัญชีวัสดุ','คุมวัสดุ']):excluded.append(found.pop(k))
 old=json.loads((ROOT/'catalog.json').read_text(encoding='utf-8'))
 for item in old:
  if key(item['url']) in found and not item.get('downloaded'):
   found[key(item['url'])]['download_error']=item.get('error','not_downloaded')
 candidates=Path(__file__).resolve().parent/'data'/'candidates'
 physical=json.loads((candidates/'catalog.json').read_text(encoding='utf-8'))+json.loads((candidates/'hr-catalog.json').read_text(encoding='utf-8'))
 additions=ROOT/'additional_sources.json'
 if additions.exists():physical+=json.loads(additions.read_text(encoding='utf-8'))
 titles={
  'leave-employees-2565.pdf':'ประกาศ ก.บ.ม. 6/2565 การลาของพนักงานมหาวิทยาลัย (ยกเลิกแล้ว)',
  'leave-workers-2565.pdf':'ประกาศ ก.บ.ม. 7/2565 การลาของลูกจ้างมหาวิทยาลัย (ยกเลิกแล้ว)',
  'leave-employees-2559.pdf':'ประกาศ ก.บ.ม. 2/2559 การลาของพนักงานมหาวิทยาลัย (ยกเลิกแล้ว)',
  'salary-increase-2566.pdf':'ประกาศ ก.บ.ม. 8/2566 การเลื่อนเงินเดือน (ต้องเทียบ 6/2569)',
  'study-leave-2566.pdf':'ประกาศ ก.บ.ม. 10/2566 การไปศึกษา ฝึกอบรม วิจัย และดูงาน',
  'hr-text-2565.pdf':'ข้อบังคับการบริหารงานบุคคล พ.ศ.2565 (ต้องอ่านร่วมฉบับแก้ไข 2568 และ 2569)',
 }
 for entry in physical:
  if entry['filename']=='hr-2565.pdf' or not entry.get('downloaded'):continue
  file=(ROOT.parent/entry['local_source']) if entry.get('local_source') else candidates/entry['filename']
  if not file.exists():continue
  item=found.setdefault(key(entry['url']),dict(url=entry['url'],labels=[],contexts=[],index_urls=[],topics=[entry['category']],downloaded=False))
  item['labels']=[titles.get(entry['filename'],entry.get('title',entry['filename']))]
  target=ROOT/'files'/file.name
  if file.resolve()!=target.resolve():shutil.copy2(file,target)
  item.update(downloaded=True,local_file='files/'+file.name,sha256=hashlib.sha256(file.read_bytes()).hexdigest(),bytes=file.stat().st_size)
  from pypdf import PdfReader
  item['pages']=len(PdfReader(file).pages)
  item['historical']=entry['filename'] in {'leave-employees-2559.pdf','leave-employees-2565.pdf','leave-workers-2565.pdf'}
  sidecar=file.with_suffix('.sections.json')
  if sidecar.exists():
   dest=ROOT/'files'/(file.stem+'.text-review.json');shutil.copy2(sidecar,dest)
   item['text_file']='files/'+dest.name
 # Normalize alternate links to the same old regulation without inflating document counts.
 aliases={}
 for item in found.values():
  u=unquote(item['url'])
  if '6-2565-ปฏิบัติงาน-การลา-พนักงาน' in u:aliases.setdefault('leave-employees-2565.pdf',[]).append(item)
  if '7-2565-ปฏิบัติงาน-การลาฯ-ลูกจ้าง' in u or '7-65-หลักเกณฑ์-ปฏิบัติงาน-การลาฯ-ลูกจ้าง' in u:aliases.setdefault('leave-workers-2565.pdf',[]).append(item)
 for filename,items in aliases.items():
  primary=next((i for i in items if i.get('downloaded')),None)
  if primary:
   primary['alternate_urls']=[i['url'] for i in items if i is not primary]
   for item in items:
    if item is not primary:found.pop(key(item['url']),None)
 records=sorted(found.values(),key=lambda x:(0 if x.get('priority') else 1 if x.get('downloaded') else 2,x['url']))
 for i,item in enumerate(records,1):
  item['id']=f'KKU-{i:03}'
  item['title']=next((s for s in item['labels'] if len(s)>8),' '.join(item['contexts'])[:180] or unquote(item['url'].split('/')[-1]))
  item['scope']='คณะสหวิทยาการ / หนองคาย' if 'is.kku.ac.th' in item['url'] else 'ส่วนกลาง มข. / ต้องตรวจผู้มีสิทธิในเนื้อหา'
  item['status']='ประวัติ — ห้ามใช้สรุปสิทธิปัจจุบัน' if item.get('historical') else 'มีไฟล์ — รอตรวจเนื้อหาและฉบับแก้ไข' if item['downloaded'] else 'พบลิงก์ทางการ — ยังไม่มีไฟล์ในเครื่อง'
  item['effective_from_verified']=False;item['approved_for_current_answers']=False
  if not item['downloaded']:item.setdefault('download_error','ยังดาวน์โหลดไม่ได้หรือยังไม่ได้ลองรายลิงก์')
 stats=dict(catalog_entries=len(records),downloaded_files=sum(i['downloaded'] for i in records),historical_files=sum(i.get('historical',False) for i in records),archived_index_pages=sum('archive' in s for s in sources),current_entitlements_verified=False,ai_enabled=False)
 for name,value in [('catalog.json',records),('source_pages.json',sources),('excluded_out_of_scope.json',excluded),('summary.json',stats)]:
  (ROOT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
 lines=['# คลังเอกสารบุคลากร มหาวิทยาลัยขอนแก่น','', 'ตรวจค้น 27 ตุลาคม 2569 • ยังไม่ใช้ AI สร้างคำตอบ', '',f"ทะเบียน {len(records)} รายการอ้างอิง (ยังไม่ใช่จำนวนฉบับกฎหมายที่ตรวจแล้ว) • มีไฟล์ต้นฉบับ {stats['downloaded_files']} ฉบับ • ในนี้เป็นประวัติที่ยกเลิกแล้ว {stats['historical_files']} ฉบับ",'', 'เอกสารฉบับใหม่หลายรายการดาวน์โหลดหมดเวลา จึงยังไม่สรุปจำนวนวันลา วงเงินเบิก หรือสิทธิรายบุคคล วันที่ในชื่อไฟล์ไม่ใช่หลักฐานวันเริ่มใช้ อ่านสถานะก่อนใช้ทุกครั้ง','', '## รายการเอกสาร','']
 for item in records:
  lines += [f"### {item['id']} · {item['title']}",f"- หมวด: {', '.join(NAMES.get(k,k) for k in item['topics'])} · ขอบเขต: {item['scope']}",f"- สถานะ: **{item['status']}**",f"- [ต้นฉบับทางการ]({item['url']})"]
  if item.get('local_file'):lines += [f"- [ไฟล์ในเครื่อง]({item['local_file']}) · {item['pages']} หน้า · SHA-256 `{item['sha256']}`"]
  for index in item['index_urls']:lines += [f'- [สารบัญหน่วยงานเจ้าของเรื่อง]({index})']
  lines += ['']
 (ROOT/'CATALOG.md').write_text('\n'.join(lines),encoding='utf-8')
 print(json.dumps(stats,ensure_ascii=False))

if __name__=='__main__':main()
