#!/usr/bin/env python3
"""eYD — easy YouTube Downloader  (yt-dlp + aria2c batch wrapper)"""
from __future__ import annotations

import argparse
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path


# ── rich bootstrap ─────────────────────────────────────────────────────────────
# rich lives in the yt-dlp pipx venv. If invoked with system Python (where rich
# is absent), inject rich into the venv and re-exec — transparent, runs once.

_YTDLP_PY = Path.home() / ".local/share/pipx/venvs/yt-dlp/bin/python"


def _ensure_rich() -> None:
    try:
        import rich  # noqa: F401
        return
    except ImportError:
        pass

    # If the yt-dlp venv doesn't exist yet, create it silently so we can inject rich.
    if not _YTDLP_PY.is_file() and shutil.which("pipx"):
        subprocess.run(["pipx", "install", "yt-dlp"], capture_output=True)

    if _YTDLP_PY.is_file() and str(_YTDLP_PY) != sys.executable:
        subprocess.run(
            ["pipx", "inject", "yt-dlp", "rich", "--quiet"],
            capture_output=True,
        )
        os.execv(str(_YTDLP_PY), [str(_YTDLP_PY), *sys.argv])

    for cmd in (
        [sys.executable, "-m", "pip", "install", "--user", "--quiet", "rich"],
        [sys.executable, "-m", "pip", "install", "--quiet", "--break-system-packages", "rich"],
    ):
        if subprocess.run(cmd, capture_output=True).returncode == 0:
            return

    sys.exit("rich is required — run: pipx inject yt-dlp rich")


_ensure_rich()

from rich.console import Console  # noqa: E402
from rich.panel import Panel       # noqa: E402
from rich.table import Table       # noqa: E402
from rich.text import Text         # noqa: E402

console = Console(stderr=True, highlight=False)


# ── OS / package manager detection ────────────────────────────────────────────
_INSTALLERS: list[tuple[str, list[str]]] = [
    ("apt",    ["sudo", "apt",    "install", "-y"]),
    ("dnf",    ["sudo", "dnf",    "install", "-y"]),
    ("pacman", ["sudo", "pacman", "-S", "--noconfirm"]),
    ("zypper", ["sudo", "zypper", "install", "-y"]),
    ("apk",    ["sudo", "apk",    "add"]),
    ("brew",   ["brew", "install"]),
    ("port",   ["sudo", "port",   "install"]),
]

_PKG_MAP: dict[str, dict[str, str]] = {
    "ffmpeg": {m: "ffmpeg" for m, _ in _INSTALLERS},
    "aria2c": {m: "aria2"  for m, _ in _INSTALLERS},
}


def _detect_pkg_mgr() -> tuple[str, list[str]] | None:
    for name, cmd in _INSTALLERS:
        if shutil.which(name):
            return name, cmd
    return None


def _prompt(question: str) -> bool:
    """Ask a Y/n question. Non-interactive (EOF) defaults to False."""
    try:
        ans = console.input(f"  [yellow]?[/yellow]  {question} [Y/n] ")
        return ans.strip().lower() in ("", "y", "yes")
    except (EOFError, KeyboardInterrupt):
        console.print()
        return False


def _install_sys_pkg(binary: str) -> bool:
    """Detect package manager, ask permission, install. Returns True on success."""
    mgr = _detect_pkg_mgr()
    if not mgr:
        return False
    mgr_name, cmd = mgr
    pkg = _PKG_MAP.get(binary, {}).get(mgr_name)
    if not pkg:
        return False
    if not _prompt(f"install {binary} via {mgr_name}?"):
        return False
    result = subprocess.run([*cmd, pkg])
    return result.returncode == 0 and bool(shutil.which(binary))


# ── URL classification ─────────────────────────────────────────────────────────
_PATTERNS: list[tuple[str, str]] = [
    (r"youtube\.com/shorts/",          "short"),
    (r"youtube\.com/playlist\?list=",  "playlist"),
    (r"youtube\.com/watch.*[?&]list=", "playlist"),
    (r"youtube\.com/@[^/?]+",          "channel"),
    (r"youtube\.com/channel/",         "channel"),
    (r"youtube\.com/c/",               "channel"),
    (r"youtube\.com/user/",            "channel"),
    (r"youtube\.com/watch",            "video"),
    (r"youtu\.be/",                    "video"),
]

