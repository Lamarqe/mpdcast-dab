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

"""This module caches and serves MPD cover images for using them in the cast app"""

import urllib
from aiohttp import web


class ImageRequestHandler():
  URL_PREFIX = 'mpd_image/'

  def __init__(self, my_ip, port):
    self.my_ip  = my_ip
    self.port   = port
    self.images = {}

  def get_routes(self):
    return [web.get(r'/mpd_image/{song_path:.+}', self._http_handler)]

  def store_song_picture(self, song_path, picture_dict):
    self.images[song_path] = picture_dict
    return self._song_to_image_url(song_path)

  # Chromecast will use this http interface to get the actual images
  async def _http_handler(self, request):
    song_path = request.match_info['song_path']
    if not song_path in self.images:
      raise web.HTTPMovedPermanently('https://www.musicpd.org/logo.png')

    return web.Response(
      content_type = self.images[song_path]['type'],
      body         = self.images[song_path]['binary'])

  def _song_to_image_url(self, song_path):
    image_path = urllib.parse.quote(song_path)
    return 'http://' + self.my_ip + ':' + str(self.port) + '/' + ImageRequestHandler.URL_PREFIX + image_path
