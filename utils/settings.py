# Copyright (C) 2018-2021 HelpSeeker <AlmostSerious@protonmail.ch>
#
# This file is part of CoubDownloader.
#
# CoubDownloader is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# CoubDownloader is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with CoubDownloader.  If not, see <https://www.gnu.org/licenses/>.

from fnmatch import fnmatch
import os
import pathlib
from ssl import SSLContext
import subprocess
import sys
from textwrap import dedent

from utils import container

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Classes
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

class DefaultSettings:

    def __init__(self):
        self._verbosity = 1
        self._prompt = None
        self._path = pathlib.Path().resolve()
        self._keep = False
        self._repeat = 1000
        self._duration = None
        # download defaults
        self._connections = 25
        self._retries = 5
        self._max_coubs = None
        # format defaults
        self._v_quality = -1
        self._a_quality = -1
        self._v_max = "higher"
        self._v_min = "med"
        self._aac = 1
        self._share = False
        # channel defaults
        self._recoubs = 1
        # preview defaults
        self._preview = None
        # misc. defaults
        self._a_only = False
        self._v_only = False
        self._output_list = None
        self._archive = set()
        self._archive_path = None
        self._json = None
        # output defaults
        self._merge_ext = "mkv"
        self._name_template = "%id%"
        # advanced defaults
        self._ffmpeg_path = "ffmpeg"
        self._tag_sep = "_"
        self._fallback_char = "-"
        self._write_method = "w"
        self._chunk_size = 1024

        self.input = []

        self._context = SSLContext()
        self._env = dict(os.environ)
        # Change library search path based on script usage
        # https://pyinstaller.readthedocs.io/en/stable/runtime-information.html#ld-library-path-libpath-considerations
        if hasattr(sys, 'frozen') and hasattr(sys, '_MEIPASS'):
            lp_key = 'LD_LIBRARY_PATH'  # for GNU/Linux and *BSD.
            lp_orig = self._env.get(lp_key + '_ORIG')
            if lp_orig is not None:
                self._env[lp_key] = lp_orig
            else:
                self._env.pop(lp_key, None)   # LD_LIBRARY_PATH was not set


