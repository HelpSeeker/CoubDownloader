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
# Default Settings
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Change verbosity of the script
# 0 for quiet, >= 1 for normal verbosity
verbosity = 1

# Allowed values: yes, no, prompt
prompt_answer = "prompt"

# Default download destination
save_path = "."

# Keep individual video/audio streams
keep = False

# How often to loop the video
# If longer than audio duration -> audio decides length
repeat = 1000

# What video/audio quality to download
#  0 -> worst quality
# -1 -> best quality
# Everything else can lead to undefined behavior
v_quality = -1
a_quality = -1

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

# Default sort order
sort_order = "newest"

# Advanced settings
page_limit = 99           # used for tags; must be <= 99
entries_per_page = 25     # allowed: 1-25
concat_list = "list.txt"
tag_separator = "_"

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

# Don't touch these
input_links = []
input_lists = []
input_channels = []
input_tags = []
input_searches = []
coub_list = []

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Functions
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def err(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

def msg(*args, **kwargs):
    if verbosity >= 1:
        print(*args, **kwargs)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def usage():
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
    try:
        subprocess.run(["ffmpeg"], stdout=subprocess.DEVNULL, \
                                   stderr=subprocess.DEVNULL)
    except KeyboardInterrupt:
        raise
    except:
        err("Error: FFmpeg not found!")
        sys.exit(missing_dep)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Parse command line options
# I prefer manual parsing of input arguments
def parse_options():
    global verbosity
    global prompt_answer
    global save_path
    global keep
    global repeat
    global sort_order
    global v_quality, a_quality
    global recoubs, only_recoubs
    global preview, preview_command
    global a_only, v_only

    position = 1
    while position < len(sys.argv):
        option = sys.argv[position]
        # Input
        if fnmatch(option, "*coub.com/view/*"):
            input_links.append(option.strip("/"))
            position += 1
        elif option in ("-l", "--list"):
            l = sys.argv[position+1]
            if os.path.exists(l):
                input_lists.append(os.path.abspath(l))
            else:
                err("'", l, "' is no valid list.", sep="")
            position += 2
        elif option in ("-c", "--channel"):
            input_channels.append(sys.argv[position+1].strip("/"))
            position += 2
        elif option in ("-t", "--tag"):
            input_tags.append(sys.argv[position+1].strip("/"))
            position += 2
        elif option in ("-e", "--search"):
            input_searches.append(sys.argv[position+1].strip("/"))
            position += 2
        # Common options
        elif option in ("-h", "--help"):
            usage()
            sys.exit(0)
        elif option in ("-q", "--quiet"):
            verbosity = 0
            position += 1
        elif option in ("-y", "--yes"):
            prompt_answer = "yes"
            position += 1
        elif option in ("-n", "--no"):
            prompt_answer = "no"
            position += 1
        elif option in ("-s", "--short"):
            repeat = 1
            position += 1
        elif option in ("-p", "--path"):
            save_path = sys.argv[position+1]
            position += 2
        elif option in ("-k", "--keep"):
            keep = True
            position += 1
        elif option in ("-r", "--repeat"):
            repeat = int(sys.argv[position+1])
            position += 2
        elif option in ("-d", "--duration"):
            global duration
            duration = sys.argv[position+1]
            position += 2
        # Download options
        elif option == "--sleep":
            global sleep_dur
            sleep_dur = float(sys.argv[position+1])
            position += 2
        elif option == "--limit-num":
            global max_coubs
            max_coubs = int(sys.argv[position+1])
            position += 2
        elif option == "--sort":
            sort_order = sys.argv[position+1]
            position += 2
        # Format selection
        elif option == "--bestvideo":
            v_quality = -1
            position += 1
        elif option == "--worstvideo":
            v_quality = 0
            position += 1
        elif option == "--bestaudio":
            a_quality = -1
            position += 1
        elif option == "--worstaudio":
            a_quality = 0
            position += 1
        # Channel options
        elif option == "--recoubs":
            recoubs = True
            position += 1
        elif option == "--no-recoubs":
            recoubs = False
            position += 1
        elif option == "--only-recoubs":
            only_recoubs = True
            position += 1
        # Preview options
        elif option == "--preview":
            preview = True
            preview_command = sys.argv[position+1]
            position += 2
        elif option == "--no-preview":
            preview = False
            position += 1
        # Misc options
        elif option == "--audio-only":
            a_only = True
            position += 1
        elif option == "--video-only":
            v_only = True
            position += 1
        elif option == "--write-list":
            global out_file
            out_file = os.path.abspath(sys.argv[position+1])
            position += 2
        elif option == "--use-archive":
            global archive_file
            archive_file = os.path.abspath(sys.argv[position+1])
            position += 2
        # Output
        elif option in ("-o", "--output"):
            global out_format
            out_format = sys.argv[position+1]
            position += 2
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

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def check_options():
    if repeat <= 0:
        err("-r/--repeat must be greater than 0!")
        sys.exit(err_option)
    elif "max_coubs" in globals() and max_coubs <= 0:
        err("--limit-num must be greater than zero!")
        sys.exit(err_option)

    if "duration" in globals():
        command = ["ffmpeg", "-v", "quiet",
                   "-f", "lavfi", "-i", "anullsrc",
                   "-t", duration, "-c", "copy",
                   "-f", "null", "-"]
        try:
            subprocess.check_call(command)
        except KeyboardInterrupt:
            raise
        except subprocess.CalledProcessError:
            err("Invalid duration! For the supported syntax see:")
            err("https://ffmpeg.org/ffmpeg-utils.html#time-duration-syntax")
            sys.exit(err_option)

    if a_only and v_only:
        err("--audio-only and --video-only are mutually exclusive!")
        sys.exit(err_option)
    elif not recoubs and only_recoubs:
        err("--no-recoubs and --only-recoubs are mutually exclusive!")
        sys.exit(err_option)

    allowed_sort = ["newest",
                    "oldest",
                    "newest_popular",
                    "likes_count",
                    "views_count"]
    if sort_order not in allowed_sort:
        err("Invalid sort order ('", sort_order, "')!", sep="")
        sys.exit(err_option)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def resolve_paths():
    if not os.path.exists(save_path):
        os.mkdir(save_path)
    os.chdir(save_path)

    if os.path.exists(concat_list):
        err("Error: Reserved filename ('", concat_list, "') " \
            "exists in '", save_path, "'!", sep="")
        sys.exit(err_runtime)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def parse_input_links():
    for link in input_links:
        if "max_coubs" in globals() and len(coub_list) >= max_coubs:
            break
        coub_list.append(link)

    if input_links:
        msg("Reading command line:")
        msg("  ", len(input_links), " link(s) found", sep="")

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def parse_input_list(in_list):
    msg("Reading input list (", in_list, "):", sep="")

    with open(in_list, "r") as f:
        link_list = f.read()

    # Replace tabs and spaces with newlines
    # Emulates default wordsplitting in Bash
    link_list = link_list.replace("\t", "\n")
    link_list = link_list.replace(" ", "\n")
    link_list = link_list.splitlines()

    for link in link_list:
        if "max_coubs" in globals() and len(coub_list) >= max_coubs:
            break
        coub_list.append(link)

    msg("  ", len(link_list), " link(s) found", sep="")

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def parse_input_timeline(url_type, url):
    if url_type == "channel":
        channel_id = url.split("/")[-1]
        api_call = "https://coub.com/api/v2/timeline/channel/" + channel_id
        api_call += "?"
    elif url_type == "tag":
        tag_id = url.split("/")[-1]
        api_call = "https://coub.com/api/v2/timeline/tag/" + tag_id
        api_call += "?"
    elif url_type == "search":
        search_term = url.split("=")[-1]
        api_call = "https://coub.com/api/v2/search/coubs?q=" + search_term
        api_call += "&"
    else:
        err("Error: Unknown input type in parse_input_timeline!")
        clean()
        sys.exit(err_runtime)

    api_call += "per_page=" + str(entries_per_page)

    if sort_order == "oldest" and url_type in ("tag", "search"):
        api_call += "&order_by=oldest"
    # Don't do anything for newest (as it's the default)
    # check_options already got rid of invalid values
    elif sort_order != "newest":
        api_call += "&order_by=" + sort_order

    page_json = urllib.request.urlopen(api_call).read()
    page_json = json.loads(page_json)

    total_pages = page_json['total_pages']

    msg("Downloading ", url_type, " info (", url, "):", sep="")

    for page in range(1, total_pages+1):
        # tag timeline redirects pages >99 to page 1
        # channel timelines work like intended
        if url_type == "tag" and page > page_limit:
            msg("  Max. page limit reached!")
            return

        msg("  ", page, " out of ", total_pages, " pages", sep="")
        page_json = urllib.request.urlopen(api_call + "&page=" + str(page)).read()
        page_json = json.loads(page_json)

        for entry in range(entries_per_page):
            if "max_coubs" in globals() and len(coub_list) >= max_coubs:
                return

            try:
                coub_id = page_json['coubs'][entry]['recoub_to']['permalink']
                if not recoubs:
                    continue
                coub_list.append("https://coub.com/view/" + coub_id)
            except KeyboardInterrupt:
                raise
            except:
                if only_recoubs:
                    continue
                try:
                    coub_id = page_json['coubs'][entry]['permalink']
                    coub_list.append("https://coub.com/view/" + coub_id)
                except KeyboardInterrupt:
                    raise
                except:
                    continue


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def parse_input():
    parse_input_links()
    for in_list in input_lists:
        parse_input_list(in_list)
    for channel in input_channels:
        parse_input_timeline("channel", channel)
    for tag in input_tags:
        parse_input_timeline("tag", tag)
    for search in input_searches:
        parse_input_timeline("search", search)

    if not coub_list:
        err("Error: No coub links specified!")
        clean()
        sys.exit(err_option)

    if "max_coubs" in globals() and len(coub_list) >= max_coubs:
        msg("\nDownload limit (", max_coubs, ") reached!", sep="")

    if "out_file" in globals():
        with open(out_file, "w") as f:
            for link in coub_list:
                print(link, file=f)
        msg("\nParsed coubs written to '", out_file, "'!", sep="")
        clean()
        sys.exit(0)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def get_out_name(coub_json, coub_id):
    if not "out_format" in globals():
        return coub_id

    out_name = out_format

    out_name = out_name.replace("%id%", coub_id)
    out_name = out_name.replace("%title%", coub_json['title'])
    out_name = out_name.replace("%creation%", coub_json['created_at'])
    out_name = out_name.replace("%channel%", coub_json['channel']['title'])
    # Coubs don't necessarily have a category
    try:
        out_name = out_name.replace("%category%", coub_json['categories'][0]['permalink'])
    except:
        out_name = out_name.replace("%category%", "")

    tags = ""
    for tag in coub_json['tags']:
        tags += tag['title'] + tag_separator
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
    except KeyboardInterrupt:
        raise
    except:
        err("Error: Filename invalid or too long! ", end="")
        err("Falling back to '", coub_id, "'.", sep="")
        out_name = coub_id

    return out_name

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def existence(name):
    if (os.path.exists(name + ".mkv") and not a_only and not v_only) or \
       (os.path.exists(name + ".mp4") and v_only) or \
       (os.path.exists(name + ".mp3") and a_only):
        return True

    return False

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def overwrite():
    if prompt_answer == "yes":
        return True
    elif prompt_answer == "no":
        return False
    elif prompt_answer == "prompt":
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
    if action == "read":
        if not os.path.exists(archive_file):
            return False
        with open(archive_file, "r") as f:
            archive = f.readlines()
        for line in archive:
            if line == coub_id + "\n":
                return True
        return False
    elif action == "write":
        with open(archive_file, "a") as f:
            print(coub_id, file=f)
    else:
        err("Error: Unknown action in use_archive!")
        clean()
        sys.exit(err_runtime)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def download(data, name):
    video = []
    audio = []
    v_size = 0
    a_size = 0

    for quality in ["low", "med", "high"]:
        try:
            v_size = data['file_versions']['html5']['video'][quality]['size']
        except KeyboardInterrupt:
            raise
        except:
            pass
        try:
            a_size = data['file_versions']['html5']['audio'][quality]['size']
        except KeyboardInterrupt:
            raise
        except:
            pass

        if v_size > 0:
            video.append(data['file_versions']['html5']['video'][quality]['url'])
        if a_size > 0:
            audio.append(data['file_versions']['html5']['audio'][quality]['url'])

    if not a_only:
        try:
            urllib.request.urlretrieve(video[v_quality], name + ".mp4")
            # Fix broken video stream
            # Done in downloads to avoid unncessary read() of whole file
        except KeyboardInterrupt:
            raise
        except:
            err("Error: Coub unavailable!")
            raise

    if not v_only:
        try:
            urllib.request.urlretrieve(audio[a_quality], name + ".mp3")
        except KeyboardInterrupt:
            raise
        except:
            if a_only:
                err("Error: Audio or coub unavailable!")
                raise

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def merge(name):
    # Print .txt for ffmpeg's concat
    with open(concat_list, "w") as f:
        for i in range(repeat):
            print("file '" + name + ".mp4'", file=f)

    # Loop footage until shortest stream ends
    # Concatenated video (via list) counts as one long stream
    command = ["ffmpeg", "-y", "-v", "error",
               "-f", "concat", "-safe", "0",
               "-i", concat_list, "-i", name + ".mp3"]

    if "duration" in globals():
        command.extend(["-t", duration])

    command.extend(["-c", "copy", "-shortest", name + ".mkv"])

    subprocess.run(command)

    if not keep:
        os.remove(name + ".mp4")
        os.remove(name + ".mp3")

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def show_preview(name):
    # For normal downloads .mkv, unless error downloading audio
    if os.path.exists(name + ".mkv"):
        extension = ".mkv"
    else:
        extension = ".mp4"
    if a_only:
        extension = ".mp3"
    if v_only:
        extension = ".mp4"

    try:
        command = preview_command.split(" ")
        command.append(name + extension)
        subprocess.run(command, stdout=subprocess.DEVNULL, \
                                stderr=subprocess.DEVNULL)
    except KeyboardInterrupt:
        raise
    except:
        err("Error: Missing file in show_preview or invalid preview command!")
        raise

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def clean():
    if os.path.exists(concat_list):
        os.remove(concat_list)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Main Function
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def main():
    check_requirements()
    parse_options()
    check_options()
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
        if ("archive_file" in globals() and use_archive("read", coub_id)) or \
           (out_format not in globals() and existence(coub_id) and not overwrite()):
            msg("Already downloaded!")
            clean()
            continue

        api_call = "https://coub.com/api/v2/coubs/" + coub_id
        try:
            coub_json = urllib.request.urlopen(api_call).read()
        except KeyboardInterrupt:
            raise
        except:
            err("Error: Coub unavailable!")
            continue
        coub_json = json.loads(coub_json)

        out_name = get_out_name(coub_json, coub_id)

        # Another check for custom output formatting
        # Far slower to skip existing files (archive usage is recommended)
        if "out_format" in globals() and existence(out_name) and not overwrite():
            msg("Already downloaded!")
            clean()
            downloads += 1
            continue

        if "sleep_dur" in globals() and counter > 1:
            time.sleep(sleep_dur)
        # Download video/audio streams
        # Skip if the requested media couldn't be downloaded
        try:
            download(coub_json, out_name)
        except KeyboardInterrupt:
            raise
        except:
            continue

        # Fix broken video stream
        if not a_only:
            with open(out_name + ".mp4", "r+b") as f:
                temp = f.read()
            with open(out_name + ".mp4", "w+b") as f:
                f.write(b'\x00\x00' + temp[2:])

        # Merge video and audio
        if not v_only and not a_only and os.path.exists(out_name + ".mp3"):
            merge(out_name)

        # Write downloaded coub to archive
        if "archive_file" in globals():
            use_archive("write", coub_id)

        # Preview downloaded coub
        if preview:
            try:
                show_preview(out_name)
            except KeyboardInterrupt:
                raise
            except:
                continue

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
