# KNOX AI

ระบบต้นแบบสำหรับค้นคืนข้อมูลระเบียบและประกาศที่เกี่ยวข้องกับบุคลากรมหาวิทยาลัยขอนแก่นด้วยแนวทาง Retrieval-Augmented Generation (RAG) ระบบแสดงข้อความหลักฐาน เลขหน้า และลิงก์เอกสารต้นฉบับเพื่อให้ผู้ใช้ตรวจสอบได้

> ระบบเป็นเครื่องมือช่วยค้นหาและสรุปจากหลักฐานในคลัง ไม่ใช่ระบบรับรองสิทธิรายบุคคลหรือคำวินิจฉัยของหน่วยงานทรัพยากรบุคคล

## ข้อมูลโครงงาน

| รายการ | รายละเอียด |
| --- | --- |
| รายวิชา | IN404498 : โครงงานทางวิทยาการคอมพิวเตอร์และสารสนเทศ 1 |
| ผู้จัดทำ | นางสาวภวพิชญา คำวงษา |
| รหัสนักศึกษา | 663450042-8 |
| หลักสูตร | วิทยาการคอมพิวเตอร์และสารสนเทศ สาขาวิทยาการคอมพิวเตอร์และสารสนเทศ |

เอกสารสถานะและผลตรวจ: [CURRENT_READINESS.md](CURRENT_READINESS.md), [EVALUATION_REPORT.md](EVALUATION_REPORT.md), และ [PROJECT_READINESS_REVIEW.md](PROJECT_READINESS_REVIEW.md)

## ความสามารถหลัก

- ค้นข้อความจากเอกสารตามประเภทบุคลากร หมวด วันที่อ้างอิง และขอบเขตหลักฐาน
- ตรวจความสัมพันธ์ระหว่างเอกสารฉบับเดิมและฉบับแก้ไขก่อนค้นคืน
- แสดงข้อความอ้างอิง เลขหน้า และลิงก์ PDF ต้นฉบับ
- ใช้ TF-IDF ได้โดยไม่โหลด semantic model เพื่อรองรับเครื่องหรือ Cloud ที่มี RAM จำกัด
- ใช้ AI สร้างคำตอบได้เมื่อกำหนด OpenAI API key; หากไม่กำหนด ระบบยังค้นและแสดงหลักฐานได้
- ป้องกันหน้าเว็บ API และคลังเอกสารด้วย HTTP Basic Authentication

## โครงสร้างสำคัญ

```text
backend/app.py              FastAPI application และ RAG workflow
backend/web/                หน้าเว็บ HTML, CSS และ JavaScript
backend/data/               SQLite และไฟล์ runtime (ไม่เก็บใน Git)
backend/.env.example        ตัวอย่างตัวแปร environment
DOCUMENT_LIBRARY/           สำเนาเอกสารอ้างอิงในเครื่อง (ตรวจสิทธิ์ก่อนเผยแพร่)
EVALUATION_RESULTS/         ผลการประเมิน
```

## เปิดใช้งานในเครื่อง

1. คัดลอก `backend/.env.example` เป็น `backend/.env`

   ```powershell
   Copy-Item backend/.env.example backend/.env
   ```

2. กำหนดค่าต่อไปนี้ใน `backend/.env`

   ```env
   ADMIN_USER=your-admin-user
   ADMIN_PASSWORD=use-a-strong-password
   USE_TFIDF_ONLY=true
   ```

   หากไม่ต้องการเรียกบริการ AI ให้ตั้ง `KNOX_GENERATION_ENABLED=0`

3. รัน `INSTALL_KNOX.ps1` แล้วรัน `START_KNOX.ps1`
4. เปิด `http://127.0.0.1:8000/` และกรอก Basic Auth ตามค่าที่กำหนด

ระบบจะไม่เริ่มทำงานหากไม่มี `ADMIN_USER` และ `ADMIN_PASSWORD` และห้าม commit ไฟล์ `.env`

## วิธีใช้งาน

1. เลือกประเภทบุคลากร หมวดข้อมูล วันที่อ้างอิง และขอบเขตหลักฐาน
2. พิมพ์คำถาม เช่น `ลาป่วยต้องใช้ใบรับรองแพทย์ไหม` แล้วกดปุ่ม **ถาม**
3. อ่านคำตอบและเปิดลิงก์ PDF เพื่อตรวจข้อความต้นฉบับ

หน้าคลังต้นฉบับ: http://127.0.0.1:8000/references/

คลังและฐานค้นมี 24 PDF แต่ใช้ตอบเฉพาะข้อความที่ผ่านขอบเขตการตรวจสอบแล้ว ไม่รับรองทุกข้อความของทุกไฟล์หรือสิทธิรายบุคคล

## ติดตั้งใหม่บน Windows / Python 3.13

รัน INSTALL_KNOX.ps1 เพื่อสร้าง .venv และติดตั้ง dependencies พื้นฐาน จากนั้น START_KNOX.ps1

