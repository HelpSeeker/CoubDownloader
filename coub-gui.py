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
import sys

from ssl import SSLContext
from threading import Thread
from tkinter import Tk
from tkinter import messagebox
from tkinter import ttk

import coub
from utils import colors
from utils import container
from utils import download
from utils import exitcodes as status
from utils import gui
from utils.messaging import err, set_message_verbosity
from utils.options import DefaultOptions

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Global Variables
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# List of directories to scan for config files
# Only script's dir for now
CONF_DIRS = [os.path.dirname(os.path.realpath(__file__))]

PADDING = 5

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Classes
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

class Options:
    """Class to hold all available options."""

    def __init__(self):
        defaults = DefaultOptions(CONF_DIRS)
        if defaults.error:
            err("\n".join(defaults.error))
            sys.exit(status.OPT)

        # Actually unnecessary as overwritten msg functions just ignore the level
        self.verbosity = 1
        self.prompt = defaults.PROMPT
        self.path = defaults.PATH
        self.keep = defaults.KEEP
        self.repeat = defaults.REPEAT
        self.duration = defaults.DURATION
        self.connections = defaults.CONNECTIONS
        self.retries = defaults.RETRIES
        self.max_coubs = defaults.MAX_COUBS
        self.v_quality = defaults.V_QUALITY
        self.a_quality = defaults.A_QUALITY
        self.v_max = defaults.V_MAX
        self.v_min = defaults.V_MIN
        self.aac = defaults.AAC
        self.share = defaults.SHARE
        self.recoubs = defaults.RECOUBS
        self.preview = defaults.PREVIEW
        self.a_only = defaults.A_ONLY
        self.v_only = defaults.V_ONLY
        self.output_list = defaults.OUTPUT_LIST
        self.archive = defaults.ARCHIVE
        self.merge_ext = defaults.MERGE_EXT
        self.name_template = defaults.NAME_TEMPLATE
        self.ffmpeg_path = defaults.FFMPEG_PATH
        self.tag_sep = defaults.TAG_SEP
        self.fallback_char = defaults.FALLBACK_CHAR
        self.write_method = defaults.WRITE_METHOD
        self.chunk_size = defaults.CHUNK_SIZE

        self.input = []

        if self.archive and os.path.exists(self.archive):
            with open(self.archive, "r") as f:
                self.archive_content = {l.strip() for l in f}
        else:
            self.archive_content = set()
        if not self.path or self.path == ".":
            self.path = os.path.join(os.path.expanduser("~"), "coubs")
        else:
            self.path = os.path.abspath(self.path)
        if self.name_template == "%id%":
            self.name_template = None
        if self.tag_sep == "space":
            self.tag_sep = " "
        if self.fallback_char is None:
            self.fallback_char = ""
        elif self.fallback_char == "space":
            self.fallback_char = " "


