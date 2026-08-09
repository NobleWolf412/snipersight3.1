import base64
import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from engine import copilot


class SpotterAnalysisTest(unittest.TestCase):
    def frame(self, timestamp_ms=0):
        encoded = base64.b64encode(b"small-jpeg-fixture").decode("ascii")
        return {"timestamp_ms": timestamp_ms,
                "image": "data:image/jpeg;base64," + encoded}

    def test_analysis_is_ephemeral_read_only_and_image_grounded(self):
        observed = {}

        def run(args, **kwargs):
            observed["args"] = args
            observed["cwd"] = kwargs["cwd"]
            observed["prompt"] = kwargs["input"]
            image_paths = [args[i + 1] for i, value in enumerate(args)
                           if value == "--image"]
            self.assertEqual(2, len(image_paths))
            self.assertTrue(all(__import__("pathlib").Path(p).exists()
                                for p in image_paths))
            return SimpleNamespace(returncode=0, stdout="timestamped report",
                                   stderr="")

        with patch("engine.copilot.shutil.which", return_value="codex"), \
             patch("engine.copilot.subprocess.run", side_effect=run):
            result = copilot.analyze_frames([self.frame(0), self.frame(65000)])

        self.assertTrue(result["ok"])
        self.assertEqual(2, result["frames_analyzed"])
        self.assertIn("--ephemeral", observed["args"])
        self.assertIn("read-only", observed["args"])
        self.assertIn("--ignore-user-config", observed["args"])
        self.assertIn("--ignore-rules", observed["args"])
        self.assertIn("01:05", observed["prompt"])
        self.assertFalse(__import__("pathlib").Path(observed["cwd"]).exists())

    def test_invalid_frame_never_invokes_codex(self):
        with patch("engine.copilot.shutil.which", return_value="codex"), \
             patch("engine.copilot.subprocess.run") as run:
            result = copilot.analyze_frames([{"image": "not-an-image"}])
        self.assertFalse(result["ok"])
        run.assert_not_called()

    def test_timeout_is_audible(self):
        with patch("engine.copilot.shutil.which", return_value="codex"), \
             patch("engine.copilot.subprocess.run",
                   side_effect=subprocess.TimeoutExpired("codex", 300)):
            result = copilot.analyze_frames([self.frame()])
        self.assertFalse(result["ok"])
        self.assertIn("timed out", result["error"])


if __name__ == "__main__":
    unittest.main()
