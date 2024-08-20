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

"""Callback interfaces to handle DAB+ data and events"""

import asyncio

from mpdcast_dab.welle_python.welle_py import RadioControllerInterface, ProgrammeHandlerInterface

class ProgrammeHandler():
  def on_frame_errors(self, frame_errors: int) -> None:
    pass

  def on_new_audio(self, audio_data: bytes, sample_rate: int, mode: str) -> None:
    pass

  def on_rs_errors(self, uncorrected_errors: int, num_corrected_errors: int) -> None:
    pass

  def on_aac_errors(self, aac_errors: int) -> None:
    pass

  def on_new_dynamic_label(self, label: str) -> None:
    pass

  def on_mot(self, data: bytes, mime_type: str, name: str) -> None:
    pass

class RadioHandler():
  def on_snr(self, snr: float) -> None:
    pass

  def on_frequency_corrector_change(self, fine: int, coarse: int) -> None:
    pass

  def on_sync_change(self, is_sync: bool) -> None:
    pass

  def on_signal_presence(self, is_signal: int) -> None:
    pass

  def on_service_detected(self, service_id: int) -> None:
    pass

  def on_new_ensemble(self, ensemble_id: int) -> None:
    pass

  def on_set_ensemble_label(self, label: str) -> None:
    pass

  def on_datetime_update(self, timestamp: int) -> None:
    pass

  def on_fib_decode_success(self, crc_check_ok: int, fib: int) -> None:
    pass

  def on_message(self, text: str, text2: str, is_error: bool) -> None:
    pass

class CallbackForwarder():
  # This abstract base class forwards all c-lib callbacks to the actual Interface object
  # Making this indirect has two reasons:
  # 1: It allows dynamic controller objects in python without having to re-initialize the device in C
  # 2: The indirection includes a thread handover into async which is required anyways

  def __init__(self, target, fallback):
    self._target = target
    self._pass_handler = fallback
    self._loop = asyncio.get_event_loop()

  def __getattr__(self, attr):
    method = getattr(self._target, attr, None)
    # if the target does not implement the interface, redirect the fall
    if not method:
      return getattr(self._pass_handler, attr)

    def asyncio_callback(*args, **kwargs):
      asyncio.run_coroutine_threadsafe(method(*args, **kwargs), self._loop)
    return asyncio_callback

class RadioCallbackForwarder(CallbackForwarder, RadioControllerInterface):
  def __init__(self):
    CallbackForwarder.__init__(self, None, RadioHandler())
    RadioControllerInterface.__init__(self)

  def subscribe_for_callbacks(self, target) -> bool:
    if self._target is not None:
      return False
    self._target = target
    return True

  def unsubscribe_from_callbacks(self) -> bool:
    if self._target is None:
      return False
    self._target = None
    return True

class ProgrammeCallbackForwarder(CallbackForwarder, ProgrammeHandlerInterface):
  def __init__(self, target):
    CallbackForwarder.__init__(self, target, ProgrammeHandler())
    ProgrammeHandlerInterface.__init__(self)
