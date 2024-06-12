#!/usr/bin/env python3
# coding=utf-8

import asyncio
import re
import tomllib
import pychromecast
import zeroconf
import mpd.asyncio
import argparse
import time
import socket
import time
from mpdcast_dab.cast_sender.local_media_player import LocalMediaPlayerController, APP_LOCAL
import mpdcast_dab.cast_sender.imageserver as imageserver
from mpdcast_dab.cast_sender.cast_finder import CastFinder
from mpdcast_dab.cast_sender.tvheadend_connector import TvheadendChannel
from mpdcast_dab.cast_sender.dabserver_connector import DabserverStation


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

  def __init__(self, config, my_ip, image_server, cast_receiver_url):
    self.image_server = image_server
    self.cast_receiver_url = cast_receiver_url
    self.default_image = 'https://www.musicpd.org/logo.png'
    self.my_ip = my_ip
    self.mpd_port = int(config.get("port", "6600"))

    for audio_output in config["audio_output"]:
      if audio_output["type"] == "httpd":
        streaming_port = int(audio_output["port"])
        self.cast_url = "http://" + self.my_ip + ":" + str(streaming_port) + "/"
        self.device_name = audio_output["name"]

    self.mpd_client = mpd.asyncio.MPDClient()
    self.controller  = None
    self.chromecast  = None
    self._tvheadend_show_updater    = None
    self._dabserver_current_station = None
    self._media_event = asyncio.Event()
    self._media_status = None
  
  def waitfor_and_register_device(self):
    cast_finder = CastFinder(self.device_name)
    cast_finder.doDiscovery()
    self.chromecast = pychromecast.get_chromecast_from_cast_info(cast_finder.device, zeroconf.Zeroconf())

    self.chromecast.wait()
    if (self.chromecast.app_id != pychromecast.IDLE_APP_ID):
      self.chromecast.quit_app()
      time.sleep(0.5)
    self.controller = LocalMediaPlayerController(self.cast_receiver_url, False)
    self.chromecast.register_handler(self.controller)   # allows Chromecast to use Local Media Player app
    self.chromecast.register_connection_listener(self)  # this will call new_connection_status() => re-init from scratch
    self.controller.register_status_listener(self)      # this will call new_media_status() / load_media_failed()
