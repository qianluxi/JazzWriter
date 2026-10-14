import tempfile
import unittest
from pathlib import Path

import store
from store import load_runs, save_run
from tests.helpers import make_session


class RecordsTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self._runs, self._advice = store.RUNS_DIR, store.ADVICE_PATH
        store.RUNS_DIR = self.tmp / "runs"
        store.ADVICE_PATH = self.tmp / "advice.jsonl"

    def tearDown(self):
        store.RUNS_DIR, store.ADVICE_PATH = self._runs, self._advice
        self._tmp.cleanup()

    def test_play_writes_complete_run_record(self):
        session = make_session(seed=321)
        take, evaluation = session.play(
            "废弃工厂。林推开门。", pov="林", chapter=3,
            jazz_mode="free_jazz", seed=321,
        )
        records = load_runs(outdir=store.RUNS_DIR)
        self.assertEqual(len(records), 1)
        rec = records[0]
        for field in ("run_id", "chapter", "seed", "mode", "cue", "cue_directives",
                      "prompt", "scene", "take", "evaluation", "conductor_advice",
                      "provider", "created_at"):
            self.assertIn(field, rec, f"missing {field}")
        # the saved prompt must be the prompt actually sent to the model
        self.assertEqual(rec["prompt"], take.prompt)
        self.assertEqual(rec["cue"]["seed_int"], 321)
        self.assertEqual(rec["take"]["text"], take.text)
        self.assertEqual(rec["evaluation"]["overall"], round(evaluation.overall, 3))

    def test_save_run_roundtrip(self):
        rec = {"run_id": "ch000_x", "chapter": 0, "take": {"text": "hi"}}
        save_run(rec, outdir=store.RUNS_DIR)
        got = load_runs(outdir=store.RUNS_DIR)
        self.assertEqual(got[0]["run_id"], "ch000_x")


if __name__ == "__main__":
    unittest.main()
