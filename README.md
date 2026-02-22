# GhostShift v2.1

> Advanced IP Rotation & Anonymity Tool — Powered by the Tor Network

GhostShift is a terminal-based anonymity tool that routes your traffic through the **Tor network**, masking your real IP address with a different exit node identity. It features a rich, color-coded CLI with an interactive menu, step-by-step setup wizard, auto-rotation, DNS leak testing, and session history — all from a single Python script.

---

## Features

- **Check Current IP** — Fetch your active Tor exit IP with full geolocation info (country, city, ISP, ASN, coordinates)
- **Rotate IP Once** — Send a NEWNYM signal to Tor and instantly get a fresh circuit and exit IP
- **Auto-Rotate** — Rotate on a configurable timer (e.g. every 60 seconds), indefinitely or for N cycles
- **DNS Leak Test** — Verify that DNS queries are resolving inside Tor and not exposing your real IP
- **Active Circuits View** — Inspect all currently built Tor circuits and their relay fingerprints
- **Real IP Reveal** — Bypass Tor temporarily to confirm your actual public IP
- **Tor Status & Auto-Start** — Diagnose Tor health and attempt to start it automatically if offline
- **Session History** — Log every IP seen during a session with timestamps and geolocation
- **Session Statistics** — Track rotation count, success rate, countries visited, and session duration
- **Anonymity Grading** — Each IP gets a score and letter grade (A+ → C) based on proxy/hosting flags
- **Interactive Help Wizard** — OS-aware setup guide that walks you through installation step by step
- **Configurable Settings** — Adjust SOCKS/control ports, auth password, and request timeout at runtime

---

## Requirements

- Python 3.8+
- Tor installed and running on your system

### Python Dependencies

```bash
pip install requests[socks] stem rich pyfiglet
```

> GhostShift will attempt to auto-install missing packages on first launch.

---

## Installation & Setup

### Linux (Debian / Ubuntu)

```bash
sudo apt update && sudo apt install tor -y
```

Edit `/etc/tor/torrc` and add (or uncomment):

```
ControlPort 9051
CookieAuthentication 1
```

```bash
sudo systemctl enable tor
sudo systemctl restart tor
```

If authentication fails, add your user to the Tor group:

```bash
sudo usermod -aG debian-tor $USER   # debian-tor on Ubuntu, tor on Fedora/Arch
```

Then log out and back in.

### Linux (Fedora / Arch)

```bash
# Fedora
sudo dnf install tor -y

# Arch
sudo pacman -S tor --noconfirm
```

Same torrc edits and systemctl commands apply.

### Windows

1. Download the **Tor Expert Bundle** (not the Tor Browser) from [torproject.org/download/tor](https://www.torproject.org/download/tor/)
2. Extract to `C:\tor\`
3. Create `C:\tor\Data\Tor\torrc` with:

```
SocksPort 9050
ControlPort 9051
CookieAuthentication 1
```

4. Start Tor:

```cmd
cd C:\tor\Tor
tor.exe -f ..\Data\Tor\torrc
```

5. To run Tor as a background Windows Service:

```cmd
tor.exe --service install -options -f C:\tor\Data\Tor\torrc
net start tor
```

---

## Usage

```bash
python ip_changer.py
```

GhostShift will launch an interactive menu. Use the key shown in brackets to select any option.

```
[1]  Check Current IP          [7]  Tor Status / Start Tor
[2]  Rotate IP Once            [8]  View History
[3]  Auto-Rotate IP            [9]  Session Statistics
[4]  DNS Leak Test             [S]  Settings
[5]  Active Tor Circuits       [H]  Help & Tutorial
[6]  Show Real IP (no Tor)     [0]  Exit
```

---

## Help & Tutorial (In-App)

Press **H** from the main menu to open the interactive help wizard. It asks for your OS and preferences before showing anything, so you only see steps relevant to your setup.

Topics covered:
- How GhostShift and Tor work together
- Linux setup (per-distro: Debian, Fedora, Arch)
- Windows setup (Expert Bundle or Windows Service)
- Troubleshooting (port offline, control port closed, auth errors, IP not changing, DNS leaks)
- Full menu reference table
- Quick-start checklist to verify everything is working

---

## Configuration

Default values can be changed at runtime via **Settings (S)**:

| Setting | Default | Description |
|---|---|---|
| `TOR_SOCKS_PORT` | `9050` | Port Tor listens on for SOCKS5 traffic |
| `TOR_CONTROL_PORT` | `9051` | Port used to send signals to Tor |
| `TOR_PASSWORD` | _(empty)_ | Leave empty to use cookie authentication |
| `TOR_TIMEOUT` | `10s` | Request timeout for Tor-routed connections |
| `LOG_FILE` | `ghostshift_history.json` | File where session history is saved |

To use password authentication instead of cookies, generate a hash:

```bash
tor --hash-password YourPassword
```

Add to `torrc`:

```
HashedControlPassword 16:YOURHASHHERE
```

Then set the password in GhostShift Settings.

---

## How Tor Ports Work

| Port | Name | Purpose |
|---|---|---|
| `9050` | SOCKS5 Proxy | All traffic is routed through this port |
| `9051` | Control Port | Used to send NEWNYM (rotate IP) and query circuits |

Port `9050` is required for everything. Port `9051` is required for IP rotation (options 2, 3, and 5).

---

## Troubleshooting

**Tor not detected**
Run `sudo systemctl status tor` (Linux) or check that `tor.exe` is still running (Windows). Use option **7** in GhostShift to auto-start Tor.

**Control port 9051 closed**
Add `ControlPort 9051` and `CookieAuthentication 1` to your `torrc`, then restart Tor.

**Authentication failed**
Add your user to the `debian-tor` / `tor` group (Linux), or switch to password auth via Settings.

**IP not changing after rotation**
Tor enforces a minimum 10-second wait between NEWNYM signals. GhostShift handles this automatically — if the IP still doesn't change, try again after 30 seconds. Some exit nodes are reused by design.

**DNS leak detected**
Set your system DNS to `127.0.0.1` or use `DNS=127.0.0.1` in `/etc/systemd/resolved.conf` (Linux). GhostShift itself uses `socks5h://` which resolves DNS inside Tor — a leak usually means another application is bypassing the proxy.

---

## Disclaimer

GhostShift is intended for **educational purposes**, **privacy research**, and **legitimate anonymity use cases** only. Routing traffic through Tor does not make you completely anonymous. Do not use this tool for illegal activities. The Tor network has limitations — exit nodes can be monitored, and timing attacks exist.

---

## License

MIT License. See `LICENSE` for details.
