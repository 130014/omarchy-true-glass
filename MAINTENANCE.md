# Compatibility fork maintenance

## Scope and provenance

This fork maintains the Omarchy integration originally written by Eddie175. The
vendored rendering engine is based on Jeremy Trufier's hyprglass. Original MIT,
BSD, and third-party notices remain in place. This is not an official Omarchy or
Hyprland project.

Version 1.0.4 corrects bar-background handling. Version 1.0.5 also fixes the
rendered bar bounds for Omarchy's newer full-screen transparent bar surfaces:
only the layer-shell reserved strip receives glass, not the whole desktop.

## Compatibility

- Development version: **1.0.5**, based on upstream **1.0.3 / dda3708**.
- Target system inspected: **Omarchy 4.5.0-2**, **Hyprland 0.56.2-4**
  (running compositor 0.56.2), **Quickshell 0.3.2.r7.g2b4501a-1**.
- Current Omarchy: use the explicit `omarchy bar background none` setter, not
  `toggleBarTransparency`, which now cycles `none`, `glassy`, and `opaque`.
  A read-only smoke check against the installed CLI correctly selected the new
  API and read the current `none` background without changing it.
- Legacy shells: use the old toggle only if the CLI does not advertise the
  background API and IPC confirms a boolean `bar.transparent`, with no
  `bar.background` field. Unknown or unreadable configurations fail closed.
- The engine remains restricted to **Hyprland 0.56.x**. A compatible version
  number alone is not a guarantee of plugin ABI compatibility.
- The patched engine compiled and loaded successfully against the installed
  Hyprland 0.56.2 headers on an NVIDIA RTX 3060 Ti. One
  `HyprlandAPI::addConfigKeyword` deprecation warning remains.
- Version 1.0.4 passed 19 live lifecycle checks: enable/disable, opaque/glassy/none
  background restoration, preservation of a manual background change, and a shell
  restart. The settings menu was inspected visually and config errors were empty.
- Version 1.0.5 passed live pixel checks on the static wallpaper margin outside
  windows and the bar. It exactly matched the Glass-disabled baseline with Dark
  glass alone, Clear terminals alone, and both enabled. The old engine reduced
  that margin's mean red channel from about 239 to 85 with Dark glass enabled.
- Live tests are limited to this system. Crash recovery, other GPUs, floating-bar
  plugins, and all lock-screen paths are not comprehensively validated. Geometry
  regression tests cover all four edges and scaled dimensions, not live rotated
  monitor behavior.

## Bar restoration

Glass records the previous `opaque` or `glassy` background in
`$XDG_STATE_HOME/omarchy-glass/bar-background-before` (normally
`~/.local/state/omarchy-glass/`). It records this before requesting a clear bar,
retains it across shell restarts, and removes it after successful cleanup.

A bar that was already clear is left alone. On shutdown, a non-clear background
chosen by the user is preserved. Failed reads or writes retain recovery state
for the next cleanup attempt. The old `bar-made-transparent` marker is understood
as a saved `opaque` background, matching upstream's two-state assumption; an
existing new-format saved value takes precedence.

If setting the bar fails during startup, Glass rolls back through its stop path
and reports a bar-background error instead of reporting success. Shutdown still
finishes the remaining cleanup if bar restoration fails, but reports that failure
and retains the saved background rather than silently reporting `off`.

## Full-screen bar surfaces

`shape.exclusive = true` opts a layer shape into native layer-shell clipping.
The engine uses each surface's positive exclusive zone and its anchored edge to
find the real strip in logical coordinates before applying the configured
insets. Framebuffer/sample coordinates remain full-sized; only the glass bounds
are restricted. Bar attachment and underline sampling use the reserved strip.
Unknown zones/edges take the ordinary surface-rendering path instead of falling
back to full-screen glass. Legacy strip-sized surfaces retain their bounds.

## Migrating from upstream

The plugin ID remains `io.github.eddie175.true-glass`; both repositories must not
be enabled as separate plugins. Settings and engine paths also remain shared.

1. Turn off upstream True Glass with its menu switch.
2. Back up the plugin's settings and any customized terminal/shell configuration.
   Removal deletes the plugin's settings and engine cache.
3. Remove upstream with `omarchy plugin remove io.github.eddie175.true-glass`.
4. Install this fork with the command in the README. Leave Glass off until ready
   for the live checks below, then restore any desired settings deliberately.

These are manual instructions, not actions performed by the automated tests.

## Automated checks

Requires Bash, Python 3, jq, a C++23 compiler (`c++`), and Lua's `luac`:

```bash
python3 -m unittest discover -s tests -v
bash -n bin/glass bin/glass-engine
luac -p glass.lua
# On Omarchy, also validate against the installed manifest schema:
omarchy plugin validate .
git diff --check
```

The suite has 29 tests: 28 shell lifecycle tests plus a hermetic C++ geometry
harness with fullscreen/legacy strip, edge, invalid-zone, and scaling cases.
The shell tests cover restoration, write/read failures, legacy state, and
help-stream SIGPIPE handling under `pipefail`. They source `bin/glass` without
dispatching a command or installing its exit trap. Mock `omarchy` and `omarchy-shell` executables stand in for the desktop;
all fixtures and state live in temporary directories inside this checkout.

Build checks should copy `engine/` into `.build/engine/` and run `make` there
against installed Hyprland headers, without loading the resulting shared object.
Do not use `bin/glass-engine` for an isolated build check: it writes the real
per-user engine cache.

## Live validation before a release

Use a disposable desktop session where possible. Loading a compositor plugin can
crash the session; save work and have a TTY recovery path before proceeding.

- Start from each background: opaque, glassy, and none. Enable Glass and confirm
  the bar stays clear; disable it and confirm the original background returns.
- Restart the shell while Glass is active; confirm the original background is
  still restored on disable.
- Change the background yourself while Glass is active; disable Glass and
  confirm that your new choice is not overwritten.
- Switch themes, open/switch menus, and inspect accent-colored widgets,
  notifications, OSD, and floating-bar bounds.
- Exercise enable, disable, removal, and shader/build failure recovery.
- Check terminals and lock-screen restoration separately before claiming those
  integration paths are supported on a new Omarchy release.
- Check `hyprctl configerrors` and the shell logs after each lifecycle test.

## Follow-up work

- [Upstream #1](https://github.com/Eddie175/omarchy-true-glass/issues/1): accent
  color keying erases unrelated bar-widget pixels. Not fixed by this patch.
- [Upstream #3](https://github.com/Eddie175/omarchy-true-glass/pull/3): floating-bar
  geometry fix. Review and test independently rather than silently bundling it.
- [Upstream #2](https://github.com/Eddie175/omarchy-true-glass/issues/2): collaborate
  with hyprglass on moving engine improvements upstream and eventually replacing
  the embedded fork. Do not swap engines without proving feature/protocol parity.
- Add a reproducible, version-pinned engine build matrix and live GPU coverage
  before expanding supported Hyprland versions.

Keep compatibility fixes small, regression-tested, and suitable for contributing
back to the original project. Do not remove attribution or imply the upstream
project has been formally abandoned.
