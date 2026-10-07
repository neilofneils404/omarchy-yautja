# Yautja mode for Omarchy

Hunter tooling for [Omarchy](https://omarchy.org): thermal vision shaders, a
window cloak, a lock-on kill key, and a trophy wall on the bar.

Pairs with the [Yautja theme](https://github.com/neilofneils404/omarchy-yautja-theme),
but works under any theme.

Fan-made and unaffiliated with any film or game franchise.

![Yautja mode in thermal vision](preview.png)

## What you get

| Key | Does |
| --- | --- |
| `Super + Alt + V` | Cycle vision mode: thermal, electromagnetic, tracking, off |
| `Super + Alt + C` | Cloak or decloak the focused window |
| `Super + Alt + X` | Lock on to the focused window. Press again within 6 seconds to kill it |

- **Vision modes** are full-screen Hyprland shaders. The mode you leave on
  survives config reloads and logins until you switch it off.
  While active, they redraw the whole monitor on changed frames to prevent
  stale colors and cursor-triggered flicker after switching modes. This adds
  GPU work during updates; turning vision off restores your redraw setting.
- **Cloak** drops a window to about 7% opacity.
- **Hunt** sends `SIGKILL` to the window's process. Unsaved work in it is lost.
  The honour code spares anything using under 100 MB as unarmed; pass
  `--no-honour` to `yautja hunt` to override it.
- **Trophy wall** is a bar widget: one skull per kill of 1 GB or more since
  boot. Left click cycles vision, middle click turns it off, right click lists
  the kills.
- **Yautja menu** provides vision, cloak and trophy controls, plus Self-destruct:
  a 10 second countdown, then a real shutdown. Click the countdown notification,
  pick Self-destruct again, or choose **Abort self-destruct** to cancel it.
  **Stand down** cancels the countdown,
  releases the target, decloaks all windows, and turns vision off.
- **Thermal look**: while the Yautja theme is active, the focused window gets a
  heat glow and the rest dim and cool. Themes installed from git cannot carry
  Hyprland Lua, so this lives here.

## Install

Requires Omarchy 4 (Lua Hyprland config and the Quickshell bar). Everything
else it uses already ships with Omarchy:

- `jq`, `pgrep` and `ps` for state and process lookups
- `flock` (util-linux) to serialize commands and protect shared state
- Python 3 for comment-preserving installation and removal of config entries
- `hyprctl` for shaders, window tags and reloads
- `pw-play` (PipeWire) for the click sound; without it the plugin is silent

No sudo, no network access, no packages installed.

```bash
omarchy plugin add https://github.com/neilofneils404/omarchy-yautja.git --yes
~/.config/omarchy/plugins/neil.yautja/install.sh
```

`install.sh` links `yautja` into `~/.local/bin`, adds a managed loader to
`~/.config/hypr/hyprland.lua`, adds the menu block to
`~/.config/omarchy/extensions/omarchy-menu.jsonc`, and places the widget after
the workspaces. It backs up changed config files first and is safe to run
again. Re-running it updates the menu and keeps your existing widget placement.
It preserves JSONC comments and configuration symlinks, and refuses to overwrite
an unrelated `yautja` command.

To work from your own checkout, clone it anywhere and run `./install.sh`; it
symlinks the checkout into the plugin directory.

## Command

```
yautja vision [next|off|thermal|em|tracking|status]
yautja cloak [all-off]
yautja hunt [--no-honour]
yautja trophies [notify|clear|json]
yautja self-destruct [abort]
yautja reset
yautja --help
```

- `SOUND=0` in `~/.config/yautja/config` silences the clicks.
- `YAUTJA_DRY_RUN=1 yautja self-destruct` runs the countdown without shutting down.
- `yautja reset` is the command-line equivalent of **Stand down**.
- State and kill history live in `${XDG_STATE_HOME:-~/.local/state}/yautja`.
  The widget follows the same location. On a vertical bar it shows only the
  mode icon; hover for recent kills and click hints.

After updating this checkout or the installed plugin, run `./install.sh` again
to refresh the menu entries.

## Uninstall

```bash
~/.config/omarchy/plugins/neil.yautja/uninstall.sh
omarchy plugin remove neil.yautja
```

## Layout

```
manifest.json, BarWidget.qml   trophy wall bar widget
bin/yautja                     the command behind every key and menu row
shaders/                       thermal, em and tracking screen shaders
hypr/yautja.lua                keybinds, cloak and lock rules, thermal look
menu/omarchy-menu.jsonc        the Yautja submenu
sounds/clicks.ogg              synthesized click sound
scripts/manage-config.py      preserves user config while managing plugin blocks
tests/                        isolated runtime and installation regression tests
```

## Checks

```bash
python3 -m unittest discover -s tests -v
for script in bin/yautja install.sh uninstall.sh; do bash -n "$script"; done
luac -p hypr/yautja.lua
for shader in shaders/*.frag; do glslangValidator -S frag "$shader"; done
```

The regression tests use temporary homes and mock desktop commands. They never
kill applications or shut down the machine. `glslangValidator` is an optional
development tool, not a runtime dependency.

## Licence

MIT
