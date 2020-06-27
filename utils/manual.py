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


GENERAL = """
++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                          WORK IN PROGRESS
++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

CoubDownloader allows you to download videos (aka coubs) from coub.com.

Here you can find useful informations about how to use this tool to download your favorite coubs.


Adding/editing/removing sources
===============================

To download coubs you need to specify one or more input sources. These sources can be direct links to a single coub, a user's channel, a specific tag and much more. For a full list of supported sources and how to use them, please take a look at the input help.

There are two ways to add new sources:

  1. Add a new URL
  ----------------

    1.) Click the button "New URL"
    2.) Wait for a dialog window to pop up
    3.) Paste the URL into the text field said window
    4.) Hit enter or press ok

  2. Add a new item
  -----------------

    1.) Click the button "New Item"
    2.) Wait for a dialog window to pop up
    3.) Specify the type, name/term/id and sort method (if supported)
    4.) Hit enter or press ok

The new input source should now show appear in the list at the top of the window, with information about its type, name/term/id and sort method. Especially when using URL input, it is a good idea to check, if those values are correct.

If this is not the case or you want to edit an already existing input source, simply select the item in the list. A new button "Edit Item" should appear. Clicking it will bring up a dialog window, which can be used to adjust all aspects of the source. You can also double click the item to open the same dialog.

To remove an already existing source, select the item in the list and either open the edit dialog and press "Remove" or hit the delete key on your keyboard.


Running CoubDownloader
======================

Once all wanted sources have been added, you can start the download by pressing "Start". CoubDownloader will then start parsing all input and afterwards download all found links. The status and progress of the operation will be shown in the center frame.

Running downloads can be stopped with "Cancel". Please note that this will remove all only partially downloaded media streams and discard the list of parsed links. If you want to download from many extensive sources (e.g. searches) and it's likely that you have to stop the operation, then consider outputting the parsed links to a list (Settings -> Output -> Output all parsed links to a list) and use said list as input instead.

The "Clean" button can be used to remove any text (progress or error messages) from the center frame.


Settings
========

Common options can be accessed via the "Settings" button. The settings window is the main way to temporarily change settings.

------------------------------------------------------------------------
IMPORTANT: Changes aren't saved between sessions!
------------------------------------------------------------------------

To permenantly change settings you have to create a custom config file named "coub.conf" in the same location as CoubDownloader. For a list of supported options and their defaults see the example configuration file example.conf.

The following list provides a short overview of what the available options (as seen in the settings window) do.

Overwrite prompt
----------------

CoubDownloader asks you for permission to overwrite any already existing file. This will stall the script until input was given. To avoid this you can tell CoubDownloader to assume an answer for all prompts.

CLI equivalent: -y/--yes, -n/--no

Loop count
----------

Coubs are short videos most often looped to music. This option allows to limit the max. (!) number of loops. It is important to note that the audio itself is also a hard limit. If the video is looped 10 tens for a total of 100 seconds, but the audio is only 30 seconds long, then the final clip will also be 30 seconds in length. A very high default value will therefore ensure that the video will always match up with the audio duration.

If no audio is present then video looping is disabled.

CLI equivalent: -r/--repeat, -s/--short (alias for -r 1)

Limit Duration
--------------

Similar to "Loop Count", but works with absolute values instead. This option uses FFmpeg's time syntax (https://ffmpeg.org/ffmpeg-utils.html#time-duration-syntax) to trim the output to a certain length. It can be used in combination with "Loop Count", in which case the shorter duration will take precedence. Also like "Loop Count" the audio duration is a hard upper limit, which cannot be exceeded.

CLI equivalent: -d/--duration

Preview Command
---------------

CoubDownloader allows you to preview each coub after it has been finished processing. To preview a coub, enter a command which will be called with the coub's location as last argument (e.g. mpv, vlc, ffplay, totem). Be careful when calling CLI players without a separate window as their keyboard shortcuts will likely stop working.

Please note that CoubDownloader does not enforce any restrictions on the given command nor check its content. It is the user's responsibility to know the consequences of the invoked command.

CLI equivalent: --preview, --no-preview

Archive
-------

Archive files can be used to keep track of already downloaded coubs. When an archive file is selected, each downloaded coub will have its ID saved and be ignored during future downloads. Using an archive file to skip existing coubs is usually a lot faster than relying on duplicate filenames (especially with custom name templates).

CLI equivalent: --use-archive

Recoubs
-------

A channel on Coub contains two kinds of coubs. Original ones and recoubs. This option allows you to decide how to treat recoubs during channel downloads.

CLI equivalent: --recoubs, --no-recoubs, --only-recoubs

Keep Streams
------------

Coub stores its media as separate audio and video streams (the 'share' version being the exception). CoubDownloader downloads both streams and then remuxes (i.e. combines) them into the final file. Afterwards the initially downloaded streams are discarded. Check this option to prevent their deletion.

CLI equivalent: -k/--keep

"""

INPUT = """
++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                          WORK IN PROGRESS
++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
"""

ABOUT = """
CoubDownloader

A simple downloader for coub.com

https://github.com/HelpSeeker/CoubDownloader
"""

LICENSE = """
Copyright (C) 2018-2020 HelpSeeker <AlmostSerious@protonmail.ch>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""
