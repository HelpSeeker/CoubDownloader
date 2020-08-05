#!/usr/bin/env python3

"""
Copyright (C) 2018-2020 HelpSeeker <AlmostSerious@protonmail.ch>

This file is part of CoubDownloader.

CoubDownloader is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

CoubDownloader is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with CoubDownloader.  If not, see <https://www.gnu.org/licenses/>.
"""

import argparse
import os
import sys

from functools import partial
from subprocess import run, CalledProcessError
from textwrap import dedent

from utils import container

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Global Variables
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

ENV = dict(os.environ)
# Change library search path based on script usage
# https://pyinstaller.readthedocs.io/en/stable/runtime-information.html#ld-library-path-libpath-considerations
if hasattr(sys, 'frozen') and hasattr(sys, '_MEIPASS'):
    lp_key = 'LD_LIBRARY_PATH'  # for GNU/Linux and *BSD.
    lp_orig = ENV.get(lp_key + '_ORIG')
    if lp_orig is not None:
        ENV[lp_key] = lp_orig
    else:
        ENV.pop(lp_key, None)   # LD_LIBRARY_PATH was not set

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Classes
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

class ConfigError(Exception):
    """Thrown when wrong default or unknown config options are encountered."""

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
    JSON = None
    # Output defaults
    MERGE_EXT = "mkv"
    NAME_TEMPLATE = "%id%"
    # Advanced defaults
    FFMPEG_PATH = "ffmpeg"
    TAG_SEP = "_"
    FALLBACK_CHAR = "-"
    WRITE_METHOD = "w"
    CHUNK_SIZE = 1024

    def __init__(self, config_dirs):
        self.error = []

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
            self.error.append(f"Error reading config file '{path}'!")
            user_settings = []

        for setting in user_settings:
            name = setting.split("=")[0].strip()
            value = setting.split("=")[1].strip()
            if hasattr(self, name):
                value = self.guess_string_type(name, value)
                setattr(self, name, value)
            else:
                self.error.append(f"Unknown option in config file: {name}")

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
            "JSON": (lambda x: isinstance(x, str) or x is None),
            "MERGE_EXT": (lambda x: x in ["mkv", "mp4", "asf", "avi", "flv", "f4v", "mov"]),
            "NAME_TEMPLATE": (lambda x: isinstance(x, str) or x is None),
            "FFMPEG_PATH": (lambda x: isinstance(x, str)),
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
                self.error.append(f"{e[0]}: invalid default value '{e[1]}'")

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
            "JSON",
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
          --story ID            download coubs from the story with the given ID
                                  ID as seen in the URL (e.g. 12345-example-story)
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
          -g, --gui             start Tkinter GUI

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
          --print-json FILE     output basic coub infos as JSON to FILE
                                  see --output for the currently available infos

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
          -) Stories
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
            Story:        https://coub.com/stories/example-story
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
            Story:        --story example-story
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
            Story:        stories/example-story
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

          Input types not mentioned in the following list don't support sorting.

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

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Functions
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def positive_int(string):
    """Convert string provided by parse_cli() to a positive int."""
    try:
        value = int(string)
        if value <= 0:
            raise ValueError
    except ValueError:
        raise argparse.ArgumentTypeError("invalid positive int")
    return value


def valid_time(ffmpeg_path, string):
    """Test valditiy of time syntax with FFmpeg."""
    command = [
        ffmpeg_path, "-v", "quiet",
        "-f", "lavfi", "-i", "anullsrc",
        "-t", string, "-c", "copy",
        "-f", "null", "-",
    ]
    try:
        run(command, env=ENV, check=True)
    except CalledProcessError:
        raise argparse.ArgumentTypeError("invalid time syntax")

    return string


