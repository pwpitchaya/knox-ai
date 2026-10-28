import unittest
from versioning import resolve_versions


class VersionTests(unittest.TestCase):
    def setUp(self):
        self.docs = [dict(id=x, reviewed=1, effective_from='2020-01-01', effective_to=None) for x in ['old','new','third']]
        self.records = [dict(document_id=x, text=x) for x in ['old','new','third']]
        self.edge = dict(older_id='old',newer_id='new',kind='REPLACES',scope='document',
                         effective_from='2022-10-27',reviewed=1,evidence_excerpt='verified repeal',
                         source_url='https://hr.kku.ac.th/source',pdf_page=1)

    def resolve(self, edges):
        return resolve_versions(self.records,self.docs,edges,'2026-10-27')

    def test_excludes_superseded_document(self):
        records,audit,issues=self.resolve([self.edge])
        self.assertEqual([r['document_id'] for r in records],['new','third'])
        self.assertEqual(len(audit),1);self.assertEqual(issues,[])

    def test_future_relationship_does_not_apply(self):
        records,_,issues=self.resolve([dict(self.edge,effective_from='2030-01-01')])
        self.assertEqual(len(records),3);self.assertEqual(issues,[])

    def test_missing_or_unreviewed_replacement_blocks(self):
        for change in [dict(newer_id='missing'),dict(reviewed=0)]:
            self.assertTrue(self.resolve([dict(self.edge,**change)])[2])
        self.docs[1]['reviewed']=0
        self.assertTrue(self.resolve([self.edge])[2])

    def test_partial_amendment_requires_review(self):
        self.assertTrue(self.resolve([dict(self.edge,kind='AMENDS',scope='clause:12')])[2])

    def test_branch_and_cycle_are_blocked(self):
        self.assertTrue(self.resolve([self.edge,dict(self.edge,newer_id='third')])[2])
        self.assertTrue(self.resolve([self.edge,dict(self.edge,older_id='new',newer_id='old')])[2])


if __name__=='__main__':unittest.main()
