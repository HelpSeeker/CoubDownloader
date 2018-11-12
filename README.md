# CoubDownloader
```
CoubDownloader is a simple download script for coub.com
Usage: coub.sh [OPTIONS] LINK [LINK]...

Options:
 -h, --help			show this help
 -y, --yes			answer all prompts with yes
 -s, --short			disable video looping
 -p, --path <path>		set output destination (default: $HOME/coub)
 --preview <command>		play finished coub via the given command
```

### Requirements

* [youtube-dl](https://github.com/rg3/youtube-dl)
* [FFmpeg](https://www.ffmpeg.org/) (incl. ffprobe)
* Bash >= 4.0

### Change default path

At the beginning of the script change `save_path="$HOME/coub"` to whatever default path you want.