_KIND_STYLE: dict[str, str] = {
    "video":    "bold cyan",
    "short":    "bold magenta",
    "playlist": "bold yellow",
    "channel":  "bold green",
    "other":    "bold blue",
}


def classify(url: str) -> str:
    for pattern, kind in _PATTERNS:
        if re.search(pattern, url):
            return kind
    return "other"


def load_urls(src: Path) -> list[str]:
    urls = []
    for raw in src.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line == "end":
            break
        urls.append(line)
    return urls


# ── dependency check ───────────────────────────────────────────────────────────
def check_deps() -> str | None:
    """Ensure all tools are present, prompting to install missing ones.
    Returns the detected JS runtime name, or None."""

    # ffmpeg and aria2c — system packages, auto-detected package manager
    for binary in ("ffmpeg", "aria2c"):
        if shutil.which(binary):
            continue
        if _install_sys_pkg(binary):
            console.print(f"  [green]✓[/green] {binary} installed")
            continue
        mgr = _detect_pkg_mgr()
        if mgr:
            pkg  = _PKG_MAP.get(binary, {}).get(mgr[0], binary)
            hint = f"{mgr[0]} install {pkg}"
        else:
            pkg  = _PKG_MAP.get(binary, {}).get("apt", binary)
            hint = f"apt / brew / dnf install {pkg}"
        console.print(f"  [red]✗[/red] {binary} not found — {hint}")
        sys.exit(1)

    # yt-dlp — pipx only (system packages are outdated)
    if not shutil.which("yt-dlp"):
        if shutil.which("pipx") and _prompt("install yt-dlp via pipx?"):
            r = subprocess.run(["pipx", "install", "yt-dlp"])
            if r.returncode == 0 and shutil.which("yt-dlp"):
                console.print("  [green]✓[/green] yt-dlp installed")
            else:
                console.print("  [red]✗[/red] install failed — run: pipx install yt-dlp")
                sys.exit(1)
        else:
            console.print("  [red]✗[/red] yt-dlp not found — run: pipx install yt-dlp")
            sys.exit(1)

    # secretstorage — Linux-only DBus cookie decryption, silent injection
    if platform.system() == "Linux" and _YTDLP_PY.is_file():
        probe = subprocess.run(
            [str(_YTDLP_PY), "-c", "import secretstorage"],
            capture_output=True,
        )
        if probe.returncode != 0:
            console.print("  [blue]·[/blue] injecting secretstorage into yt-dlp venv …")
            subprocess.run(
                ["pipx", "inject", "yt-dlp", "secretstorage", "jeepney"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )

    # JS runtime — deno/node/bun detection, ask before installing deno
    deno_bin = Path.home() / ".deno/bin"
    if deno_bin.is_dir():
        os.environ["PATH"] = f"{deno_bin}:{os.environ['PATH']}"

    for rt in ("deno", "node", "bun"):
        if shutil.which(rt):
            return rt

    if not shutil.which("curl"):
        console.print("  [yellow]⚠[/yellow] no JS runtime + no curl — YouTube n-challenge may fail")
        return None

    if not _prompt("no JS runtime found — install deno? (needed for YouTube downloads)"):
        console.print("  [yellow]⚠[/yellow] no JS runtime — some YouTube downloads may fail")
        return None

    console.print("  [blue]·[/blue] installing deno …")
    fetch = subprocess.run(
        ["curl", "-fsSL", "https://deno.land/install.sh"],
        capture_output=True, text=True,
    )
    if fetch.returncode == 0:
        inst = subprocess.run(
            ["sh", "-s", "--", "--no-modify-path"],
            input=fetch.stdout, text=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        if inst.returncode == 0:
            os.environ["PATH"] = f"{deno_bin}:{os.environ['PATH']}"
            console.print("  [green]✓[/green] deno installed")
            return "deno"

    console.print("  [yellow]⚠[/yellow] deno install failed — n-challenge may not resolve")
    return None


# ── helpers ────────────────────────────────────────────────────────────────────
def cleanup_subs(directory: Path) -> None:
    for pat in ("*.vtt", "*.srt", "*.ass", "*.ssa"):
        for f in directory.glob(pat):
            f.unlink(missing_ok=True)


def run_dl(
    url: str,
    outdir: Path,
    kind_args: list[str],
    common: list[str],
    attempts: int,
    subs: str,
) -> bool:
    outdir.mkdir(parents=True, exist_ok=True)
    for n in range(1, attempts + 1):
        if n > 1:
            wait = 2 ** n
            console.print(f"  [yellow]⚠[/yellow] retry {n}/{attempts} — waiting {wait}s …")
            time.sleep(wait)
        result = subprocess.run(["yt-dlp", *common, *kind_args, "--", url])
        if result.returncode == 0:
            if subs != "none":
                cleanup_subs(outdir)
            return True
    return False


# ── argument parser ────────────────────────────────────────────────────────────
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="eYD",
        add_help=False,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="eYD — easy YouTube Downloader\nBatch downloader built on yt-dlp + aria2c.",
    )
    p.add_argument("-q", dest="quality",  type=int, default=1440,   metavar="PX",      help="max height in pixels (default: 1440)")
    p.add_argument("-r", dest="fps",      type=int, default=60,     metavar="FPS",     help="preferred fps (default: 60)")
    p.add_argument("-s", dest="subs",               default="none", metavar="LANG",    help='subtitle language or "none" (default: none)')
    p.add_argument("-f", dest="file",               default="",     metavar="FILE",    help="source filename or full path (default: source.txt)")
    p.add_argument("-p", dest="outdir",             default="",     metavar="DIR",     help="working / output directory (default: cwd)")
    p.add_argument("-m", dest="maxsize",            default="10g",  metavar="SIZE",    help="max file size e.g. 10g (default: 10g)")
    p.add_argument("-x", dest="proxy",              default="",     metavar="URL",     help="proxy URL")
    p.add_argument("-C", dest="cookies",            default="",     metavar="BROWSER", help="cookies from browser: brave|chrome|firefox|edge")
    p.add_argument("-A", dest="attempts", type=int, default=3,      metavar="N",       help="download attempts per URL (default: 3)")
    p.add_argument("-R", dest="retries",  type=int, default=20,     metavar="N",       help="yt-dlp retries per attempt (default: 20)")
    p.add_argument("-h", action="help", default=argparse.SUPPRESS,                     help="show help")
    return p


# ── main ───────────────────────────────────────────────────────────────────────
def main() -> None:
    args = build_parser().parse_args()

    workdir = Path(args.outdir).expanduser().resolve() if args.outdir else Path.cwd()

    if args.file:
        src = Path(args.file) if "/" in args.file else workdir / args.file
    else:
        src = workdir / "source.txt"

    if not src.is_file():
        console.print(f"  [red]✗[/red] source not found: {src}")
        sys.exit(1)

    js_rt = check_deps()

    # ── yt-dlp argument assembly ───────────────────────────────────────────────
    net_args: list[str] = []
    if args.proxy:
        net_args += [f"--proxy={args.proxy}"]
    if args.cookies:
        net_args += [f"--cookies-from-browser={args.cookies}"]

    js_args: list[str] = []
    if js_rt:
        js_args = ["--js-runtimes", js_rt, "--remote-components", "ejs:github"]

    sub_args: list[str] = []
    if args.subs != "none" and args.subs:
        sub_args = [
            "--write-auto-subs",
            "--sub-langs", args.subs,
            "--embed-subs",
            "--convert-subs", "srt",
            "--compat-options", "no-keep-subs",
        ]

    archive = workdir / "archive.txt"
    q, fps  = args.quality, args.fps

    common: list[str] = [
        "--console-title", "--progress",
        "--windows-filenames", "--trim-filenames", "180",
        "--extractor-args", "youtube:player_client=default",
        *net_args,
        *js_args,
        "--max-filesize", args.maxsize,
        "--retries", str(args.retries),
        "--fragment-retries", str(args.retries),
        "--file-access-retries", str(args.retries),
        "--retry-sleep", "exp=1:30",
        "--socket-timeout", "30",
        "--downloader", "aria2c",
        "--downloader-args",
        "aria2c:-x 16 -s 16 -k 1M --file-allocation=none --console-log-level=warn --summary-interval=0",
        "--downloader", "dash,m3u8:native",
        "--concurrent-fragments", "4",
        "--http-chunk-size", "10M",
        "--embed-chapters",
        "--no-overwrites",
        "--download-archive", str(archive),
        *sub_args,
    ]

    fmt = (
        f"bv*[acodec=none][height<={q}][fps>={fps}]+ba/b[height<={q}][fps>={fps}]"
        f" / bv*[acodec=none][height<={q}][fps<={fps}]+ba/b[height<={q}][fps<={fps}]"
        f" / bv*[acodec=none][height<={q}]+ba/b[height<={q}]"
        f" / b[height<={q}] / b"
    )

    # ── config panel ──────────────────────────────────────────────────────────
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="dim", min_width=12)
    grid.add_column()
    for label, value in (
        ("source",     str(src)),
        ("output",     str(workdir)),
        ("quality",    f"{q}p @ {fps}fps  max {args.maxsize}"),
        ("subtitles",  args.subs),
        ("cookies",    args.cookies or "none"),
        ("proxy",      args.proxy    or "none"),
        ("runtime",    js_rt         or "none"),
        ("downloader", "aria2c + native (dash/m3u8)"),
        ("retry",      f"{args.attempts} attempts · {args.retries} retries · exp backoff"),
        ("archive",    str(archive)),
    ):
        grid.add_row(label, value)

    console.print()
    console.print(Panel(grid, title="[bold]eYD[/bold]", expand=False, border_style="bright_blue"))
    console.print()

    # ── URL loop ───────────────────────────────────────────────────────────────
    urls = load_urls(src)
    n_total = len(urls)

    workdir.mkdir(parents=True, exist_ok=True)
    ok_path   = workdir / "downloaded.txt"
    fail_path = workdir / "failed.txt"
    ok_path.write_text("")
    fail_path.write_text("")

    passed = failed = 0

    try:
        for idx, url in enumerate(urls, 1):
            kind  = classify(url)
            style = _KIND_STYLE.get(kind, "bold white")

            badge = Text()
            badge.append(f"  [{idx}/{n_total}] ", style="dim")
            badge.append(f"[{kind}]", style=style)
            badge.append(f"  {url}", style="dim")
            console.print(badge)

            tmpl_base = "%(title)s [%(upload_date>%Y-%m-%d)s] [%(id)s].%(ext)s"

            match kind:
                case "video" | "short":
                    sub       = "videos" if kind == "video" else "shorts"
                    outdir    = workdir / "youtube" / sub
                    kind_args = [
                        "-f", fmt, "--merge-output-format", "mkv", "--no-playlist", "-i",
                        "-o", str(outdir / tmpl_base),
                    ]
                case "playlist":
                    outdir    = workdir / "youtube" / "playlists"
                    kind_args = [
                        "-f", fmt, "--merge-output-format", "mkv", "--yes-playlist", "-i",
                        "-o", str(outdir / "%(playlist)s/%(playlist_index)s - %(title)s [%(id)s].%(ext)s"),
                    ]
                case "channel":
                    outdir    = workdir / "youtube" / "channels"
                    kind_args = [
                        "-f", fmt, "--merge-output-format", "mkv", "--yes-playlist", "-i",
                        "-o", str(outdir / "%(uploader)s/%(upload_date>%Y-%m-%d)s - %(title)s [%(id)s].%(ext)s"),
                    ]
                case _:
                    outdir    = workdir / "other"
                    kind_args = [
                        "-f", "bv*+ba/b / b", "--merge-output-format", "mkv", "-i",
                        "-o", str(outdir / "%(extractor)s/%(title)s [%(id)s].%(ext)s"),
                    ]

            ok = run_dl(url, outdir, kind_args, common, args.attempts, args.subs)

            if ok:
                passed += 1
                console.print("  [green]✓[/green] done\n")
                with ok_path.open("a") as fh:
                    fh.write(url + "\n")
            else:
                failed += 1
                console.print("  [red]✗[/red] failed\n")
                with fail_path.open("a") as fh:
                    fh.write(url + "\n")

    except KeyboardInterrupt:
        console.print("\n  [yellow]⚠[/yellow] interrupted\n")

    # ── summary ────────────────────────────────────────────────────────────────
    sg = Table.grid(padding=(0, 2))
    sg.add_column(min_width=16)
    sg.add_column(justify="right", style="bold")
    sg.add_row("[green]✓  downloaded[/green]", str(passed))
    sg.add_row("[red]✗  failed[/red]",          str(failed))
    sg.add_row("total",                           str(n_total))

    border = "green" if failed == 0 else "red"
    console.print(Panel(sg, title="[bold]done[/bold]", expand=False, border_style=border))
    console.print()


if __name__ == "__main__":
    main()
