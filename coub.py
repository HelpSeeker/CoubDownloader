#!/usr/bin/env python3

"""
Copyright (C) 2018-2020 HelpSeeker <AlmostSerious@protonmail.ch>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import argparse
import asyncio
import json
import os
import subprocess
import sys
import certifi

from math import ceil
from ssl import SSLCertVerificationError, create_default_context
from textwrap import dedent

import urllib.error
from urllib.request import urlopen
from urllib.parse import quote as urlquote
from urllib.parse import unquote as urlunquote

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
# Classes For Global Variables
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

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Global Variables
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

status = ExitCodes()
fgcolors = Colors()
if not colors:
    fgcolors.disable()

total = 0
count = 0
done = 0

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Classes
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

class DefaultOptions:
    """Define and store all import user settings."""

    # Common defaults
    VERBOSITY = 1
    PROMPT = None
    PATH = "."
    KEEP = False
    REPEAT = 1000
    DURATION = None
    # Download defaults
    CONNECTIONS = 25
    RETRIES = 5
    MAX_COUBS = None
    # Format defaults
    V_QUALITY = -1
    A_QUALITY = -1
    V_MAX = "higher"
    V_MIN = "med"
    AAC = 1
    SHARE = False
    # Channel defaults
    RECOUBS = 1
    # Preview defaults
    PREVIEW = None
    # Misc. defaults
    A_ONLY = False
    V_ONLY = False
    OUTPUT_LIST = None
    ARCHIVE = None
    # Output defaults
    MERGE_EXT = "mkv"
    NAME_TEMPLATE = "%id%"
    # Advanced defaults
    FFMPEG_PATH = "ffmpeg"
    COUBS_PER_PAGE = 25
    TAG_SEP = "_"
    FALLBACK_CHAR = "-"
    WRITE_METHOD = "w"
    CHUNK_SIZE = 1024

    def __init__(self, config_dirs=None):
        if not config_dirs:
            # Only supports script's location as default for now
            config_dirs = [os.path.dirname(os.path.realpath(__file__))]
        for d in config_dirs:
            config_path = os.path.join(d, "coub.conf")
            if os.path.exists(config_path):
                self.read_from_config(config_path)
        self.check_values()

    def read_from_config(self, path):
        """Change default options based on user config file."""
        try:
            with open(path, "r") as f:
                user_settings = [l for l in f
                                 if "=" in l and not l.startswith("#")]
        except (OSError, UnicodeError):
            err(f"Error reading config file '{path}'!", color=fgcolors.WARNING)
            user_settings = []

        for setting in user_settings:
            name = setting.split("=")[0].strip()
            value = setting.split("=")[1].strip()
            if hasattr(self, name):
                value = self.guess_string_type(name, value)
                setattr(self, name, value)
            else:
                err(f"Unknown option in config file: {name}",
                    color=fgcolors.WARNING)

    def check_values(self):
        """Test defaults for valid ranges and types."""
        checks = {
            "VERBOSITY": (lambda x: x in [0, 1]),
            "PROMPT": (lambda x: True),     # Anything but yes/no will lead to prompt
            "PATH": (lambda x: isinstance(x, str)),
            "KEEP": (lambda x: isinstance(x, bool)),
            "REPEAT": (lambda x: isinstance(x, int) and x > 0),
            "DURATION": (lambda x: isinstance(x, str) or x is None),
            "CONNECTIONS": (lambda x: isinstance(x, int) and x > 0),
            "RETRIES": (lambda x: isinstance(x, int)),
            "MAX_COUBS": (lambda x: isinstance(x, int) and x > 0 or x is None),
            "V_QUALITY": (lambda x: x in [0, -1]),
            "A_QUALITY": (lambda x: x in [0, -1]),
            "V_MAX": (lambda x: x in ["higher", "high", "med"]),
            "V_MIN": (lambda x: x in ["higher", "high", "med"]),
            "AAC": (lambda x: x in [0, 1, 2, 3]),
            "SHARE": (lambda x: isinstance(x, bool)),
            "RECOUBS": (lambda x: x in [0, 1, 2]),
            "PREVIEW": (lambda x: isinstance(x, str) or x is None),
            "A_ONLY": (lambda x: isinstance(x, bool)),
            "V_ONLY": (lambda x: isinstance(x, bool)),
            "OUTPUT_LIST": (lambda x: isinstance(x, str) or x is None),
            "ARCHIVE": (lambda x: isinstance(x, str) or x is None),
            "MERGE_EXT": (lambda x: x in ["mkv", "mp4", "asf", "avi", "flv", "f4v", "mov"]),
            "NAME_TEMPLATE": (lambda x: isinstance(x, str) or x is None),
            "FFMPEG_PATH": (lambda x: isinstance(x, str)),
            "COUBS_PER_PAGE": (lambda x: x in range(1, 26)),
            "TAG_SEP": (lambda x: isinstance(x, str)),
            "FALLBACK_CHAR": (lambda x: isinstance(x, str) or x is None),
            "WRITE_METHOD": (lambda x: x in ["w", "a"]),
            "CHUNK_SIZE": (lambda x: isinstance(x, int) and x > 0),
        }

        errors = []
        for option in checks:
            value = getattr(self, option)
            if not checks[option](value):
                errors.append((option, value))
        if errors:
            for e in errors:
                err(f"{e[0]}: invalid default value '{e[1]}'")
            sys.exit(status.OPT)

    @staticmethod
    def guess_string_type(option, string):
        """Convert values from config file (all strings) to the right type."""
        specials = {
            "None": None,
            "True": True,
            "False": False,
        }
        # Some options should not undergo integer conversion
        # Usually options which are supposed to ONLY take strings
        exceptions = [
            "PATH",
            "DURATION",
            "PREVIEW",
            "OUTPUT_LIST",
            "ARCHIVE",
            "NAME_TEMPLATE",
            "FFMPEG_PATH",
            "TAG_SEP",
            "FALLBACK_CHAR",
        ]

        if string in specials:
            return specials[string]
        if option in exceptions:
            return string
        try:
            return int(string)
        except ValueError:
            return string


class InputHelp(argparse.Action):
    """Custom action to print input help."""

    def __init__(self, **kwargs):
        super(InputHelp, self).__init__(nargs=0, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        parser.print_input_help()
        parser.exit()


class CustomArgumentParser(argparse.ArgumentParser):
    """Override ArgumentParser's automatic help text formatting."""

    def print_input_help(self, file=None):
        """Slightly changed version of the internal print_help method."""
        if file is None:
            file = sys.stdout
        self._print_message(self.format_input_help(), file)

    def format_help(self):
        """Return custom help text."""
        help_text = dedent(f"""\
        CoubDownloader is a simple download script for coub.com

        Usage: {self.prog} [OPTIONS] INPUT [INPUT]...

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
          -p, --path PATH       set output destination (def: '{self.get_default("path")}')
          -k, --keep            keep the individual video/audio parts
          -r, --repeat N        repeat video N times (def: until audio ends)
          -d, --duration TIME   specify max. coub duration (FFmpeg syntax)

        Download options:
          --connections N       max. number of connections (def: {self.get_default("connections")})
          --retries N           number of retries when connection is lost (def: {self.get_default("retries")})
                                  0 to disable, <0 to retry indefinitely
          --limit-num LIMIT     limit max. number of downloaded coubs

        Format selection:
          --bestvideo           download best available video quality (def)
          --worstvideo          download worst available video quality
          --max-video FORMAT    set limit for the best video format (def: {self.get_default("v_max")})
                                  Supported values: med, high, higher
          --min-video FORMAT    set limit for the worst video format (def: {self.get_default("v_min")})
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
          --ext EXTENSION       merge output with the given extension (def: {self.get_default("merge_ext")})
                                  ignored if no merge is required
          -o, --output FORMAT   save output with the given template (def: {self.get_default("name_template")})

            Special strings:
              %id%        - coub ID (identifier in the URL)
              %title%     - coub title
              %creation%  - creation date/time
              %community% - coub community
              %channel%   - channel title
              %tags%      - all tags (separated by {self.get_default("tag_sep")})

            Other strings will be interpreted literally.
            This option has no influence on the file extension.
        """)

        return help_text

    @staticmethod
    def format_input_help():
        """Print help text regarding input and input options."""
        help_text = dedent(f"""\
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
        """)

        return help_text


