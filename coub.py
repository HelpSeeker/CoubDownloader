#!/usr/bin/env python3

import sys
import os
import time
import json
import subprocess
from fnmatch import fnmatch

import urllib.error
from urllib.request import urlopen
from urllib.parse import quote as urlquote

try:
    import asyncio
    import aiohttp
    aio = True
except ModuleNotFoundError:
    aio = False

# TODO
# -) implement --limit-rate
# -) look out for new API changes

# Error codes
# 1 -> missing required software
# 2 -> invalid user-specified option
# 3 -> misc. runtime error (missing function argument, unknown value in case, etc.)
# 4 -> not all input coubs exist after execution (i.e. some downloads failed)
# 5 -> termination was requested mid-way by the user (i.e. Ctrl+C)
err_stat = {
    'dep': 1,
    'opt': 2,
    'run': 3,
    'down': 4,
    'int': 5
}

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Classes
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

class Options:
    """Stores general options"""

    # Change verbosity of the script
    # 0 for quiet, >= 1 for normal verbosity
    verbosity = 1

    # Allowed values: yes, no, prompt
    prompt_answer = "prompt"

    # Default download destination
    path = "."

    # Keep individual video/audio streams
    keep = False

    # How often to loop the video
    # If longer than audio duration -> audio decides length
    repeat = 1000

    # Max. coub duration (FFmpeg syntax)
    dur = None

    # Max no. of connections for aiohttp's ClientSession
    # Be careful with this limit. Trust me.
    # Raising it too high can potentially stall the script indefinitely
    connect = 25

    # No. of coubs to process per batch
    # Within a batch pre- and postprocessing are done at once
    # Downloading may be distributed to several threads
    # 0 -> single batch for all coubs
    # 1 -> one coub at a time
    batch = 1

    # Pause between downloads (in sec)
    sleep_dur = None

    # Limit how many coubs can be downloaded during one script invocation
    max_coubs = None

    # Default sort order
    sort = None

    # What video/audio quality to download
    #  0 -> worst quality
    # -1 -> best quality
    # Everything else can lead to undefined behavior
    v_quality = -1
    a_quality = -1

    # Limits for the list of video streams
    #   max: limits what counts as best stream
    #   min: limits what counts as worst stream
    # Supported values: med (~640px width), high (~1280px width), higher (~1600px width)
    v_max = 'higher'
    v_min = 'med'

    # How much to prefer AAC audio
    # 0 -> never download AAC audio
    # 1 -> rank it between low and high quality MP3
    # 2 -> prefer AAC, use MP3 fallback
    # 3 -> either AAC or no audio
    aac = 1

    # Use shared video+audio instead of merging separate streams
    share = False

    # Download reposts during channel downloads
    recoubs = True

    # ONLY download reposts during channel downloads
    only_recoubs = False

    # Show preview after each download with the given command
    preview = False
    preview_command = "mpv"

    # Only download video/audio stream
    # Can't be both true!
    a_only = False
    v_only = False

    # Output parsed coubs to file instead of downloading
    # DO NOT TOUCH!
    out_file = None

    # Use an archive file to keep track of downloaded coubs
    archive_file = None

    # Output name formatting (default: %id%)
    # Supports the following special keywords:
    #   %id%        - coub ID (identifier in the URL)
    #   %title%     - coub title
    #   %creation%  - creation date/time
    #   %category%  - coub category
    #   %channel%   - channel title
    #   %tags%      - all tags (separated by tag_sep, see below)
    # All other strings are interpreted literally.
    #
    # Setting a custom value severely increases skip duration for existing coubs
    # Usage of an archive file is recommended in such an instance
    out_format = None

    # Advanced settings
    coubs_per_page = 25       # allowed: 1-25
    tag_sep = "_"

