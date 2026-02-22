#!/usr/bin/env python3
"""
GhostShift v2.1 -- Advanced IP Rotation & Anonymity Tool
Powered by Tor Network | Built with Rich + PyFiglet
"""

import sys
import os
import subprocess

REQUIRED = {
    "requests": "requests[socks]",
    "stem":     "stem",
    "rich":     "rich",
    "pyfiglet": "pyfiglet",
}

def _auto_install():
    missing = []
    for mod, pkg in REQUIRED.items():
        try:
            __import__(mod)
        except ImportError:
            missing.append(pkg)
    if missing:
        print(f"\n[GhostShift] Installing: {', '.join(missing)}\n")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--quiet"] + missing
        )
        print("\n[GhostShift] Done. Restarting...\n")
        os.execv(sys.executable, [sys.executable] + sys.argv)

_auto_install()

import time
import socket
import platform
import json
import re
from datetime import datetime, timedelta
from collections import deque
from typing import Optional, List, Dict, Tuple

import requests
from stem import Signal, CircStatus
from stem.control import Controller
import pyfiglet

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, IntPrompt, Confirm
from rich.progress import (
    Progress, SpinnerColumn, TextColumn,
    BarColumn, TaskProgressColumn, TimeRemainingColumn,
)
from rich.align import Align
from rich import box
from rich.rule import Rule
from rich.columns import Columns
from rich.markup import escape
from rich.traceback import install as rich_traceback_install
from rich.logging import RichHandler
import logging

rich_traceback_install(show_locals=False)
logging.basicConfig(
    level=logging.WARNING,
    format="%(message)s",
    handlers=[RichHandler(rich_tracebacks=True, show_path=False)],
)
log = logging.getLogger("ghostshift")

console = Console(highlight=False)

P = {
    "primary":  "#00D9FF",
    "accent":   "#FF6B35",
    "success":  "#39FF14",
    "danger":   "#FF2D55",
    "warn":     "#FFD700",
    "muted":    "#6B7280",
    "dim":      "#3D4451",
    "white":    "#E8EAF0",
    "purple":   "#BF5FFF",
    "teal":     "#00FFBF",
}

TOR_SOCKS_PORT   = 9050
TOR_CONTROL_PORT = 9051
TOR_PASSWORD     = ""
TOR_TIMEOUT      = 10
DIRECT_TIMEOUT   = 8
MAX_HISTORY      = 100
NEWNYM_WAIT      = 5
LOG_FILE         = "ghostshift_history.json"

PROXIES = {
    "http":  f"socks5h://127.0.0.1:{TOR_SOCKS_PORT}",
    "https": f"socks5h://127.0.0.1:{TOR_SOCKS_PORT}",
}

IP_CHECK_URLS = [
    "https://api.ipify.org?format=json",
    "https://api64.ipify.org?format=json",
    "https://httpbin.org/ip",
    "https://checkip.amazonaws.com",
]

GEO_URL = (
    "http://ip-api.com/json/{ip}"
    "?fields=status,country,countryCode,region,regionName,"
    "city,isp,org,as,lat,lon,timezone,mobile,proxy,hosting"
)

session_stats: Dict = {
    "start_time":     datetime.now(),
    "rotations":      0,
    "failed":         0,
    "countries_seen": set(),
}
ip_history: deque = deque(maxlen=MAX_HISTORY)

def render_banner() -> str:
    font = "slant"
    try:
        fig = pyfiglet.figlet_format("GhostShift", font=font, width=110)
    except pyfiglet.FontNotFound:
        fig = pyfiglet.figlet_format("GhostShift", width=110)

    gradient = [
        P["primary"], P["primary"],
        "#00B8D9", "#009BB5", "#007A91", P["muted"],
    ]
    lines = fig.rstrip().split("\n")
    colored = []
    for i, line in enumerate(lines):
        color = gradient[min(i, len(gradient) - 1)]
        colored.append(f"[{color}]{escape(line)}[/]")
    return "\n".join(colored)


SUBTITLE = (
    f"[bold {P['accent']}]"
    f"[ v2.1 ]  IP Rotation & Anonymity Platform  |  Powered by Tor"
    f"[/]"
)


def is_tor_running() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", TOR_SOCKS_PORT), timeout=2):
            return True
    except OSError:
        return False


def is_control_port_open() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", TOR_CONTROL_PORT), timeout=2):
            return True
    except OSError:
        return False


def get_tor_controller() -> Optional[Controller]:
    if not is_control_port_open():
        return None
    try:
        ctrl = Controller.from_port(port=TOR_CONTROL_PORT)
        if TOR_PASSWORD:
            ctrl.authenticate(password=TOR_PASSWORD)
        else:
            ctrl.authenticate()
        return ctrl
    except Exception as exc:
        log.warning(f"Controller auth failed: {exc}")
        return None


def get_tor_version() -> str:
    try:
        ctrl = get_tor_controller()
        if ctrl:
            v = ctrl.get_version()
            ctrl.close()
            return str(v)
    except Exception:
        pass
    return "Unknown"


def get_tor_circuits() -> List[Dict]:
    circuits = []
    try:
        ctrl = get_tor_controller()
        if not ctrl:
            return circuits
        for circ in ctrl.get_circuits():
            if circ.status == CircStatus.BUILT:
                path = " -> ".join(
                    fp[:8] for fp, _ in circ.path
                ) if circ.path else "-"
                circuits.append({
                    "id":      circ.id,
                    "status":  str(circ.status).split(".")[-1],
                    "path":    path,
                    "purpose": str(circ.purpose).split(".")[-1],
                })
        ctrl.close()
    except Exception as exc:
        log.debug(f"Circuits error: {exc}")
    return circuits


def rotate_ip() -> Tuple[bool, str]:
    if not is_control_port_open():
        return False, "Control port not reachable. Add 'ControlPort 9051' to torrc."
    try:
        ctrl = get_tor_controller()
        if ctrl is None:
            return False, "Authentication failed. Check TOR_PASSWORD or cookie auth."
        wait = NEWNYM_WAIT
        try:
            wait = ctrl.get_newnym_wait()
        except Exception:
            pass
        ctrl.signal(Signal.NEWNYM)
        ctrl.close()
        time.sleep(max(float(wait), float(NEWNYM_WAIT)))
        return True, ""
    except Exception as exc:
        return False, str(exc)


