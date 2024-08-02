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

"""MPD http server stream to google cast sync module."""

import asyncio
import time
import logging
import dataclasses
from zeroconf import Zeroconf
import pychromecast
import mpd.asyncio

from mpdcast_dab.cast_sender.imageserver import ImageRequestHandler
from mpdcast_dab.cast_sender.local_media_player import LocalMediaPlayerController, APP_LOCAL
from mpdcast_dab.cast_sender.cast_finder import CastFinder
from mpdcast_dab.cast_sender.tvheadend_connector import TvheadendChannel
from mpdcast_dab.cast_sender.dabserver_connector import DabserverStation

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class CastData():
  def __init__(self, title = None, artist = None, image_url = None):
    self.title     = title
    self.artist    = artist
    self.image_url = image_url

class MpdCaster(pychromecast.controllers.receiver.CastStatusListener,
                pychromecast.socket_client.ConnectionStatusListener,
                pychromecast.controllers.media.MediaStatusListener):
  """
  This class is reponsible to cast all media
  that is played on the mpd http server stream (defined via handed over config)
  to the chromecast device which is listed in the config

  Casting is activated using cast_forever.
  cast_forever returns as soon as the connection to the mpdclient instance is lost
  """


  @dataclasses.dataclass
  class CastStatus():
    def __init__(self):
      self.controller   = None
      self.chromecast   = None
      self.media_status = None
      self.media_event = asyncio.Event()

  @dataclasses.dataclass
  class UpdateTasks():
    def __init__(self):
      self.tvh_show  = None
      self.dab_label = None
      self.dab_image = None

  @dataclasses.dataclass
  class Config():
    def __init__(self, cast_url, cast_receiver_url, mpd_port, device_name):
      self.cast_receiver_url = cast_receiver_url
      self.mpd_port          = mpd_port
      self.device_name       = device_name
      self.cast_url          = cast_url
      self.default_image     = 'https://www.musicpd.org/logo.png'


  def __init__(self, cast_url, cast_receiver_url, mpd_port, device_name):
    self._config     = self.Config(cast_url, cast_receiver_url, mpd_port, device_name)
    self._updater    = self.UpdateTasks()
    self._cast       = self.CastStatus()
    self._image_server = ImageRequestHandler(cast_receiver_url.host, cast_receiver_url.port)
    self._mpd_client = mpd.asyncio.MPDClient()
    self._dabserver_current_station = None
    self._cast_finder   = None

  def waitfor_and_register_castdevice(self):
    if not self._cast.chromecast:
      self._cast_finder = CastFinder(self._config.device_name)
      self._cast_finder.do_discovery()
      if self._cast_finder.device:
        self._cast.chromecast = pychromecast.get_chromecast_from_cast_info(self._cast_finder.device, Zeroconf())

        self._cast.chromecast.wait()
        if self._cast.chromecast.app_id != pychromecast.IDLE_APP_ID:
          self._cast.chromecast.quit_app()
          time.sleep(0.5)
        self._cast.controller = LocalMediaPlayerController(str(self._config.cast_receiver_url), False)
        self._cast.chromecast.register_handler(self._cast.controller)  # allows Chromecast to use Local Media Player app
        self._cast.chromecast.register_connection_listener(self)  # await new_connection_status() => re-initialize
        self._cast.controller.register_status_listener(self)      # await new_media_status() / load_media_failed()
        #self._cast.chromecast.register_status_listener(self)     # await new_cast_status()  => not of interest

      self._cast_finder = None

  def new_media_status(self, status):
    self._cast.media_status = status
    if status.media_session_id:
      self._cast.media_event.set()

  def load_media_failed(self, queue_item_id, error_code):
    self._cast.media_status = error_code

  async def _handle_mpd_start_play(self):
    self._cast.controller.update_local_receiver_path()

    args = {}
    args["content_type"] = "audio/mpga"
    args["title"] = "Streaming MPD"

    # initiate the cast
    self._cast.chromecast.wait()
    self._cast.controller.play_media(str(self._config.cast_url), **args)
    await self._cast.media_event.wait()
    self._cast.media_event.clear()

  def _handle_mpd_stop_play(self):
    self._stop_update_tasks()
    if self._cast.chromecast and self._cast.chromecast.status.app_id == APP_LOCAL:
      self._cast.chromecast.wait()
      self._cast.chromecast.quit_app()

  async def _handle_mpd_new_song_delayed(self, song_info, delay):
    await asyncio.sleep(delay)
    await self._handle_mpd_new_song(song_info, True)

  async def _check_new_dab_label(self, song_info):
    while True:
      await self._dabserver_current_station.new_label()
      await self._handle_mpd_new_song(song_info, True)

  async def _check_new_dab_image(self, song_info):
    while True:
      await self._dabserver_current_station.new_image()
      await self._handle_mpd_new_song(song_info, True)

  def _stop_update_tasks(self):
    if self._updater.tvh_show:
      self._updater.tvh_show.cancel()
      self._updater.tvh_show = None
    if self._dabserver_current_station:
      self._updater.dab_label.cancel()
      self._updater.dab_label = None
      self._updater.dab_image.cancel()
      self._updater.dab_image = None
      self._dabserver_current_station = None

  async def _handle_mpd_new_song(self, song_info, dynamic_update = False):
    if not dynamic_update:
      self._stop_update_tasks()

    song_file = song_info['file']
    cast_data = CastData(image_url = self._config.default_image)

    if song_file.startswith('http'):
      tvh_channel = TvheadendChannel(song_file)
      dab_station = DabserverStation(song_file)

      if self._dabserver_current_station:
        # Label or image update of a DAB station
        self._dabserver_current_station.fill_cast_data(cast_data)
      elif await tvh_channel.initialize():
        # new TvHeadend URL or EPG update
        await tvh_channel.fill_cast_data(cast_data)
        remaining_time = tvh_channel.get_remaining_show_time()
        if remaining_time:
          tvh_coro = self._handle_mpd_new_song_delayed(song_info, remaining_time + 10)
          self._updater.tvh_show = asyncio.create_task(tvh_coro)
      elif await dab_station.initialize():
        logger.info('new DAB station')
        # New DAB station
        dab_station.fill_cast_data(cast_data)
        self._dabserver_current_station = dab_station
        # Create tasks which will update the image and song details
        self._updater.dab_label = asyncio.create_task(self._check_new_dab_label(song_info))
        self._updater.dab_image = asyncio.create_task(self._check_new_dab_image(song_info))
    else:
      try:
        await self._fill_cast_data(cast_data, song_info)
      except mpd.base.CommandError as exc:
        logger.exception('Received exception from MPD')
        logger.exception(str(exc))

    if self._cast.chromecast:
      self._cast.chromecast.wait()
      logger.info('update details: title: %s artist: %s image_url: %s',
                  cast_data.title, cast_data.artist, cast_data.image_url)
      if self._cast.controller:
        self._cast.controller.set_music_track_media_metadata(cast_data.title, cast_data.artist, cast_data.image_url)

  async def _fill_cast_data(self, cast_data, song_info):
    song_file = song_info['file']
    if 'title' in song_info:
      cast_data.title = song_info['title']
    elif 'name' in song_info:
      cast_data.title = song_info['name']
    else:
      cast_data.title = None

    if 'artist' in song_info:
      cast_data.artist = song_info['artist']
      picture_dict = await self._mpd_client.readpicture(song_file)
      if picture_dict:
        cast_data.image_url = self._image_server.store_song_picture(song_file, picture_dict)

  def new_cast_status(self, status):
    if self._cast.chromecast:
      logger.info ("Chromecast Session ID: %s",  str(self._cast.chromecast.status.session_id))
    if self._cast.controller:
      logger.info ("Controller Session ID: %s", str(self._cast.controller.status.media_session_id))
    logger.info ("Listener Session ID: %s", str(status.session_id))

  def new_connection_status(self, status):
    # Handle when the chromecast device gets shut down or loses network connection
    if status.status == 'LOST':
      self._cast.controller = None
      self._cast.chromecast = None

  async def cast_until_connection_lost(self):
    if not self._mpd_client.connected:
      await self._mpd_client.connect('localhost', self._config.mpd_port)

    initial_mpd_status = await self._mpd_client.status()
    # avoid spontaneous playback when chromecast becomes available, eg after nightly reboot
    ignore_current_playback = bool(initial_mpd_status['state'] == 'play')
    cast_is_active      = False
    processed_mpd_song  = ''

    try:
      async for _ in self._mpd_client.idle():
        mpd_client_status = await self._mpd_client.status()
        mpd_is_playing = bool(mpd_client_status['state'] == 'play')

        if not self._cast.chromecast:
          # Chromecast disappeared from the network.
          if cast_is_active:
            # Disable internal update events
            self._handle_mpd_stop_play()
          return

        # continue to ignore playback if we ignored until now and MPD is still playing
        ignore_current_playback = bool(ignore_current_playback and mpd_is_playing)
        if ignore_current_playback:
          # Dont process
          continue

        if not cast_is_active and mpd_is_playing:
          await self._handle_mpd_start_play()
          cast_is_active = True
        elif cast_is_active and not mpd_is_playing:
          self._handle_mpd_stop_play()
          processed_mpd_song = ''
          cast_is_active = False

        current_mpd_song = await self._mpd_client.currentsong()
        if cast_is_active and current_mpd_song and current_mpd_song != processed_mpd_song:
          logger.info('current_mpd_song: %s', current_mpd_song)
          await self._handle_mpd_new_song(current_mpd_song)
          processed_mpd_song = current_mpd_song
    except mpd.base.ConnectionError:
      # Connection to MPD lost
      self._handle_mpd_stop_play()

  async def stop(self):
    if self._cast_finder:
      self._cast_finder.cancel()
    else:
      self._mpd_client.stop()
      self._mpd_client.disconnect()
      self._handle_mpd_stop_play()

  def get_routes(self):
    return self._image_server.get_routes()