class BaseContainer:
    """Base class for link containers (timelines)."""
    type = None

    def __init__(self, id_):
        self.valid = True
        self.pages = 0
        self.template = ""

        id_ = no_url(id_)
        try:
            self.id, self.sort = id_.split("#")
        except ValueError:
            self.id = id_
            self.sort = None

        # Links copied from the browser already have special characters escaped
        # Using urlquote on them again in the template functions would lead
        # to invalid templates
        # Also prettifies messages that show the ID as info
        self.id = urlunquote(self.id)

    def get_template(self):
        """Placeholder function, which must be overwritten by subclasses."""
        self.template = ""

    def get_page_count(self):
        """Contact API once to get page count and check validity."""
        if not self.valid:
            return

        try:
            with urlopen(self.template, context=context) as resp:
                resp_json = json.loads(resp.read())
        except urllib.error.HTTPError:
            err(f"\nInvalid {self.type} ('{self.id}')!",
                color=fgcolors.WARNING)
            self.valid = False
            return

        self.pages = resp_json['total_pages']

    async def process(self, quantity=None):
        """
        Parse the coub links from tags, channels, etc.

        The Coub API refers to the list of coubs from a tag, channel,
        community, etc. as a timeline.
        """
        self.get_template()
        self.get_page_count()
        if not self.valid:
            return []

        pages = self.pages

        # Limit max. number of requested pages
        # Necessary as self.parse_page() returns when limit
        # is reached, but only AFTER the request was made
        if quantity:
            max_pages = ceil(quantity / opts.coubs_per_page)
            if pages > max_pages:
                pages = max_pages

        requests = [f"{self.template}&page={p}" for p in range(1, pages+1)]

        msg(f"\nDownloading {self.type} info"
            f"{f': {self.id}' if self.id else ''}"
            f" (sorted by '{self.sort}')")

        if aio:
            msg(f"  {pages} out of {self.pages} pages")

            tout = aiohttp.ClientTimeout(total=None)
            conn = aiohttp.TCPConnector(limit=opts.connections)
            async with aiohttp.ClientSession(timeout=tout, connector=conn) as session:
                tasks = [parse_page(req, session) for req in requests]
                ids = await asyncio.gather(*tasks)
            ids = [i for page in ids for i in page]
        else:
            ids = []
            for i in range(pages):
                msg(f"  {i+1} out of {self.pages} pages")
                page = await parse_page(requests[i])
                ids.extend(page)

        if quantity:
            return ids[:quantity]
        return ids


