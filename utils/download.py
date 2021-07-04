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

import utils.messaging as msg
from utils.settings import Settings

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

CANCELLED = False

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
        self.infos = {
            '%id%': self.id,
            '%title%': "",
            '%creation%': "",
            '%channel%': "",
            '%tags%': "",
        }

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
        if not Settings.get().name_template:
            if not self.name:
                old_file = exists(self.id)
        else:
            if self.name:
                old_file = exists(self.name)

        if old_file and not overwrite(old_file):
            self.exists = True

    def update_infos(self, resp_json):
        """Fetch basic coub information."""
        self.infos['%title%'] = resp_json['title']
        self.infos['%creation%'] = resp_json['created_at']
        self.infos['%channel%'] = resp_json['channel']['title']
        self.infos['%tags%'] = [t['title'] for t in resp_json['tags']]

        # Coubs don't necessarily belong to a community (although it's rare)
        try:
            self.infos['%community%'] = resp_json['communities'][0]['permalink']
        except (KeyError, TypeError, IndexError):
            self.infos['%community%'] = "undefined"

    def get_name(self):
        """Assemble final output name of a given coub."""
        if not Settings.get().name_template:
            self.name = self.infos['%id%']
            return

        name = Settings.get().name_template
        for to_replace in self.infos:
            if to_replace == '%tags%':
                name = name.replace(to_replace, Settings.get().tag_sep.join(self.infos['%tags%']))
            else:
                name = name.replace(to_replace, self.infos[to_replace])

        # An attempt to remove the most blatant problematic characters
        # Linux supports all except /, but \n and \t are only asking for trouble
        # https://dwheeler.com/essays/fixing-unix-linux-filenames.html
        # ' is problematic as it causes issues with FFmpeg's concat muxer
        forbidden = ["\n", "\t", "'", "/"]
        if os.name == "nt":
            forbidden.extend(["<", ">", ":", "\"", "\\", "|", "?", "*"])
        for to_replace in forbidden:
            name = name.replace(to_replace, Settings.get().fallback_char)

        try:
            # Add example extension to simulate the full name length
            f = open(f"{name}.ext", "w")
            f.close()
            os.remove(f"{name}.ext")
        except OSError:
            msg.err(f"Error: Filename invalid or too long! Falling back to '{self.infos['%id%']}'",
                color=msg.WARNING)
            name = self.infos['%id%']

        self.name = name

    async def parse(self, session):
        """Get all necessary coub infos from the Coub API."""
        if self.erroneous():
            return

        async with session.get(self.req) as resp:
            resp_json = await resp.read()
            print(self.req)
            resp_json = json.loads(resp_json)

        v_list, a_list = stream_lists(resp_json)
        if v_list:
            self.v_link = v_list[Settings.get().v_quality]
        else:
            self.unavailable = True
            return

        if a_list:
            self.a_link = a_list[Settings.get().a_quality]
        elif Settings.get().a_only:
            self.unavailable = True
            return

        self.update_infos(resp_json)
        self.get_name()

        if not Settings.get().a_only:
            self.v_name = f"{self.name}.mp4"
        if not Settings.get().v_only and self.a_link:
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
            if Settings.get().a_only:
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

        m_name = f"{self.name}.{Settings.get().merge_ext}"     # merged name
        t_name = f"{self.name}.txt"                  # txt name

        try:
            # Print .txt for FFmpeg's concat
            with open(t_name, "w") as f:
                for _ in range(Settings.get().repeat):
                    print(f"file 'file:{self.v_name}'", file=f)

            # Loop footage until shortest stream ends
            # Concatenated video (via list) counts as one long stream
            command = [
                Settings.get().ffmpeg_path, "-y", "-v", "error",
                "-f", "concat", "-safe", "0",
                "-i", f"file:{t_name}", "-i", f"file:{self.a_name}",
            ]
            if Settings.get().duration:
                command.extend(["-t", Settings.get().duration])
            command.extend(["-c", "copy", "-shortest", f"file:temp_{m_name}"])

            subprocess.run(command, env=ENV, check=False)
        finally:
            if os.path.exists(t_name):
                os.remove(t_name)

        # Merging would break when using <...>.mp4 both as input and output
        os.replace(f"temp_{m_name}", m_name)

        if not Settings.get().keep:
            if self.v_name != m_name:
                os.remove(self.v_name)
            os.remove(self.a_name)

    def print_json(self, path):
        """Output basic coub information to file."""
        if self.erroneous():
            return

        # Strip surrounding % from the internally used keys
        output = {i.strip("%"): self.infos[i] for i in self.infos}
        with open(path, "a") as f:
            print(json.dumps(output), file=f)

    def archive(self):
        """Log a coub's ID in the archive file."""
        # This return also prevents users from creating new archive files
        # from already existing coub collections
        if self.erroneous():
            return

        # TODO: change archive path to pathlib object
        with open(Settings.get().archive_path, "a") as f:
            print(self.id, file=f)

    def preview(self):
        """Play a coub with the user provided command."""
        if self.erroneous():
            return

        if self.v_name and self.a_name:
            play = f"{self.name}.{Settings.get().merge_ext}"
        elif self.v_name:
            play = self.v_name
        elif self.a_name:
            play = self.a_name

        try:
            # Need to split command string into list for check_call
            command = Settings.get().preview.split(" ")
            command.append(play)
            subprocess.run(command, env=ENV, check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except (subprocess.CalledProcessError, FileNotFoundError):
            msg.err("Warning: Preview command failed!", color=msg.WARNING)

    async def process(self, session):
        """Process a single coub."""
        global count, done

        # 1st existence check
        # Handles default naming scheme and archive usage
        self.check_existence()

        await self.parse(session)

        # 2nd existence check
        # Handles custom names exclusively (slower since API request necessary)
        if Settings.get().name_template:
            self.check_existence()

        # Download
        await self.download(session)

        # Postprocessing stage
        self.check_integrity()
        if not (Settings.get().v_only or Settings.get().a_only):
            self.merge()

        # Success should be logged as soon as possible to avoid deletion
        # of valid streams with special format options (e.g. --video-only)
        self.done = True

        if Settings.get().json:
            self.print_json(Settings.get().json)
        if Settings.get().archive_path:
            self.archive()
        if Settings.get().preview:
            self.preview()

        # Log status after processing
        count += 1
        progress = f"[{count: >{len(str(total))}}/{total}]"
        if self.unavailable:
            msg.err(f"  {progress} {self.link: <30} ... ", end="")
            msg.err("unavailable", color=msg.ERROR)
        elif self.corrupted:
            msg.err(f"  {progress} {self.link: <30} ... ", end="")
            msg.err("failed to download", color=msg.ERROR)
        elif self.exists:
            done += 1
            msg.msg(f"  {progress} {self.link: <30} ... ", end="")
            msg.msg("exists", color=msg.WARNING)
        else:
            done += 1
            msg.msg(f"  {progress} {self.link: <30} ... ", end="")
            msg.msg("finished", color=msg.SUCCESS)

    def delete(self):
        """Delete any leftover streams."""
        if self.v_name and os.path.exists(self.v_name):
            os.remove(self.v_name)
        if self.a_name and os.path.exists(self.a_name):
            os.remove(self.a_name)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Functions
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def exists(name):
    """Test if a video with the given name and requested extension exists."""
    if Settings.get().v_only or Settings.get().share:
        full_name = [f"{name}.mp4"]
    elif Settings.get().a_only:
        # exists() gets called before and after the API request was made
        # Unless MP3 or AAC audio are strictly prohibited, there's no way to
        # tell the final extension before the API request
        full_name = []
        if Settings.get().aac > 0:
            full_name.append(f"{name}.m4a")
        if Settings.get().aac < 3:
            full_name.append(f"{name}.mp3")
    else:
        full_name = [f"{name}.{Settings.get().merge_ext}"]

    for f in full_name:
        if os.path.exists(f):
            return f

    return None


def overwrite(name):
    """Prompt the user if they want to overwrite an existing coub."""
    if Settings.get().prompt == "yes":
        return True
    if Settings.get().prompt == "no":
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
    if Settings.get().share:
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

    v_max = v_formats[Settings.get().v_max]
    v_min = v_formats[Settings.get().v_min]

    version = resp_json['file_versions']['html5']['video']
    for vq in v_formats:
        if v_min <= v_formats[vq] <= v_max:
            # html5 stream sizes can be 0 OR None in case of a missing stream
            # None is the exception and an irregularity in the Coub API
            if vq in version and version[vq]['size']:
                video.append(version[vq]['url'])

    # Audio stream parsing
    if Settings.get().aac >= 2:
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
            if Settings.get().aac:
                # Mobile audio doesn't list its size
                # So just pray that the file behind the link exists
                audio.append(version[aq])
        elif aq in version and version[aq]['size'] and Settings.get().aac < 3:
            audio.append(version[aq]['url'])

    return (video, audio)


def valid_stream(path, attempted_fix=False):
    """Test a given stream for eventual corruption with a test remux (FFmpeg)."""
    command = [
        Settings.get().ffmpeg_path, "-v", "error",
        "-i", f"file:{path}",
        "-t", "1",
        "-f", "null", "-",
    ]
    out = subprocess.run(command, capture_output=True, text=True, env=ENV, check=False)

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


async def save_stream(link, path, session):
    """Download a single media stream."""
    async with session.get(link) as stream:
        with open(path, "wb") as f:
            while True:
                if CANCELLED:
                    raise KeyboardInterrupt
                chunk = await stream.content.read(Settings.get().chunk_size)
                if not chunk:
                    break
                f.write(chunk)
