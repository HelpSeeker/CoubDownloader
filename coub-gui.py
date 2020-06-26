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
from textwrap import dedent
from threading import Thread
from tkinter import Tk, Toplevel, Text, StringVar, IntVar, BooleanVar
from tkinter import filedialog
from tkinter import messagebox
from tkinter import ttk

import coub
from utils import colors
from utils import container
from utils import download
from utils import exitcodes as status
from utils import manual
from utils.messaging import err, set_message_verbosity
from utils.options import DefaultOptions, mapped_input

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


class NewURLWindow(Toplevel):
    """Window to let user input new sources via an URL."""

    def __init__(self):
        super(NewURLWindow, self).__init__(padx=PADDING, pady=PADDING)
        self.title("Add new URL")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.resizable(True, False)

        #self.frame = ttk.Frame(self, padding=PADDING)
        #self.frame.columnconfigure(0, weight=1)
        #self.frame.grid(sticky="news")

        # Differentiate between private vars to hold widget values
        # and public vars for get method
        self.iurl = StringVar()
        self.url = StringVar()

        url_l1 = ttk.Label(self, text="Enter URL")
        url_e1 = ttk.Entry(self, textvariable=self.iurl, width=30)
        ok = ttk.Button(self, text="OK", command=self.ok_press)
        cancel = ttk.Button(self, text="Cancel", command=self.destroy)

        url_l1.grid(row=0, columnspan=3, sticky="w")
        url_e1.grid(row=1, columnspan=3, sticky="ew", pady=PADDING)
        ok.grid(row=2, column=1, padx=PADDING)
        cancel.grid(row=2, column=2)

        url_e1.focus_set()

        self.bind('<Return>', self.ok_press)

    def ok_press(self, *args):
        """Destroy window."""
        self.url.set(self.iurl.get())
        self.destroy()

    def get(self):
        """Extract entered URL."""
        url = self.url.get()
        if url:
            return mapped_input(url)
        return None


