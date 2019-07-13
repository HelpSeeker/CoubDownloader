import sys
import os
import time
import json
import urllib.request
import subprocess
from fnmatch import fnmatch

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

# Show preview after each download with the given command
preview = False
preview_command = "mpv"

# Only download video/audio stream
# Can't be both true!
a_only = False
v_only = False

# Advanced settings
concat_list = "list.txt"

# Don't touch these
input_links=[]
coub_list=[]

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Functions
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def err(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

def msg(*args, **kwargs):
    if verbosity >= 1: print(*args, **kwargs)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def usage():
    print(
'''CoubDownloader is a simple download script for coub.com

Usage: coub.py [OPTIONS] INPUT [INPUT]...

Input:
  LINK                   download specified coubs

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

Preview options:
  --preview COMMAND      play finished coub via the given command
  --no-preview           explicitly disable coub preview

Misc. options:
  --audio-only           only download audio streams
  --video-only           only download video streams
  --write-list FILE      write all parsed coub links to FILE
  --use-archive FILE     use FILE to keep track of already downloaded coubs'''
    )

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def check_requirements():
    try:
        subprocess.run(["ffmpeg"], stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL)
    except:
        err("Error: FFmpeg not found!")
        exit()

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Parse command line options
# I prefer manual parsing of input arguments
def parse_options():
    global verbosity
    global prompt_answer
    global save_path
    global keep
    global repeat
    global preview, preview_command
    global a_only, v_only

    position = 1
    while position < len(sys.argv):
        option = sys.argv[position]
        if option == "-h" or option == "--help":
            usage()
            exit()
        elif option == "-q" or option == "--quiet":
            verbosity = 0
            position += 1
        elif option == "-y" or option == "--yes":
            prompt_answer = "yes"
            position += 1
        elif option == "-n" or option == "--no":
            prompt_answer = "no"
            position += 1
        elif option == "-s" or option == "--short":
            repeat = 1
            position += 1
        elif option == "-p" or option == "--path":
            save_path = sys.argv[position+1]
            position += 2
        elif option == "-k" or option == "--keep":
            keep = True
            position += 1
        elif option == "-r" or option == "--repeat":
            repeat = int(sys.argv[position+1])
            position += 2
        elif option == "-d" or option == "--duration":
            global duration
            duration = sys.argv[position+1]
            position += 2
        elif option == "--sleep":
            global sleep_dur
            sleep_dur = float(sys.argv[position+1])
            position += 2
        elif option == "--limit-num":
            global max_coubs
            max_coubs = int(sys.argv[position+1])
            position += 2
        elif option == "--preview":
            preview = True
            preview_command = sys.argv[position+1]
            position += 2
        elif option == "--no-preview":
            preview = False
            position += 1
        elif option == "--audio-only":
            a_only == True
            position += 1
        elif option == "--video-only":
            v_only == True
            position += 1
        elif option == "--write-list":
            global out_file
            out_file = sys.argv[position+1]
            position += 2
        elif option == "--use-archive":
            global archive_file
            archive_file = sys.argv[position+1]
            position += 2
        elif fnmatch(option, "*coub.com/view/*"):
            input_links.append(option)
            position += 1
        elif fnmatch(option, "-*"):
            msg("Unknown flag '", option, "'!", sep="")
            usage()
            exit()
        else:
            msg("'", option, "' is not an option or a coub link!", sep="")
            usage()
            exit()

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def check_options():
    if repeat <= 0:
        err("-r/--repeat must be greater than 0!")
        exit()
    elif "max_coubs" in globals() and max_coubs <= 0:
        err("--limit-num must be greater than zero!")
        exit()

    if "duration" in globals():
        command = ["ffmpeg", "-v", "quiet",
                   "-f", "lavfi", "-i", "anullsrc",
                   "-t", duration, "-c", "copy",
                   "-f", "null", "-"]
        try:
            subprocess.check_call(command)
        except subprocess.CalledProcessError:
            err("Invalid duration! For the supported syntax see:")
            err("https://ffmpeg.org/ffmpeg-utils.html#time-duration-syntax")
            exit()

    if a_only and v_only:
        err("--audio-only and --video-only are mutually exclusive!")
        exit()

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def resolve_paths():
    if not os.path.exists(save_path):
        os.mkdir(save_path)
    os.chdir(save_path)

    if os.path.exists(concat_list):
        err("Error: Reserved filename ('", concat_list, "') "
              "exists in '", save_path, "'!", sep="")
        exit()

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def parse_input_links():
    for link in input_links:
        if "max_coubs" in globals() and len(coub_list) >= max_coubs:
            break
        coub_list.append(link)

    if len(input_links):
        msg("Reading command line:")
        msg("  ", len(input_links), " link(s) found", sep="")

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def parse_input():
    parse_input_links()

    if len(coub_list) == 0:
        err("No coub links specified!")
        usage()
        clean()
        exit()

    if "max_coubs" in globals() and len(coub_list) >= max_coubs:
        msg("\nDownload limit (", max_coubs, ") reached!", sep="")

    if "out_file" in globals():
        with open(out_file, "w") as f:
            for link in coub_list: print(link, file=f)
        msg("\nParsed coubs written to '", out_file, "'!", sep="")
        clean()
        exit()

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def get_out_name(coub_id):
    out_name = coub_id
    return out_name

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def existence(name):
    if ( os.path.exists(name + ".mkv") and not a_only and not v_only ) or \
       ( os.path.exists(name + ".mp4") and v_only ) or \
       ( os.path.exists(name + ".mp3") and a_only ):
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
            if answer == "1": return True
            if answer == "2": return False
    else:
        err("Unknown prompt_answer in overwrite!")
        clean()
        exit()

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
        exit()

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def download(data, name):
    video = ""
    audio = ""
    v_size = 0
    a_size = 0

    for quality in ["high","med"]:
        v_size = data['file_versions']['html5']['video'][quality]['size']
        a_size = data['file_versions']['html5']['audio'][quality]['size']
        if not video and v_size > 0:
            video = data['file_versions']['html5']['video'][quality]['url']
        if not audio and a_size > 0:
            audio = data['file_versions']['html5']['audio'][quality]['url']

    if not a_only:
        try:
            urllib.request.urlretrieve(video, name + ".mp4")
            # Fix broken video stream
            # Done in downloads to avoid unncessary read() of whole file
        except:
            err("Error: Coub unavailable!")
            raise

    if not v_only:
        try:
            urllib.request.urlretrieve(audio, name + ".mp3")
        except:
            err("Error: Audio unavailable!")
            if a_only:
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
    if a_only: extension = ".mp3"
    if v_only: extension = ".mp4"

    try:
        command = preview_command.split(" ")
        command.append(name + extension)
        subprocess.run(command, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
    except:
        err("Error: Missing file in show_preview!")
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
    for coub in coub_list:
        counter += 1
        msg("  ", counter, " out of ", len(coub_list), " (", coub, ")", sep="")

        coub_id = coub.split("/")[-1]

        # Pass existing files to avoid unnecessary downloads
        # This check handles archive file search and default output formatting
        # Avoids curl usage (slow!) just to skip files anyway
        if ( "archive_file" in globals() and use_archive("read", coub_id) ) \
           or ( existence(coub_id) and not overwrite() ):
            msg("Already downloaded!")
            clean()
            continue

        out_name = get_out_name(coub_id)

        api_call = "https://coub.com/api/v2/coubs/" + coub_id
        try:
            coub_json = urllib.request.urlopen(api_call).read()
        except:
            err("Error: Coub unavailable!")
            continue
        coub_json = json.loads(coub_json)

        if "sleep_dur" in globals() and counter > 1:
            time.sleep(sleep_dur)
        # Download video/audio streams
        # Skip if the requested media couldn't be downloaded
        try:
            download(coub_json, out_name)
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
            except:
                continue

        # Clean workspace
        clean()

    msg("\n### Finished ###\n")

# Execute main function
if len(sys.argv) == 1: usage(); exit()
main()