class Channel(BaseContainer):
    """Store and parse channels."""
    type = "channel"

    def __init__(self, id_):
        super(Channel, self).__init__(id_)
        # Available:      most_recent, most_liked, most_viewed, oldest, random
        # Coub's default: most_recent
        if not self.sort:
            self.sort = "most_recent"

    def get_template(self):
        """Return API request template for channels."""
        methods = {
            'most_recent': "newest",
            'most_liked': "likes_count",
            'most_viewed': "views_count",
            'oldest': "oldest",
            'random': "random",
        }

        template = f"https://coub.com/api/v2/timeline/channel/{urlquote(self.id)}"
        template = f"{template}?per_page={opts.coubs_per_page}"

        if opts.recoubs == 0:
            template = f"{template}&type=simples"
        elif opts.recoubs == 2:
            template = f"{template}&type=recoubs"

        if self.sort in methods:
            template = f"{template}&order_by={methods[self.sort]}"
        else:
            err(f"\nInvalid channel sort order '{self.sort}' ({self.id})!",
                color=fgcolors.WARNING)
            self.valid = False

        self.template = template


class Tag(BaseContainer):
    """Store and parse tags."""
    type = "tag"

    def __init__(self, id_):
        super(Tag, self).__init__(id_)
        # Available:      popular, top, views_count, fresh
        # Coub's default: popular
        if not self.sort:
            self.sort = "popular"

    def get_template(self):
        """Return API request template for tags."""
        methods = {
            'popular': "newest_popular",
            'top': "likes_count",
            'views_count': "views_count",
            'fresh': "newest"
        }

        template = f"https://coub.com/api/v2/timeline/tag/{urlquote(self.id)}"
        template = f"{template}?per_page={opts.coubs_per_page}"

        if self.sort in methods:
            template = f"{template}&order_by={methods[self.sort]}"
        else:
            err(f"\nInvalid tag sort order '{self.sort}' ({self.id})!",
                color=fgcolors.WARNING)
            self.valid = False

        self.template = template

    def get_page_count(self):
        super(Tag, self).get_page_count()
        # API limits tags to 99 pages
        if self.pages > 99:
            self.pages = 99


class Search(BaseContainer):
    """Store and parse searches."""
    type = "search"

    def __init__(self, id_):
        super(Search, self).__init__(id_)
        # Available:      relevance, top, views_count, most_recent
        # Coub's default: relevance
        if not self.sort:
            self.sort = "relevance"

    def get_template(self):
        """Return API request template for coub searches."""
        methods = {
            'relevance': None,
            'top': "likes_count",
            'views_count': "views_count",
            'most_recent': "newest"
        }

        template = f"https://coub.com/api/v2/search/coubs?q={urlquote(self.id)}"
        template = f"{template}&per_page={opts.coubs_per_page}"

        if self.sort not in methods:
            err(f"\nInvalid search sort order '{self.sort}' ({self.id})!",
                color=fgcolors.WARNING)
            self.valid = False
        # The default tab on coub.com is labelled "Relevance", but the
        # default sort order is actually no sort order
        elif self.sort != "relevance":
            template = f"{template}&order_by={methods[self.sort]}"

        self.template = template


class Community(BaseContainer):
    """Store and parse communities."""
    type = "community"

    def __init__(self, id_):
        super(Community, self).__init__(id_)
        # Available:      hot_daily, hot_weekly, hot_monthly, hot_quarterly,
        #                 hot_six_months, rising, fresh, top, views_count, random
        # Coub's default: hot_monthly
        if not self.sort:
            if self.id in ("featured", "coub-of-the-day"):
                self.sort = "recent"
            else:
                self.sort = "hot_monthly"

    def get_template(self):
        """Return API request template for communities."""
        if self.id == "featured":
            methods = {
                'recent': None,
                'top_of_the_month': "top_of_the_month",
                'undervalued': "undervalued",
            }
            template = "https://coub.com/api/v2/timeline/explore?"
        elif self.id == "coub-of-the-day":
            methods = {
                'recent': None,
                'top': "top",
                'views_count': "views_count",
            }
            template = "https://coub.com/api/v2/timeline/explore/coub_of_the_day?"
        else:
            methods = {
                'hot_daily': "daily",
                'hot_weekly': "weekly",
                'hot_monthly': "monthly",
                'hot_quarterly': "quarter",
                'hot_six_months': "half",
                'rising': "rising",
                'fresh': "fresh",
                'top': "likes_count",
                'views_count': "views_count",
                'random': "random",
            }
            template = f"https://coub.com/api/v2/timeline/community/{urlquote(self.id)}"

        if self.sort not in methods:
            err(f"\nInvalid community sort order '{self.sort}' ({self.id})!",
                color=fgcolors.WARNING)
            self.valid = False
            return

        if self.id in ("featured", "coub-of-the-day"):
            if self.sort != "recent":
                template = f"{template}order_by={methods[self.sort]}&"
        else:
            if self.sort in ("top", "views_count"):
                template = f"{template}/fresh?order_by={methods[self.sort]}&"
            elif self.sort == "random":
                template = f"https://coub.com/api/v2/timeline/random/{self.id}?"
            else:
                template = f"{template}/{methods[self.sort]}?"

        self.template = f"{template}per_page={opts.coubs_per_page}"

    def get_page_count(self):
        super(Community, self).get_page_count()
        # API limits communities to 99 pages
        if self.pages > 99:
            self.pages = 99