def start_tor() -> bool:
    candidates = ["tor"] if platform.system() != "Windows" else ["tor.exe", "tor"]
    for cmd in candidates:
        try:
            subprocess.Popen(
                [cmd],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            for _ in range(20):
                time.sleep(1)
                if is_tor_running():
                    return True
        except FileNotFoundError:
            continue
    return False


def fetch_ip(use_tor: bool = True) -> Optional[str]:
    proxies = PROXIES if use_tor else {}
    timeout = TOR_TIMEOUT if use_tor else DIRECT_TIMEOUT
    for url in IP_CHECK_URLS:
        try:
            r = requests.get(url, proxies=proxies, timeout=timeout)
            r.raise_for_status()
            text = r.text.strip()
            try:
                data = r.json()
                ip = data.get("ip") or data.get("origin", "").split(",")[0].strip()
                if ip:
                    return ip
            except Exception:
                pass
            if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", text):
                return text
        except Exception:
            continue
    return None


def fetch_geo(ip: str, use_tor: bool = True) -> Dict:
    proxies = PROXIES if use_tor else {}
    timeout = TOR_TIMEOUT if use_tor else DIRECT_TIMEOUT
    try:
        r = requests.get(GEO_URL.format(ip=ip), proxies=proxies, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        if data.get("status") == "success":
            return data
    except Exception:
        pass
    return {}


def get_full_identity(use_tor: bool = True) -> Dict:
    ip = fetch_ip(use_tor=use_tor)
    if not ip:
        return {"ip": None, "geo": {}, "success": False, "use_tor": use_tor}
    geo = fetch_geo(ip, use_tor=use_tor)
    return {"ip": ip, "geo": geo, "success": True, "use_tor": use_tor}


def check_dns_leak(use_tor: bool = True) -> List[str]:
    results = []
    proxies = PROXIES if use_tor else {}
    try:
        r = requests.get(
            "https://ipleak.net/json/",
            proxies=proxies,
            timeout=TOR_TIMEOUT,
        )
        data = r.json()
        ip = data.get("ip")
        if ip:
            results.append(ip)
    except Exception:
        pass
    return results


def anonymity_score(geo: Dict) -> Tuple[int, str]:
    score = 100
    if geo.get("proxy"):
        score -= 10
    if geo.get("mobile"):
        score -= 5
    if not geo:
        score = 50
    grade = (
        "A+" if score >= 95
        else "A"  if score >= 85
        else "B"  if score >= 70
        else "C"
    )
    return score, grade


def save_history():
    try:
        with open(LOG_FILE, "w") as f:
            json.dump(list(ip_history), f, indent=2, default=str)
    except Exception as exc:
        log.warning(f"Could not save history: {exc}")


def load_history():
    if not os.path.exists(LOG_FILE):
        return
    try:
        with open(LOG_FILE) as f:
            data = json.load(f)
        for entry in data[-MAX_HISTORY:]:
            ip_history.append(entry)
    except Exception as exc:
        log.warning(f"Could not load history: {exc}")


def clear_screen():
    os.system("cls" if platform.system() == "Windows" else "clear")


def status_label(online: bool) -> str:
    if online:
        return f"[bold {P['success']}]ONLINE[/]"
    return f"[bold {P['danger']}]OFFLINE[/]"


def grade_color(grade: str) -> str:
    return (
        P["success"] if grade in ("A+", "A")
        else P["warn"]   if grade == "B"
        else P["danger"]
    )


def header(tor_online: bool = False):
    clear_screen()
    console.print(Align.center(render_banner()))
    console.print(Align.center(SUBTITLE))
    console.print(
        Align.center(
            f"[{P['muted']}]Python {sys.version.split()[0]}  |"
            f"  {platform.system()} {platform.release()}  |"
            f"  {datetime.now().strftime('%Y-%m-%d')}[/]"
        )
    )
    console.print()
    console.print(Rule(style=P["primary"]))

    elapsed = str(timedelta(seconds=int(
        (datetime.now() - session_stats["start_time"]).total_seconds()
    )))
    console.print(
        Align.center(
            f"[{P['muted']}]"
            f"Session: [{P['warn']}]{elapsed}[/{P['warn']}]  |  "
            f"Rotations: [{P['success']}]{session_stats['rotations']}[/{P['success']}]  |  "
            f"Failed: [{P['danger']}]{session_stats['failed']}[/{P['danger']}]  |  "
            f"Countries: [{P['teal']}]{len(session_stats['countries_seen'])}[/{P['teal']}]  |  "
            f"Tor: {status_label(tor_online)}"
            f"[/]"
        )
    )
    console.print(Rule(style=P["dim"]))
    console.print()


def section_rule(title: str):
    console.print(Rule(f"[bold {P['primary']}] {title} [/]", style=P["dim"]))
    console.print()


def ok_msg(msg: str):
    console.print(f"[bold {P['success']}]  [OK]  {msg}[/]")


def err_msg(msg: str):
    console.print(f"[bold {P['danger']}]  [!!]  {msg}[/]")


def info_msg(msg: str):
    console.print(f"[{P['muted']}]  [--]  {msg}[/]")


def warn_panel(msg: str, title: str = "Warning"):
    console.print(
        Panel(
            f"[{P['danger']}]{msg}[/]",
            border_style=P["danger"],
            title=f"[bold {P['danger']}] !! {title} [/]",
            padding=(0, 3),
        )
    )


def press_enter():
    console.print()
    console.input(f"  [{P['muted']}]Press Enter to return to menu...[/]")


def spinner_countdown(message: str, seconds: int):
    with Progress(
        SpinnerColumn(spinner_name="dots12", style=P["primary"]),
        TextColumn(f"[{P['muted']}]{message}[/]"),
        BarColumn(bar_width=30, style=P["dim"], complete_style=P["primary"]),
        TaskProgressColumn(style=P["muted"]),
        TimeRemainingColumn(style=P["warn"]),
        transient=True,
        console=console,
    ) as prog:
        task = prog.add_task("", total=seconds)
        for _ in range(seconds):
            time.sleep(1)
            prog.advance(task)


def identity_panel(info: Dict, label: str = "Current Identity") -> Panel:
    ip      = info.get("ip") or "N/A"
    geo     = info.get("geo", {})
    success = info.get("success", False)
    via_tor = info.get("use_tor", True)

    score, gr = anonymity_score(geo)
    gc = grade_color(gr)

    grid = Table.grid(padding=(0, 2))
    grid.add_column(style=f"bold {P['muted']}", justify="right", width=16)
    grid.add_column(style=f"bold {P['white']}", width=55)

    grid.add_row(
        "IP Address",
        f"[bold {P['primary']}]{escape(ip)}[/]"
        f"   [{gc}]Grade: {gr}  ({score}/100)[/]",
    )

    if geo:
        city    = geo.get("city",       "?")
        region  = geo.get("regionName", "")
        country = geo.get("country",    "?")
        cc      = geo.get("countryCode","")
        tz      = geo.get("timezone",   "-")
        lat     = geo.get("lat",        "")
        lon     = geo.get("lon",        "")
        isp     = geo.get("isp",        "-")
        org     = geo.get("org",        "-")
        asn     = geo.get("as",         "-")
        proxy   = geo.get("proxy",      False)
        hosting = geo.get("hosting",    False)

        loc_str = ", ".join(filter(None, [city, region, country]))
        if cc:
            loc_str += f"  [{P['muted']}]({cc})[/]"

        grid.add_row("Location",    loc_str)
        grid.add_row("Coordinates", f"[{P['muted']}]{lat} N, {lon} E   TZ: {tz}[/]")
        grid.add_row("ISP",         escape(isp))
        grid.add_row("Organization",escape(org))
        grid.add_row("ASN",         f"[{P['muted']}]{escape(asn)}[/]")

        flags = []
        if proxy:   flags.append(f"[{P['warn']}][PROXY][/]")
        if hosting: flags.append(f"[{P['teal']}][HOSTING][/]")
        if flags:
            grid.add_row("Flags", "  ".join(flags))

    grid.add_row(
        "Routed via",
        f"[bold {P['success']}]Tor Network[/]"
        if via_tor else f"[bold {P['danger']}]Direct Connection (no Tor)[/]",
    )
    grid.add_row(
        "Timestamp",
        f"[{P['muted']}]{datetime.now().strftime('%Y-%m-%d  %H:%M:%S')}[/]",
    )

    border = P["primary"] if success else P["danger"]
    return Panel(
        Align.center(grid),
        title=f"[bold {P['accent']}]  {label}  [/]",
        border_style=border,
        padding=(1, 4),
        box=box.DOUBLE_EDGE,
    )


def action_check_ip():
    section_rule("Check Current IP")
    info_msg("Connecting through Tor network...")
    with console.status(f"[{P['primary']}]Fetching IP...", spinner="dots"):
        info = get_full_identity(use_tor=True)

    if not info["success"]:
        err_msg("Could not retrieve IP. Is Tor running?")
        return

    console.print(identity_panel(info))

    ip_history.append({
        "timestamp": datetime.now().isoformat(),
        "ip": info["ip"],
        "geo": info["geo"],
        "action": "check",
    })
    if info["geo"].get("countryCode"):
        session_stats["countries_seen"].add(info["geo"]["countryCode"])


def action_rotate():
    section_rule("Rotate IP Once")

    if not is_control_port_open():
        warn_panel(
            "Tor control port (9051) is not open.\n\n"
            "Add to torrc:\n"
            "  ControlPort 9051\n"
            "  CookieAuthentication 1\n\n"
            "Then restart Tor.",
            title="Control Port Required"
        )
        return

    info_msg("Fetching identity before rotation...")
    with console.status(f"[{P['muted']}]Fetching pre-rotation IP...", spinner="point"):
        before = get_full_identity(use_tor=True)

    if before["success"]:
        console.print(identity_panel(before, label="Before Rotation"))

    console.print()
    info_msg("Sending NEWNYM signal to Tor...")
    with console.status(f"[{P['primary']}]Rotating circuit...", spinner="bouncingBall"):
        ok, err = rotate_ip()

    if not ok:
        err_msg(f"Rotation failed: {err}")
        session_stats["failed"] += 1
        return

    ok_msg("Circuit rotated! Fetching new identity...")
    console.print()

    with console.status(f"[{P['primary']}]Fetching new IP...", spinner="dots"):
        after = get_full_identity(use_tor=True)

    if not after["success"]:
        err_msg("Rotation succeeded but could not verify new IP.")
        return

    console.print(identity_panel(after, label="After Rotation -- New Identity"))

    if before["success"] and before["ip"] != after["ip"]:
        ok_msg(
            f"IP changed:  {before['ip']}"
            f"  -->  [{P['primary']}]{after['ip']}[/]"
        )
    elif before["success"]:
        warn_panel(
            "IP did not change. Tor may need more time.\n"
            "Wait a few seconds and try again.",
            title="No Change"
        )

    session_stats["rotations"] += 1
    if after["geo"].get("countryCode"):
        session_stats["countries_seen"].add(after["geo"]["countryCode"])

    ip_history.append({
        "timestamp": datetime.now().isoformat(),
        "ip": after["ip"],
        "geo": after["geo"],
        "action": "rotate",
    })
    save_history()


def action_auto_rotate():
    section_rule("Auto-Rotate IP")

    if not is_control_port_open():
        warn_panel(
            "Control port not available.\n"
            "Auto-rotate requires ControlPort 9051 in torrc.",
            title="Control Port Required"
        )
        return

    console.print(f"[{P['muted']}]  Configure auto-rotation parameters:\n[/]")
    interval = IntPrompt.ask(
        f"  [{P['accent']}]Rotation interval (seconds)[/]", default=60
    )
    count = IntPrompt.ask(
        f"  [{P['accent']}]Number of rotations  (0 = run until Ctrl+C)[/]", default=5
    )
    interval = max(5, interval)

    console.print()
    console.print(
        Panel(
            f"[bold {P['primary']}]Auto-rotation starting[/]\n"
            f"[{P['muted']}]Interval : [bold]{interval}s[/]\n"
            f"Rotations: [bold]{'infinite' if count == 0 else count}[/]\n"
            f"Press Ctrl+C to stop at any time.[/]",
            border_style=P["accent"],
            padding=(0, 3),
        )
    )
    console.print()

    rot_count     = 0
    success_count = 0

    log_table = Table(
        box=box.SIMPLE_HEAVY,
        border_style=P["dim"],
        header_style=f"bold {P['primary']}",
        show_lines=True,
        show_edge=True,
        expand=False,
        min_width=72,
    )
    log_table.add_column("#",         width=4,  justify="right",  style=f"bold {P['warn']}")
    log_table.add_column("IP Address",width=18, justify="left",   style=f"bold {P['success']}")
    log_table.add_column("Location",  width=22, justify="left",   style=P["white"])
    log_table.add_column("ISP",       width=20, justify="left",   style=P["muted"])
    log_table.add_column("Grade",     width=5,  justify="center")
    log_table.add_column("Time",      width=10, justify="right",  style=P["muted"])

    try:
        while True:
            with console.status(
                f"[{P['primary']}]Rotating circuit ({rot_count + 1})...",
                spinner="dots"
            ):
                ok, err = rotate_ip()
                info = get_full_identity(use_tor=True) if ok else {
                    "ip": None, "geo": {}, "success": False
                }

            rot_count += 1
            now_str = datetime.now().strftime("%H:%M:%S")

            if ok and info["success"]:
                success_count += 1
                session_stats["rotations"] += 1
                geo     = info.get("geo", {})
                ip      = info["ip"]
                city    = geo.get("city",    "?")
                country = geo.get("country", "?")
                isp     = (geo.get("isp") or "-")[:20]
                sc, gr  = anonymity_score(geo)
                gc      = grade_color(gr)
                loc_str = f"{city}, {country}"[:22]

                if geo.get("countryCode"):
                    session_stats["countries_seen"].add(geo["countryCode"])

                log_table.add_row(
                    str(rot_count),
                    escape(ip),
                    escape(loc_str),
                    escape(isp),
                    f"[{gc}]{gr}[/]",
                    now_str,
                )
                ip_history.append({
                    "timestamp": datetime.now().isoformat(),
                    "ip": ip, "geo": geo, "action": "auto-rotate",
                })
            else:
                session_stats["failed"] += 1
                log_table.add_row(
                    str(rot_count),
                    f"[{P['danger']}]FAILED[/]",
                    "-", "-", "-", now_str,
                )

            console.print(log_table)
            console.print(
                f"  [{P['muted']}]"
                f"Success: [{P['success']}]{success_count}/{rot_count}[/]  |  "
                f"Countries: [{P['teal']}]{len(session_stats['countries_seen'])}[/]"
                f"[/]"
            )

            if count and rot_count >= count:
                console.print()
                ok_msg(f"Auto-rotate complete: {success_count}/{rot_count} successful.")
                save_history()
                break

            spinner_countdown(f"Next rotation in {interval}s...", interval)

    except KeyboardInterrupt:
        console.print(
            f"\n[bold {P['accent']}]  Stopped.[/]  "
            f"Completed {rot_count} rotation(s), "
            f"[{P['success']}]{success_count}[/] successful."
        )
        save_history()


def action_dns_leak():
    section_rule("DNS Leak Test")
    info_msg("Checking DNS resolution through Tor...")

    with console.status(f"[{P['primary']}]Running DNS leak test...", spinner="dots"):
        leaked_ips = check_dns_leak(use_tor=True)
        real_ip    = fetch_ip(use_tor=False)
        tor_ip     = fetch_ip(use_tor=True)

    table = Table(
        box=box.ROUNDED,
        border_style=P["primary"],
        header_style=f"bold {P['primary']}",
        show_lines=True,
        expand=False,
        min_width=70,
    )
    table.add_column("Check",   width=16, style=P["muted"])
    table.add_column("Result",  width=20)
    table.add_column("Status",  width=30)

    table.add_row(
        "Tor Exit IP",
        f"[bold {P['primary']}]{escape(tor_ip or 'N/A')}[/]",
        f"[{P['success']}][OK] Routed via Tor[/]"
        if tor_ip
        else f"[{P['danger']}][!!] Tor not working[/]",
    )

    leak = bool(real_ip and tor_ip and real_ip == tor_ip)
    table.add_row(
        "Real IP",
        f"[bold {P['danger']}]{escape(real_ip or 'N/A')}[/]",
        f"[{P['danger']}][!!] LEAK -- IPs match![/]"
        if leak
        else f"[{P['success']}][OK] IPs differ (good)[/]",
    )

    if leaked_ips:
        for ip in leaked_ips:
            is_leaked = bool(real_ip and ip == real_ip)
            table.add_row(
                "DNS IP",
                f"[bold]{escape(ip)}[/]",
                f"[{P['danger']}][!!] Leaked[/]"
                if is_leaked
                else f"[{P['teal']}][OK] Via Tor[/]",
            )
    else:
        table.add_row("DNS IP", "[dim]N/A[/]", f"[{P['muted']}]Could not check[/]")

    console.print(table)

    if not leak:
        console.print(
            f"\n  [bold {P['success']}][OK]  No DNS leak detected. You appear anonymous.[/]"
        )
    else:
        warn_panel(
            "Your real IP matches or DNS is leaking!\n"
            "Ensure Tor is set as your system proxy.",
            title="DNS Leak Detected"
        )


def action_circuits():
    section_rule("Active Tor Circuits")

    if not is_control_port_open():
        warn_panel(
            "Control port not available. Cannot list circuits.",
            title="Unavailable"
        )
        return

    with console.status(f"[{P['primary']}]Fetching circuits...", spinner="dots"):
        circuits = get_tor_circuits()

    if not circuits:
        info_msg("No active circuits found.")
        return

    table = Table(
        box=box.SIMPLE_HEAVY,
        border_style=P["primary"],
        header_style=f"bold {P['primary']}",
        show_lines=True,
        expand=False,
        min_width=80,
    )
    table.add_column("ID",      width=6,  justify="right",  style=f"bold {P['warn']}")
    table.add_column("Status",  width=10, justify="center", style=P["success"])
    table.add_column("Purpose", width=14, justify="left",   style=P["teal"])
    table.add_column("Path (fingerprints)", width=55, style=P["muted"])

    for c in circuits:
        table.add_row(
            str(c["id"]),
            c["status"],
            c["purpose"],
            c["path"],
        )

    console.print(table)
    console.print(
        f"\n  [{P['muted']}]Total circuits: "
        f"[bold {P['primary']}]{len(circuits)}[/][/]"
    )


def action_real_ip():
    section_rule("Real IP  (Direct Connection)")
    warn_panel(
        "This will connect DIRECTLY without Tor.\n"
        "Your real IP address will be visible below.",
        title="Privacy Warning"
    )
    console.print()

    if not Confirm.ask(
        f"  [{P['accent']}]Continue and reveal your real IP?[/]", default=False
    ):
        info_msg("Cancelled.")
        return

    with console.status(
        f"[{P['primary']}]Connecting directly (no Tor)...", spinner="dots"
    ):
        info = get_full_identity(use_tor=False)

    if not info["success"]:
        err_msg("Could not retrieve real IP address.")
        return

    console.print(identity_panel(info, label="Real Identity -- Direct Connection"))
    console.print(
        f"\n  [bold {P['danger']}][!!]  This is your actual IP. Handle with care.[/]"
    )


def action_tor_status():
    section_rule("Tor Service Status")

    socks_ok   = is_tor_running()
    control_ok = is_control_port_open()
    version    = get_tor_version() if socks_ok else "-"

    grid = Table.grid(padding=(0, 3))
    grid.add_column(style=f"bold {P['muted']}", justify="right", width=20)
    grid.add_column(width=40)

    grid.add_row("SOCKS Port (9050)",   status_label(socks_ok))
    grid.add_row("Control Port (9051)", status_label(control_ok))
    grid.add_row("Tor Version",         f"[bold {P['white']}]{version}[/]")
    grid.add_row("OS / Platform",
        f"[{P['muted']}]{platform.system()} {platform.release()}[/]")
    grid.add_row("Python",
        f"[{P['muted']}]{sys.version.split()[0]}[/]")

    console.print(Panel(
        Align.center(grid),
        title=f"[bold {P['accent']}]  Service Diagnostics  [/]",
        border_style=P["primary"],
        padding=(1, 3),
    ))

    if not socks_ok:
        console.print()
        warn_panel(
            "Tor SOCKS proxy is not running on port 9050.\n\n"
            "Install Tor:\n"
            "  Linux   :  sudo apt install tor  &&  sudo systemctl start tor\n"
            "  macOS   :  brew install tor  &&  brew services start tor\n"
            "  Windows :  https://www.torproject.org/download/\n\n"
            "Enable control port -- add to torrc:\n"
            "  ControlPort 9051\n"
            "  CookieAuthentication 1\n"
            "Then restart Tor.",
            title="Setup Required"
        )
        console.print()
        if Confirm.ask(
            f"  [{P['accent']}]Attempt to start Tor automatically?[/]", default=False
        ):
            with console.status(
                f"[{P['primary']}]Starting Tor...", spinner="bouncingBall"
            ):
                started = start_tor()
            if started:
                ok_msg("Tor started successfully!")
            else:
                err_msg(
                    "Could not start Tor automatically.\n"
                    "  Please install and start Tor manually."
                )
    elif not control_ok:
        warn_panel(
            "Tor is running but the control port is closed.\n"
            "IP rotation requires the control port.\n\n"
            "Add to torrc:\n"
            "  ControlPort 9051\n"
            "  CookieAuthentication 1\n\n"
            "Then restart Tor.",
            title="Control Port Closed"
        )


def action_history():
    section_rule("Rotation History")

    if not ip_history:
        info_msg("No history recorded yet.")
        return

    entries = list(ip_history)[-50:]

    table = Table(
        box=box.SIMPLE_HEAVY,
        border_style=P["dim"],
        header_style=f"bold {P['primary']}",
        show_lines=True,
        expand=False,
        min_width=78,
    )
    table.add_column("#",         width=4,  justify="right",  style=f"bold {P['warn']}")
    table.add_column("Timestamp", width=17, justify="left",   style=P["muted"])
    table.add_column("IP Address",width=18, justify="left",   style=f"bold {P['primary']}")
    table.add_column("Location",  width=22, justify="left",   style=P["white"])
    table.add_column("Action",    width=12, justify="center")

    action_colors = {
        "rotate":      P["success"],
        "auto-rotate": P["teal"],
        "check":       P["muted"],
    }

    for i, entry in enumerate(reversed(entries), 1):
        geo     = entry.get("geo", {})
        city    = geo.get("city",    "?")
        country = geo.get("country", "?")
        loc_str = f"{city}, {country}"[:22]
        action  = entry.get("action", "-")
        ac      = action_colors.get(action, P["white"])

        ts_raw = entry.get("timestamp", "")
        try:
            ts = datetime.fromisoformat(ts_raw).strftime("%m-%d %H:%M:%S")
        except Exception:
            ts = ts_raw[:16]

        table.add_row(
            str(i),
            ts,
            escape(entry.get("ip") or "-"),
            escape(loc_str),
            f"[{ac}]{action}[/]",
        )

    console.print(table)
    console.print(
        f"\n  [{P['muted']}]"
        f"Showing last {len(entries)} of {len(ip_history)} entries.  "
        f"Countries seen: [{P['teal']}]{len(session_stats['countries_seen'])}[/]"
        f"[/]"
    )

    console.print()
    if Confirm.ask(
        f"  [{P['accent']}]Export full history to {LOG_FILE}?[/]", default=False
    ):
        save_history()
        ok_msg(f"History saved to {LOG_FILE}")


def action_stats():
    section_rule("Session Statistics")

    elapsed = timedelta(seconds=int(
        (datetime.now() - session_stats["start_time"]).total_seconds()
    ))
    total = session_stats["rotations"] + session_stats["failed"]
    rate  = (
        f"{session_stats['rotations'] / total * 100:.1f}%"
        if total > 0 else "N/A"
    )

    grid = Table.grid(padding=(0, 4))
    grid.add_column(style=f"bold {P['muted']}", justify="right", width=22)
    grid.add_column(style=f"bold {P['white']}", width=40)

    grid.add_row("Session Duration",  f"[bold {P['warn']}]{elapsed}[/]")
    grid.add_row("Started At",        session_stats["start_time"].strftime("%Y-%m-%d %H:%M:%S"))
    grid.add_row("Total Rotations",   f"[bold {P['success']}]{session_stats['rotations']}[/]")
    grid.add_row("Failed Rotations",  f"[bold {P['danger']}]{session_stats['failed']}[/]")
    grid.add_row("Success Rate",      f"[bold {P['teal']}]{rate}[/]")
    grid.add_row("Unique Countries",  f"[bold {P['purple']}]{len(session_stats['countries_seen'])}[/]")
    grid.add_row("IPs Logged",        f"[bold {P['primary']}]{len(ip_history)}[/]")
    grid.add_row("History File",      LOG_FILE)

    if session_stats["countries_seen"]:
        cc_list = ", ".join(sorted(session_stats["countries_seen"])[:20])
        if len(session_stats["countries_seen"]) > 20:
            cc_list += "..."
        grid.add_row("Countries", f"[{P['muted']}]{cc_list}[/]")

    console.print(Panel(
        Align.center(grid),
        title=f"[bold {P['accent']}]  Session Report  [/]",
        border_style=P["primary"],
        padding=(1, 4),
        box=box.DOUBLE_EDGE,
    ))


def action_settings():
    global TOR_SOCKS_PORT, TOR_CONTROL_PORT, TOR_PASSWORD, TOR_TIMEOUT

    section_rule("Settings")

    grid = Table.grid(padding=(0, 3))
    grid.add_column(style=f"bold {P['muted']}", justify="right", width=20)
    grid.add_column(style=f"bold {P['white']}", width=40)

    grid.add_row("Tor SOCKS Port",   str(TOR_SOCKS_PORT))
    grid.add_row("Tor Control Port", str(TOR_CONTROL_PORT))
    grid.add_row("Tor Password",     "[dim]set[/]" if TOR_PASSWORD else "[dim]not set (cookie auth)[/]")
    grid.add_row("Request Timeout",  f"{TOR_TIMEOUT}s")
    grid.add_row("History File",     LOG_FILE)

    console.print(Panel(
        Align.center(grid),
        title=f"[bold {P['accent']}]  Current Configuration  [/]",
        border_style=P["primary"],
        padding=(1, 3),
    ))

    console.print()
    if Confirm.ask(f"  [{P['accent']}]Modify settings?[/]", default=False):
        console.print(f"\n  [{P['muted']}]Press Enter to keep the current value.\n[/]")
        TOR_SOCKS_PORT   = IntPrompt.ask(
            f"  [{P['accent']}]Tor SOCKS port[/]", default=TOR_SOCKS_PORT)
        TOR_CONTROL_PORT = IntPrompt.ask(
            f"  [{P['accent']}]Tor control port[/]", default=TOR_CONTROL_PORT)
        new_pw = Prompt.ask(
            f"  [{P['accent']}]Tor password (Enter = keep current)[/]",
            default=TOR_PASSWORD, password=True)
        if new_pw is not None:
            TOR_PASSWORD = new_pw
        TOR_TIMEOUT = IntPrompt.ask(
            f"  [{P['accent']}]Request timeout (seconds)[/]", default=TOR_TIMEOUT)

        PROXIES["http"]  = f"socks5h://127.0.0.1:{TOR_SOCKS_PORT}"
        PROXIES["https"] = f"socks5h://127.0.0.1:{TOR_SOCKS_PORT}"

        ok_msg("Settings updated for this session.")


# ─────────────────────────────────────────────────────────────────────────────
#  HELP / TUTORIAL
# ─────────────────────────────────────────────────────────────────────────────

def _help_section(title: str, content: str):
    """Print a styled help section panel."""
    console.print(
        Panel(
            content,
            title=f"[bold {P['accent']}]  {title}  [/]",
            border_style=P["primary"],
            padding=(1, 3),
            box=box.ROUNDED,
        )
    )
    console.print()


def _help_choice_prompt(question: str, choices: list) -> str:
    """Display a numbered choice menu and return the selected key."""
    console.print(f"\n  [bold {P['white']}]{question}[/]\n")
    for key, label, desc in choices:
        console.print(
            f"  [{P['primary']}][{key}][/]  [bold {P['white']}]{label}[/]"
            + (f"  [{P['muted']}]-- {desc}[/]" if desc else "")
        )
    console.print()
    valid = {c[0].upper() for c in choices}
    while True:
        raw = Prompt.ask(
            f"  [bold {P['accent']}]Enter choice[/]",
            show_choices=False,
        ).strip().upper()
        if raw in valid:
            return raw
        err_msg(f"Invalid choice '{escape(raw)}'. Options: {', '.join(sorted(valid))}")


def _help_step(num: int, total: int, title: str, body: str):
    """Print a single numbered step panel."""
    console.print(
        Panel(
            body,
            title=f"[bold {P['accent']}]  Step {num}/{total}  --  {title}  [/]",
            border_style=P["primary"],
            padding=(1, 3),
            box=box.ROUNDED,
        )
    )
    console.print()


def _help_wait_next(step: int, total: int):
    if step < total:
        console.input(
            f"  [{P['muted']}]Press [bold]Enter[/bold] for next step "
            f"({step + 1}/{total})...[/]  "
        )


def _help_show_overview():
    section_rule("GhostShift -- Overview")
    _help_section(
        "HOW IT WORKS",
        f"[bold {P['white']}]GhostShift[/] routes all your traffic through the "
        f"[bold {P['primary']}]Tor anonymity network[/], replacing your real IP\n"
        f"with the exit node's IP address -- a different one every time you rotate.\n\n"
        f"Two ports must be open on your machine:\n\n"
        f"  [{P['success']}]9050[/]  [bold]SOCKS5 Proxy[/]  -- Tor listens here; GhostShift sends traffic through it.\n"
        f"  [{P['success']}]9051[/]  [bold]Control Port[/]  -- Lets GhostShift tell Tor to switch circuits (rotate IP).\n\n"
        f"[{P['muted']}]Without port 9050 nothing works. Without port 9051 you can still\n"
        f"check your IP, but cannot rotate it automatically.[/]",
    )


def _help_show_tool_reference():
    section_rule("GhostShift -- Menu Reference")
    t = Table(
        box=box.SIMPLE_HEAVY,
        border_style=P["dim"],
        header_style=f"bold {P['primary']}",
        show_lines=True,
        expand=False,
        min_width=80,
    )
    t.add_column("Key",          width=5,  justify="center", style=f"bold {P['accent']}")
    t.add_column("Name",         width=24, style=f"bold {P['white']}")
    t.add_column("What it does", width=46, style=P["muted"])
    t.add_column("Port 9051?",   width=10, justify="center")
    rows = [
        ("1", "Check Current IP",      "Fetch your exit IP via Tor + geolocation.",      f"[{P['success']}]No[/]"),
        ("2", "Rotate IP Once",        "Send NEWNYM -- new circuit, new exit IP.",        f"[{P['danger']}]Yes[/]"),
        ("3", "Auto-Rotate IP",        "Rotate on a timer, indefinitely or N times.",     f"[{P['danger']}]Yes[/]"),
        ("4", "DNS Leak Test",         "Check if DNS queries expose your real IP.",       f"[{P['success']}]No[/]"),
        ("5", "Active Tor Circuits",   "List all built circuits and relay fingerprints.", f"[{P['danger']}]Yes[/]"),
        ("6", "Show Real IP (no Tor)", "Bypass Tor -- reveals your actual public IP.",    f"[{P['success']}]No[/]"),
        ("7", "Tor Status / Start",    "Diagnose health; try auto-start if offline.",     f"[{P['success']}]No[/]"),
        ("8", "View History",          "Browse all IPs logged this session.",             f"[{P['success']}]No[/]"),
        ("9", "Session Statistics",    "Rotations, countries, success rate.",             f"[{P['success']}]No[/]"),
        ("S", "Settings",              "Change ports, password, timeout.",                f"[{P['success']}]No[/]"),
        ("H", "Help & Tutorial",       "Interactive setup wizard -- this menu.",          f"[{P['success']}]No[/]"),
        ("0", "Exit",                  "Save history and quit GhostShift.",              f"[{P['success']}]No[/]"),
    ]
    for r in rows:
        t.add_row(*r)
    console.print(Panel(t, title=f"[bold {P['accent']}]  MENU REFERENCE  [/]",
        border_style=P["primary"], padding=(1, 2), box=box.ROUNDED))
    console.print()


def _help_show_checklist():
    section_rule("GhostShift -- Quick-Start Checklist")
    _help_section(
        "CHECKLIST",
        f"  [{P['success']}][1][/]  Tor is installed on your system\n"
        f"  [{P['success']}][2][/]  torrc has: [bold {P['warn']}]ControlPort 9051[/]  and  "
        f"[bold {P['warn']}]CookieAuthentication 1[/]\n"
        f"  [{P['success']}][3][/]  Tor service is running  --  use option [bold]7[/] to verify\n"
        f"  [{P['success']}][4][/]  Option [bold]1[/] returns a Tor exit IP (different from your real IP)\n"
        f"  [{P['success']}][5][/]  Option [bold]4[/] DNS Leak Test says [bold {P['success']}]No DNS leak detected[/]\n"
        f"  [{P['success']}][6][/]  Option [bold]2[/] or [bold]3[/] successfully rotates your IP\n\n"
        f"  [{P['muted']}]Stuck? Use option [bold]7[/] for diagnostics, or select [bold]H > Troubleshooting[/].[/]"
    )


def _help_linux_setup():
    section_rule("Linux Setup Tutorial")
    distro = _help_choice_prompt(
        "Which Linux distribution are you using?",
        [
            ("D", "Debian / Ubuntu", "apt-based (Ubuntu, Mint, Pop!_OS, Kali...)"),
            ("F", "Fedora / RHEL",   "dnf-based (Fedora, Rocky, AlmaLinux...)"),
            ("A", "Arch Linux",      "pacman-based (Arch, Manjaro, EndeavourOS...)"),
        ]
    )
    install_cmd = {"D": "sudo apt update && sudo apt install tor -y",
                   "F": "sudo dnf install tor -y",
                   "A": "sudo pacman -S tor --noconfirm"}[distro]
    distro_label = {"D": "Debian / Ubuntu", "F": "Fedora / RHEL", "A": "Arch Linux"}[distro]
    tor_group    = {"D": "debian-tor", "F": "tor", "A": "tor"}[distro]
    TOTAL = 5

    _help_step(1, TOTAL, "Install Tor",
        f"[{P['muted']}]Run this in your terminal:[/]\n\n"
        f"  [bold {P['teal']}]{install_cmd}[/]\n\n"
        f"  [{P['muted']}]This installs Tor and registers it as a systemd service.[/]"
    )
    _help_wait_next(1, TOTAL)

    _help_step(2, TOTAL, "Enable the Control Port in torrc",
        f"[{P['muted']}]Open the Tor config file:[/]\n\n"
        f"  [bold {P['teal']}]sudo nano /etc/tor/torrc[/]\n\n"
        f"Find (or add) these lines -- make sure they are [bold]not commented out[/] (no leading #):\n\n"
        f"  [{P['warn']}]ControlPort 9051[/]\n"
        f"  [{P['warn']}]CookieAuthentication 1[/]\n\n"
        f"  [{P['muted']}]Save: [bold]Ctrl+O[/] then [bold]Enter[/].  Exit: [bold]Ctrl+X[/].[/]"
    )
    _help_wait_next(2, TOTAL)

    _help_step(3, TOTAL, "Start / Restart Tor",
        f"  [bold {P['teal']}]sudo systemctl enable tor[/]   [{P['muted']}](auto-start on boot)[/]\n"
        f"  [bold {P['teal']}]sudo systemctl restart tor[/]\n\n"
        f"[{P['muted']}]Verify it started:[/]\n\n"
        f"  [bold {P['teal']}]sudo systemctl status tor[/]\n\n"
        f"  [{P['muted']}]Look for [bold {P['success']}]active (running)[/] in the output.[/]"
    )
    _help_wait_next(3, TOTAL)

    _help_step(4, TOTAL, "Verify Ports Are Open",
        f"  [bold {P['teal']}]ss -tlnp | grep tor[/]\n\n"
        f"  [{P['muted']}]Expected:[/]\n"
        f"  [{P['success']}]0.0.0.0:9050[/]   -- SOCKS proxy\n"
        f"  [{P['success']}]127.0.0.1:9051[/]  -- Control port\n\n"
        f"  [{P['muted']}]If 9051 is missing, re-check Step 2 and restart Tor.[/]"
    )
    _help_wait_next(4, TOTAL)

    _help_step(5, TOTAL, "Fix Permissions (if needed) & Launch",
        f"[{P['muted']}]If auth fails on port 9051, add your user to the Tor group:[/]\n\n"
        f"  [bold {P['teal']}]sudo usermod -aG {tor_group} $USER[/]\n"
        f"  [{P['muted']}]Then log out and back in.[/]\n\n"
        f"[{P['muted']}]Install Python deps (first time only):[/]\n\n"
        f"  [bold {P['teal']}]pip install requests[socks] stem rich pyfiglet[/]\n\n"
        f"[{P['muted']}]Launch:[/]\n\n"
        f"  [bold {P['teal']}]python ip_changer.py[/]\n\n"
        f"  [{P['success']}][OK]  All done on {distro_label}![/]"
    )


def _help_windows_setup():
    section_rule("Windows Setup Tutorial")
    method = _help_choice_prompt(
        "How would you like to run Tor on Windows?",
        [
            ("E", "Expert Bundle (manual)", "Lightweight -- recommended for most users"),
            ("S", "Windows Service",        "Runs silently in background (advanced)"),
        ]
    )
    TOTAL = 5 if method == "E" else 6

    _help_step(1, TOTAL, "Download the Tor Expert Bundle",
        f"[{P['muted']}]Go to:[/]  [bold {P['teal']}]https://www.torproject.org/download/tor/[/]\n\n"
        f"  Download [bold]Windows Expert Bundle[/] (NOT the Tor Browser).\n"
        f"  Extract the .zip to a simple path, e.g.  [bold {P['warn']}]C:\\tor\\[/]\n\n"
        f"  [{P['muted']}]After extraction you should have [bold]C:\\tor\\Tor\\tor.exe[/][/]"
    )
    _help_wait_next(1, TOTAL)

    _help_step(2, TOTAL, "Create the torrc Configuration File",
        f"[{P['muted']}]Open Notepad and create this file:[/]\n\n"
        f"  [bold {P['warn']}]C:\\tor\\Data\\Tor\\torrc[/]\n\n"
        f"  [{P['muted']}](Create the folders [bold]Data\\Tor\\[/] if they don't exist yet.)\n"
        f"  Save as type [bold]All Files[/], name exactly [bold]torrc[/] (no .txt extension.)[/]\n\n"
        f"Paste these three lines into the file:\n\n"
        f"  [{P['warn']}]SocksPort 9050[/]\n"
        f"  [{P['warn']}]ControlPort 9051[/]\n"
        f"  [{P['warn']}]CookieAuthentication 1[/]"
    )
    _help_wait_next(2, TOTAL)

    if method == "E":
        _help_step(3, TOTAL, "Start Tor",
            f"[{P['muted']}]Open Command Prompt or PowerShell and run:[/]\n\n"
            f"  [bold {P['teal']}]cd C:\\tor\\Tor[/]\n"
            f"  [bold {P['teal']}]tor.exe -f ..\\Data\\Tor\\torrc[/]\n\n"
            f"  [{P['muted']}]Keep this window open -- Tor must stay running.\n"
            f"  Wait for [bold {P['success']}]Bootstrapped 100%[/] in the output.[/]"
        )
    else:
        _help_step(3, TOTAL, "Install Tor as a Windows Service",
            f"[{P['muted']}]Open [bold]Command Prompt as Administrator[/]:[/]\n\n"
            f"  [bold {P['teal']}]cd C:\\tor\\Tor[/]\n"
            f"  [bold {P['teal']}]tor.exe --service install -options -f C:\\tor\\Data\\Tor\\torrc[/]\n"
            f"  [bold {P['teal']}]net start tor[/]\n\n"
            f"  [{P['muted']}]Tor now starts automatically on every Windows boot.\n"
            f"  To stop it later:  [bold {P['teal']}]net stop tor[/][/]"
        )
    _help_wait_next(3, TOTAL)

    _help_step(4, TOTAL, "Verify Tor Is Running",
        f"[{P['muted']}]Open a [bold]new[/] Command Prompt window and run:[/]\n\n"
        f"  [bold {P['teal']}]netstat -an | findstr 9050[/]\n"
        f"  [bold {P['teal']}]netstat -an | findstr 9051[/]\n\n"
        f"  [{P['muted']}]Both should show a [bold {P['success']}]LISTENING[/] entry.\n"
        f"  If 9051 is missing, re-check your torrc file.[/]"
    )
    _help_wait_next(4, TOTAL)

    _help_step(5, TOTAL, "Install Python Dependencies",
        f"[{P['muted']}]In any terminal:[/]\n\n"
        f"  [bold {P['teal']}]pip install requests[socks] stem rich pyfiglet[/]\n\n"
        f"  [{P['muted']}]If pip is not found, try:[/]\n"
        f"  [bold {P['teal']}]python -m pip install requests[socks] stem rich pyfiglet[/]"
    )
    _help_wait_next(5, TOTAL)

    if TOTAL == 6:
        _help_step(6, TOTAL, "Launch GhostShift",
            f"[{P['muted']}]With Tor running as a service in the background:[/]\n\n"
            f"  [bold {P['teal']}]python ip_changer.py[/]\n\n"
            f"  [{P['success']}][OK]  All done on Windows![/]"
        )
    else:
        console.print(
            f"  [{P['success']}][OK]  Tor is running. Open a new terminal and start GhostShift:[/]\n"
            f"  [bold {P['teal']}]  python ip_changer.py[/]\n"
        )


def _help_troubleshooting():
    section_rule("GhostShift -- Troubleshooting")
    problem = _help_choice_prompt(
        "What problem are you running into?",
        [
            ("A", "Tor not detected / port 9050 offline", ""),
            ("B", "Control port 9051 is closed",          "can't rotate IP"),
            ("C", "Authentication failed (cookie error)", ""),
            ("D", "IP is not changing after rotation",    ""),
            ("E", "DNS leak detected",                    ""),
        ]
    )
    if problem == "A":
        _help_section("FIX: Tor Not Running (port 9050 offline)",
            f"[bold {P['primary']}]Linux:[/]\n"
            f"  [bold {P['teal']}]sudo systemctl status tor[/]   -- check what failed\n"
            f"  [bold {P['teal']}]sudo systemctl start tor[/]    -- try to start\n"
            f"  [bold {P['teal']}]sudo journalctl -u tor -n 30[/]  -- read error logs\n\n"
            f"[bold {P['primary']}]Windows:[/]\n"
            f"  Re-run [bold {P['teal']}]tor.exe -f ..\\Data\\Tor\\torrc[/] in its terminal.\n"
            f"  Or if using a service:  [bold {P['teal']}]net start tor[/]\n\n"
            f"[bold {P['primary']}]Either platform:[/]\n"
            f"  Use GhostShift option [bold]7[/] -- it will try to auto-start Tor."
        )
    elif problem == "B":
        _help_section("FIX: Control Port 9051 Closed",
            f"The control port is [bold]not[/] enabled by default. Edit torrc and add:\n\n"
            f"  [{P['warn']}]ControlPort 9051[/]\n"
            f"  [{P['warn']}]CookieAuthentication 1[/]\n\n"
            f"[bold {P['primary']}]Linux torrc path:[/]   [bold {P['teal']}]/etc/tor/torrc[/]\n"
            f"[bold {P['primary']}]Windows torrc path:[/] [bold {P['teal']}]C:\\tor\\Data\\Tor\\torrc[/]\n\n"
            f"Then restart Tor:\n"
            f"  Linux  :  [bold {P['teal']}]sudo systemctl restart tor[/]\n"
            f"  Windows:  stop & re-run [bold {P['teal']}]tor.exe -f ..\\Data\\Tor\\torrc[/]"
        )
    elif problem == "C":
        _help_section("FIX: Cookie Authentication Failed",
            f"[bold {P['primary']}]Linux -- add your user to the Tor group:[/]\n\n"
            f"  Debian/Ubuntu:  [bold {P['teal']}]sudo usermod -aG debian-tor $USER[/]\n"
            f"  Fedora / Arch:  [bold {P['teal']}]sudo usermod -aG tor $USER[/]\n\n"
            f"  [{P['muted']}]Log out and back in, then restart Tor.[/]\n\n"
            f"[bold {P['primary']}]Alternative -- password auth (all platforms):[/]\n\n"
            f"  1. Generate a hash:  [bold {P['teal']}]tor --hash-password YourPassword[/]\n"
            f"  2. Add to torrc:\n"
            f"       [{P['warn']}]ControlPort 9051[/]\n"
            f"       [{P['warn']}]HashedControlPassword 16:YOURHASH[/]\n"
            f"  3. In GhostShift go to [bold]Settings (S)[/] and enter your password."
        )
    elif problem == "D":
        _help_section("FIX: IP Not Changing After Rotation",
            f"Tor enforces a minimum [bold]10-second wait[/] between NEWNYM signals.\n"
            f"GhostShift waits automatically, but here are other causes:\n\n"
            f"  [{P['warn']}][1][/]  Tor reused the same exit node -- try rotating again.\n"
            f"  [{P['warn']}][2][/]  Some circuits persist longer -- wait ~30 seconds.\n"
            f"  [{P['warn']}][3][/]  Small exit node pool in your region -- Tor network condition,\n"
            f"         not a GhostShift bug.\n\n"
            f"[{P['muted']}]Use option [bold]5[/] (Active Circuits) to check circuit health.[/]"
        )
    elif problem == "E":
        _help_section("FIX: DNS Leak Detected",
            f"DNS queries are going outside Tor -- your real IP may be exposed.\n\n"
            f"[bold {P['primary']}]Linux fix (systemd-resolved):[/]\n"
            f"  Edit [bold {P['teal']}]/etc/systemd/resolved.conf[/] and set:\n"
            f"  [{P['warn']}]DNS=127.0.0.1[/]\n"
            f"  Restart:  [bold {P['teal']}]sudo systemctl restart systemd-resolved[/]\n\n"
            f"[bold {P['primary']}]All platforms:[/]\n"
            f"  Set your network adapter's DNS to [bold]127.0.0.1[/] in system settings.\n\n"
            f"  [{P['muted']}]GhostShift uses [bold]socks5h://[/] which resolves DNS inside Tor.\n"
            f"  A leak usually means another app is bypassing the proxy.[/]"
        )


def action_help():
    while True:
        header(is_tor_running())
        section_rule("GhostShift -- Help & Tutorial")
        console.print(
            Panel(
                f"[bold {P['white']}]Welcome to the interactive GhostShift help system.[/]\n\n"
                f"Choose a topic -- you will be guided step by step.\n"
                f"[{P['muted']}]You can return to this menu after each section.[/]",
                border_style=P["primary"],
                padding=(1, 4),
                box=box.ROUNDED,
            )
        )
        console.print()

        topic = _help_choice_prompt(
            "What would you like help with?",
            [
                ("O", "Overview",              "How GhostShift and Tor work together"),
                ("L", "Linux Setup",           "Step-by-step install guide for Linux"),
                ("W", "Windows Setup",         "Step-by-step install guide for Windows"),
                ("T", "Troubleshooting",       "Fix common problems (ports, auth, leaks)"),
                ("M", "Menu Reference",        "What every menu option does"),
                ("C", "Quick-Start Checklist", "Verify everything is configured correctly"),
                ("B", "Back to Main Menu",     ""),
            ]
        )

        if topic == "B":
            break

        header(is_tor_running())

        if topic == "O":
            _help_show_overview()
        elif topic == "L":
            _help_linux_setup()
        elif topic == "W":
            _help_windows_setup()
        elif topic == "T":
            _help_troubleshooting()
        elif topic == "M":
            _help_show_tool_reference()
        elif topic == "C":
            _help_show_checklist()

        console.print()
        go_back = Confirm.ask(
            f"  [{P['accent']}]Return to Help menu?[/]",
            default=True,
        )
        if not go_back:
            break

# ─────────────────────────────────────────────────────────────────────────────
MENU_ITEMS = [
    ("1",  "Check Current IP",          action_check_ip),
    ("2",  "Rotate IP Once",            action_rotate),
    ("3",  "Auto-Rotate IP",            action_auto_rotate),
    ("4",  "DNS Leak Test",             action_dns_leak),
    ("5",  "Active Tor Circuits",       action_circuits),
    ("6",  "Show Real IP  (no Tor)",    action_real_ip),
    ("7",  "Tor Status / Start Tor",    action_tor_status),
    ("8",  "View History",              action_history),
    ("9",  "Session Statistics",        action_stats),
    ("S",  "Settings",                  action_settings),
    ("H",  "Help & Tutorial",           action_help),
    ("0",  "Exit",                      None),
]

MENU_SPLIT = 6


def _make_menu_column(items: List) -> Table:
    t = Table(
        box=box.ROUNDED,
        border_style=P["primary"],
        show_header=False,
        padding=(0, 2),
        expand=False,
        min_width=34,
    )
    t.add_column(justify="center", width=4,  style=f"bold {P['primary']}")
    t.add_column(justify="left",   width=26, style=f"bold {P['white']}")
    for key, label, _ in items:
        if key == "0":
            key_color = P["danger"]
        elif key == "H":
            key_color = P["purple"]
        else:
            key_color = P["primary"]
        t.add_row(
            f"[{key_color}][{key}][/]",
            label,
        )
    return t


def draw_menu(tor_online: bool):
    left  = MENU_ITEMS[:MENU_SPLIT]
    right = MENU_ITEMS[MENU_SPLIT:]
    console.print(
        Columns(
            [_make_menu_column(left), _make_menu_column(right)],
            equal=True,
            expand=False,
        )
    )
    console.print()
    console.print(
        Align.center(
            f"[{P['muted']}]Tor: {status_label(tor_online)}[/]"
        )
    )
    console.print()


def main():
    load_history()
    tor_online = is_tor_running()
    header(tor_online)

    if not tor_online:
        warn_panel(
            "Tor is not running on port 9050.\n"
            "Select [bold]7[/bold] from the menu for diagnostics, "
            "or [bold]H[/bold] for the full setup tutorial.",
            title="Tor Not Detected"
        )
        console.print()

    valid_keys = {m[0].upper() for m in MENU_ITEMS}

    while True:
        tor_online = is_tor_running()
        draw_menu(tor_online)

        try:
            choice = Prompt.ask(
                f"[bold {P['accent']}]  Select option[/]",
                show_choices=False,
            ).strip().upper()
        except (KeyboardInterrupt, EOFError):
            choice = "0"

        if choice not in valid_keys:
            err_msg(
                f"Invalid option '{escape(choice)}'.  "
                f"Choose: {', '.join(m[0] for m in MENU_ITEMS)}"
            )
            time.sleep(1)
            header(tor_online)
            continue

        if choice == "0":
            console.print()
            console.print(Panel(
                Align.center(
                    f"{render_banner()}\n\n"
                    f"[bold {P['accent']}]GhostShift signing off.[/]\n"
                    f"[{P['muted']}]"
                    f"Rotations : [{P['success']}]{session_stats['rotations']}[/]  |  "
                    f"Countries : [{P['teal']}]{len(session_stats['countries_seen'])}[/]\n\n"
                    f"Stay anonymous. Stay safe.[/]"
                ),
                border_style=P["primary"],
                padding=(1, 4),
                box=box.DOUBLE_EDGE,
            ))
            save_history()
            console.print()
            sys.exit(0)

        for key, label, action in MENU_ITEMS:
            if key.upper() == choice and action:
                header(tor_online)
                action()
                press_enter()
                header(tor_online)
                break


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print(f"\n\n[{P['muted']}]Interrupted. Goodbye.[/]\n")
        save_history()
        sys.exit(0)
