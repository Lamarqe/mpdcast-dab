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
from mpdcast_dab.welle_python.service_controller import ServiceController
from mpdcast_dab.welle_python.dab_callbacks import ChannelEventPass
from mpdcast_dab.welle_python.welle_io import ChannelEventHandler

logger = logging.getLogger(__name__)

class RadioController(ChannelEventHandler, ChannelEventPass):

  @dataclasses.dataclass
  class Service:
    name:       str               = None
    controller: ServiceController = None

  @dataclasses.dataclass
  class ChannelData:
    name:               str = ''
    ensemble_label:     str = None
    datetime:           int = None

  SERVICE_DISCOVERY_TIMEOUT = 10
  CHANNEL_RESET_DELAY       = 5

  def __init__(self, device):
    ChannelEventHandler.__init__(self)
    self._dab_device         = device
    self._services           = {}
    self._channel            = self.ChannelData()
    self._channel_reset_task = None

    # lock to prevent parallel initialization from multiple users
    self._subscription_lock = asyncio.Lock()

  async def on_service_detected(self, service_id):
    if not service_id in self._services:
      self._services[service_id] = self.Service()

  async def on_set_ensemble_label(self, label):
    self._channel.ensemble_label = label

  async def on_datetime_update(self, timestamp):
    self._channel.datetime = datetime.datetime.fromtimestamp(timestamp)

  def _fill_service_id(self, lookup_name):
    for service_id, service in self._services.items():
      if not service.name or len(service.name) == 0:
        service.name = self._dab_device.get_service_name(service_id).rstrip()
      if service.name == lookup_name:
        return service_id
    # Not found
    return None

  async def _wait_for_channel(self, service_name):
    # initial check, as we might already have an active subscription for the service
    service_id = self._fill_service_id(service_name)
    if service_id:
      return service_id

    # wait the defined time for the service discovery
    # and check every 0.5 seconds if it was succesful
    for _ in range(2 * RadioController.SERVICE_DISCOVERY_TIMEOUT):
      await asyncio.sleep(0.5)
      service_id = self._fill_service_id(service_name)
      if service_id:
        return service_id
    # Not found
    return None

  # returns controller in case the subscription suceeded, otherwise None
  async def subscribe_service(self, channel, service_name):
    async with self._subscription_lock:
      if not self._tune_channel(channel):
        return None
      return await self._subscribe_for_service_in_current_channel(service_name)

  def _tune_channel(self, channel):
    # first check, if there is a delayed channel reset pending
    if self._channel_reset_task:
      # we have an active channel, check if we can reuse it
      if self._channel.name != channel:
        # no, we cant. reset channel immediately, so we can select a new one afterwards
        self._reset_channel()
      # we either reuse the channel or we resetted it. In both cases: Cancel the delayed reset
      self._channel_reset_task.cancel()
      self._channel_reset_task = None

    # If there is a channel active, check if its the correct one
    if self._channel.name:
      if self._channel.name != channel:
        logger.warning('there is another channel active')
        return False
      # nothing to do for us here
      return True
    # There is no active channel. tune the device to the channel
    if not self._dab_device.lock.acquire(blocking=False):
      logger.error('DAB device is locked. No playback possible.')
      return False
    if not self._dab_device.set_channel(channel, self):
      logger.error("could not set the device channel.")
      self._dab_device.lock.release()
      return False
    # success!
    self._channel.name = channel
    return True

  async def _subscribe_for_service_in_current_channel(self, service_name):
    # Wait for the selected service to appear in the channel
    try:
      service_id = await self._wait_for_channel(service_name)

    # Because the user might cancel the subscription request while waiting,
    # we need to check for CancelledError and ConnectionResetError.
    # In these cases, we need to reset the c lib to get back to an idle state.
    except (asyncio.exceptions.CancelledError,
          ConnectionResetError):
      self._cleanup_channel()
      # re-throw the exception so the caller can also do its cleanup
      raise

    # The service is not part of the channel
    if not service_id:
      self._cleanup_channel()
      logger.error('The service %s is not part of the channel %s', service_name, self._channel.name)
      return None

    # the service exists in the channel. Check if there is already an active subscription
    service_controller = self._services[service_id].controller
    if not service_controller:
      # First time subscription to the service. Set up the controller and register it.
      service_controller = ServiceController()
      self._services[service_id].controller = service_controller
      if not self._dab_device.subscribe_service(service_controller, service_id):
        self._cleanup_channel()
        logger.error('Subscription to selected service failed')
        return None

    # increase the counter of active subscriptions for the selected service
    service_controller.subscribers += 1
    logger.debug('subscribers: %d', service_controller.subscribers)
    return service_controller

  def unsubscribe_service(self, lookup_name):
    for service_id, service in self._services.items():
      if service.name == lookup_name:
        self._unsubscribe(service_id)
        return

  def get_service_controller(self, lookup_name):
    for service_id, service in self._services.items():
      if service.name == lookup_name:
        service = self._services.get(service_id)
        return service.controller if service else None
    # not subscribed
    return None

  def _unsubscribe(self, service_id):
    service_controller = self._services[service_id].controller
    if not service_controller:
      return

    service_controller.subscribers -= 1
    logger.debug('subscribers: %d', service_controller.subscribers)
    if service_controller.subscribers == 0:
      self._dab_device.unsubscribe_service(service_id)
      self._services[service_id].controller.release_waiters()
      self._services[service_id].controller = None
      self._cleanup_channel()

  def _cleanup_channel(self):
    # only reset when there is no service subscription
    for service in self._services.values():
      if service.controller:
        return
    # no subscription found
    self._channel_reset_task = asyncio.get_running_loop().create_task(self._reset_channel_later())

  async def _reset_channel_later(self):
    await asyncio.sleep(RadioController.CHANNEL_RESET_DELAY)
    # the reset job did not get cancelled. So do it now
    self._reset_channel()
    self._channel_reset_task = None

  def _reset_channel(self):
    assert not next((srv for srv in self._services.values() if srv.controller is not None), None)
    self._dab_device.reset_channel()
    self._channel.name = None
    self._services.clear()
    self._dab_device.lock.release()

  def stop(self):
    active_sids = list(self._services.keys())
    for service_id in active_sids:
      self._unsubscribe(service_id)
    # cancel a pending reset and reset immediately
    if self._channel_reset_task:
      self._reset_channel()
      self._channel_reset_task.cancel()
      self._channel_reset_task = None

  def can_subscribe(self, new_channel):
    return (not self._channel.name or            # either there is no active channel
            self._channel.name == new_channel or # OR target and current channel are the same
            self._channel_reset_task)            # OR a delayed reset is pending
