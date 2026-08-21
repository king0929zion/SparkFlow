from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


class RepositoryPolicyTests(unittest.TestCase):
    def test_obsolete_branch_workflows_are_removed(self):
        self.assertFalse((WORKFLOWS / "schedule_api.yml").exists())
        self.assertFalse((WORKFLOWS / "schedule_dev.yml").exists())
        self.assertFalse((WORKFLOWS / "smoke.yml").exists())

    def test_unified_workflow_does_not_checkout_legacy_branches(self):
        workflow = (WORKFLOWS / "schedule.yml").read_text(encoding="utf-8")
        self.assertNotIn("ref: api", workflow)
        self.assertNotIn("ref: dev", workflow)
        self.assertIn("python main.py --mode smoke", workflow)
        self.assertIn("python main.py --mode send", workflow)

    def test_branch_policy_preserves_only_main(self):
        policy = (WORKFLOWS / "branch-policy.yml").read_text(encoding="utf-8")
        self.assertIn('if [ "$branch" = "main" ]', policy)
        self.assertIn("Delete every non-main branch", policy)

    def test_douyin_runtime_is_locked_to_web_chat(self):
        workflow = (WORKFLOWS / "schedule.yml").read_text(encoding="utf-8")
        tasks = (ROOT / "core" / "tasks.py").read_text(encoding="utf-8")

        self.assertIn('CHAT_URL = "https://www.douyin.com/chat"', tasks)
        self.assertNotIn("creator.douyin.com", tasks)
        self.assertIn('"https://www.douyin.com/chat"', workflow)
        self.assertNotIn('"https://www.douyin.com/"', workflow)


if __name__ == "__main__":
    unittest.main()
