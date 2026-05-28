# eYD — Easy YouTube Downloader

Batch download manager built on **yt-dlp** and **aria2c**.  
Supports YouTube videos, shorts, playlists, channels, and [1000+ other sites](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md).

[![Donate BTC](https://img.shields.io/badge/BTC-Donate-orange)](https://idpay.ir/oky2abbas)
[![Donate ETH](https://img.shields.io/badge/ETH%20%2F%20USDT-Donate-blue)](https://idpay.ir/oky2abbas)

**BTC** `1HPZyUP9EJZi2S87QrvCDrE47qRV4i5Fze`  
**ETH / USDT** `0x4a4b0A26Eb31e9152653E4C08bCF10f04a0A02a9`

---

## Features

- Auto-detects URL type: video, short, playlist, channel, or any yt-dlp-supported site
- Best video + audio merged into a single MKV, with chapter markers embedded
- 16-connection parallel downloading via aria2c
- Resume support — `archive.txt` tracks completed downloads; re-runs skip them
- Exponential backoff retry across both outer attempts and yt-dlp-level retries
- Optional subtitle download and embedding
- Smart dependency management: detects OS and package manager, prompts to install missing tools
- Auto-injects `rich`, `deno`, and `secretstorage` on first run as needed

---

## Requirements

**macOS**
```bash
brew install pipx && pipx ensurepath && pipx install yt-dlp
```

**Ubuntu / Debian**
```bash
sudo apt install pipx && pipx ensurepath && pipx install yt-dlp
```

**Fedora / Red Hat**
```bash
sudo dnf install pipx && pipx ensurepath && pipx install yt-dlp
```

`ffmpeg` and `aria2` are required but eYD will detect your package manager and offer to install them automatically on first run.

---

## Installation

```bash
wget https://raw.githubusercontent.com/oky2abbas/easyYoutubeDL/master/easy-youtube-dl.py
chmod +x easy-youtube-dl.py
sudo mv easy-youtube-dl.py /usr/local/bin/eYD
```

Or as an alias in `~/.zshrc` / `~/.bashrc`:
```bash
alias eYD='python3 /path/to/easy-youtube-dl.py'
```

---

## Usage

```
eYD [OPTIONS]

  -q PX       max height in pixels              (default: 1440)
  -r FPS      preferred frames per second       (default: 60)
  -s LANG     subtitle language, or "none"      (default: none)
  -f FILE     source filename or full path      (default: source.txt)
  -p DIR      working / output directory        (default: cwd)
  -m SIZE     max file size e.g. 10g            (default: 10g)
  -x URL      proxy URL
  -C BROWSER  cookies from browser: brave|chrome|firefox|edge
  -A N        download attempts per URL         (default: 3)
  -R N        yt-dlp retries per attempt        (default: 20)
  -h          show help
```

---

## Source File

One URL per line. Lines starting with `#` are ignored. `end` stops processing.

```
# YouTube video
https://www.youtube.com/watch?v=XXXXXXXXXXX

# Playlist
https://www.youtube.com/playlist?list=XXXXXXXXXXX

# Channel
https://www.youtube.com/@ChannelHandle

# Any other supported site
https://vimeo.com/XXXXXXXXXXX

end
```

---

## Examples

```bash
# 1080p, English subtitles, cookies from Brave
eYD -q 1080 -r 30 -s en -C brave -p ~/Downloads/ydl -f source.txt

# 4K, Persian subtitles, 5g size limit
eYD -q 2160 -r 60 -s fa -m 5g -p ~/Downloads -f source.txt

# Through a SOCKS5 proxy
eYD -q 1080 -x socks5://127.0.0.1:1080 -p ~/Downloads -f source.txt

# Aggressive retry for unstable connections
eYD -q 1080 -A 5 -R 50 -p ~/Downloads -f source.txt
```

---

## Output Structure

```
<output dir>/
├── youtube/
│   ├── videos/         ← single YouTube videos
│   ├── shorts/         ← YouTube Shorts
│   ├── playlists/      ← playlists (subdirectory per playlist)
│   └── channels/       ← channel downloads (subdirectory per uploader)
├── other/              ← all other sites (subdirectory per extractor)
├── archive.txt         ← permanent record of downloaded IDs (resume)
├── downloaded.txt      ← URLs processed successfully in this session
└── failed.txt          ← URLs that failed all attempts in this session
```

File naming: `Title [YYYY-MM-DD] [videoID].mkv`

---

## Resume

Every completed download is recorded in `archive.txt`. Re-running the script skips any URL already in the archive. Interrupted partial downloads resume automatically via aria2c.

To force a full re-download, delete `archive.txt`.

---

## Cookies

Required for age-restricted, members-only, or bot-check-protected content.

```bash
eYD -q 1080 -C brave -p ~/Downloads -f source.txt
```

Supported: `brave`, `chrome`, `firefox`, `edge`.  
On Linux, close the browser before running, or eYD will auto-inject `secretstorage` to handle cookie decryption.

---

## Troubleshooting

**"Sign in to confirm you're not a bot"** — pass `-C brave` or your browser.

**"n challenge solving failed"** — no JS runtime. eYD will offer to install deno automatically, or run `sudo apt install nodejs` / `brew install node` manually.

**Subtitles not embedding** — ensure ffmpeg is installed.

**Downloads are slow** — aria2c uses 16 connections. Add a proxy with `-x` if throttled.

**A URL always fails** — check `failed.txt`, then debug manually:
```bash
yt-dlp --list-formats "https://..."
```

---

## License

MIT
