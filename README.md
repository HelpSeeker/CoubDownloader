# What's new in the last days

There are new bash commands:

* `./save example` saves coubs by specified list example.txt
* `./save_channel undefined-isotope` saves specified channel
* `./save_tag coub_vault` saves coubs by specified tag
* `./save_search vault` saves coubs by specified search term
* `./save_community memes` saves specified community
* `./save_story 2154597-coub_vault` saves specified community
* `./save_hot` saves coubs from the hot section
* `./save_all` saves random coubs again and again

# RIP Coub

Coub will soon be gone, so now is the time to download your favorite coubs, before it's too late.

Because of this many new people have stumbled upon this project and started using it. As much as it hurts to lose Coub, I'm happy to see you all here.

Personally I haven't used CoubDownloader in quite a while. My main focus was Gyre and even that worked well enough for my personal use to not touch its code for almost a year. Because of this you may stumble upon bugs and other problems, that have evaded me all these years.

I will try to address any issues asap during the next two weeks, but please understand that this will be only a life support. My main priority are issues that prevent the correct download of coubs. I won't work on QoL features or force any changes on the dev branch into master. It's too late for that.

Hotfix releases will be available on the release page. Although I advise setting up a Python environment for CoubDownloader and running it directly, as it removes another point of failure and makes debugging easier.

Thank you very much.

# CoubDownloader

