<div align="center">

<img src="https://readme-typing-svg.demolab.com?font=JetBrains+Mono&weight=800&size=42&pause=1000&color=00D9FF&center=true&vCenter=true&width=600&height=80&lines=GhostShift+v2.1" alt="GhostShift" />

**Terminal-based IP anonymization tool powered by the Tor network.**  
Rotate identities, test for leaks, inspect circuits — all from a single Python script.

<br/>

[![Python](https://img.shields.io/badge/Python-3.8%2B-00D9FF?style=for-the-badge&logo=python&logoColor=white&labelColor=0d1117)](https://python.org)
[![Tor](https://img.shields.io/badge/Powered_by-Tor-7D4698?style=for-the-badge&logo=torproject&logoColor=white&labelColor=0d1117)](https://torproject.org)
[![License](https://img.shields.io/badge/License-MIT-39FF14?style=for-the-badge&labelColor=0d1117)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20Windows-FF6B35?style=for-the-badge&labelColor=0d1117)](https://github.com)
[![Rich](https://img.shields.io/badge/UI-Rich%20TUI-BF5FFF?style=for-the-badge&labelColor=0d1117)](https://github.com/Textualize/rich)

<br/>

```
   ______           __  _____ __    _ ______
  / ____/  ____    / / / ___// /_  (_) __/ /_
 / / __ / / __ \  / /  \__ \/ __ \/ / /_/ __/
/ /_/ / / / / / // /  ___/ / / / / / __/ /_
\____/ /_/ /_/ /___/ /____/_/ /_/_/_/  \__/
```

</div>

---

## ⚡ What is GhostShift?

GhostShift masks your real IP address by routing all traffic through the **Tor anonymity network**, giving you a different exit identity every time you rotate. Built for privacy researchers, developers, and anyone who needs reliable, scriptable IP rotation without a browser.

> Every rotation = a new country, a new ISP, a new you.

---

## ✦ Features

<table>
<tr>
<td width="50%">

**🔍 Identity & Verification**
- Live exit IP with geolocation (city, ISP, ASN)
- Anonymity score & letter grade per IP
- Direct real-IP reveal (no Tor bypass)
- DNS leak detection with per-query analysis

</td>
<td width="50%">

**🔄 Rotation Engine**
- One-click manual IP rotation via NEWNYM
- Auto-rotate on a configurable timer
- Infinite loop or fixed rotation count
- Live rotation log with country tracking

</td>
</tr>
<tr>
<td width="50%">

**🛡️ Network Inspection**
- View all active Tor circuits
- Relay fingerprint path visualization
- Per-circuit status and purpose labels
- Control port health diagnostics

</td>
<td width="50%">

**📊 Session Tracking**
- Full IP history with timestamps
- Session stats (rotations, success rate, countries)
- Export history to JSON
- Persistent log across restarts

</td>
</tr>
</table>

---

## 🖥️ Preview

```
╔══════════════════════════════════════════════════════════════════════╗
║                      ⬡  Current Identity                            ║
╠══════════════════════════════════════════════════════════════════════╣
║  IP Address    185.220.101.47       Grade: A+  (100/100)            ║
║  Location      Frankfurt, Hesse, Germany  (DE)                      ║
║  Coordinates   50.1109 N, 8.6821 E   TZ: Europe/Berlin              ║
║  ISP           Hetzner Online GmbH                                   ║
║  Organization  AS24940 Hetzner Online GmbH                          ║
║  Routed via    ✓ Tor Network                                        ║
║  Timestamp     2025-02-22  14:33:07                                 ║
╚══════════════════════════════════════════════════════════════════════╝

  Session: 0:04:21  |  Rotations: 7  |  Failed: 0  |  Countries: 5  |  Tor: ONLINE
```

---

## 🚀 Quick Start

### 1 — Install Tor

<details>
<summary><b>🐧 Debian / Ubuntu</b></summary>

```bash
sudo apt update && sudo apt install tor -y
```

Edit `/etc/tor/torrc` and add:
```
ControlPort 9051
CookieAuthentication 1
```

```bash
sudo systemctl enable tor && sudo systemctl restart tor
```

If authentication fails, add your user to the Tor group:
```bash
sudo usermod -aG debian-tor $USER
```

</details>

<details>
<summary><b>🐧 Fedora / Arch Linux</b></summary>

```bash
# Fedora
sudo dnf install tor -y

# Arch
sudo pacman -S tor --noconfirm
```

Edit `/etc/tor/torrc`, add `ControlPort 9051` and `CookieAuthentication 1`, then:
```bash
sudo systemctl enable tor && sudo systemctl restart tor
```

</details>

<details>
<summary><b>🪟 Windows</b></summary>

1. Download the **[Tor Expert Bundle](https://www.torproject.org/download/tor/)** — not the Tor Browser
2. Extract to `C:\tor\`
3. Create `C:\tor\Data\Tor\torrc`:

```
SocksPort 9050
ControlPort 9051
CookieAuthentication 1
```

4. Start Tor in a terminal window:
```cmd
cd C:\tor\Tor
tor.exe -f ..\Data\Tor\torrc
```

**Optional — run as a Windows Service:**
```cmd
tor.exe --service install -options -f C:\tor\Data\Tor\torrc
net start tor
```

</details>

### 2 — Install Python Dependencies

```bash
pip install requests[socks] stem rich pyfiglet
```

> GhostShift auto-installs any missing packages on first launch.

### 3 — Run

```bash
python ip_changer.py
```

---

## 🗂️ Menu Reference

| Key | Option | Needs Port 9051? |
|:---:|--------|:----------------:|
| `1` | Check Current IP | — |
| `2` | Rotate IP Once | ✓ |
| `3` | Auto-Rotate IP | ✓ |
| `4` | DNS Leak Test | — |
| `5` | Active Tor Circuits | ✓ |
| `6` | Show Real IP (no Tor) | — |
| `7` | Tor Status / Start Tor | — |
| `8` | View History | — |
| `9` | Session Statistics | — |
| `S` | Settings | — |
| `H` | Help & Tutorial | — |
| `0` | Exit | — |

---

## 🧩 Interactive Help Wizard

Press **`H`** from the main menu to open the built-in setup wizard. It asks for your OS and preferences first, then walks you through installation one step at a time — no scrolling walls of irrelevant text.

```
What would you like help with?

  [O]  Overview              -- How GhostShift and Tor work together
  [L]  Linux Setup           -- Step-by-step install guide for Linux
  [W]  Windows Setup         -- Step-by-step install guide for Windows
  [T]  Troubleshooting       -- Fix common problems (ports, auth, leaks)
  [M]  Menu Reference        -- What every menu option does
  [C]  Quick-Start Checklist -- Verify everything is configured correctly
  [B]  Back to Main Menu
```

---

## ⚙️ Configuration

All settings are adjustable live via **`S`** — no config file required.

| Setting | Default | Description |
|---------|---------|-------------|
| `TOR_SOCKS_PORT` | `9050` | SOCKS5 proxy — all traffic routes through here |
| `TOR_CONTROL_PORT` | `9051` | Control port — needed for rotation & circuit inspection |
| `TOR_PASSWORD` | *(empty)* | Leave empty to use cookie authentication |
| `TOR_TIMEOUT` | `10s` | Timeout for Tor-routed HTTP requests |
| `LOG_FILE` | `ghostshift_history.json` | Session history export path |

**Password auth setup (alternative to cookies):**

```bash
tor --hash-password YourPassword
```

Add to `torrc`:
```
HashedControlPassword 16:YOURHASHHERE
```

Then go to GhostShift → `S` Settings → enter your password.

---

## 🔧 Troubleshooting

<details>
<summary><b>Tor not detected on port 9050</b></summary>

```bash
# Check status
sudo systemctl status tor

# Start Tor
sudo systemctl start tor

# Read error logs
sudo journalctl -u tor -n 30
```

Windows: ensure `tor.exe` is still running, or use `net start tor` for service installs. Use option **7** in GhostShift for auto-start.

</details>

<details>
<summary><b>Control port 9051 is closed</b></summary>

The control port is disabled by default. Add to `torrc`:

```
ControlPort 9051
CookieAuthentication 1
```

Restart Tor, then try again.

</details>

<details>
<summary><b>Authentication failed (cookie error)</b></summary>

```bash
# Debian / Ubuntu
sudo usermod -aG debian-tor $USER

# Fedora / Arch
sudo usermod -aG tor $USER
```

Log out and back in, then restart Tor. Or use password auth — see Configuration above.

</details>

<details>
<summary><b>IP not changing after rotation</b></summary>

Tor enforces a minimum 10-second cooldown between NEWNYM signals. GhostShift handles the wait automatically. If the IP still looks the same after 30 seconds, try rotating again — Tor may have intentionally reused an exit node when the pool is limited.

</details>

<details>
<summary><b>DNS leak detected</b></summary>

GhostShift uses `socks5h://` which resolves DNS inside Tor. A leak typically means another app is bypassing the proxy.

```bash
# Linux fix — /etc/systemd/resolved.conf
DNS=127.0.0.1

sudo systemctl restart systemd-resolved
```

Windows: set your network adapter DNS to `127.0.0.1` in system settings.

</details>

---

## 🏗️ Architecture

```
ip_changer.py
├── Tor Interface     stem          NEWNYM signals, circuit queries
├── IP Resolution     requests      Routed through socks5h://127.0.0.1:9050
├── Geolocation       ip-api.com    Country, city, ISP, ASN, proxy flags
├── DNS Leak Check    ipleak.net    Verify DNS resolves inside Tor
├── TUI               Rich          Panels, tables, progress bars, spinners
├── Session State     deque         In-memory history, stats, country tracking
└── Persistence       JSON          Export to ghostshift_history.json
```

---

## 📋 Requirements

| | Details |
|--|---------|
| **Python** | 3.8 or higher |
| **Tor** | Any recent version, SOCKS5 on port 9050 |
| **Control Port** | 9051 — optional, required for IP rotation |
| **OS** | Linux · Windows · macOS *(Tor installed separately)* |
| **pip packages** | `requests[socks]` `stem` `rich` `pyfiglet` |

---

## ⚠️ Disclaimer

GhostShift is intended for **educational purposes**, **privacy research**, and **legitimate anonymity use cases** only. Tor does not guarantee complete anonymity — exit nodes can be monitored and timing attacks exist. You are solely responsible for how you use this tool.

---

## 📄 License

Released under the **MIT License** — see [`LICENSE`](LICENSE) for details.

---

<div align="center">

<br/>

*Stay anonymous. Stay safe.*

</div>