#    self.chromecast.register_status_listener(self)      # this will call new_cast_status()  => not of interest

  def new_media_status(self, status):
    self._media_status = status
    if status.media_session_id:
      self._my_async_loop.call_soon_threadsafe(self._media_event.set)

  def load_media_failed(self, queue_item_id, error_code):
    self._media_status = error_code

  async def _handle_mpd_start_play(self):
    self.controller.update_local_receiver_path()

    args = {}
    args["content_type"] = "audio/mpga"
    args["title"] = "Streaming MPD"

    # initiate the cast
    self.chromecast.wait()
    self.controller.play_media(self.cast_url, **args)
    await self._media_event.wait()
    self._media_event.clear()
  
  def _handle_mpd_stop_play(self):
    if self._tvheadend_show_updater:
      self._tvheadend_show_updater.cancel()
      self._tvheadend_show_updater = None
    if self._dabserver_current_station:
      self._dabserver_label_updater.cancel()
      self._dabserver_label_updater = None
      self._dabserver_image_updater.cancel()
      self._dabserver_image_updater = None
      self._dabserver_current_station = None
    
    if self.chromecast.status.app_id == APP_LOCAL:
      self.chromecast.wait()
      self.chromecast.quit_app()

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

  async def _handle_mpd_new_song(self, song_info, dynamic_update = False):
    if not dynamic_update:
      if self._tvheadend_show_updater:
        self._tvheadend_show_updater.cancel()
        self._tvheadend_show_updater = None
      if self._dabserver_current_station:
        self._dabserver_label_updater.cancel()
        self._dabserver_label_updater = None
        self._dabserver_image_updater.cancel()
        self._dabserver_image_updater = None
        self._dabserver_current_station = None
  
    song_file = song_info['file']
    image_url = self.default_image

    if 'title' in song_info:
      title = song_info['title']
    else:
      title = None
    if 'artist' in song_info:
      artist = song_info['artist']
    else:
      artist = None

    if song_file.startswith('http'):
      tvh_channel = TvheadendChannel(song_file)
      dab_station = DabserverStation(song_file)

      if (self._dabserver_current_station):
        # Label or image update of a DAB station
        title  = self._dabserver_current_station.station_name
        artist = self._dabserver_current_station.label
        image_url = self._dabserver_current_station.image_url

      elif (await tvh_channel.initialize()):
        # new TvHeadend URL or EPG update
        tvheadend_image_url = await tvh_channel.image_url()
        if tvheadend_image_url:
          image_url = tvheadend_image_url
        else:
          image_url = 'https://www.radio.de/assets/images/app-stores/square_512x512_playstore.png'

        show_details = await tvh_channel.current_show()
        if show_details:
          if 'title' in show_details:
            title = show_details['title']
          if 'subtitle' in show_details:
            artist = show_details['subtitle']
          show_end = int(show_details['stop'])
          time_remaining = int(show_end - time.time())
          self._tvheadend_show_updater = asyncio.create_task(self._handle_mpd_new_song_delayed(song_info, time_remaining + 10))
        else:
          # No EPG data. Show only channel name
          title = tvh_channel.name()

      elif (await dab_station.initialize()):
        print('new DAB station')
        # New DAB station
        self._dabserver_current_station = dab_station
        title  = self._dabserver_current_station.station_name
        artist = self._dabserver_current_station.label
        image_url = self._dabserver_current_station.image_url
        # Create tasks which will update the image and song details 
        self._dabserver_label_updater = asyncio.create_task(self._check_new_dab_label(song_info))
        self._dabserver_image_updater = asyncio.create_task(self._check_new_dab_image(song_info))

    else:
      try:
        picture_dict = await self.mpd_client.readpicture(song_file)        
        if picture_dict:
          image_url = self.image_server.store_song_picture(song_file, picture_dict)
      except mpd.base.CommandError as exception:
        print(exception)

    if not title and 'name' in song_info:
      title = song_info['name']

    self.chromecast.wait()
    print('update:',  title, artist, image_url)
    self.controller.set_MusicTrackMediaMetadata(title, artist, image_url)
  
  def new_cast_status(self, status):
    if self.chromecast:
      print ("Chromecast Session ID: " + str(self.chromecast.status.session_id))
    if self.controller:
      print ("Controller Session ID: " + str(self.controller.status.media_session_id))
    print ("Listener Session ID: " + str(status.session_id))

  def new_connection_status(self, status):
    # Handle when the chromecast device gets shut down or loses network connection
    if status.status == 'LOST':
      self.controller = None
      self.chromecast = None

  async def cast_forever(self):
    self._my_async_loop = asyncio.get_running_loop()
    await self.mpd_client.connect('localhost', self.mpd_port)
      
    processed_mpd_state = ""
    processed_mpd_song  = ""

    try:
      async for subsystem in self.mpd_client.idle():
        mpd_client_status = await self.mpd_client.status()
        current_mpd_state = mpd_client_status["state"]
        current_mpd_song = await self.mpd_client.currentsong()

        if not self.controller:
          # Chromecast disappeared from the network or discovery has not yet been executed
          return

        if current_mpd_state != processed_mpd_state:
          match current_mpd_state:
            case "play":
              await self._handle_mpd_start_play()
            case "stop" | "pause":
              self._handle_mpd_stop_play()
              processed_mpd_song = ""
          processed_mpd_state = current_mpd_state

        if current_mpd_song != processed_mpd_song:
          print('current_mpd_song:', current_mpd_song)
          if current_mpd_song and current_mpd_state == "play":
            await self._handle_mpd_new_song(current_mpd_song)
            processed_mpd_song = current_mpd_song
    except mpd.base.ConnectionError:
      return

  def stop(self):
    self.mpd_client.disconnect()

def load_mpd_config(config_filename):
  print('Loading config from ' + config_filename)
  cfg_file = open(config_filename, "r")
  confStr = cfg_file.read()

  # convert curly brace groups to toml arrays
  confStr = re.sub(r"\n([^\s#]*?)\s*{(.*?)}", r"\n[[\1]]\2\n", confStr, flags=re.S, count=0)
  # separate key and value with equals sign
  confStr = re.sub(r"^\s*(\w+)\s*(.*)$", r"\1 = \2", confStr, flags=re.M, count=0)
  # now the config should adhere to toml spec.
  mpd_config = tomllib.loads(confStr)
  cfg_file.close()

  return mpd_config
