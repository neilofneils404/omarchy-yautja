#!/usr/bin/env bash
set -euo pipefail

project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
plugin_id="neil.yautja"
plugin_dir="$HOME/.config/omarchy/plugins/$plugin_id"
shell_config="$HOME/.config/omarchy/shell.json"
hypr_config="$HOME/.config/hypr/hyprland.lua"
menu_config="$HOME/.config/omarchy/extensions/omarchy-menu.jsonc"
bin_link="$HOME/.local/bin/yautja"

# `omarchy plugin add` clones the repo straight into the plugin directory. Run
# from any other checkout, link that checkout in instead.
mkdir -p "$(dirname "$plugin_dir")"
if [[ -e $plugin_dir || -L $plugin_dir ]]; then
  if [[ $(readlink -f "$plugin_dir") != "$(readlink -f "$project_dir")" ]]; then
    echo "An existing $plugin_id installation is present at $plugin_dir. Move it before installing this checkout." >&2
    exit 1
  fi
else
  ln -s "$project_dir" "$plugin_dir"
fi

mkdir -p "$(dirname "$bin_link")"
ln -sfn "$plugin_dir/bin/yautja" "$bin_link"

# Hyprland: keybinds, cloak and lock rules, thermal look. loadfile keeps the
# config valid if the plugin is later removed without running uninstall.sh.
if [[ -f $hypr_config ]] && ! grep -q "$plugin_id" "$hypr_config"; then
  cp "$hypr_config" "$hypr_config.bak.$(date +%s)"
  cat >>"$hypr_config" <<'LUA'

-- Yautja mode (neil.yautja). Remove with the plugin's uninstall.sh.
local yautja_mode = loadfile(os.getenv("HOME") .. "/.config/omarchy/plugins/neil.yautja/hypr/yautja.lua") -- neil.yautja
if yautja_mode then yautja_mode() end -- neil.yautja
LUA
fi

# Omarchy menu: a Yautja submenu, inserted before the closing brace.
if [[ -f $menu_config ]] && ! grep -q ">>> $plugin_id" "$menu_config"; then
  cp "$menu_config" "$menu_config.bak.$(date +%s)"
  last_brace=$(grep -n '^}' "$menu_config" | tail -n1 | cut -d: -f1)
  if [[ -n $last_brace ]]; then
    {
      head -n $((last_brace - 1)) "$menu_config"
      cat "$project_dir/menu/omarchy-menu.jsonc"
      tail -n +"$last_brace" "$menu_config"
    } >"$menu_config.tmp"
    mv "$menu_config.tmp" "$menu_config"
  else
    echo "Could not find the closing brace in $menu_config; skipped the menu entries." >&2
  fi
fi

omarchy-shell -q shell rescanPlugins
# The shell owns shell.json: let it place the widget, and leave an existing
# placement alone.
if [[ -f $shell_config ]] && jq -e --arg id "$plugin_id" 'any(.bar.layout[]?[]?; .id? == $id)' "$shell_config" >/dev/null; then
  echo "$plugin_id is already in your bar; left its placement alone."
else
  omarchy plugin enable "$plugin_id" --after omarchy.workspaces
fi

hyprctl reload >/dev/null 2>&1 || true
errors=$(hyprctl configerrors 2>/dev/null || true)
if [[ -n $errors ]]; then
  echo "Hyprland reported config errors after install:" >&2
  echo "$errors" >&2
fi

cat <<'DONE'
Installed Yautja mode.
  Super + Alt + V   cycle vision mode
  Super + Alt + C   cloak the focused window
  Super + Alt + X   lock on, press again to kill
For the matching look: omarchy theme install https://github.com/neilofneils404/omarchy-yautja-theme
DONE