class CoubInputData:
    """Stores coub-related data (e.g. links)"""

    links = []
    lists = []
    channels = []
    tags = []
    searches = []
    categories = []
    hot = False

    parsed = []
    count = 0

    def check_category(self, cat):
        """Make sure only valid categories get accepted"""

        allowed_cat = [
            "animals-pets",
            "anime",
            "art",
            "cars",
            "cartoons",
            "celebrity",
            "dance",
            "fashion",
            "gaming",
            "mashup",
            "movies",
            "music",
            "nature-travel",
            "news",
            "nsfw",
            "science-technology",
            "sports",
            # Special categories
            "newest",
            "random",
            "coub_of_the_day"
        ]

        cat = cat.split("/")[-1]

        return bool(cat in allowed_cat)

    def parse_links(self):
        """Parse direct input links from the command line"""

        for link in self.links:
            if opts.max_coubs and len(self.parsed) >= opts.max_coubs:
                break
            self.parsed.append(link)

        if self.links:
            msg("Reading command line:")
            msg(f"  {len(self.links)} link(s) found")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def parse_lists(self):
        """Parse coub links from input lists"""

        for l in self.lists:
            msg(f"Reading input list ({l}):")

            with open(l, "r") as f:
                content = f.read()

            # Replace tabs and spaces with newlines
            # Emulates default wordsplitting in Bash
            content = content.replace("\t", "\n")
            content = content.replace(" ", "\n")
            content = content.splitlines()

            for link in content:
                if opts.max_coubs and len(self.parsed) >= opts.max_coubs:
                    break
                self.parsed.append(link)

            msg(f"  {len(content)} link(s) found")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def parse_timeline(self, url_type, url):
        """
        Parse coub links from various Coub source

        Currently supports
        -) channels
        -) tags
        -) coub searches
        """

        if url_type == "channel":
            channel = url.split("/")[-1]
            req = "https://coub.com/api/v2/timeline/channel/" + channel
            req += "?"
        elif url_type == "tag":
            tag = url.split("/")[-1]
            tag = urlquote(tag)
            req = "https://coub.com/api/v2/timeline/tag/" + tag
            req += "?"
        elif url_type == "search":
            search = url.split("=")[-1]
            search = urlquote(search)
            req = "https://coub.com/api/v2/search/coubs?q=" + search
            req += "&"
        elif url_type == "category":
            cat = url.split("/")[-1]
            req = "https://coub.com/api/v2/timeline/explore/" + cat
            req += "?"
        elif url_type == "hot":
            req = "https://coub.com/api/v2/timeline/hot"
            req += "?"
        else:
            err("Error: Unknown input type in parse_timeline!")
            sys.exit(err_stat['run'])

        req += "per_page=" + str(opts.coubs_per_page)

        # Add sort order
        # Different timeline types support different values
        # Invalid values get ignored though, so no need for further checks
        if opts.sort:
            req += "&order_by=" + opts.sort

        req_json = urlopen(req).read()
        req_json = json.loads(req_json)

        pages = req_json['total_pages']

        msg(f"Downloading {url_type} info ({url}):")

        for p in range(1, pages+1):
            # tag/hot section/category timeline redirects pages >99 to page 1
            # other timelines work like intended
            if url_type in ("tag", "hot", "category") and p > 99:
                msg("  Max. page limit reached!")
                return

            msg(f"  {p} out of {pages} pages")
            req_json = urlopen(req + "&page=" + str(p)).read()
            req_json = json.loads(req_json)

            for c in range(opts.coubs_per_page):
                if opts.max_coubs and len(self.parsed) >= opts.max_coubs:
                    return

                try:
                    c_id = req_json['coubs'][c]['recoub_to']['permalink']
                    if not opts.recoubs:
                        continue
                    self.parsed.append("https://coub.com/view/" + c_id)
                except (TypeError, KeyError, IndexError):
                    if opts.only_recoubs:
                        continue
                    try:
                        c_id = req_json['coubs'][c]['permalink']
                        self.parsed.append("https://coub.com/view/" + c_id)
                    except (TypeError, KeyError, IndexError):
                        continue


    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def find_dupes(self):
        """Find and remove duplicates from the parsed list"""
        dupes = 0

        self.parsed.sort()
        last = self.parsed[-1]

        for i in range(len(self.parsed)-2, -1, -1):
            if last == self.parsed[i]:
                dupes += 1
                del self.parsed[i]
            else:
                last = self.parsed[i]

        return dupes

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def parse_input(self):
        """Parse coub links from all available sources"""

        self.parse_links()
        self.parse_lists()
        for c in self.channels:
            self.parse_timeline("channel", c)
        for t in self.tags:
            self.parse_timeline("tag", t)
        for s in self.searches:
            self.parse_timeline("search", s)
        for c in self.categories:
            self.parse_timeline("category", c)
        if self.hot:
            self.parse_timeline("hot", "https://coub.com/hot")

        if not self.parsed:
            err("Error: No coub links specified!")
            sys.exit(err_stat['opt'])

        if opts.max_coubs and len(self.parsed) >= opts.max_coubs:
            msg(f"\nDownload limit ({opts.max_coubs}) reached!")

        msg("\nResults:")
        msg(f"  {len(self.parsed)} input link(s)")
        msg(f"  {self.find_dupes()} duplicates")
        msg(f"  {len(self.parsed)} output link(s)")

        if opts.out_file:
            with open(opts.out_file, "a") as f:
                for link in self.parsed:
                    print(link, file=f)
            msg(f"\nParsed coubs written to '{opts.out_file}'!")
            sys.exit(0)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def update_count(self):
        self.count = len(self.parsed)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