class NewItemWindow(Toplevel):
    """Window to let user input new sources by specifiying its properties."""

    TYPES = (
        "Link",
        "List",
        "Channel",
        "Search",
        "Tag",
        "Community",
        "Featured",
        "Coub of the Day",
        "Story",
        "Hot section",
        "Random",
    )

    NEED_NAME = {"Link", "List", "Channel", "Search", "Tag", "Community", "Story"}

    ALLOWED_SORT = {
        'Link': (),
        'List': (),
        'Channel': ("most_recent", "most_liked", "most_viewed", "oldest", "random"),
        'Search': ("relevance", "top", "views_count", "most_recent"),
        'Tag': ("popular", "top", "views_count", "fresh"),
        'Community': ("hot_daily", "hot_weekly", "hot_monthly", "hot_quarterly",
                      "hot_six_months", "rising", "fresh", "top", "views_count", "random"),
        'Featured': ("recent", "top", "views_count"),
        'Coub of the Day': ("recent", "top", "views_count"),
        'Story': (),
        'Hot section': ("hot_daily", "hot_weekly", "hot_monthly", "hot_quarterly",
                        "hot_six_months", "rising", "fresh"),
        'Random': ("popular", "top"),
    }

    DEFAULT_SORT = {
        'Channel': "most_recent",
        'Search': "relevance",
        'Tag': "popular",
        'Community': "hot_monthly",
        'Featured': "recent",
        'Coub of the Day': "recent",
        'Hot section': "hot_monthly",
        'Random': "popular",
    }

    def __init__(self):
        super(NewItemWindow, self).__init__(padx=PADDING, pady=PADDING)
        self.title("Add new item")
        self.resizable(True, False)
        self.columnconfigure(0, weight=1)

        # Differentiate between private vars to hold widget values
        # and public vars for get method
        self.itype = StringVar()
        self.iname = StringVar()
        self.isort = StringVar()
        self.type = StringVar()
        self.name = StringVar()
        self.sort = StringVar()

        type_l1 = ttk.Label(self, text="Item Type")
        type_b1 = ttk.Combobox(self, textvariable=self.itype,
                               values=self.TYPES, state="readonly")
        name_l1 = ttk.Label(self, text="Identifier (tag, channel, community, ...)")
        self.name_e1 = ttk.Entry(self, textvariable=self.iname, width=30)
        # Browse button only used if "List" is selected as type
        self.name_b1 = ttk.Button(self, text="Browse", command=self.ask_list)
        sort_l1 = ttk.Label(self, text="Sort Method")
        self.sort_b1 = ttk.Combobox(self, textvariable=self.isort, state="readonly")
        ok = ttk.Button(self, text="OK", command=self.ok_press)
        # self.cancel to give EditItemWindow access to it
        self.cancel = ttk.Button(self, text="Cancel", command=self.destroy)

        # Initialize default Combobox lists
        self.itype.set("Link")
        self.update_widgets()
        self.name_e1.focus_set()

        type_l1.grid(row=0, columnspan=3, sticky="w")
        type_b1.grid(row=1, columnspan=3, sticky="ew", pady=PADDING)
        name_l1.grid(row=2, columnspan=3, sticky="w")
        self.name_e1.grid(row=3, columnspan=3, sticky="ew", pady=PADDING)
        sort_l1.grid(row=4, columnspan=3, sticky="w")
        self.sort_b1.grid(row=5, columnspan=3, sticky="ew", pady=PADDING)
        ok.grid(row=6, column=1, padx=PADDING)
        self.cancel.grid(row=6, column=2)

        type_b1.bind('<<ComboboxSelected>>', self.update_widgets)
        self.bind('<Return>', self.ok_press)

    def update_widgets(self, *args):
        """Update widgets based on selected input type."""
        t = self.itype.get()

        if t in self.NEED_NAME:
            self.name_e1.configure(state="normal")
        else:
            self.iname.set("")
            self.name_e1.configure(state="disabled")

        if self.ALLOWED_SORT[t]:
            self.sort_b1.set(self.DEFAULT_SORT[t])
            self.sort_b1.configure(state="readonly", values=self.ALLOWED_SORT[t])
        else:
            self.sort_b1.set("")
            self.sort_b1.configure(state="disabled")

        if t == "List":
            self.name_e1.grid(columnspan=2)
            self.name_b1.grid(row=3, column=2, sticky="e", pady=PADDING)
        else:
            self.name_e1.grid(columnspan=3)
            self.name_b1.grid_remove()

    def ask_list(self):
        """Open file picker to get link list path."""
        n = self.iname.get()
        n_path = os.path.abspath(n)
        if n and os.path.exists(n_path):
            init = n_path
        else:
            init = os.path.expanduser("~")

        if os.path.isfile(init):
            path = filedialog.askopenfilename(
                parent=self,
                title="Open link list",
                initialfile=init,
            )
        else:
            path = filedialog.askopenfilename(
                parent=self,
                title="Open link list",
                initialdir=init
            )

        if path:
            # For now no safe guard is in place, so just give visual feedback
            try:
                with open(path, "r") as f:
                    _ = f.read(1)
            except FileNotFoundError:
                path = "Error: File not found"
            except (OSError, UnicodeError):
                path = "Error: Can't decode file"

            self.iname.set(path)

    def ok_press(self, *args):
        """Destroy window and assign private to public variables."""
        self.type.set(self.itype.get())
        self.name.set(self.iname.get())
        self.sort.set(self.isort.get())
        self.destroy()

    def get(self):
        """Return source object based on chosen properties."""
        t = self.type.get()
        n = self.name.get()
        s = self.sort.get()
        if n or t in {"Featured", "Coub of the Day", "Hot section", "Random"}:
            if s:
                n = f"{n}#{s}"
            if t == "Link":
                source = n
            if t == "List":
                source = container.LinkList(n)
            if t == "Channel":
                source = container.Channel(n)
            if t == "Search":
                source = container.Search(n)
            if t == "Tag":
                source = container.Tag(n)
            if t == "Community":
                source = container.Community(n)
            if t == "Featured":
                source = container.Community(f"featured#{s}")
            if t == "Coub of the Day":
                source = container.Community(f"coub-of-the-day#{s}")
            if t == "Story":
                source = container.Story(n)
            if t == "Hot section":
                source = container.HotSection(s)
            if t == "Random":
                source = container.RandomCategory(s)
        else:
            source = None

        return source