class HotSection(BaseContainer):
    """Store and parse the hot section."""
    type = "hot section"

    def __init__(self, sort=None):
        super(HotSection, self).__init__("hot")
        self.id = None
        self.sort = sort
        # Available:      hot_daily, hot_weekly, hot_monthly, hot_quarterly,
        #                 hot_six_months, rising, fresh
        # Coub's default: hot_monthly
        if not self.sort:
            self.sort = "hot_monthly"

    def get_template(self):
        """Return API request template for Coub's hot section."""
        methods = {
            'hot_daily': "daily",
            'hot_weekly': "weekly",
            'hot_monthly': "monthly",
            'hot_quarterly': "quarter",
            'hot_six_months': "half",
            'rising': "rising",
            'fresh': "fresh",
        }

        template = "https://coub.com/api/v2/timeline/subscriptions"

        if self.sort in methods:
            template = f"{template}/{methods[self.sort]}"
        else:
            err(f"\nInvalid hot section sort order '{self.sort}'!",
                color=fgcolors.WARNING)
            self.valid = False

        template = f"{template}?per_page={opts.coubs_per_page}"

        self.template = template

    def get_page_count(self):
        super(HotSection, self).get_page_count()
        # API limits hot section to 99 pages
        if self.pages > 99:
            self.pages = 99


class RandomCategory(BaseContainer):
    """Store and parse the random category."""
    type = "random"

    def __init__(self, sort=None):
        super(RandomCategory, self).__init__("random")
        self.id = None
        self.sort = sort
        # Available:      popular, top
        # Coub's default: popular
        if not self.sort:
            self.sort = "popular"

    def get_template(self):
        """Return API request template for Coub's random category."""
        methods = {
            'popular': None,
            'top': "top",
        }
        template = "https://coub.com/api/v2/timeline/explore/random?"

        if self.sort not in methods:
            err(f"\nInvalid random sort order '{self.sort}'!",
                color=fgcolors.WARNING)
            self.valid = False
            return
        if self.sort == "top":
            template = f"{template}order_by={methods[self.sort]}&"

        self.template = f"{template}per_page={opts.coubs_per_page}"


class LinkList:
    """Store and parse link lists."""
    type = "list"

    def __init__(self, path):
        self.id = valid_list(path)
        self.sort = None

    async def process(self, quantity=None):
        """Parse coub links provided in via an external text file."""
        msg(f"\nReading input list ({self.id}):")

        with open(self.id, "r") as f:
            content = f.read()

        # Replace tabs and spaces with newlines
        # Emulates default wordsplitting in Bash
        content = content.replace("\t", "\n")
        content = content.replace(" ", "\n")
        content = content.splitlines()

        links = [
            l.partition("https://coub.com/view/")[2]
            for l in content if "https://coub.com/view/" in l
        ]
        msg(f"  {len(links)} link{'s' if len(links) != 1 else ''} found")

        if quantity:
            return links[:quantity]
        return links


class Coub:
    """Store all relevant infos and methods to process a single coub."""

    def __init__(self, c_id):
        self.id = c_id
        self.link = f"https://coub.com/view/{self.id}"
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

        old_file = None
        # Existence of self.name indicates whether API request was already
        # made (i.e. if 1st or 2nd check)
        if not opts.name_template:
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
                with urlopen(self.req, context=context) as resp:
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

        m_name = f"{self.name}.{opts.merge_ext}"     # merged name
        t_name = f"{self.name}.txt"                  # txt name

        try:
            # Print .txt for FFmpeg's concat
            with open(t_name, "w", encoding="utf-8") as f:
                for _ in range(opts.repeat):
                    print(f"file 'file:{self.v_name}'", file=f)

            # Loop footage until shortest stream ends
            # Concatenated video (via list) counts as one long stream
            command = [
                opts.ffmpeg_path, "-y", "-v", "error",
                "-f", "concat", "-safe", "0",
                "-i", f"file:{t_name}", "-i", f"file:{self.a_name}",
            ]
            if opts.duration:
                command.extend(["-t", opts.duration])
            command.extend(["-c", "copy", "-shortest", f"file:temp_{m_name}"])

            subprocess.run(command, check=False)
        finally:
            if os.path.exists(t_name):
                os.remove(t_name)

        # Merging would break when using <...>.mp4 both as input and output
        os.replace(f"temp_{m_name}", m_name)

        if not opts.keep:
            if self.v_name != m_name:
                os.remove(self.v_name)
            os.remove(self.a_name)

    def archive(self):
        """Log a coub's ID in the archive file."""
        # This return also prevents users from creating new archive files
        # from already existing coub collections
        if self.erroneous():
            return

        with open(opts.archive, "a") as f:
            print(self.id, file=f)

    def preview(self):
        """Play a coub with the user provided command."""
        if self.erroneous():
            return

        if self.v_name and self.a_name:
            play = f"{self.name}.{opts.merge_ext}"
        elif self.v_name:
            play = self.v_name
        elif self.a_name:
            play = self.a_name

        try:
            # Need to split command string into list for check_call
            command = opts.preview.split(" ")
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
        if opts.name_template:
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

        if opts.archive:
            self.archive()
        if opts.preview:
            self.preview()

        # Log status after processing
        count += 1
        progress = f"[{count: >{len(str(total))}}/{total}]"
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


def check_prereq():
    """Test if all required 3rd-party tools are installed."""
    try:
        subprocess.run([opts.ffmpeg_path],
                       stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL,
                       check=False)
    except FileNotFoundError:
        err("Error: FFmpeg not found!")
        sys.exit(status.DEP)


