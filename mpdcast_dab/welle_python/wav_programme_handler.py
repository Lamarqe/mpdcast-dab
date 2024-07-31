import asyncio
import datetime
import logging
from mpdcast_dab.welle_python.welle_io import ProgrammeHandlerInterface

logger = logging.getLogger(__name__)


class UnsubscribedError(Exception):
  pass

class WavProgrammeHandler(ProgrammeHandlerInterface):
  BUFFER_SIZE = 10

  def __init__(self):
    self.subscribers = 0

    self._next_frame = 0
    self._audio_data = [b''] * WavProgrammeHandler.BUFFER_SIZE
    self._audio_data_lock = asyncio.Lock()

    # properties for most recent data. 
    # Can be used directly by user applications to get the most recent data
    self.picture = None
    self.label   = ''
    
    # internal update notification events
    self._audio_event      = asyncio.Event()
    self._picture_event    = asyncio.Event()
    self._label_event      = asyncio.Event()
    
    self._delete_in_progress = False

  # notification routines for user applications
  async def new_audio(self, start_frame=0):
    if start_frame == self._next_frame:
      await self._audio_event.wait()
      if self._delete_in_progress:
        raise UnsubscribedError
    async with self._audio_data_lock:
      if start_frame < self._next_frame:
        ret_list = self._audio_data[start_frame:self._next_frame]
      else:
        ret_list = self._audio_data[start_frame:] + self._audio_data[:self._next_frame]
      audio_out = b''.join(ret_list)
      return self._next_frame, audio_out

  async def new_picture(self):
    logger.debug('waiting for new picture')
    await self._picture_event.wait()
    if self._delete_in_progress:
      raise UnsubscribedError
    else:
      logger.debug('forwarding new picture of type %s', self.picture['type'])
      return self.picture

  async def new_label(self):
    logger.debug('waiting for new label')
    await self._label_event.wait()
    if self._delete_in_progress:
      raise UnsubscribedError
    else:
      logger.debug('forwarding new label')
      return self.label

  def _release_waiters(self):
    self._delete_in_progress = True
    self._audio_event.set()
    self._picture_event.set()
    self._label_event.set()

  async def onNewAudio(self, audio_data, sample_rate, mode):
    self.sample_rate = sample_rate
    await self.buffer_audio(audio_data)

  async def buffer_audio(self, audio_data):
    async with self._audio_data_lock:
      self._audio_data[self._next_frame] = audio_data
      self._next_frame = (self._next_frame+1) % WavProgrammeHandler.BUFFER_SIZE
    if not self._delete_in_progress:
      self._audio_event.set()
      self._audio_event.clear()

  async def onNewDynamicLabel(self, label):
    self.label = label
    await self._set_event(self._label_event)
    
  async def _set_event(self, event):
    if not self._delete_in_progress:
      event.set()
      event.clear()

  async def onMOT(self, data, mime_type, name):
    self.picture = {'type': mime_type, 'data': data, 'name': name}
    await self._set_event(self._picture_event)