class CoubBuffer():
    """Store batches of coubs to be processed"""

    def __init__(self):
        self.coubs = []
        self.existing = 0
        self.errors = 0

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def print_progress(self):
        if len(self.coubs) == 1:
            msg(f"  {count} out of {coubs.count} (https://coub.com/view/{self.coubs[0]['id']})")
        else:
            msg(f"  {count} out of {coubs.count}")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def def_existence(self):
        """
        Pass existing files to avoid unnecessary downloads
        This check handles archive file search and default output formatting
        # Avoids json request (slow!) just to skip files anyway
        """
        global done

        for i in range(len(self.coubs)-1, -1, -1):
            c_id = self.coubs[i]['id']

            if (opts.archive_file and read_archive(c_id)) or \
               (not opts.out_format and exists(c_id) and not overwrite()):
                if len(self.coubs) == 1:
                    msg("Already downloaded!")
                self.existing += 1
                done += 1
                del self.coubs[i]

        if len(self.coubs) > 1 and not opts.out_format and self.existing:
            msg(f"{self.existing} coubs already downloaded!")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def parse_json(self):
        for i in range(len(self.coubs)-1, -1, -1):
            req = "https://coub.com/api/v2/coubs/" + self.coubs[i]['id']
            try:
                with urlopen(req) as resp:
                    resp_json = json.load(resp)
            except urllib.error.HTTPError:
                if len(self.coubs) == 1:
                    err("Error: Coub unavailable!")
                self.errors += 1
                del self.coubs[i]
                continue

            v_list, a_list = stream_lists(resp_json)
            try:
                self.coubs[i]['v_link'] = v_list[opts.v_quality]
            except IndexError:
                if len(self.coubs) == 1:
                    err("Error: Coub unavailable!")
                self.errors += 1
                del self.coubs[i]
                continue

            try:
                self.coubs[i]['a_link'] = a_list[opts.a_quality]
            except IndexError:
                self.coubs[i]['a_link'] = None
                if opts.a_only:
                    if len(self.coubs) == 1:
                        err("Error: Audio or coub unavailable!")
                    self.errors += 1
                    del self.coubs[i]
                    continue

            if opts.v_only:
                self.coubs[i]['a_link'] = None
            if opts.a_only:
                self.coubs[i]['v_link'] = None

            name = get_name(resp_json, self.coubs[i]['id'])

            self.coubs[i]['name'] = name
            self.coubs[i]['v_name'] = f"{name}.mp4"
            # Needs special treatment since audio link can be None
            if self.coubs[i]['a_link']:
                a_ext = self.coubs[i]['a_link'].split(".")[-1]
                self.coubs[i]['a_name'] = f"{name}.{a_ext}"
            else:
                self.coubs[i]['a_name'] = None

        if len(self.coubs) > 1 and self.errors:
            msg(f"{self.errors} coubs unavailable!")
        # Reset counter to differentiate between errors before/after download
        self.errors = 0

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def custom_existence(self):
        """
        Another check for custom output formatting
        Far slower to skip existing files (archive usage is recommended)
        """
        global done

        for i in range(len(self.coubs)-1, -1, -1):
            if exists(self.coubs[i]['name']) and not overwrite():
                if len(self.coubs) == 1:
                    msg("Already downloaded!")
                self.existing += 1
                done += 1
                del self.coubs[i]

        if len(self.coubs) > 1 and self.existing:
            msg(f"{self.existing} coubs already downloaded!")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def check_streams(self):
        for i in range(len(self.coubs)-1, -1, -1):
            v_name = self.coubs[i]['v_name']
            a_name = self.coubs[i]['a_name']

            # Whether a download was successful gets tested here
            # If wanted stream is present -> success
            # I'm not happy with this solution
            if not opts.a_only and not os.path.exists(v_name):
                if len(self.coubs) == 1:
                    err("Error: Coub unavailable!")
                self.errors += 1
                del self.coubs[i]
                continue

            if not opts.v_only and a_name and not os.path.exists(a_name):
                self.coubs[i]['a_name'] = None
                if opts.a_only:
                    if len(self.coubs) == 1:
                        err("Error: Audio or coub unavailable!")
                    self.errors += 1
                    del self.coubs[i]
                    continue

        if len(self.coubs) > 1 and self.errors:
            msg(f"{self.errors} coubs failed to download!")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def merge(self):
        for c in self.coubs:
            try:
                if not c['a_name']:
                    continue

                # Print .txt for ffmpeg's concat
                with open(f"{c['name']}.txt", "w") as f:
                    for j in range(opts.repeat):
                        print(f"file '{c['v_name']}'", file=f)

                # Loop footage until shortest stream ends
                # Concatenated video (via list) counts as one long stream
                command = [
                    "ffmpeg", "-y", "-v", "error",
                    "-f", "concat", "-safe", "0",
                    "-i", f"{c['name']}.txt", "-i", f"{c['a_name']}"
                ]
                if opts.dur:
                    command.extend(["-t", opts.dur])
                command.extend(["-c", "copy", "-shortest", f"{c['name']}.mkv"])

                subprocess.run(command)

                if not opts.keep:
                    os.remove(f"{c['v_name']}")
                    os.remove(f"{c['a_name']}")
            finally:
                if os.path.exists(f"{c['name']}.txt"):
                    os.remove(f"{c['name']}.txt")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def archive(self):
        """Write all downloaded coubs in a batch to archive"""
        for c in self.coubs:
            write_archive(c['id'])

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def preview_all(self):
        """Preview all downloaded coubs in a batch"""
        for c in self.coubs:
            try:
                show_preview(c['a_name'].split(".")[-1], c['name'])
            except subprocess.CalledProcessError:
                pass

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def log_progress(self):
        global done

        for c in self.coubs:
            done += 1

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def preprocess(self):
        self.print_progress()
        self.def_existence()
        self.parse_json()
        if opts.out_format:
            self.custom_existence()

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def postprocess(self):
        self.check_streams()
        if not opts.v_only and not opts.a_only:
            self.merge()
        if opts.archive_file:
            self.archive()
        if opts.preview:
            self.preview_all()
        self.log_progress()

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def download(self):
        """Encompasses the whole download process with sequential downloads"""
        for c in self.coubs:
            if c['v_link']:
                download_stream(c['v_link'], c['v_name'])
            if c['a_link']:
                download_stream(c['a_link'], c['a_name'])

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    async def download_aio(self):
        """Encompasses the whole download process with asynchronous I/O"""
        video = [(c['v_link'], c['v_name']) for c in self.coubs if c['v_link']]
        audio = [(c['a_link'], c['a_name']) for c in self.coubs if c['a_link']]
        streams = video + audio

        tout = aiohttp.ClientTimeout(total=None)
        conn = aiohttp.TCPConnector(limit=opts.connect)
        async with aiohttp.ClientSession(timeout=tout, connector=conn) as session:
            tasks = [(download_stream_aio(session, s[0], s[1])) for s in streams]
            await asyncio.gather(*tasks, return_exceptions=False)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Functions
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def err(*args, **kwargs):
    """Print to stderr"""
    print(*args, file=sys.stderr, **kwargs)

