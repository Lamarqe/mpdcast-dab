# Copyright (C) 2024 Lamarqe
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License
# as published by the Free Software Foundation, version 3.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty
# of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""This module retrieves stream metadata from TvHeadend."""

import json
import time
import logging
import aiohttp
import yarl
import typing
from typing import NotRequired

from .mpd_caster import CastData

logger = logging.getLogger(__name__)

ShowDetails = typing.TypedDict('ShowDetails', {'eventId': int, 'channelName': NotRequired[str], 'channelUuid': str,
              'channelNumber': NotRequired[str], 'channelIcon': NotRequired[str], 'start': int,
              'stop': int, 'title': NotRequired[str], 'subtitle': NotRequired[str], 'description': NotRequired[str],
              'widescreen': int, 'subtitled': int, 'audiodesc': int,
              'hd': int, 'ageRating': int, 'genre': list[int], 'nextEventId': NotRequired[int]})

ChannelData = typing.TypedDict('ChannelData', {'uuid': str, 'enabled': bool, 'autoname': bool, 'name': str,
              'number': NotRequired[int], 'icon': str, 'icon_public_url': NotRequired[str], 'epgauto': bool,
              'epglimit': int, 'dvr_pre_time': int, 'dvr_pst_time': int,
              'epg_tuning': int, 'remote_timeshift': bool, 'services': list[str],
              'tags': list[str], 'bouquet': str})

supported_stream_links = {'channelnumber': 'number', 'channelname': 'name', 'channel': 'uuid'}

class TvheadendChannel():
  """
  Connector to interact with Tvheadend.
  Handle playlist items like: http://<tvh_server>:9981/stream/channelname/BAYERN%203
  """

  def __init__(self, song_urlstring: str) -> None:
    self.song_url:      yarl.URL           = yarl.URL(song_urlstring)
    self._initialized:  bool               = False
    self._channel_data: ChannelData | None = None
    self._show_end:     int | None         = None

  async def initialize(self) -> bool:
    logger.info('initializing tvheadend server')
    self._initialized = True
    channel_path_items = self.song_url.path_qs.split('/')

    if (len(channel_path_items) == 4
      and channel_path_items[1] == 'stream'
      and channel_path_items[2] in supported_stream_links):

      filter_field = supported_stream_links[channel_path_items[2]]
      channel_id = channel_path_items[3]

      data = {}
      data['start'] = '0'
      data['limit'] ='1'
      data['sort']  ='name'
      data['dir']    = 'ASC'
      filter1 = {}
      filter1['type'] = 'string'
      filter1['value'] = channel_id
      filter1['field'] = filter_field
      filter2 = {}
      filter2['type'] = 'string'
      filter2['value'] = 'Radio'
      filter2['field'] = 'tags'
      filters = [filter1, filter2]
      data['filter'] = json.dumps(filters)
      channel_url = self.song_url.with_path('api/channel/grid')

      async with aiohttp.ClientSession() as session:
        async with session.post(channel_url, data=data) as channel_response:
          channel_json = await channel_response.json()

      # Make sure the channel id is really equal (dont use "QVC ZWEI" instead of "QVC")
      for entry in channel_json['entries']:
        if entry[filter_field] == channel_id:
          self._channel_data = entry
          return True
    # channel was not found
    return False

  async def fill_cast_data(self, cast_data: CastData) -> bool:
    if not self._initialized:
      return False
    tvheadend_image_url = await self.image_url()
    if tvheadend_image_url:
      cast_data.image_url = tvheadend_image_url
    else:
      cast_data.image_url = 'https://www.radio.de/assets/images/app-stores/square_512x512_playstore.png'

    show_details = await self.current_show()
    if show_details:
      if 'title' in show_details:
        cast_data.title = show_details['title']
      if 'subtitle' in show_details:
        cast_data.artist = show_details['subtitle']
      self._show_end = int(show_details['stop'])
    else:
      # No EPG data. Show only channel name
      cast_data.title = self.name()
    return True

  def get_remaining_show_time(self) -> int | None:
    if not self._show_end:
      return None
    return int(self._show_end - time.time())

  def name(self) -> str:
    assert self._channel_data
    return self._channel_data['name']

  async def current_show(self) -> ShowDetails | None:
    if not self._initialized:
      await self.initialize()

    if self._channel_data:
      data = {}
      data['start']   = '0'
      data['limit']   ='1'
      data['sort']    ='channelnumber'
      data['dir']     = 'ASC'
      data['mode']    = 'now'
      data['channel'] = self._channel_data['uuid']
      epg_url = self.song_url.with_path('api/epg/events/grid')

      async with aiohttp.ClientSession() as session:
        async with session.post(epg_url, data=data) as epg_response:
          epg_json = await epg_response.json()

      if 'entries' in epg_json and len(epg_json['entries']) > 0:
        show: ShowDetails = epg_json['entries'][0]
        return show

    return None

  async def image_url(self) -> str | None:
    if not self._initialized:
      await self.initialize()
    if not self._channel_data:
      return None

    if 'icon_public_url' in self._channel_data:
      image_path = self._channel_data['icon_public_url']
    else:
      image_path = 'static/img/logobig.png'
    return str(self.song_url.with_path(image_path))
