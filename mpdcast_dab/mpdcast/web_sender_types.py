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

"""
This file replicates the google cast web sender message types.
Official documentation: https://developers.google.com/cast/docs/reference/web_sender
Relevant sub-package: chrome.cast.media

Currently, this file only contains a subset of all data types.
"""

from pychromecast import const
from pychromecast.controllers import media


class Image(dict):
  URL    = "url"
  HEIGHT = "height"
  WIDTH  = "width"

  def __init__(self, url: str) -> None:
    super().__init__()
    self[Image.URL]    = url
    self[Image.HEIGHT] = None
    self[Image.WIDTH]  = None


class MusicTrackMediaMetadata(dict):
  METADATATYPE = "metadataType"
  TYPE         = "type"
  ALBUMARTIST  = "albumArtist"
  ALBUMNAME    = "albumName"
  ARTIST       = "artist"
  ARTISTNAME   = "artistName"
  COMPOSER     = "composer"
  DISCNUMBER   = "discNumber"
  IMAGES       = "images"
  RELEASEDATE  = "releaseDate"
  RELEASEYEAR  = "releaseYear"
  SONGNAME     = "songName"
  TITLE        = "title"
  TRACKNUMBER  = "trackNumber"

  def __init__(self) -> None:
    super().__init__()
    self[MusicTrackMediaMetadata.METADATATYPE] = media.METADATA_TYPE_MUSICTRACK
    self[MusicTrackMediaMetadata.TYPE]         = media.METADATA_TYPE_MUSICTRACK


class MediaInfo(dict):
  CONTENTID      = "contentId"
  CONTENTTYPE    = "contentType"
  CUSTOMDATA     = "customData"
  DURATION       = "duration"
  METADATA       = "metadata"
  STREAMTYPE     = "streamType"
  TEXTTRACKSTYLE = "textTrackStyle"
  TRACKS         = "tracks"

  def __init__(self, contentId: str | None, contentType: str | None) -> None:
    super().__init__()
    self[MediaInfo.CONTENTID]      = contentId
    self[MediaInfo.CONTENTTYPE]    = contentType
    self[MediaInfo.CUSTOMDATA]     = None
    self[MediaInfo.DURATION]       = None
    self[MediaInfo.METADATA]       = None
    self[MediaInfo.STREAMTYPE]     = None
    self[MediaInfo.TEXTTRACKSTYLE] = None
    self[MediaInfo.TRACKS]         = None

class QueueItem(dict):
  MEDIA            = "media"
  ITEMID           = "itemId"
  AUTOPLAY         = "autoplay"
  STARTTIME        = "startTime"
  PLAYBACKDURATION = "playbackDuration"
  PRELOADTIME      = "preloadTime"
  ACTIVETRACKIDS   = "activeTrackIds"
  CUSTOMDATA       = "customData"

  def __init__(self, mediaInfo: MediaInfo) -> None:
    super().__init__()
    self[QueueItem.MEDIA]            = mediaInfo
    self[QueueItem.ITEMID]           = None
    self[QueueItem.AUTOPLAY]         = True
    self[QueueItem.STARTTIME]        = 0
    self[QueueItem.PLAYBACKDURATION] = None
    self[QueueItem.PRELOADTIME]      = 0
    self[QueueItem.ACTIVETRACKIDS]   = None
    self[QueueItem.CUSTOMDATA]       = None


class QueueUpdateItemsRequest(dict):
  CUSTOMDATA = "customData"
  ITEMS      = "items"

  def __init__(self, itemsToUpdate: list[QueueItem]) -> None:
    super().__init__()
    self[const.MESSAGE_TYPE]                 = media.TYPE_QUEUE_UPDATE
    self[QueueUpdateItemsRequest.ITEMS]      = itemsToUpdate
    self[QueueUpdateItemsRequest.CUSTOMDATA] = None
