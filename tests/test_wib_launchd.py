from __future__ import annotations

import importlib.machinery
import importlib.util
import plistlib
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "wib"


def load_script():
    loader = importlib.machinery.SourceFileLoader("wib_launchd_script", str(SCRIPT))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[loader.name] = module
    loader.exec_module(module)
    return module


class WibLaunchdTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_script()

    def test_load_settings_and_build_plist(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "WorkInBox"
            python = project / ".venv" / "bin" / "python"
            app_config = project / "config.yaml"
            log_dir = project / "logs"
            python.parent.mkdir(parents=True)
            python.touch()
            app_config.touch()
            config = root / "maintenance.conf"
            config.write_text(
                "[workinbox]\n"
                f"project_dir = {project}\n"
                f"python = {python}\n"
                f"config = {app_config}\n"
                f"log_dir = {log_dir}\n"
                "host = 127.0.0.1\n"
                "port = 8123\n",
                encoding="utf-8",
            )

            settings = self.module.load_settings(config)
            plist = self.module.build_plist(settings)

            self.assertEqual(plist["Label"], "jp.workinbox.web")
            self.assertEqual(plist["WorkingDirectory"], str(project.resolve()))
            self.assertEqual(plist["ProgramArguments"][-1], "8123")
            self.assertEqual(
                plist["StandardOutPath"], str(log_dir.resolve() / "web-launchd.log")
            )
            plistlib.dumps(plist)

    def test_missing_config_has_actionable_message(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            missing = Path(temp_dir) / "missing.conf"
            with self.assertRaisesRegex(ValueError, "maintenance.conf.example"):
                self.module.load_settings(missing)

    def test_invalid_path_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = root / "maintenance.conf"
            config.write_text(
                "[workinbox]\n"
                f"project_dir = {root / 'missing'}\n"
                f"python = {root / 'missing-python'}\n"
                f"config = {root / 'missing-config'}\n"
                f"log_dir = {root / 'logs'}\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "存在しません"):
                self.module.load_settings(config)


if __name__ == "__main__":
    unittest.main()
