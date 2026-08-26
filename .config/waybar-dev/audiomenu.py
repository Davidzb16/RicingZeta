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
    import json
    try:
        sinks_out = subprocess.check_output("pactl -f json list sinks 2>/dev/null", shell=True).decode('utf-8', errors='ignore')
        sinks_json = json.loads(sinks_out)
        sources_out = subprocess.check_output("pactl -f json list sources 2>/dev/null", shell=True).decode('utf-8', errors='ignore')
        sources_json = json.loads(sources_out)
        cards_out = subprocess.check_output("pactl -f json list cards 2>/dev/null", shell=True).decode('utf-8', errors='ignore')
        cards_json = json.loads(cards_out)
        info_out = subprocess.check_output("pactl -f json info 2>/dev/null", shell=True).decode('utf-8', errors='ignore')
        info_json = json.loads(info_out)
    except Exception as e:
        return [], []

    def_sink_name = info_json.get("default_sink_name", "")
    def_source_name = info_json.get("default_source_name", "")

    sinks = []
    sources = []
    
    for s in sinks_json:
        is_def = (s["name"] == def_sink_name)
        desc = s.get("description", "")
        if not desc or desc == "(null)":
            desc = s.get("properties", {}).get("device.description", s["name"])
            
        vol_percent = 50
        if "volume" in s and "front-left" in s["volume"]:
            vol_str = str(s["volume"]["front-left"].get("value_percent", "50%"))
            vol_percent = float(vol_str.strip('%'))
            
        desc = desc.replace("CORSAIR Slipstream Multi-Device Receiver Pro", "Corsair Slipstream")
        desc = desc.replace("CORSAIR Slipstream Multi-Device Receiver", "Corsair Slipstream")
        desc = desc.replace("Ryzen HD Audio Controller", "Ryzen HD Audio")
        desc = desc.replace("GB205 High Definition Audio Controller", "GB205 Audio")
        
        sinks.append({
            "id": s["name"], "name": desc, "is_default": is_def, "vol": vol_percent,
            "type": "sink", "card": s.get("properties", {}).get("alsa.card_name", "")
        })

    for s in sources_json:
        if s["name"].endswith(".monitor"): continue
            
        is_def = (s["name"] == def_source_name)
        desc = s.get("description", "")
        if not desc or desc == "(null)":
            desc = s.get("properties", {}).get("device.description", s["name"])
            
        vol_percent = 50
        if "volume" in s and "front-left" in s["volume"]:
            vol_str = str(s["volume"]["front-left"].get("value_percent", "50%"))
            vol_percent = float(vol_str.strip('%'))
            
        desc = desc.replace("CORSAIR Slipstream Multi-Device Receiver Pro", "Corsair Slipstream")
        desc = desc.replace("CORSAIR Slipstream Multi-Device Receiver", "Corsair Slipstream")
        desc = desc.replace("Ryzen HD Audio Controller", "Ryzen HD Audio")
        desc = desc.replace("GB205 High Definition Audio Controller", "GB205 Audio")
        
        sources.append({
            "id": s["name"], "name": desc, "is_default": is_def, "vol": vol_percent,
            "type": "source", "card": s.get("properties", {}).get("alsa.card_name", "")
        })

    for c in cards_json:
        card_id = c.get("name")
        card_desc = c.get("properties", {}).get("device.description", card_id)
        card_desc = card_desc.replace("CORSAIR Slipstream Multi-Device Receiver", "Corsair Slipstream")
        card_desc = card_desc.replace("Ryzen HD Audio Controller", "Ryzen HD Audio")
        card_desc = card_desc.replace("GB205 High Definition Audio Controller", "GB205 Audio")
        
        profiles = c.get("profiles", {})
        active_prof = c.get("active_profile")
        
        for p_name, p_info in profiles.items():
            if p_name == "off" or p_name == active_prof: continue
            if "surround" in p_name: continue
            if "extra2" in p_name or "extra3" in p_name or "extra4" in p_name: continue
            if p_info.get("available") is False and "analog" not in p_name: continue
            
            p_desc = p_info.get("description", p_name)
            if p_desc == "(null)":
                if "analog-stereo" in p_name: p_desc = "Analog"
                elif "iec958" in p_name: p_desc = "Digital"
                else: p_desc = p_name
            
            # Avoid duplicate analog profiles from duplex
            if "input:analog-stereo" in p_name and "output:analog-stereo" not in p_name and "output:iec958" not in p_name:
                continue
                
            if p_info.get("sinks", 0) > 0 and not any(s["type"] == "profile" and s["card"] == card_id and s["name"] == f"{card_desc} ({p_desc})" for s in sinks):
                sinks.append({
                    "id": p_name, "name": f"{card_desc} ({p_desc})", "is_default": False,
                    "vol": 50, "type": "profile", "card": card_id
                })
                
            if p_info.get("sources", 0) > 0 and not any(s["type"] == "profile" and s["card"] == card_id and s["name"] == f"{card_desc} ({p_desc})" for s in sources):
                sources.append({
                    "id": p_name, "name": f"{card_desc} ({p_desc})", "is_default": False,
                    "vol": 50, "type": "profile", "card": card_id
                })

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
            
            def on_sink_click(w, item=s):
                if item.get("type") == "profile":
                    run_cmd(f"pactl set-card-profile {item['card']} {item['id']}")
                else:
                    run_cmd(f"wpctl set-default {item['id']}")
                for b in self.sink_btns:
                    b.get_style_context().remove_class("active")
                w.get_style_context().add_class("active")
                
            btn.connect("clicked", on_sink_click)
            self.sink_btns.append(btn)
            vbox.pack_start(btn, False, False, 0)

        # Output Slider
        def_sink = next((s for s in sinks if s['is_default']), sinks[0] if sinks else None)
        if def_sink and def_sink.get("type") == "sink":
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
                
            def on_source_click(w, item=s):
                if item.get("type") == "profile":
                    run_cmd(f"pactl set-card-profile {item['card']} {item['id']}")
                else:
                    run_cmd(f"wpctl set-default {item['id']}")
                for b in self.source_btns:
                    b.get_style_context().remove_class("active")
                w.get_style_context().add_class("active")
                
            btn.connect("clicked", on_source_click)
            self.source_btns.append(btn)
            vbox.pack_start(btn, False, False, 0)

        # Input slider
        def_source = next((s for s in sources if s['is_default']), sources[0] if sources else None)
        if def_source and def_source.get("type") == "source":
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
