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
    self.ui_status['scanner_status'] = ''
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
      for service in channel_details.values():
        playlist+= '#EXTINF:-1,' + service['name'] + '\n'
        playlist+= 'http://' + ip + ':' + str(port) + '/stream/' + channel_name + '/' + urllib.parse.quote(service['name']) + '\n'
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
        discovered_services+= len(services)
      self.ui_status['progress_text'] = str(progress) + '% (' + str(scanned_channels)
      self.ui_status['progress_text']+= ' of ' + str(number_of_channels) + ' channels)'
      self.ui_status['progress_text']+= ' Found ' + str(discovered_services) + ' radio services.'
    else:
      self.ui_status['progress_text'] = '&nbsp;'
      self.ui_status['progress'] = 0
      self.ui_status['is_scan_active'] = False
    return self.ui_status

  async def wait_for_scan_complete(self):
    if self._scanner_task:
      await self._scanner_task

  async def _run_scan(self):
    self.scan_results = {}
    self.ui_status['download_ready'] = False
    service_count = 0
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

    # scan finished. release the DAB device and remove strong reference to running task
    self._dab_device.release()
    self._scanner_task = None
    self.ui_status['scanner_status'] = 'Scan finished. Found ' + str(service_count) + ' radio services.'
    self.ui_status['download_ready'] = True

  async def onServiceDetected(self, sId):
    current_channel = list(self.scan_results.keys())[-1]
		# TODO: Filter data channels via rx->getComponents(s).transportMode()) case TransportMode::Audio:
    if not sId in self.scan_results[current_channel].keys() and sId <= 0xFFFF:
      self.scan_results[current_channel][sId] = {}

  async def onSignalPresence(self, isSignal):
    self._is_signal = isSignal
    self._signal_presence_event.set()
    self._signal_presence_event.clear()

def updateLoggerConfig(quiet):
  internal_log_level = logging.WARNING if quiet else logging.INFO
  external_log_level = logging.ERROR   if quiet else logging.WARNING
  logging.basicConfig(format='%(name)s - %(levelname)s: %(message)s', encoding='utf-8', level=internal_log_level, stream=sys.stdout, force=True)
  logging.getLogger("Welle.io").setLevel(external_log_level)

def main():
  parser = argparse.ArgumentParser(description='DAB Scanner')
  parser.add_argument('--quiet', help = 'Disable verbose output', action = 'store_true')
  parser.add_argument('--conf', help = 'mpd config file to use. Default: /etc/mpd.conf', default = '/etc/mpd.conf')

  args = vars(parser.parse_args())

  stdout_grabber = OutputGrabber(sys.stdout, 'Welle.io', logging.Logger.error)
  stderr_grabber = OutputGrabber(sys.stderr, 'Welle.io', logging.Logger.warning)
  sys.stdout = stdout_grabber.redirect_stream()
  sys.stderr = stderr_grabber.redirect_stream()
  updateLoggerConfig(args['quiet'])

  device = DabDevice('auto')
  
  dab_scanner = DabScanner(device)
  loop = asyncio.get_event_loop()
  try:
    if loop.run_until_complete(dab_scanner.start_scan()):
      loop.run_until_complete(dab_scanner.wait_for_scan_complete())
  except KeyboardInterrupt:
    pass

  stdout_grabber.cleanup()
  stderr_grabber.cleanup()

if __name__ == '__main__':
  main()
