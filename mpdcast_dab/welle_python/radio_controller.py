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
import dataclasses
from mpdcast_dab.welle_python.wav_programme_handler import WavProgrammeHandler
from mpdcast_dab.welle_python.dab_callbacks import RadioControllerInterface

logger = logging.getLogger(__name__)

class RadioController(RadioControllerInterface):
  @dataclasses.dataclass
  class ChannelData():
    def __init__(self):
      self.name           = ''
      self.ensemble_label = None
      self.datetime       = None

  PROGRAM_DISCOVERY_TIMEOUT = 10
  CHANNEL_RESET_DELAY       = 5

  def __init__(self, device):
    self._dab_device         = device
    self._programs           = {}
    self._programme_handlers = {}
    self._channel            = self.ChannelData()
    self._channel_reset_task = None

    # lock to prevent parallel initialization from multiple users
    self._subscription_lock = asyncio.Lock()

  async def on_service_detected(self, service_id):
    if not service_id in self._programs:
      self._programs[service_id] = None

  async def on_set_ensemble_label(self, label):
    self._channel.ensemble_label = label

  async def on_datetime_update(self, timestamp):
    self._channel.datetime = datetime.datetime.fromtimestamp(timestamp)

  def _fill_service_id(self, lookup_name):
    for service_id, program_name in self._programs.items():
      if not program_name or len(program_name) == 0:
        self._programs[service_id] = self._dab_device.get_service_name(service_id).rstrip()
      if self._programs[service_id] == lookup_name:
        return service_id
    # Not found
    return None

  async def _wait_for_channel(self, program_name):
    # initial check, as we might already have an active subscription for the program
    service_id = self._fill_service_id(program_name)
    if service_id:
      return service_id

    # wait the defined time for the program discovery
    # and check every 0.5 seconds if it was succesful
    for _ in range(2 * RadioController.PROGRAM_DISCOVERY_TIMEOUT):
      await asyncio.sleep(0.5)
      service_id = self._fill_service_id(program_name)
      if service_id:
        return service_id
    # Not found
    return None

  # returns handler in case the subscription suceeded, otherwise None
  async def subscribe_program(self, channel, program_name):
    async with self._subscription_lock:
      if not self._tune_channel(channel):
        return None
      return await self._subscribe_for_service_in_current_channel(program_name)

  def _tune_channel(self, channel):
    # first check, if there is a delayed channel reset pending
    if self._channel_reset_task:
      # we have an active channel, check if we can reuse it
      if self._channel.name != channel:
        # no, we cant. reset channel immediately, so we can select a new one afterwards
        self._reset_channel()
      # we either reuse the channel or we resetted it. In both cases: Cancel the delayed reset
      self._channel_reset_task.cancel()

    # If there is a channel active, check if its the correct one
    if self._channel.name:
      if self._channel.name != channel:
        logger.warning('there is another channel active')
        return False
      # nothing to do for us here
      return True
    # There is no active channel. tune the device to the channel
    if not self._dab_device.aquire_now(self):
      logger.error('DAB device is locked. No playback possible.')
      return False
    if not self._dab_device.set_channel(channel):
      logger.error("could not set the device channel.")
      self._dab_device.release()
      return False
    # success!
    self._channel.name = channel
    return True

  async def _subscribe_for_service_in_current_channel(self, program_name):
    # Wait for the selected program to appear in the channel
    try:
      service_id = await self._wait_for_channel(program_name)

    # Because the user might cancel the subscription request while waiting,
    # we need to check for CancelledError and ConnectionResetError.
    # In these cases, we need to reset the c lib to get back to an idle state.
    except (asyncio.exceptions.CancelledError,
          ConnectionResetError):
      self._cleanup_channel()
      # re-throw the exception so the caller can also do its cleanup
      raise

    # The program is not part of the channel
    if not service_id:
      self._cleanup_channel()
      logger.error('The program %s is not part of the channel %s', program_name, self._channel.name)
      return None

    # the program exists in the channel. Check if there is already an active subscription
    if service_id in self._programme_handlers:
      programme_handler = self._programme_handlers[service_id]
    else:
      # First time subscription to the channel. Set up the handler and register it.
      programme_handler = WavProgrammeHandler()
      self._programme_handlers[service_id] = programme_handler
      if not self._dab_device.subscribe_program(programme_handler, service_id):
        self._cleanup_channel()
        logger.error('Subscription to selected program failed')
        return None

    # increase the counter of active subscriptions for the selected program
    programme_handler.subscribers += 1
    logger.debug('subscribers: %d', programme_handler.subscribers)
    return programme_handler

  def unsubscribe_program(self, lookup_name):
    for service_id, program_name in self._programs.items():
      if program_name == lookup_name:
        self._unsubscribe(service_id)
        return

  def get_handler(self, lookup_name):
    for service_id, program_name in self._programs.items():
      if program_name == lookup_name:
        return self._programme_handlers.get(service_id)
    # not subscribed
    return None

  def _unsubscribe(self, service_id):
    programme_handler = self._programme_handlers[service_id]
    if not programme_handler:
      return

    programme_handler.subscribers -= 1
    logger.debug('subscribers: %d', programme_handler.subscribers)
    if programme_handler.subscribers == 0:
      self._dab_device.unsubscribe_program(service_id)
      self._programme_handlers[service_id].release_waiters()
      del self._programme_handlers[service_id]
      self._cleanup_channel()

  def _cleanup_channel(self):
    # nothing to do if there is still at least one programme subscription
    if self._programme_handlers:
      return
    def remove_ref(task):
      self._channel_reset_task = None
    self._channel_reset_task = asyncio.get_running_loop().create_task(self._reset_channel_later())
    # clean up reference to the reset as soon as it is complete or got cancelled
    self._channel_reset_task.add_done_callback(remove_ref)

  async def _reset_channel_later(self):
    await asyncio.sleep(RadioController.CHANNEL_RESET_DELAY)
    # the reset job did not get cancelled. So do it now
    self._reset_channel()
    # no need to clean up reference. Will be done by done_callback

  def _reset_channel(self):
    assert bool(not self._programme_handlers)
    self._dab_device.set_channel("")
    self._channel.name = None
    self._programs.clear()
    self._dab_device.release()

  async def stop(self):
    async with self._subscription_lock:
      active_sids = list(self._programme_handlers.keys())
      for service_id in active_sids:
        await self._unsubscribe(service_id)
    # cancel a pending reset and reset immediately
    if self._channel_reset_task:
      self._channel_reset_task.cancel()
      self._reset_channel()

  def can_subscribe(self, new_channel):
    return (not self._channel.name or            # either there is no active channel
            self._channel.name == new_channel or # OR target and current channel are the same
            self._channel_reset_task)            # OR a delayed reset is pending
