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

from math import ceil
from os.path import abspath
from ssl import SSLContext

import urllib.error
from urllib.request import urlopen
from urllib.parse import quote as urlquote
from urllib.parse import unquote as urlunquote

import aiohttp

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Global Variables
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

PER_PAGE = 25
RECOUBS = None
CONTEXT = SSLContext()
CANCELLED = False

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Classes
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

class BaseContainer:
    """Base class for link containers (timelines)."""
    type = None

    def __init__(self, id_):
        self.valid = True
        self.error = ""
        self.pages = 0
        self.max_pages = 0
        self.template = ""

        try:
            self.id, self.sort = id_.split("#")
        except ValueError:
            self.id = id_
            self.sort = None

        # Links copied from the browser already have special characters escaped
        # Using urlquote on them again in the template functions would lead
        # to invalid templates
        # Also prettifies messages that show the ID as info
        self.id = urlunquote(self.id)

    def get_template(self):
        """Placeholder function, which must be overwritten by subclasses."""
        self.template = ""

    def get_pages(self):
        """Contact API once to get page count and check validity."""
        # BaseContainer cannot be invalid at this point, but its ancestors can
        if not self.valid:
            return

        try:
            with urlopen(self.template, context=CONTEXT) as resp:
                resp_json = json.loads(resp.read())
        except urllib.error.HTTPError:
            self.error = f"Invalid {self.type} ('{self.id}')!"
            self.valid = False
            return

        self.pages = resp_json['total_pages']

    def prepare(self, quantity):
        """Get all relevant values for processing."""
        self.get_template()
        self.get_pages()

        if quantity:
            self.max_pages = ceil(quantity/PER_PAGE)
            if self.pages < self.max_pages:
                self.max_pages = self.pages
        else:
            self.max_pages = self.pages

    async def process(self, connections, quantity):
        """
        Parse the coub links from tags, channels, etc.

        The Coub API refers to the list of coubs from a tag, channel,
        community, etc. as a timeline.
        """
        requests = [f"{self.template}&page={p}" for p in range(1, self.max_pages+1)]

        tout = aiohttp.ClientTimeout(total=None)
        conn = aiohttp.TCPConnector(limit=connections, ssl=CONTEXT)
        async with aiohttp.ClientSession(timeout=tout, connector=conn) as session:
            tasks = [parse_page(req, session) for req in requests]
            ids = await asyncio.gather(*tasks)
        ids = [i for page in ids for i in page]

        if quantity:
            return ids[:quantity]
        return ids


class Channel(BaseContainer):
    """Store and parse channels."""
    type = "channel"

    def __init__(self, id_):
        super(Channel, self).__init__(id_)
        # Available:      most_recent, most_liked, most_viewed, oldest, random
        # Coub's default: most_recent
        if not self.sort:
            self.sort = "most_recent"
        self.recoubs = None

    def set_recoubs(self, recoubs):
        """Specify how channel recoubs should be handled."""
        self.recoubs = recoubs

    def get_template(self):
        """Return API request template for channels."""
        methods = {
            'most_recent': "newest",
            'most_liked': "likes_count",
            'most_viewed': "views_count",
            'oldest': "oldest",
            'random': "random",
        }

        template = f"https://coub.com/api/v2/timeline/channel/{urlquote(self.id)}"
        template = f"{template}?per_page={PER_PAGE}"

        if self.recoubs == 0:
            template = f"{template}&type=simples"
        elif self.recoubs == 2:
            template = f"{template}&type=recoubs"
        elif self.recoubs is None:
            self.valid = False
            self.error = f"Error: Recoub setting for {self.id} not set!"

        if self.sort in methods:
            template = f"{template}&order_by={methods[self.sort]}"
        else:
            self.error = f"Invalid channel sort order '{self.sort}' ({self.id})!"
            self.valid = False

        self.template = template