E5 เป็นส่วนเสริม: ติดตั้ง backend/requirements-semantic.txt และต้องมีโมเดล intfloat/multilingual-e5-base ในแคช ระบบไม่ดาวน์โหลดโมเดลเอง หากไม่มีจะค้นแบบ TF-IDF ได้

OCR เป็นส่วนเสริม: SETUP_OCR.ps1 และต้องมี pdftoppm ใน PATH ผล OCR ยังต้องตรวจภาพก่อนอนุมัติใช้ตอบ

ทดสอบติดตั้ง environment ใหม่ในเครื่องเดียวแล้ว ไม่อ้างว่าทดสอบทุกเครื่องหรือทุกระบบปฏิบัติการ

## การตั้งค่า AI และ Environment

เก็บ OPENAI_API_KEY และ OPENAI_MODEL ใน backend/.env เท่านั้น KNOX_GENERATION_ENABLED=1 เปิดการสร้างคำตอบ และ =0 ใช้อ่านหลักฐานอย่างเดียว คีย์ไม่อยู่ในหน้าเว็บหรือ Git

คำถามและข้อความหลักฐานที่ค้นพบจะถูกส่งไป OpenAI เมื่อเปิด AI ใช้กับเอกสารสาธารณะเท่านั้น ไม่มีการเชื่อมข้อมูลส่วนบุคคลจากระบบ HR

อ้างอิง API: https://developers.openai.com/api/docs/guides/structured-outputs

| ตัวแปร | ความหมาย |
| --- | --- |
| `ADMIN_USER` / `ADMIN_PASSWORD` | ข้อมูลสำหรับ HTTP Basic Auth; ต้องกำหนดทั้งคู่ |
| `USE_TFIDF_ONLY` | ตั้งเป็น `true` เพื่อข้าม E5 และประหยัด RAM |
| `KNOX_SEMANTIC` | เปิด/ปิด semantic retrieval เมื่อมีโมเดลใน local cache |
| `KNOX_GENERATION_ENABLED` | ตั้งเป็น `0` เพื่อใช้โหมดค้นเอกสารอย่างเดียว |
| `OPENAI_API_KEY`, `OPENAI_MODEL` | การตั้งค่าสำหรับ AI generation (เป็นทางเลือก) |
| `ENABLE_DOCS` | ตั้งเป็น `true` เมื่อต้องการ Swagger/ReDoc; ยังต้องผ่าน Basic Auth |

## Deploy อย่างปลอดภัย

ตั้ง `ADMIN_USER` และ `ADMIN_PASSWORD` เป็น secret/environment variables ของผู้ให้บริการโฮสต์ (ไม่ใช้ค่า default และไม่ commit `.env`) หน้าเว็บ, `/assets`, `/api` และ `/references` ต้องผ่าน HTTP Basic Auth ทั้งหมด ส่วน `/docs`, `/redoc` และ `/openapi.json` ปิดเป็นค่าเริ่มต้น; เปิดเฉพาะเมื่อจำเป็นด้วย `ENABLE_DOCS=true` และยังต้องผ่าน Basic Auth

HTTP Basic Auth ส่งรหัสผ่านมากับทุก request ดังนั้นต้อง Deploy หลัง HTTPS ของผู้ให้บริการเท่านั้น ห้ามเผยแพร่ผ่าน HTTP ปกติ

## ตรวจซ้ำ

python -m unittest discover -s backend -p 'test_*.py'

python backend/verify_audit_lock.py

python backend/evaluate_rag_v2.py --mode lexical

python backend/evaluate_rag_v2.py --mode hybrid

คำสั่ง --mode live --fresh ใช้ API จริง มีค่าใช้จ่าย จึงไม่ต้องรันซ้ำก่อนสาธิตทุกครั้ง

## ข้อมูล เอกสาร และการย้ายเครื่อง

สำรอง `backend/data/`, `DOCUMENT_LIBRARY/`, `backend/verified_corpus_v2.json` และไฟล์ตั้งค่าแยกอย่างปลอดภัย SQLite และต้นฉบับอยู่ในเครื่อง อย่านำ `.env` ไปเผยแพร่ ข้อมูล `backend/data/` ถูกละเว้นจาก Git จึงต้องส่งชุดข้อมูลแยกหากต้องการย้ายเครื่อง

ก่อนเผยแพร่ repository แบบ public ต้องตรวจสิทธิ์เผยแพร่ ลิขสิทธิ์ และข้อมูลส่วนบุคคลของเอกสารใน `DOCUMENT_LIBRARY/` ทุกฉบับ แม้เอกสารจะอ้างถึงแหล่งสาธารณะ ระบบจะทำงานได้โดยไม่มีโฟลเดอร์นี้ แต่หน้าคลังเอกสารจะไม่ถูก mount; หากไม่มี `backend/data/` ระบบจะเริ่มได้แต่ไม่มีฐานความรู้พร้อมตอบคำถาม

โค้ดปัจจุบันเริ่มที่ backend/app.py; backend/main.py เป็นระบบเดิม ไม่ใช่จุดเปิดโปรแกรมเวอร์ชันนี้