class EditItemWindow(NewItemWindow):
    """Window to let user edit or remove already existing sources."""

    TYPE_MAP = {
        'link': "Link",
        'list': "List",
        'channel': "Channel",
        'tag': "Tag",
        'search': "Search",
        'community': "Community",
        'story': "Story",
        'hot section': "Hot section",
        'random': "Random",
    }

    def __init__(self, selection):
        super(EditItemWindow, self).__init__()
        self.title("Edit item")
        self.cancel.configure(text="Remove", command=self.remove_press)

        t = selection['values'][0]
        n = selection['values'][1]
        s = selection['values'][2]

        # Map internal container type to shown label
        t = self.TYPE_MAP[t]

        if t == "Community" and n == "featured":
            t = "Featured"
            n = ""
        elif t == "Community" and n == "coub-of-the-day":
            t = "Coub of the Day"
            n = ""

        self.itype.set(t)
        self.iname.set(n)
        self.isort.set(s)
        self.type.set(t)
        self.name.set(n)
        self.sort.set(s)
        self.update_widgets()

    def remove_press(self):
        """Destroy window and reset main properties."""
        # Resetting sort wouldn't really do anything
        self.type.set("")
        self.name.set("")
        self.destroy()


class GeneralSettings(ttk.Frame):
    """Frame holding general options in the settings window."""

    def __init__(self, master):
        super(GeneralSettings, self).__init__(master, padding=PADDING)
        self.columnconfigure(0, weight=1)

        self.prompt = StringVar()
        self.repeat = IntVar()
        self.dur = StringVar()
        self.preview = StringVar()
        self.archive = StringVar()
        self.keep = BooleanVar()
        self.recoubs = IntVar()

        self.prompt.set("" if not coub.opts.prompt else coub.opts.prompt)
        self.repeat.set(coub.opts.repeat)
        self.dur.set("" if not coub.opts.duration else coub.opts.duration)
        self.preview.set("" if not coub.opts.preview else coub.opts.preview)
        self.archive.set("" if not coub.opts.archive else coub.opts.archive)
        self.keep.set(coub.opts.keep)
        self.recoubs.set(coub.opts.recoubs)

        # Prompt behavior
        ttk.Label(self, text="Prompt Behavior", style="Heading.TLabel")
        ttk.Label(self, text="How to answer user prompts")
        ttk.Radiobutton(self, text="Prompt", value="", variable=self.prompt)
        ttk.Radiobutton(self, text="Yes", value="yes", variable=self.prompt)
        ttk.Radiobutton(self, text="No", value="no", variable=self.prompt)
        # Loop count
        ttk.Label(self, text="Loop Count", style="Heading.TLabel")
        ttk.Label(self, text="How often to loop the video stream")
        ttk.Spinbox(self, from_=1, textvariable=self.repeat)
        # Duration
        ttk.Label(self, text="Limit Duration", style="Heading.TLabel")
        ttk.Label(self, text="Max. output duration (FFmpeg syntax)")
        ttk.Entry(self, textvariable=self.dur)
        # Preview
        ttk.Label(self, text="Preview Command", style="Heading.TLabel")
        ttk.Label(self, text="Command to preview each finished coub")
        ttk.Entry(self, textvariable=self.preview)
        # Archive
        ttk.Label(self, text="Archive", style="Heading.TLabel")
        ttk.Label(self, text="Use an archive file to keep track of "
                             "already downloaded coubs")
        archive_e1 = ttk.Entry(self, textvariable=self.archive)
        archive_b1 = ttk.Button(self, text="Browse", command=self.ask_archive)
        # Recoub handling
        ttk.Label(self, text="Recoubs", style="Heading.TLabel")
        ttk.Label(self, text="How to treat recoubs during channel downloads")
        ttk.Radiobutton(self, text="No Recoubs", value=0, variable=self.recoubs)
        ttk.Radiobutton(self, text="With Recoubs", value=1, variable=self.recoubs)
        ttk.Radiobutton(self, text="Only Recoubs", value=2, variable=self.recoubs)
        # Keep streams
        ttk.Label(self, text="Keep Streams", style="Heading.TLabel")
        ttk.Checkbutton(self, variable=self.keep,
                        text="Keep individual streams after merging")

        for row, child in enumerate(self.winfo_children()):
            child.grid(row=row, sticky="w")
            if isinstance(child, ttk.Label) and child['style'] == "Heading.TLabel":
                child.grid(pady=PADDING)
            if isinstance(child, ttk.Entry) and not isinstance(child, ttk.Spinbox):
                child.grid(columnspan=2, sticky="ew")
        archive_e1.grid(columnspan=1)
        archive_b1.grid(row=16, column=1, sticky="e")

    def ask_archive(self):
        """Open file picker to get path of archive file."""
        a = self.archive.get()
        a_path = os.path.abspath(a)
        if a and os.path.exists(a_path):
            init = a_path
        else:
            init = os.path.expanduser("~")

        if os.path.isfile(init):
            path = filedialog.asksaveasfilename(
                parent=self,
                title="Open archive file",
                initialfile=init
            )
        else:
            path = filedialog.asksaveasfilename(
                parent=self,
                title="Open archive file",
                initialdir=init
            )

        if path:
            # For now no safe guard is in place, so just give visual feedback
            try:
                with open(path, "r") as f:
                    _ = f.read(1)
            except FileNotFoundError:
                pass
            except (OSError, UnicodeError):
                path = "Error: Can't decode file"

            self.archive.set(path)

    def apply_values(self):
        """Apply internal values to global options."""
        coub.opts.prompt = None if not self.prompt.get() else self.prompt.get()
        coub.opts.repeat = self.repeat.get()
        coub.opts.duration = None if not self.dur.get() else self.dur.get()
        coub.opts.preview = None if not self.preview.get() else self.preview.get()
        coub.opts.archive = None if not self.archive.get() else self.archive.get()
        coub.opts.keep = self.keep.get()
        coub.opts.recoubs = self.recoubs.get()


