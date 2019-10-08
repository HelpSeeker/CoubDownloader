# CoubDownloader

CoubDownloader is a simple script to download videos (called coubs) from [Coub](https://coub.com).  

## coub.py vs. coub_v2.py

*coub.py* and *coub_v2.py* are both standalone scripts with almost the same functionality.

The main difference is that *coub.py* was developed with Coub's old database in mind (before they introduced watermarks), while *coub_v2.py* adapts to the new changes.

For now *coub.py* is safer to use. It still repairs videos (Coub stored all html5 streams in a broken state in the past) and allows to download coubs without a watermark (`--mobile`) if the old mobile version is still present (unfortunately it's already quite rare).

Eventually *coub_v2.py* will replace *coub.py*.

In the meantime, if you use *coub_v2.py* and run into errors like

```
[mov,mp4,m4a,3gp,3g2,mj2 @ 0x563bd7dcf740] moov atom not found
[concat @ 0x563bd7d883c0] Impossible to open 'abcdef.mp4'
list.txt: Invalid data found when processing input
```

then please switch to *coub.py* for these problematic coubs, which still use the old html5 video streams.

## Usage

```
CoubDownloader is a simple download script for coub.com

Usage: coub_v2.py [OPTIONS] INPUT [INPUT]... [-o FORMAT]

Input:
  LINK                   download specified coubs
  -l, --list LIST        read coub links from a text file
  -c, --channel CHANNEL  download all coubs from a channel
  -t, --tag TAG          download all coubs with the specified tag
  -e, --search TERM      download all search results for the given term

Common options:
  -h, --help             show this help
  -q, --quiet            suppress all non-error/prompt messages
  -y, --yes              answer all prompts with yes
  -n, --no               answer all prompts with no
  -s, --short            disable video looping
  -p, --path PATH        set output destination (default: '.')
  -k, --keep             keep the individual video/audio parts
  -r, --repeat N         repeat video N times (default: until audio ends)
  -d, --duration TIME    specify max. coub duration (FFmpeg syntax)

Download options:
  --sleep TIME           pause the script for TIME seconds before each download
  --limit-num LIMIT      limit max. number of downloaded coubs
  --sort ORDER           specify download order for channels/tags
                         Allowed values:
                           newest (default)      likes_count
                           newest_popular        views_count
                           oldest (tags/search only)

Format selection:
  --bestvideo            Download best available video quality (default)
  --worstvideo           Download worst available video quality
  --bestaudio            Download best available audio quality (default)
  --worstaudio           Download worst available audio quality
  --aac                  Prefer AAC over higher quality MP3 audio
  --aac-strict           Only download AAC audio (never MP3)
  --share                Download 'share' video (shorter and includes audio)

Channel options:
  --recoubs              include recoubs during channel downloads (default)
  --no-recoubs           exclude recoubs during channel downloads
  --only-recoubs         only download recoubs during channel downloads

Preview options:
  --preview COMMAND      play finished coub via the given command
  --no-preview           explicitly disable coub preview

Misc. options:
  --audio-only           only download audio streams
  --video-only           only download video streams
  --write-list FILE      write all parsed coub links to FILE
  --use-archive FILE     use FILE to keep track of already downloaded coubs

Output:
  -o, --output FORMAT    save output with the specified name (default: %id%)

    Special strings:
      %id%        - coub ID (identifier in the URL)
      %title%     - coub title
      %creation%  - creation date/time
      %category%  - coub category
      %channel%   - channel title
      %tags%      - all tags (separated by '_')

    Other strings will be interpreted literally.
    This option has no influence on the file extension.
```

## Requirements

* Python >= 3.6
* [FFmpeg](https://www.ffmpeg.org/)

## Input

#### Links

The simplest form of input is a direct link to a coub. Only strings that contain `coub.com/view/` will get parsed as coub links.

#### Lists

A list is a simple text file containing one or more coub links. Links must be separated by a white space, tab or new line. Like before only strings that contain `coub.com/view/` will get parsed as coub links.

Example:

```
https://coub.com/view/111111
https://coub.com/view/222222
https://coub.com/view/333333
https://coub.com/view/444444
https://coub.com/view/555555 https://coub.com/view/666666 https://coub.com/view/777777
```

`--write-list` can be used to parse links, lists, channels and tags and output all found coub links into a list for later usage.

#### Channels

Whole channels can be downloaded by providing a full URL or the name of the channel (the name as seen in the URL). By default both original coubs and recoubs will be downloaded. `--no-recoubs` will skip all recoubs, while `--only-recoubs` will only download recoubs.

#### Tags

Tags can be scraped by providing the term or a full URL. Due to a bug (?) in the Coub API you can only download the first 99 pages (i.e. 2475 coubs) listed. All pages afterwards will redirect to page 1.

#### Searches

Coubs from search queries can be downloaded by providing the search term or the corresponding search URL. Please note that searches can (in extreme cases) provide tens of thousands of coub links. The usage of `--limit-num` is advised. 

***

Please note for **channels**, **tags** and **searches** that the URL mustn't include a special sort order (e.g. https://coub.com/tags/tag/likes) or other filters (e.g. https://coub.com/user/reposts). The last word in the URL needs to be the channel name, tag or search term.

***

Input gets parsed in the following order:

* Links  
* Lists  
* Channels  
* Tags
* Searches

## Misc. information

### AAC audio

I'd like to quickly address how *coub_v2.py* handles AAC audio, because it might be a bit confusing.

The script gathers potential audio streams and chooses the final link based on `--best-/worstaudio`.

The audio streams are by default ranked in the following order:

* MP3@160Kbps VBR
* AAC@128Kbps CBR
* MP3@128Kbps CBR

So it's pretty uncommon to get AAC audio. Only if the high quality MP3 audio stream isn't present, will the script switch to AAC. However, some users might prefer AAC audio, which is why I added the `--aac` and `--aac-strict` options.

With `--aac` the ranking will simply change to:

* AAC@128Kbps CBR
* MP3@160Kbps VBR
* MP3@128Kbps CBR

It basically tells the script to rank AAC higher than anything else. On the other hand `--aac-strict` reduces the ranking to:

* AAC@128Kbps CBR

Either an AAC stream is present or the audio will be entirely missing. This ensures AAC audio under any circumstances. Another way to look at it is that `--aac` tries to download AAC with MP3 as fallback, while `--aac-strict` gets rid of the fallback.

To make matters even more complicated, some users might not want AAC audio at all. This is hopefully only a small demographic (after all AAC support is thorough and it does compress a lot better than MP3), but the script is still able to cater to this group. There's no extra command line option, but look for the following lines inside the script and change `aac` to 0.

```
    # How much to prefer AAC audio
    # 0 -> never download AAC audio
    # 1 -> rank it between low and high quality MP3
    # 2 -> prefer AAC, use MP3 fallback
    # 3 -> either AAC or no audio
    aac = 1
```

Now AAC audio will be completely ignored and the script only serves MP3 audio (like the old version).

### 'share' videos

Another special new option is `--share`. Coub now offers a video version primarily targeted at people, who want to share coubs. These videos already contain both video (~720p, sometimes ~360p) and audio (AAC@128Kbps CBR) and don't require further muxing. Videos downloaded with `--share` come as MP4.

***

**WARNING:** There's a danger of overwriting *share* videos with video-only streams, as they both come as MP4.

***

The downside is that the audio is often considerably shorter than the other available audio streams. Sometimes that's beneficial, as Coub tends to loop the audio for short tracks (e.g. 2x 25 sec. audio). Often you just lose a lot of audio duration though (e.g. 3 min. song gets reduced to 20 sec.).

Also because of the special property of the *share* version, there are some pitfalls to look out for. Many options become useless, when used together with `--share`

* `--short`
* `--keep`
* `--repeat`
* `--duration`
* all other format selection options
* `--audio-only` and `--video-only` (throws error)

There's no fallback for *share* videos. If the *share* version is not yet available, then the script will count the coub as unavailable.

## Changes since Coub's database upgrade (watermark & co)

Coub started to massively overhaul their database and API. Of course those changes aren't documented (why would you document API changes anyway?), so it will take a while to weed through all the changes. A few things I need to change are already clear though:

- [x] Remove video repair (most videos are already stored in a non-broken state and the rest will soon follow)
- [x] Remove mobile option (they now come with a watermark and are the exact same as html5 med) 
- [x] Add AAC mobile audio as another possible audio version (ranked between low and high quality MP3 audio)
- [x] Add options to prefer AAC or only download AAC audio
- [x] Add shared option (video+audio already combined)

~~I also need to find out if they already overhauled all videos. Otherwise I need to keep the old approach for compatibility, until they're finished.~~ 

They aren't finished yet. There's also no predictable pattern for their update process. For now it's best to keep the old script for compatibility.

## Changes since switching to Coub's API (previously used youtube-dl)

- [x] Download all coubs from a channel
- [x] Download all recoubs from a channel  
- [x] Limit number of downloaded coubs  
- [x] Wait x seconds between downloads  
- [x] Limit download speed  
- [x] Download all coubs with a certain tag  
- [x] Check for the existence of a coub before downloading  
- [x] Specify max. coub duration (FFmpeg syntax) 
- [x] Keep track of already downloaded coubs  
- [x] Export parsed coub links (from channels or tags) to a file for later usage
- [x] Different verbosity levels   
- [x] Choose download order for channels and tags
- [x] Custom output formatting
- [x] Download all coubs from a search query
- [x] Choose what video/audio quality to download
- [x] ~~Download videos for mobile devices to avoid watermarks~~ (not possible anymore)
- [ ] Download stories*  

*Story support will be more difficult to implement, as Coub's API doesn't provide any related endpoint. It will require conventional scraping, after JS execution with a headless browser.
