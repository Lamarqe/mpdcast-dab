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

"""Class that receives DAB data and forwards it to the subscribers"""

import asyncio
import logging
import dataclasses
from mpdcast_dab.welle_python.dab_callbacks import ProgrammeHandlerInterface

logger = logging.getLogger(__name__)


class UnsubscribedError(Exception):
  pass

@dataclasses.dataclass
class WavProgrammeData():
  def __init__(self):
    # properties for most recent data.
    # Can be used directly by user applications to get the most recent data
    self.picture     = None
    self.label       = ''
    self.sample_rate = None

class WavProgrammeHandler(ProgrammeHandlerInterface):
  @dataclasses.dataclass
  class WavProgrammEvents():
    def __init__(self):
      # internal update notification events
      self.audio      = asyncio.Event()
      self.picture    = asyncio.Event()
      self.label      = asyncio.Event()

  @dataclasses.dataclass
  class AudioBuffer():
    BUFFER_SIZE = 10
    def __init__(self):
      self.next_frame  = 0
      self.data        = [b''] * WavProgrammeHandler.AudioBuffer.BUFFER_SIZE
      self.data_lock   = asyncio.Lock()

  def __init__(self):
    self.subscribers         = 0
    self.data                = WavProgrammeData()
    self._audio_buffer       = self.AudioBuffer()
    self._events             = self.WavProgrammEvents()
    self._delete_in_progress = False

  # notification routines for user applications
  async def new_audio(self, start_frame=0):
    if start_frame == self._audio_buffer.next_frame:
      await self._events.audio.wait()
      if self._delete_in_progress:
        raise UnsubscribedError
    async with self._audio_buffer.data_lock:
      if start_frame < self._audio_buffer.next_frame:
        ret_list = self._audio_buffer.data[start_frame:self._audio_buffer.next_frame]
      else:
        ret_list = self._audio_buffer.data[start_frame:] + self._audio_buffer.data[:self._audio_buffer.next_frame]
      audio_out = b''.join(ret_list)
      return self._audio_buffer.next_frame, audio_out

  async def new_picture(self):
    logger.debug('waiting for new picture')
    await self._events.picture.wait()
    if self._delete_in_progress:
      raise UnsubscribedError
    logger.debug('forwarding new picture of type %s', self.data.picture['type'])
    return self.data.picture

  async def new_label(self):
    logger.debug('waiting for new label')
    await self._events.label.wait()
    if self._delete_in_progress:
      raise UnsubscribedError
    logger.debug('forwarding new label')
    return self.data.label

  def release_waiters(self):
    self._delete_in_progress = True
    self._events.audio.set()
    self._events.picture.set()
    self._events.label.set()

  async def on_new_audio(self, audio_data, sample_rate, mode):
    self.data.sample_rate = sample_rate
    async with self._audio_buffer.data_lock:
      self._audio_buffer.data[self._audio_buffer.next_frame] = audio_data
      self._audio_buffer.next_frame = (self._audio_buffer.next_frame+1) % WavProgrammeHandler.AudioBuffer.BUFFER_SIZE
    if not self._delete_in_progress:
      self._events.audio.set()
      self._events.audio.clear()

  async def on_new_dynamic_label(self, label):
    self.data.label = label
    if not self._delete_in_progress:
      self._events.label.set()
      self._events.label.clear()

  async def on_mot(self, data, mime_type, name):
    self.data.picture = {'type': mime_type, 'data': data, 'name': name}
    if not self._delete_in_progress:
      self._events.picture.set()
      self._events.picture.clear()
