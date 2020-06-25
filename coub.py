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

import asyncio
import json
import os
import subprocess
import sys

from ssl import SSLCertVerificationError, SSLContext
from textwrap import dedent

import urllib.error
from urllib.request import urlopen

import aiohttp

from utils import container
from utils import exitcodes as status
from utils.options import parse_cli

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

# Trigger keyboard interrupt from the outside
cancelled = False

# List of directories to scan for config files
# Only script's dir for now
CONF_DIRS = [os.path.dirname(os.path.realpath(__file__))]

fgcolors = Colors()
if not colors:
    fgcolors.disable()

total = 0
count = 0
done = 0

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Classes
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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

    async def parse(self, session):
        """Get all necessary coub infos from the Coub API."""
        if self.erroneous():
            return

        async with session.get(self.req) as resp:
            resp_json = await resp.read()
            resp_json = json.loads(resp_json)

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

    async def download(self, session):
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
            with open(t_name, "w") as f:
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

            subprocess.run(command, env=env, check=False)
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
            subprocess.run(command, env=env, check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except (subprocess.CalledProcessError, FileNotFoundError):
            err("Warning: Preview command failed!", color=fgcolors.WARNING)

    async def process(self, session):
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
                       env=env, check=False)
    except FileNotFoundError:
        err("Error: FFmpeg not found!")
        sys.exit(status.DEP)


def check_connection():
    """Check if user can connect to coub.com."""
    try:
        urlopen("https://coub.com/", context=sslcontext)
    except urllib.error.URLError as e:
        if isinstance(e.reason, SSLCertVerificationError):
            err("Certificate verification failed! Please update your CA certificates.")
        else:
            err("Unable to connect to coub.com! Please check your connection.")
        sys.exit(status.CONN)


def resolve_paths():
    """Change into (and create) the destination directory."""
    if not os.path.exists(opts.path):
        os.makedirs(opts.path)
    os.chdir(opts.path)


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
        else:
            rest = None

        if isinstance(c, container.Channel):
            c.set_recoubs(opts.recoubs)
        if not isinstance(c, container.LinkList):
            c.prepare(rest)

        if not c.valid:
            err("\n", c.error, color=fgcolors.WARNING, sep="")
            continue

        if isinstance(c, container.LinkList):
            msg(f"\nReading input list ({c.id}):")
        else:
            msg(f"\nDownloading {c.type} info",
                f": {c.id}"*bool(c.id),
                f" (sorted by '{c.sort}')"*bool(c.sort), sep="")
            msg(f"  {c.max_pages} out of {c.pages} pages")

        level = 0
        while opts.retries < 0 or level <= opts.retries:
            try:
                if isinstance(c, container.LinkList):
                    parsed.extend(asyncio.run(c.process(rest)))
                else:
                    parsed.extend(asyncio.run(c.process(opts.connections, rest)))
                break   # Exit loop on successful completion
            except (aiohttp.ClientConnectionError, aiohttp.ClientPayloadError):
                check_connection()
                level += 1
                err(f"  Retrying... ({level} of "
                    f"{opts.retries if opts.retries > 0 else 'Inf'} attempts)",
                    color=fgcolors.WARNING)

        if isinstance(c, container.LinkList):
            msg(f"  {c.length} link{'s' if c.length != 1 else ''} found")

        if level > opts.retries >= 0:
            err(f"  Can't fetch {c.type} info! Please check your connection.")
            sys.exit(status.CONN)

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


async def save_stream(link, path, session):
    """Download a single media stream."""
    async with session.get(link) as stream:
        with open(path, "wb") as f:
            while True:
                if cancelled:
                    raise KeyboardInterrupt
                chunk = await stream.content.read(opts.chunk_size)
                if not chunk:
                    break
                f.write(chunk)


def valid_stream(path, attempted_fix=False):
    """Test a given stream for eventual corruption with a test remux (FFmpeg)."""
    command = [
        opts.ffmpeg_path, "-v", "error",
        "-i", f"file:{path}",
        "-t", "1",
        "-f", "null", "-",
    ]
    out = subprocess.run(command, capture_output=True, text=True, env=env, check=False)

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
    tout = aiohttp.ClientTimeout(total=None)
    conn = aiohttp.TCPConnector(limit=opts.connections, ssl=sslcontext)
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
    except (aiohttp.ClientConnectionError, aiohttp.ClientPayloadError):
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
    global total

    check_prereq()
    resolve_paths()
    check_connection()

    msg("\n### Parse Input ###")
    try:
        ids = parse_input(opts.input)
    except KeyboardInterrupt:
        err("\nUser Interrupt!", color=fgcolors.WARNING)
        sys.exit(status.INT)
    if ids:
        if opts.output_list:
            write_list(ids)
            sys.exit(0)
        total = len(ids)
        coubs = [Coub(i) for i in ids]

        msg("\n### Download Coubs ###\n")
        try:
            attempt_process(coubs)
        except KeyboardInterrupt:
            clean(coubs)
            err("\nUser Interrupt!", color=fgcolors.WARNING)
            sys.exit(status.INT)
        finally:
            clean(coubs)
    else:
        msg("\nAll coubs present in archive file!", color=fgcolors.WARNING)

    msg("\n### Finished ###\n")


# Execute main function
if __name__ == '__main__':
    sslcontext = SSLContext()
    env = dict(os.environ)
    # Change library search path based on script usage
    # https://pyinstaller.readthedocs.io/en/stable/runtime-information.html#ld-library-path-libpath-considerations
    if hasattr(sys, 'frozen') and hasattr(sys, '_MEIPASS'):
        lp_key = 'LD_LIBRARY_PATH'  # for GNU/Linux and *BSD.
        lp_orig = env.get(lp_key + '_ORIG')
        if lp_orig is not None:
            env[lp_key] = lp_orig
        else:
            env.pop(lp_key, None)   # LD_LIBRARY_PATH was not set

    opts = parse_cli(CONF_DIRS)
    # parse_cli returns list with error messages on non-argparse failure
    if isinstance(opts, list):
        err("\n".join(opts))
        sys.exit(status.OPT)

    try:
        main()
    except KeyboardInterrupt:
        err("\nUser Interrupt!", color=fgcolors.WARNING)
        sys.exit(status.INT)

    # Indicate failure if not all input coubs exist after execution
    if done < count:
        sys.exit(status.DOWN)
    sys.exit(0)
