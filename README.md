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

Usage: coub.py [OPTIONS] INPUT [INPUT]... [-o FORMAT]

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
  --mobile               Download mobile video quality (no watermark, 360p)

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

## Changes since Coub's database upgrade (watermark & co)

Coub started to massively overhaul their database and API. Of course those changes aren't documented (why would you document API changes anyway?), so it will take a while to weed through all the changes. A few things I need to change are already clear though:

- [x] Remove video repair (most videos are already stored in a non-broken state and the rest will soon follow)
- [x] Remove mobile option (they now come with a watermark and are the exact same as html5 med) 
- [ ] Use AAC mobile audio, instead of html5 audio med (MP3), which both come at 128Kbps CBR
- [ ] Add shared option (video+audio already combined and audio always the right length)

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
