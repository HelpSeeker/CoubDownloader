# CoubDownloader

CoubDownloader is a simple script to download videos (called coubs) from [Coub](https://coub.com).

## Contents

1. [Usage](https://github.com/HelpSeeker/CoubDownloader#usage)  
2. [Requirements](https://github.com/HelpSeeker/CoubDownloader#requirements)  
3. [Input](https://github.com/HelpSeeker/CoubDownloader#input)  
3.1. [Links](https://github.com/HelpSeeker/CoubDownloader#links)  
3.2. [Lists](https://github.com/HelpSeeker/CoubDownloader#lists)  
3.3. [Channels](https://github.com/HelpSeeker/CoubDownloader#channels)  
3.4. [Tags](https://github.com/HelpSeeker/CoubDownloader#tags)  
3.5. [Searches](https://github.com/HelpSeeker/CoubDownloader#searches)  
3.6. [Hot section](https://github.com/HelpSeeker/CoubDownloader#hot-section)  
3.7. [Categories](https://github.com/HelpSeeker/CoubDownloader#categories)  
4. [Misc. information](https://github.com/HelpSeeker/CoubDownloader#misc-information)  
4.1. [Remux errors](https://github.com/HelpSeeker/CoubDownloader#remux-errors-ffmpeg)  
4.2. [Video resolution vs. quality](https://github.com/HelpSeeker/CoubDownloader#video-resolution-vs-quality)  
4.3. [AAC audio](https://github.com/HelpSeeker/CoubDownloader#aac-audio)  
4.4. ['share' videos](https://github.com/HelpSeeker/CoubDownloader#share-videos)  
5. [Changes since Coub's database upgrade (watermark & co)](https://github.com/HelpSeeker/CoubDownloader#changes-since-coubs-database-upgrade-watermark--co)  
6. [Changes since switching to Coub's API (previously used youtube-dl)](https://github.com/HelpSeeker/CoubDownloader#changes-since-switching-to-coubs-api-previously-used-youtube-dl)  

## Usage

```
CoubDownloader is a simple download script for coub.com

Usage: coub.py [OPTIONS] INPUT [INPUT]...

Input:
  LINK                   download specified coubs
  -l, --list LIST        read coub links from a text file
  -c, --channel CHANNEL  download coubs from a channel
  -t, --tag TAG          download coubs with the specified tag
  -e, --search TERM      download search results for the given term
  --hot                  download coubs from the 'Hot' section
  --category CATEGORY    download coubs from a certain category
                         '--category help' for all supported values

Common options:
  -h, --help             show this help
  -q, --quiet            suppress all non-error/prompt messages
  -y, --yes              answer all prompts with yes
  -n, --no               answer all prompts with no
  -s, --short            disable video looping
  -p, --path PATH        set output destination (def: '.')
  -k, --keep             keep the individual video/audio parts
  -r, --repeat N         repeat video N times (def: until audio ends)
  -d, --duration TIME    specify max. coub duration (FFmpeg syntax)

Download options:
  --sleep TIME           pause the script for TIME seconds before each download
  --limit-num LIMIT      limit max. number of downloaded coubs
  --sort ORDER           specify download order for channels, tags, etc.
                         '--sort help' for all supported values

Format selection:
  --bestvideo            Download best available video quality (def)
  --worstvideo           Download worst available video quality
  --max-video FORMAT     Set limit for the best video format (def: 'higher')
                         Supported values: med, high, higher
  --min-video FORMAT     Set limit for the worst video format (def: 'med')
                         Supported values: see '--max-video'
  --bestaudio            Download best available audio quality (def)
  --worstaudio           Download worst available audio quality
  --aac                  Prefer AAC over higher quality MP3 audio
  --aac-strict           Only download AAC audio (never MP3)
  --share                Download 'share' video (shorter and includes audio)

Channel options:
  --recoubs              include recoubs during channel downloads (def)
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
  -o, --output FORMAT    save output with the specified name (def: %id%)

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

#### Hot section

The currently most popular/trending coubs can be found in the [hot section](https://coub.com/hot). Similar to tags, you can only download the first 99 pages (i.e. 2475 coubs) listed. All pages afterwards will redirect to page 1.

#### Categories

There are currently 20 supported categories. 17 communities and 3 special categories (newest, random and coub_of_the_day). Categories limit the max. number of pages just like tags and the hot section. So once again max. 2475 coubs per category.

***

Please note that URLs mustn't include a special sort order (e.g. https://coub.com/tags/tag/likes) or other filters (e.g. https://coub.com/user/reposts). The last word in a URL needs to be the channel name, tag, search term, etc.

***

Input gets parsed in the following order:

* Links  
* Lists  
* Channels  
* Tags
* Searches
* Categories
* Hot section

## Misc. information

### Remux errors (FFmpeg)

```
[mov,mp4,m4a,3gp,3g2,mj2 @ 0x563bd7dcf740] moov atom not found
[concat @ 0x563bd7d883c0] Impossible to open 'abcdef.mp4'
list.txt: Invalid data found when processing input
```

These errors are the product of encountering a not yet updated video stream. In the past Coub stored all HTML5 video streams in a broken state, but nowadays it's quite rare to find such streams. Only ~1% of all low quality streams are affected.

To download these problematic streams, please refer to the [legacy version](https://github.com/HelpSeeker/CoubDownloader/releases/tag/v1).

### Video resolution vs. quality

Resolution is not a synonym for quality. That is what everybody with a bit of knowledge in video encoding will tell you. It is important to remember, when we discuss the quality of available video streams.

Coub usually offers 3 video streams:

* higher (~1600px width)
* high (~1280px width)
* med (~640px width)

This is also the order in which *coub.py* ranks those video streams. Said ranking can be limited with `--min-/--max-video` and the final choice depends on `--best-/--worstvideo`. But the question is, does this really reflect the quality of those streams? And the answer is: **No**

The main problem is that Coub does something very peculiar. In order to provide several available streams, they don't just scale input videos down, but also up. This is a recent change. Before the introduction of the watermarks, you would find coubs, which were only available in 360p, simply because a low resolution input video was used. Now you can find the same video in 900p as well, because they (quite noticeably) upscaled the low resolution input.

This makes it very difficult to discern which stream actually offers the best quality. Not because of the used compression settings (Coub reencodes look equally bad at all resolutions), but because of the details lost in the scaling process. Usually you want to get the stream, which has the resolution closest to the source video and scale it yourself during playback. A properly configured media player can produce far better results than Coub's blurry upscaling. But even if blurry upscaling is preferred (e.g. to mitigate compression artifacts), you will save a considerate amount of disk space by letting your media player handle the scaling process.

But how to apply that knowledge in practice? How do you know which stream to download? Well, I'm still looking for an answer myself. The only accurate method is to download all versions and compare them yourself. Details are a good indicator to look out for. Pick the stream which still has the most of them left. Alternatively you can also compare, which stream looks the sharpest to you.

Unfortunately there's no clear rule, which would help to automate the decision process. However based on my personal experience I can give you the following hint. The best quality is often 'high', sometimes 'med' and almost never 'higher'.

### AAC audio

I'd like to quickly address how *coub.py* handles AAC audio, because it might be a bit confusing.

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

Coub started to massively overhaul their database and API. Of course those changes aren't documented (why would you document API changes anyway?).

- [x] Remove video repair (most videos are already stored in a non-broken state and the rest will soon follow)
- [x] Remove mobile option (they now come with a watermark and are the exact same as html5 med) 
- [x] Add AAC mobile audio as another possible audio version (ranked between low and high quality MP3 audio)
- [x] Add options to prefer AAC or only download AAC audio
- [x] Add shared option (video+audio already combined)
- [x] Download coubs from the hot section
- [x] Download coubs from categories

## Changes since switching to Coub's API (previously used youtube-dl)

- [x] Download all coubs from a channel
- [x] Download all recoubs from a channel  
- [x] Limit number of downloaded coubs  
- [x] Wait x seconds between downloads
- [x] ~~Limit download speed~~ (was only possible in the Bash version)
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