def check_connection():
    """Check if user can connect to coub.com."""
    try:
        urlopen('https://coub.com/', context=context)
    except urllib.error.URLError as e:
        if isinstance(e.reason, SSLCertVerificationError):
            err("Certificate verification failed! Please update your CA certificates.")
        else:
            err("Unable to connect to coub.com! Please check your connection.")
        sys.exit(status.CONN)


def no_url(string):
    """Test if direct input is an URL."""
    if "coub.com" in string:
        raise argparse.ArgumentTypeError("input options don't support URLs")
    return string


def positive_int(string):
    """Convert string provided by parse_cli() to a positive int."""
    try:
        value = int(string)
        if value <= 0:
            raise ValueError
    except ValueError:
        raise argparse.ArgumentTypeError("invalid positive int")
    return value


def valid_time(string):
    """Test valditiy of time syntax with FFmpeg."""
    # Gets called in parse_cli, so opts.ffmpeg_path isn't available yet
    # Exploits the fact that advanced defaults and options are always the same
    defaults = DefaultOptions()
    command = [
        defaults.FFMPEG_PATH, "-v", "quiet",
        "-f", "lavfi", "-i", "anullsrc",
        "-t", string, "-c", "copy",
        "-f", "null", "-",
    ]
    try:
        subprocess.check_call(command)
    except subprocess.CalledProcessError:
        raise argparse.ArgumentTypeError("invalid time syntax")

    return string


def valid_list(string):
    """Convert string provided by parse_cli() to an absolute path."""
    path = os.path.abspath(string)
    try:
        with open(path, "r") as f:
            _ = f.read(1)
    except FileNotFoundError:
        raise argparse.ArgumentTypeError("path doesn't exist")
    except (OSError, UnicodeError):
        raise argparse.ArgumentTypeError("invalid list")

    return path


def valid_archive(string):
    """Convert string provided by parse_cli() to an absolute path."""
    path = os.path.abspath(string)
    try:
        with open(path, "r") as f:
            _ = f.read(1)
    except FileNotFoundError:
        pass
    except (OSError, UnicodeError):
        raise argparse.ArgumentTypeError("invalid archive file")

    return path


def normalize_link(string):
    """Format link to guarantee strict adherence to https://coub.com/<info>#<sort>"""
    to_replace = {
        'channel': {
            '/coubs': None,
            '/reposts': None,
            '/stories': None,
        },
        'tag': {
            '/likes': "top",
            '/views': "views_count",
            '/fresh': "fresh"
        },
        'search': {
            '/likes': "top",
            '/views': "views_count",
            '/fresh': "most_recent",
            '/channels': None,
        },
        'community': {
            '/rising': "rising",
            '/fresh': "fresh",
            '/top': "top",
            '/views': "views_count",
            '/random': "random",
        },
        'featured': {
            'featured/coubs/top_of_the_month': "top_of_the_month",
            'featured/coubs/undervalued': "undervalued",
            'featured/stories': None,
            'featured/channels': None,
            'featured': "recent",
        },
        'random': {
            '/top': "top",
        },
    }

    try:
        link, sort = string.split("#")
    except ValueError:
        link = string
        sort = None

    info = link.rpartition("coub.com")[2]
    info = info.strip("/")

    if "tags/" in info:
        for r in to_replace['tag']:
            parts = info.partition(r)
            if parts[1]:
                if not sort:
                    sort = to_replace['tag'][r]
                info = parts[0]
    # If search is followed by ?q= then it shouldn't have any suffixes anyway
    elif "search/" in info:
        for r in to_replace['search']:
            parts = info.partition(r)
            if parts[1]:
                if not sort:
                    sort = to_replace['search'][r]
                info = f"{parts[0]}{parts[2]}"
    elif "community/" in info:
        for r in to_replace['community']:
            parts = info.partition(r)
            if parts[1]:
                if not sort:
                    sort = to_replace['community'][r]
                info = parts[0]
    elif "featured" in info:
        for r in to_replace['featured']:
            parts = info.partition(r)
            if parts[1]:
                if not sort:
                    sort = to_replace['featured'][r]
                info = "community/featured"
    elif "random" in info:
        for r in to_replace['random']:
            parts = info.partition(r)
            if parts[1]:
                if not sort:
                    sort = to_replace['random'][r]
                info = parts[0]
    # These are the 2 special cases for the hot section
    elif info in ("rising", "fresh"):
        if not sort:
            sort = info
        info = ""
    else:
        for r in to_replace['channel']:
            parts = info.partition(r)
            if parts[1]:
                if not sort:
                    sort = to_replace['channel'][r]
                info = parts[0]

    if info:
        normalized = f"https://coub.com/{info}"
    else:
        normalized = "https://coub.com"
    if sort:
        normalized = f"{normalized}#{sort}"

    return normalized


def mapped_input(string):
    """Convert string provided by parse_cli() to valid input source."""
    # Categorize existing paths as lists
    # Otherwise the paths would be forced into a coub link like form
    # which obviously leads to garbled nonsense
    if os.path.exists(string):
        path = valid_list(string)
        return LinkList(path)

    link = normalize_link(string)

    if "https://coub.com/view/" in link:
        source = link.partition("https://coub.com/view/")[2]
    elif "https://coub.com/tags/" in link:
        name = link.partition("https://coub.com/tags/")[2]
        source = Tag(name)
    elif "https://coub.com/search?q=" in link:
        term = link.partition("https://coub.com/search?q=")[2]
        source = Search(term)
    elif "https://coub.com/community/" in link:
        name = link.partition("https://coub.com/community/")[2]
        source = Community(name)
    elif "https://coub.com/random" in link:
        try:
            _, sort = link.split("#")
        except ValueError:
            sort = None
        source = RandomCategory(sort)
    elif "https://coub.com/hot" in link or \
         "https://coub.com#" in link or \
         link.strip("/") == "https://coub.com":
        try:
            _, sort = link.split("#")
        except ValueError:
            sort = None
        source = HotSection(sort)
    # Unfortunately channel URLs don't have any special characteristics
    # and are basically the fallthrough link type
    else:
        name = link.partition("https://coub.com/")[2]
        source = Channel(name)

    return source


