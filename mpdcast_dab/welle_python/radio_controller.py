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

"""Controller that receives streaming requests and interacts with the welle.io interface """

import asyncio
import datetime
import logging
from mpdcast_dab.welle_python.wav_programme_handler import WavProgrammeHandler
from mpdcast_dab.welle_python.dab_callbacks import RadioControllerInterface

logger = logging.getLogger(__name__)

class RadioController(RadioControllerInterface):
  PROGRAM_DISCOVERY_TIMEOUT = 10
  CHANNEL_UNSUBSCRIBE_DELAY = 5

  def __init__(self, device):
    self._dab_device = device
    self.programs            = {}
    self._programme_handlers = {}

    self._current_channel = ''
    self.ensemble_label   = None
    self.datetime         = None

    '''
    event _cancel_delayed_unsubscribe will:
     not be set (or cleared) when we wait for somebody to cancel a delayed unsubscribe
     set when the unsubscribe
      -shall be cancelled or
      -there is no delayed unsubscribe pending
     awaited to be set during a potential unsubscription cancel:
     event set => the unsubscribe was cancelled, so dont reset
     Timeout => unsubscribe was not cancelled, so reset (or dont in case someone did an immediate unsubscribe)
    '''
    self._cancel_delayed_unsubscribe = asyncio.Event()
    self._cancel_delayed_unsubscribe.set()

    # lock to prevent parallel initialization from multiple users
    self._subscription_lock = asyncio.Lock()

  async def on_service_detected(self, service_id):
    if not service_id in self.programs:
      self.programs[service_id] = None

  async def on_set_ensemble_label(self, label):
    self.ensemble_label = label

  async def on_datetime_update(self, timestamp):
    self.datetime = datetime.datetime.fromtimestamp(timestamp)

  def _get_program_id(self, lookup_name):
    for service_id, program_name in self.programs.items():
      if not program_name or len(program_name) == 0:
        self.programs[service_id] = self._dab_device.get_service_name(service_id).rstrip()
      if self.programs[service_id] == lookup_name:
        return service_id
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
    # first check, if there is a delayed un-subscription pending
    if not self._cancel_delayed_unsubscribe.is_set():
      # we have an active subscription, but no subscribers.
      # check if we can reuse the subscription
      if self._current_channel == channel:
        # yes, we can. So notify to cancel the unsubscribe
        self._cancel_delayed_unsubscribe.set()
      else:
        # no, we cant. Trigger the delayed unsubscribe to happen immediately
        async with self._subscription_lock:
          await self._reset_channel()
    # now we do the actual subscribe job
    async with self._subscription_lock:
      # Block actions in case there is another channel active
      if self._current_channel and self._current_channel != channel:
        logger.warning('there is another channel active')
        return None

      # If There is no active channel, tune the device to the channel
      if not self._current_channel:
        if not self._dab_device.aquire_now(self):
          logger.warning('DAB device is locked. No playback possible.')
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
        await self._reset_if_no_handler()
        # re-throw the exception so the caller can also do its cleanup
        raise

      # The program is not part of the channel
      if not program_pid:
        await self._reset_if_no_handler()
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
          await self._reset_if_no_handler()
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
    return program_pid in self._programme_handlers


  async def _unsubscribe(self, program_pid):
    programme_handler = self._programme_handlers[program_pid]
    if not programme_handler:
      return

    programme_handler.subscribers -= 1
    logger.debug('subscribers: %d', programme_handler.subscribers)
    if programme_handler.subscribers == 0:
      self._dab_device.unsubscribe_program(program_pid)
      self._programme_handlers[program_pid].release_waiters()
      del self._programme_handlers[program_pid]
      asyncio.get_running_loop().create_task(self._reset_if_no_handler())

  async def _reset_if_no_handler(self):
    if self._programme_handlers:
      return
    # wait to see if someone wants to reuse the subscription
    reset_target_channel = self._current_channel
    try:
      self._cancel_delayed_unsubscribe.clear()
      await asyncio.wait_for(self._cancel_delayed_unsubscribe.wait(), RadioController.CHANNEL_UNSUBSCRIBE_DELAY)
      # as the subscription will be reused, dont reset
      return
    except TimeoutError:
      # timeout passed without somebody cancelling the delayed unsubscribe
      async with self._subscription_lock:
        # make sure our job is still valid (nobody in the meantime triggered an immediate unsubscribe)
        if self._current_channel and self._current_channel == reset_target_channel:
          await self._reset_channel()


  async def _reset_channel(self):
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
