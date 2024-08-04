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
import re
import logging
import dataclasses
import tomllib
from aiohttp import web
from yarl import URL
import pychromecast
import mpd.asyncio

from mpdcast_dab.cast_sender.imageserver import ImageRequestHandler
from mpdcast_dab.cast_sender.local_media_player import LocalMediaPlayerController, APP_LOCAL
from mpdcast_dab.cast_sender.cast_finder import CastFinder
from mpdcast_dab.cast_sender.tvheadend_connector import TvheadendChannel
from mpdcast_dab.cast_sender.dabserver_connector import DabserverStation

logger = logging.getLogger(__name__)

CAST_PATH     = '/cast_receiver'
CAST_PAGE     = 'receiver.html'
DEFAULT_IMAGE = 'https://www.musicpd.org/logo.png'

class MpdConfig():
  def __init__(self, filename):
    self._filename      = filename
    self._config        = None
    self.port           = None
    self.streaming_port = None
    self.device_name    = None
    self.init_okay      = False

  def cast_url(self):
    return URL.build(scheme = 'http', host = 'dummy', port = self.streaming_port)

  def initialize(self):
    try:
      self.load()
      self.read()
      self.init_okay = True
    except (FileNotFoundError, SyntaxError) as error:
      logger.warning('Failed to read MPD Cast configuration. Disabling.')
      logger.warning(str(error))
    return self.init_okay

  def load(self):
    logger.info('Loading config from %s', self._filename)
    with open(self._filename, 'r', encoding='utf-8') as cfg_file:
      config_string = cfg_file.read()
      # convert curly brace groups to toml arrays
      config_string = re.sub(r"\n([^\s#]*?)\s*{(.*?)}", r"\n[[\1]]\2\n", config_string, flags=re.S, count=0)
      # separate key and value with equals sign
      config_string = re.sub(r"^\s*(\w+)\s*(.*)$", r"\1 = \2", config_string, flags=re.M, count=0)
      # now the config should adhere to toml spec.
      self._config = tomllib.loads(config_string)

  def read(self):
    self.port = int(self._config.get("port", "6600"))

    httpd_defined  = False
    if "audio_output" in self._config:
      for audio_output in self._config["audio_output"]:
        if 'type' in audio_output and audio_output['type'] == 'httpd':
          httpd_defined = True
          if 'port' in audio_output:
            self.streaming_port = audio_output['port']
          if 'name' in audio_output:
            self.device_name = audio_output['name']

    if not httpd_defined:
      raise SyntaxError('No httpd audio output defined.')
    if not self.streaming_port:
      raise SyntaxError('No httpd streaming port defined.')
    if not self.streaming_port.isdigit():
      raise SyntaxError('Invalid http streaming port defined: ' + self.streaming_port + '.')
    if not self.device_name:
      raise SyntaxError('No cast device name defined')


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
      self.cast_finder  = None
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

  def __init__(self, config_filename, my_ip, port):
    self.cast_receiver_url = URL.build(scheme = 'http', host = my_ip, port = port, path = CAST_PATH + '/' + CAST_PAGE)
    self._mpd_config   = MpdConfig(config_filename)
    self._updater      = self.UpdateTasks()
    self._cast         = self.CastStatus()
    self._image_server = ImageRequestHandler(my_ip, port)
    self._mpd_client   = mpd.asyncio.MPDClient()
    self._dabserver_current_station = None

  def initialize(self):
    return self._mpd_config.initialize()

  async def waitfor_and_register_castdevice(self, blocking_zconf):
    if not self._cast.chromecast:
      self._cast.cast_finder = CastFinder(self._mpd_config.device_name)
      await self._cast.cast_finder.do_discovery()
      if self._cast.cast_finder.device:
        loop = asyncio.get_running_loop()
        self._cast.chromecast = await loop.run_in_executor(None,
                                                           pychromecast.get_chromecast_from_cast_info,
                                                           self._cast.cast_finder.device,
                                                           blocking_zconf)
        await loop.run_in_executor(None, self._cast.chromecast.wait)
        if self._cast.chromecast.app_id != pychromecast.IDLE_APP_ID:
          self._cast.chromecast.quit_app()
          await asyncio.sleep(0.5)
        self._cast.controller = LocalMediaPlayerController(str(self.cast_receiver_url), False)
        self._cast.chromecast.register_handler(self._cast.controller)  # allows Chromecast to use Local Media Player app
        self._cast.chromecast.register_connection_listener(self)  # await new_connection_status() => re-initialize
        self._cast.controller.register_status_listener(self)      # await new_media_status() / load_media_failed()
        #self._cast.chromecast.register_status_listener(self)     # await new_cast_status()  => not of interest

      self._cast.cast_finder = None

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
    cast_url = self._mpd_config.cast_url().with_host(self.cast_receiver_url.host)
    self._cast.controller.play_media(str(cast_url), **args)
    await self._cast.media_event.wait()
    self._cast.media_event.clear()
    while self._cast.media_status.media_session_id is None:
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
    cast_data = CastData(image_url = DEFAULT_IMAGE)

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
      await self._mpd_client.connect('localhost', self._mpd_config.port)

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
    if self._cast.cast_finder:
      self._cast.cast_finder.cancel()
    else:
      self._mpd_client.stop()
      self._mpd_client.disconnect()
      self._handle_mpd_stop_play()

  def get_routes(self):
    return (self._image_server.get_routes()
         + [web.static(CAST_PATH, '/usr/share/mpdcast-dab/cast_receiver')])

  def init_okay(self):
    return self._mpd_config.init_okay