def parse_cli():
    """Parse the command line."""
    defaults = DefaultOptions()
    parser = CustomArgumentParser(usage="%(prog)s [OPTIONS] INPUT [INPUT]...")

    # Input
    parser.add_argument("raw_input", nargs="*", type=mapped_input)
    parser.add_argument("-i", "--id", dest="input", action="append",
                        type=no_url)
    parser.add_argument("-l", "--list", dest="input", action="append",
                        type=LinkList)
    parser.add_argument("-c", "--channel", dest="input", action="append",
                        type=Channel)
    parser.add_argument("-t", "--tag", dest="input", action="append",
                        type=Tag)
    parser.add_argument("-e", "--search", dest="input", action="append",
                        type=Search)
    parser.add_argument("-m", "--community", dest="input", action="append",
                        type=Community)
    parser.add_argument("--hot", dest="input", action="append_const",
                        const=HotSection())
    parser.add_argument("--random", "--random#popular", dest="input",
                        action="append_const", const=RandomCategory())
    parser.add_argument("--random#top", dest="input", action="append_const",
                        const=RandomCategory("top"))
    parser.add_argument("--input-help", action=InputHelp)
    # Common Options
    parser.add_argument("-q", "--quiet", dest="verbosity", action="store_const",
                        const=0, default=defaults.VERBOSITY)
    prompt = parser.add_mutually_exclusive_group()
    prompt.add_argument("-y", "--yes", dest="prompt", action="store_const",
                        const="yes", default=defaults.PROMPT)
    prompt.add_argument("-n", "--no", dest="prompt", action="store_const",
                        const="no", default=defaults.PROMPT)
    repeat = parser.add_mutually_exclusive_group()
    repeat.add_argument("-s", "--short", dest="repeat", action="store_const",
                        const=1, default=defaults.REPEAT)
    repeat.add_argument("-r", "--repeat", type=positive_int, default=defaults.REPEAT)
    parser.add_argument("-p", "--path", type=os.path.abspath, default=defaults.PATH)
    parser.add_argument("-k", "--keep", action="store_true", default=defaults.KEEP)
    parser.add_argument("-d", "--duration", type=valid_time,
                        default=defaults.DURATION)
    # Download Options
    parser.add_argument("--connections", type=positive_int,
                        default=defaults.CONNECTIONS)
    parser.add_argument("--retries", type=int, default=defaults.RETRIES)
    parser.add_argument("--limit-num", dest="max_coubs", type=positive_int,
                        default=defaults.MAX_COUBS)
    # Format Selection
    v_qual = parser.add_mutually_exclusive_group()
    v_qual.add_argument("--bestvideo", dest="v_quality", action="store_const",
                        const=-1, default=defaults.V_QUALITY)
    v_qual.add_argument("--worstvideo", dest="v_quality", action="store_const",
                        const=0, default=defaults.V_QUALITY)
    a_qual = parser.add_mutually_exclusive_group()
    a_qual.add_argument("--bestaudio", dest="a_quality", action="store_const",
                        const=-1, default=defaults.A_QUALITY)
    a_qual.add_argument("--worstaudio", dest="a_quality", action="store_const",
                        const=0, default=defaults.A_QUALITY)
    parser.add_argument("--max-video", dest="v_max", default=defaults.V_MAX,
                        choices=["med", "high", "higher"])
    parser.add_argument("--min-video", dest="v_min", default=defaults.V_MIN,
                        choices=["med", "high", "higher"])
    aac = parser.add_mutually_exclusive_group()
    aac.add_argument("--aac", action="store_const", const=2, default=defaults.AAC)
    aac.add_argument("--aac-strict", dest="aac", action="store_const", const=3,
                     default=defaults.AAC)
    # Channel Options
    recoub = parser.add_mutually_exclusive_group()
    recoub.add_argument("--recoubs", action="store_const",
                        const=1, default=defaults.RECOUBS)
    recoub.add_argument("--no-recoubs", dest="recoubs", action="store_const",
                        const=0, default=defaults.RECOUBS)
    recoub.add_argument("--only-recoubs", dest="recoubs", action="store_const",
                        const=2, default=defaults.RECOUBS)
    # Preview Options
    player = parser.add_mutually_exclusive_group()
    player.add_argument("--preview", default=defaults.PREVIEW)
    player.add_argument("--no-preview", dest="preview", action="store_const",
                        const=None, default=defaults.PREVIEW)
    # Misc. Options
    stream = parser.add_mutually_exclusive_group()
    stream.add_argument("--audio-only", dest="a_only", action="store_true",
                        default=defaults.A_ONLY)
    stream.add_argument("--video-only", dest="v_only", action="store_true",
                        default=defaults.V_ONLY)
    stream.add_argument("--share", action="store_true", default=defaults.SHARE)
    parser.add_argument("--write-list", dest="output_list", type=os.path.abspath,
                        default=defaults.OUTPUT_LIST)
    parser.add_argument("--use-archive", dest="archive", type=valid_archive,
                        default=defaults.ARCHIVE)
    # Output
    parser.add_argument("--ext", dest="merge_ext", default=defaults.MERGE_EXT,
                        choices=["mkv", "mp4", "asf", "avi", "flv", "f4v", "mov"])
    parser.add_argument("-o", "--output", dest="name_template",
                        default=defaults.NAME_TEMPLATE)

    # Advanced Options
    parser.set_defaults(
        ffmpeg_path=defaults.FFMPEG_PATH,
        coubs_per_page=defaults.COUBS_PER_PAGE,
        tag_sep=defaults.TAG_SEP,
        fallback_char=defaults.FALLBACK_CHAR,
        write_method=defaults.WRITE_METHOD,
        chunk_size=defaults.CHUNK_SIZE,
    )

    if not sys.argv[1:]:
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()

    # Append raw input (no option) to the regular input list
    if args.input:
        args.input.extend(args.raw_input)
    else:
        args.input = args.raw_input
    # Read archive content
    if args.archive and os.path.exists(args.archive):
        with open(args.archive, "r") as f:
            args.archive_content = {l.strip() for l in f}
    else:
        args.archive_content = set()
    # The default naming scheme is the same as using %id%
    # but internally the default value is None
    if args.name_template == "%id%":
        args.name_template = None
    # Defining whitespace or an empty string in the config isn't possible
    # Instead translate appropriate keywords
    if args.tag_sep == "space":
        args.tag_sep = " "
    if args.fallback_char is None:
        args.fallback_char = ""
    elif args.fallback_char == "space":
        args.fallback_char = " "

    return args


