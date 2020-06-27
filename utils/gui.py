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

from tkinter import Toplevel, StringVar
from tkinter import filedialog
from tkinter import ttk

from utils import container
from utils.options import mapped_input

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Global Variables
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

PADDING = 5

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Classes
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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