class DownloadSettings(ttk.Frame):
    """Frame holding download options in the settings window."""

    def __init__(self, master):
        super(DownloadSettings, self).__init__(master, padding=PADDING)
        self.columnconfigure(0, weight=1)

        self.conn = IntVar()
        self.retry = IntVar()
        self.max = IntVar()

        self.conn.set(coub.opts.connections)
        self.retry.set(coub.opts.retries)
        self.max.set(0 if not coub.opts.max_coubs else coub.opts.max_coubs)

        # Connections
        ttk.Label(self, text="Connections", style="Heading.TLabel")
        ttk.Label(self, text="How many connections to use (>100 not recommended)")
        ttk.Spinbox(self, from_=1, textvariable=self.conn)
        # Retries
        ttk.Label(self, text="Retries", style="Heading.TLabel")
        ttk.Label(self, text="How often to reconnect to Coub after connection loss"
                             " (<0 for infinite retries)")
        ttk.Spinbox(self, from_=-9999, textvariable=self.retry)
        # Limit coubs
        ttk.Label(self, text="Limit Quantity", style="Heading.TLabel")
        ttk.Label(self, text="How many coub links to parse (0 for no limit)")
        ttk.Spinbox(self, from_=0, textvariable=self.max)

        for row, child in enumerate(self.winfo_children()):
            child.grid(row=row, sticky="w")
            if isinstance(child, ttk.Label) and child['style'] == "Heading.TLabel":
                child.grid(pady=PADDING)

    def apply_values(self):
        """Apply internal values to global options."""
        coub.opts.connections = self.conn.get()
        coub.opts.retries = self.retry.get()
        coub.opts.max_coubs = None if not self.max.get() else self.max.get()


