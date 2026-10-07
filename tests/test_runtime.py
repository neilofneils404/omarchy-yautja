#!/usr/bin/env python3
"""Hermetic CLI regressions: compositor, notifications, signals and shutdown are mocked."""
import concurrent.futures
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest

REPO = Path(__file__).resolve().parents[1]
MOCK = r'''#!/usr/bin/env python3
import json, os, pathlib, sys, time
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
with open(os.environ["TEST_LOG"], "a") as log:
    log.write(json.dumps([name, *args]) + "\n")
if name == "hyprctl":
    if args[0] == "activewindow":
        print(pathlib.Path(os.environ["TEST_WINDOW"]).read_text())
    elif args[0] == "clients":
        print(pathlib.Path(os.environ["TEST_CLIENTS"]).read_text())
    elif os.environ.get("MOCK_HYPR_FAIL"):
        print("Lua runtime error: rejected")
        sys.exit(1 if os.environ["MOCK_HYPR_FAIL"] == "exit" else 0)
    else:
        print("ok")
elif name == "omarchy-notification-send":
    if os.environ.get("MOCK_NOTIFY_FAIL") or pathlib.Path(os.environ["TEST_NOTIFY_FAIL_FILE"]).exists():
        sys.exit(1)
    if "-p" in args:
        print(17)
elif name == "ps":
    print(os.environ.get("MOCK_RSS", "2048"))
elif name == "pgrep":
    sys.exit(1)
elif name == "sleep":
    time.sleep(float(args[0]) * float(os.environ.get("MOCK_SLEEP_FACTOR", "1")))
elif name == "jq":
    os.execv("/usr/bin/jq", ["jq", *args])
'''


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="yautja-runtime-")
        self.base = Path(self.temp.name)
        self.checkout = self.base / 'checkout with \'quotes" and \\slashes'
        (self.checkout / "bin").mkdir(parents=True)
        shutil.copy2(REPO / "bin/yautja", self.checkout / "bin/yautja")
        shutil.copytree(REPO / "shaders", self.checkout / "shaders")
        self.home = self.base / "home"
        self.config = self.base / "config"
        self.state = self.base / "state"
        self.runtime = self.base / "runtime"
        self.mockbin = self.base / "mockbin"
        for path in [self.home, self.config / "yautja", self.state, self.runtime, self.mockbin]:
            path.mkdir(parents=True)
        (self.config / "yautja/config").write_text("SOUND=0\nLOCK_SECONDS=2\n")
        for command in ["hyprctl", "omarchy-notification-send", "omarchy", "pw-play", "ps", "pgrep", "sleep", "jq"]:
            script = self.mockbin / command
            script.write_text(MOCK)
            script.chmod(0o755)
        self.log = self.base / "commands.jsonl"
        self.kill_log = self.base / "signals.log"
        self.window_file = self.base / "window.json"
        self.clients_file = self.base / "clients.json"
        self.set_window("0xa")
        self.clients_file.write_text("[]")
        bash_env = self.base / "bash-env"
        # Override the Bash builtin itself; even a regression cannot signal the
        # test runner or any desktop process. The shutdown executable is mocked.
        bash_env.write_text('kill() { printf "%s\\n" "$*" >>"$TEST_KILL_LOG"; }\n')
        self.env = os.environ | {
            "HOME": str(self.home), "XDG_CONFIG_HOME": str(self.config),
            "XDG_STATE_HOME": str(self.state), "XDG_RUNTIME_DIR": str(self.runtime),
            "PATH": str(self.mockbin) + ":/usr/bin:/bin", "BASH_ENV": str(bash_env),
            "TEST_LOG": str(self.log), "TEST_KILL_LOG": str(self.kill_log),
            "TEST_WINDOW": str(self.window_file), "TEST_CLIENTS": str(self.clients_file),
            "TEST_NOTIFY_FAIL_FILE": str(self.base / "notifications-unavailable"),
        }
        self.env.pop("YAUTJA_DRY_RUN", None)
        self.state_file = self.state / "yautja/state.json"
        self.run = self.runtime / "yautja"

    def tearDown(self):
        self.cli("reset", check=False)
        # Workers use cooperative cancellation. Retain their isolated files
        # until the longest possible sleep has completed.
        if self.log.exists() and any(row[0] == "sleep" for row in self.commands()):
            time.sleep(2.1)
        self.temp.cleanup()

    def cli(self, *args, check=True, extra=None):
        result = subprocess.run(
            ["/usr/bin/bash", str(self.checkout / "bin/yautja"), *args],
            env=self.env | (extra or {}), text=True, capture_output=True, timeout=8,
        )
        if check and result.returncode:
            self.fail(f"{args}: {result.returncode}\n{result.stdout}\n{result.stderr}")
        return result

    def set_window(self, address):
        self.window_file.write_text(json.dumps({
            "address": address, "pid": os.getpid(), "class": "test-app", "title": "Mock window", "tags": [],
        }))

    def commands(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def shutdowns(self):
        return [row for row in self.commands() if row == ["omarchy", "system", "shutdown"]]

    def wait_for(self, predicate, timeout=4):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(0.02)
        self.fail("Timed out waiting for isolated worker")

    def test_help_and_invalid_actions_have_no_side_effects(self):
        self.assertIn("yautja reset", self.cli("--help").stdout)
        for args in [("self-destruct", "abortt"), ("hunt", "typo"), ("vision", "../thermal"), ("reset", "extra")]:
            self.assertEqual(self.cli(*args, check=False).returncode, 2)
        self.assertFalse(self.run.exists())
        self.assertEqual(self.commands(), [])

    def test_vision_failure_does_not_persist(self):
        for failure in ["exit", "reply"]:
            self.assertNotEqual(self.cli("vision", "thermal", check=False, extra={"MOCK_HYPR_FAIL": failure}).returncode, 0)
            self.assertFalse(self.state_file.exists())
            self.assertFalse((self.state / "omarchy/toggles/hypr/yautja-vision.lua").exists())

    def test_vision_paths_are_lua_escaped(self):
        self.cli("vision", "thermal")
        self.assertEqual(json.loads(self.state_file.read_text())["vision"], "thermal")
        persisted = (self.state / "omarchy/toggles/hypr/yautja-vision.lua").read_text()
        self.assertIn('\\"', persisted)
        self.assertIn('\\\\slashes', persisted)
        # Execute only the generated Lua configuration against an in-memory
        # stub; the literal must round-trip to the real shader path.
        lua = shutil.which("lua")
        if lua:
            result = subprocess.run([lua, "-"], input="hl = { get_config = function() return 2 end, config = function(c) print(c.decoration.screen_shader) end }\n" + persisted,
                                    text=True, capture_output=True, check=True)
            self.assertEqual(result.stdout.rstrip("\n"), str(self.checkout / "shaders/thermal.frag"))
        self.assertEqual(self.cli("vision", "status").stdout.strip(), "thermal")

    def test_vision_restores_redraw_setting_after_cycles_and_reload(self):
        lua = shutil.which("lua")
        if not lua:
            self.skipTest("Lua interpreter is required")
        scripts = []
        for mode in ["thermal", "em", "tracking", "off"]:
            self.cli("vision", mode)
            scripts.append([c[2] for c in self.commands() if c[:2] == ["hyprctl", "eval"]][-1])
        fixture = '''
local damage = INITIAL
hl = {
  get_config = function(key) assert(key == "debug.damage_tracking"); return damage end,
  config = function(c) if c.debug then damage = c.debug.damage_tracking end end
}
'''
        for initial in [0, 1, 2]:
            with self.subTest(initial=initial):
                program = fixture.replace("INITIAL", str(initial))
                # Off without prior activation must leave the setting alone.
                program += scripts[3] + f"\nassert(damage == {initial})\n"
                for script in scripts[:3]:
                    program += script + f"\nassert(damage == 1); assert(_G.yautja_vision_damage_tracking == {initial})\n"
                program += scripts[3] + f"\nassert(damage == {initial}); assert(_G.yautja_vision_damage_tracking == nil)\n"
                # A persisted toggle loaded into a fresh config must capture
                # that config's value, not the value from the prior session.
                program += "damage = 2\n" + scripts[1] + "\n" + scripts[3] + "\nassert(damage == 2)\n"
                # Respect a deliberate setting change made while vision runs.
                program += scripts[1] + "\ndamage = 0\n" + scripts[3] + "\nassert(damage == 0)\n"
                subprocess.run([lua, "-"], input=program, text=True, capture_output=True, check=True)

    def test_parallel_vision_cycles_preserve_state(self):
        self.cli("vision", "off")
        content = json.loads(self.state_file.read_text())
        content["trophies"] = [{"boot": "fixture", "worthy": True, "class": "saved", "rss_kb": 1}]
        self.state_file.write_text(json.dumps(content))
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda _: self.cli("vision", "next"), range(8)))
        after = json.loads(self.state_file.read_text())
        self.assertEqual(after, content)
        self.assertEqual(self.state_file.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.run.stat().st_mode & 0o777, 0o700)

    def test_hunt_requires_two_presses_and_spares_small_apps(self):
        self.cli("hunt")
        self.assertTrue((self.run / "lock").exists())
        self.assertFalse(self.kill_log.exists())
        self.cli("hunt")
        self.assertFalse((self.run / "lock").exists())
        self.assertFalse(self.kill_log.exists())
        self.assertTrue(any("No sport" in row for row in self.commands()))

    def test_hunt_records_only_after_mocked_signal(self):
        self.cli("hunt", extra={"MOCK_RSS": "2097152"})
        self.cli("hunt", extra={"MOCK_RSS": "2097152"})
        self.assertEqual(self.kill_log.read_text().strip(), f"-KILL {os.getpid()}")
        trophies = json.loads(self.cli("trophies", "json").stdout)
        self.assertEqual(len(trophies), 1)
        self.assertTrue(trophies[0]["worthy"])

    def test_hunt_keeps_private_titles_out_of_process_arguments(self):
        title = 'PRIVATE-DOCUMENT-731: "budget" \\ drafts\t秘密\nsecond line'
        window = json.loads(self.window_file.read_text())
        window["title"] = title
        self.window_file.write_text(json.dumps(window))
        self.cli("vision", "thermal")
        for rss in ("2097152", "2048"):
            self.cli("hunt", "--no-honour", extra={"MOCK_RSS": rss})
            self.cli("hunt", "--no-honour", extra={"MOCK_RSS": rss})

        for command in self.commands():
            self.assertNotIn("PRIVATE-DOCUMENT-731", " ".join(command), command)
        state = json.loads(self.state_file.read_text())
        self.assertEqual(state["vision"], "thermal")
        trophies = state["trophies"]
        self.assertEqual([entry["title"] for entry in trophies], [title, title])
        self.assertEqual([entry["worthy"] for entry in trophies], [True, False])
        history = self.state / "yautja/kills.jsonl"
        self.assertEqual([json.loads(line) for line in history.read_text().splitlines()], trophies)
        for path in (self.state_file, history):
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_old_expiry_cannot_remove_new_lock_on_same_window(self):
        self.cli("hunt")
        old_token = (self.run / "lock").read_text().split()[-1]
        time.sleep(0.8)
        self.set_window("0xb")
        self.cli("hunt")
        self.set_window("0xa")
        self.cli("hunt")
        new_lock = (self.run / "lock").read_text()
        self.assertNotEqual(new_lock.split()[-1], old_token)
        time.sleep(1.2)
        self.assertEqual((self.run / "lock").read_text(), new_lock)

    def test_countdown_requires_visible_notification(self):
        result = self.cli("self-destruct", check=False, extra={"MOCK_NOTIFY_FAIL": "1", "MOCK_SLEEP_FACTOR": "0.03"})
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.run / "destruct.token").exists())
        self.assertFalse(self.shutdowns())

    def test_countdown_cancels_if_notifications_disappear(self):
        self.cli("self-destruct", extra={"MOCK_SLEEP_FACTOR": "0.1"})
        Path(self.env["TEST_NOTIFY_FAIL_FILE"]).touch()
        self.wait_for(lambda: not (self.run / "destruct.token").exists())
        self.assertFalse(self.shutdowns())

    def test_countdown_abort_never_signals_stored_pid(self):
        self.run.mkdir()
        (self.run / "destruct.pid").write_text(str(os.getpid()))
        self.cli("self-destruct", "abort")
        self.assertFalse(self.kill_log.exists())
        self.cli("self-destruct", extra={"MOCK_SLEEP_FACTOR": "0.05"})
        self.cli("self-destruct", "abort")
        time.sleep(0.9)
        self.assertFalse(self.shutdowns())
        self.assertFalse(self.kill_log.exists())

    def test_parallel_countdown_toggles_cancel_both(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda _: self.cli("self-destruct", extra={"MOCK_SLEEP_FACTOR": "0.05"}), range(2)))
        time.sleep(1)
        self.assertFalse((self.run / "destruct.token").exists())
        self.assertFalse(self.shutdowns())

    def test_restarted_countdown_has_only_one_owner(self):
        self.cli("self-destruct", extra={"MOCK_SLEEP_FACTOR": "0.05"})
        first_token = (self.run / "destruct.token").read_text()
        self.cli("self-destruct", "abort")
        self.cli("self-destruct", extra={"MOCK_SLEEP_FACTOR": "0.05"})
        self.assertNotEqual((self.run / "destruct.token").read_text(), first_token)
        self.wait_for(lambda: len(self.shutdowns()) == 1)
        time.sleep(0.3)
        self.assertEqual(len(self.shutdowns()), 1)
        notices = [row for row in self.commands() if row[0] == "omarchy-notification-send" and "--exec" in row]
        self.assertTrue(notices)
        self.assertEqual(notices[0][-4:], ["--exec", str(self.checkout / "bin/yautja"), "self-destruct", "abort"])

    def test_countdown_dry_run_and_completion(self):
        self.cli("self-destruct", extra={"YAUTJA_DRY_RUN": "1", "MOCK_SLEEP_FACTOR": "0.02"})
        self.wait_for(lambda: any("Boom" in row for row in self.commands()))
        self.assertFalse(self.shutdowns())
        self.assertTrue(any("Boom" in row for row in self.commands()))
        self.cli("self-destruct", extra={"MOCK_SLEEP_FACTOR": "0.02"})
        self.wait_for(lambda: len(self.shutdowns()) == 1)

    def test_reset_cancels_and_restores_desktop(self):
        self.cli("vision", "thermal")
        self.cli("hunt")
        self.cli("self-destruct", extra={"MOCK_SLEEP_FACTOR": "0.05"})
        self.clients_file.write_text(json.dumps([{"address": "0xa", "tags": ["yautja-cloak", "yautja-lock"]}]))
        self.cli("reset")
        time.sleep(0.9)
        self.assertFalse((self.run / "lock").exists())
        self.assertFalse((self.run / "destruct.token").exists())
        self.assertEqual(json.loads(self.state_file.read_text())["vision"], "off")
        self.assertFalse((self.state / "omarchy/toggles/hypr/yautja-vision.lua").exists())
        self.assertFalse(self.shutdowns())
        dispatches = "\n".join(row[-1] for row in self.commands() if row[:2] == ["hyprctl", "dispatch"])
        self.assertIn("-yautja-lock", dispatches)
        self.assertIn("-yautja-cloak", dispatches)


if __name__ == "__main__":
    unittest.main(verbosity=2)
