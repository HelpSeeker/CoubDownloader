# CoubDownloader
```
CoubDownloader is a simple download script for coub.com
Usage: coub.sh [OPTIONS] LINK [LINK]...
  or   coub.sh [OPTIONS] -l LIST [-l LIST]...

Options:
 -h, --help			show this help
 -y, --yes			answer all prompts with yes
 -s, --short			disable video looping
 -p, --path <path>		set output destination (default: $HOME/coub)
 -k, --keep			keep the individual video/audio parts
 -l, --list <file>		read coub links from a text file
 -r, --repeat <n>		repeat video n times (default: until audio ends)
 --preview <command>		play finished coub via the given command
 --audio-only			only download the audio
 --video-only			only download the video
```

### Requirements

* [youtube-dl](https://github.com/rg3/youtube-dl)
* [FFmpeg](https://www.ffmpeg.org/)
* Bash >= 4.0

### Change defaults

All the following settings can be found at the beginning of the script.

**Path:** Change `save_path="$HOME/coub"` to whatever default path you want.

**Preview:** Change `preview=false` to true and `preview_command="mpv"` to whatever default command you want.

All other settings can be made default by changing their value from `false` to `true`.

### Input list(s)

For easier usage the script accepts lists of coub links in the form of text files. Just make sure each link is either on a new line or separated from the prior one by a white space.

For example:

```
https://coub.com/view/111111
https://coub.com/view/222222
https://coub.com/view/333333
https://coub.com/view/444444
https://coub.com/view/555555 https://coub.com/view/666666 https://coub.com/view/777777
```

Links that don't contain `coub.com/view/` will be silently ignored.
