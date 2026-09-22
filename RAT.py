#!/usr/bin/env python3
"""
0_x - Universal Device Mirror & Control (TUI) – simplified for USB-first mirroring
Run with: sudo python3 rat15_fixed.py

Requirements:
    pip install textual netifaces
    sudo apt install arp-scan adb scrcpy
"""

import asyncio
import json
import subprocess
import sys
import os
import re
import traceback
import time
from pathlib import Path
from typing import List, Optional, Callable, Tuple
from textual import on
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Button, Static, ListView, ListItem, Label, Input
from textual.screen import Screen
import netifaces

# ------------------------------------------------------------
# Device class
# ------------------------------------------------------------
class Device:
    def __init__(self, ip: str = "", mac: str = "", hostname: str = "", os: str = "unknown",
                 connection: str = "network", serial: str = "", status: str = "device"):
        self.ip = ip
        self.mac = mac
        self.hostname = hostname
        self.os = os
        self.connection = connection   # "usb" | "wifi-adb" | "network"
        self.serial = serial
        self.status = status

    def __str__(self):
        if self.connection == "usb":
            conn = "🔌 USB"
        elif self.connection == "wifi-adb":
            conn = "📲 WiFi"
        else:
            conn = "📶 NET"
        status_icon = "✅" if self.status == "device" else "⚠️"
        label = self.ip or self.serial or "unknown"
        return f"{conn}  {label}  {self.hostname}  ({self.os}) {status_icon}"

# ------------------------------------------------------------
# Network helpers
# ------------------------------------------------------------
def get_interface() -> str:
    try:
        gateways = netifaces.gateways()
        default = gateways.get('default', {}).get(netifaces.AF_INET)
        if default:
            return default[1]
    except Exception:
        pass
    for iface in netifaces.interfaces():
        if iface.startswith("lo"):
            continue
        addrs = netifaces.ifaddresses(iface)
        if netifaces.AF_INET in addrs:
            ip = addrs[netifaces.AF_INET][0]['addr']
            if ip and not ip.startswith("127."):
                return iface
    return "wlan0"

def get_local_ip() -> str:
    iface = get_interface()
    try:
        return netifaces.ifaddresses(iface)[netifaces.AF_INET][0]['addr']
    except Exception:
        return "127.0.0.1"

# ------------------------------------------------------------
# Network scan
# ------------------------------------------------------------
def scan_network_arp_scan() -> List[Device]:
    devices = []
    try:
        iface = get_interface()
        base = ".".join(get_local_ip().split(".")[:3]) + ".0/24"
        print(f"[*] Running arp-scan -I {iface} {base}")
        result = subprocess.run(["arp-scan", "-I", iface, base],
                                capture_output=True, text=True, timeout=15)
        if result.returncode != 0:
            print(f"[!] arp-scan failed: {result.stderr}")
            return []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line or line.startswith(("Starting", "Ending", "Interface", "WARNING")):
                continue
            parts = re.split(r'\t+|\s{2,}', line)
            if len(parts) < 2:
                continue
            ip = parts[0].strip()
            mac = parts[1].strip()
            if not re.match(r'^\d+\.\d+\.\d+\.\d+$', ip):
                continue
            hostname = "unknown"
            try:
                import socket
                hostname = socket.gethostbyaddr(ip)[0]
            except Exception:
                pass
            devices.append(Device(ip=ip, mac=mac, hostname=hostname,
                                  os="unknown", connection="network"))
        print(f"[*] arp-scan found {len(devices)} devices")
    except FileNotFoundError:
        print("[!] arp-scan not found. Install: sudo apt install arp-scan")
    except Exception as e:
        print(f"[!] arp-scan error: {e}")
    return devices