class QualitySettings(ttk.Frame):
    """Frame holding quality options in the settings window."""

    def __init__(self, master):
        super(QualitySettings, self).__init__(master, padding=PADDING)
        self.columnconfigure(0, weight=1)

        self.vq = IntVar()
        self.aq = IntVar()
        self.vmax = StringVar()
        self.vmin = StringVar()
        self.aac = IntVar()
        self.a_only = BooleanVar()
        self.v_only = BooleanVar()
        self.share = BooleanVar()

        self.vq.set(coub.opts.v_quality)
        self.aq.set(coub.opts.v_quality)
        self.vmax.set(coub.opts.v_max)
        self.vmin.set(coub.opts.v_min)
        self.aac.set(coub.opts.aac)
        self.a_only.set(coub.opts.a_only)
        self.v_only.set(coub.opts.v_only)
        self.share.set(coub.opts.share)

        # Video quality
        ttk.Label(self, text="Video Quality", style="Heading.TLabel")
        ttk.Label(self, text="Which video quality to download")
        self.vq_r1 = ttk.Radiobutton(self, text="Best quality", value=-1)
        self.vq_r2 = ttk.Radiobutton(self, text="Worst quality", value=0)
        for widget in [self.vq_r1, self.vq_r2]:
            widget.configure(variable=self.vq)
        # Max video quality
        ttk.Label(self, text="Limit max. video quality")
        self.vmax_r1 = ttk.Radiobutton(self, text="higher", value="higher")
        self.vmax_r2 = ttk.Radiobutton(self, text="high", value="high")
        self.vmax_r3 = ttk.Radiobutton(self, text="med", value="med")
        for rad in [self.vmax_r1, self.vmax_r2, self.vmax_r3]:
            rad.configure(variable=self.vmax, command=self.update_widgets)
        # Min video quality
        ttk.Label(self, text="Limit min. video quality")
        self.vmin_r1 = ttk.Radiobutton(self, text="higher", value="higher")
        self.vmin_r2 = ttk.Radiobutton(self, text="high", value="high")
        self.vmin_r3 = ttk.Radiobutton(self, text="med", value="med")
        for widget in [self.vmin_r1, self.vmin_r2, self.vmin_r3]:
            widget.configure(variable=self.vmin, command=self.update_widgets)
        # Audio quality
        ttk.Label(self, text="Audio Quality", style="Heading.TLabel")
        ttk.Label(self, text="Which audio quality to download")
        self.aq_r1 = ttk.Radiobutton(self, text="Best quality", value=-1)
        self.aq_r2 = ttk.Radiobutton(self, text="Worst quality", value=0)
        for widget in [self.aq_r1, self.aq_r2]:
            widget.configure(variable=self.aq)
        # Audio format
        ttk.Label(self, text="How much to prefer AAC over MP3")
        self.aac_r1 = ttk.Radiobutton(self, text="Only MP3", value=0)
        self.aac_r2 = ttk.Radiobutton(self, text="No Bias", value=1)
        self.aac_r3 = ttk.Radiobutton(self, text="Prefer AAC", value=2)
        self.aac_r4 = ttk.Radiobutton(self, text="Only AAC", value=3)
        for widget in [self.aac_r1, self.aac_r2, self.aac_r3, self.aac_r4]:
            widget.configure(variable=self.aac)
        # Special formats
        ttk.Label(self, text="Special Download Formats", style="Heading.TLabel")
        self.a_only_b1 = ttk.Checkbutton(self, text="Download only audio streams",
                                         variable=self.a_only)
        self.v_only_b1 = ttk.Checkbutton(self, text="Download only video streams",
                                         variable=self.v_only)
        self.share_b1 = ttk.Checkbutton(self, text="Download 'share' version",
                                        variable=self.share)
        for widget in [self.a_only_b1, self.v_only_b1, self.share_b1]:
            widget.configure(command=self.update_widgets)

        # Update widgets in case of v_only/a_only/share via config file
        self.update_widgets()

        for row, child in enumerate(self.winfo_children()):
            child.grid(row=row, sticky="w")
            if isinstance(child, ttk.Label):
                child.grid(pady=PADDING)

    def update_widgets(self):
        """Update widgets to avoid mutually exclusive value pairings."""
        v_state = "disabled" if self.a_only.get() or self.share.get() else "normal"
        a_state = "disabled" if self.v_only.get() or self.share.get() else "normal"
        s_state = "disabled" if self.a_only.get() or self.v_only.get() else "normal"

        vmax_high = v_state if self.vmin.get() not in {"higher"} else "disabled"
        vmax_med = v_state if self.vmin.get() not in {"higher", "high"} else "disabled"
        vmin_high = v_state if self.vmax.get() not in {"med"} else "disabled"
        vmin_higher = v_state if self.vmax.get() not in {"high", "med"} else "disabled"

        self.vq_r1.configure(state=v_state)
        self.vq_r2.configure(state=v_state)
        self.aq_r1.configure(state=a_state)
        self.aq_r2.configure(state=a_state)
        self.vmax_r1.configure(state=v_state)
        self.vmax_r2.configure(state=vmax_high)
        self.vmax_r3.configure(state=vmax_med)
        self.vmin_r1.configure(state=vmin_higher)
        self.vmin_r2.configure(state=vmin_high)
        self.vmin_r3.configure(state=v_state)
        self.aac_r1.configure(state=a_state)
        self.aac_r2.configure(state=a_state)
        self.aac_r3.configure(state=a_state)
        self.aac_r4.configure(state=a_state)
        self.a_only_b1.configure(state=a_state)
        self.v_only_b1.configure(state=v_state)
        self.share_b1.configure(state=s_state)

    def apply_values(self):
        """Apply internal values to global options."""
        coub.opts.v_quality = self.vq.get()
        coub.opts.a_quality = self.aq.get()
        coub.opts.v_max = self.vmax.get()
        coub.opts.v_min = self.vmin.get()
        coub.opts.aac = self.aac.get()
        coub.opts.a_only = self.a_only.get()
        coub.opts.v_only = self.v_only.get()
        coub.opts.share = self.share.get()


