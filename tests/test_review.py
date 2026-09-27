import os, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from database import CollationDB, DomainError

class ReviewSignoffTest(unittest.TestCase):
    def setUp(self):
        fd,self.path=tempfile.mkstemp(suffix=".db"); os.close(fd); self.db=CollationDB(self.path)
        self.owner=self.db.add_user("负责人","owner"); self.editor=self.db.add_user("编辑","editor")
        self.reviewer=self.db.add_user("审阅","reviewer"); self.viewer=self.db.add_user("旁观","reviewer")
        self.work=self.db.create_work("残卷","审阅流程",self.owner)
        self.w1=self.db.add_witness(self.work,"甲本","version"); self.w2=self.db.add_witness(self.work,"乙本","fragment")
        self.db.grant_witness_editor(self.w2,self.editor,self.owner)
        self.db.grant_work_access(self.work,self.reviewer,"review",self.owner)
        self.db.grant_work_access(self.work,self.viewer,"view",self.owner)
        self.passage=self.db.add_passage(self.work,"第一节","春水东流，故人南去。",self.owner)
        self.db.align_passage(self.passage,self.w1,"春水东流，故人南去。",1,self.owner)
        self.db.align_passage(self.passage,self.w2,"春水东流，[缺页]",2,self.editor)
        self.variant=self.db.create_variant(self.passage,self.w2,"春水东流，故人南去。","按语义补足",self.editor,0)
    def tearDown(self): self.db.close(); os.unlink(self.path)

    def test_review_requires_permission_decision_and_opinion(self):
        with self.assertRaisesRegex(DomainError,"审阅权限"):
            self.db.add_review(self.passage,self.viewer,"approved","看过")
        with self.assertRaisesRegex(DomainError,"结论"):
            self.db.add_review(self.passage,self.reviewer,"maybe","看过")
        with self.assertRaisesRegex(DomainError,"处理意见"):
            self.db.add_review(self.passage,self.reviewer,"approved","  ")
        rid=self.db.add_review(self.passage,self.reviewer,"approved","底本可信，拟文可从。")
        self.assertGreater(rid,0)
        exported=self.db.export_collation(self.work,self.viewer)
        self.assertEqual("approved",exported["passages"][0]["review_state"])
        self.assertEqual("审阅",exported["passages"][0]["reviews"][0]["reviewer_name"])

    def test_returned_review_must_be_addressed_and_blocks_lock(self):
        rid=self.db.add_review(self.passage,self.reviewer,"returned","补字缺少版本依据，退回重拟。")
        with self.assertRaisesRegex(DomainError,"签认编号"):
            self.db.update_variant(self.variant,"春水东流，旧人南去。","换拟补字",self.editor,1)
        with self.assertRaisesRegex(DomainError,"签认编号无效"):
            self.db.update_variant(self.variant,"春水东流，旧人南去。","换拟补字",self.editor,1,999)
        with self.assertRaisesRegex(DomainError,"退回签认"):
            self.db.lock_passage(self.passage,self.owner,"定稿")
        rev=self.db.update_variant(self.variant,"春水东流，旧人南去。","据丙本行款改拟",self.editor,1,rid)
        self.assertEqual(2,rev)
        reviews=self.db.export_collation(self.work,self.owner)["passages"][0]["reviews"]
        self.assertEqual("addressed",reviews[0]["status"]); self.assertEqual(2,reviews[0]["addressed_revision"])
        with self.assertRaisesRegex(DomainError,"处理中"):
            self.db.lock_passage(self.passage,self.owner,"定稿")
        self.db.add_review(self.passage,self.reviewer,"approved","新拟文有据，可以通过。")
        self.db.lock_passage(self.passage,self.owner,"定稿")
        with self.assertRaisesRegex(DomainError,"锁定"):
            self.db.add_review(self.passage,self.reviewer,"approved","锁定后不应再签认")

    def test_content_change_invalidates_old_review(self):
        self.db.add_review(self.passage,self.reviewer,"approved","当前文本可定。")
        self.db.update_variant(self.variant,"春水东流，[不可辨]南去。","墨迹存疑改标",self.editor,1)
        exported=self.db.export_collation(self.work,self.owner)
        self.assertEqual("superseded",exported["passages"][0]["reviews"][0]["status"])
        self.assertEqual("pending",exported["passages"][0]["review_state"])
        with self.assertRaisesRegex(DomainError,"处理中"):
            self.db.lock_passage(self.passage,self.owner,"定稿")

    def test_legacy_passage_without_reviews_unchanged(self):
        legacy=self.db.add_passage(self.work,"第二节","明月照积雪。",self.owner)
        self.db.lock_passage(legacy,self.owner,"旧段落直接定稿")
        exported=self.db.export_collation(self.work,self.owner)
        second=exported["passages"][1]
        self.assertEqual("none",second["review_state"]); self.assertEqual([],second["reviews"])
        self.assertEqual("locked",second["status"])

if __name__=="__main__": unittest.main()