def check_options():
    """Test the user input (command line) for its validity."""
    formats = {'med': 0, 'high': 1, 'higher': 2}
    if formats[opts.v_min] > formats[opts.v_max]:
        err("Quality of --min-quality greater than --max-quality!")
        sys.exit(status.OPT)


def resolve_paths():
    """Change into (and create) the destination directory."""
    if not os.path.exists(opts.path):
        os.makedirs(opts.path)
    os.chdir(opts.path)


async def parse_page(req, session=None):
    """Request a single timeline page and parse its content."""
    if aio:
        async with session.get(req) as resp:
            resp_json = await resp.read()
            resp_json = json.loads(resp_json)
    else:
        with urlopen(req, context=context) as resp:
            resp_json = resp.read()
            resp_json = json.loads(resp_json)

    ids = [
        c['recoub_to']['permalink'] if c['recoub_to'] else c['permalink']
        for c in resp_json['coubs']
    ]
    return ids


def remove_container_dupes(containers):
    """Remove duplicate containers to avoid unnecessary parsing."""
    no_dupes = []
    # Brute-force sorting
    for c in containers:
        unique = True
        for u in no_dupes:
            if (c.type, c.id, c.sort) == (u.type, u.id, u.sort):
                unique = False
        if unique or c.type == "random":
            no_dupes.append(c)

    return no_dupes


def parse_input(sources):
    """Handle the parsing process of all provided input sources."""
    directs = [s for s in sources if isinstance(s, str)]
    containers = [s for s in sources if not isinstance(s, str)]
    containers = remove_container_dupes(containers)

    if opts.max_coubs:
        parsed = directs[:opts.max_coubs]
    else:
        parsed = directs

    if parsed:
        msg("\nReading command line:")
        msg(f"  {len(parsed)} link{'s' if len(parsed) != 1 else ''} found")

    # And now all containers
    for c in containers:
        if opts.max_coubs:
            rest = opts.max_coubs - len(parsed)
            if not rest:
                break
            parsed.extend(asyncio.run(c.process(rest)))
        else:
            parsed.extend(asyncio.run(c.process()))

    if not parsed:
        err("\nNo coub links specified!", color=fgcolors.WARNING)
        sys.exit(status.OPT)

    if opts.max_coubs and len(parsed) >= opts.max_coubs:
        msg(f"\nDownload limit ({opts.max_coubs}) reached!",
            color=fgcolors.WARNING)

    before = len(parsed)
    parsed = list(set(parsed))      # Weed out duplicates
    dupes = before - len(parsed)
    parsed = [i for i in parsed if i not in opts.archive_content]
    archived = before - dupes - len(parsed)
    after = len(parsed)
    if dupes or archived:
        msg(dedent(f"""
            Results:
              {before} input link{'s' if before != 1 else ''}
              {dupes} duplicate{'s' if dupes != 1 else ''}
              {archived} found in archive file
              {after} final link{'s' if after != 1 else ''}"""))
    else:
        msg(dedent(f"""
            Results:
              {after} link{'s' if after != 1 else ''}"""))

    return parsed


def write_list(ids):
    """Output parsed links to a list and exit."""
    with open(opts.output_list, opts.write_method) as f:
        for i in ids:
            print(f"https://coub.com/view/{i}", file=f)
    msg(f"\nParsed coubs written to '{opts.output_list}'!",
        color=fgcolors.SUCCESS)


