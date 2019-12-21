#!/usr/bin/env python3

import asyncio
import json
import os
import subprocess
import sys

from fnmatch import fnmatch
from math import ceil

import urllib.error
from urllib.request import urlopen
from urllib.parse import quote as urlquote

try:
    import aiohttp
    aio = True
except ModuleNotFoundError:
    aio = False

# ANSI escape codes don't work on Windows, unless the user jumps through
# additional hoops (either by using 3rd-party software or enabling VT100
# emulation with Windows 10)
# colorama solves this issue by converting ANSI escape codes into the
# appropriate win32 calls (only on Windows)
# If colorama isn't available, disable colorized output on Windows
colors = True
try:
    import colorama
    colorama.init()
except ModuleNotFoundError:
    if os.name == "nt":
        colors = False

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Global constants
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

class ExitCodes:
    """Store exit codes for non-successful execution."""

    DEP = 1         # missing required software
    OPT = 2         # invalid user-specified option
    RUN = 3         # misc. runtime error
    DOWN = 4        # failed to download all input links (existence == success)
    INT = 5         # early termination was requested by the user (i.e. Ctrl+C)
    CONN = 6        # connection either couldn't be established or was lost


class Colors:
    """Store ANSI escape codes for colorized output."""

    # https://en.wikipedia.org/wiki/ANSI_escape_code#Colors
    ERROR = '\033[31m'      # red
    WARNING = '\033[33m'    # yellow
    SUCCESS = '\033[32m'    # green
    RESET = '\033[0m'

    def disable(self):
        """Disable colorized output by removing escape codes."""
        # I'm not going to stop addressing these attributes as constants, just
        # because Windows thinks it needs to be special
        self.ERROR = ''
        self.SUCCESS = ''
        self.WARNING = ''
        self.RESET = ''


# Create objects to hold constants
status = ExitCodes()
fgcolors = Colors()

if not colors:
    fgcolors.disable()

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Classes
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

class Options:
    """Define and store all import user settings."""

    # Change verbosity of the script
    # 0 for quiet, >= 1 for normal verbosity
    verbosity = 1

    # yes/no will answer prompts automatically
    # Everything else will lead to a prompt
    prompt_answer = None

    # Default download destination
    path = "."

    # Keep individual video/audio streams
    keep = False

    # How often to loop the video
    # Only has an effect, if the looped video is shorter than the audio
    # Otherwise the max. length is limited by the audio duration
    repeat = 1000

    # Max. coub duration (FFmpeg syntax)
    # Can be used in combination with repeat, in which case the shorter
    # duration will be used
    dur = None

    # Max no. of connections for aiohttp's ClientSession
    # Raising this value can lead to shorter download times, but also
    # increases the risk of Coub throttling or terminating your connections
    # There's also no benefit in higher values, if your connection is already
    # fully utilized
    connect = 25

    # How often to retry download when connection is lost
    # >0 -> retry the specified number of times
    #  0 -> don't retry
    # <0 -> retry indefinitely
    # Retries happen through recursion, so the max. number is theoretically
    # limited to 1000 retries (although Python's limit could be raised as well)
    retries = 5

    # Limit how many coubs can be downloaded during one script invocation
    max_coubs = None

    # What video/audio quality to download
    #   0 -> worst quality
    #  -1 -> best quality
    # Everything else can lead to undefined behavior
    v_quality = -1
    a_quality = -1

    # Limits for the list of video streams
    #   v_max: limits what counts as best stream
    #   v_min: limits what counts as worst stream
    # Supported values:
    #   med    ( ~640px width)
    #   high   (~1280px width)
    #   higher (~1600px width)
    v_max = 'higher'
    v_min = 'med'

    # How much to prefer AAC audio
    #   0 -> never download AAC audio
    #   1 -> rank it between low and high quality MP3
    #   2 -> prefer AAC, use MP3 fallback
    #   3 -> either AAC or no audio
    aac = 1

    # Use shared video+audio instead of merging separate streams
    # Leads to shorter videos, also no further quality selection
    share = False

    # Download reposts during channel downloads
    recoubs = True

    # ONLY download reposts during channel downloads
    only_recoubs = False

    # Preview a downloaded coub with the given command
    # Keyboard shortcuts may not work for CLI audio players
    preview = False
    preview_command = "mpv"

    # Only download video/audio stream
    # a_only and v_only are mutually exclusive
    a_only = False
    v_only = False

    # Output parsed coubs to file instead of downloading
    # Values other than None will terminate the script after the initial
    # parsing process (i.e. no coubs will be downloaded)
    out_file = None

    # Use an archive file to keep track of downloaded coubs
    archive_file = None

    # Output name formatting (default: %id%)
    # Supports the following special keywords:
    #   %id%        - coub ID (identifier in the URL)
    #   %title%     - coub title
    #   %creation%  - creation date/time
    #   %community% - coub community
    #   %channel%   - channel title
    #   %tags%      - all tags (separated by tag_sep, see below)
    # All other strings are interpreted literally.
    #
    # Setting a custom value increases skip duration for existing coubs
    # Usage of an archive file is recommended in such an instance
    out_format = None

    # Advanced settings
    coubs_per_page = 25       # allowed: 1-25
    tag_sep = "_"

    default_sort = {
        'channel': "newest",  # newest, likes_count, views_count, oldest, random
        'tag': None,
        'search': None,
        'community': None,
    }


