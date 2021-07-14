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
import json
import math
import pathlib
from urllib.parse import quote as urlquote
from urllib.parse import unquote as urlunquote

from aiohttp import ClientError

from core import checker
from core.settings import Settings

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Classes
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

class ContainerUnavailableError(Exception):
    pass


class APIResponseError(Exception):
    pass


class InvalidSortingError(Exception):
    pass


class BaseContainer:
    type = ""
    id = ""
    sort = ""
    supported = set()

    # Attempts are done on a per-page level, but the attempt limit is for all pages
    attempt = 0

    pages = 0

    PER_PAGE = 25

    def __init__(self, id_, sort):
        # Links copied from the browser already have special characters escaped
        # Using urlquote again leads to invalid templates
        self.id = urlunquote(id_)
        self.sort = sort

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            # Not necessary to check type again, as it is a unique class trait
            return (self.id, self.sort) == (other.id, other.sort)
        return False

    def __hash__(self):
        return hash((self.type, self.id, self.sort))

    def _get_template(self):
        if self.sort not in self.supported:
            raise InvalidSortingError from None

        return ""

    async def _fetch_page_count(self, request, session):
        try:
            async with session.get(request) as response:
                api_json = json.loads(await response.read())
                if api_json.get("error") is not None:
                    raise ContainerUnavailableError from None
                self.pages = api_json.get("total_pages")
        except ClientError:
            raise APIResponseError from None

    async def _fetch_api_json(self, request, session):
        try:
            async with session.get(request) as response:
                api_json = await response.read()
                api_json = json.loads(api_json)
        except ClientError:
            api_json = None

        return api_json

    async def _fetch_page_ids(self, request, session):
        retries = Settings.get().retries
        while retries < 0 or self.attempt <= retries:
            api_json = await self._fetch_api_json(request, session)
            if api_json:
                break
            self.attempt += 1

        if not api_json:
            raise APIResponseError from None

        ids = []
        for coub in api_json["coubs"]:
            if coub["recoub_to"]:
                c_id = coub["recoub_to"]["permalink"]
            else:
                c_id = coub["permalink"]

            if not (checker.in_archive(c_id) or checker.in_session(c_id)):
                ids.append(c_id)

        return ids

    async def get_ids(self, session, quantity):
        base_request = self._get_template()
        await self._fetch_page_count(base_request, session)

        # TODO: Rewrite logic to stop prematurely on quantity instead of limiting pages
        #       (same for Gyre)
        if quantity:
            max_pages = math.ceil(quantity/self.PER_PAGE)
            if self.pages > max_pages:
                self.pages = max_pages

        requests = [f"{base_request}&page={p}" for p in range(1, self.pages+1)]
        tasks = [self._fetch_page_ids(r, session) for r in requests]
        ids = await asyncio.gather(*tasks)
        ids = [i for page in ids for i in page]

        if quantity:
            return ids[:quantity]
        return ids


class SingleCoub(BaseContainer):
    type = "coub"

    def __init__(self, id_, sort=""):
        super().__init__(id_, sort)

    # async is unnecessary here, but avoids the need for special treatment
    async def get_ids(self, session, quantity):
        # Only here to test if coub exists
        await self._fetch_page_count(f"https://coub.com/api/v2/coubs/{self.id}", session)

        # TODO: Add check to Gyre
        if not (checker.in_archive(self.id) or checker.in_session(self.id)):
            return [self.id]
        return []


class LinkList(BaseContainer):
    type = "list"

    def __init__(self, id_, sort=""):
        super().__init__(id_, sort)
        self.list = pathlib.Path(id_)
        self.id = self.list.resolve()

    def _valid_list_file(self):
        # Avoid using path object methods as they always read the whole file
        with self.list.open("r") as f:
            _ = f.read(1)

    # async is unnecessary here, but avoids the need for special treatment
    async def get_ids(self, session, quantity):
        self._valid_list_file()

        ids = self.list.read_text().splitlines()
        ids = [i for i in ids if i.startswith("https://coub.com/view/")]
        ids = [i.replace("https://coub.com/view/", "") for i in ids]
        # TODO: Add check to Gyre
        ids = [i for i in ids if not (checker.in_archive(i) or checker.in_session(i))]

        if quantity:
            return ids[:quantity]
        return ids


class Channel(BaseContainer):
    type = "channel"
    supported = {"newest", "likes_count", "views_count", "oldest", "random"}

    def __init__(self, id_, sort="newest"):
        super().__init__(id_, sort)

    def _get_template(self):
        super()._get_template()
        template = f"https://coub.com/api/v2/timeline/channel/{urlquote(self.id)}"
        template = f"{template}?per_page={self.PER_PAGE}"

        if not Settings.get().recoubs:
            template = f"{template}&type=simples"
        elif Settings.get().recoubs == 2:
            template = f"{template}&type=recoubs"

        template = f"{template}&order_by={self.sort}"

        return template


