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

"""Module to load a local cast receiver app via a public redirect service in order to avoid CORS violations."""

import logging
import requests
from pychromecast.controllers.media import MediaController

from .web_sender_types import (Image, MusicTrackMediaMetadata, MediaInfo, QueueItem, QueueUpdateItemsRequest)

logger = logging.getLogger(__name__)

APP_LOCAL = "D29D8DD1"

class LocalMediaPlayerController(MediaController):
  """Controller to interact with local media player app."""

  def __init__(self, forward_url, update_initial=True):
    super().__init__()
    self.app_id = APP_LOCAL
    self.supporting_app_id = APP_LOCAL
    self.forward_url = forward_url
    if update_initial:
      self.update_local_receiver_path()

  def update_local_receiver_path(self):
    with requests.post(
      'https://lamarqe.pythonanywhere.com/storeforwardurl',
      data={'localForwardURL': self.forward_url},
      headers={"Content-Type": "application/x-www-form-urlencoded"},
      timeout=30.0
    ) as sid_response:
      logger.info(sid_response.text)


  def set_music_track_media_metadata(self, title=None, artist=None, image_url=None):
    images = [] if image_url is None else [Image(image_url)]
    metadata = MusicTrackMediaMetadata()
    metadata[MusicTrackMediaMetadata.TITLE]  = title
    metadata[MusicTrackMediaMetadata.ARTIST] = artist
    metadata[MusicTrackMediaMetadata.IMAGES] = images
    mediainfo = MediaInfo(self.status.content_id, self.status.content_type)
    mediainfo[MediaInfo.METADATA] = metadata
    queueitem = QueueItem(mediainfo)
    queueitem[QueueItem.ITEMID] = 1
    queue_update_items_request = QueueUpdateItemsRequest([queueitem])

    self._send_command(queue_update_items_request)

  def quick_play(self, media_id=None, media_type="video/mp4", **kwargs):
    self.play_media(media_id, media_type, **kwargs)
