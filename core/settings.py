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

import os
import pathlib
from ssl import SSLContext
import subprocess
import sys
from textwrap import dedent

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Classes
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

class DefaultSettings:

    def __init__(self):
        # Change terminal output verbosity
        #   0 -> print only errors
        # >=1 -> all messages
        # Supported values: 0, 1
        self._verbosity = 1

        # How to treat already existing files
        #   True  -> overwrite existing files
        #   False -> skip existing files
        # Supported values: True, False
        self._overwrite = False

        # Output location for downloaded coubs
        # Supported values: pathlib.Path objects
        # See https://docs.python.org/3/library/pathlib.html
        self._path = pathlib.Path().resolve()

        # What to do with the individual streams after merging
        #   True  -> keep the extra files
        #   False -> delete the extra files
        # Supported values: True, False
        self._keep = False

        # How often to loop the video to the audio
        # The resulting looped video length will never exceed the audio length
        # Supported values: Positive integers (excl. 0)
        self._repeat = 1000

        # Max merged video duration
        # Can be used to restrict the looped video duration further
        # Ignored if looped video already shorter than the max duration
        # Supported values: FFmpeg time syntax (excl. negative values) or None
        # See https://ffmpeg.org/ffmpeg-utils.html#time-duration-syntax
        self._duration = None

        # Maximum number of connections
        # Only raise this value, if your internet connection isn't yet fully utilized
        # Too many connections can result in Coub simply refusing them
        # Supported values: Positive integers (excl. 0)
        self._connections = 25

        # How often to reestablish connections before giving up
        #  >0 -> retry the specified number of times
        #   0 -> don't retry
        #  <0 -> retry indefinitely
        # Supported values: Integers
        self._retries = 5

        # Max number of coubs to download during one script invocation
        # Supported values: Positive integers (excl. 0) or None
        self._max_coubs = None

        # What available video resolution and audio quality to select
        # The list of available video resolutions can be reduced via _v_max, _v_min
        #   0 ->  lowest resolution / worst quality
        #  -1 -> highest resolution /  best quality
        # Supported values: 0, -1
        self._v_quality = -1
        self._a_quality = -1

        # Limit the list of available video resolutions
        #   _v_max -> highest allowed resolution
        #   _v_min ->  lowest allowed resolution
        # Supported values:
        #   "med"    (max 640x480)
        #   "high"   (max 1280x960)
        #   "higher" (max 1600x1200)
        self._v_max = "higher"
        self._v_min = "med"

        # Download special 'share' version
        # Usually shorter, low resolution videos with AAC audio
        # This is what you get when you click the download button on their website
        # Supported values: True, False
        self._share = False

        # How to treat recoubs during channel downloads
        #   0 -> no recoubs
        #   1 -> with recoubs
        #   2 -> only recoubs
        # Supported values: 0, 1, 2
        self._recoubs = 1

        # Enable/disable audio/video download
        # _video and _audio mustn't both be False at the same time
        #   True  -> download stream (if it exists)
        #   False -> don't download stream
        # Supported values: True, False
        self._audio = True
        self._video = True

        # Print parsed coub links to a file
        # This option will make the script exit after the parsing stage
        # Supported values: pathlib.Path objects or None
        # See https://docs.python.org/3/library/pathlib.html
        self._output_list = None
        
        # Print unavaiable coub links to a file
        # Supported values: pathlib.Path objects or None
        # See https://docs.python.org/3/library/pathlib.html
        self._unavaiable_list = None

        # Use an archive file to keep track of already downloaded coubs
        # Supported values: pathlib.Path objects or None
        # See https://docs.python.org/3/library/pathlib.html
        self._archive = None

        # Output additional information about downloaded coubs to a JSON file
        # The following information will be recorded:
        #   -) ID (identifier in the URL)
        #   -) Title
        #   -) Creation date/time
        #   -) Channel
        #   -) Community
        #   -) Tags
        # Supported values: pathlib.Path objects or None
        # See https://docs.python.org/3/library/pathlib.html
        self._json = None

        # Container to merge separate video/audio streams into
        # Supported values: Containers with support for AVC video and MP3 audio
        # See: https://en.wikipedia.org/wiki/Comparison_of_video_container_formats
        # Some common examples: mkv, mp4, asf, avi, flv, f4v, mov
        self._merge_ext = "mkv"

        # Name template for downloaded coubs
        # Supports the following special keywords:
        #   %id%        - ID (identifier in the URL)
        #   %title%     - Title
        #   %creation%  - Creation date/time
        #   %community% - Which community the coub belongs to
        #   %channel%   - The uploader's channel name
        #   %tags%      - All tags (separated by tag_sep, see below)
        # All other strings are interpreted literally.
        # Supported values: Strings
        self._name_template = "%id%"

        # Advanced Settings
        self._ffmpeg_path = "ffmpeg"
        self._tag_sep = "_"             # tag seperator in output filenames
        self._write_method = "w"        # for _output_list; w -> overwrite / a -> append
        self._chunk_size = 1024
        self._allow_unicode = True      # for output filenames

        # DO NOT TOUCH
        self.input = set()
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
        # TODO: Add more checks
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
    def overwrite(self):
        return self._overwrite

    @overwrite.setter
    def overwrite(self, value):
        self._overwrite = value

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
                raise ConfigurationError("quantity limit must be >0") from None
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
            raise ConfigurationError(
                "max video quality must be 'higher', 'high' or 'med'"
            ) from None

        self._v_max = value

    @property
    def v_min(self):
        return self._v_min

    @v_min.setter
    def v_min(self, value):
        if value not in ["higher", "high", "med"]:
            raise ConfigurationError(
                "min video quality must be 'higher', 'high' or 'med'"
            ) from None

        self._v_min = value

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
    def audio(self):
        return self._audio

    @audio.setter
    def audio(self, value):
        if not (value or self.video):
            raise ConfigurationError("can't disable both video and audio") from None
        self._audio = value

    @property
    def video(self):
        return self._video

    @video.setter
    def video(self, value):
        if not (value or self.audio):
            raise ConfigurationError("can't disable both video and audio") from None
        self._video = value

    # TODO: Add write permission error handling during runtime
    @property
    def output_list(self):
        return self._output_list

    @output_list.setter
    def output_list(self, value):
        # We're gonna trust the user not to output to a location without write permission
        self._output_list = pathlib.Path(value).resolve()

    @property
    def unavaiable_list(self):
        return self._unavaiable_list

    @unavaiable_list.setter
    def unavaiable_list(self, value):
        # We're gonna trust the user not to output to a location without write permission
        self._unavaiable_list = pathlib.Path(value).resolve()    
    
    @property
    def archive(self):
        return self._archive

    @archive.setter
    def archive(self, value):
        path = pathlib.Path(value).resolve()
        try:
            with path.open("r") as f:
                _ = f.read(1)
        except FileNotFoundError:
            pass
        # Only checks read and not write permission
        except (PermissionError, OSError, UnicodeError):
            raise ConfigurationError("can't access archive file") from None

        self._archive = path

    @property
    def json(self):
        return self._json

    @json.setter
    def json(self, value):
        # We're gonna trust the user not to output to a location without write permission
        self._json = pathlib.Path(value).resolve()

    @property
    def merge_ext(self):
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
    def allow_unicode(self):
        return self._allow_unicode

    @allow_unicode.setter
    def allow_unicode(self, value):
        self._allow_unicode = value

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

