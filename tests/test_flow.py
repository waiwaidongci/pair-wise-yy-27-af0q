import os, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from database import CollationDB, DomainError

class CollationFlowTest(unittest.TestCase):
    def setUp(self):
        fd,self.path=tempfile.mkstemp(suffix=".db"); os.close(fd); self.db=CollationDB(self.path)
        self.owner=self.db.add_user("负责人","owner"); self.editor=self.db.add_user("编辑","editor"); self.reviewer=self.db.add_user("审阅","reviewer"); self.outsider=self.db.add_user("外部","reviewer")
        self.work=self.db.create_work("残卷","异文比较",self.owner)
        self.w1=self.db.add_witness(self.work,"甲本","version"); self.w2=self.db.add_witness(self.work,"乙本","fragment","馆藏残片","中段缺页")
        self.db.grant_witness_editor(self.w2,self.editor,self.owner); self.db.grant_work_access(self.work,self.reviewer,"view",self.owner)
        self.passage=self.db.add_passage(self.work,"第一节","春水东流，故人南去。",self.owner)
        self.db.align_passage(self.passage,self.w1,"春水东流，故人南去。",1,self.owner)
        self.db.align_passage(self.passage,self.w2,"春水东流，[缺页]",2,self.editor)
    def tearDown(self): self.db.close(); os.unlink(self.path)
    def test_multilayer_revision_snapshot_export_and_lock(self):
        variant=self.db.create_variant(self.passage,self.w2,"春水东流，故人南去。","按语义补足",self.editor,0)
        rev=self.db.update_variant(variant,"春水东流，[不可辨]人南去。","墨迹受损，不再直接补写",self.editor,1)
        self.assertEqual(2,rev)
        snap=self.db.get_snapshot(self.passage,2,self.owner)
        self.assertEqual(2,snap["layer"])
        exported=self.db.export_collation(self.work,self.reviewer)
        self.assertEqual(1,exported["gap_count"])
        self.assertTrue(exported["passages"][0]["variants"][0]["notes"] == [])
        self.db.lock_passage(self.passage,self.owner,"定稿")
        with self.assertRaisesRegex(DomainError,"锁定"):
            self.db.update_variant(variant,"另一文本","无意义修改",self.editor,2)
    def test_optimistic_lock_permission_and_mark_validation(self):
        first=self.db.create_variant(self.passage,self.w2,"补足一","理由一",self.editor,0)
        with self.assertRaisesRegex(DomainError,"版本冲突"):
            self.db.create_variant(self.passage,self.w2,"补足二","理由二",self.editor,0)
        with self.assertRaisesRegex(DomainError,"无权"):
            self.db.create_variant(self.passage,self.w2,"补足三","理由三",self.reviewer,1)
        with self.assertRaisesRegex(DomainError,"无权"):
            self.db.export_collation(self.work,self.outsider)
        with self.assertRaisesRegex(DomainError,"括号"):
            self.db.align_passage(self.passage,self.w1,"文本[未闭合",9,self.owner)

class ReviewSignoffTest(unittest.TestCase):
    def setUp(self):
        fd,self.path=tempfile.mkstemp(suffix=".db"); os.close(fd); self.db=CollationDB(self.path)
        self.owner=self.db.add_user("负责人","owner"); self.editor=self.db.add_user("编辑","editor"); self.reviewer=self.db.add_user("审阅","reviewer"); self.viewer=self.db.add_user("旁观","reviewer")
        self.work=self.db.create_work("残卷","审阅流程",self.owner)
        self.w1=self.db.add_witness(self.work,"甲本","version")
        self.db.grant_witness_editor(self.w1,self.editor,self.owner)
        self.db.grant_work_access(self.work,self.reviewer,"review",self.owner); self.db.grant_work_access(self.work,self.viewer,"view",self.owner)
        self.passage=self.db.add_passage(self.work,"第一节","春水东流，故人南去。",self.owner)
        self.db.align_passage(self.passage,self.w1,"春水东流，故人南去。",1,self.owner)
        self.variant=self.db.create_variant(self.passage,self.w1,"春水东流，故人南去。","初始异文记录",self.editor,0)
    def tearDown(self): self.db.close(); os.unlink(self.path)
    def test_return_requires_reference_and_blocks_lock_until_approval(self):
        with self.assertRaisesRegex(DomainError,"审阅权限"):
            self.db.review_passage(self.passage,"approved","已经过目",self.viewer)
        with self.assertRaisesRegex(DomainError,"结论"):
            self.db.review_passage(self.passage,"maybe","含糊结论",self.reviewer)
        with self.assertRaisesRegex(DomainError,"意见"):
            self.db.review_passage(self.passage,"approved","",self.reviewer)
        rid=self.db.review_passage(self.passage,"returned","第二句缺笔，需重校",self.reviewer)
        with self.assertRaisesRegex(DomainError,"签认"):
            self.db.update_variant(self.variant,"春水东流，故人南去。","无视退回意见",self.editor,1)
        with self.assertRaisesRegex(DomainError,"签认"):
            self.db.update_variant(self.variant,"春水东流，故人南去。","错误签认编号",self.editor,1,review_id=999)
        with self.assertRaisesRegex(DomainError,"锁定"):
            self.db.lock_passage(self.passage,self.owner,"定稿")
        rev=self.db.update_variant(self.variant,"春水东流，[不可辨]南去。","按退回意见重校",self.editor,1,review_id=rid)
        self.assertEqual(2,rev)
        with self.assertRaisesRegex(DomainError,"签认"):
            self.db.update_variant(self.variant,"春水东流，故人南去。","重复引用已失效签认",self.editor,2,review_id=rid)
        with self.assertRaisesRegex(DomainError,"锁定"):
            self.db.lock_passage(self.passage,self.owner,"定稿")
        self.db.review_passage(self.passage,"approved","同意本次修订",self.reviewer)
        self.db.lock_passage(self.passage,self.owner,"定稿")
        with self.assertRaisesRegex(DomainError,"锁定"):
            self.db.review_passage(self.passage,"approved","锁定后再签认",self.reviewer)
    def test_approval_invalidated_by_new_revision_and_export_marks_review(self):
        self.db.review_passage(self.passage,"approved","可以通过",self.reviewer)
        self.db.update_variant(self.variant,"春水东流，故人南去！","补足句读",self.editor,1)
        with self.assertRaisesRegex(DomainError,"锁定"):
            self.db.lock_passage(self.passage,self.owner,"定稿")
        exported=self.db.export_collation(self.work,self.viewer)
        passage=exported["passages"][0]
        self.assertEqual("superseded",passage["review_status"])
        self.assertEqual("approved",passage["review"]["decision"])
        self.assertEqual("可以通过",passage["review"]["opinion"])
        self.assertEqual("审阅",passage["review"]["reviewer_name"])
    def test_legacy_passage_without_reviews_behaves_as_before(self):
        self.db.update_variant(self.variant,"春水东流，故人南去。","无签认照常修订",self.editor,1)
        self.db.lock_passage(self.passage,self.owner,"定稿")
        exported=self.db.export_collation(self.work,self.viewer)
        self.assertEqual("none",exported["passages"][0]["review_status"])
        self.assertIsNone(exported["passages"][0]["review"])

if __name__=="__main__": unittest.main()
