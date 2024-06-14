import asyncio
import datetime
import logging
logger = logging.getLogger(__name__)

import mpdcast_dab.welle_python.libwelle_py as c_lib

class UnsubscribedError(Exception):
  pass

class WavProgrammeHandler():
  BUFFER_SIZE = 10

  def __init__(self, controller, sId):
    self._controller = controller
    self.sId = sId
    self._subscribers = 0

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
    
    self._caller_loop = asyncio.get_running_loop()
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
      logger.debug('forwarding new picture of type', self.picture['type'])
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

  def onFrameErrors(self, frameErrors):
    pass

  def onNewAudio(self, audio_data, sample_rate, mode):
    self.sample_rate = sample_rate
    asyncio.run_coroutine_threadsafe(self.buffer_audio(audio_data), self._caller_loop)

  async def buffer_audio(self, audio_data):
    async with self._audio_data_lock:
      self._audio_data[self._next_frame] = audio_data
      self._next_frame = (self._next_frame+1) % WavProgrammeHandler.BUFFER_SIZE
    if not self._delete_in_progress:
      self._audio_event.set()
      self._audio_event.clear()

  def onRsErrors(self, uncorrectedErrors, numCorrectedErrors):
    pass

  def onAacErrors(self, aacErrors):
    pass

  def onNewDynamicLabel(self, label):
    self.label = label
    asyncio.run_coroutine_threadsafe(self._set_event(self._label_event), self._caller_loop)
    
  async def _set_event(self, event):
    if not self._delete_in_progress:
      event.set()
      event.clear()

  def onMOT(self, data, mime_type, name):
    self.picture = {'type': mime_type, 'data': data, 'name': name}
    asyncio.run_coroutine_threadsafe(self._set_event(self._picture_event), self._caller_loop)

  def onPADLengthError(self, announced_xpad_len, xpad_len):
    pass


class RadioController():
  PROGRAM_DISCOVERY_TIMEOUT = 10
  
  def __init__(self, gain=-1):
#    test = c_lib.RadioController()
#    test.WPH_Test()
    self.gain = gain    
    self.programs            = {}
    self._programme_handlers = {}

    self._current_channel = ""
    self.ensemble_label   = None

    # lock to prevent parallel initialization from multiple users
    self._subscription_lock = asyncio.Lock()

    
  # Note: This method must not be called by __init__, as self cannot yet be used at this point
  def init(self, device_name = "auto"):
    self.c_impl = c_lib.init_device(self, device_name, self.gain)

  def onSNR(self, snr):
    pass
    
  def onFrequencyCorrectorChange(self, fine, coarse):
    pass
    
  def onSyncChange(self, isSync):
    if isSync[0]:
      pass
    
  def onSignalPresence(self, isSignal):
    pass
    
  def onServiceDetected(self, sId):
    if not sId in self.programs:
      self.programs[sId] = None
    
  def onNewEnsemble(self, eId):
    pass
    
  def onSetEnsembleLabel(self, label):
    self.ensemble_label = label

  def onDateTimeUpdate(self, timestamp):
    self.datetime = datetime.datetime.fromtimestamp(timestamp)

  def onFIBDecodeSuccess(self, crcCheckOk, fib):
    pass
    
  def onMessage(self, text, text2, isError):
    pass
    
  def _get_program_id(self, program_name):
    for sId in self.programs:
      if not self.programs[sId] or len(self.programs[sId]) == 0:
        self.programs[sId] = c_lib.get_service_name(self.c_impl, sId).rstrip()
      if self.programs[sId] == program_name:
        return sId
    # Not found
    return None


  async def _wait_for_channel(self, program_name):
    # initial check, as we might already have an active subscription for the program
    program_pid = self._get_program_id(program_name)
    if program_pid:
      return program_pid
    
    # wait the defined time for the program discovery 
    # and check every 0.5 seconds if it was succesful
    for _ in range(2 * RadioController.PROGRAM_DISCOVERY_TIMEOUT):
      await asyncio.sleep(0.5)
      program_pid = self._get_program_id(program_name)
      if program_pid:
        return program_pid
    # Not found
    return None
      

  # returns handler in case the subscription suceeded, otherwise None
  async def subscribe_program(self, channel, program_name):
    async with self._subscription_lock:
      # Block actions in case there is another channel active
      if self._current_channel and self._current_channel != channel:
        return None

      # If There is no active channel, tune the device to the channel
      if not self._current_channel:
        tune_okay = c_lib.set_channel(self.c_impl, channel)
        if tune_okay:
          self._current_channel = channel
        else:
          print("could not start device, fatal")
          return None

      # Wait for the selected program to appear in the channel
      try:
        program_pid = await self._wait_for_channel(program_name)

      # Because the user might cancel the subscription request while waiting,
      # we need to check for CancelledError and ConnectionResetError.
      # In these cases, we need to reset the c lib to get back to an idle state. 
      except (asyncio.exceptions.CancelledError,
            ConnectionResetError):
        if not self._programme_handlers:
          await self._reset()
				# re-throw the exception so the caller can also do its cleanup
        raise

      # The program is not part of the channel
      if not program_pid:
        if not self._programme_handlers:
          await self._reset()
        return None
       
      # the program exists in the channel. Check if there is already an active subscription
      if program_pid in self._programme_handlers:
        programme_handler = self._programme_handlers[program_pid]
      else:
        # First time subscription to the channel. Set up the handler and register it.
        programme_handler = WavProgrammeHandler(self, program_pid)
        self._programme_handlers[program_pid] = programme_handler
        if not c_lib.subscribe_program(self.c_impl, programme_handler, program_pid):
          if not self._programme_handlers:
            await self._reset()
          return None

      # increase the counter of active subscriptions for the selected program
      programme_handler._subscribers += 1
      logger.debug('subscribers:', programme_handler._subscribers)
      return programme_handler


  async def unsubscribe_program(self, program_name):
    async with self._subscription_lock:
      program_pid = self._get_program_id(program_name)
      if program_pid:
        await self._unsubscribe(program_pid)


  def is_playing(self, program_name):
    program_pid = self._get_program_id(program_name)
    if not program_pid:
      return False
    else:
      return program_pid in self._programme_handlers


  async def _unsubscribe(self, program_pid):
    programme_handler = self._programme_handlers[program_pid]
    if not programme_handler:
      return

    programme_handler._subscribers -= 1
    logger.debug('subscribers:', programme_handler._subscribers)
    if programme_handler._subscribers == 0:
      c_lib.unsubscribe_program(self.c_impl, program_pid)
      self._programme_handlers[program_pid]._release_waiters()
      del self._programme_handlers[program_pid]
      await asyncio.sleep(1)
      if not self._programme_handlers:
        await self._reset()

  async def _reset(self):
    c_lib.set_channel(self.c_impl, "")
    self._current_channel = None
    self.programs.clear()
    await asyncio.sleep(1)
  
  async def finalize(self):
    active_pids = list(self._programme_handlers.keys())
    for program_pid in active_pids:
      await self._unsubscribe(program_pid)
    c_lib.close_device(self.c_impl)
    c_lib.finalize(self.c_impl)
    
