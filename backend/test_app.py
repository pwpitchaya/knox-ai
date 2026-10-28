import base64
import os
import runpy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ['KNOX_SEMANTIC'] = '0'
os.environ['ADMIN_USER'] = 'verify-user'
os.environ['ADMIN_PASSWORD'] = 'verify-password'
from fastapi.testclient import TestClient
import app as knox


class AppTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=knox.ROOT / 'data')
        self.paths = patch.multiple(knox, DATA=Path(self.temp.name), DB=Path(self.temp.name) / 'test.sqlite3')
        self.paths.start()
        (knox.DATA / 'files').mkdir()
        knox.initialize()
        token = base64.b64encode(b'verify-user:verify-password').decode('ascii')
        self.auth_headers = {'Authorization': f'Basic {token}'}
        self.client = TestClient(knox.app, headers=self.auth_headers)
        self.anonymous_client = TestClient(knox.app)
        self.invalid_client = TestClient(knox.app, headers={'Authorization': 'Basic d3Jvbmc6Y3JlZGVudGlhbHM='})
        self.ai = patch('app.ai_config', return_value=(None,None))
        self.ai.start()
        self.generation = patch('app.generation_enabled', return_value=True)
        self.generation.start()
        self.audit = patch('app.audit_frozen',return_value=False)
        self.audit.start()
        self.missing = patch('app.missing_evidence_guard',return_value=None)
        self.missing.start()
        self.current_records_impl=knox.current_records
        self.current = patch('app.current_records',side_effect=lambda records,as_of:records)
        self.current.start()

    def tearDown(self):
        self.invalid_client.close()
        self.anonymous_client.close()
        self.client.close()
        self.ai.stop()
        self.audit.stop()
        self.missing.stop()
        self.current.stop()
        self.generation.stop()
        self.paths.stop()
        self.temp.cleanup()

    def upload(self, text='ข้อความจำลองเพื่อทดสอบเท่านั้น การลาป่วยให้ยื่นเอกสารหลักฐาน', **changes):
        fields = dict(title='TEST ONLY — not a regulation', category='leave',
                      source_url='https://hr.kku.ac.th/test-only', personnel='พนักงานมหาวิทยาลัย',
                      effective_from='2020-01-01')
        fields.update(changes)
        return self.client.post('/api/documents', data=fields,
                                files={'file': ('test.txt', text.encode(), 'text/plain')})

    def question(self, **changes):
        payload = dict(question='การลาป่วยให้ยื่นเอกสารหลักฐานอะไร', personnel='พนักงานมหาวิทยาลัย', as_of='2026-10-27')
        payload.update(changes)
        return self.client.post('/api/ask', json=payload)

    def test_upload_review_retrieve_delete(self):
        uploaded = self.upload()
        self.assertEqual(uploaded.status_code, 201, uploaded.text)
        identifier = uploaded.json()['id']
        self.assertEqual(self.question().json()['status'], 'insufficient_evidence')
        self.assertEqual(self.client.patch(f'/api/documents/{identifier}/review', json={'reviewed': True}).status_code, 200)
        with patch.dict(os.environ, {'OPENAI_API_KEY': '', 'OPENAI_MODEL': ''}):
            result = self.question().json()
        self.assertEqual(result['status'], 'retrieval_only')
        self.assertEqual(result['sources'][0]['citation'], 'S1')
        self.assertIsNone(result['sources'][0]['page_number'])
        self.assertEqual(self.client.get(f'/api/documents/{identifier}/file').status_code, 200)
        self.assertEqual(self.client.delete(f'/api/documents/{identifier}').status_code, 200)
        self.assertEqual(self.client.get('/api/documents').json(), [])
        self.assertEqual(self.client.get(f'/api/documents/{identifier}/file').status_code, 404)

    def test_category_personnel_future_expired_filters(self):
        for changes in [dict(effective_from='2030-01-01'), dict(effective_to='2021-01-01'),
                        dict(personnel='ข้าราชการ'), dict(category='travel')]:
            identifier = self.upload(text=str(changes)+' การลาป่วย', **changes).json()['id']
            self.client.patch(f'/api/documents/{identifier}/review', json={'reviewed': True})
        self.assertEqual(self.question(category='leave').json()['sources'], [])

    def test_metadata_and_duplicate_checks(self):
        self.assertEqual(self.upload(source_url='https://kku.ac.th.evil.example/a').status_code, 422)
        self.assertEqual(self.upload(effective_from='2569-99-01').status_code, 422)
        self.assertEqual(self.upload(effective_to='2019-01-01').status_code, 422)
        self.assertEqual(self.upload().status_code, 201)
        self.assertEqual(self.upload().status_code, 409)
        self.assertEqual(len(list((knox.DATA / 'files').iterdir())), 1)

    def test_missing_date_cannot_be_approved(self):
        identifier = self.upload(effective_from='').json()['id']
        self.assertEqual(self.client.patch(f'/api/documents/{identifier}/review', json={'reviewed': True}).status_code, 422)

    def test_clarifies_personnel(self):
        self.assertEqual(self.question(personnel='').json()['status'], 'clarification')

    def test_cross_origin_write_refused(self):
        self.assertEqual(self.client.post('/api/ask', headers={'origin':'https://evil.example'},
                                        json={'question':'test'}).status_code, 403)

    def test_generation_rejects_unknown_citations(self):
        fake = {'output':[{'type':'message','content':[{'type':'output_text',
                'text':'{"status":"answered","answer":"unsupported [S99]","citations":["S99"]}'}]}]}
        with patch('app.ai_config', return_value=('test-key','test-model')):
            with patch('httpx.post') as post:
                post.return_value.json.return_value = fake
                from fastapi import HTTPException
                with self.assertRaises(HTTPException):
                    knox.generate_answer('question', 'staff', [{'citation':'S1','text':'test'}], '2026-10-27')

    def test_grounded_generation_contract(self):
        fake = {'output':[{'type':'message','content':[{'type':'output_text',
                'text':'{"status":"answered","answer":"ข้อความทดสอบ [S1]","citations":["S1"]}'}]}]}
        identifier = self.upload().json()['id']
        self.client.patch(f'/api/documents/{identifier}/review',json={'reviewed':True})
        with patch('app.ai_config', return_value=('test-key','test-model')):
            with patch('httpx.post') as post:
                post.return_value.json.return_value = fake
                response = self.question()
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['status'],'answered')
        self.assertEqual(response.json()['citations'],['S1'])

    def test_generation_rejects_invented_day_count(self):
        fake={'output':[{'type':'message','content':[{'type':'output_text',
              'text':'{"status":"answered","answer":"ลาได้ 999 วัน [S1]","citations":["S1"]}'}]}]}
        with patch('app.ai_config',return_value=('test-key','test-model')):
            with patch('httpx.post') as post:
                post.return_value.json.return_value=fake
                from fastapi import HTTPException
                with self.assertRaises(HTTPException):
                    knox.generate_answer('question','staff',[{'citation':'S1','text':'ลาได้ ๓ วัน'}],'2026-10-27')

    def test_equivalent_number_and_citation_format(self):
        import json
        fake={'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps({'status':'answered','answer':'อัตรา 2500.00 บาท [ S1 ]','citations':['S1']})}]}]}
        with patch('app.ai_config',return_value=('test-key','test-model')),patch('httpx.post') as post:
            post.return_value.json.return_value=fake
            answer=knox.generate_answer('question','staff',[{'citation':'S1','text':'อัตรา 2,500 บาท'}],'2026-10-27')
            self.assertEqual(answer['status'],'answered')
            self.assertIn('[S1]',answer['answer'])
            self.assertEqual(post.call_count,1)

    def test_one_validation_repair_and_usage_accounting(self):
        import json
        def fake(number,tokens):
            return {'usage':{'input_tokens':tokens,'output_tokens':1,'total_tokens':tokens+1},'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps({'status':'answered','answer':f'ลาได้ {number} วัน [S1]','citations':['S1']})}]}]}
        with patch('app.ai_config',return_value=('test-key','test-model')),patch('httpx.post') as post:
            post.return_value.json.side_effect=[fake(999,10),fake(3,20)]
            answer=knox.generate_answer('question','staff',[{'citation':'S1','text':'ลาได้ 3 วัน'}],'2026-10-27')
            self.assertEqual(answer['validation_repairs'],1)
            self.assertEqual(answer['usage']['input_tokens'],30)
            self.assertEqual(post.call_count,2)

    def test_user_tenure_context_does_not_authorize_invented_rate(self):
        import json
        from fastapi import HTTPException
        def fake(answer):
            return {'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps({'status':'answered','answer':answer,'citations':['S1']})}]}]}
        with patch('app.ai_config',return_value=('test-key','test-model')),patch('httpx.post') as post:
            post.return_value.json.return_value=fake('ทำงานมา 3 ปี สะสมได้ 20 วันทำการ [S1]')
            result=knox.generate_answer('ทำงานมา 3 ปี สะสมวันลาได้เท่าไร','staff',[{'citation':'S1','text':'สะสมได้ 20 วันทำการ'}],'2026-10-27')
            self.assertIn('context_from_question',result)
            post.return_value.json.return_value=fake('เบิกได้ 3 บาท [S1]')
            with self.assertRaises(HTTPException):
                knox.generate_answer('ทำงานมา 3 ปี เบิกได้เท่าไร','staff',[{'citation':'S1','text':'เบิกได้ 20 บาท'}],'2026-10-27')

    def test_credit_error_is_explained_without_credentials(self):
        import httpx
        from fastapi import HTTPException
        response=httpx.Response(429,json={'error':{'code':'credit_balance_exhausted'}},
                                request=httpx.Request('POST','https://api.openai.com/v1/responses'))
        with patch('app.ai_config',return_value=('test-key','test-model')):
            with patch('httpx.post',return_value=response):
                with self.assertRaises(HTTPException) as caught:
                    knox.generate_answer('question','staff',[],'2026-10-27')
        self.assertEqual(caught.exception.status_code,503)
        self.assertIn('เครดิต',caught.exception.detail)
        self.assertNotIn('test-key',caught.exception.detail)

    def test_document_only_mode_never_calls_ai(self):
        with patch('app.generation_enabled',return_value=False):
            with patch('app.ai_config',return_value=('configured-key','configured-model')):
                with patch('httpx.post') as post:
                    self.assertIsNone(knox.generate_answer('question','staff',[],'2026-10-27'))
                    post.assert_not_called()

    def test_ui_assets(self):
        for route in ['/', '/assets/app.js', '/assets/style.css', '/api/status']:
            self.assertEqual(self.client.get(route).status_code, 200)
        self.assertEqual(self.client.get('/assets/not-found').status_code, 404)

    def test_basic_auth_protects_app_api_and_references(self):
        self.assertEqual(self.anonymous_client.get('/').status_code, 401)
        self.assertEqual(self.anonymous_client.post('/api/ask', json={'question': 'test'}).status_code, 401)
        self.assertEqual(self.anonymous_client.get('/references/').status_code, 401)
        self.assertEqual(self.invalid_client.get('/').status_code, 401)
        self.assertEqual(self.client.get('/').status_code, 200)
        self.assertEqual(self.client.get('/api/status').status_code, 200)
        self.assertEqual(self.client.get('/references/').status_code, 200)

    def test_docs_are_unavailable_when_disabled(self):
        for route in ['/docs', '/redoc', '/openapi.json']:
            self.assertEqual(self.client.get(route).status_code, 404)

    def test_missing_auth_settings_prevent_startup(self):
        with patch.dict(os.environ, {'ADMIN_USER': '', 'ADMIN_PASSWORD': ''}, clear=False):
            with patch('dotenv.load_dotenv', return_value=False):
                with self.assertRaisesRegex(RuntimeError, 'ADMIN_USER and ADMIN_PASSWORD'):
                    runpy.run_path(str(knox.ROOT / 'app.py'))

    def test_missing_documents_stop_before_retrieval_and_ai(self):
        from audit_lock import missing_evidence_guard
        with patch('audit_lock.POLICY',Path(self.temp.name)/'policy.json'), patch('app.missing_evidence_guard',side_effect=missing_evidence_guard), patch('app.rank') as rank, patch('app.generate_answer') as generate:
            for question in ['1/2569','๒/๒๕๖๙','4163/2569','5/2569','6/2569','1605/2564','1026/2564','ลาป่วยได้กี่วัน','เงินเดือนเท่าไร','เบิกค่ารักษาพยาบาล','ส่งใช้เงินยืม']:
                result=self.client.post('/api/ask',json={'question':question,'personnel':'พนักงานมหาวิทยาลัย'}).json()
                self.assertEqual(result['status'],'insufficient_evidence',question)
                self.assertEqual(result['sources'],[])
            rank.assert_not_called()
            generate.assert_not_called()
            self.assertIsNone(missing_evidence_guard('ค่าแท็กซี่เดินทางไปปฏิบัติงาน'))

    def test_audit_lock_blocks_document_mutation(self):
        with patch('app.audit_frozen',return_value=True):
            self.assertEqual(self.upload().status_code,423)
            self.assertEqual(self.client.post('/api/relationships',json={}).status_code,423)

    def test_current_scope_checks_hash_and_review_horizon(self):
        identifier=self.upload().json()['id']
        rows=[{'document_id':identifier}]
        self.assertEqual(self.current_records_impl(rows,'2026-10-27'),[])
        with knox.connect() as db:
            digest=db.execute('SELECT sha256 FROM documents WHERE id=?',(identifier,)).fetchone()[0]
            db.execute('INSERT INTO document_audits VALUES(?,?,?,?,?)',(identifier,1,'2026-10-27',digest,'test evidence'))
        self.assertEqual(self.current_records_impl(rows,'2026-10-27'),rows)
        self.assertEqual(self.current_records_impl(rows,'2026-10-28'),[])
        with knox.connect() as db:db.execute('UPDATE document_audits SET approved_sha=?',('changed-content',))
        self.assertEqual(self.current_records_impl(rows,'2026-10-27'),[])

    def test_answer_cache_avoids_second_generation(self):
        identifier=self.upload().json()['id']
        self.client.patch(f'/api/documents/{identifier}/review',json={'reviewed':True})
        with patch('app.generate_answer',return_value={'status':'answered','answer':'ข้อความจำลอง [S1]','citations':['S1']}) as generate:
            first=self.question().json();second=self.question().json()
            self.assertEqual(first['status'],'answered')
            self.assertFalse(first['cached']);self.assertTrue(second['cached'])
            self.assertEqual(generate.call_count,1)

    def test_relationship_runs_before_retrieval(self):
        old=self.upload(text='เอกสารฉบับเก่าการลาป่วย',title='old').json()['id']
        new=self.upload(text='เอกสารฉบับใหม่การลาป่วย',title='new',effective_from='2022-10-27').json()['id']
        for identifier in [old,new]:
            self.client.patch(f'/api/documents/{identifier}/review',json={'reviewed':True})
        relation=dict(older_id=old,newer_id=new,kind='REPLACES',scope='document',
                      effective_from='2022-10-27',source_url='https://hr.kku.ac.th/source',
                      pdf_page=1,evidence_excerpt='ข้อความจำลองว่าฉบับใหม่ให้ยกเลิกฉบับเดิม',reviewed=True)
        self.assertEqual(self.client.post('/api/relationships',json=relation).status_code,201)
        result=self.question().json()
        self.assertEqual(len(result['version_audit']),1)
        self.assertTrue(result['sources'])
        self.assertTrue(all(s['document_id']==new for s in result['sources']))

    def test_partial_relationship_abstains(self):
        old=self.upload(text='เอกสารฉบับเก่าการลาป่วย',title='old').json()['id']
        new=self.upload(text='เอกสารแก้ไขการลาป่วย',title='new').json()['id']
        for identifier in [old,new]:
            self.client.patch(f'/api/documents/{identifier}/review',json={'reviewed':True})
        relation=dict(older_id=old,newer_id=new,kind='AMENDS',scope='clause:10',
                      effective_from='2022-10-27',source_url='https://hr.kku.ac.th/source',
                      pdf_page=1,evidence_excerpt='ข้อความจำลองแก้ไขเฉพาะข้อสิบของฉบับเดิม',reviewed=True)
        self.client.post('/api/relationships',json=relation)
        self.assertEqual(self.question().json()['status'],'needs_manual_review')


if __name__ == '__main__':
    unittest.main()
