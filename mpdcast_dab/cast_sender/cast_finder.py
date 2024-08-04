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
import pychromecast

class CastFinder(pychromecast.discovery.AbstractCastListener):
  def __init__(self, device_name):
    self._device_name = device_name
    self.device = None
    self._browser = None
    self._my_task = None

  def add_cast(self, uuid, _service):
    if self._device_name == self._browser.services[uuid].friendly_name:
      self.device = self._browser.services[uuid]
      self._my_task.set()

  def remove_cast(self, uuid, _service, cast_info):
    pass

  def update_cast(self, uuid, _service):
    pass

  async def do_discovery (self):
    self._browser = pychromecast.discovery.CastBrowser(self, zeroconf.Zeroconf(), None)
    self._my_task = asyncio.Event()
    self._browser.start_discovery()
    await self._my_task.wait()
    self._browser.stop_discovery()

  def cancel(self):
    self._my_task.set()
