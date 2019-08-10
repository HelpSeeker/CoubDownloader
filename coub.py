#!/usr/bin/env python3

import sys
import os
import time
import json
import urllib.request
import subprocess
from fnmatch import fnmatch

# TODO
# -) --limit-rate

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Global Variables
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# options object also global (defined in main())

coub_list = []

# Error codes
# 1 -> missing required software
# 2 -> invalid user-specified option
# 3 -> misc. runtime error (missing function argument, unknown value in case, etc.)
# 4 -> not all input coubs exist after execution (i.e. some downloads failed)
# 5 -> termination was requested mid-way by the user (i.e. Ctrl+C)
missing_dep = 1
err_option = 2
err_runtime = 3
err_download = 4
user_interrupt = 5

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Default Settings
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

class Options_Assembler:
    """
    Handles all actions regarding user options.

    -) assigns default options
    -) parses command line options
    -) checks for invalid user input
    """
    def __init__(self):
        """Parse command line arguments"""

        # Change verbosity of the script
        # 0 for quiet, >= 1 for normal verbosity
        self.verbosity = 1

        # Allowed values: yes, no, prompt
        self.prompt_answer = "prompt"

        # Default download destination
        self.save_path = "."

        # Keep individual video/audio streams
        self.keep = False

        # How often to loop the video
        # If longer than audio duration -> audio decides length
        self.repeat = 1000

        # What video/audio quality to download
        #  0 -> worst quality
        # -1 -> best quality
        # Everything else can lead to undefined behavior
        self.v_quality = -1
        self.a_quality = -1

        # Download reposts during channel downloads
        self.recoubs = True

        # ONLY download reposts during channel downloads
        self.only_recoubs = False

        # Show preview after each download with the given command
        self.preview = False
        self.preview_command = "mpv"

        # Only download video/audio stream
        # Can't be both true!
        self.a_only = False
        self.v_only = False

        # Default sort order
        self.sort_order = "newest"

        # Advanced settings
        self.page_limit = 99           # used for tags; must be <= 99
        self.entries_per_page = 25     # allowed: 1-25
        self.concat_list = "list.txt"
        self.tag_separator = "_"

        # Don't touch these
        self.input_links = []
        self.input_lists = []
        self.input_channels = []
        self.input_tags = []
        self.input_searches = []

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def parse_options(self):
        """Parse command line options"""

        with_argument = ["-l", "--list",
                         "-c", "--channel",
                         "-t", "--tag",
                         "-e", "--search",
                         "-p", "--path",
                         "-r", "--repeat",
                         "-d", "--duration",
                         "--sleep",
                         "--limit-num",
                         "--sort",
                         "--preview",
                         "--write-list",
                         "--use-archive",
                         "-o", "--output"]

        position = 1
        while position < len(sys.argv):
            option = sys.argv[position]
            if option in with_argument:
                try:
                    argument = sys.argv[position+1]
                except IndexError:
                    err("Missing value for ", option, "!", sep="")
                    sys.exit(err_option)

            try:
                # Input
                if fnmatch(option, "*coub.com/view/*"):
                    self.input_links.append(option.strip("/"))
                elif option in ("-l", "--list"):
                    if os.path.exists(argument):
                        self.input_lists.append(os.path.abspath(argument))
                    else:
                        err("'", argument, "' is no valid list.", sep="")
                elif option in ("-c", "--channel"):
                    self.input_channels.append(argument.strip("/"))
                elif option in ("-t", "--tag"):
                    self.input_tags.append(argument.strip("/"))
                elif option in ("-e", "--search"):
                    self.input_searches.append(argument.strip("/"))
                # Common options
                elif option in ("-h", "--help"):
                    usage()
                    sys.exit(0)
                elif option in ("-q", "--quiet"):
                    self.verbosity = 0
                elif option in ("-y", "--yes"):
                    self.prompt_answer = "yes"
                elif option in ("-n", "--no"):
                    self.prompt_answer = "no"
                elif option in ("-s", "--short"):
                    self.repeat = 1
                elif option in ("-p", "--path"):
                    self.save_path = argument
                elif option in ("-k", "--keep"):
                    self.keep = True
                elif option in ("-r", "--repeat"):
                    self.repeat = int(argument)
                elif option in ("-d", "--duration"):
                    self.duration = argument
                # Download options
                elif option == "--sleep":
                    self.sleep_dur = float(argument)
                elif option == "--limit-num":
                    self.max_coubs = int(argument)
                elif option == "--sort":
                    self.sort_order = argument
                # Format selection
                elif option == "--bestvideo":
                    self.v_quality = -1
                elif option == "--worstvideo":
                    self.v_quality = 0
                elif option == "--bestaudio":
                    self.a_quality = -1
                elif option == "--worstaudio":
                    self.a_quality = 0
                # Channel options
                elif option == "--recoubs":
                    self.recoubs = True
                elif option == "--no-recoubs":
                    self.recoubs = False
                elif option == "--only-recoubs":
                    self.only_recoubs = True
                # Preview options
                elif option == "--preview":
                    self.preview = True
                    self.preview_command = argument
                elif option == "--no-preview":
                    self.preview = False
                # Misc options
                elif option == "--audio-only":
                    self.a_only = True
                elif option == "--video-only":
                    self.v_only = True
                elif option == "--write-list":
                    self.out_file = os.path.abspath(argument)
                elif option == "--use-archive":
                    self.archive_file = os.path.abspath(argument)
                # Output
                elif option in ("-o", "--output"):
                    self.out_format = argument
                elif fnmatch(option, "-*"):
                    err("Unknown flag '", option, "'!", sep="")
                    err("Try '", os.path.basename(sys.argv[0]), \
                        " --help' for more information.", sep="")
                    sys.exit(err_option)
                else:
                    err("'", option, "' is neither an option nor a coub link!", sep="")
                    err("Try '", os.path.basename(sys.argv[0]), \
                        " --help' for more information.", sep="")
                    sys.exit(err_option)
            except ValueError:
                err("Invalid ", option, " ('", argument, "')!", sep="")
                sys.exit(err_option)

            if option in with_argument:
                position += 2
            else:
                position += 1

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def check_options(self):
        """Check validity of command line options"""

        if self.repeat <= 0:
            err("-r/--repeat must be greater than 0!")
            sys.exit(err_option)
        elif hasattr(self, "max_coubs") and self.max_coubs <= 0:
            err("--limit-num must be greater than zero!")
            sys.exit(err_option)

        if hasattr(self, "duration"):
            command = ["ffmpeg", "-v", "quiet",
                       "-f", "lavfi", "-i", "anullsrc",
                       "-t", self.duration, "-c", "copy",
                       "-f", "null", "-"]
            try:
                subprocess.check_call(command)
            except subprocess.CalledProcessError:
                err("Invalid duration! For the supported syntax see:")
                err("https://ffmpeg.org/ffmpeg-utils.html#time-duration-syntax")
                sys.exit(err_option)

        if self.a_only and self.v_only:
            err("--audio-only and --video-only are mutually exclusive!")
            sys.exit(err_option)
        elif not self.recoubs and self.only_recoubs:
            err("--no-recoubs and --only-recoubs are mutually exclusive!")
            sys.exit(err_option)

        allowed_sort = ["newest",
                        "oldest",
                        "newest_popular",
                        "likes_count",
                        "views_count"]
        if self.sort_order not in allowed_sort:
            err("Invalid sort order ('", self.sort_order, "')!", sep="")
            sys.exit(err_option)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Functions
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def err(*args, **kwargs):
    """Print to stderr"""
    print(*args, file=sys.stderr, **kwargs)

