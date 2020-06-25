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

import os

# https://en.wikipedia.org/wiki/ANSI_escape_code#Colors
ERROR = '\033[31m'      # red
WARNING = '\033[33m'    # yellow
SUCCESS = '\033[32m'    # green
RESET = '\033[0m'

def disable():
    """Disable colorized output by removing escape codes."""
    global ERROR, WARNING, SUCCESS, RESET

    ERROR = ''
    SUCCESS = ''
    WARNING = ''
    RESET = ''

# ANSI escape codes don't work on Windows, unless the user jumps through
# additional hoops (either by using 3rd-party software or enabling VT100
# emulation with Windows 10)
# colorama solves this issue by converting ANSI escape codes into the
# appropriate win32 calls (only on Windows)
# If colorama isn't available, disable colorized output on Windows
try:
    import colorama
    colorama.init()
except ModuleNotFoundError:
    if os.name == "nt":
        disable()
