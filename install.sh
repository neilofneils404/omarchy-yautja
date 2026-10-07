#!/usr/bin/env bash
set -euo pipefail

project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
plugin_id="neil.yautja"
plugin_dir="$HOME/.config/omarchy/plugins/$plugin_id"
hypr_config="$HOME/.config/hypr/hyprland.lua"
menu_config="$HOME/.config/omarchy/extensions/omarchy-menu.jsonc"
bin_link="$HOME/.local/bin/yautja"
config_helper="$project_dir/scripts/manage-config.py"

for dependency in python3 omarchy omarchy-shell hyprctl jq flock; do
  command -v "$dependency" >/dev/null || {
    echo "Yautja requires $dependency. Install it before running install.sh." >&2
    exit 1
  }
done

# Refuse conflicts before modifying the user's configuration or creating links.
if [[ -e $bin_link || -L $bin_link ]]; then
  if [[ ! -L $bin_link || $(readlink -f "$bin_link") != "$(readlink -f "$project_dir/bin/yautja")" ]]; then
    echo "An unrelated command exists at $bin_link. Move it before installing Yautja." >&2
    exit 1
  fi
fi
python3 "$config_helper" check "$hypr_config" "$menu_config" "$project_dir/menu/omarchy-menu.jsonc"

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

# Back up and update only the managed blocks, preserving JSONC comments and
# other customizations. The menu is also created for a fresh Omarchy profile.
python3 "$config_helper" install "$hypr_config" "$menu_config" "$project_dir/menu/omarchy-menu.jsonc"

omarchy-shell -q shell rescanPlugins
# Discovery is asynchronous, just as it is for `omarchy plugin add`.
discovered=0
for ((attempt = 0; attempt < 40; attempt++)); do
  if omarchy plugin list --json | jq -e --arg id "$plugin_id" 'any(.[]; .id == $id)' >/dev/null; then
    discovered=1
    break
  fi
  sleep 0.05
done
if (( ! discovered )); then
  echo "The Omarchy shell has not discovered $plugin_id. Check that the shell is running, then run install.sh again." >&2
  exit 1
fi
# The shell keeps an existing placement, re-enables disabled widgets, and puts
# new left-section widgets after workspaces (or at the end if it is absent).
omarchy plugin enable "$plugin_id"

config_failure() {
  printf '%s\n' "$1" >&2
  echo "Yautja files remain installed. Edited configs have backups alongside them; fix the reported error and rerun install.sh." >&2
  exit 1
}

if ! reload_result=$(hyprctl reload 2>&1); then
  config_failure "Hyprland reload failed: $reload_result"
fi
if ! errors=$(hyprctl configerrors 2>&1); then
  config_failure "Could not check Hyprland config errors: $errors"
fi
if [[ -n $errors ]]; then
  config_failure "Hyprland reported config errors after install: $errors"
fi

cat <<'DONE'
Installed Yautja mode.
  Super + Alt + V   cycle vision mode
  Super + Alt + C   cloak the focused window
  Super + Alt + X   lock on, press again to kill
For the matching look: omarchy theme install https://github.com/neilofneils404/omarchy-yautja-theme
DONE