class Tag(BaseContainer):
    """Store and parse tags."""
    type = "tag"

    def __init__(self, id_):
        super(Tag, self).__init__(id_)
        # Available:      popular, top, views_count, fresh
        # Coub's default: popular
        if not self.sort:
            self.sort = "popular"

    def get_template(self):
        """Return API request template for tags."""
        methods = {
            'popular': "newest_popular",
            'top': "likes_count",
            'views_count': "views_count",
            'fresh': "newest"
        }

        template = f"https://coub.com/api/v2/timeline/tag/{urlquote(self.id)}"
        template = f"{template}?per_page={PER_PAGE}"

        if self.sort in methods:
            template = f"{template}&order_by={methods[self.sort]}"
        else:
            self.error = f"Invalid tag sort order '{self.sort}' ({self.id})!"
            self.valid = False

        self.template = template

    def get_pages(self):
        super(Tag, self).get_pages()
        # API limits tags to 99 pages
        if self.pages > 99:
            self.pages = 99


class Search(BaseContainer):
    """Store and parse searches."""
    type = "search"

    def __init__(self, id_):
        super(Search, self).__init__(id_)
        # Available:      relevance, top, views_count, most_recent
        # Coub's default: relevance
        if not self.sort:
            self.sort = "relevance"

    def get_template(self):
        """Return API request template for coub searches."""
        methods = {
            'relevance': None,
            'top': "likes_count",
            'views_count': "views_count",
            'most_recent': "newest"
        }

        template = f"https://coub.com/api/v2/search/coubs?q={urlquote(self.id)}"
        template = f"{template}&per_page={PER_PAGE}"

        if self.sort not in methods:
            self.error = f"Invalid search sort order '{self.sort}' ({self.id})!"
            self.valid = False
        # The default tab on coub.com is labelled "Relevance", but the
        # default sort order is actually no sort order
        elif self.sort != "relevance":
            template = f"{template}&order_by={methods[self.sort]}"

        self.template = template


class Community(BaseContainer):
    """Store and parse communities."""
    type = "community"

    def __init__(self, id_):
        super(Community, self).__init__(id_)
        # Available:      hot_daily, hot_weekly, hot_monthly, hot_quarterly,
        #                 hot_six_months, rising, fresh, top, views_count, random
        # Coub's default: hot_monthly
        if not self.sort:
            if self.id in ("featured", "coub-of-the-day"):
                self.sort = "recent"
            else:
                self.sort = "hot_monthly"

    def get_template(self):
        """Return API request template for communities."""
        if self.id == "featured":
            methods = {
                'recent': None,
                'top_of_the_month': "top_of_the_month",
                'undervalued': "undervalued",
            }
            template = "https://coub.com/api/v2/timeline/explore?"
        elif self.id == "coub-of-the-day":
            methods = {
                'recent': None,
                'top': "top",
                'views_count': "views_count",
            }
            template = "https://coub.com/api/v2/timeline/explore/coub_of_the_day?"
        else:
            methods = {
                'hot_daily': "daily",
                'hot_weekly': "weekly",
                'hot_monthly': "monthly",
                'hot_quarterly': "quarter",
                'hot_six_months': "half",
                'rising': "rising",
                'fresh': "fresh",
                'top': "likes_count",
                'views_count': "views_count",
                'random': "random",
            }
            template = f"https://coub.com/api/v2/timeline/community/{urlquote(self.id)}"

        if self.sort not in methods:
            self.error = f"Invalid community sort order '{self.sort}' ({self.id})!"
            self.valid = False
            return

        if self.id in ("featured", "coub-of-the-day"):
            if self.sort != "recent":
                template = f"{template}order_by={methods[self.sort]}&"
        else:
            if self.sort in ("top", "views_count"):
                template = f"{template}/fresh?order_by={methods[self.sort]}&"
            elif self.sort == "random":
                template = f"https://coub.com/api/v2/timeline/random/{self.id}?"
            else:
                template = f"{template}/{methods[self.sort]}?"

        self.template = f"{template}per_page={PER_PAGE}"

    def get_pages(self):
        super(Community, self).get_pages()
        # API limits communities to 99 pages
        if self.pages > 99:
            self.pages = 99