# TODO: Add counter-switch for all bool switches
# TODO: Show defaults where appropriate
# TODO: Show "(def)" based on default value

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
          -q, --quiet           suppress all non-error messages
          -y, --overwrite       overwrite any existing files
          -n, --no-overwrite    skip any existing files (def)
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
          --share               download 'share' video (shorter and includes audio)

        Channel options:
          --recoubs             include recoubs during channel downloads (def)
          --no-recoubs          exclude recoubs during channel downloads
          --only-recoubs        only download recoubs during channel downloads

        Misc. options:
          --audio-only              only download audio streams
          --video-only              only download video streams
          --write-list FILE         write all parsed coub links to FILE
          --unavaiable-list FILE    write unavaiable coubs links to FILE
          --use-archive FILE        use FILE to keep track of already downloaded coubs
          --print-json FILE         output basic coub infos as JSON to FILE
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

            Channels:         newest (default)
                              likes_count
                              views_count
                              oldest
                              random

            Searches:         relevance (default)
                              likes_count
                              views_count
                              newest

            Tags:             newest_popular (default)
                              likes_count
                              views_count
                              newest

            Communities:      daily
                              weekly
                              monthly (default)
                              quarter
                              half
                              rising
                              fresh
                              likes_count
                              views_count
                              random

            Featured:         recent (default)
            (community)       top_of_the_month
                              undervalued

            Coub of the Day:  recent (default)
            (community)       top
                              views_count

            Hot section:      daily
                              weekly
                              monthly (default)
                              quarter
                              half
                              rising
                              fresh

            Random:           popular (default)
                              top
    """))


def parse_cli():
    from core.container import create_container

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
        "--unavaiable-list",
        "--use-archive",
        "--print-json",
        "--ext",
        "-o", "--output",
    ]
    supports_sort = [
        "-c", "--channel",
        "-t", "--tag",
        "-e", "--search",
        "-m", "--community",
    ]
    special_sort_items = [
        "--hot#",
        "--random#",
    ]

    treat_as_input = False
    i = 1
    while i < len(sys.argv):
        option = sys.argv[i]
        id_ = sort = None

        if option in needs_value and not treat_as_input:
            try:
                id_ = value = sys.argv[i+1]
            except IndexError:
                raise ConfigurationError(f"missing value for '{option}'") from None
            i += 2
        else:
            i += 1

        if option in supports_sort and "#" in value:
            id_, sort = value.split("#")

        for item in special_sort_items:
            if option.startswith(item):
                option, sort = option.split("#")

        # Input
        if treat_as_input or not option.startswith("-"):
            settings.input.add(create_container(*map_raw_input(option)))
        elif option in ("-i", "--id"):
            settings.input.add(create_container("coub", id_, sort))
        elif option in ("-l", "--list"):
            settings.input.add(create_container("list", id_, sort))
        elif option in ("-c", "--channel"):
            settings.input.add(create_container("channel", id_, sort))
        elif option in ("-t", "--tag"):
            settings.input.add(create_container("tag", id_, sort))
        elif option in ("-e", "--search"):
            settings.input.add(create_container("search", id_, sort))
        elif option in ("-m", "--community",):
            settings.input.add(create_container("community", id_, sort))
        elif option.startswith("--hot"):
            settings.input.add(create_container("Hot section", id_, sort))
        elif option.startswith("--random"):
            settings.input.add(create_container("random coubs", id_, sort))
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
            settings.overwrite = True
        elif option in ("-n", "--no"):
            settings.overwrite = False
        elif option in ("-s", "--short"):
            settings.repeat = 1
        elif option in ("-p", "--path"):
            settings.path = value
        elif option in ("-k", "--keep"):
            settings.keep = True
        elif option in ("-r", "--repeat"):
            settings.repeat = value
        elif option in ("-d", "--duration"):
            settings.duration = value
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
        elif option in ("--share",):
            settings.share = True
            # share version is basically like a video-only download
            settings.video = True
            settings.audio = False
        # Channel options
        elif option in ("--recoubs",):
            settings.recoubs = 1
        elif option in ("--no-recoubs",):
            settings.recoubs = 0
        elif option in ("--only-recoubs",):
            settings.recoubs = 2
        # Preview options
        elif option in ("--preview",):
            settings.preview = True
            settings.preview_command = value
        elif option in ("--no-preview",):
            settings.preview = False
        # Misc options
        elif option in ("--audio-only",):
            settings.video = False
        elif option in ("--video-only",):
            settings.audio = False
        elif option in ("--write-list",):
            settings.output_list = value
        elif option in ("--unavaiable-list",):
            settings.unavaiable_list = value
        elif option in ("--use-archive",):
            settings.archive = value
        elif option in ("--print-json",):
            settings.json = value
        # Output
        elif option in ("--ext",):
            settings.merge_ext = value
        elif option in ("-o", "--output"):
            settings.name_template = value
        elif option in ("--",):
            treat_as_input = True
        # Unknown options
        else:
            raise ConfigurationError(f"unknown flag '{option}'") from None


def map_raw_input(string):
    if pathlib.Path(string).exists():
        return ("list", string, None)

    sort_map = {
        "channel": {
            "/coubs": None,
            "/reposts": None,
            "/stories": None,
        },
        "search": {
            "/likes": "likes_count",
            "/views": "views_count",
            "/fresh": "newest",
            "/channels": None,
        },
        "tag": {
            "/likes": "likes_count",
            "/views": "views_count",
            "/fresh": "newest"
        },
        "community": {
            "/rising": "rising",
            "/fresh": "fresh",
            "/top": "likes_count",
            "/views": "views_count",
            "/random": "random",
            # The following are special values for the featured community
            "/coubs/top_of_the_month": "top_of_the_month",
            "/coubs/undervalued": "undervalued",
            "/stories": None,
            "/channels": None,
        },
        "Hot Section": {
            "/rising": "rising",
            "/fresh": "fresh",
            "/hot": "monthly",
        },
        "Random": {
            "/top": "top",
        },
    }

    # Shorten URL for easier parsing
    url = string.strip(" /").lstrip("htps:/")

    # Type detection
    if url.startswith("coub.com/view"):
        type_ = "coub"
    elif url.startswith("coub.com/search"):
        type_ = "search"
    elif url.startswith("coub.com/tags"):
        type_ = "tag"
    elif url.startswith(("coub.com/community/featured", "coub.com/featured")):
        type_ = "community"
        id_ = "featured"
    elif url.startswith("coub.com/community/coub-of-the-day"):
        type_ = "community"
        id_ = "coub-of-the-day"
    elif url.startswith("coub.com/community"):
        type_ = "community"
    elif url.startswith("coub.com/stories"):
        type_ = "story"
    elif url.startswith("coub.com/random"):
        type_ = "random coubs"
    elif url in ["coub.com", "coub.com/rising", "coub.com/fresh", "coub.com/hot"]:
        type_ = "Hot section"
    else:
        type_ = "channel"

    # Sort detection
    sort = None
    if type_ in sort_map:
        for suffix in sort_map[type_]:
            # Despite its name, this string isn't necessarily at the very end (e.g. searches)
            if suffix in url:
                sort = sort_map[type_][suffix]
                url = url.replace(suffix, "")

    # ID detection
    id_ = None
    if type_ == "coub":
        id_ = url.partition("coub.com/view/")[2]
    elif type_ == "channel":
        id_ = url.partition("coub.com/")[2]
    elif type_ == "search":
        id_ = url.partition("coub.com/search?q=")[2]
    elif type_ == "tag":
        id_ = url.partition("coub.com/tags/")[2]
    elif type_ == "community" and not id_:
        id_ = url.partition("coub.com/community/")[2]
    elif type_ == "story":
        id_ = url.partition("coub.com/stories/")[2]

    return (type_, id_, sort)
