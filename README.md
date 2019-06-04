# CoubDownloader

CoubDownloader is a simple script to download videos (called coubs) from [Coub](https://coub.com).  

### Usage

```
CoubDownloader is a simple download script for coub.com
Usage: coub.sh [OPTIONS] INPUT [INPUT]...

Input:
 LINK                  download specified coubs
 -l, --list LIST       read coub links from a text file
 -c, --channel CHANNEL download all coubs from a channel

Options:
 -h, --help             show this help
 -y, --yes              answer all prompts with yes
 -n, --no               answer all prompts with no
 -s, --short            disable video looping
 -p, --path PATH        set output destination (default: $HOME/coub)
 -k, --keep             keep the individual video/audio parts
 -r, --repeat N         repeat video n times (default: until audio ends)
 -d, --duration TIME    specify max. coub duration (FFmpeg syntax)
 --recoubs              include recoubs during channel downloads (default)
 --no-recoubs           exclude recoubs during channel downloads
 --only-recoubs         only download recoubs during channel downloads
 --preview COMMAND      play finished coub via the given command
 --no-preview           explicitly disable coub preview
 --audio-only           only download the audio
 --video-only           only download the video
 --limit-rate RATE      limit download rate (see wget's --limit-rate)
 --limit-num LIMIT      limit max. number of downloaded coubs
 --sleep TIME           pause the script for TIME seconds before each download
```

### Requirements

* Bash >= 4.0
* [jq](https://stedolan.github.io/jq/)
* [FFmpeg](https://www.ffmpeg.org/)
* [curl](https://curl.haxx.se/)
* [wget](https://www.gnu.org/software/wget/)
* [grep](https://www.gnu.org/software/grep/)

### Defaults (and how to change them)

All default settings can be found at the beginning of the script.

**Path:** Change `save_path="$HOME/coub"` to a different (ideally absolute) path

**Max. duration:** Uncomment `duration="-t 00:01:00.000"` and change `00:01:00.000` to the desired max. duration (see: [FFmpeg's time syntax](https://ffmpeg.org/ffmpeg-utils.html#time-duration-syntax))

**Preview:** Change `preview=false` to true and `preview_command="mpv"` to the desired playback command

**Download rate:** Uncomment `limit_rate="--limit-rate=100K"` and change `100K` to the desired max. download rate (see: [wget's --limit-rate](https://www.gnu.org/software/wget/manual/html_node/Download-Options.html#Download-Options))

The other defaults should be self-explanatory.  
Please note that the following settings are mutually exclusive (one of them has to be false):  

* audio_only and video_only  
* recoubs and only_recoubs

### Input lists

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

### Changes to the new version

This list documents the (planned) changes since switching from youtube-dl to Coub's API.  

- [x] Download all coubs from a channel
- [x] Download all recoubs from a channel  
- [x] Limit number of downloaded coubs  
- [x] Wait x seconds between downloads  
- [x] Limit download speed  
- [ ] Download all coubs with a certain tag  
- [x] Check for the existence of a coub before downloading  
- [ ] Different verbosity levels
- [ ] Keep track of already downloaded coubs
- [ ] Download stories*
- [x] Specify max. coub duration (FFmpeg syntax)

*Story support will be more difficult to implement, as Coub's API doesn't provide any related endpoint. It will require conventional scraping, after JS execution with a headless browser.
