#!/usr/bin/env bash
set -euo pipefail

plugin_id="neil.yautja"
plugin_dir="$HOME/.config/omarchy/plugins/$plugin_id"
hypr_config="$HOME/.config/hypr/hyprland.lua"
menu_config="$HOME/.config/omarchy/extensions/omarchy-menu.jsonc"
bin_link="$HOME/.local/bin/yautja"
state_home=${XDG_STATE_HOME:-$HOME/.local/state}

# Leave nothing on screen: vision off, every window decloaked.
if [[ -x $bin_link ]]; then
  "$bin_link" vision off || true
  "$bin_link" cloak all-off || true
fi
rm -f "$state_home/omarchy/toggles/hypr/yautja-vision.lua"

if [[ -f $hypr_config ]] && grep -q "$plugin_id" "$hypr_config"; then
  cp "$hypr_config" "$hypr_config.bak.$(date +%s)"
  sed -i "/$plugin_id/d" "$hypr_config"
fi

if [[ -f $menu_config ]] && grep -q ">>> $plugin_id" "$menu_config"; then
  cp "$menu_config" "$menu_config.bak.$(date +%s)"
  sed -i "/>>> $plugin_id/,/<<< $plugin_id/d" "$menu_config"
fi

omarchy plugin disable "$plugin_id" >/dev/null 2>&1 || true
[[ -L $bin_link ]] && rm -f "$bin_link"
hyprctl reload >/dev/null 2>&1 || true

echo "Yautja mode is switched off. Kill history is kept in $state_home/yautja."
echo "To delete the plugin itself: omarchy plugin remove $plugin_id"
