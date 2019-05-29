# CoubDownloader

### What is new_coub.sh?

new_coub.sh aims to provide a new approach for downloading coubs. Instead of using youtube-dl, the script utilizes Coub's API.  

The following changes will be or have been implemented in this version.  
Some of them might get backported to the old version.  

- [x] Download all coubs from a channel (only native coubs work yet, reposts fail to download)  
- [ ] Download all reposts from a channel  
- [ ] Limit number of downloaded coubs  
- [ ] Wait x seconds between downloads  
- [ ] Limit download speed  
- [ ] Download all coubs with a certain tag  
- [ ] Check for the existence of a coub before downloading  
- [ ] Allow different verbosity levels  

```
CoubDownloader is a simple download script for coub.com
Usage: new_coub.sh [OPTIONS] LINK [LINK]...
  or   new_coub.sh [OPTIONS] -l LIST [-l LIST]...
  or   new_coub.sh [OPTIONS] -c CHANNEL [-c CHANNEL]...

Options:
 -h, --help             show this help
 -y, --yes              answer all prompts with yes
 -s, --short            disable video looping
 -p, --path <path>      set output destination (default: $HOME/coub)
 -k, --keep             keep the individual video/audio parts
 -l, --list <file>      read coub links from a text file
 -c, --channel <link>   download all coubs from a channel
 -r, --repeat <n>       repeat video n times (default: until audio ends)
 --preview <command>    play finished coub via the given command
 --no-preview           explicitly disable coub preview
 --audio-only           only download the audio
 --video-only           only download the video
```

### Requirements

* Bash >= 4.0
* [jq](https://stedolan.github.io/jq/)
* [FFmpeg](https://www.ffmpeg.org/)
* [curl](https://curl.haxx.se/)
* [wget](https://www.gnu.org/software/wget/)
* [grep](https://www.gnu.org/software/grep/)

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
