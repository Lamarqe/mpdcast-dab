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

"""This module is used to wait for a chromecast device to appear on the network."""

import asyncio
import zeroconf
import uuid
import pychromecast

class CastFinder(pychromecast.discovery.AbstractCastListener):
  def __init__(self, device_name: str) -> None:
    self._device_name:          str                                = device_name
    self._device:               uuid.UUID | None                   = None
    self._browser:              pychromecast.discovery.CastBrowser = None
    self._discovery_done_event: asyncio.Event                      = asyncio.Event()

  def add_cast(self, uuid: uuid.UUID, _service: str) -> None:
    if self._device_name == self._browser.services[uuid].friendly_name:
      self._device = self._browser.services[uuid]
      self._discovery_done_event.set()

  def remove_cast(self, uuid: uuid.UUID, _service: str, cast_info: pychromecast.discovery.CastInfo) -> None:
    pass

  def update_cast(self, uuid: uuid.UUID, _service: str) -> None:
    pass

  async def find_device (self) -> uuid.UUID | None:
    self._device = None
    self._discovery_done_event.clear()
    self._browser = pychromecast.discovery.CastBrowser(self, zeroconf.Zeroconf(), None)
    self._browser.start_discovery()
    await self._discovery_done_event.wait()
    self._browser.stop_discovery()
    return self._device

  def cancel(self) -> None:
    self._discovery_done_event.set()