class OutputSettings(ttk.Frame):
    """Frame holding output options in the settings window."""

    def __init__(self, master):
        super(OutputSettings, self).__init__(master, padding=PADDING)
        self.columnconfigure(0, weight=1)

        self.o_list = StringVar()
        self.path = StringVar()
        self.ext = StringVar()
        self.name = StringVar()

        self.o_list.set("" if not coub.opts.output_list else coub.opts.output_list)
        self.path.set(coub.opts.path)
        self.ext.set(coub.opts.merge_ext)
        self.name.set("%id%" if not coub.opts.name_template else coub.opts.name_template)

        # Output list
        ttk.Label(self, text="Output to List", style="Heading.TLabel")
        ttk.Label(self, text="Output all parsed links to a list (no download)")
        ttk.Entry(self, textvariable=self.o_list)
        ttk.Button(self, text="Browse", command=self.ask_list)
        # Output path
        ttk.Label(self, text="Output Directory", style="Heading.TLabel")
        ttk.Label(self, text="Where to save downloaded coubs")
        ttk.Entry(self, textvariable=self.path)
        ttk.Button(self, text="Browse", command=self.ask_path)
        # Merge extension
        ttk.Label(self, text="Output Container", style="Heading.TLabel")
        ttk.Label(self, text="What extension to use for merged output files\n"
                             "(has no effect if no merge is required)")
        ttk.Combobox(self, textvariable=self.ext, state="readonly",
                     values=("mkv", "mp4", "asf", "avi", "flv", "f4v", "mov"))
        # Name template
        ttk.Label(self, text="Name Template", style="Heading.TLabel")
        ttk.Label(self, text="Change the naming convention of output files")
        ttk.Entry(self, textvariable=self.name).grid(columnspan=2)

        for row, child in enumerate(self.winfo_children()):
            child.grid(row=row, sticky="w")
            if isinstance(child, ttk.Label) and child['style'] == "Heading.TLabel":
                child.grid(pady=PADDING)
            elif isinstance(child, ttk.Entry) and not isinstance(child, ttk.Combobox):
                child.grid(sticky="ew")
            elif isinstance(child, ttk.Button):
                child.grid(row=row-1, column=1, sticky="e")

    def ask_list(self):
        """Open filepicker to get output list path."""
        l = self.o_list.get()
        l_path = os.path.abspath(l)
        if l and os.path.exists(l_path):
            init = l_path
        else:
            init = os.path.expanduser("~")

        if os.path.isfile(init):
            path = filedialog.asksaveasfilename(
                parent=self,
                title="Save links to file",
                initialfile=init,
            )
        else:
            path = filedialog.asksaveasfilename(
                parent=self,
                title="Save links to file",
                initialdir=init,
            )

        if path:
            # For now no safe guard is in place, so just give visual feedback
            try:
                with open(path, "r") as f:
                    _ = f.read(1)
            except FileNotFoundError:
                pass
            except (OSError, UnicodeError):
                path = "Error: Can't decode file"

            self.o_list.set(path)

    def ask_path(self):
        """Open directory picker to get output directory."""
        p = self.path.get()
        if p and os.path.exists(os.path.abspath(p)):
            init = os.path.abspath(p)
        else:
            init = os.path.join(os.path.expanduser("~"), "coubs")
        path = filedialog.askdirectory(
            parent=self,
            title="Choose output destination",
            initialdir=init
        )
        if path:
            self.path.set(path)

    def apply_values(self):
        """Apply internal values to global options."""
        o_list = self.o_list.get()
        path = self.path.get()
        name = self.name.get()

        # Last safeguard to prevent empty path
        fallback_path = os.path.join(os.path.expanduser("~"), "coubs")

        coub.opts.output_list = None if not o_list else o_list
        coub.opts.path = fallback_path if not path else path
        coub.opts.merge_ext = self.ext.get()
        coub.opts.name_template = None if name == "%id%" else name


