#!/usr/bin/env bash
set -euo pipefail

project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
plugin_id="neil.yautja"
hypr_config="$HOME/.config/hypr/hyprland.lua"
menu_config="$HOME/.config/omarchy/extensions/omarchy-menu.jsonc"
bin_link="$HOME/.local/bin/yautja"
state_home=${XDG_STATE_HOME:-$HOME/.local/state}
run_dir=${XDG_RUNTIME_DIR:-$state_home/yautja}/yautja
live_cleanup_failed=0

# Use this checkout's command, even if the installed command link has changed.
# Abort the shutdown countdown before removing its menu and bar controls.
if [[ -x $project_dir/bin/yautja ]]; then
  if ! "$project_dir/bin/yautja" reset; then
    # A busy runtime can fail before it reaches abort. Keep the controls in
    # place if a countdown is still armed; offline compositor errors are fine.
    if [[ -f $run_dir/destruct.token ]]; then
      echo "Could not cancel Yautja's countdown. Run 'yautja self-destruct abort', then uninstall again." >&2
      exit 1
    fi
    live_cleanup_failed=1
    echo "Could not verify all live Yautja effects were cleared. Continuing to remove configuration and disable the plugin." >&2
  fi
fi
rm -f "$state_home/omarchy/toggles/hypr/yautja-vision.lua"

python3 "$project_dir/scripts/manage-config.py" uninstall "$hypr_config" "$menu_config" "$project_dir/menu/omarchy-menu.jsonc"

omarchy plugin disable "$plugin_id" >/dev/null 2>&1 || true
if [[ -L $bin_link && $(readlink -f "$bin_link") == "$(readlink -f "$project_dir/bin/yautja")" ]]; then
  rm -f "$bin_link"
fi
hyprctl reload >/dev/null 2>&1 || true

if (( live_cleanup_failed )); then
  echo "Yautja configuration removed; live desktop cleanup could not be verified."
else
  echo "Yautja mode is switched off."
fi
echo "Kill history is kept in $state_home/yautja."
echo "To delete the plugin itself: omarchy plugin remove $plugin_id"