class Settings:

    instance = None

    @staticmethod
    def get():
        if Settings.instance is None:
            Settings.instance = DefaultSettings()
            Settings.instance.__class__ = Settings

        return Settings.instance

    def check(self):
        #Test for discrepancies between min/max video quality
        formats = {
            'med': 0,
            'high': 1,
            'higher': 2,
        }
        if formats[self.v_min] > formats[self.v_max]:
            raise ConfigurationError("--min-quality greater than --max-quality") from None

    @property
    def verbosity(self):
        return self._verbosity

    @verbosity.setter
    def verbosity(self, value):
        self._verbosity = value

    @property
    def prompt(self):
        return self._prompt

    @prompt.setter
    def prompt(self, value):
        self._prompt = value

    @property
    def path(self):
        return self._path

    @path.setter
    def path(self, value):
        path = pathlib.Path(value).resolve()
        if path.is_file():
            raise ConfigurationError("output path is a file") from None
        try:
            path.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            raise ConfigurationError("no write permission for output path") from None

        self._path = path

    @property
    def keep(self):
        return self._keep

    @keep.setter
    def keep(self, value):
        self._keep = value

    @property
    def repeat(self):
        return self._repeat

    @repeat.setter
    def repeat(self, value):
        try:
            value = int(value)
            if value < 1:
                raise ConfigurationError("cannot loop video less than one time") from None
        except ValueError:
            raise ConfigurationError("number of loops must be an integer") from None

        self._repeat = value

    @property
    def duration(self):
        return self._duration

    @duration.setter
    def duration(self, value):
        command = [
            self.ffmpeg_path, "-v", "quiet",
            "-f", "lavfi", "-i", "anullsrc",
            "-t", str(value), "-c", "copy",
            "-f", "null", "-",
        ]
        try:
            subprocess.run(command, env=self.env, check=True)
        except subprocess.CalledProcessError:
            raise ConfigurationError("invalid FFmpeg duration string") from None

        self._duration = value

    @property
    def connections(self):
        return self._connections

    @connections.setter
    def connections(self, value):
        try:
            value = int(value)
            if value < 1:
                raise ConfigurationError("cannot use less than one connection") from None
        except ValueError:
            raise ConfigurationError("number of connections must be an integer") from None

        self._connections = value

    @property
    def retries(self):
        return self._retries

    @retries.setter
    def retries(self, value):
        try:
            value = int(value)
        except ValueError:
            raise ConfigurationError("number of retries must be an integer") from None

        self._retries = value

    @property
    def max_coubs(self):
        return self._max_coubs

    @max_coubs.setter
    def max_coubs(self, value):
        try:
            value = int(value)
            if value < 1:
                raise ConfigurationError("nothing to do with less than one coub to download") from None
        except ValueError:
            raise ConfigurationError("quantity limit must be an interger") from None


        self._max_coubs = value

    @property
    def v_quality(self):
        return self._v_quality

    @v_quality.setter
    def v_quality(self, value):
        self._v_quality = value

    @property
    def a_quality(self):
        return self._a_quality

    @a_quality.setter
    def a_quality(self, value):
        self._a_quality = value

    @property
    def v_max(self):
        return self._v_max

    @v_max.setter
    def v_max(self, value):
        if value not in ["higher", "high", "med"]:
            raise ConfigurationError("max video quality must be 'higher', 'high' or 'med'") from None

        self._v_max = value

    @property
    def v_min(self):
        return self._v_min

    @v_min.setter
    def v_min(self, value):
        if value not in ["higher", "high", "med"]:
            raise ConfigurationError("min video quality must be 'higher', 'high' or 'med'") from None

        self._v_min = value

    @property
    def aac(self):
        return self._aac

    @aac.setter
    def aac(self, value):
        self._aac = value

    @property
    def share(self):
        return self._share

    @share.setter
    def share(self, value):
        self._share = value

    @property
    def recoubs(self):
        return self._recoubs

    @recoubs.setter
    def recoubs(self, value):
        self._recoubs = value

    @property
    def preview(self):
        return self._preview

    @preview.setter
    def preview(self, value):
        self._preview = value

    @property
    def a_only(self):
        return self._a_only

    @a_only.setter
    def a_only(self, value):
        self._a_only = value

    @property
    def v_only(self):
        return self._v_only

    @v_only.setter
    def v_only(self, value):
        self._v_only = value

    @property
    def output_list(self):
        return self._output_list

    @output_list.setter
    def output_list(self, value):
        self._output_list = value

    @property
    def archive(self):
        return self._archive

    @archive.setter
    def archive(self, value):
        # TODO: Change archive path from string to pathlib.Path
        self.archive_path = value
        try:
            with open(self.archive_path, "r") as f:
                self._archive = {l.strip() for l in f}
        except FileNotFoundError:
            pass
        except (OSError, UnicodeError):
            # TODO: Look up exception types
            raise ConfigurationError("unable to open archive file") from None

    @property
    def archive_path(self):
        return self._archive_path

    @archive_path.setter
    def archive_path(self, value):
        self._archive_path = value

    @property
    def json(self):
        return self._json

    @json.setter
    def json(self, value):
        self._json = value

    @property
    def merge_ext(self):
        # TODO: Add extension support
        return self._merge_ext

    @merge_ext.setter
    def merge_ext(self, value):
        if value not in ["mkv", "mp4", "asf", "avi", "flv", "f4v", "mov"]:
            raise ConfigurationError("unsupported extension")

        self._merge_ext = value

    @property
    def name_template(self):
        return self._name_template

    @name_template.setter
    def name_template(self, value):
        # TODO: Port over Gyre string check
        self._name_template = value

    @property
    def ffmpeg_path(self):
        return self._ffmpeg_path

    @ffmpeg_path.setter
    def ffmpeg_path(self, value):
        self._ffmpeg_path = value

    @property
    def tag_sep(self):
        return self._tag_sep

    @tag_sep.setter
    def tag_sep(self, value):
        self._tag_sep = value

    @property
    def fallback_char(self):
        return self._fallback_char

    @fallback_char.setter
    def fallback_char(self, value):
        self._fallback_char = value

    @property
    def write_method(self):
        return self._write_method

    @write_method.setter
    def write_method(self, value):
        self._write_method = value

    @property
    def chunk_size(self):
        return self._chunk_size

    @chunk_size.setter
    def chunk_size(self, value):
        self._chunk_size = value

    @property
    def context(self):
        return self._context

    @context.setter
    def context(self, value):
        self._context = value

    @property
    def env(self):
        return self._env

    @env.setter
    def env(self, value):
        self._env = value