class ParsableTimeline:
    """Store timeline-related data important for later parsing."""

    supported_types = [
        "channel",
        "tag",
        "search",
        "community",
    ]

    def __init__(self, url, url_type):
        """Initialize timeline object."""
        self.valid = True
        self.pages = 0
        self.template = ""

        if url_type in self.supported_types:
            self.type = url_type
        else:
            err("Error: Tried to initialize timeline with unsupported type!")
            sys.exit(status.RUN)

        try:
            self.url, self.sort = url.split("#")
        except ValueError:
            self.url = url
            self.sort = opts.default_sort[self.type]

    def get_request_template(self):
        """Assign template URL for API request based on input type."""
        if self.type == "channel":
            self.template = self.channel_template()
        else:
            template = "https://coub.com/api/v2"

            if self.type in ("tag", "community"):
                t_id = self.url.split("/")[-1]
            elif self.type in ("search",):
                t_id = self.url.split("=")[-1]

            if self.type in ("tag", "search"):
                t_id = urlquote(t_id)

            if self.type in ("tag",):
                template = f"{template}/timeline/{self.type}/{t_id}?"
            elif self.type in ("search",):
                template = f"{template}/search/coubs?q={t_id}&"
            elif self.type in ("community",):
                # Communities use most popular (on a monthly basis) as default sort
                # I rather use newest first for now
                template = f"{template}/timeline/community/{t_id}/fresh?"

            self.template = f"{template}per_page={opts.coubs_per_page}"

    def channel_template(self):
        """Return API request template for channel timelines."""
        methods = ["newest", "likes_count", "views_count", "oldest", "random"]

        t_id = self.url.split("/")[-1]
        template = f"https://coub.com/api/v2/timeline/channel/{t_id}"
        template = f"{template}?per_page={opts.coubs_per_page}"

        if not opts.recoubs:
            template = f"{template}&type=simples"
        elif opts.only_recoubs:
            template = f"{template}&type=recoubs"

        if self.sort in methods:
            template = f"{template}&order_by={self.sort}"
        else:
            err(f"\nInvalid channel sort order '{self.sort}' ({self.url})!",
                color=fgcolors.WARNING)
            self.valid = False

        return template

    def get_page_count(self):
        """Contact API once to get page count and check timeline validity."""
        try:
            with urlopen(self.template) as resp:
                resp_json = json.loads(resp.read())
        except urllib.error.HTTPError:
            err(f"\nInvalid {self.type} ('{self.url}')!",
                color=fgcolors.WARNING)
            self.valid = False
            return

        self.pages = resp_json['total_pages']
        # tag/community timeline redirects pages >99 to page 1
        # other timelines work like intended
        if self.type in ("tag", "community") and self.pages > 99:
            self.pages = 99