def scan_network_scapy() -> List[Device]:
    devices = []
    try:
        import scapy.all as scapy
        iface = get_interface()
        ip_info = netifaces.ifaddresses(iface).get(netifaces.AF_INET)
        if not ip_info:
            return []
        base = ".".join(ip_info[0]['addr'].split(".")[:3]) + ".0/24"
        print(f"[*] Scapy scanning {base}")
        ans, _ = scapy.srp(
            scapy.Ether(dst="ff:ff:ff:ff:ff:ff") / scapy.ARP(pdst=base),
            timeout=3, iface=iface, verbose=False
        )
        for _, received in ans:
            hostname = "unknown"
            try:
                import socket
                hostname = socket.gethostbyaddr(received.psrc)[0]
            except Exception:
                pass
            devices.append(Device(ip=received.psrc, mac=received.hwsrc,
                                  hostname=hostname, os="unknown", connection="network"))
        print(f"[*] Scapy found {len(devices)} devices")
    except ImportError:
        print("[!] scapy not installed: pip install scapy")
    except Exception as e:
        print(f"[!] Scapy error: {e}")
    return devices

def scan_network() -> List[Device]:
    devices = scan_network_arp_scan()
    if devices:
        return devices
    print("[*] arp-scan failed, trying scapy...")
    return scan_network_scapy()

# ------------------------------------------------------------
# USB / ADB scan
# ------------------------------------------------------------
def scan_usb() -> List[Device]:
    devices = []
    print("[*] Scanning ADB devices (USB + Wi-Fi ADB)...")
    try:
        subprocess.run(["adb", "start-server"], capture_output=True, timeout=5)
    except Exception:
        pass
    try:
        subprocess.run(["adb", "version"], capture_output=True, check=True, timeout=3)
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("[!] ADB not found. Install: sudo apt install android-tools-adb")
        return devices

    try:
        result = subprocess.run(["adb", "devices", "-l"],
                                capture_output=True, text=True, timeout=8)
        print(f"[*] ADB output:\n{result.stdout}")
        for line in result.stdout.strip().splitlines()[1:]:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            serial = parts[0]
            status = parts[1]
            is_wifi = re.match(r'^\d+\.\d+\.\d+\.\d+:\d+$', serial)
            connection = "wifi-adb" if is_wifi else "usb"
            model = ""
            for token in parts[2:]:
                if token.startswith("model:"):
                    model = token.split(":", 1)[1].replace("_", " ")
                    break
            if not model and status == "device":
                try:
                    r = subprocess.run(
                        ["adb", "-s", serial, "shell", "getprop", "ro.product.model"],
                        capture_output=True, text=True, timeout=4
                    )
                    model = r.stdout.strip()
                except Exception:
                    pass
            ip = serial.split(":")[0] if is_wifi else ""
            if not ip and status == "device" and not is_wifi:
                # Try to get IP from device
                try:
                    r = subprocess.run(
                        ["adb", "-s", serial, "shell", "ip", "route", "show", "default"],
                        capture_output=True, text=True, timeout=4
                    )
                    for token in r.stdout.split():
                        if token.startswith("src"):
                            ip = token.split()[1]
                            break
                except Exception:
                    pass
            devices.append(Device(
                ip=ip,
                hostname=model or serial[:20],
                os="Android",
                connection=connection,
                serial=serial,
                status=status
            ))
    except subprocess.TimeoutExpired:
        print("[!] ADB scan timed out")
    except Exception as e:
        print(f"[!] ADB scan error: {e}")
        traceback.print_exc()
    return devices