class ConfigurationError(Exception):

    def __init__(self, cause):
        super().__init__()
        self.cause = cause

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Functions
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def print_help():
    print(dedent(f"""\
        CoubDownloader is a simple download script for coub.com

        Usage: {sys.argv[0]} [OPTIONS] INPUT [INPUT]...

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
          -p, --path PATH       set output destination (def: '{Settings.get().path}')
          -k, --keep            keep the individual video/audio parts
          -r, --repeat N        repeat video N times (def: until audio ends)
          -d, --duration TIME   specify max. coub duration (FFmpeg syntax)

        Download options:
          --connections N       max. number of connections (def: {Settings.get().connections})
          --retries N           number of retries when connection is lost (def: {Settings.get().retries})
                                  0 to disable, <0 to retry indefinitely
          --limit-num LIMIT     limit max. number of downloaded coubs

        Format selection:
          --bestvideo           download best available video quality (def)
          --worstvideo          download worst available video quality
          --max-video FORMAT    set limit for the best video format (def: {Settings.get().v_max})
                                  Supported values: med, high, higher
          --min-video FORMAT    set limit for the worst video format (def: {Settings.get().v_min})
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
          --ext EXTENSION       merge output with the given extension (def: {Settings.get().merge_ext})
                                  ignored if no merge is required
          -o, --output FORMAT   save output with the given template (def: {Settings.get().name_template})

            Special strings:
              %id%        - coub ID (identifier in the URL)
              %title%     - coub title
              %creation%  - creation date/time
              %community% - coub community
              %channel%   - channel title
              %tags%      - all tags (separated by {Settings.get().tag_sep})

            Other strings will be interpreted literally.
            This option has no influence on the file extension.
    """))


def print_help_input():
    print(dedent("""\
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
    """))