def get_name(req_json, c_id):
    """Assemble final output name of a given coub."""
    if not opts.name_template:
        return c_id

    specials = {
        '%id%': c_id,
        '%title%': req_json['title'],
        '%creation%': req_json['created_at'],
        '%channel%': req_json['channel']['title'],
        '%tags%': opts.tag_sep.join([t['title'] for t in req_json['tags']]),
    }
    # Coubs don't necessarily belong to a community (although it's rare)
    try:
        specials['%community%'] = req_json['communities'][0]['permalink']
    except (KeyError, TypeError, IndexError):
        specials['%community%'] = "undefined"

    name = opts.name_template
    for to_replace in specials:
        name = name.replace(to_replace, specials[to_replace])

    # An attempt to remove the most blatant problematic characters
    # Linux supports all except /, but \n and \t are only asking for trouble
    # https://dwheeler.com/essays/fixing-unix-linux-filenames.html
    # ' is problematic as it causes issues with FFmpeg's concat muxer
    forbidden = ["\n", "\t", "'", "/"]
    if os.name == "nt":
        forbidden.extend(["<", ">", ":", "\"", "\\", "|", "?", "*"])
    for to_replace in forbidden:
        name = name.replace(to_replace, opts.fallback_char)

    try:
        # Add example extension to simulate the full name length
        f = open(f"{name}.ext", "w")
        f.close()
        os.remove(f"{name}.ext")
    except OSError:
        err(f"Error: Filename invalid or too long! Falling back to '{c_id}'",
            color=fgcolors.WARNING)
        name = c_id

    return name


def exists(name):
    """Test if a video with the given name and requested extension exists."""
    if opts.v_only or opts.share:
        full_name = [f"{name}.mp4"]
    elif opts.a_only:
        # exists() gets called before and after the API request was made
        # Unless MP3 or AAC audio are strictly prohibited, there's no way to
        # tell the final extension before the API request
        full_name = []
        if opts.aac > 0:
            full_name.append(f"{name}.m4a")
        if opts.aac < 3:
            full_name.append(f"{name}.mp3")
    else:
        full_name = [f"{name}.{opts.merge_ext}"]

    for f in full_name:
        if os.path.exists(f):
            return f

    return None


def overwrite(name):
    """Prompt the user if they want to overwrite an existing coub."""
    if opts.prompt == "yes":
        return True
    if opts.prompt == "no":
        return False

    # this should get printed even with --quiet
    # so print() instead of msg()
    print(f"Overwrite file? ({name})")
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
                    chunk = await stream.content.read(opts.chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
    else:
        try:
            with urlopen(link, context=context) as stream, open(path, "wb") as f:
                while True:
                    chunk = stream.read(opts.chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
        except (urllib.error.HTTPError, urllib.error.URLError):
            return


def valid_stream(path, attempted_fix=False):
    """Test a given stream for eventual corruption with a test remux (FFmpeg)."""
    command = [
        opts.ffmpeg_path, "-v", "error",
        "-i", f"file:{path}",
        "-t", "1",
        "-f", "null", "-",
    ]
    out = subprocess.run(command, capture_output=True, text=True, check=False)

    # Fix broken video stream
    if "moov atom not found" in out.stderr and not attempted_fix:
        with open(path, "r+b") as f:
            temp = f.read()
        with open(path, "w+b") as f:
            f.write(b'\x00\x00' + temp[2:])
        return valid_stream(path, attempted_fix=True)

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
        conn = aiohttp.TCPConnector(limit=opts.connections)
        try:
            async with aiohttp.ClientSession(timeout=tout, connector=conn) as session:
                tasks = [c.process(session) for c in coubs]
                await asyncio.gather(*tasks)
        except aiohttp.ClientConnectionError:
            err("\nLost connection to coub.com!")
            raise
        except aiohttp.ClientPayloadError:
            err("\nReceived malformed data!")
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
    except json.decoder.JSONDecodeError:
        err("\nCoub API temporarily not available!")
        check_connection()
        # Reduce the list of coubs to only those yet to finish
        coubs = [c for c in coubs if not c.done]
        level += 1
        attempt_process(coubs, level)
    except Exception as e:
        if aio and isinstance(e, (aiohttp.ClientConnectionError, aiohttp.ClientPayloadError)):
            check_connection()
            # Reduce the list of coubs to only those yet to finish
            coubs = [c for c in coubs if not c.done]
            level += 1
            attempt_process(coubs, level)
        else:
            raise

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Main Function
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def main():
    """Download all requested coubs."""
    global total

    check_prereq()
    check_options()
    resolve_paths()
    check_connection()

    msg("\n### Parse Input ###")

    attempt = 0
    ids = []
    while opts.retries < 0 or attempt <= opts.retries:
        try:
            ids = parse_input(opts.input)
            break
        except json.decoder.JSONDecodeError:
            err("\nCoub API temporarily not available!")
            check_connection()
            attempt += 1

    if ids:
        if opts.output_list:
            write_list(ids)
            sys.exit(0)
        total = len(ids)
        coubs = [Coub(i) for i in ids]

        msg("\n### Download Coubs ###\n")
        try:
            attempt_process(coubs)
        finally:
            clean(coubs)
    elif opts.retries >= 0 and attempt > opts.retries:
        err("\nRan out of connection retries! Please try again later.")
    else:
        msg("\nAll coubs present in archive file!", color=fgcolors.WARNING)

    msg("\n### Finished ###\n")


# Execute main function
if __name__ == '__main__':
    context = create_default_context(cafile=certifi.where())
    opts = parse_cli()
    try:
        main()
    except KeyboardInterrupt:
        err("\nUser Interrupt!", color=fgcolors.WARNING)
        sys.exit(status.INT)

    # Indicate failure if not all input coubs exist after execution
    if done < count:
        sys.exit(status.DOWN)
    sys.exit(0)