def valid_text_file(string):
    """Check if a provided path points to a decodable text file."""
    path = os.path.abspath(string)
    try:
        with open(path, "r") as f:
            _ = f.read(1)
    except FileNotFoundError:
        pass
    except (OSError, UnicodeError):
        raise argparse.ArgumentTypeError(f"invalid text file '{string}'")

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
    elif "stories/" in info:
        pass
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
        return container.LinkList(string)

    link = normalize_link(string)

    if "https://coub.com/view/" in link:
        source = link.partition("https://coub.com/view/")[2]
    elif "https://coub.com/tags/" in link:
        name = link.partition("https://coub.com/tags/")[2]
        source = container.Tag(name)
    elif "https://coub.com/search?q=" in link:
        term = link.partition("https://coub.com/search?q=")[2]
        source = container.Search(term)
    elif "https://coub.com/community/" in link:
        name = link.partition("https://coub.com/community/")[2]
        source = container.Community(name)
    elif "https://coub.com/stories/" in link:
        name = link.partition("https://coub.com/stories/")[2]
        source = container.Story(name)
    elif "https://coub.com/random" in link:
        try:
            _, sort = link.split("#")
        except ValueError:
            sort = None
        source = container.RandomCategory(sort)
    elif "https://coub.com/hot" in link or \
         "https://coub.com#" in link or \
         link.strip("/") == "https://coub.com":
        try:
            _, sort = link.split("#")
        except ValueError:
            sort = None
        source = container.HotSection(sort)
    # Unfortunately channel URLs don't have any special characteristics
    # and are basically the fallthrough link type
    else:
        name = link.partition("https://coub.com/")[2]
        source = container.Channel(name)

    return source


def parse_cli(config_locations):
    """
    Parse the command line.

    Return values:
        On Success: Option object
        On Failure: List with error messages (unless argparse exits)
    """
    defaults = DefaultOptions(config_locations)
    if defaults.error:
        raise ConfigError("\n".join(defaults.error))

    # Uses FFmpeg to test duration string, so it needs to know about custom paths
    valid_dur = partial(valid_time, defaults.FFMPEG_PATH)

    parser = CustomArgumentParser(usage="%(prog)s [OPTIONS] INPUT [INPUT]...")

    # Input
    parser.add_argument("raw_input", nargs="*", type=mapped_input)
    parser.add_argument("-i", "--id", dest="input", action="append")
    parser.add_argument("-l", "--list", dest="input", action="append",
                        type=container.LinkList)
    parser.add_argument("-c", "--channel", dest="input", action="append",
                        type=container.Channel)
    parser.add_argument("-t", "--tag", dest="input", action="append",
                        type=container.Tag)
    parser.add_argument("-e", "--search", dest="input", action="append",
                        type=container.Search)
    parser.add_argument("-m", "--community", dest="input", action="append",
                        type=container.Community)
    parser.add_argument("--story", dest="input", action="append",
                        type=container.Story)
    parser.add_argument("--hot", dest="input", action="append_const",
                        const=container.HotSection())
    parser.add_argument("--random", "--random#popular", dest="input",
                        action="append_const", const=container.RandomCategory())
    parser.add_argument("--random#top", dest="input", action="append_const",
                        const=container.RandomCategory("top"))
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
    parser.add_argument("-d", "--duration", type=valid_dur,
                        default=defaults.DURATION)
    parser.add_argument("-g", "--gui", action="store_true")
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
    parser.add_argument("--use-archive", dest="archive", type=valid_text_file,
                        default=defaults.ARCHIVE)
    parser.add_argument("--print-json", dest="json", type=valid_text_file,
                        default=defaults.JSON)
    # Output
    parser.add_argument("--ext", dest="merge_ext", default=defaults.MERGE_EXT,
                        choices=["mkv", "mp4", "asf", "avi", "flv", "f4v", "mov"])
    parser.add_argument("-o", "--output", dest="name_template",
                        default=defaults.NAME_TEMPLATE)

    # Advanced Options
    parser.set_defaults(
        ffmpeg_path=defaults.FFMPEG_PATH,
        tag_sep=defaults.TAG_SEP,
        fallback_char=defaults.FALLBACK_CHAR,
        write_method=defaults.WRITE_METHOD,
        chunk_size=defaults.CHUNK_SIZE,
    )
    args = parser.parse_args()

    # Implicitly set GUI mode if no command line options are provided
    if not sys.argv[1:]:
        args.gui = True
    # GUI-specific tweaks
    if args.gui:
        args.verbosity = 1
        args.input = []
        args.raw_input = []
        # Currently GUI uses the same default path as CLI (i.e. script location)
        #if not args.path or args.path == ".":
        #    args.path = os.path.join(os.path.expanduser("~"), "coubs")

    # Test for discrepancies between min/max video quality
    formats = {'med': 0, 'high': 1, 'higher': 2}
    if formats[args.v_min] > formats[args.v_max]:
        raise ConfigError("Quality of --min-quality greater than --max-quality!")

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