def msg(*args, **kwargs):
    """Print to stdout based on verbosity level"""
    if opts.verbosity >= 1:
        print(*args, **kwargs)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def usage():
    """Print help text"""

    print(f"""CoubDownloader is a simple download script for coub.com

Usage: {os.path.basename(sys.argv[0])} [OPTIONS] INPUT [INPUT]...

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
  -p, --path PATH        set output destination (def: '{opts.path}')
  -k, --keep             keep the individual video/audio parts
  -r, --repeat N         repeat video N times (def: until audio ends)
  -d, --duration TIME    specify max. coub duration (FFmpeg syntax)

Download options:
  --connections N        raise max. number of connections (def: '{opts.connect}')
  --batch N              how many coubs to process per batch (def: '{opts.batch}')
  --sleep TIME           pause the script for TIME seconds after each batch
  --limit-num LIMIT      limit max. number of downloaded coubs
  --sort ORDER           specify download order for channels, tags, etc.
                         '--sort help' for all supported values

Format selection:
  --bestvideo            download best available video quality (def)
  --worstvideo           download worst available video quality
  --max-video FORMAT     set limit for the best video format (def: '{opts.v_max}')
                         Supported values: med, high, higher
  --min-video FORMAT     set limit for the worst video format (def: '{opts.v_min}')
                         Supported values: see '--max-video'
  --bestaudio            download best available audio quality (def)
  --worstaudio           download worst available audio quality
  --aac                  prefer AAC over higher quality MP3 audio
  --aac-strict           only download AAC audio (never MP3)
  --share                download 'share' video (shorter and includes audio)

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
      %tags%      - all tags (separated by '{opts.tag_sep}')

    Other strings will be interpreted literally.
    This option has no influence on the file extension.""")

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def usage_sort():
    """Print supported values for --sort"""

    print("""Supported sort values:

Channels:
  likes_count, views_count, newest_popular
Tags:
  likes_count, views_count, newest_popular, oldest
Searches:
  likes_count, views_count, newest_popular, oldest, newest
Hot section:
  likes_count, views_count, newest_popular, oldest
Categories:
  likes_count, views_count, newest_popular""")

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def usage_category():
    """Print supported values for --category"""

    print("""Supported categories:

Communities:
  animals-pets
  anime
  art
  cars
  cartoons
  celebrity
  dance
  fashion
  gaming
  mashup
  movies
  music
  nature-travel
  news
  nsfw
  science-technology
  sports

Special categories:
  newest
  random
  coub_of_the_day""")

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def check_prereq():
    """check existence of required software"""

    try:
        subprocess.run(["ffmpeg"], stdout=subprocess.DEVNULL, \
                                   stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        err("Error: FFmpeg not found!")
        sys.exit(err_stat['dep'])

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def parse_cli():
    """Parse command line"""
    global opts, coubs

    if not sys.argv[1:]:
        usage()
        sys.exit(0)

    with_arg = [
        "-l", "--list",
        "-c", "--channel",
        "-t", "--tag",
        "-e", "--search",
        "--category",
        "-p", "--path",
        "-r", "--repeat",
        "-d", "--duration",
        "--connections",
        "--batch",
        "--sleep",
        "--limit-num",
        "--sort",
        "--max-video",
        "--min-video",
        "--preview",
        "--write-list",
        "--use-archive",
        "-o", "--output"
    ]

    pos = 1
    while pos < len(sys.argv):
        opt = sys.argv[pos]
        if opt in with_arg:
            try:
                arg = sys.argv[pos+1]
            except IndexError:
                err(f"Missing value for '{opt}'!")
                sys.exit(err_stat['opt'])

            pos += 2
        else:
            pos += 1

        try:
            # Input
            if fnmatch(opt, "*coub.com/view/*"):
                coubs.links.append(opt.strip("/"))
            elif opt in ("-l", "--list"):
                if os.path.exists(arg):
                    coubs.lists.append(os.path.abspath(arg))
                else:
                    err(f"'{arg}' is not a valid list!")
            elif opt in ("-c", "--channel"):
                coubs.channels.append(arg.strip("/"))
            elif opt in ("-t", "--tag"):
                coubs.tags.append(arg.strip("/"))
            elif opt in ("-e", "--search"):
                coubs.searches.append(arg.strip("/"))
            elif opt in ("--hot",):
                coubs.hot = True
            elif opt in ("--category",):
                if arg == "help":
                    usage_category()
                    sys.exit(0)
                elif coubs.check_category(arg.strip("/")):
                    coubs.categories.append(arg.strip("/"))
                else:
                    err(f"'{arg}' is not a valid category!")
            # Common options
            elif opt in ("-h", "--help"):
                usage()
                sys.exit(0)
            elif opt in ("-q", "--quiet"):
                opts.verbosity = 0
            elif opt in ("-y", "--yes"):
                opts.prompt_answer = "yes"
            elif opt in ("-n", "--no"):
                opts.prompt_answer = "no"
            elif opt in ("-s", "--short"):
                opts.repeat = 1
            elif opt in ("-p", "--path"):
                opts.path = arg
            elif opt in ("-k", "--keep"):
                opts.keep = True
            elif opt in ("-r", "--repeat"):
                opts.repeat = int(arg)
            elif opt in ("-d", "--duration"):
                opts.dur = arg
            # Download options
            elif opt in ("--connections",):
                opts.connect = int(arg)
            elif opt in ("--batch",):
                opts.batch = int(arg)
            elif opt in ("--sleep",):
                opts.sleep_dur = float(arg)
            elif opt in ("--limit-num",):
                opts.max_coubs = int(arg)
            elif opt in ("--sort",):
                if arg == "help":
                    usage_sort()
                    sys.exit(0)
                else:
                    opts.sort = arg
            # Format selection
            elif opt in ("--bestvideo",):
                opts.v_quality = -1
            elif opt in ("--worstvideo",):
                opts.v_quality = 0
            elif opt in ("--max-video",):
                opts.v_max = arg
            elif opt in ("--min-video",):
                opts.v_min = arg
            elif opt in ("--bestaudio",):
                opts.a_quality = -1
            elif opt in ("--worstaudio",):
                opts.a_quality = 0
            elif opt in ("--aac",):
                opts.aac = 2
            elif opt in ("--aac-strict",):
                opts.aac = 3
            elif opt in ("--share",):
                opts.share = True
            # Channel options
            elif opt in ("--recoubs",):
                opts.recoubs = True
            elif opt in ("--no-recoubs",):
                opts.recoubs = False
            elif opt in ("--only-recoubs",):
                opts.only_recoubs = True
            # Preview options
            elif opt in ("--preview",):
                opts.preview = True
                opts.preview_command = arg
            elif opt in ("--no-preview",):
                opts.preview = False
            # Misc options
            elif opt in ("--audio-only",):
                opts.a_only = True
            elif opt in ("--video-only",):
                opts.v_only = True
            elif opt in ("--write-list",):
                opts.out_file = os.path.abspath(arg)
            elif opt in ("--use-archive",):
                opts.archive_file = os.path.abspath(arg)
            # Output
            elif opt in ("-o", "--output"):
                opts.out_format = arg
            # Unknown options
            elif fnmatch(opt, "-*"):
                err(f"Unknown flag '{opt}'!")
                err(f"Try '{os.path.basename(sys.argv[0])} --help' for more information.")
                sys.exit(err_stat['opt'])
            else:
                err(f"'{opt}' is neither an option nor a coub link!")
                err(f"Try '{os.path.basename(sys.argv[0])} --help' for more information.")
                sys.exit(err_stat['opt'])
        except ValueError:
            err(f"Invalid {opt} ('{arg}')!")
            sys.exit(err_stat['opt'])

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def check_options():
    """Check validity of command line options"""

    if opts.repeat <= 0:
        err("-r/--repeat must be greater than 0!")
        sys.exit(err_stat['opt'])
    elif opts.max_coubs and opts.max_coubs <= 0:
        err("--limit-num must be greater than 0!")
        sys.exit(err_stat['opt'])
    elif opts.connect <= 0:
        err("--connections must be greater than 0!")
        sys.exit(err_stat['opt'])
    elif opts.batch < 0:
        err("--batch can't be negative!")
        sys.exit(err_stat['opt'])

    if opts.dur:
        command = ["ffmpeg", "-v", "quiet",
                   "-f", "lavfi", "-i", "anullsrc",
                   "-t", opts.dur, "-c", "copy",
                   "-f", "null", "-"]
        try:
            subprocess.check_call(command)
        except subprocess.CalledProcessError:
            err("Invalid duration! For the supported syntax see:")
            err("https://ffmpeg.org/ffmpeg-utils.html#time-duration-syntax")
            sys.exit(err_stat['opt'])

    if opts.a_only and opts.v_only:
        err("--audio-only and --video-only are mutually exclusive!")
        sys.exit(err_stat['opt'])
    elif not opts.recoubs and opts.only_recoubs:
        err("--no-recoubs and --only-recoubs are mutually exclusive!")
        sys.exit(err_stat['opt'])
    elif opts.share and (opts.v_only or opts.a_only):
        err("--share and --video-/audio-only are mutually exclusive!")
        sys.exit(err_stat['opt'])

    v_formats = {
        'med': 0,
        'high': 1,
        'higher': 2
    }
    if opts.v_max not in v_formats:
        err(f"Invalid value for --max-video ('{opts.v_max}')!")
        sys.exit(err_stat['opt'])
    elif opts.v_min not in v_formats:
        err(f"Invalid value for --min-video ('{opts.v_min}')!")
        sys.exit(err_stat['opt'])
    elif v_formats[opts.v_min] > v_formats[opts.v_max]:
        err("Quality of --min-quality greater than --max-quality!")
        sys.exit(err_stat['opt'])

    # Not really necessary to check as invalid values get ignored anyway
    # But it also catches typos, so keep it for now
    allowed_sort = [
        "likes_count",
        "views_count",
        "newest_popular",
        "oldest",
        "newest"
    ]
    if opts.sort and opts.sort not in allowed_sort:
        err(f"Invalid sort order ('{opts.sort}')!\n")
        usage_sort()
        sys.exit(err_stat['opt'])

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def resolve_paths():
    """Handle output path"""

    if not os.path.exists(opts.path):
        os.mkdir(opts.path)
    os.chdir(opts.path)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def get_name(req_json, c_id):
    """Decide filename for output file"""

    if not opts.out_format:
        return c_id

    name = opts.out_format

    name = name.replace("%id%", c_id)
    name = name.replace("%title%", req_json['title'])
    name = name.replace("%creation%", req_json['created_at'])
    name = name.replace("%channel%", req_json['channel']['title'])
    # Coubs don't necessarily have a category
    try:
        name = name.replace("%category%", req_json['categories'][0]['permalink'])
    except (KeyError, TypeError, IndexError):
        name = name.replace("%category%", "")

    tags = ""
    for t in req_json['tags']:
        tags += t['title'] + opts.tag_sep
    name = name.replace("%tags%", tags)

    # Strip/replace special characters that can lead to script failure (ffmpeg concat)
    # ' common among coub titles
    # Newlines can be occasionally found as well
    name = name.replace("'", "")
    name = name.replace("\n", " ")

    try:
        f = open(name, "w")
        f.close()
        os.remove(name)
    except OSError:
        err(f"Error: Filename invalid or too long! Falling back to '{c_id}'")
        name = c_id

    return name

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def exists(name):
    """Check if a coub with given name already exists"""

    if opts.v_only:
        full_name = [name + ".mp4"]
    elif opts.a_only:
        # exists() gets possibly called before the API request
        # to be safe check for both possible audio extensions
        full_name = [name + ".mp3", name + ".m4a"]
    else:
        full_name = [name + ".mkv"]

    for f in full_name:
        if os.path.exists(f):
            return True

    return False

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def overwrite():
    """Decide if existing coub should be overwritten"""

    if opts.prompt_answer == "yes":
        return True
    elif opts.prompt_answer == "no":
        return False
    elif opts.prompt_answer == "prompt":
        print("Overwrite file?")
        print("1) yes")
        print("2) no")
        while True:
            answer = input("#? ")
            if answer == "1":
                return True
            if answer == "2":
                return False
    else:
        err("Unknown prompt_answer in overwrite!")
        sys.exit(err_stat['run'])

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def read_archive(c_id):
    """Check archive file for coub ID"""

    if not os.path.exists(opts.archive_file):
        return False

    with open(opts.archive_file, "r") as f:
        content = f.readlines()
    for l in content:
        if l == c_id + "\n":
            return True

    return False

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def write_archive(c_id):
    """Output coub ID to archive file"""

    with open(opts.archive_file, "a") as f:
        print(c_id, file=f)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def stream_lists(data):
    """Collect available video/audio streams of a coub"""

    # A few words (or maybe more) regarding Coub's streams:
    #
    # 'html5' has 3 video and 2 audio qualities
    #     video: med    (~360p)
    #            high   (~720p)
    #            higher (~900p)
    #     audio: med    (MP3@128Kbps CBR)
    #            high   (MP3@160Kbps VBR)
    #
    # 'mobile' has 1 video and 2 audio qualities
    #     video: video  (~360p)
    #     audio: 0      (AAC@128Kbps CBR or MP3@128Kbps CBR)
    #            1      (MP3@128Kbps CBR)
    #
    # 'share' has 1 quality (audio+video)
    #     video+audio: default (~720p, sometimes ~360p + AAC@128Kbps CBR)
    #
    # -) all videos come with a watermark
    # -) html5 video/audio and mobile audio may come in less available qualities
    # -) html5 video med and mobile video are the same file
    # -) html5 audio med and the worst mobile audio are the same file
    # -) mobile audio 0 is always the best mobile audio
    # -) often only mobile audio 0 is available as MP3 (no mobile audio 1)
    # -) share video has the same quality as mobile video
    # -) share audio is always AAC, even if mobile audio is only available as MP3
    # -) share audio is often shorter than other audio versions
    # -) videos come as MP4, MP3 audio as MP3 and AAC audio as M4A.
    #
    # All the aforementioned information regards the new Coub storage system (after the watermark introduction).
    # Also Coub is still catching up with encoding, so not every stream existence is yet guaranteed.
    #
    # Streams that may still be unavailable:
    #   -) share
    #   -) mobile video with direct URL (not the old base64 format)
    #   -) mobile audio in AAC
    #   -) html5 video higher
    #   -) html5 video med/high in a non-broken state (don't require \x00\x00 fix)
    #
    # There are no universal rules in which order new streams get added.
    # Sometimes you find videos with non-broken html5 streams, but the old base64 mobile URL.
    # Sometimes you find videos without html5 higher, but with the new mobile video.
    # Sometimes only html5 video med is still broken.
    #
    # It's a mess. Also release an up-to-date API documentations, you dolts!

    video = []
    audio = []

    # Special treatment for shared video
    if opts.share:
        try:
            version = data['file_versions']['share']['default']
            # Non-existence should result in None
            # Unfortunately there are exceptions to this rule (e.g. '{}')
            if not version or version in ("{}",):
                raise KeyError
        except KeyError:
            return ([], [])
        return ([version], [])

    # Video stream parsing
    v_formats = {
        'med': 0,
        'high': 1,
        'higher': 2
    }

    v_max = v_formats[opts.v_max]
    v_min = v_formats[opts.v_min]

    for vq in v_formats:
        if v_min <= v_formats[vq] <= v_max:
            try:
                version = data['file_versions']['html5']['video'][vq]
            except KeyError:
                continue

            # v_size/a_size can be 0 OR None in case of a missing stream
            # None is the exception and an irregularity in the Coub API
            if version['size']:
                video.append(version['url'])

    # Audio streams parsing
    if opts.aac >= 2:
        a_combo = [("html5", "med"), ("html5", "high"), ("mobile", 0)]
    else:
        a_combo = [("html5", "med"), ("mobile", 0), ("html5", "high")]

    for form, aq in a_combo:
        try:
            version = data['file_versions'][form]['audio'][aq]
        except KeyError:
            continue

        if form == "mobile":
            # Mobile audio doesn't list size
            # So just pray that the file behind the link exists
            if opts.aac:
                audio.append(version)
        else:
            if version['size'] and opts.aac < 3:
                audio.append(version['url'])

    return (video, audio)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def download_stream(link, path):
    """Download individual coub streams with urllib"""
    try:
        with urlopen(link) as stream, open(path, "wb") as f:
            f.write(stream.read())
    except urllib.error.HTTPError:
        return

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

async def download_stream_aio(session, link, path):
    """Download individual coub streams with aiohttp"""
    async with session.get(link) as response:
        with open(path, "wb") as f:
            while True:
                chunk = await response.content.read(1024)
                if not chunk:
                    break
                f.write(chunk)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def show_preview(a_ext, name):
    """Play finished coub with the given command"""

    # For normal downloads .mkv, unless error downloading audio
    if os.path.exists(name + ".mkv"):
        ext = ".mkv"
    else:
        ext = ".mp4"
    if opts.a_only:
        ext = "." + a_ext
    if opts.v_only:
        ext = ".mp4"

    try:
        # Need to split command string into list for check_call
        command = opts.preview_command.split(" ")
        command.append(name + ext)
        subprocess.check_call(command, stdout=subprocess.DEVNULL, \
                                       stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        err("Error: Missing file, invalid command or user interrupt in show_preview!")
        raise

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Main Function
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def main():
    """Main function body"""
    global count

    check_prereq()
    parse_cli()
    check_options()
    resolve_paths()

    msg("\n### Parse Input ###\n")
    coubs.parse_input()
    coubs.update_count()

    msg("\n### Download Coubs ###\n")

    if not opts.batch:
        batch_size = coubs.count
    else:
        batch_size = opts.batch

    while coubs.parsed:
        batch = CoubBuffer()
        while len(batch.coubs) < batch_size:
            try:
                batch.coubs.append({
                    'id': coubs.parsed[0].split("/")[-1],
                    'v_link': None,
                    'a_link': None,
                    'v_name': None,
                    'a_name': None,
                    'name': None
                })
                count += 1
                del coubs.parsed[0]
            except IndexError:
                break

        batch.preprocess()
        if not aio:
            batch.download()
        else:
            asyncio.run(batch.download_aio())
        batch.postprocess()

        if opts.sleep_dur and coubs.parsed:
            time.sleep(opts.sleep_dur)

    msg("\n### Finished ###\n")

# Execute main function
if __name__ == '__main__':
    opts = Options()
    coubs = CoubInputData()
    count = 0
    done = 0

    try:
        main()
    except KeyboardInterrupt:
        err("User Interrupt!")
        sys.exit(err_stat['int'])

    # Indicate failure if not all input coubs exist after execution
    if done < count:
        sys.exit(err_stat['down'])
    sys.exit(0)
