# 📱 vector-rat — Universal Device Mirror & Control

> A sleek terminal UI to discover, mirror, and control Android devices over USB or Wi-Fi — all from one powerful TUI.

![Python](https://img.shields.io/badge/python-3.9+-blue.svg)
![Platform](https://img.shields.io/badge/platform-linux%20%7C%20macOS%20%7C%20termux-lightgrey)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Status](https://img.shields.io/badge/status-active-brightgreen)

---

## ✨ What is vector-rat?

**vector-rat** is a single-file, terminal-based control panel that lets you:

- 🔍 **Auto-discover** every device on your local network (ARP + Scapy)
- 🔌 **Detect** Android devices connected over USB via ADB
- 📲 **Switch** seamlessly between USB and Wi-Fi ADB
- 🖥️ **Mirror** any Android screen live using `scrcpy`
- 📁 **Push & play** media files to a device's gallery
- 🎛️ **Control everything** from one Textual TUI — no browser, no GUI required

Built for **pentesters**, **QA engineers**, **Android developers**, and anyone who needs a fast, scriptable way to interact with devices.

---

## 🚀 Features

| Feature | Description |
|---------|-------------|
| 🌐 **Network scan** | Uses `arp-scan` (fast) with `scapy` fallback to find every live host on your LAN |
| 🔌 **USB detection** | Automatically lists Android devices connected via ADB |
| 📲 **Wi-Fi ADB** | Enables wireless ADB with one click (`adb tcpip 5555`) so you can unplug and still mirror |
| 🖥️ **Screen mirroring** | Launches `scrcpy` with correct serial — USB or wireless |
| 📁 **Media injection** | Pushes a video to `/sdcard/DCIM/` and auto-opens it |
| 🎨 **Textual TUI** | Clean, keyboard-driven, dark-mode UI with live device list and log panel |
| ⚡ **Async-first** | Network + ADB scans run in parallel — no freezing |
| 🧠 **Smart fallbacks** | If `arp-scan` is missing, `scapy` takes over automatically |

---

## 📸 Screenshots

> _Add your own screenshots here once you run it_

```
┌─ 📡 Devices ────────────────────┐  ┌─ 📋 Log ─────────────────────────┐
│ 🔌 USB   R58M12ABCDEF  Pixel 7  │  │ ✅ 4 devices found                │
│ 📲 WiFi  192.168.1.42  Galaxy   │  │    🔌 USB: 1  📲 WiFi: 1  📶 Net: 2│
│ 📶 NET   192.168.1.10  router   │  │                                   │
│ 📶 NET   192.168.1.22  laptop   │  │ Ready.                            │
└─────────────────────────────────┘  └───────────────────────────────────┘
  [🔍 Scan All]  [🔌 Scan USB]  [🖥️ Mirror]  [📁 Inject]
```

---

## 🛠️ Installation

### 1. Clone the repo
```bash
git clone https://github.com/cyber-vector/vector-rat.git
cd vector-rat
```

### 2. Install system dependencies

**Debian / Ubuntu / Kali:**
```bash
sudo apt update
sudo apt install -y arp-scan adb scrcpy python3-pip
```

**Arch / Manjaro:**
```bash
sudo pacman -S arp-scan android-tools scrcpy python-pip
```

**Termux (Android):**
```bash
pkg install arp-scan android-tools python
# Note: scrcpy is not available in Termux
```

### 3. Install Python dependencies
```bash
pip install textual netifaces
# Optional (recommended fallback for network scan):
pip install scapy
```

---

## ▶️ Usage

Run with **root** (required for ARP scanning):

```bash
sudo python3 RAT.py
```

### Typical workflow

**🖥️ Mirror an Android phone (USB → Wi-Fi)**

1. Enable **Developer Options** → **USB Debugging** on your phone.
2. Plug it in via USB.
3. Launch `vector-rat`, click **🔌 Scan USB/WiFi**.
4. Select your phone → click **🖥️ Mirror Selected**.
5. It launches `scrcpy` and enables `adb tcpip 5555`.
6. Unplug the USB — **mirroring continues wirelessly**.

**📁 Push media to a device**

1. Select an Android device.
2. Click **📁 Inject Media**.
3. Enter the local file path (e.g. `/home/user/clip.mp4`).
4. The file is pushed to `/sdcard/DCIM/` and opened automatically.

**🌐 Discover devices on your LAN**

1. Click **🔍 Scan All**.
2. Every live host appears with IP, MAC, and hostname (if resolvable).

---

## ⌨️ Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `↑` / `↓` | Navigate device list |
| `Tab` | Move between panels |
| `Ctrl+C` | Quit |

---

## 📋 Requirements

| Component | Purpose | Install |
|-----------|---------|---------|
| `adb` | Talk to Android devices | `sudo apt install adb` |
| `scrcpy` | Screen mirroring | `sudo apt install scrcpy` |
| `arp-scan` | Fast LAN discovery | `sudo apt install arp-scan` |
| `python3` | Runtime | Built-in |
| `textual` | TUI framework | `pip install textual` |
| `netifaces` | Interface detection | `pip install netifaces` |
| `scapy` | Fallback scanner | `pip install scapy` |

---

## 🗂️ Project Structure

```
vector-rat/
└── RAT.py      # Entire app — single file, no config, no build
```

Yes, really — **one file**. Just drop it anywhere and run.

---

## 🔒 Safety & Ethics

This tool is intended for **authorized use only**:

- ✅ Your own devices
- ✅ Devices you have **explicit written permission** to test
- ✅ Lab environments, CTFs, and personal testing
- ❌ Devices you don't own or don't have permission to access

The tool uses **standard Android tooling** (`adb`, `scrcpy`) which requires the target device to have **USB debugging explicitly enabled by the user** — this is a security control, not a bypass. It does not exploit vulnerabilities.

---

## 🐛 Troubleshooting

| Problem | Fix |
|---------|-----|
| `arp-scan not found` | `sudo apt install arp-scan` |
| `scrcpy: command not found` | `sudo apt install scrcpy` |
| `Missing: No module named 'textual'` | `pip install textual netifaces` |
| Phone not appearing after USB connect | Enable **USB Debugging**, tap **Allow** on phone |
| Mirror over Wi-Fi fails | Plug USB first, mirror once, then unplug |
| `Requires root` error | Run with `sudo` |

---

## 🗺️ Roadmap

- [ ] iOS support via `libimobiledevice`
- [ ] Multi-device mirroring (grid view)
- [ ] File browser for remote device
- [ ] Shell command runner per device
- [ ] Saved device profiles
- [ ] Dark / light theme toggle
- [ ] Windows support via WSL

---

## 🤝 Contributing

PRs welcome! If you want to add a feature:

1. Fork the repo
2. Create a branch: `git checkout -b feature/my-feature`
3. Commit changes: `git commit -m "Add my feature"`
4. Push: `git push origin feature/my-feature`
5. Open a Pull Request

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## ⭐ Credits

- [Textual](https://github.com/Textualize/textual) — beautiful TUIs
- [scrcpy](https://github.com/Genymobile/scrcpy) — screen mirroring
- [ADB](https://developer.android.com/studio/command-line/adb) — Android Debug Bridge
- [arp-scan](https://github.com/royhills/arp-scan) — LAN discovery

---

<p align="center">
  <b>Built for terminal lovers. ⚡</b><br>
  <i>Star this repo if it saved you time.</i>
</p>