class CoubInputData:
    """Store and parse all user-defined input sources."""

    links = []
    lists = []
    timelines = []

    parsed = []
    # This keeps track of the initial size of parsed for progress messages
    count = 0

    def map_input(self, link):
        """Detect input link type."""
        if fnmatch(link, "*coub.com/view/*"):
            self.links.append(link)
        elif fnmatch(link, "*coub.com/tags/*"):
            self.timelines.append(ParsableTimeline(link, "tag"))
        elif fnmatch(link, "*coub.com/search*"):
            self.timelines.append(ParsableTimeline(link, "search"))
        elif fnmatch(link, "*coub.com/community/*"):
            self.timelines.append(ParsableTimeline(link, "community"))
        # Unfortunately channel URLs don't have any special characteristics
        # Many yet unsupported URLs (communities, etc.) will be matched as
        # a channel for now
        elif fnmatch(link, "*coub.com*"):
            self.timelines.append(ParsableTimeline(link, "channel"))
        elif os.path.exists(link):
            self.lists.append(os.path.abspath(link))
        else:
            err(f"'{link}' is not a valid input!", color=fgcolors.WARNING)

    def parse_links(self):
        """Parse the coub links given directly via the command line."""
        for link in self.links:
            if opts.max_coubs and len(self.parsed) >= opts.max_coubs:
                break
            self.parsed.append(link)

        if self.links:
            msg("\nReading command line:")
            msg(f"  {len(self.links)} link(s) found")

    def parse_lists(self):
        """Parse the coub links provided in list form (i.e. external file)."""
        for l in self.lists:
            msg(f"\nReading input list ({l}):")

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

    async def parse_page(self, req, session=None):
        """Request a single timeline page and parse its content."""
        if aio:
            async with session.get(req) as resp:
                resp_json = await resp.read()
                resp_json = json.loads(resp_json)
        else:
            with urlopen(req) as resp:
                resp_json = resp.read()
                resp_json = json.loads(resp_json)

        for c in resp_json['coubs']:
            if opts.max_coubs and len(self.parsed) >= opts.max_coubs:
                return

            if c['recoub_to']:
                c_id = c['recoub_to']['permalink']
            else:
                c_id = c['permalink']

            self.parsed.append(f"https://coub.com/view/{c_id}")

    async def parse_timeline(self, timeline):
        """
        Parse the coub links from tags, channels, etc.

        The Coub API refers to the list of coubs from a tag, channel,
        community, etc. as a timeline.
        """
        if opts.max_coubs and len(self.parsed) >= opts.max_coubs:
            return

        pages = timeline.pages

        # Limit max. number of requested pages
        # Necessary as self.parse_page() returns when limit
        # is reached, but only AFTER the request was made
        if opts.max_coubs:
            to_limit = opts.max_coubs - len(self.parsed)
            max_pages = ceil(to_limit / opts.coubs_per_page)
            if pages > max_pages:
                pages = max_pages

        requests = [f"{timeline.template}&page={p}" for p in range(1, pages+1)]

        msg(f"\nDownloading {timeline.type} info ({timeline.url}):")

        if aio:
            msg(f"  {pages} out of {timeline.pages} pages")

            tout = aiohttp.ClientTimeout(total=None)
            conn = aiohttp.TCPConnector(limit=opts.connect)
            async with aiohttp.ClientSession(timeout=tout, connector=conn) as session:
                tasks = [self.parse_page(req, session) for req in requests]
                await asyncio.gather(*tasks)
        else:
            for i in range(pages):
                msg(f"  {i+1} out of {timeline.pages} pages")
                await self.parse_page(requests[i])

    def find_dupes(self):
        """Find and remove duplicates from the parsed coub link list."""
        dupes = 0

        self.parsed.sort()
        last = self.parsed[-1]

        # There are faster and more elegant ways to do this
        # but I also want to keep track of how many dupes were found
        for i in range(len(self.parsed)-2, -1, -1):
            if last == self.parsed[i]:
                dupes += 1
                del self.parsed[i]
            else:
                last = self.parsed[i]

        return dupes

    def parse_input(self):
        """Handle the parsing process of all provided input sources."""
        self.parse_links()
        self.parse_lists()
        for t in self.timelines:
            t.get_request_template()
            t.get_page_count()
            if t.valid:
                asyncio.run(self.parse_timeline(t))

        if not self.parsed:
            err("\nNo coub links specified!", color=fgcolors.WARNING)
            sys.exit(status.OPT)

        if opts.max_coubs and len(self.parsed) >= opts.max_coubs:
            msg(f"\nDownload limit ({opts.max_coubs}) reached!",
                color=fgcolors.WARNING)

        msg("\nResults:")
        msg(f"  {len(self.parsed)} input link(s)")
        msg(f"  {self.find_dupes()} duplicates")
        msg(f"  {len(self.parsed)} output link(s)")

        if opts.out_file:
            with open(opts.out_file, "a") as f:
                for link in self.parsed:
                    print(link, file=f)
            msg(f"\nParsed coubs written to '{opts.out_file}'!",
                color=fgcolors.SUCCESS)
            sys.exit(0)

    def update_count(self):
        """Keep track of the initial number of parsed links."""
        self.count = len(self.parsed)