def msg(*args, **kwargs):
    """Print to stdout based on verbosity level"""
    if options.verbosity >= 1:
        print(*args, **kwargs)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def usage():
    """Print help text"""

    print(
'''CoubDownloader is a simple download script for coub.com

Usage: coub.py [OPTIONS] INPUT [INPUT]...

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
    This option has no influence on the file extension.'''
    )

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def check_requirements():
    """check existence of required software"""

    try:
        subprocess.run(["ffmpeg"], stdout=subprocess.DEVNULL, \
                                   stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        err("Error: FFmpeg not found!")
        sys.exit(missing_dep)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def resolve_paths():
    """Handle output path"""

    if not os.path.exists(options.save_path):
        os.mkdir(options.save_path)
    os.chdir(options.save_path)

    if os.path.exists(options.concat_list):
        err("Error: Reserved filename ('", options.concat_list, "') " \
            "exists in '", options.save_path, "'!", sep="")
        sys.exit(err_runtime)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def parse_input_links():
    """Parse direct input links from the command line"""

    for link in options.input_links:
        if hasattr(options, "max_coubs") and \
           len(coub_list) >= options.max_coubs:
            break
        coub_list.append(link)

    if options.input_links:
        msg("Reading command line:")
        msg("  ", len(options.input_links), " link(s) found", sep="")

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def parse_input_list(in_list):
    """Parse coub links from input lists"""

    msg("Reading input list (", in_list, "):", sep="")

    with open(in_list, "r") as f:
        link_list = f.read()

    # Replace tabs and spaces with newlines
    # Emulates default wordsplitting in Bash
    link_list = link_list.replace("\t", "\n")
    link_list = link_list.replace(" ", "\n")
    link_list = link_list.splitlines()

    for link in link_list:
        if hasattr(options, "max_coubs") and \
           len(coub_list) >= options.max_coubs:
            break
        coub_list.append(link)

    msg("  ", len(link_list), " link(s) found", sep="")

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def parse_input_timeline(url_type, url):
    """
    Parse coub links from various Coub source

    Currently supports
    -) channels
    -) tags
    -) coub searches
    """

    if url_type == "channel":
        channel_id = url.split("/")[-1]
        api_call = "https://coub.com/api/v2/timeline/channel/" + channel_id
        api_call += "?"
    elif url_type == "tag":
        tag_id = url.split("/")[-1]
        tag_id = urllib.parse.quote(tag_id)
        api_call = "https://coub.com/api/v2/timeline/tag/" + tag_id
        api_call += "?"
    elif url_type == "search":
        search_term = url.split("=")[-1]
        search_term = urllib.parse.quote(search_term)
        api_call = "https://coub.com/api/v2/search/coubs?q=" + search_term
        api_call += "&"
    else:
        err("Error: Unknown input type in parse_input_timeline!")
        clean()
        sys.exit(err_runtime)

    api_call += "per_page=" + str(options.entries_per_page)

    if options.sort_order == "oldest" and url_type in ("tag", "search"):
        api_call += "&order_by=oldest"
    # Don't do anything for newest (as it's the default)
    # check_options already got rid of invalid values
    elif options.sort_order != "newest":
        api_call += "&order_by=" + options.sort_order

    page_json = urllib.request.urlopen(api_call).read()
    page_json = json.loads(page_json)

    total_pages = page_json['total_pages']

    msg("Downloading ", url_type, " info (", url, "):", sep="")

    for page in range(1, total_pages+1):
        # tag timeline redirects pages >99 to page 1
        # channel timelines work like intended
        if url_type == "tag" and page > options.page_limit:
            msg("  Max. page limit reached!")
            return

        msg("  ", page, " out of ", total_pages, " pages", sep="")
        page_json = urllib.request.urlopen(api_call + "&page=" + str(page)).read()
        page_json = json.loads(page_json)

        for entry in range(options.entries_per_page):
            if hasattr(options, "max_coubs") and \
               len(coub_list) >= options.max_coubs:
                return

            try:
                coub_id = page_json['coubs'][entry]['recoub_to']['permalink']
                if not options.recoubs:
                    continue
                coub_list.append("https://coub.com/view/" + coub_id)
            except (TypeError, KeyError, IndexError):
                if options.only_recoubs:
                    continue
                try:
                    coub_id = page_json['coubs'][entry]['permalink']
                    coub_list.append("https://coub.com/view/" + coub_id)
                except (TypeError, KeyError, IndexError):
                    continue


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def parse_input():
    """Parse coub links from all available sources"""

    parse_input_links()
    for in_list in options.input_lists:
        parse_input_list(in_list)
    for channel in options.input_channels:
        parse_input_timeline("channel", channel)
    for tag in options.input_tags:
        parse_input_timeline("tag", tag)
    for search in options.input_searches:
        parse_input_timeline("search", search)

    if not coub_list:
        err("Error: No coub links specified!")
        clean()
        sys.exit(err_option)

    if hasattr(options, "max_coubs") and \
       len(coub_list) >= options.max_coubs:
        msg("\nDownload limit (", options.max_coubs, ") reached!", sep="")

    if hasattr(options, "out_file"):
        with open(options.out_file, "w") as f:
            for link in coub_list:
                print(link, file=f)
        msg("\nParsed coubs written to '", options.out_file, "'!", sep="")
        clean()
        sys.exit(0)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def get_out_name(coub_json, coub_id):
    """Decide filename for output file"""

    if not hasattr(options, "out_format"):
        return coub_id

    out_name = options.out_format

    out_name = out_name.replace("%id%", coub_id)
    out_name = out_name.replace("%title%", coub_json['title'])
    out_name = out_name.replace("%creation%", coub_json['created_at'])
    out_name = out_name.replace("%channel%", coub_json['channel']['title'])
    # Coubs don't necessarily have a category
    try:
        out_name = out_name.replace("%category%", coub_json['categories'][0]['permalink'])
    except (KeyError, TypeError):
        out_name = out_name.replace("%category%", "")

    tags = ""
    for tag in coub_json['tags']:
        tags += tag['title'] + options.tag_separator
    out_name = out_name.replace("%tags%", tags)

    # Strip/replace special characters that can lead to script failure (ffmpeg concat)
    # ' common among coub titles
    # Newlines can be occasionally found as well
    out_name = out_name.replace("'", "")
    out_name = out_name.replace("\n", " ")

    try:
        f = open(out_name, "w")
        f.close()
        os.remove(out_name)
    except OSError:
        err("Error: Filename invalid or too long! ", end="")
        err("Falling back to '", coub_id, "'.", sep="")
        out_name = coub_id

    return out_name

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def existence(name):
    """Check if a coub with given name already exists"""

    if (os.path.exists(name + ".mkv") \
            and not options.a_only and not options.v_only) or \
       (os.path.exists(name + ".mp4") and options.v_only) or \
       (os.path.exists(name + ".mp3") and options.a_only):
        return True

    return False

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def overwrite():
    """Decide if existing coub should be overwritten"""

    if options.prompt_answer == "yes":
        return True
    elif options.prompt_answer == "no":
        return False
    elif options.prompt_answer == "prompt":
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
        clean()
        sys.exit(err_runtime)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def use_archive(action, coub_id):
    """
    Handles all actions regarding archive usage

    Supported actions:
    -) read
    -) write
    """

    if action == "read":
        if not os.path.exists(options.archive_file):
            return False
        with open(options.archive_file, "r") as f:
            archive = f.readlines()
        for line in archive:
            if line == coub_id + "\n":
                return True
        return False
    elif action == "write":
        with open(options.archive_file, "a") as f:
            print(coub_id, file=f)
    else:
        err("Error: Unknown action in use_archive!")
        clean()
        sys.exit(err_runtime)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def download(data, name):
    """Download individual video/audio streams of a coub"""

    video = []
    audio = []
    v_size = 0
    a_size = 0

    for quality in ["low", "med", "high"]:
        try:
            v_size = data['file_versions']['html5']['video'][quality]['size']
        except KeyError:
            v_size = 0
        try:
            a_size = data['file_versions']['html5']['audio'][quality]['size']
        except KeyError:
            a_size = 0

        # v_size/a_size can be 0 OR None in case of a missing stream
        # None is the exception and an irregularity in the Coub API
        if v_size:
            video.append(data['file_versions']['html5']['video'][quality]['url'])
        if a_size:
            audio.append(data['file_versions']['html5']['audio'][quality]['url'])

    if not options.a_only:
        try:
            urllib.request.urlretrieve(video[options.v_quality], name + ".mp4")
        except (IndexError, urllib.error.HTTPError):
            err("Error: Coub unavailable!")
            raise

    if not options.v_only:
        try:
            urllib.request.urlretrieve(audio[options.a_quality], name + ".mp3")
        except (IndexError, urllib.error.HTTPError):
            if options.a_only:
                err("Error: Audio or coub unavailable!")
                raise

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def merge(name):
    """Merge video/audio stream with ffmpeg and loop video"""

    # Print .txt for ffmpeg's concat
    with open(options.concat_list, "w") as f:
        for i in range(options.repeat):
            print("file '" + name + ".mp4'", file=f)

    # Loop footage until shortest stream ends
    # Concatenated video (via list) counts as one long stream
    command = ["ffmpeg", "-y", "-v", "error",
               "-f", "concat", "-safe", "0",
               "-i", options.concat_list, "-i", name + ".mp3"]

    if hasattr(options, "duration"):
        command.extend(["-t", options.duration])

    command.extend(["-c", "copy", "-shortest", name + ".mkv"])

    subprocess.run(command)

    if not options.keep:
        os.remove(name + ".mp4")
        os.remove(name + ".mp3")

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def show_preview(name):
    """Play finished coub with the given command"""

    # For normal downloads .mkv, unless error downloading audio
    if os.path.exists(name + ".mkv"):
        extension = ".mkv"
    else:
        extension = ".mp4"
    if options.a_only:
        extension = ".mp3"
    if options.v_only:
        extension = ".mp4"

    try:
        command = options.preview_command.split(" ")
        command.append(name + extension)
        subprocess.check_call(command, stdout=subprocess.DEVNULL, \
                                       stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        err("Error: Missing file, invalid command or user interrupt in show_preview!")
        raise

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def clean():
    """Clean workspace"""

    if os.path.exists(options.concat_list):
        os.remove(options.concat_list)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Main Function
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def main():
    """Main function body"""
    global options

    check_requirements()

    options = Options_Assembler()
    options.parse_options()
    options.check_options()

    resolve_paths()

    msg("\n### Parse Input ###\n")
    parse_input()

    msg("\n### Download Coubs ###\n")
    counter = 0
    downloads = 0
    for coub in coub_list:
        counter += 1
        msg("  ", counter, " out of ", len(coub_list), " (", coub, ")", sep="")

        coub_id = coub.split("/")[-1]

        # Pass existing files to avoid unnecessary downloads
        # This check handles archive file search and default output formatting
        # Avoids json request (slow!) just to skip files anyway
        if (hasattr(options, "archive_file") and use_archive("read", coub_id)) or \
           (not hasattr(options, "out_format") \
                and existence(coub_id) and not overwrite()):
            msg("Already downloaded!")
            clean()
            continue

        api_call = "https://coub.com/api/v2/coubs/" + coub_id
        try:
            coub_json = urllib.request.urlopen(api_call).read()
        except urllib.error.HTTPError:
            err("Error: Coub unavailable!")
            continue
        coub_json = json.loads(coub_json)

        out_name = get_out_name(coub_json, coub_id)

        # Another check for custom output formatting
        # Far slower to skip existing files (archive usage is recommended)
        if hasattr(options, "out_format") and existence(out_name) and not overwrite():
            msg("Already downloaded!")
            clean()
            downloads += 1
            continue

        if hasattr(options, "sleep_dur") and counter > 1:
            time.sleep(options.sleep_dur)
        # Download video/audio streams
        # Skip if the requested media couldn't be downloaded
        try:
            download(coub_json, out_name)
        except (IndexError, urllib.error.HTTPError):
            continue

        # Fix broken video stream
        if not options.a_only:
            with open(out_name + ".mp4", "r+b") as f:
                temp = f.read()
            with open(out_name + ".mp4", "w+b") as f:
                f.write(b'\x00\x00' + temp[2:])

        # Merge video and audio
        if not options.v_only and not options.a_only and \
           os.path.exists(out_name + ".mp3"):
            merge(out_name)

        # Write downloaded coub to archive
        if hasattr(options, "archive_file"):
            use_archive("write", coub_id)

        # Preview downloaded coub
        if options.preview:
            try:
                show_preview(out_name)
            except subprocess.CalledProcessError:
                pass

        # Clean workspace
        clean()

        # Record successful download
        downloads += 1

    msg("\n### Finished ###\n")

    # Indicate failure, if not all input coubs exist after execution
    if downloads < counter:
        sys.exit(err_download)

# Execute main function
if len(sys.argv) == 1:
    usage()
    sys.exit(0)
try:
    main()
except KeyboardInterrupt:
    err("User Interrupt!")
    clean()
    sys.exit(user_interrupt)
sys.exit(0)
