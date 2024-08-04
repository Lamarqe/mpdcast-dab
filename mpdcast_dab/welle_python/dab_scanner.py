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

"""DAB Scanner to find all DAB radio services and generate a playlist."""

import asyncio
import logging
import urllib
from mpdcast_dab.welle_python.dab_callbacks import RadioControllerInterface

logger = logging.getLogger(__name__)

class DabScanner(RadioControllerInterface):
  PROGRAM_DISCOVERY_TIMEOUT = 10

  def __init__(self, device):
    self._dab_device = device
    self._is_signal = None
    self._scanner_task = None
    self._all_channel_names = device.__class__.all_channel_names()
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
          playlist+= 'http://' + ip + ':' + str(port)
          playlist+= '/stream/' + channel_name
          playlist+= '/' + urllib.parse.quote(service_details['name']) + '\n'
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
          for service_id in self.scan_results[channel].keys():
            name = self._dab_device.get_service_name(service_id).rstrip()
            self.scan_results[channel][service_id]['name'] = name
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
      self.ui_status['download_ready'] = bool(service_count > 0)

    self.ui_status['scanner_status'] = 'Scan finished. Found ' + str(service_count) + ' radio services.'

  async def on_service_detected(self, service_id):
    current_channel = list(self.scan_results.keys())[-1]
    if not service_id in self.scan_results[current_channel].keys():
      if self._dab_device.is_audio_service(service_id):
        self.scan_results[current_channel][service_id] = {}

  async def on_signal_presence(self, is_signal):
    self._is_signal = is_signal
    self._signal_presence_event.set()
    self._signal_presence_event.clear()
