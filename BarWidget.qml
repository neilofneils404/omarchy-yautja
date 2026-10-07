import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

// Trophy wall. Reads the state bin/yautja writes: one skull per
// worthy kill since boot, and the vision mode currently on screen.
BarWidget {
  id: root
  moduleName: "neil.yautja"

  readonly property string yautja: decodeURIComponent(Qt.resolvedUrl("bin/yautja").toString().replace(/^file:\/\//, ""))
  readonly property string skull: String.fromCodePoint(0xF068C)
  readonly property string eye: String.fromCodePoint(0xF0208)
  readonly property string sight: String.fromCodePoint(0xF04FE)
  readonly property string stateHome: Quickshell.env("XDG_STATE_HOME") || (Quickshell.env("HOME") + "/.local/state")
  readonly property var visionNames: ({ off: "Off", thermal: "Thermal", em: "Electromagnetic", tracking: "Tracking" })
  readonly property string visionIcon: vision === "off" ? sight : eye

  property string bootId: ""
  property string vision: "off"
  property var kills: []

  readonly property var trophies: kills.filter(function(kill) { return kill.worthy === true })
  readonly property int maxSkulls: {
    var count = Number(setting("maxSkulls", 8))
    return isFinite(count) ? Math.max(1, Math.min(32, Math.floor(count))) : 8
  }

  readonly property string label: {
    // Vertical bars have room for one glyph; the tooltip keeps the full tally.
    if (vertical) return visionIcon
    var parts = [visionIcon]
    var shown = Math.min(trophies.length, maxSkulls)
    if (shown > 0) parts.push(skull.repeat(shown))
    if (trophies.length > shown) parts.push("+" + (trophies.length - shown))
    return parts.join(" ")
  }

  readonly property string tooltip: {
    var lines = ["Yautja · " + visionNames[vision]]
    if (kills.length === 0) {
      lines.push("The wall is bare")
    } else {
      lines.push(trophies.length + (trophies.length === 1 ? " trophy" : " trophies") + " · " + kills.length + (kills.length === 1 ? " kill since boot" : " kills since boot"))
    }
    var shown = Math.min(kills.length, 8)
    for (var i = 0; i < shown; i++) {
      var kill = kills[kills.length - 1 - i]
      var mass = kill.rss_kb >= 1048576
        ? (kill.rss_kb / 1048576).toFixed(1) + " GiB"
        : Math.floor(kill.rss_kb / 1024) + " MiB"
      lines.push((kill.worthy ? skull : "·") + " " + kill.class + "  " + mass)
    }
    if (kills.length > shown) lines.push("+" + (kills.length - shown) + " older kills")
    lines.push("", "Left: cycle vision · Middle: vision off", "Right: trophy history")
    return lines.join("\n")
  }

  function parse(text) {
    var state
    try {
      state = JSON.parse(text)
    } catch (error) {
      return
    }
    if (state === null || typeof state !== "object" || Array.isArray(state)) return
    vision = typeof state.vision === "string" && Object.prototype.hasOwnProperty.call(visionNames, state.vision) ? state.vision : "off"
    var all = Array.isArray(state.trophies) ? state.trophies : []
    kills = all.filter(function(kill) {
      return kill !== null && typeof kill === "object" && !Array.isArray(kill)
        && root.bootId !== "" && kill.boot === root.bootId
        && typeof kill.rss_kb === "number" && isFinite(kill.rss_kb) && kill.rss_kb >= 0
    }).map(function(kill) {
      return {
        class: typeof kill.class === "string" ? kill.class.replace(/\s+/g, " ").slice(0, 64) : "Unknown window",
        rss_kb: kill.rss_kb,
        worthy: kill.worthy === true
      }
    })
  }

  visible: true
  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  FileView {
    path: "/proc/sys/kernel/random/boot_id"
    printErrors: false
    onLoaded: {
      root.bootId = text().trim()
      stateFile.reload()
    }
  }

  FileView {
    id: stateFile
    path: root.stateHome + "/yautja/state.json"
    watchChanges: true
    printErrors: false
    onFileChanged: reload()
    onLoaded: root.parse(text())
  }

  // On a fresh install the state directory may not exist yet, so FileView
  // cannot watch it. Retry until the first command creates its state file.
  Timer {
    interval: 1000
    running: !stateFile.loaded
    repeat: true
    onTriggered: stateFile.reload()
  }

  WidgetButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: root.label
    active: root.vision !== "off"
    fontSize: Style.font.body
    tooltipText: root.tooltip

    onPressed: function(b) {
      if (!root.bar) return
      if (b === Qt.RightButton) Util.execArgv([root.yautja, "trophies", "notify"])
      else if (b === Qt.MiddleButton) Util.execArgv([root.yautja, "vision", "off"])
      else Util.execArgv([root.yautja, "vision", "next"])
    }
  }
}