class Coub():
    """Store all relevant infos and methods to process a single coub."""

    def __init__(self, link):
        """Initialize a Coub object."""
        self.link = link
        self.id = link.split("/")[-1]
        self.req = f"https://coub.com/api/v2/coubs/{self.id}"

        self.v_link = None
        self.a_link = None
        self.v_name = None
        self.a_name = None
        self.name = None

        self.unavailable = False
        self.exists = False
        self.corrupted = False

        self.done = False

    def erroneous(self):
        """Test if any errors occurred for the coub."""
        return bool(self.unavailable or self.exists or self.corrupted)

    def check_existence(self):
        """Test if the coub already exists or is present in the archive."""
        if self.erroneous():
            return

        if opts.archive_file and self.in_archive():
            self.exists = True
            return

        old_file = None
        # Existence of self.name indicates whether API request was already
        # made (i.e. if 1st or 2nd check)
        if not opts.out_format:
            if not self.name:
                old_file = exists(self.id)
        else:
            if self.name:
                old_file = exists(self.name)

        if old_file and not overwrite(old_file):
            self.exists = True

    async def parse(self, session=None):
        """Get all necessary coub infos from the Coub API."""
        if self.erroneous():
            return

        if aio:
            async with session.get(self.req) as resp:
                resp_json = await resp.read()
                resp_json = json.loads(resp_json)
        else:
            try:
                with urlopen(self.req) as resp:
                    resp_json = resp.read()
                    resp_json = json.loads(resp_json)
            except (urllib.error.HTTPError, urllib.error.URLError):
                self.unavailable = True
                return

        v_list, a_list = stream_lists(resp_json)
        if v_list:
            self.v_link = v_list[opts.v_quality]
        else:
            self.unavailable = True
            return

        if a_list:
            self.a_link = a_list[opts.a_quality]
        elif opts.a_only:
            self.unavailable = True
            return

        self.name = get_name(resp_json, self.id)

        if not opts.a_only:
            self.v_name = f"{self.name}.mp4"
        if not opts.v_only and self.a_link:
            a_ext = self.a_link.split(".")[-1]
            self.a_name = f"{self.name}.{a_ext}"

    async def download(self, session=None):
        """Download all requested streams."""
        if self.erroneous():
            return

        streams = []
        if self.v_name:
            streams.append((self.v_link, self.v_name))
        if self.a_name:
            streams.append((self.a_link, self.a_name))

        tasks = [save_stream(s[0], s[1], session) for s in streams]
        await asyncio.gather(*tasks)

    def check_integrity(self):
        """Test if a coub was downloaded successfully (e.g. no corruption)."""
        if self.erroneous():
            return

        # Whether a download was successful gets tested here
        # If wanted stream is present -> success
        # I'm not happy with this solution
        if self.v_name and not os.path.exists(self.v_name):
            self.corrupted = True
            return

        if self.a_name and not os.path.exists(self.a_name):
            self.a_name = None
            if opts.a_only:
                self.corrupted = True
            return

        if self.v_name and not valid_stream(self.v_name) or \
           self.a_name and not valid_stream(self.a_name):

            if self.v_name and os.path.exists(self.v_name):
                os.remove(self.v_name)
            if self.a_name and os.path.exists(self.a_name):
                os.remove(self.a_name)

            self.corrupted = True
            return

    def merge(self):
        """Mux the separate video/audio streams with FFmpeg."""
        if self.erroneous():
            return

        # Checking against v_name here is redundant (at least for now)
        if not (self.v_name and self.a_name):
            return

        m_name = f"{self.name}.mkv"     # merged name
        t_name = f"{self.name}.txt"     # txt name

        try:
            # Print .txt for FFmpeg's concat
            with open(t_name, "w") as f:
                for _ in range(opts.repeat):
                    print(f"file 'file:{self.v_name}'", file=f)

            # Loop footage until shortest stream ends
            # Concatenated video (via list) counts as one long stream
            command = [
                "ffmpeg", "-y", "-v", "error",
                "-f", "concat", "-safe", "0",
                "-i", f"file:{t_name}", "-i", f"file:{self.a_name}",
            ]
            if opts.dur:
                command.extend(["-t", opts.dur])
            command.extend(["-c", "copy", "-shortest", f"file:{m_name}"])

            subprocess.run(command)
        finally:
            if os.path.exists(t_name):
                os.remove(t_name)

        if not opts.keep:
            os.remove(self.v_name)
            os.remove(self.a_name)

    def in_archive(self):
        """Test if a coub's ID is present in the archive file."""
        if not os.path.exists(opts.archive_file):
            return False

        with open(opts.archive_file, "r") as f:
            content = f.readlines()
        for l in content:
            if l == self.id + "\n":
                return True

        return False

    def archive(self):
        """Log a coub's ID in the archive file."""
        # This return also prevents users from creating new archive files
        # from already existing coub collections
        if self.erroneous():
            return

        with open(opts.archive_file, "a") as f:
            print(self.id, file=f)

    def preview(self):
        """Play a coub with the user provided command."""
        if self.erroneous():
            return

        if self.v_name and self.a_name:
            play = f"{self.name}.mkv"
        elif self.v_name:
            play = self.v_name
        elif self.a_name:
            play = self.a_name

        try:
            # Need to split command string into list for check_call
            command = opts.preview_command.split(" ")
            command.append(play)
            subprocess.check_call(command, stdout=subprocess.DEVNULL, \
                                           stderr=subprocess.DEVNULL)
        except (subprocess.CalledProcessError, FileNotFoundError):
            err("Warning: Preview command failed!", color=fgcolors.WARNING)

    async def process(self, session=None):
        """Process a single coub."""
        global count, done

        # 1st existence check
        # Handles default naming scheme and archive usage
        self.check_existence()

        await self.parse(session)

        # 2nd existence check
        # Handles custom names exclusively (slower since API request necessary)
        if opts.out_format:
            self.check_existence()

        # Download
        await self.download(session)

        # Postprocessing stage
        self.check_integrity()
        if not (opts.v_only or opts.a_only):
            self.merge()

        # Success should be logged as soon as possible to avoid deletion
        # of valid streams with special format options (e.g. --video-only)
        self.done = True

        if opts.archive_file:
            self.archive()
        if opts.preview:
            self.preview()

        # Log status after processing
        count += 1
        progress = f"[{count: >{len(str(user_input.count))}}/{user_input.count}]"
        if self.unavailable:
            err(f"  {progress} {self.link: <30} ... ", color=fgcolors.RESET, end="")
            err("unavailable")
        elif self.corrupted:
            err(f"  {progress} {self.link: <30} ... ", color=fgcolors.RESET, end="")
            err("failed to download")
        elif self.exists:
            done += 1
            msg(f"  {progress} {self.link: <30} ... ", end="")
            msg("exists", color=fgcolors.WARNING)
        else:
            done += 1
            msg(f"  {progress} {self.link: <30} ... ", end="")
            msg("finished", color=fgcolors.SUCCESS)

    def delete(self):
        """Delete any leftover streams."""
        if self.v_name and os.path.exists(self.v_name):
            os.remove(self.v_name)
        if self.a_name and os.path.exists(self.a_name):
            os.remove(self.a_name)


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Functions
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def err(*args, color=fgcolors.ERROR, **kwargs):
    """Print to stderr."""
    sys.stderr.write(color)
    print(*args, file=sys.stderr, **kwargs)
    sys.stderr.write(fgcolors.RESET)
    sys.stdout.write(fgcolors.RESET)


