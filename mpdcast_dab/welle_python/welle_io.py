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

"""Python interface defintions for welle.io python wrapper"""

import atexit
import logging
from typing import Any

from mpdcast_dab.welle_python.welle_py import DabDeviceCpp
from mpdcast_dab.welle_python.dab_callbacks import RadioCallbackForwarder, ProgrammeCallbackForwarder

logger = logging.getLogger(__name__)

class DabDevice(DabDeviceCpp):
  def __init__(self, device_name: str = 'auto', gain: int = -1):
    self._handler = RadioCallbackForwarder()
    DabDeviceCpp.__init__(self, self._handler, device_name, gain)

  def aquire_now(self, handler: object) -> bool:
    return self._handler.subscribe_for_callbacks(handler)

  def release(self) -> bool:
    return self._handler.unsubscribe_from_callbacks()

  def subscribe_service(self, handler: Any, service_id: int) -> bool:
    forwarder = ProgrammeCallbackForwarder(handler)
    # small hack, required as otherwise the forwarder and its handler will be garbage collected
    handler.forwarder = forwarder
    retval = self.subscribe_program(forwarder, service_id)
    return retval