# ------------------------------------------------------------
# Mirror engine – simplified for USB-first
# ------------------------------------------------------------
def start_mirror(dev: Device) -> Tuple[bool, str]:
    # If it's a network device (no ADB), try to see if it responds to ADB on port 5555
    if dev.connection == "network":
        if not dev.ip:
            return False, "No IP address for this device."
        # Quick port probe
        try:
            import socket as sck
            sock = sck.socket(sck.AF_INET, sck.SOCK_STREAM)
            sock.settimeout(1.5)
            if sock.connect_ex((dev.ip, 5555)) != 0:
                sock.close()
                # No ADB open – suggest USB
                return False, (
                    f"No ADB on {dev.ip}:5555.\n"
                    "To mirror wirelessly:\n"
                    "  1. Connect your phone via USB (with USB debugging enabled).\n"
                    "  2. Click Mirror once – it will enable Wi-Fi ADB.\n"
                    "  3. Unplug and mirror wirelessly from then on.\n"
                    "Or enable Wireless Debugging in Developer Options."
                )
            sock.close()
        except Exception:
            return False, "Could not connect to ADB port. Please check connection."

        # ADB port open – try to connect and get model
        target = f"{dev.ip}:5555"
        try:
            subprocess.run(["adb", "connect", target], capture_output=True, timeout=5)
            # Get model to confirm it's Android
            r = subprocess.run(
                ["adb", "-s", target, "shell", "getprop", "ro.product.model"],
                capture_output=True, text=True, timeout=4
            )
            if not r.stdout.strip():
                return False, f"Connected to {target} but not an Android device."
            # upgrade device info
            dev.os = "Android"
            dev.serial = target
            dev.connection = "wifi-adb"
            dev.hostname = r.stdout.strip()
            dev.status = "device"
        except Exception as e:
            return False, f"ADB connection error: {e}"

    # Now we have a proper Android device (USB or Wi-Fi)
    if dev.os.lower() != "android":
        return False, f"Not Android (OS: {dev.os})"
    if dev.status != "device":
        return False, f"Status: {dev.status}. Accept USB debugging on phone."
    if not dev.serial:
        return False, "No ADB serial."

    # Check scrcpy
    try:
        subprocess.run(["scrcpy", "--version"], capture_output=True, timeout=5)
    except FileNotFoundError:
        return False, "scrcpy not installed. Install: sudo apt install scrcpy"

    # Ensure ADB server is running
    subprocess.run(["adb", "start-server"], capture_output=True)

    # For USB: enable tcpip so we can later mirror wirelessly without re-plugging
    if dev.connection == "usb":
        try:
            subprocess.run(
                ["adb", "-s", dev.serial, "tcpip", "5555"],
                capture_output=True, timeout=8
            )
        except Exception:
            pass  # not critical

    # Launch scrcpy
    try:
        proc = subprocess.Popen(
            ["scrcpy", "-s", dev.serial, "--no-audio"],
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
        )
        time.sleep(2.5)
        if proc.poll() is not None:
            err = proc.stderr.read().decode(errors="replace").strip()
            # Extract meaningful error
            for line in err.splitlines():
                if "ERROR" in line.upper() or "FAIL" in line.upper():
                    return False, f"scrcpy error: {line}"
            return False, f"scrcpy failed: {err[:200]}"
        if dev.connection == "usb":
            return True, f"✅ Mirroring {dev.hostname} over USB.\nNow you can unplug and mirror wirelessly (same IP)."
        else:
            return True, f"✅ Mirroring {dev.hostname} wirelessly ({dev.serial})."
    except Exception as e:
        return False, f"Exception: {e}"

# ------------------------------------------------------------
# Inject engine – similarly simplified
# ------------------------------------------------------------
def inject_media(dev: Device, filepath: str) -> Tuple[bool, str]:
    # Same logic: if network, try to connect
    if dev.connection == "network":
        if not dev.ip:
            return False, "No IP address."
        target = f"{dev.ip}:5555"
        try:
            subprocess.run(["adb", "connect", target], capture_output=True, timeout=5)
            r = subprocess.run(
                ["adb", "-s", target, "shell", "getprop", "ro.product.model"],
                capture_output=True, text=True, timeout=4
            )
            if not r.stdout.strip():
                return False, "Not an Android device."
            dev.serial = target
            dev.connection = "wifi-adb"
            dev.os = "Android"
            dev.hostname = r.stdout.strip()
            dev.status = "device"
        except Exception as e:
            return False, f"ADB connection failed: {e}"

    if dev.os.lower() != "android" or not dev.serial:
        return False, "Only Android ADB devices are supported."
    if dev.status != "device":
        return False, "Device not authorized. Accept USB debugging."
    if not os.path.exists(filepath):
        return False, f"File not found: {filepath}"

    dest = f"/sdcard/DCIM/{os.path.basename(filepath)}"
    try:
        subprocess.run(["adb", "-s", dev.serial, "push", filepath, dest],
                       capture_output=True, timeout=30, check=True)
        subprocess.run(["adb", "-s", dev.serial, "shell", "am", "start",
                        "-a", "android.intent.action.VIEW",
                        "-d", f"file://{dest}", "-t", "video/mp4"],
                       capture_output=True, timeout=10, check=True)
        return True, f"✅ Injected {os.path.basename(filepath)}"
    except subprocess.CalledProcessError as e:
        return False, f"ADB error: {e.stderr.decode().strip()}"
    except Exception as e:
        return False, f"Exception: {e}"