def msg(*args, color=fgcolors.RESET, **kwargs):
    """Print to stdout based on verbosity level."""
    if opts.verbosity >= 1:
        sys.stdout.write(color)
        print(*args, **kwargs)
        sys.stderr.write(fgcolors.RESET)
        sys.stdout.write(fgcolors.RESET)


def usage():
    """Print the help text."""
    print(f"""CoubDownloader is a simple download script for coub.com

Usage: {os.path.basename(sys.argv[0])} [OPTIONS] INPUT [INPUT]...

Input:
  LINK                   download specified coubs
  -l, --list LIST        read coub links from a text file
  -c, --channel CHANNEL  download coubs from a channel
  -t, --tag TAG          download coubs with the specified tag
  -e, --search TERM      download search results for the given term
  --community COMMUNITY  download coubs from a certain community

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
  --connections N        max. number of connections (def: {opts.connect})
  --retries N            number of retries when connection is lost (def: {opts.retries})
                           0 to disable, <0 to retry indefinitely
  --limit-num LIMIT      limit max. number of downloaded coubs

Format selection:
  --bestvideo            download best available video quality (def)
  --worstvideo           download worst available video quality
  --max-video FORMAT     set limit for the best video format (def: {opts.v_max})
                           Supported values: med, high, higher
  --min-video FORMAT     set limit for the worst video format (def: {opts.v_min})
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
      %community% - coub community
      %channel%   - channel title
      %tags%      - all tags (separated by {opts.tag_sep})

    Other strings will be interpreted literally.
    This option has no influence on the file extension.""")


