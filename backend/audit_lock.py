"""Local audit policy, checked before retrieval or generation; no AI dependency."""
import json
import re
from pathlib import Path

POLICY = Path(__file__).resolve().parent.parent / 'DOCUMENT_LIBRARY' / 'AUDIT_LOCK.json'

def audit_frozen():
    # A missing/corrupt lock must not silently reopen generation or collection.
    try:
        return json.loads(POLICY.read_text(encoding='utf-8')).get('frozen', True)
    except (OSError, ValueError):
        return True

def assert_collection_open():
    if audit_frozen():
        raise RuntimeError('Audit lock active: collection/import/rebuild stopped. Explicit scope change required.')

def missing_evidence_guard(question):
    text=question.translate(str.maketrans('๐๑๒๓๔๕๖๗๘๙','0123456789'))
    text=re.sub(r'\s+','',text)
    if any(w in text.lower() for w in ['ignoreprevious','เพิกเฉยคำสั่ง','แสดงapikey','เปิดเผยapikey','systemprompt']):
        return {'status':'insufficient_evidence','answer':'คำขอนี้อยู่นอกขอบเขตค้นเอกสารบุคลากร มข. ระบบไม่เปิดเผยคำสั่งหรือข้อมูลลับ','sources':[]}
    if any(w in text for w in ['ยอดคงเหลือของฉัน','ยอดเงินคงเหลือ','วันลาคงเหลือของฉัน','เหลือวันลากี่วัน','เงินเดือนของฉัน','ประวัติการลาของ']):
        return {'status':'insufficient_evidence','answer':'ระบบมีเฉพาะระเบียบสาธารณะ ไม่มีข้อมูลเงินเดือน ยอดสิทธิ หรือประวัติส่วนบุคคล กรุณาตรวจระบบบุคลากร/เจ้าหน้าที่ที่เกี่ยวข้อง','sources':[]}
    if any(w in text for w in ['ลงทุนหุ้น','เลขเด็ด','สูตรทำอาหาร','สภาพอากาศ','รหัสผ่าน']):
        return {'status':'insufficient_evidence','answer':'คำถามอยู่นอกขอบเขตเอกสารการลา การเดินทาง เบิกจ่าย และสิทธิบุคลากร มข.','sources':[]}
    try:
        coverage=json.loads((POLICY.parent/'coverage_policy.json').read_text(encoding='utf-8'))
        approved=set(coverage.get('reviewed_numbers',[]))
    except (OSError,ValueError):approved=set()
    rules=[
        ('1/2569','การลาของพนักงานมหาวิทยาลัย', ['ลาป่วย','ลากิจ','ลาคลอด','ลาพักผ่อน','วันลา','สิทธิลา','การลา']),
        ('2/2569','การลาของลูกจ้างของมหาวิทยาลัย', ['ลาป่วย','ลากิจ','ลาคลอด','ลาพักผ่อน','วันลา','สิทธิลา','การลา']),
        ('4163/2569','การมอบอำนาจเกี่ยวกับการลา', ['อนุมัติลา','อนุมัติการลา','มอบอำนาจ']),
        ('5/2569','บัญชีเงินเดือนและค่าตอบแทน', ['เงินเดือน','ค่าตอบแทน','โบนัส','เงินรางวัล']),
        ('6/2569','หลักเกณฑ์เลื่อนเงินเดือน', ['เลื่อนเงินเดือน','ขึ้นเงินเดือน']),
        ('1605/2564','สวัสดิการผู้ปฏิบัติงาน', ['สวัสดิการ','รักษาพยาบาล','ตรวจสุขภาพ','ศึกษาบุตร','ภัยพิบัติ']),
        ('1026/2564','เงินยืมทดรองจ่าย', ['เงินยืม','ยืมเงิน','ทดรอง','ส่งใช้เงิน','คืนเงินยืม']),
        ('1880/2559','ค่าใช้จ่ายฝึกอบรม/ดำเนินโครงการและฉบับแก้ไข', ['อาหารว่าง','ค่าวิทยากร','สมนาคุณวิทยากร','จัดประชุม','จัดอบรม']),
    ]
    blocked=[]
    for number,title,terms in rules:
        if number in approved:continue
        pattern=r'(?<![0-9])'+re.escape(number)+r'(?![0-9])'
        matches=any(term in text for term in terms)
        if number=='5/2569' and any(w in text for w in ['ลาป่วย','ลากิจ','ลาคลอด','ลาพักผ่อน','ระหว่างลา']):matches=False
        if re.search(pattern,text) or matches:
            blocked.append({'number':number,'title':title})
    if not blocked:return None
    return {'status':'insufficient_evidence','answer':'ยังสรุปสิทธิไม่ได้: ยังไม่มีข้อความที่ผ่านตรวจเพียงพอสำหรับ '+ ' / '.join(r['number']+' '+r['title'] for r in blocked)+ ' (อาจมีไฟล์แล้วแต่ยังรอตรวจ) จึงหยุดก่อนค้นหรือเรียก AI และไม่ใช้ฉบับเก่าแทน',
            'sources':[],'missing_documents':blocked,'audit_locked':audit_frozen()}