class MainWindow(ttk.Frame):
    """Frame to hold the main interface."""

    def __init__(self, master):
        super(MainWindow, self).__init__(master)
        self.configure(padding=(PADDING, PADDING, PADDING, 0))
        self.rowconfigure(2, weight=1)
        self.columnconfigure(3, weight=1)
        self.grid(sticky="news")

        self.input = gui.InputFrame(self)
        new_url = ttk.Button(self, text="New URL", command=self.new_url_press)
        new_item = ttk.Button(self, text="New Item", command=self.new_item_press)
        self.edit_item = ttk.Button(self, text="Edit Item",
                                    command=self.edit_item_press)
        prefs = ttk.Button(self, text="Settings", command=self.settings_press)
        about = ttk.Button(self, text="Help", command=gui.HelpWindow)
        output = gui.OutputFrame(self)
        sys.stdout = output
        sys.stderr = output
        #progress = ttk.Progressbar(self, orient=HORIZONTAL, mode="indeterminate")
        clean = ttk.Button(self, text="Clean", command=output.clear)
        start = ttk.Button(self, text="Start", command=self.start_press)
        cancel = ttk.Button(self, text="Cancel", command=self.cancel_press)

        self.input.grid(row=0, columnspan=6, sticky="news")
        new_url.grid(row=1, pady=PADDING)
        new_item.grid(row=1, column=1, padx=PADDING, pady=PADDING)
        prefs.grid(row=1, column=4, padx=PADDING, pady=PADDING)
        about.grid(row=1, column=5, pady=PADDING)
        output.grid(row=2, columnspan=6, sticky="news")
        #progress.grid(row=3, columnspan=2, sticky="ew")
        clean.grid(row=3, column=0, pady=PADDING)
        start.grid(row=3, column=4, padx=PADDING, pady=PADDING)
        cancel.grid(row=3, column=5, pady=PADDING)

        self.master.bind('u', self.new_url_press)
        self.master.bind('i', self.new_item_press)
        self.master.bind('e', self.edit_item_press)
        self.input.tree.bind('<<TreeviewSelect>>', self.update_widgets)
        self.input.tree.bind('<Delete>', self.input.tree.delete_item)
        self.input.tree.bind('<Double-1>', self.edit_item_press)

        self.thread = Thread(target=coub.main)

    def update_widgets(self, *args):
        """Update widgets based on source selection/quantity."""
        # Show "Edit Item" button if any item is selected
        if self.input.tree.focus():
            self.edit_item.grid(row=1, column=2, pady=PADDING)
        else:
            self.edit_item.grid_forget()

        # Update widgets for input frame to show scrollbar if necessary
        self.input.update_widgets()

    def new_url_press(self, *args):
        """Open new URL window."""
        dialog = gui.NewURLWindow()
        self.wait_window(dialog)
        self.input.tree.add_item(dialog.get())
        self.update_widgets()

    def new_item_press(self, *args):
        """"Open new item window."""
        dialog = gui.NewItemWindow()
        self.wait_window(dialog)
        self.input.tree.add_item(dialog.get())
        self.update_widgets()

    def edit_item_press(self, *args):
        """Open edit item window."""
        selection = self.input.tree.focus()
        if selection:
            dialog = gui.EditItemWindow(self.input.tree.item(selection))
            self.wait_window(dialog)
            self.input.tree.edit_item(selection, dialog.get())
            self.update_widgets()

    def settings_press(self):
        """Open settings window."""
        dialog = gui.SettingsWindow(coub.opts)
        self.wait_window(dialog)
        coub.opts = dialog.get_settings()

    def start_press(self):
        """Start coub process in a separate thread."""
        download.total = 0
        download.count = 0
        download.done = 0
        container.CANCELLED = False
        download.CANCELLED = False

        if self.input.tree.sources:
            coub.opts.input = list(self.input.tree.sources.values())
            self.thread = Thread(target=coub.main)
            self.thread.start()

    @staticmethod
    def cancel_press():
        """Signal cancelation to coub processing thread."""
        container.CANCELLED = True
        download.CANCELLED = True

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Functions
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def overwrite(name, opts):
    """Prompt the user if they want to overwrite an existing coub."""
    if opts.prompt == "yes":
        return True
    if opts.prompt == "no":
        return False

    return messagebox.askyesno(title="File exists", icon="question",
                               message=f"Overwrite file? ({name})")


def close_prompt():
    """Prompt user if main window should be closed during running coub process."""
    if not main.thread.is_alive():
        root.destroy()
    elif messagebox.askokcancel("Quit", "Really quit while a download is running?"):
        main.cancel_press()
        root.destroy()


if __name__ == '__main__':
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
    coub.env = env
    coub.sslcontext = SSLContext()
    download.overwrite = overwrite

    coub.opts = Options()

    # Adjust messaging system for GUI
    colors.disable()
    set_message_verbosity(coub.opts.verbosity)

    root = Tk()
    root.title("CoubDownloader")
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)
    root.protocol("WM_DELETE_WINDOW", close_prompt)

    ttk.Style().configure("Heading.TLabel", font="TkHeadingFont")
    main = MainWindow(root)

    root.mainloop()