class SettingsWindow(Toplevel):
    """Window to allow user to change settings."""

    def __init__(self):
        super(SettingsWindow, self).__init__(padx=PADDING, pady=PADDING/2)
        self.title("Settings")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        notebook = ttk.Notebook(self)
        general = GeneralSettings(self)
        down = DownloadSettings(self)
        quality = QualitySettings(self)
        output = OutputSettings(self)
        ok = ttk.Button(self, text="OK", command=self.ok_press)
        cancel = ttk.Button(self, text="Cancel", command=self.destroy)

        notebook.add(general, text="General", sticky="nesw")
        notebook.add(down, text="Download", sticky="nesw")
        notebook.add(quality, text="Quality", sticky="nesw")
        notebook.add(output, text="Output", sticky="nesw")

        notebook.grid(row=0, columnspan=3, sticky="news", pady=PADDING/2)
        ok.grid(row=1, column=1, padx=PADDING, pady=PADDING/2)
        cancel.grid(row=1, column=2, pady=PADDING/2)

    def ok_press(self):
        """Apply values of all settings frames to global options."""
        for child in self.winfo_children():
            if isinstance(child, ttk.Frame):
                child.apply_values()
        self.destroy()


class ScrolledText(ttk.Frame):
    """Custom version of ScrolledText with less hacks and modern Scrollbar."""

    def __init__(self, master, **kwargs):
        super(ScrolledText, self).__init__(master)
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        self.text = Text(self, **kwargs)
        self.scroll = ttk.Scrollbar(self, command=self.text.yview)
        self.text.configure(yscrollcommand=self.scroll.set)

        self.text.grid(sticky="nesw")
        self.scroll.grid(row=0, column=1, sticky="ns")


