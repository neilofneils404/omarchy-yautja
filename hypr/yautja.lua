-- Yautja mode: cloak, target lock, the keys that drive bin/yautja, and the
-- thermal window look that goes with the Yautja theme.
--
-- install.sh loads this from ~/.config/hypr/hyprland.lua.

local home = os.getenv("HOME")
local yautja = home .. "/.local/bin/yautja"

-- Cloaked windows are nearly invisible, focused or not.
o.window({ tag = "yautja-cloak" }, { opacity = "0.07 override 0.04 override 0.07 override", no_shadow = true })

-- A locked-on target wears a red border until it is taken or the lock lapses.
o.window({ tag = "yautja-lock" }, { border_color = "rgb(ff1a1a) rgb(ff7a00) 90deg" })

o.bind("SUPER + ALT + V", "Yautja vision mode", yautja .. " vision next")
o.bind("SUPER + ALT + C", "Yautja cloak window", yautja .. " cloak")
o.bind("SUPER + ALT + X", "Yautja hunt window", yautja .. " hunt")

-- An installed theme cannot ship Lua, so the thermal look lives here and only
-- switches on while the Yautja theme is the current one.
local function current_theme()
  local state = os.getenv("XDG_STATE_HOME") or (home .. "/.local/state")
  local file = io.open(state .. "/omarchy/current/theme.name", "r")
  if not file then
    return nil
  end

  local name = file:read("*l")
  file:close()
  return name
end

if current_theme() == "yautja" then
  hl.config({
    decoration = {
      dim_inactive = true,
      dim_strength = 0.2,

      -- Heat bloom around the focused window, a cold halo around the rest.
      shadow = {
        enabled = true,
        range = 24,
        render_power = 2,
        color = "rgba(ff5a1f70)",
        color_inactive = "rgba(1a247050)",
      },

      -- Gives a cloaked window something to refract.
      blur = {
        enabled = true,
        size = 6,
        passes = 2,
        noise = 0.06,
      },
    },
  })
end