# ------------------------------------------------------------
# File input modal
# ------------------------------------------------------------
class FileInputScreen(Screen):
    def __init__(self, callback: Callable[[Optional[str]], None]):
        super().__init__()
        self.callback = callback
        self._done = False

    def compose(self) -> ComposeResult:
        yield Container(
            Label("Enter file path on this machine:", classes="label"),
            Input(placeholder="/path/to/video.mp4", id="file-input"),
            Horizontal(
                Button("Inject", id="inject-confirm", variant="success"),
                Button("Cancel", id="inject-cancel", variant="default"),
            ),
            id="file-modal",
        )

    @on(Button.Pressed, "#inject-confirm")
    async def on_confirm(self):
        if self._done:
            return
        self._done = True
        path = self.query_one("#file-input", Input).value.strip()
        self.dismiss()
        self.callback(path or None)

    @on(Button.Pressed, "#inject-cancel")
    async def on_cancel(self):
        if self._done:
            return
        self._done = True
        self.dismiss()
        self.callback(None)

# ------------------------------------------------------------
# Main App
# ------------------------------------------------------------
class ZeroXApp(App):
    TITLE = "0_x — Mirror & Control"

    CSS = """
    Screen { background: #1e1e2e; }
    #device-list { height: 1fr; border: solid $primary; background: #2a2a3a; }
    #info-panel { height: 1fr; border: solid $secondary; background: #2a2a3a; padding: 1; }
    Button { margin: 1; }
    #file-modal {
        width: 60%; height: auto; border: thick $primary;
        background: $surface; align: center middle; padding: 1;
    }
    #file-modal Input { margin: 1; width: 90%; }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Horizontal(
                Vertical(
                    Label("📡 Devices", id="device-label"),
                    ListView(id="device-list"),
                    Button("🔍 Scan All",          id="scan-btn",        variant="primary"),
                    Button("🔌 Scan USB/WiFi",      id="usb-scan-btn",    variant="primary"),
                    Button("🖥️  Mirror Selected",  id="mirror-btn",      variant="success"),
                    Button("📁 Inject Media",       id="inject-btn",      variant="warning"),
                    id="left-panel",
                ),
                Vertical(
                    Label("📋 Log", id="log-label"),
                    Static("Ready.\n\n"
                           "👉 To mirror wirelessly without Developer Options:\n"
                           "  1. Connect phone via USB (USB debugging must be ON).\n"
                           "  2. Click Mirror once – it will enable Wi-Fi ADB.\n"
                           "  3. Unplug and now you can mirror wirelessly.\n\n"
                           "📶 For network devices: the tool will try ADB on port 5555.\n"
                           "   If it fails, plug USB first as above.",
                           id="info-panel"),
                    id="right-panel",
                ),
            ),
        )
        yield Footer()

    def on_mount(self) -> None:
        self.call_after_refresh(lambda: asyncio.ensure_future(self._startup()))

    async def _startup(self):
        await self.scan_both()

    async def scan_both(self) -> None:
        info = self.query_one("#info-panel", Static)
        list_view = self.query_one("#device-list", ListView)
        info.update("🔄 Scanning...")
        try:
            net_devs, adb_devs = await asyncio.gather(
                asyncio.to_thread(scan_network),
                asyncio.to_thread(scan_usb),
            )
            unique = {}
            for dev in adb_devs + net_devs:
                key = dev.serial or dev.ip
                if key and key not in unique:
                    unique[key] = dev
            final = list(unique.values())
            await list_view.clear()
            for dev in final:
                item = ListItem(Label(str(dev)))
                item._device = dev
                await list_view.append(item)
            usb = sum(1 for d in final if d.connection == "usb")
            wifi = sum(1 for d in final if d.connection == "wifi-adb")
            net = sum(1 for d in final if d.connection == "network")
            info.update(f"✅ {len(final)} devices found\n   🔌 USB: {usb}   📲 Wi-Fi: {wifi}   📶 Net: {net}")
        except Exception as e:
            info.update(f"⚠️ Scan error: {e}")

    async def scan_usb_only(self) -> None:
        info = self.query_one("#info-panel", Static)
        list_view = self.query_one("#device-list", ListView)
        info.update("🔄 Scanning USB/Wi-Fi ADB...")
        try:
            devs = await asyncio.to_thread(scan_usb)
            await list_view.clear()
            for dev in devs:
                item = ListItem(Label(str(dev)))
                item._device = dev
                await list_view.append(item)
            info.update(f"✅ Found {len(devs)} ADB device(s).")
        except Exception as e:
            info.update(f"⚠️ Scan error: {e}")

    def _get_selected(self) -> Optional[Device]:
        selected = self.query_one("#device-list", ListView).highlighted_child
        return getattr(selected, "_device", None) if selected else None

    @on(Button.Pressed, "#scan-btn")
    async def on_scan(self):
        await self.scan_both()

    @on(Button.Pressed, "#usb-scan-btn")
    async def on_usb_scan(self):
        await self.scan_usb_only()

    @on(Button.Pressed, "#mirror-btn")
    async def on_mirror(self):
        info = self.query_one("#info-panel", Static)
        dev = self._get_selected()
        if not dev:
            info.update("❌ Select a device first.")
            return
        info.update(f"🔄 Mirroring {dev.hostname or dev.serial}...")
        ok, msg = await asyncio.to_thread(start_mirror, dev)
        info.update(msg)

    @on(Button.Pressed, "#inject-btn")
    async def on_inject(self):
        info = self.query_one("#info-panel", Static)
        dev = self._get_selected()
        if not dev:
            info.update("❌ Select a device.")
            return
        if dev.os.lower() not in ("android", "unknown"):
            info.update("❌ Only Android devices.")
            return
        if dev.status != "device":
            info.update("❌ Device not authorized. Accept USB debugging.")
            return

        def cb(path):
            if path:
                asyncio.ensure_future(self._do_inject(dev, path))
        await self.push_screen(FileInputScreen(cb))

    async def _do_inject(self, dev, path):
        info = self.query_one("#info-panel", Static)
        info.update(f"🔄 Injecting {os.path.basename(path)}...")
        ok, msg = await asyncio.to_thread(inject_media, dev, path)
        info.update(msg)

# ------------------------------------------------------------
# Entry
# ------------------------------------------------------------
if __name__ == "__main__":
    try:
        import textual, netifaces
    except ImportError as e:
        print(f"Missing: {e}\nInstall: pip install textual netifaces")
        sys.exit(1)
    if os.geteuid() != 0:
        print("⚠️  Requires root for ARP scanning.\nRun: sudo python3 rat15_fixed.py")
        sys.exit(1)
    for cmd in ["adb", "scrcpy", "arp-scan"]:
        try:
            subprocess.run([cmd, "--version"] if cmd != "arp-scan" else [cmd, "--help"],
                           capture_output=True, timeout=3)
            print(f"[✓] {cmd} found.")
        except:
            print(f"[✗] {cmd} not found.")
    ZeroXApp().run()
