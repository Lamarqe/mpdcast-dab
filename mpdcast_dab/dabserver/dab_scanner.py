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
import typing

import yarl

from .welle_io import DabDevice, ChannelEventHandler, all_channel_names
from .dab_callbacks import ChannelEventPass

logger = logging.getLogger(__name__)

UiStatus = typing.TypedDict('UiStatus', {'scanner_status': str,
                                         'download_ready': bool,
                                         'is_scan_active': bool,
                                         'progress': int,
                                         'progress_text': str})

class DabScanner(ChannelEventHandler, ChannelEventPass):
  SERVICE_DISCOVERY_TIMEOUT = 10

  def __init__(self, device: DabDevice) -> None:
    ChannelEventHandler.__init__(self)
    self._dab_device: DabDevice = device
    self._is_signal: bool | None = None
    self._scanner_task: asyncio.Task | None = None
    self._all_channel_names = all_channel_names()
    self.scan_results: dict[str, dict[int, dict[str, str]]] = {}
    self.ui_status: UiStatus = {'scanner_status': '&nbsp;', 
                                'download_ready': False,
                                'is_scan_active': False,
                                'progress': 0,
                                'progress_text': '&nbsp;'}

    # internal update notification event
    self._signal_presence_event = asyncio.Event()

  async def start_scan(self) -> dict:
    if self._scanner_task:
      self.ui_status['scanner_status']      = 'Scan in progress. No new scan possible.'
    elif not self._dab_device.lock.acquire(blocking=False):
      self.ui_status['scanner_status']      = 'DAB device is locked. No scan possible.'
    else:
      self._scanner_task = asyncio.create_task(self._run_scan())
      self.ui_status['scanner_status']      = 'Scan started succesfully'
    return { }

  def get_playlist(self, base_url: yarl.URL) -> str:
    playlist = '#EXTM3U\n'
    for channel_name, channel_details in self.scan_results.items():
      for service_details in channel_details.values():
        if 'name' in service_details:
          stream_url = base_url / channel_name / service_details['name']
          playlist+= '#EXTINF:-1,' + service_details['name'] + '\n'
          playlist+= str(stream_url) + '\n'
    return playlist

  def status(self) -> UiStatus:
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
      self.ui_status['scanner_status'] = 'Scan in progress. Currently scanning channel '
      self.ui_status['scanner_status']+= self._dab_device.get_channel() + '.'
    else:
      self.ui_status['progress_text'] = '&nbsp;'
      self.ui_status['progress'] = 0
      self.ui_status['is_scan_active'] = False
    return self.ui_status

  def stop_scan(self) -> dict:
    if self._scanner_task:
      self._scanner_task.cancel()
    return { }

  async def _run_scan(self) -> None:
    service_count = 0
    try:
      self.scan_results = {}
      self.ui_status['download_ready'] = False
      for channel in self._all_channel_names:
        self.scan_results[channel] = {}
        # tune to the channel
        self._dab_device.set_channel(channel, self, True)
        await self._signal_presence_event.wait()
        if self._is_signal:
          # wait for service detection
          await asyncio.sleep(DabScanner.SERVICE_DISCOVERY_TIMEOUT)

          # collect service names
          for service_id in self.scan_results[channel].keys():
            name = self._dab_device.get_service_name(service_id).rstrip()
            self.scan_results[channel][service_id]['name'] = name
            service_count+= 1

        self._dab_device.reset_channel()
    except asyncio.CancelledError:
      self._dab_device.reset_channel()
      self.ui_status['scanner_status'] = 'Scan stopped. Found ' + str(service_count) + ' radio services.'
      raise
    finally:
      # scan finished. release the DAB device and remove strong reference to running task
      self._dab_device.lock.release()
      self._scanner_task = None
      self.ui_status['download_ready'] = bool(service_count > 0)

    self.ui_status['scanner_status'] = 'Scan finished. Found ' + str(service_count) + ' radio services.'

  async def on_service_detected(self, service_id: int) -> None:
    current_channel = list(self.scan_results.keys())[-1]
    if not service_id in self.scan_results[current_channel].keys():
      if self._dab_device.is_audio_service(service_id):
        self.scan_results[current_channel][service_id] = {}

  async def on_signal_presence(self, is_signal: bool) -> None:
    self._is_signal = is_signal
    self._signal_presence_event.set()
    self._signal_presence_event.clear()

  async def stop(self) -> None:
    if self._scanner_task:
      self._scanner_task.cancel()
      try:
        await self._scanner_task
      except asyncio.CancelledError:
        pass