class Tag(BaseContainer):
    type = "tag"
    supported = {"newest_popular", "likes_count", "views_count", "newest"}

    def __init__(self, id_, sort="newest_popular"):
        super().__init__(id_, sort)

    def _get_template(self):
        super()._get_template()
        template = f"https://coub.com/api/v2/timeline/tag/{urlquote(self.id)}"
        template = f"{template}?per_page={self.PER_PAGE}&order_by={self.sort}"

        return template

    async def _fetch_page_count(self, request, session):
        await super()._fetch_page_count(request, session)
        # API limits tags to 99 pages
        if self.pages > 99:
            self.pages = 99


class Search(BaseContainer):
    type = "search"
    supported = {"relevance", "likes_count", "views_count", "newest"}

    def __init__(self, id_, sort="relevance"):
        super().__init__(id_, sort)

    def _get_template(self):
        super()._get_template()
        template = f"https://coub.com/api/v2/search/coubs?q={urlquote(self.id)}"
        template = f"{template}&per_page={self.PER_PAGE}"

        if self.sort != "relevance":
            template = f"{template}&order_by={self.sort}"

        return template


class Community(BaseContainer):
    type = "community"
    supported = {
        "daily",
        "weekly",
        "monthly",
        "quarter",
        "half",
        "rising",
        "fresh",
        "likes_count",
        "views_count",
        "random",
    }

    def __init__(self, id_, sort="monthly"):
        super().__init__(id_, sort)

    def _get_template(self):
        super()._get_template()
        template = f"https://coub.com/api/v2/timeline/community/{urlquote(self.id)}"

        if self.sort in ("likes_count", "views_count"):
            template = f"{template}/fresh?order_by={self.sort}&"
        elif self.sort == "random":
            template = f"https://coub.com/api/v2/timeline/random/{self.id}?"
        else:
            template = f"{template}/{self.sort}?"

        template = f"{template}per_page={self.PER_PAGE}"

        return template

    async def _fetch_page_count(self, request, session):
        await super()._fetch_page_count(request, session)
        # API limits communities to 99 pages
        if self.pages > 99:
            self.pages = 99


class Featured(Community):
    supported = {"recent", "top_of_the_month", "undervalued"}

    def __init__(self, id_="", sort="recent"):
        super().__init__(id_, sort)

    def _get_template(self):
        super()._get_template()
        template = "https://coub.com/api/v2/timeline/explore?"

        if self.sort != "recent":
            template = f"{template}order_by={self.sort}&"

        template = f"{template}per_page={self.PER_PAGE}"

        return template


class CoubOfTheDay(Community):
    supported = {"recent", "top", "views_count"}

    def __init__(self, id_="", sort="recent"):
        super().__init__(id_, sort)

    def _get_template(self):
        super()._get_template()
        template = "https://coub.com/api/v2/timeline/explore/coub_of_the_day?"

        if self.sort != "recent":
            template = f"{template}order_by={self.sort}&"

        template = f"{template}per_page={self.PER_PAGE}"

        return template


class Story(BaseContainer):
    type = "story"
    PER_PAGE = 20

    def __init__(self, id_, sort=""):
        super().__init__(id_, sort)

    def _get_template(self):
        # Story URL contains ID + title separated by a dash
        template = f"https://coub.com/api/v2/stories/{self.id.split('-')[0]}/coubs"
        template = f"{template}?per_page={self.PER_PAGE}"

        return template


class HotSection(BaseContainer):
    type = "Hot section"
    supported = {
        "daily",
        "weekly",
        "monthly",
        "quarter",
        "half",
        "rising",
        "fresh",
    }


    def __init__(self, id_="", sort="monthly"):
        super().__init__(id_, sort)

    def _get_template(self):
        super()._get_template()
        template = "https://coub.com/api/v2/timeline/subscriptions"
        template = f"{template}/{self.sort}?per_page={self.PER_PAGE}"

        return template

    async def _fetch_page_count(self, request, session):
        await super()._fetch_page_count(request, session)
        # API limits hot section to 99 pages
        if self.pages > 99:
            self.pages = 99


class Random(BaseContainer):
    type = "random coubs"
    supported = {"popular", "top"}

    def __init__(self, id_="", sort="popular"):
        super().__init__(id_, sort)

    def _get_template(self):
        super()._get_template()
        template = "https://coub.com/api/v2/timeline/explore/random?"

        if self.sort != "popular":
            template = f"{template}order_by={self.sort}&"

        template = f"{template}per_page={self.PER_PAGE}"

        return template

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Functions
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# def create_container(type, id_, sort, quantity):
#     args = {}
#     if id_:
#         args["id"] = id_
#     if sort:
#         args["sort"] = sort
#     if quantity:
#         args["quantity"] = quantity

#     if type == "Coub":
#         return SingleCoub(**args)
#     if type == "List":
#         return LinkList(**args)
#     if type == "Channel":
#         return Channel(**args)
#     if type == "Tag":
#         return Tag(**args)
#     if type == "Search":
#         return Search(**args)
#     if type == "Community":
#         return Community(**args)
#     if type == "Featured":
#         return Featured(**args)
#     if type == "Coub of the Day":
#         return CoubOfTheDay(**args)
#     if type == "Story":
#         return Story(**args)
#     if type == "Hot Section":
#         return HotSection(**args)
#     if type == "Random":
#         return Random(**args)
