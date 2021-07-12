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

from core.settings import Settings

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Global variables
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

session = None
archive = None

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Functions
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def init():
    global session, archive

    session = set()
    archive = set()
    if Settings.get().archive and Settings.get().archive.exists():
        archive = set(Settings.get().archive.read_text().splitlines())


def uninit():
    global session, archive

    session = None
    archive = None


def in_session(coub):
    dupe = coub in session
    if not dupe:
        session.add(coub)

    return dupe


def in_archive(coub):
    return coub in archive
