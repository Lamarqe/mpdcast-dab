import asyncio
import datetime
import logging
logger = logging.getLogger(__name__)

from mpdcast_dab.welle_python.wav_programme_handler import WavProgrammeHandler, UnsubscribedError
from mpdcast_dab.welle_python.welle_io import RadioControllerInterface, DabDevice

class RadioController(RadioControllerInterface):
  PROGRAM_DISCOVERY_TIMEOUT = 10
  
  def __init__(self, device: DabDevice):
    self._dab_device = device
    self.programs            = {}
    self._programme_handlers = {}

    self._current_channel = ''
    self.ensemble_label   = None

    # lock to prevent parallel initialization from multiple users
    self._subscription_lock = asyncio.Lock()
    
  async def onServiceDetected(self, sId):
    if not sId in self.programs:
      self.programs[sId] = None
    
  async def onSetEnsembleLabel(self, label):
    self.ensemble_label = label

  async def onDateTimeUpdate(self, timestamp):
    self.datetime = datetime.datetime.fromtimestamp(timestamp)

  def _get_program_id(self, program_name):
    for sId in self.programs:
      if not self.programs[sId] or len(self.programs[sId]) == 0:
        self.programs[sId] = self._dab_device.get_service_name(sId).rstrip()
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
        logger.error('there is another channel active')
        return None

      # If There is no active channel, tune the device to the channel
      if not self._current_channel:
        if not self._dab_device.aquire_now(self):
          logger.error('DAB device is locked. No playback possible.')
          return None

        tune_okay = self._dab_device.set_channel(channel)
        if tune_okay:
          self._current_channel = channel
        else:
          print("could not start device, fatal")
          self._dab_device.release()
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
        logger.error('The program %s is not part of the channel %s', program_name, channel)
        return None
       
      # the program exists in the channel. Check if there is already an active subscription
      if program_pid in self._programme_handlers:
        programme_handler = self._programme_handlers[program_pid]
      else:
        # First time subscription to the channel. Set up the handler and register it.
        programme_handler = WavProgrammeHandler()
        self._programme_handlers[program_pid] = programme_handler
        if not self._dab_device.subscribe_program(programme_handler, program_pid):
          if not self._programme_handlers:
            await self._reset()
          logger.error('Subscription to selected program failed')
          return None

      # increase the counter of active subscriptions for the selected program
      programme_handler.subscribers += 1
      logger.debug('subscribers: %d', programme_handler.subscribers)
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

    programme_handler.subscribers -= 1
    logger.debug('subscribers: %d', programme_handler.subscribers)
    if programme_handler.subscribers == 0:
      self._dab_device.unsubscribe_program(program_pid)
      self._programme_handlers[program_pid]._release_waiters()
      del self._programme_handlers[program_pid]
      if not self._programme_handlers:
        await self._reset()

  async def _reset(self):
    self._dab_device.set_channel("")
    self._current_channel = None
    self.programs.clear()
    self._dab_device.release()
  
  async def unsubscribe_all_programs(self):
    async with self._subscription_lock:
      active_pids = list(self._programme_handlers.keys())
      for program_pid in active_pids:
        await self._unsubscribe(program_pid)
  
  def get_current_channel(self):
    return self._current_channel