class HelpWindow(Toplevel):
    """Window to hold help and about text."""

    ABOUT = dedent(
        """
        CoubDownloader

        A simple downloader for coub.com

        https://github.com/HelpSeeker/CoubDownloader
        """
    )

    LICENSE = dedent(
        """
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
    )

    def __init__(self):
        super(HelpWindow, self).__init__(padx=PADDING, pady=PADDING)
        self.title("Help")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        notebook = ttk.Notebook(self)
        notebook.grid(sticky="nesw")

        about = ScrolledText(self, width=72, height=16)
        about.text.insert("1.0", self.ABOUT, ("centered"))
        about.text.tag_configure("centered", justify="center")
        about.text.configure(state="disabled")

        gplv3 = ScrolledText(self, width=72, height=16)
        gplv3.text.insert("1.0", self.LICENSE)
        gplv3.text.configure(state="disabled")

        basic = ScrolledText(self, width=72, height=16, wrap="word")
        basic.text.insert("1.0", manual.GENERAL)
        basic.text.configure(state="disabled")

        sources = ScrolledText(self, width=72, height=16, wrap="word")
        sources.text.insert("1.0", manual.INPUT)
        sources.text.configure(state="disabled")

        notebook.add(basic, text="General", sticky="nesw", padding=PADDING)
        notebook.add(sources, text="Input", sticky="nesw", padding=PADDING)
        notebook.add(about, text="About", sticky="nesw", padding=PADDING)
        notebook.add(gplv3, text="License", sticky="nesw", padding=PADDING)


class InputTree(ttk.Treeview):
    """Treeview to visualize all added input sources."""

    def __init__(self, master):
        super(InputTree, self).__init__(master)
        self.configure(
            columns=("type", "name", "sort"),
            show="headings",
            selectmode="browse",
            height=6,
        )

        self.column("type")
        self.column("name")
        self.column("sort")
        self.heading("type", text="Type")
        self.heading("name", text="Name")
        self.heading("sort", text="Sort")

        self.sources = {}

        self.tag_configure("alternate", background="#f0f0ff")

    def update_format(self):
        """Update colorized lines for newest changes."""
        for row, item in enumerate(self.get_children(), start=1):
            if not row % 2:
                self.item(item, tags=("alternate"))
            else:
                self.item(item, tags=())

    def add_item(self, source=None):
        """Add new item and/or update list view."""
        if source:
            item = self.insert("", "end")
            if isinstance(source, str):
                self.set(item, "type", "link")
                self.set(item, "name", source)
            else:
                self.set(item, "type", source.type)
                self.set(item, "name", source.id)
                self.set(item, "sort", source.sort)
            self.sources[item] = source
            self.update_format()

    def delete_item(self, *args):
        """Remove selected source from list."""
        selection = self.focus()
        if selection:
            self.delete(selection)
            del self.sources[selection]
            self.update_format()

    def edit_item(self, old=None, new=None):
        """Edit already existing source."""
        if old:
            if not new:
                self.delete(old)
                del self.sources[old]
            elif isinstance(new, str):
                self.set(old, "type", "link")
                self.set(old, "name", new)
                self.sources[old] = new
            else:
                self.set(old, "type", new.type)
                self.set(old, "name", new.id)
                self.set(old, "sort", new.sort)
                self.sources[old] = new
            self.update_format()


class InputFrame(ttk.Frame):
    """Frame to hold InputTree and its scrollbar widget."""

    def __init__(self, master):
        super(InputFrame, self).__init__(master)
        self.columnconfigure(0, weight=1)

        self.tree = InputTree(self)
        self.scroll = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=self.scroll.set)
        self.tree.grid(sticky="nesw")

    def update_widgets(self):
        """Enable/disable scrollbar based on treeview item quantity."""
        if len(self.tree.get_children()) > self.tree['height']:
            self.scroll.grid(row=0, column=1, sticky="ns")
        else:
            self.scroll.grid_forget()


class OutputFrame(ScrolledText):
    """Textbox to redirect stdout and stderr to."""

    def __init__(self, master):
        super(OutputFrame, self).__init__(master)
        self.text.configure(height=15, width=50, state="disabled")

    def write(self, text):
        """Print received text."""
        # Disabling a textbox also deactivates its insert method
        self.text.configure(state="normal")
        self.text.insert("end", text)
        self.text.see("end")
        self.flush()
        self.text.configure(state="disabled")

    def flush(self):
        """Refresh textbox to print in realtime."""
        self.text.update_idletasks()

    def clear(self):
        """Clear all text from the textbox."""
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")


class MainWindow(ttk.Frame):
    """Frame to hold the main interface."""

    def __init__(self, master):
        super(MainWindow, self).__init__(master)
        self.configure(padding=(PADDING, PADDING, PADDING, 0))
        self.rowconfigure(2, weight=1)
        self.columnconfigure(3, weight=1)
        self.grid(sticky="news")

        self.input = InputFrame(self)
        new_url = ttk.Button(self, text="New URL", command=self.new_url_press)
        new_item = ttk.Button(self, text="New Item", command=self.new_item_press)
        self.edit_item = ttk.Button(self, text="Edit Item",
                                    command=self.edit_item_press)
        prefs = ttk.Button(self, text="Settings", command=self.settings_press)
        about = ttk.Button(self, text="Help", command=HelpWindow)
        output = OutputFrame(self)
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
        dialog = NewURLWindow()
        self.wait_window(dialog)
        self.input.tree.add_item(dialog.get())
        self.update_widgets()

    def new_item_press(self, *args):
        """"Open new item window."""
        dialog = NewItemWindow()
        self.wait_window(dialog)
        self.input.tree.add_item(dialog.get())
        self.update_widgets()

    def edit_item_press(self, *args):
        """Open edit item window."""
        selection = self.input.tree.focus()
        if selection:
            dialog = EditItemWindow(self.input.tree.item(selection))
            self.wait_window(dialog)
            self.input.tree.edit_item(selection, dialog.get())
            self.update_widgets()

    def settings_press(self):
        """Open settings window."""
        dialog = SettingsWindow()
        self.wait_window(dialog)

    def start_press(self):
        """Start coub process in a separate thread."""
        coub.total = 0
        coub.count = 0
        coub.done = 0
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
