#!/usr/bin/env python3
# coding=utf-8

import io
import os
import sys
import asyncio
import argparse
import socket
import ifaddr
import time
import logging
import urllib
from aiohttp import web

import threading
import traceback
logger = logging.getLogger(__name__)

if __name__ == '__main__':
  sys.path.append(os.path.dirname(__file__)  + '/../..')

from mpdcast_dab.cast_sender.output_grabber import *

from mpdcast_dab.welle_python.welle_io import RadioControllerInterface, DabDevice

class DabScanner(RadioControllerInterface):
  PROGRAM_DISCOVERY_TIMEOUT = 10

  def __init__(self, device: DabDevice):
    self._dab_device = device
    self._is_signal = None
    self._scanner_task = None
    self._all_channel_names = DabDevice.all_channel_names()
    self.scan_results = {}
    self.ui_status = {}
    self.ui_status['scanner_status'] = '&nbsp;'
    self.ui_status['download_ready'] = False

    # internal update notification event
    self._signal_presence_event = asyncio.Event()

  async def start_scan(self):
    if self._scanner_task:
      self.ui_status['scanner_status']      = 'Scan in progress. No new scan possible.'
    elif not self._dab_device.aquire_now(self):
      self.ui_status['scanner_status']      = 'DAB device is locked. No scan possible.'
    else:
      self._scanner_task = asyncio.create_task(self._run_scan())
      self.ui_status['scanner_status']      = 'Scan started succesfully'
    return { }

  def get_playlist(self, ip, port):
    playlist = '#EXTM3U\n'
    for channel_name, channel_details in self.scan_results.items():
      for service_details in channel_details.values():
        if 'name' in service_details:
          playlist+= '#EXTINF:-1,' + service_details['name'] + '\n'
          playlist+= 'http://' + ip + ':' + str(port) + '/stream/' + channel_name + '/' + urllib.parse.quote(service_details['name']) + '\n'
    return playlist

  def status(self):
    if self._scanner_task:
      self.ui_status['is_scan_active'] = True
      number_of_channels  = len(self._all_channel_names)
      scanned_channels    = max (0, len(self.scan_results.keys()) - 1)
      progress            = int(100.0 * scanned_channels / number_of_channels)
      discovered_services = 0
      self.ui_status['progress'] = progress
      for services in self.scan_results.values():
        for service_details in services.values():
          if 'name' in service_details:
            discovered_services+= 1
      self.ui_status['progress_text'] = str(progress) + '% (' + str(scanned_channels)
      self.ui_status['progress_text']+= ' of ' + str(number_of_channels) + ' channels)'
      self.ui_status['progress_text']+= ' Found ' + str(discovered_services) + ' radio services.'
    else:
      self.ui_status['progress_text'] = '&nbsp;'
      self.ui_status['progress'] = 0
      self.ui_status['is_scan_active'] = False
    return self.ui_status

  def stop_scan(self):
    if self._scanner_task:
      self._scanner_task.cancel()
    return { }

  async def wait_for_scan_complete(self):
    if self._scanner_task:
      await self._scanner_task

  async def _run_scan(self):
    service_count = 0
    try:
      self.scan_results = {}
      self.ui_status['download_ready'] = False
      for channel in self._all_channel_names:
        self.scan_results[channel] = {}
        # tune to the channel
        self._dab_device.set_channel(channel, True)
        await self._signal_presence_event.wait()
        if self._is_signal:
          # wait for program detection
          await asyncio.sleep(DabScanner.PROGRAM_DISCOVERY_TIMEOUT)

          # collect program names
          for sId in self.scan_results[channel].keys():
            name = self._dab_device.get_service_name(sId).rstrip()
            self.scan_results[channel][sId]['name'] = name
            service_count+= 1
      
        self._dab_device.set_channel('', True)
    except asyncio.CancelledError:
      self._dab_device.set_channel('', True)
      self.ui_status['scanner_status'] = 'Scan stopped. Found ' + str(service_count) + ' radio services.'
      raise
    finally:
      # scan finished. release the DAB device and remove strong reference to running task
      self._dab_device.release()
      self._scanner_task = None
      self.ui_status['download_ready'] = (service_count > 0)

    self.ui_status['scanner_status'] = 'Scan finished. Found ' + str(service_count) + ' radio services.'

  async def onServiceDetected(self, sId):
    current_channel = list(self.scan_results.keys())[-1]
    if not sId in self.scan_results[current_channel].keys():
      if self._dab_device.is_audio_service(sId):
        self.scan_results[current_channel][sId] = {}

  async def onSignalPresence(self, isSignal):
    self._is_signal = isSignal
    self._signal_presence_event.set()
    self._signal_presence_event.clear()