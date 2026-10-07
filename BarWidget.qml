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

  property string bootId: ""
  property string vision: "off"
  property var kills: []

  readonly property var trophies: kills.filter(function(kill) { return kill.worthy === true })
  readonly property int maxSkulls: Math.max(1, Number(setting("maxSkulls", 8)))

  readonly property string label: {
    var parts = [vision === "off" ? sight : eye]
    var shown = Math.min(trophies.length, maxSkulls)
    if (shown > 0) parts.push(skull.repeat(shown))
    if (trophies.length > shown) parts.push("+" + (trophies.length - shown))
    return parts.join(" ")
  }

  readonly property string tooltip: {
    var lines = ["Vision: " + vision]
    if (kills.length === 0) lines.push("The wall is bare")
    for (var i = 0; i < kills.length; i++) {
      var kill = kills[i]
      var mass = kill.rss_kb >= 1048576
        ? (kill.rss_kb / 1048576).toFixed(1) + " GB"
        : Math.floor(kill.rss_kb / 1024) + " MB"
      lines.push((kill.worthy ? skull : "·") + " " + kill.class + "  " + mass)
    }
    return lines.join("\n")
  }

  function parse(text) {
    var state
    try {
      state = JSON.parse(text)
    } catch (error) {
      return
    }
    vision = state.vision || "off"
    var all = Array.isArray(state.trophies) ? state.trophies : []
    kills = all.filter(function(kill) { return kill.boot === root.bootId })
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
    path: Quickshell.env("HOME") + "/.local/state/yautja/state.json"
    watchChanges: true
    printErrors: false
    onFileChanged: reload()
    onLoaded: root.parse(text())
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
      if (b === Qt.RightButton) root.bar.run(root.yautja + " trophies notify")
      else if (b === Qt.MiddleButton) root.bar.run(root.yautja + " vision off")
      else root.bar.run(root.yautja + " vision next")
    }
  }
}