class Story(BaseContainer):
    """Store and parse stories."""
    type = "story"

    def __init__(self, id_):
        super(Story, self).__init__(id_)
        self.sort = None

    def get_template(self):
        # Story URL contains ID + title separated by a dash
        template = f"https://coub.com/api/v2/stories/{self.id.split('-')[0]}/coubs"
        template = f"{template}?per_page={PER_PAGE}"

        self.template = template


class HotSection(BaseContainer):
    """Store and parse the hot section."""
    type = "hot section"

    def __init__(self, sort=None):
        super(HotSection, self).__init__("hot")
        self.id = None
        self.sort = sort
        # Available:      hot_daily, hot_weekly, hot_monthly, hot_quarterly,
        #                 hot_six_months, rising, fresh
        # Coub's default: hot_monthly
        if not self.sort:
            self.sort = "hot_monthly"

    def get_template(self):
        """Return API request template for Coub's hot section."""
        methods = {
            'hot_daily': "daily",
            'hot_weekly': "weekly",
            'hot_monthly': "monthly",
            'hot_quarterly': "quarter",
            'hot_six_months': "half",
            'rising': "rising",
            'fresh': "fresh",
        }

        template = "https://coub.com/api/v2/timeline/subscriptions"

        if self.sort in methods:
            template = f"{template}/{methods[self.sort]}"
        else:
            self.error = f"Invalid hot section sort order '{self.sort}'!"
            self.valid = False

        template = f"{template}?per_page={PER_PAGE}"

        self.template = template

    def get_pages(self):
        super(HotSection, self).get_pages()
        # API limits hot section to 99 pages
        if self.pages > 99:
            self.pages = 99


class RandomCategory(BaseContainer):
    """Store and parse the random category."""
    type = "random"

    def __init__(self, sort=None):
        super(RandomCategory, self).__init__("random")
        self.id = None
        self.sort = sort
        # Available:      popular, top
        # Coub's default: popular
        if not self.sort:
            self.sort = "popular"

    def get_template(self):
        """Return API request template for Coub's random category."""
        methods = {
            'popular': None,
            'top': "top",
        }
        template = "https://coub.com/api/v2/timeline/explore/random?"

        if self.sort not in methods:
            self.error = f"Invalid random sort order '{self.sort}'!"
            self.valid = False
            return
        if self.sort == "top":
            template = f"{template}order_by={methods[self.sort]}&"

        self.template = f"{template}per_page={PER_PAGE}"


class LinkList:
    """Store and parse link lists."""
    type = "list"

    def __init__(self, path):
        self.valid = True
        self.id = abspath(path)
        try:
            with open(self.id, "r") as f:
                _ = f.read(1)
        except FileNotFoundError:
            self.error = f"Input list {self.id} doesn't exist!"
            self.valid = False
        except (OSError, UnicodeError):
            self.error = f"Invalid input list {self.id}!"
            self.valid = False

        self.sort = None
        self.length = 0

    async def process(self, quantity):
        """Parse coub links provided in via an external text file."""
        with open(self.id, "r") as f:
            content = f.read()

        # Replace tabs and spaces with newlines
        # Emulates default wordsplitting in Bash
        content = content.replace("\t", "\n")
        content = content.replace(" ", "\n")
        content = content.splitlines()

        links = [
            l.partition("https://coub.com/view/")[2]
            for l in content if "https://coub.com/view/" in l
        ]
        self.length = len(links)

        if quantity:
            return links[:quantity]
        return links

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Functions
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

async def parse_page(req, session):
    """Request a single timeline page and parse its content."""
    if CANCELLED:
        raise KeyboardInterrupt

    async with session.get(req) as resp:
        resp_json = await resp.read()
        resp_json = json.loads(resp_json)

    ids = [
        c['recoub_to']['permalink'] if c['recoub_to'] else c['permalink']
        for c in resp_json['coubs']
    ]
    return ids
