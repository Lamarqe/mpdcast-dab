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

class ProgrammeHandler():
  async def on_frame_errors(self, frame_errors: int) -> None:
    pass

  async def on_new_audio(self, audio_data: bytes, sample_rate: int, mode: str) -> None:
    pass

  async def on_rs_errors(self, uncorrected_errors: int, num_corrected_errors: int) -> None:
    pass

  async def on_aac_errors(self, aac_errors: int) -> None:
    pass

  async def on_new_dynamic_label(self, label: str) -> None:
    pass

  async def on_mot(self, data: bytes, mime_type: str, name: str) -> None:
    pass

class RadioHandler():
  async def on_snr(self, snr: float) -> None:
    pass

  async def on_frequency_corrector_change(self, fine: int, coarse: int) -> None:
    pass

  async def on_sync_change(self, is_sync: bool) -> None:
    pass

  async def on_signal_presence(self, is_signal: int) -> None:
    pass

  async def on_service_detected(self, service_id: int) -> None:
    pass

  async def on_new_ensemble(self, ensemble_id: int) -> None:
    pass

  async def on_set_ensemble_label(self, label: str) -> None:
    pass

  async def on_datetime_update(self, timestamp: int) -> None:
    pass

  async def on_fib_decode_success(self, crc_check_ok: int, fib: int) -> None:
    pass

  async def on_message(self, text: str, text2: str, is_error: bool) -> None:
    pass
