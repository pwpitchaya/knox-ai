"""Publish actual evidence and reproducible test results, never academic submission artifacts."""
import hashlib,json,shutil
from pathlib import Path
import app

ROOT=app.ROOT.parent
LIB=ROOT/'DOCUMENT_LIBRARY'
OUT=ROOT/'EVALUATION_RESULTS';OUT.mkdir(exist_ok=True)
reports={}
for name in ['lexical-v2','hybrid-v2','live-v2','live-v2-initial','live-v2-with-safe-abstentions']:
 source=app.DATA/'evaluations'/(name+'.json')
 if source.exists():
  shutil.copy2(source,OUT/source.name);reports[name]=json.loads(source.read_text(encoding='utf-8'))
shutil.copy2(app.ROOT/'evaluation_cases_v2.json',OUT/'reference_cases.json')
catalog=json.loads((LIB/'catalog.json').read_text(encoding='utf-8'))
physical=[r for r in catalog if r.get('local_file')]
for r in physical:assert hashlib.sha256((LIB/r['local_file']).read_bytes()).hexdigest()==r['sha256']
with app.connect() as db:
 db_count=db.execute('SELECT COUNT(*) FROM documents').fetchone()[0]
 reviewed=db.execute('SELECT COUNT(*) FROM documents WHERE reviewed=1').fetchone()[0]
 excerpts=db.execute('SELECT COUNT(*) FROM chunks c JOIN documents d ON d.id=c.document_id WHERE d.reviewed=1').fetchone()[0]
assert db_count==len(physical)
summary=json.loads((LIB/'summary.json').read_text(encoding='utf-8'))
summary.update(ai_enabled=app.generation_enabled() and not app.audit_frozen(),search_database_documents=db_count,reviewed_excerpt_documents=reviewed,reviewed_excerpts=excerpts,fully_verified_entitlements=False,audit_baseline_preserved=True,updated='2026-10-28')
(LIB/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
audit=dict(date='2026-10-28',documents=[dict(filename=Path(d['local_file']).name,sha256=d['sha256'],source_url=d['url'],reviewed_excerpts=d.get('verified_excerpts',0),current_verified=d.get('current_verified',False)) for d in physical],search_db_count=db_count,reviewed_excerpt_count=excerpts,approval_boundary='Only explicitly checked excerpts, never entire documents or personal eligibility')
(LIB/'CORPUS_AUDIT.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
lines=['# ผลประเมินโปรแกรมและ RAG — 28 ตุลาคม 2569','',f'คลังและฐานค้นตรงกัน {db_count} ฉบับ มีข้อความตรวจเทียบภาพ {excerpts} ส่วนจาก {reviewed} ฉบับ ส่วนอื่นเป็นประวัติหรือรอตรวจ ไม่ใช้สร้างคำตอบ','', '## วิธีทดลอง','', '- คำถามชุดพัฒนา 60 ข้อ: 48 ข้อที่มีคำตอบอ้างจาก PDF และ 12 ข้อที่ต้องปฏิเสธ/ขอข้อมูลเพิ่ม', '- ระบุประเภทบุคลากร วันที่ ขอบเขต ชื่อไฟล์ เลขหน้า และข้อเท็จจริงสำคัญที่คาดสำหรับแต่ละข้อ', '- ทดลอง TF-IDF, E5 + TF-IDF และ Responses API จริงกับหลักฐานเดียวกัน', '- รอบ AI ล่าสุดปิดแคชคำตอบ; อนุญาตแก้คำตอบที่ไม่ผ่านตัวตรวจได้ไม่เกินหนึ่งครั้ง', '- เกณฑ์อัตโนมัติตรวจสถานะ ข้อเท็จจริงสำคัญ และการอ้างหลักฐานที่คาด ไม่ใช่การพิสูจน์ความหมายทุกข้อความ', '- เป็นชุดที่ใช้พัฒนาและแก้ปัญหา จึงไม่ใช่ชุด holdout และไม่ใช่ผลประเมินจากผู้ใช้อิสระ','', '| วิธี | พบหลักฐาน | ปฏิเสธ/ถามเพิ่มถูก | คำตอบผ่านรายการตรวจ | เวลาเฉลี่ย |','|---|---:|---:|---:|---:|']
for key,label in [('lexical-v2','TF-IDF'),('hybrid-v2','E5 + TF-IDF'),('live-v2','RAG จริง ล่าสุด')]:
 if key not in reports:continue
 s=reports[key]['summary'];answer='ยังไม่วัดการสร้างคำตอบ' if s['end_to_end_passes'] is None else f"{s['end_to_end_passes']}/{s['positive']}"
 lines.append(f"| {label} | {s['retrieval_hits']}/{s['positive']} | {s['negative_correct']}/{s['negative']} | {answer} | {s['mean_ms']/1000:.2f} วินาที |")
if 'live-v2-initial' in reports:
 s=reports['live-v2-initial']['summary'];lines+=['',f"รอบแรกก่อนแก้: คำตอบผ่าน {s['end_to_end_passes']}/{s['positive']} มีข้อผิดพลาด {s['errors']} กรณี เก็บไฟล์ผลเดิมไว้แยกจากรอบล่าสุด"]
lines+=['','## ข้อจำกัดที่ยังต้องระบุ','', '- เอกสาร 24 ฉบับไม่เท่ากับตรวจครบ 24 ฉบับ ข้อความผ่านตรวจใช้เฉพาะหน้าที่ระบุ', '- เงินเดือน/ผู้มีอำนาจอนุมัติ/ค่าอาหารว่างและวิทยากรบางเรื่องยังไม่อนุญาตให้สรุปอัตรา แม้มีเอกสารบางส่วนแล้ว', '- เอกสารเดินทางและเงินยืมที่ยังไม่รับรองความครบถ้วนฉบับแก้ไขใช้โหมดตามฉบับในคลัง พร้อมคำเตือน', '- ข้อมูลจริงรายบุคคล เช่น เงินเดือน ยอดสิทธิ และประวัติการลา ไม่ได้เชื่อมระบบบุคลากร', '- ระบบสำหรับใช้ในเครื่อง ยังไม่เปิดหลายผู้ใช้ผ่านอินเทอร์เน็ต และยังไม่มีผลทดลองผู้ใช้อิสระ', '- การทดสอบติดตั้งเป็น environment ใหม่ในเครื่องเดียว ไม่ใช่การยืนยันทุกเครื่องหรือทุกระบบปฏิบัติการ', '', '## ไฟล์สำหรับตรวจซ้ำ', '', '- EVALUATION_RESULTS/reference_cases.json', '- EVALUATION_RESULTS/lexical-v2.json', '- EVALUATION_RESULTS/hybrid-v2.json', '- EVALUATION_RESULTS/live-v2.json', '- DOCUMENT_LIBRARY/CORPUS_AUDIT.json', '', 'คำสั่งประเมินไม่ใช้ API: `python backend/evaluate_rag_v2.py --mode lexical` และ `--mode hybrid`', '', 'คำสั่ง `--mode live --fresh` ใช้ API จริง จึงไม่รันซ้ำโดยไม่จำเป็น']
(ROOT/'EVALUATION_REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
print('Published real test evidence:',db_count,'PDFs',excerpts,'checked excerpts')
