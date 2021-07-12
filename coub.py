#!/usr/bin/env python3

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

import asyncio
import subprocess
import sys
from ssl import SSLCertVerificationError
import urllib

import aiohttp

from core import checker
from core import container
from core import download
import core.messaging as msg
from core.settings import Settings, parse_cli, ConfigurationError

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Global Variables
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# A hard limit on how many Coubs to process at once
# Prevents excessive RAM usage for very large downloads
COUB_LIMIT = 1000

ERROR_DEP = 1     # missing required software
ERROR_OPT = 2     # invalid user-specified option
ERROR_RUN = 3     # misc. runtime error
ERROR_DOWN = 4    # failed to download all input links (existence == success)
ERROR_INT = 5     # early termination was requested by the user (i.e. Ctrl+C)
ERROR_CONN = 6    # connection either couldn't be established or was lost

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Functions
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def check_prereq():
    """Test if all required 3rd-party tools are installed."""
    try:
        subprocess.run([Settings.get().ffmpeg_path],
                       stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL,
                       env=Settings.get().env, check=False)
    except FileNotFoundError:
        msg.err("Error: FFmpeg not found!", color=msg.ERROR)
        sys.exit(ERROR_DEP)


def check_connection():
    """Check if user can connect to coub.com."""
    try:
        urllib.request.urlopen("https://coub.com/", context=Settings.get().context)
    except urllib.error.URLError as e:
        if isinstance(e.reason, SSLCertVerificationError):
            msg.err("Certificate verification failed! Please update your CA certificates.",
                color=msg.ERROR)
        else:
            msg.err("Unable to connect to coub.com! Please check your connection.",
                color=msg.ERROR)
        sys.exit(ERROR_CONN)


# def remove_container_dupes(containers):
#     """Remove duplicate containers to avoid unnecessary parsing."""
#     no_dupes = []
    # Brute-force sorting
#     for c in containers:
#         unique = True
#         for u in no_dupes:
#             if (c.type, c.id, c.sort) == (u.type, u.id, u.sort):
#                 unique = False
#         if unique or c.type == "random":
#             no_dupes.append(c)

#     return no_dupes


async def parse_input(session):
    checker.init()

    ids = []
    quantity = Settings.get().max_coubs
    for item in Settings.get().input:
        try:
            if isinstance(item, container.LinkList):
                msg.msg(f"\nReading input list ({item.id}):")
            elif not isinstance(item, container.SingleCoub):
                msg.msg(
                    f"\nDownloading {item.type} info",
                    f": {item.id}" * bool(item.id),
                    f" (sorted by '{item.sort}')" * bool(item.sort),
                    sep="",
                )

            temp = await item.get_ids(session, quantity)

            ids.extend(temp)
            if quantity is not None:
                quantity -= len(temp)
                if not quantity:
                    break
        except container.ContainerUnavailableError:
            msg.err(f"\n{item.type}: {item.id} doesn't exist", color=msg.ERROR)
        except container.APIResponseError:
            msg.err(f"\n{item.type}: {item.id} invalid or missing API response", color=msg.ERROR)
        except FileNotFoundError:
            msg.err(f"\n{item.id} doesn't exits", color=msg.ERROR)
        except (OSError, UnicodeError):
            msg.err(f"\n{item.id} can't be read", color=msg.ERROR)

    checker.uninit()

    if len(ids) == Settings.get().max_coubs:
        msg.msg(f"\nDownload limit ({Settings.get().max_coubs}) reached!", color=msg.WARNING)

    if ids:
        msg.msg(f"\n{len(ids)} link{'s' * (len(ids) > 1)} found", color=msg.SUCCESS)

    return ids


def write_list(ids):
    """Output parsed links to a list and exit."""
    with Settings.get().output_list.open(Settings.get().write_method) as f:
        print(*[f"https://coub.com/view/{i}" for i in ids], sep="\n", file=f)
    msg.msg(f"\nParsed coubs written to '{Settings.get().output_list}'!",
        color=msg.SUCCESS)


def clean_workspace():
    """Clean workspace by deleteing unfinished coubs."""
    for file in Settings.get().path.glob("*.gyre"):
        file.unlink()


def custom_exception_ignorer(loop, context):
    if isinstance(context.exception, KeyboardInterrupt):
        pass
    else:
        loop.default_exception_handler(context)


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Main Function
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

async def main():
    """Download all requested coubs."""
    asyncio.get_running_loop().set_exception_handler(custom_exception_ignorer)

    # TODO: Move error handling outside of main
    try:
        parse_cli()
    except ConfigurationError as error:
        msg.err(f"Error: {error.cause}", color=msg.ERROR)
        sys.exit(ERROR_OPT)

    if not Settings.get().input:
        msg.err("No coub links specified!", color=msg.WARNING)
        sys.exit(ERROR_OPT)

    check_prereq()
    check_connection()

    tout = aiohttp.ClientTimeout(total=None)
    conn = aiohttp.TCPConnector(limit=Settings.get().connections)
    async with aiohttp.ClientSession(timeout=tout, connector=conn) as session:
        msg.msg("\n### Parse Input ###")

        ids = await parse_input(session)

        if not ids:
            msg.msg("\nNo new coubs!", color=msg.WARNING)
            msg.msg("\n### Finished ###\n")
            sys.exit(0)

        if Settings.get().output_list:
            write_list(ids)
            sys.exit(0)

        download.total = len(ids)
        coubs = [download.Coub(i, session) for i in ids]

        msg.msg("\n### Download Coubs ###\n")

        while coubs:
            tasks = [c.process() for c in coubs[:COUB_LIMIT]]
            await asyncio.gather(*tasks)
            coubs = coubs[COUB_LIMIT:]

    msg.msg("\n### Finished ###\n")

    # TODO: Figure out when to ideally exit to also clean the workspace in any case
    if download.errors:
        sys.exit(ERROR_DOWN)


# Execute main function
if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        msg.err("\nUser Interrupt!", color=msg.WARNING)
        sys.exit(ERROR_INT)
    finally:
        clean_workspace()