def parse_cli():
    settings = Settings.get()

    needs_value = [
        "-i", "--id",
        "-l", "--list",
        "-c", "--channel",
        "-t", "--tag",
        "-e", "--search",
        "-m", "--community",
        "-p", "--path",
        "-r", "--repeat",
        "-d", "--duration",
        "--story"
        "--connections",
        "--retries",
        "--limit-num",
        "--max-video",
        "--min-video",
        "--preview",
        "--write-list",
        "--use-archive",
        "--ext",
        "-o", "--output",
    ]

    treat_as_input = False
    i = 1
    while i < len(sys.argv):
        option = sys.argv[i]
        if option in needs_value and not treat_as_input:
            try:
                value = sys.argv[i+1]
            except IndexError:
                raise ConfigurationError(f"missing value for '{option}'") from None
            i += 2
        else:
            i += 1

        # Input
        if treat_as_input or not fnmatch(option, "-*"):
            settings.input.append(option)
        elif option in ("-i", "--id"):
            settings.input.append(value)
        # elif option in ("-l", "--list"):
        #     settings.input.append(container.LinkList(value))
        # elif option in ("-c", "--channel"):
        #     settings.input.append(container.Channel(value))
        # elif option in ("-t", "--tag"):
        #     settings.input.append(container.Tag(value))
        # elif option in ("-e", "--search"):
        #     settings.input.append(container.Search(value))
        # elif option in ("-m", "--community",):
        #     settings.input.append(container.Community(value))
        # Hot section selection doesn't have an argument, so the option
        # itself can come with a sort order attached
        # elif fnmatch(option, "--hot*"):
        #     settings.input.append(container.HotSection(option))
        elif option in ("--input-help",):
            print_help_input()
            sys.exit(0)
        # Common options
        elif option in ("-h", "--help"):
            print_help()
            sys.exit(0)
        elif option in ("-q", "--quiet"):
            settings.verbosity = 0
        elif option in ("-y", "--yes"):
            settings.prompt_answer = "yes"
        elif option in ("-n", "--no"):
            settings.prompt_answer = "no"
        elif option in ("-s", "--short"):
            settings.repeat = 1
        elif option in ("-p", "--path"):
            settings.path = value
        elif option in ("-k", "--keep"):
            settings.keep = True
        elif option in ("-r", "--repeat"):
            settings.repeat = value
        elif option in ("-d", "--duration"):
            settings.dur = value
        # Download options
        elif option in ("--connections",):
            settings.connect = value
        elif option in ("--retries",):
            settings.retries = value
        elif option in ("--limit-num",):
            settings.max_coubs = value
        # Format selection
        elif option in ("--bestvideo",):
            settings.v_quality = -1
        elif option in ("--worstvideo",):
            settings.v_quality = 0
        elif option in ("--max-video",):
            settings.v_max = value
        elif option in ("--min-video",):
            settings.v_min = value
        elif option in ("--bestaudio",):
            settings.a_quality = -1
        elif option in ("--worstaudio",):
            settings.a_quality = 0
        elif option in ("--aac",):
            settings.aac = 2
        elif option in ("--aac-strict",):
            settings.aac = 3
        elif option in ("--share",):
            settings.share = True
        # Channel options
        elif option in ("--recoubs",):
            settings.recoubs = True
        elif option in ("--no-recoubs",):
            settings.recoubs = False
        elif option in ("--only-recoubs",):
            settings.only_recoubs = True
        # Preview options
        elif option in ("--preview",):
            settings.preview = True
            settings.preview_command = value
        elif option in ("--no-preview",):
            settings.preview = False
        # Misc options
        elif option in ("--audio-only",):
            settings.a_only = True
        elif option in ("--video-only",):
            settings.v_only = True
        elif option in ("--write-list",):
            settings.out_file = value
        elif option in ("--use-archive",):
            # TODO: Check for file validity
            settings.archive = value
        # Output
        elif option in ("-o", "--output"):
            # The default naming scheme is the same as using %id%
            # but internally the default value is None
            # So simply don't assign the argument if it's only %id%
            if value != "%id%":
                settings.out_format = value
        elif option in ("--",):
            treat_as_input = True
        # Unknown options
        else:
            raise ConfigurationError(f"unknown flag '{option}'") from None

    # The default naming scheme is the same as using %id%
    # but internally the default value is None
    # if args.name_template == "%id%":
    #     args.name_template = None


# def normalize_link(string):
#     """Format link to guarantee strict adherence to https://coub.com/<info>#<sort>"""
#     to_replace = {
#         'channel': {
#             '/coubs': None,
#             '/reposts': None,
#             '/stories': None,
#         },
#         'tag': {
#             '/likes': "top",
#             '/views': "views_count",
#             '/fresh': "fresh"
#         },
#         'search': {
#             '/likes': "top",
#             '/views': "views_count",
#             '/fresh': "most_recent",
#             '/channels': None,
#         },
#         'community': {
#             '/rising': "rising",
#             '/fresh': "fresh",
#             '/top': "top",
#             '/views': "views_count",
#             '/random': "random",
#         },
#         'featured': {
#             'featured/coubs/top_of_the_month': "top_of_the_month",
#             'featured/coubs/undervalued': "undervalued",
#             'featured/stories': None,
#             'featured/channels': None,
#             'featured': "recent",
#         },
#         'random': {
#             '/top': "top",
#         },
#     }

