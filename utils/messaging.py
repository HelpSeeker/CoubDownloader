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

import sys

from utils import colors

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Global Variables
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

VERBOSITY = 0

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Functions
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def set_message_verbosity(level):
    """Adjust global verbosity level."""
    global VERBOSITY

    VERBOSITY = level


def err(*args, color=None, **kwargs):
    """Print to stderr."""
    if color:
        sys.stderr.write(color)

    print(*args, file=sys.stderr, **kwargs)

    if color:
        sys.stderr.write(colors.RESET)
        sys.stdout.write(colors.RESET)


def msg(*args, color=None, **kwargs):
    """Print to stdout based on verbosity level."""
    if VERBOSITY < 1:
        return

    if color:
        sys.stdout.write(color)

    print(*args, **kwargs)

    if color:
        sys.stderr.write(colors.RESET)
        sys.stdout.write(colors.RESET)