def check_prereq():
    """Test if all required 3rd-party tools are installed."""
    try:
        subprocess.run(["ffmpeg"], stdout=subprocess.DEVNULL, \
                                   stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        err("Error: FFmpeg not found!")
        sys.exit(status.DEP)


def check_connection():
    """Check if user can connect to coub.com."""
    try:
        urlopen("https://coub.com/")
    except urllib.error.URLError:
        err("Unable to connect to coub.com! Please check your connection.")
        sys.exit(status.CONN)


def parse_cli():
    """Parse the command line."""
    global opts, user_input

    if not sys.argv[1:]:
        usage()
        sys.exit(0)

    with_arg = [
        "-l", "--list",
        "-c", "--channel",
        "-t", "--tag",
        "-e", "--search",
        "--community",
        "-p", "--path",
        "-r", "--repeat",
        "-d", "--duration",
        "--connections",
        "--retries",
        "--limit-num",
        "--max-video",
        "--min-video",
        "--preview",
        "--write-list",
        "--use-archive",
        "-o", "--output",
    ]

    pos = 1
    while pos < len(sys.argv):
        opt = sys.argv[pos]
        if opt in with_arg:
            try:
                arg = sys.argv[pos+1]
            except IndexError:
                err(f"Missing value for '{opt}'!")
                sys.exit(status.OPT)

            pos += 2
        else:
            pos += 1

        try:
            # Input
            if not fnmatch(opt, "-*"):
                user_input.map_input(opt.strip("/"))
            elif opt in ("-l", "--list"):
                if os.path.exists(arg):
                    user_input.lists.append(os.path.abspath(arg))
                else:
                    err(f"'{arg}' is not a valid list!", color=fgcolors.WARNING)
            elif opt in ("-c", "--channel"):
                timeline = ParsableTimeline(arg.strip("/"), "channel")
                user_input.timelines.append(timeline)
            elif opt in ("-t", "--tag"):
                timeline = ParsableTimeline(arg.strip("/"), "tag")
                user_input.timelines.append(timeline)
            elif opt in ("-e", "--search"):
                timeline = ParsableTimeline(arg.strip("/"), "search")
                user_input.timelines.append(timeline)
            elif opt in ("--community",):
                timeline = ParsableTimeline(arg.strip("/"), "community")
                user_input.timelines.append(timeline)
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
            elif opt in ("--retries",):
                opts.retries = int(arg)
            elif opt in ("--limit-num",):
                opts.max_coubs = int(arg)
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
                # The default naming scheme is the same as using %id%
                # but internally the default value is None
                # So simply don't assign the argument if it's only %id%
                if arg != "%id%":
                    opts.out_format = arg
            # Unknown options
            else:
                err(f"Unknown flag '{opt}'!")
                err(f"Try '{os.path.basename(sys.argv[0])} "
                    "--help' for more information.", color=fgcolors.RESET)
                sys.exit(status.OPT)
        except ValueError:
            err(f"Invalid {opt} ('{arg}')!")
            sys.exit(status.OPT)


def check_options():
    """Test the user input (command line) for its validity."""
    if opts.repeat <= 0:
        err("-r/--repeat must be greater than 0!")
        sys.exit(status.OPT)
    elif opts.max_coubs is not None and opts.max_coubs <= 0:
        err("--limit-num must be greater than 0!")
        sys.exit(status.OPT)
    elif opts.connect <= 0:
        err("--connections must be greater than 0!")
        sys.exit(status.OPT)

    if opts.dur:
        command = [
            "ffmpeg", "-v", "quiet",
            "-f", "lavfi", "-i", "anullsrc",
            "-t", opts.dur, "-c", "copy",
            "-f", "null", "-",
        ]
        try:
            subprocess.check_call(command)
        except subprocess.CalledProcessError:
            err("Invalid duration!")
            err("For the supported syntax see:", color=fgcolors.RESET)
            err("https://ffmpeg.org/ffmpeg-utils.html#time-duration-syntax",
                color=fgcolors.RESET)
            sys.exit(status.OPT)

    if opts.a_only and opts.v_only:
        err("--audio-only and --video-only are mutually exclusive!")
        sys.exit(status.OPT)
    elif not opts.recoubs and opts.only_recoubs:
        err("--no-recoubs and --only-recoubs are mutually exclusive!")
        sys.exit(status.OPT)
    elif opts.share and (opts.v_only or opts.a_only):
        err("--share and --video-/audio-only are mutually exclusive!")
        sys.exit(status.OPT)

    v_formats = {
        'med': 0,
        'high': 1,
        'higher': 2,
    }
    if opts.v_max not in v_formats:
        err(f"Invalid value for --max-video ('{opts.v_max}')!")
        sys.exit(status.OPT)
    elif opts.v_min not in v_formats:
        err(f"Invalid value for --min-video ('{opts.v_min}')!")
        sys.exit(status.OPT)
    elif v_formats[opts.v_min] > v_formats[opts.v_max]:
        err("Quality of --min-quality greater than --max-quality!")
        sys.exit(status.OPT)


def resolve_paths():
    """Change into (and create) the destination directory."""
    if not os.path.exists(opts.path):
        os.mkdir(opts.path)
    os.chdir(opts.path)


def get_name(req_json, c_id):
    """Assemble final output name of a given coub."""
    if not opts.out_format:
        return c_id

    name = opts.out_format

    name = name.replace("%id%", c_id)
    name = name.replace("%title%", req_json['title'])
    name = name.replace("%creation%", req_json['created_at'])
    name = name.replace("%channel%", req_json['channel']['title'])
    # Coubs don't necessarily belong to a community (although it's rare)
    try:
        name = name.replace("%community%", req_json['communities'][0]['permalink'])
    except (KeyError, TypeError, IndexError):
        name = name.replace("%community%", "")

    tags = ""
    for t in req_json['tags']:
        # Don't add tag separator after the last tag
        tags += f"{t['title']}{opts.tag_sep if t != req_json['tags'][-1] else ''}"
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
        err(f"Error: Filename invalid or too long! Falling back to '{c_id}'",
            color=fgcolors.WARNING)
        name = c_id

    return name


def exists(name):
    """Test if a video with the given name and requested extension exists."""
    if opts.v_only or opts.share:
        full_name = [name + ".mp4"]
    elif opts.a_only:
        # exists() gets called before and after the API request was made
        # Unless MP3 or AAC audio are strictly prohibited, there's no way to
        # tell the final extension before the API request
        full_name = []
        if opts.aac > 0:
            full_name.append(name + ".m4a")
        if opts.aac < 3:
            full_name.append(name + ".mp3")
    else:
        full_name = [name + ".mkv"]

    for f in full_name:
        if os.path.exists(f):
            return f

    return None


def overwrite(name):
    """Prompt the user if they want to overwrite an existing coub."""
    if opts.prompt_answer == "yes":
        return True
    elif opts.prompt_answer == "no":
        return False
    else:
        # this should get printed even with --quiet
        # so print() instead of msg()
        if name:
            print(f"Overwrite file? ({name})")
        else:
            print("Overwrite file?")
        print("1) yes")
        print("2) no")
        while True:
            answer = input("#? ")
            if answer == "1":
                return True
            if answer == "2":
                return False


def stream_lists(resp_json):
    """Return all the available video/audio streams of the given coub."""
    # A few words (or maybe more) regarding Coub's streams:
    #
    # 'html5' has 3 video and 2 audio qualities
    #     video: med    ( ~640px width)
    #            high   (~1280px width)
    #            higher (~1600px width)
    #     audio: med    (MP3@128Kbps CBR)
    #            high   (MP3@160Kbps VBR)
    #
    # 'mobile' has 1 video and 2 audio qualities
    #     video: video  (~640px width)
    #     audio: 0      (AAC@128Kbps CBR or rarely MP3@128Kbps CBR)
    #            1      (MP3@128Kbps CBR)
    #
    # 'share' has 1 quality (audio+video)
    #     video+audio: default (video: ~1280px width, sometimes ~640px width
    #                           audio: AAC@128Kbps CBR)
    #
    # -) all videos come with a watermark
    # -) html5 video/audio and mobile audio may come in less available
    #    qualities (although it's quite rare)
    # -) html5 video med and mobile video are the same file
    # -) html5 audio med and the worst mobile audio are the same file
    # -) mobile audio 0 is always the best mobile audio
    # -) often mobile audio 0 is AAC, but occasionally it's MP3, in which case
    #    there's no mobile audio 1
    # -) share audio is always AAC, even if mobile audio is only available as
    #    MP3
    # -) share audio is pretty much always shorter than other audio versions
    # -) videos come as MP4, MP3 audio as MP3 and AAC audio as M4A
    #
    # I'd also like to stress that Coub may down- but also upscale (!) the
    # original footage to provide their standard resolutions. Therefore there's
    # no such thing as a "best" video stream. Ideally the resolution closest to
    # the original one should be downloaded.
    #
    # All the aforementioned information regards the new Coub storage system
    # (after the watermark introduction).
    # Coub is almost done with encoding, but not every stream existence is yet
    # guaranteed.
    #
    # Streams that may still be unavailable:
    #   -) share
    #   -) mobile audio in AAC (very very rare)
    #   -) html5 video higher
    #   -) html5 video med in a non-broken state (don't require \x00\x00 fix)
    #
    # There are no universal rules in which order new streams get added.
    #
    # It's a mess. Also release an up-to-date API documentations, you dolts!

    video = []
    audio = []

    # In case Coub returns "error: Coub not found"
    if 'error' in resp_json:
        return ([], [])

    # Special treatment for shared video
    if opts.share:
        version = resp_json['file_versions']['share']['default']
        # Non-existence results in None or '{}' (the latter is rare)
        if version and version not in ("{}",):
            return ([version], [])

        return ([], [])

    # Video stream parsing
    v_formats = {
        'med': 0,
        'high': 1,
        'higher': 2,
    }

    v_max = v_formats[opts.v_max]
    v_min = v_formats[opts.v_min]

    version = resp_json['file_versions']['html5']['video']
    for vq in v_formats:
        if v_min <= v_formats[vq] <= v_max:
            # html5 stream sizes can be 0 OR None in case of a missing stream
            # None is the exception and an irregularity in the Coub API
            if vq in version and version[vq]['size']:
                video.append(version[vq]['url'])

    # Audio stream parsing
    if opts.aac >= 2:
        a_combo = [
            ("html5", "med"),
            ("html5", "high"),
            ("mobile", 0),
        ]
    else:
        a_combo = [
            ("html5", "med"),
            ("mobile", 0),
            ("html5", "high"),
        ]

    for form, aq in a_combo:
        if 'audio' in resp_json['file_versions'][form]:
            version = resp_json['file_versions'][form]['audio']
        else:
            continue

        if form == "mobile":
            if opts.aac:
                # Mobile audio doesn't list its size
                # So just pray that the file behind the link exists
                audio.append(version[aq])
        elif aq in version and version[aq]['size'] and opts.aac < 3:
            audio.append(version[aq]['url'])

    return (video, audio)


async def save_stream(link, path, session=None):
    """Download a single media stream."""
    if aio:
        async with session.get(link) as stream:
            with open(path, "wb") as f:
                while True:
                    chunk = await stream.content.read(1024)
                    if not chunk:
                        break
                    f.write(chunk)
    else:
        try:
            with urlopen(link) as stream, open(path, "wb") as f:
                while True:
                    chunk = stream.read(1024)
                    if not chunk:
                        break
                    f.write(chunk)
        except (urllib.error.HTTPError, urllib.error.URLError):
            return


def valid_stream(path):
    """Test a given stream for eventual corruption with a test remux (FFmpeg)."""
    command = [
        "ffmpeg", "-v", "error",
        "-i", f"file:{path}",
        "-t", "1",
        "-f", "null", "-",
    ]
    out = subprocess.run(command, capture_output=True, text=True)

    # Checks against typical error messages in case of missing chunks
    # "Header missing"/"Failed to read frame size" -> audio corruption
    # "Invalid NAL" -> video corruption
    # "moov atom not found" -> old Coub storage method
    typical = [
        "Header missing",
        "Failed to read frame size",
        "Invalid NAL",
        "moov atom not found",
    ]
    for error in typical:
        if error in out.stderr:
            return False

    return True


async def process(coubs):
    """Call the process function of all parsed coubs."""
    if aio:
        tout = aiohttp.ClientTimeout(total=None)
        conn = aiohttp.TCPConnector(limit=opts.connect)
        try:
            async with aiohttp.ClientSession(timeout=tout, connector=conn) as session:
                tasks = [c.process(session) for c in coubs]
                await asyncio.gather(*tasks)
        except aiohttp.ClientConnectionError:
            err("\nLost connection to coub.com!")
            raise
    else:
        for c in coubs:
            await c.process()


def clean(coubs):
    """Clean workspace by deleteing unfinished coubs."""
    for c in [c for c in coubs if not c.done]:
        c.delete()


def attempt_process(coubs, level=0):
    """Attempt to run the process function."""
    if -1 < opts.retries < level:
        err("Ran out of connection retries! Please check your connection.")
        clean(coubs)
        sys.exit(status.CONN)

    if level > 0:
        err(f"Retrying... ({level} of "
            f"{opts.retries if opts.retries > 0 else 'Inf'} attempts)",
            color=fgcolors.WARNING)

    try:
        asyncio.run(process(coubs), debug=False)
    except aiohttp.ClientConnectionError:
        check_connection()
        # Reduce the list of coubs to only those yet to finish
        coubs = [c for c in coubs if not c.done]
        level += 1
        attempt_process(coubs, level)


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Main Function
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def main():
    """Download all requested coubs."""
    check_prereq()
    parse_cli()
    check_options()
    resolve_paths()
    check_connection()

    msg("\n### Parse Input ###")
    user_input.parse_input()
    user_input.update_count()

    msg("\n### Download Coubs ###\n")

    coubs = [Coub(l) for l in user_input.parsed]

    try:
        attempt_process(coubs)
    finally:
        clean(coubs)

    msg("\n### Finished ###\n")


# Execute main function
if __name__ == '__main__':
    opts = Options()
    user_input = CoubInputData()
    count = 0
    done = 0

    try:
        main()
    except KeyboardInterrupt:
        err("\nUser Interrupt!", color=fgcolors.WARNING)
        sys.exit(status.INT)

    # Indicate failure if not all input coubs exist after execution
    if done < count:
        sys.exit(status.DOWN)
    sys.exit(0)
