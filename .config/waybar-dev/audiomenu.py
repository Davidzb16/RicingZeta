#!/usr/bin/env python3
import gi
import subprocess
import re
import sys

gi.require_version('Gtk', '3.0')
gi.require_version('GtkLayerShell', '0.1')
from gi.repository import Gtk, Gdk, GLib, GtkLayerShell

CSS = b"""
window {
    background-color: transparent;
}
.audio-menu {
    background-color: rgba(9, 9, 11, 0.95);
    border: 1px solid #00ffcc;
    color: #00ffcc;
    padding: 20px;
    font-family: "Orbitron", sans-serif;
    font-weight: bold;
}
.title {
    color: #ff0055;
    font-size: 14px;
    margin-bottom: 10px;
    margin-top: 10px;
}
.device-btn {
    background: transparent;
    color: #00ffcc;
    border: 1px solid transparent;
    box-shadow: none;
    border-radius: 0;
    margin: 2px 0;
    padding: 8px 10px;
}
.device-btn:hover {
    background: rgba(0, 255, 204, 0.1);
    border-color: #00ffcc;
}
.device-btn.active {
    background: #00ffcc;
    color: #09090b;
}
scale {
    margin: 5px 0 15px 0;
}
scale trough {
    background: rgba(0, 255, 204, 0.2);
    border-radius: 0;
    min-height: 8px;
}
scale highlight {
    background: #00ffcc;
    border-radius: 0;
}
"""

def run_cmd(cmd):
    try:
        return subprocess.check_output(cmd, shell=True).decode('utf-8')
    except subprocess.CalledProcessError:
        return ""

def get_devices():
    out = run_cmd("wpctl status")
    sinks = []
    sources = []
    
    current_section = None
    for line in out.splitlines():
        line_strip = line.strip()
        if "Sinks:" in line:
            current_section = "sinks"
            continue
        elif "Sources:" in line:
            current_section = "sources"
            continue
        elif line_strip in ["Audio", "Video", "Settings"] or line_strip.startswith("├─ Filters:") or line_strip.startswith("└─ Streams:") or line_strip.startswith("└─ Clients:") or line_strip.startswith("└─ Default Configured Devices:"):
            current_section = None
            
        if current_section in ["sinks", "sources"]:
            is_default = "*" in line
            m = re.search(r'(\d+)\.\s+(.*?)\s+\[vol:\s+([\d\.]+).*?\]', line)
            if not m:
                m = re.search(r'(\d+)\.\s+(.*)', line)
                
            if m:
                node_id = m.group(1)
                name = m.group(2).strip()
                # Remove [vol: ...] part if it was captured in name due to regex fallback
                name = re.sub(r'\[vol:.*?\]', '', name).strip()
                vol = float(m.group(3)) * 100 if len(m.groups()) >= 3 and m.group(3) is not None else 50
                dev = {"id": node_id, "name": name, "is_default": is_default, "vol": vol}
                if current_section == "sinks":
                    sinks.append(dev)
                else:
                    sources.append(dev)
                    
    return sinks, sources

class AudioMenu(Gtk.Window):
    def __init__(self):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        
        GtkLayerShell.init_for_window(self)
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.TOP)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.TOP, True)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.RIGHT, True)
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.TOP, 45)
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.RIGHT, 15)
        GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.ON_DEMAND)
        
        self.connect("key-press-event", self.on_key_press)
        # self.connect("focus-out-event", lambda *_: Gtk.main_quit()) # optional auto-close
        
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), 
            provider, 
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        vbox.get_style_context().add_class("audio-menu")
        self.add(vbox)
        
        sinks, sources = get_devices()
        
        # Output
        lbl_out = Gtk.Label(label="OUTPUT (SPEAKERS)", xalign=0)
        lbl_out.get_style_context().add_class("title")
        vbox.pack_start(lbl_out, False, False, 0)
        
        # Output devices
        self.sink_btns = []
        for s in sinks:
            btn = Gtk.Button(label=s['name'][:35])
            btn.get_style_context().add_class("device-btn")
            if s['is_default']:
                btn.get_style_context().add_class("active")
            
            def on_sink_click(w, sid=s['id']):
                run_cmd(f"wpctl set-default {sid}")
                for b in self.sink_btns:
                    b.get_style_context().remove_class("active")
                w.get_style_context().add_class("active")
                
            btn.connect("clicked", on_sink_click)
            self.sink_btns.append(btn)
            vbox.pack_start(btn, False, False, 0)

        # Output Slider
        def_sink = next((s for s in sinks if s['is_default']), sinks[0] if sinks else None)
        if def_sink:
            adj = Gtk.Adjustment(value=def_sink['vol'], lower=0, upper=100, step_increment=1)
            scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=adj)
            scale.set_draw_value(False)
            scale.connect("value-changed", lambda w: run_cmd(f"wpctl set-volume {def_sink['id']} {w.get_value()/100:.2f}"))
            vbox.pack_start(scale, False, False, 10)
        
        # Input
        lbl_in = Gtk.Label(label="INPUT (MICROPHONE)", xalign=0)
        lbl_in.get_style_context().add_class("title")
        vbox.pack_start(lbl_in, False, False, 0)
        
        # Input devices
        self.source_btns = []
        for s in sources:
            btn = Gtk.Button(label=s['name'][:35])
            btn.get_style_context().add_class("device-btn")
            if s['is_default']:
                btn.get_style_context().add_class("active")
                
            def on_source_click(w, sid=s['id']):
                run_cmd(f"wpctl set-default {sid}")
                for b in self.source_btns:
                    b.get_style_context().remove_class("active")
                w.get_style_context().add_class("active")
                
            btn.connect("clicked", on_source_click)
            self.source_btns.append(btn)
            vbox.pack_start(btn, False, False, 0)

        # Input slider
        def_source = next((s for s in sources if s['is_default']), sources[0] if sources else None)
        if def_source:
            adj2 = Gtk.Adjustment(value=def_source['vol'], lower=0, upper=100, step_increment=1)
            scale2 = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=adj2)
            scale2.set_draw_value(False)
            scale2.connect("value-changed", lambda w: run_cmd(f"wpctl set-volume {def_source['id']} {w.get_value()/100:.2f}"))
            vbox.pack_start(scale2, False, False, 10)
                
        self.show_all()
        
    def on_key_press(self, widget, event):
        if event.keyval == Gdk.KEY_Escape:
            Gtk.main_quit()

if __name__ == "__main__":
    out = subprocess.getoutput("pgrep -fc audiomenu.py")
    if out.isdigit() and int(out) > 1:
        subprocess.run("pkill -f audiomenu.py", shell=True)
        sys.exit(0)
        
    win = AudioMenu()
    Gtk.main()
