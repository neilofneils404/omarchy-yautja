"""Installer tests use a private temporary home and stub every desktop command."""

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("manage_config", REPO / "scripts/manage-config.py")
CONFIG = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONFIG)
FRAGMENT = (REPO / "menu/omarchy-menu.jsonc").read_text()


class MenuTests(unittest.TestCase):
    def test_realistic_jsonc_variants(self):
        for original in (
            '{}',
            '{\n // Empty custom menu\n}\n',
            '{"custom":{"label":"Personal"}}',
            '{"custom":{"label":"Personal"},}',
            '{"custom":{"action":"echo \\\"http://example.com/a,b}\\\""} // Keep comment\n}\n',
            '/* Header */ {"custom":{"label":"Personal"} /* suffix */\n  } // tail\n',
        ):
            with self.subTest(original=original):
                installed = CONFIG.menu_edit(original, FRAGMENT, True)
                menu, _ = CONFIG.jsonc(installed)
                self.assertIn("yautja", menu)
                self.assertEqual(CONFIG.menu_edit(installed, FRAGMENT, True), installed)
                removed = CONFIG.menu_edit(installed, FRAGMENT, False)
                self.assertEqual(CONFIG.jsonc(removed)[0], CONFIG.jsonc(original)[0])
                if "// Keep comment" in original:
                    self.assertIn("// Keep comment", removed)
                if "/* suffix */" in original:
                    self.assertIn("/* suffix */", removed)

    def test_unmanaged_entry_is_not_overwritten(self):
        with self.assertRaisesRegex(ValueError, "outside the managed block"):
            CONFIG.menu_edit('{"yautja":{"label":"Mine"}}', FRAGMENT, True)

    def test_invalid_json_and_markers_refused(self):
        for original in ('{ broken }', '{\n// >>> neil.yautja\n}', '[1]'):
            with self.subTest(original=original), self.assertRaises(ValueError):
                CONFIG.menu_edit(original, FRAGMENT, True)

    def test_only_exact_legacy_lua_is_removed(self):
        custom = '-- My neil.yautja settings\nlocal custom = "neil.yautja"\n'
        removed = CONFIG.lua_edit(custom + CONFIG.LEGACY_LUA, False)
        self.assertEqual(removed, custom)
        installed = CONFIG.lua_edit(custom, True)
        self.assertEqual(CONFIG.lua_edit(installed, True), installed)


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="yautja-install-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.checkout = self.root / "checkout"
        self.checkout.mkdir()
        for name in ("install.sh", "uninstall.sh"):
            shutil.copy2(REPO / name, self.checkout / name)
        for name in ("scripts", "menu"):
            shutil.copytree(REPO / name, self.checkout / name)
        self.fake_bin = self.root / "fake-bin"
        self.fake_bin.mkdir()
        self.calls = self.root / "calls.jsonl"
        stub = '''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
with open(os.environ["YAUTJA_TEST_CALLS"], "a") as stream:
    stream.write(json.dumps([Path(sys.argv[0]).name, *sys.argv[1:]]) + "\\n")
if sys.argv[1:] == ["plugin", "list", "--json"]:
    print('[{"id":"neil.yautja"}]')
if Path(sys.argv[0]).name == "hyprctl" and sys.argv[1:] == [os.environ.get("YAUTJA_TEST_HYPR_FAILURE")]:
    print("Synthetic Hyprland error")
    sys.exit(int(os.environ.get("YAUTJA_TEST_HYPR_EXIT", "1")))
if Path(sys.argv[0]).name == "yautja" and sys.argv[1:] == ["reset"]:
    sys.exit(int(os.environ.get("YAUTJA_TEST_RESET_EXIT", "0")))
'''
        for name in ("omarchy", "omarchy-shell", "hyprctl"):
            path = self.fake_bin / name
            path.write_text(stub)
            path.chmod(0o755)
        (self.checkout / "bin").mkdir()
        command = self.checkout / "bin/yautja"
        command.write_text(stub)
        command.chmod(0o755)
        self.env = dict(os.environ, HOME=str(self.home),
                        XDG_STATE_HOME=str(self.root / "state"),
                        XDG_RUNTIME_DIR=str(self.root / "runtime"),
                        PATH=str(self.fake_bin) + os.pathsep + os.environ["PATH"],
                        YAUTJA_TEST_CALLS=str(self.calls))
        self.hypr = self.home / ".config/hypr/hyprland.lua"
        self.hypr.parent.mkdir(parents=True)
        self.hypr.write_text('-- My neil.yautja settings\nlocal unrelated = true\n')
        self.menu = self.home / ".config/omarchy/extensions/omarchy-menu.jsonc"
        self.menu.parent.mkdir(parents=True)
        self.menu.write_text('{"custom":{"label":"Mine"}} // preserve me\n')

    def run_script(self, name, check=True):
        return subprocess.run(["bash", str(self.checkout / name)], env=self.env,
                              text=True, capture_output=True, check=check)

    def test_install_reinstall_and_uninstall(self):
        self.run_script("install.sh")
        installed_menu = self.menu.read_text()
        installed_lua = self.hypr.read_text()
        self.run_script("install.sh")
        self.assertEqual(self.menu.read_text(), installed_menu)
        self.assertEqual(self.hypr.read_text(), installed_lua)
        self.assertEqual(len(list(self.menu.parent.glob(self.menu.name + ".bak.*"))), 1)
        self.run_script("uninstall.sh")
        self.assertEqual(CONFIG.jsonc(self.menu.read_text())[0], {"custom": {"label": "Mine"}})
        self.assertIn("// preserve me", self.menu.read_text())
        self.assertIn("-- My neil.yautja settings", self.hypr.read_text())
        self.assertNotIn("loadfile", self.hypr.read_text())
        self.assertFalse((self.home / ".local/bin/yautja").is_symlink())
        backups = list(self.menu.parent.glob(self.menu.name + ".bak.*"))
        self.assertEqual(len(backups), 2)
        calls = [json.loads(line) for line in self.calls.read_text().splitlines()]
        self.assertEqual(calls.count(["omarchy", "plugin", "enable", "neil.yautja"]), 2)
        self.assertLess(calls.index(["yautja", "reset"]), calls.index(["omarchy", "plugin", "disable", "neil.yautja"]))

    def test_creates_missing_menu(self):
        self.menu.unlink()
        self.run_script("install.sh")
        self.assertIn("yautja", CONFIG.jsonc(self.menu.read_text())[0])

    def test_invalid_menu_fails_before_any_edits(self):
        self.menu.write_text("{invalid}")
        original_lua = self.hypr.read_text()
        result = self.run_script("install.sh", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.hypr.read_text(), original_lua)
        self.assertFalse((self.home / ".config/omarchy/plugins/neil.yautja").exists())
        self.assertFalse(self.calls.exists())

    def test_refuses_unrelated_executable(self):
        command = self.home / ".local/bin/yautja"
        command.parent.mkdir(parents=True)
        command.write_text("my existing program")
        result = self.run_script("install.sh", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(command.read_text(), "my existing program")

    def test_preserves_config_symlinks(self):
        target = self.root / "dotfiles-menu.jsonc"
        self.menu.rename(target)
        self.menu.symlink_to(target)
        self.run_script("install.sh")
        self.assertTrue(self.menu.is_symlink())
        self.assertIn("yautja", CONFIG.jsonc(target.read_text())[0])

    def test_uninstall_preserves_replaced_command_link(self):
        self.run_script("install.sh")
        command = self.home / ".local/bin/yautja"
        command.unlink()
        replacement = self.root / "other-command"
        replacement.write_text("#!/bin/sh\nexit 99\n")
        replacement.chmod(0o755)
        command.symlink_to(replacement)
        self.run_script("uninstall.sh")
        self.assertTrue(command.is_symlink())
        self.assertEqual(command.resolve(), replacement)

    def test_hyprland_reload_or_validation_failure_is_reported(self):
        for command, exit_code in (("reload", "1"), ("configerrors", "1"), ("configerrors", "0")):
            with self.subTest(command=command, exit_code=exit_code):
                self.env["YAUTJA_TEST_HYPR_FAILURE"] = command
                self.env["YAUTJA_TEST_HYPR_EXIT"] = exit_code
                result = self.run_script("install.sh", check=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Synthetic Hyprland error", result.stderr)
                self.assertIn("files remain installed", result.stderr)
                self.assertNotIn("Installed Yautja mode", result.stdout)

    def test_offline_uninstall_warns_and_removes_config(self):
        self.run_script("install.sh")
        self.env["YAUTJA_TEST_RESET_EXIT"] = "1"
        result = self.run_script("uninstall.sh")
        self.assertIn("could not be verified", result.stdout)
        self.assertIn("Continuing to remove configuration", result.stderr)
        self.assertNotIn("switched off", result.stdout)
        self.assertNotIn("loadfile", self.hypr.read_text())

    def test_uncancelled_countdown_preserves_abort_controls(self):
        self.run_script("install.sh")
        self.env["YAUTJA_TEST_RESET_EXIT"] = "1"
        runtime = Path(self.env["XDG_RUNTIME_DIR"]) / "yautja"
        runtime.mkdir(parents=True)
        (runtime / "destruct.token").write_text("still-armed")
        result = self.run_script("uninstall.sh", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Could not cancel", result.stderr)
        self.assertIn("yautja.self-destruct-abort", CONFIG.jsonc(self.menu.read_text())[0])
        self.assertTrue((self.home / ".local/bin/yautja").is_symlink())


if __name__ == "__main__":
    unittest.main()