CoubDownloader is a simple script to download videos (called coubs) from [Coub](https://coub.com).

**Linux users might be interested in CoubDownloader's successor [Gyre](https://github.com/HelpSeeker/Gyre).**

**Update 2021-01-02: Gyre can now also be used on Windows, but requires an MSYS2 setup (see [Gyre on Windows](https://github.com/HelpSeeker/Gyre#gyre-on-windows)).**

## Contents

1. [Usage](#usage)
2. [Standalone builds](#standalone-builds)
3. [Requirements](#requirements)
    1. [Optional](#optional)
4. [Configuration](#configuration)
5. [Input](#input)
    1. [Overview](#overview)
    2. [Direct coub links](#direct-coub-links)
    3. [Lists](#lists)
    4. [Channels](#channels)
    5. [Searches](#searches)
    6. [Random](#random)
    7. [Tags](#tags)
    8. [Communities](#communities)
    9. [Hot section](#hot-section)
6. [GUI](#gui)
7. [Misc. information](#misc-information)
    1. [Video resolution vs. quality](#video-resolution-vs-quality)
    2. [AAC audio](#aac-audio)
    3. ['share' videos](#share-videos)
    4. [Known problems](#known-problems)

## Usage

```
CoubDownloader is a simple download script for coub.com

Usage: coub.py [OPTIONS] INPUT [INPUT]...

Input:
  URL                   download coub(s) from the given URL
  -i, --id ID           download a single coub
  -l, --list PATH       read coub links from a text file
  -c, --channel NAME    download coubs from a channel
  -t, --tag TAG         download coubs with the given tag
  -e, --search TERM     download search results for the given term
  -m, --community NAME  download coubs from a community
                          NAME as seen in the URL (e.g. animals-pets)
  --hot                 download coubs from the hot section (default sorting)
  --random              download random coubs
  --input-help          show full input help

    Input options do NOT support full URLs.
    Both URLs and input options support sorting (see --input-help).

Common options:
  -h, --help            show this help
  -q, --quiet           suppress all non-error/prompt messages
  -y, --yes             answer all prompts with yes
  -n, --no              answer all prompts with no
  -s, --short           disable video looping
  -p, --path PATH       set output destination (def: '.')
  -k, --keep            keep the individual video/audio parts
  -r, --repeat N        repeat video N times (def: until audio ends)
  -d, --duration TIME   specify max. coub duration (FFmpeg syntax)

Download options:
  --connections N       max. number of connections (def: 25)
  --retries N           number of retries when connection is lost (def: 5)
                          0 to disable, <0 to retry indefinitely
  --limit-num LIMIT     limit max. number of downloaded coubs

Format selection:
  --bestvideo           download best available video quality (def)
  --worstvideo          download worst available video quality
  --max-video FORMAT    set limit for the best video format (def: higher)
                          Supported values: med, high, higher
  --min-video FORMAT    set limit for the worst video format (def: med)
                          Supported values: med, high, higher
  --bestaudio           download best available audio quality (def)
  --worstaudio          download worst available audio quality
  --aac                 prefer AAC over higher quality MP3 audio
  --aac-strict          only download AAC audio (never MP3)
  --share               download 'share' video (shorter and includes audio)

Channel options:
  --recoubs             include recoubs during channel downloads (def)
  --no-recoubs          exclude recoubs during channel downloads
  --only-recoubs        only download recoubs during channel downloads

Preview options:
  --preview COMMAND     play finished coub via the given command
  --no-preview          explicitly disable coub preview

Misc. options:
  --audio-only          only download audio streams
  --video-only          only download video streams
  --write-list FILE     write all parsed coub links to FILE
  --use-archive FILE    use FILE to keep track of already downloaded coubs

Output:
  --ext EXTENSION       merge output with the given extension (def: mkv)
                          ignored if no merge is required
  -o, --output FORMAT   save output with the given template (def: %id%)

    Special strings:
      %id%        - coub ID (identifier in the URL)
      %title%     - coub title
      %creation%  - creation date/time
      %community% - coub community
      %channel%   - channel title
      %tags%      - all tags (separated by _)

    Other strings will be interpreted literally.
    This option has no influence on the file extension.
```

## Standalone builds

Starting with v3.7 standalone Windows builds are provided on the [release page](https://github.com/HelpSeeker/CoubDownloader/releases). These executables don't require an existing Python environment and the [GUI version](#gui) is a standalone application. FFmpeg is still a mandatory requirement.

#### Why no Mac builds?

Because I lack the necessary build environment.

#### Why no Linux builds?

Because I lack the resources to target a variety of distros individually and my attempts to create universal Linux builds were unsuccessful.

The main problem is the usage of external tools like FFmpeg (but also media players with the `--preview` option) via `subprocess.run`. They either spam the terminal output with warnings or outright fail because of library version mismatches between my build environment and the user's system. It would've required me to ship Linux builds with static FFmpeg binaries and either remove the `--preview` option or make it the user's responsibility to get it working. And even then there's still a plethora of problems regarding the GUI version, which I couldn't reliably get to work across a handful of mainstream distros (Debian, Ubuntu, CentOS, Linux Mint, etc.).

## Requirements

* Python >= 3.7
* [FFmpeg](https://www.ffmpeg.org/)

Standalone builds only require FFmpeg.

### Optional

* [aiohttp](https://aiohttp.readthedocs.io/en/stable/) for asynchronous execution **(strongly recommended)**
* [colorama](https://github.com/tartley/colorama) for colorized terminal output on Windows (you should also install it if you want to use `coub-gui.py`)
* [Gooey](https://github.com/chriskiehl/Gooey) to run `coub-gui.py` (be sure to install it with wxPython < 4.1.0)

## Configuration

CoubDownloader's defaults can be changed via a configuration file.

Simply create a text file with the name `coub.conf` in the same location as the script and specify custom defaults in the following format:

```
OPTION = value
```

Lines starting with `#` get treated as comments.

For all available options and their allowed values, please take a look at the [example configuration file](example.conf).

## Input

#### Overview

Accessible via `coub.py --input-help`

```
CoubDownloader Full Input Help

Contents
========

  1. Input Types
  2. Input Methods
  3. Sorting

1. Input Types
==============

  -) Direct coub links
  -) Lists
  -) Channels
  -) Searches
  -) Tags
  -) Communities (incl. Featured & Coub of the Day)
  -) Hot section
  -) Random

2. Input Methods
================

  1) Direct URLs from coub.com (or list paths)

    Single Coub:  https://coub.com/view/1234567
    List:         path/to/list.txt
    Channel:      https://coub.com/example-channel
    Search:       https://coub.com/search?q=example-term
    Tag:          https://coub.com/tags/example-tag
    Community:    https://coub.com/community/example-community
    Hot section:  https://coub.com or https://coub.com/hot
    Random:       https://coub.com/random

    URLs which indicate special sort orders are also supported.

  2) Input option + channel name/tag/search term/etc.

    Single Coub:  -i 1234567            or  --id 1234567
    List:         -l path/to/list.txt   or  --list path/to/list.txt
    Channel:      -c example-channel    or  --channel example-channel
    Search:       -e example-term       or  --search example-term
    Tag:          -t example-tag        or  --tag example-tag
    Community:    -m example-community  or  --community example-community
    Hot section:  --hot
    Random:       --random

  3) Prefix + channel name/tag/search term/etc.

    A subform of 1). Utilizes the script's ability to autocomplete/format
    incomplete URLs.

    Single Coub:  view/1234567
    Channel:      example-channel
    Search:       search?q=example-term
    Tag:          tags/example-tag
    Community:    community/example-community
    Hot section:  hot
    Random:       random

3. Sorting
==========

  Input types which return lists of coub links (e.g. channels or tags)
  support custom sorting/selection methods (I will refer to both as sort
  orders from now on). This is mainly useful when used in combination with
  --limit-num (e.g. download the 100 most popular coubs with a given tag),
  but sometimes it also changes the list of returned links drastically
  (e.g. a community's most popular coubs of a month vs. a week).

  Sort orders can either be specified by providing an URL that already
  indicates special sorting

    https://coub.com/search/likes?q=example-term
    https://coub.com/tags/example-tag/views
    https://coub.com/rising

  or by adding it manually to the input with '#' as separator

    https://coub.com/search?q=example-term#top
    tags/example-tag#views_count
    hot#rising

  This is supported by all input methods, except the --hot option.
  Please note that a manually specified sort order will overwrite the
  sort order as indicated by the URL.

  Supported sort orders
  ---------------------

    Channels:         most_recent (default)
                      most_liked
                      most_viewed
                      oldest
                      random

    Searches:         relevance (default)
                      top
                      views_count
                      most_recent

    Tags:             popular (default)
                      top
                      views_count
                      fresh

    Communities:      hot_daily
                      hot_weekly
                      hot_monthly (default)
                      hot_quarterly
                      hot_six_months
                      rising
                      fresh
                      top
                      views_count
                      random

    Featured:         recent (default)
    (community)       top_of_the_month
                      undervalued

    Coub of the Day:  recent (default)
    (community)       top
                      views_count

    Hot section:      hot_daily
                      hot_weekly
                      hot_monthly (default)
                      hot_quarterly
                      hot_six_months
                      rising
                      fresh

    Random:           popular (default)
                      top

```

***

The following points provide more in-depth information about the different input types, which didn't make it into the overview because of self-imposed space restrictions.

***

#### Direct coub links

A link to a single coub (e.g. https://coub.com/view/123456). This is the most basic form of input and what the other input types boil down to once parsed.

#### Lists

Lists are files on your computer, which will be scanned for direct coub links. In order to detect a direct link, it must separated from the surrounding content via one of the following delimiters:

  * whitespace
  * tab
  * newline

Additionally a direct link must start with 'https://coub.com/view/'.

CoubDownloader itself is also able to create lists with `--write-list`. When used, all parsed links will be outputted to a user-defined file. This helps to avoid additional parsing time, if a long download is split into several sessions, but also to weed out duplicate links in an already existing list.

#### Channels

Channels allow to download all (re)coubs from a single user. The channel options:

  * `--recoubs`
  * `--no-recoubs`
  * `--only-recoubs`

allow fine-grained control over what type of coub to download. As they are global options, they apply to all channels for a single script instance. Story download is not supported.

#### Searches

Searches provide the same results as on Coub's website, with the exception that it is not possible to search for channels.

Using general search terms can potentially return tens of thousands of coub links. The usage of `--limit-num` is encouraged.

#### Random

Provides a random collection of coubs. A request returns max. 1000 coubs, but several requests can be made during one script invocation (e.g. using the --random option thrice).

***

The now following input types only return a limited number of links. This is indirectly enforced by the API, although I can't say if it is done on purpose or a bug (pages >99 redirect to page 1).

Each of the following input types provides at most 2475 direct links.

***

#### Tags

Tags (just like searches) are the same as the user will know them from Coub's website.

Please note that the default sort order (by popularity) provides less results than all the other sort orders.

#### Communities

There are currently 19 supported communities.

The following list shows the names of the supported communities (as seen on Coub's website). In parenthesis are the internally used names and what should be used as input for the script.

* Animals & Pets       (**animals-pets**)
* Mashup               (**mashup**)
* Anime                (**anime**)
* Movies & TV          (**movies**)
* Gaming               (**gaming**)
* Cartoons             (**cartoons**)
* Art & Design         (**art**)
* Music                (**music**)
* News & Politics      (**news**)
* Sports               (**sports**)
* Science & Technology (**science-technology**)
* Celebrity            (**celebrity**)
* Nature & Travel      (**nature-travel**)
* Fashion & Beauty     (**fashion**)
* Dance                (**dance**)
* Auto & Technique     (**cars**)
* NSFW                 (**nsfw**)
* Featured             (**featured**)
* Coub of the Day      (**coub-of-the-day**)

The default sort order for most communities (most popular coubs of the month) may provide less results than other sort orders.

*Featured* and *Coub of the Day* have unique sort orders.

#### Hot section

The currently most popular/trending coubs.

Both

* [https://coub.com/hot](https://coub.com/hot)
* [https://coub.com](https://coub.com)

refer to the hot section and can be used as input.

The default sort order (most popular coubs of the month) may provide less results than other sort orders.

## GUI

A basic GUI, powered by [Gooey](https://github.com/chriskiehl/Gooey), is provided via `coub-gui.py`.

Please note that this is only a quickly thrown together frontend for convenience. The main focus of this project is the CLI tool.

![Settings window on Windows](/images/coub-gui_input_Windows.png) ![Progress window on Linux](/images/coub-gui_execution_Linux.png)

It provides the same functionality as the main CLI tool, with a few notable exceptions:

* No quiet mode
* No overwrite prompt (default prompt answer is set to "no")
* No option equivalent to `--random#top` (direct URL input must be used)
* The output path defaults to "coubs" in the user's home directory instead of the current one

Another important difference is that `coub-gui.py` is **NOT** a standalone script. It depends on `coub.py` being in the same location.

## Misc. information

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

To make matters even more complicated, some users might not want AAC audio at all. This is hopefully only a small demographic (after all AAC support is thorough and it does compress a lot better than MP3), but the script is still able to cater to this group. There's no extra command line option, but look for the following lines inside the script and change `AAC` to 0.

```
    # How much to prefer AAC audio
    # 0 -> never download AAC audio
    # 1 -> rank it between low and high quality MP3
    # 2 -> prefer AAC, use MP3 fallback
    # 3 -> either AAC or no audio
    AAC = 1
```

Now AAC audio will be completely ignored and the script only serves MP3 audio (like the old version).

### 'share' videos

Another special new option is `--share`. Coub now offers a video version primarily targeted at people, who want to share coubs. These videos already contain both video (~1280px width, sometimes ~360px) and audio (AAC@128Kbps CBR) and don't require further muxing. Videos downloaded with `--share` come as MP4.

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

### Known problems

* no error handling or retries if server disconnects during input parsing
* losing your internet connection while downloading will stall the script indefinitely
* some enabling switches (e.g. --keep) don't have a disabling counterpart, so activating their options via a config means you can't disable them at runtime
* using a CLI media player to preview audio files may lead to its keyboard shortcuts not working
* Python 3.8 and newer will print tracebacks (only warnings) when the user interrupts the program (see the Wiki for more infos)
* (GUI only) progress messages don't use monospace fonts on Windows
* (GUI only) having wrong values defined in your config will prevent the GUI from opening (open it from the command line to see the error)
* (GUI only) Gooey seems to be broken for WxPython 4.1.0
