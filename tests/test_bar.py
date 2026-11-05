"""Hermetic bar lifecycle tests: no live shell, compositor, or user config access."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
MOCK = r'''#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys

state_path = Path(os.environ["MOCK_STATE"])
state = json.loads(state_path.read_text())
command = [Path(sys.argv[0]).name, *sys.argv[1:]]
with open(os.environ["MOCK_CALLS"], "a") as log:
    log.write(json.dumps(command) + "\n")
args = sys.argv[1:]
if command[0] == "omarchy" and args == ["bar", "--help"]:
    print("background [opaque|glassy|none|cycle]" if state["api"] == "modern" else "position | put | move", flush=True)
    if state.get("long_help"):
        for _ in range(32):
            os.write(1, b"Additional usage details.\n" * 1024)
    sys.exit(0)
if command[0] == "omarchy" and args[:2] == ["bar", "background"]:
    if state["api"] != "modern":
        sys.exit(1)
    if len(args) == 2:
        if state.get("fail_read"):
            sys.exit(1)
        bar = state["config"]["bar"]
        print(bar.get("background", "none" if bar.get("transparent") is True else "opaque"))
        sys.exit(0)
    if state.get("fail_write"):
        sys.exit(1)
    state["config"]["bar"]["background"] = args[2]
    state["config"]["bar"].pop("transparent", None)
    state_path.write_text(json.dumps(state))
    sys.exit(0)
if command[0] == "omarchy-shell" and args == ["shell", "listShellConfig"]:
    if state.get("fail_read"):
        sys.exit(1)
    config = state["config"]
    print(config if isinstance(config, str) else json.dumps(config))
    sys.exit(0)
if command[0] == "omarchy-shell" and args == ["shell", "toggleBarTransparency"]:
    if state.get("fail_write"):
        sys.exit(1)
    reply = state.get("reply", "ok")
    if reply == "ok":
        bar = state["config"]["bar"]
        bar["transparent"] = not bar["transparent"]
        state_path.write_text(json.dumps(state))
    print(reply)
    sys.exit(0)
sys.exit("Unexpected mocked command: " + repr(command))
'''


@unittest.skipUnless(shutil.which("jq") and shutil.which("bash"), "requires bash and jq")
class BarTests(unittest.TestCase):
    def setUp(self):
        # Keep even temporary writes inside the workspace.
        self.temp = tempfile.TemporaryDirectory(prefix=".test-bar-", dir=ROOT)
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.state_dir = self.home / "state" / "omarchy-glass"
        self.state_dir.mkdir(parents=True)
        self.mock_state = self.home / "mock.json"
        self.mock_calls = self.home / "calls.jsonl"
        mock_bin = self.home / "bin"
        mock_bin.mkdir()
        for name in ("omarchy", "omarchy-shell"):
            path = mock_bin / name
            path.write_text(MOCK)
            path.chmod(0o755)
        self.env = {
            **os.environ,
            "HOME": str(self.home),
            "XDG_CONFIG_HOME": str(self.home / "config"),
            "XDG_STATE_HOME": str(self.home / "state"),
            "XDG_DATA_HOME": str(self.home / "data"),
            "XDG_RUNTIME_DIR": str(self.home / "runtime"),
            "GLASS_DIR": str(ROOT),
            "GLASS_STATE": str(self.state_dir),
            "MOCK_STATE": str(self.mock_state),
            "MOCK_CALLS": str(self.mock_calls),
            "PATH": str(mock_bin) + os.pathsep + os.environ["PATH"],
        }
        self.configure("opaque")

    def configure(self, background=None, *, api="modern", config=None, **options):
        if config is None:
            config = {"bar": {"background": background}}
        self.mock_state.write_text(json.dumps({"api": api, "config": config, **options}))

    def run_glass(self, commands, *, success=True):
        result = subprocess.run(
            ["bash", "-c", 'source "$GLASS_DIR/bin/glass"; ' + commands],
            env=self.env, text=True, capture_output=True, timeout=10,
        )
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def bar(self):
        return json.loads(self.mock_state.read_text())["config"]["bar"]

    def calls(self):
        if not self.mock_calls.exists():
            return []
        return [json.loads(line) for line in self.mock_calls.read_text().splitlines()]

    def writes(self):
        return [call for call in self.calls() if
                (call[:3] == ["omarchy", "bar", "background"] and len(call) == 4)
                or call == ["omarchy-shell", "shell", "toggleBarTransparency"]]

    def saved(self):
        return self.state_dir / "bar-background-before"

    def test_opaque_round_trip(self):
        self.run_glass("bar_on")
        self.assertEqual(self.bar(), {"background": "none"})
        self.assertEqual(self.saved().read_text(), "opaque\n")
        self.run_glass("bar_off")
        self.assertEqual(self.bar(), {"background": "opaque"})
        self.assertFalse(self.saved().exists())

    def test_glassy_round_trip(self):
        self.configure("glassy")
        self.run_glass("bar_on && bar_off")
        self.assertEqual(self.bar(), {"background": "glassy"})
        self.assertEqual(self.writes(), [
            ["omarchy", "bar", "background", "none"],
            ["omarchy", "bar", "background", "glassy"],
        ])

    def test_clear_bar_is_unchanged(self):
        self.configure("none")
        self.run_glass("bar_on && bar_off")
        self.assertEqual(self.writes(), [])
        self.assertFalse(self.saved().exists())

    def test_repeated_start_and_stop_are_idempotent(self):
        self.run_glass("bar_on && bar_on && bar_off && bar_off")
        self.assertEqual(len(self.writes()), 2)
        self.assertEqual(self.bar(), {"background": "opaque"})

    def test_original_setting_survives_separate_processes(self):
        self.configure("glassy")
        self.run_glass("bar_on")
        self.run_glass("bar_on")
        self.assertEqual(self.saved().read_text(), "glassy\n")
        self.run_glass("bar_off")
        self.assertEqual(self.bar(), {"background": "glassy"})

    def test_manual_change_is_preserved_on_stop(self):
        self.run_glass("bar_on")
        self.configure("glassy")
        self.run_glass("bar_off")
        self.assertEqual(self.bar(), {"background": "glassy"})
        self.assertEqual(len(self.writes()), 1)
        self.assertFalse(self.saved().exists())

    def test_restart_recaptures_a_manual_choice(self):
        self.run_glass("bar_on")
        self.configure("glassy")
        self.run_glass("bar_on && bar_off")
        self.assertEqual(self.bar(), {"background": "glassy"})

    def test_modern_shell_with_legacy_config_never_toggles(self):
        self.configure(config={"bar": {"transparent": False}})
        self.run_glass("bar_on && bar_off")
        self.assertEqual(self.bar(), {"background": "opaque"})
        self.assertTrue(all(call[0] == "omarchy" for call in self.calls()))

    def test_long_help_output_does_not_trigger_pipefail_fallback(self):
        self.configure("glassy", long_help=True)
        self.run_glass("bar_on && bar_off")
        self.assertEqual(self.bar(), {"background": "glassy"})
        self.assertTrue(all(call[0] == "omarchy" for call in self.calls()))

    def test_modern_read_failure_does_not_fall_back(self):
        self.configure("opaque", fail_read=True)
        self.run_glass("bar_on", success=False)
        self.assertEqual(self.writes(), [])
        self.assertFalse(self.saved().exists())
        self.assertTrue(all(call[0] == "omarchy" for call in self.calls()))

    def test_failed_start_write_keeps_recovery_state(self):
        self.configure("glassy", fail_write=True)
        self.run_glass("bar_on", success=False)
        self.assertEqual(self.bar(), {"background": "glassy"})
        self.assertEqual(self.saved().read_text(), "glassy\n")
        self.configure("glassy")
        self.run_glass("bar_off")
        self.assertFalse(self.saved().exists())
        self.assertEqual(len(self.writes()), 1)

    def test_failed_restore_can_be_retried(self):
        self.run_glass("bar_on")
        self.configure("none", fail_write=True)
        self.run_glass("bar_off", success=False)
        self.assertEqual(self.saved().read_text(), "opaque\n")
        self.configure("none")
        self.run_glass("bar_off")
        self.assertEqual(self.bar(), {"background": "opaque"})
        self.assertFalse(self.saved().exists())

    def test_failed_restore_read_keeps_recovery_state(self):
        self.run_glass("bar_on")
        self.configure("none", fail_read=True)
        self.run_glass("bar_off", success=False)
        self.assertTrue(self.saved().exists())
        self.assertEqual(len(self.writes()), 1)

    def test_unknown_modern_background_fails_closed(self):
        self.configure("rainbow")
        self.run_glass("bar_on", success=False)
        self.assertEqual(self.writes(), [])

    def test_corrupt_saved_background_is_not_applied(self):
        self.configure("none")
        self.saved().write_text("cycle\n")
        self.run_glass("bar_off", success=False)
        self.assertEqual(self.writes(), [])
        self.assertTrue(self.saved().exists())

    def test_old_marker_is_migrated_and_restored(self):
        self.configure("none")
        marker = self.state_dir / "bar-made-transparent"
        marker.touch()
        self.run_glass("bar_on")
        self.assertEqual(self.saved().read_text(), "opaque\n")
        self.run_glass("bar_off")
        self.assertEqual(self.bar(), {"background": "opaque"})
        self.assertFalse(marker.exists())

    def test_old_marker_cleanup_preserves_manual_change(self):
        self.configure("glassy")
        marker = self.state_dir / "bar-made-transparent"
        marker.touch()
        self.run_glass("bar_off")
        self.assertEqual(self.writes(), [])
        self.assertFalse(marker.exists())

    def test_new_saved_setting_takes_precedence_over_old_marker(self):
        self.configure("none")
        self.saved().write_text("glassy\n")
        (self.state_dir / "bar-made-transparent").touch()
        self.run_glass("bar_off")
        self.assertEqual(self.bar(), {"background": "glassy"})

    def test_legacy_opaque_round_trip(self):
        self.configure(api="legacy", config={"bar": {"transparent": False}})
        self.run_glass("bar_on && bar_on && bar_off")
        self.assertEqual(self.bar(), {"transparent": False})
        self.assertEqual(self.writes(), [
            ["omarchy-shell", "shell", "toggleBarTransparency"],
            ["omarchy-shell", "shell", "toggleBarTransparency"],
        ])

    def test_legacy_clear_bar_is_unchanged(self):
        self.configure(api="legacy", config={"bar": {"transparent": True}})
        self.run_glass("bar_on && bar_off")
        self.assertEqual(self.writes(), [])

    def test_legacy_toggle_error_reply_is_failure(self):
        self.configure(api="legacy", config={"bar": {"transparent": False}}, reply="no-bar")
        self.run_glass("bar_on", success=False)
        self.assertEqual(self.bar(), {"transparent": False})
        self.assertTrue(self.saved().exists())

    def test_legacy_failed_restore_keeps_marker(self):
        self.configure(api="legacy", config={"bar": {"transparent": True}}, fail_write=True)
        (self.state_dir / "bar-made-transparent").touch()
        self.run_glass("bar_off", success=False)
        self.assertTrue(self.saved().exists())
        self.assertTrue((self.state_dir / "bar-made-transparent").exists())

    def test_missing_modern_cli_does_not_toggle_new_shell(self):
        self.configure("glassy", api="legacy")
        self.run_glass("bar_on", success=False)
        self.assertEqual(self.writes(), [])

    def test_invalid_legacy_config_fails_closed(self):
        for config in ("not json", {}, {"bar": {}}, {"bar": {"transparent": "false"}}):
            with self.subTest(config=config):
                self.configure(api="legacy", config=config)
                self.run_glass("bar_on", success=False)
        self.assertEqual(self.writes(), [])

    # Stop must continue cleanup after a bar error, but report the error instead
    # of replacing it with a misleading success. Everything else is stubbed.
    STOP_STUBS = r'''
        unload() { :; }
        outlines_off() { :; }
        terminals_off() { :; }
        lock_off() { :; }
        hyprctl() { printf '%s\n' "$*" >> "$HOME/cleanup-calls"; }
    '''

    def test_stop_reports_failed_restore_and_finishes_cleanup(self):
        self.run_glass("bar_on")
        self.configure("none", fail_write=True)
        self.run_glass(self.STOP_STUBS + "stop", success=False)
        self.assertEqual((self.state_dir / "status").read_text(), "bar-restore\n")
        self.assertTrue(self.saved().exists())
        self.assertEqual((self.home / "cleanup-calls").read_text(), "reload\n")

    def test_stop_reports_success_after_restoration(self):
        self.run_glass("bar_on")
        self.run_glass(self.STOP_STUBS + "stop")
        self.assertEqual((self.state_dir / "status").read_text(), "off\n")
        self.assertEqual(self.bar(), {"background": "opaque"})

    def test_start_rolls_back_on_bar_failure(self):
        self.configure("opaque", fail_write=True)
        (self.state_dir / "settings.json").write_text('{"on":true}')
        engine_dir = self.home / "engine-fixture" / "bin"
        engine_dir.mkdir(parents=True)
        ensure = engine_dir / "glass-engine"
        ensure.write_text("#!/bin/bash\nprintf 'ok /fake/engine.so compat-test\\n'\n")
        ensure.chmod(0o755)
        stubs = self.STOP_STUBS + r'''
            DIR="$HOME/engine-fixture"
            gpu_tier() { echo full; }
            crashed_with_glass() { return 1; }
            loaded_version() { echo compat-test; }
            pacman() { echo 'hyprland 0.56.2-4'; }
            apply() { :; }
            hyprctl() {
                case "$*" in
                    'version -j') echo '{"version":"0.56.2"}' ;;
                    '-j hyprglass status') echo '{"shaders":"ready","renderer":"hardware"}' ;;
                    reload) echo reload >> "$HOME/cleanup-calls" ;;
                    *) return 1 ;;
                esac
            }
            start
        '''
        self.run_glass(stubs, success=False)
        self.assertEqual((self.state_dir / "status").read_text(), "bar\n")
        self.assertEqual((self.home / "cleanup-calls").read_text(), "reload\n")
        self.assertEqual(self.bar(), {"background": "opaque"})
        self.assertFalse(self.saved().exists())

    def test_sourcing_does_not_dispatch_or_create_cleanup_mirror(self):
        self.run_glass(":")
        self.assertEqual(self.calls(), [])
        self.assertFalse((self.home / "runtime").exists())


if __name__ == "__main__":
    unittest.main()
