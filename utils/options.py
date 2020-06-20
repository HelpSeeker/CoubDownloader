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