#     try:
#         link, sort = string.split("#")
#     except ValueError:
#         link = string
#         sort = None

#     info = link.rpartition("coub.com")[2]
#     info = info.strip("/")

#     if "tags/" in info:
#         for r in to_replace['tag']:
#             parts = info.partition(r)
#             if parts[1]:
#                 if not sort:
#                     sort = to_replace['tag'][r]
#                 info = parts[0]
#     If search is followed by ?q= then it shouldn't have any suffixes anyway
#     elif "search/" in info:
#         for r in to_replace['search']:
#             parts = info.partition(r)
#             if parts[1]:
#                 if not sort:
#                     sort = to_replace['search'][r]
#                 info = f"{parts[0]}{parts[2]}"
#     elif "community/" in info:
#         for r in to_replace['community']:
#             parts = info.partition(r)
#             if parts[1]:
#                 if not sort:
#                     sort = to_replace['community'][r]
#                 info = parts[0]
#     elif "stories/" in info:
#         pass
#     elif "featured" in info:
#         for r in to_replace['featured']:
#             parts = info.partition(r)
#             if parts[1]:
#                 if not sort:
#                     sort = to_replace['featured'][r]
#                 info = "community/featured"
#     elif "random" in info:
#         for r in to_replace['random']:
#             parts = info.partition(r)
#             if parts[1]:
#                 if not sort:
#                     sort = to_replace['random'][r]
#                 info = parts[0]
#     These are the 2 special cases for the hot section
#     elif info in ("rising", "fresh"):
#         if not sort:
#             sort = info
#         info = ""
#     else:
#         for r in to_replace['channel']:
#             parts = info.partition(r)
#             if parts[1]:
#                 if not sort:
#                     sort = to_replace['channel'][r]
#                 info = parts[0]

#     if info:
#         normalized = f"https://coub.com/{info}"
#     else:
#         normalized = "https://coub.com"
#     if sort:
#         normalized = f"{normalized}#{sort}"

#     return normalized


# def mapped_input(string):
#     """Convert string provided by parse_cli() to valid input source."""
#     Categorize existing paths as lists
#     Otherwise the paths would be forced into a coub link like form
#     which obviously leads to garbled nonsense
#     if os.path.exists(string):
#         return container.LinkList(string)

#     link = normalize_link(string)

#     if "https://coub.com/view/" in link:
#         source = link.partition("https://coub.com/view/")[2]
#     elif "https://coub.com/tags/" in link:
#         name = link.partition("https://coub.com/tags/")[2]
#         source = container.Tag(name)
#     elif "https://coub.com/search?q=" in link:
#         term = link.partition("https://coub.com/search?q=")[2]
#         source = container.Search(term)
#     elif "https://coub.com/community/" in link:
#         name = link.partition("https://coub.com/community/")[2]
#         source = container.Community(name)
#     elif "https://coub.com/stories/" in link:
#         name = link.partition("https://coub.com/stories/")[2]
#         source = container.Story(name)
#     elif "https://coub.com/random" in link:
#         try:
#             _, sort = link.split("#")
#         except ValueError:
#             sort = None
#         source = container.RandomCategory(sort)
#     elif "https://coub.com/hot" in link or \
#          "https://coub.com#" in link or \
#          link.strip("/") == "https://coub.com":
#         try:
#             _, sort = link.split("#")
#         except ValueError:
#             sort = None
#         source = container.HotSection(sort)
#     Unfortunately channel URLs don't have any special characteristics
#     and are basically the fallthrough link type
#     else:
#         name = link.partition("https://coub.com/")[2]
#         source = container.Channel(name)

#     return source
