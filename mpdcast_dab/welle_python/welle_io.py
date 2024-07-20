from abc import ABC, abstractmethod

import mpdcast_dab.welle_python.libwelle_py as welle_io
import asyncio
import atexit
import time
import logging
logger = logging.getLogger(__name__)


class ProgrammeHandlerInterface():

  def onFrameErrors(self, frameErrors: int) -> None:
    pass

  def onNewAudio(self, audio_data: bytes, sample_rate: int, mode: str) -> None:
    pass

  def onRsErrors(self, uncorrectedErrors: int, numCorrectedErrors: int) -> None:
    pass

  def onAacErrors(self, aacErrors: int) -> None:
    pass

  def onNewDynamicLabel(self, label: str) -> None:
    pass
    
  def onMOT(self, data: bytes, mime_type: str, name: str) -> None:
    pass


class RadioControllerInterface():

  async def onSNR(self, snr: float) -> None:
    pass
    
  async def onFrequencyCorrectorChange(self, fine: int, coarse: int) -> None:
    pass
    
  async def onSyncChange(self, isSync: int) -> None:
    pass
    
  async def onSignalPresence(self, isSignal: int) -> None:
    pass

  async def onServiceDetected(self, sId: int) -> None:
    pass
    
  async def onNewEnsemble(self, eId: int) -> None:
    pass
    
  async def onSetEnsembleLabel(self, label: str) -> None:
    pass

  async def onDateTimeUpdate(self, timestamp: int) -> None:
    pass

  async def onFIBDecodeSuccess(self, crcCheckOk: int, fib: int) -> None:
    pass
    
  async def onMessage(self, text: str, text2: str, isError: int) -> None:
    pass


class Forwarder():
  def __getattr__(self, attr):
    method = getattr(self.forward_object, attr)
    def asyncio_callback(*args, **kwargs):
      asyncio.run_coroutine_threadsafe(method(*args, **kwargs), self._loop)
    return asyncio_callback

class DabDevice():
  def __init__(self, device_name: str = 'auto', gain: int = -1):
    self._controller_stub = RadioControllerInterface()
    self._forwarder = Forwarder()
    self._forwarder.forward_object = self._controller_stub
    self._forwarder._loop = asyncio.get_event_loop() # = loop
    self._capsule = welle_io.init_device(self._forwarder, device_name, gain)
    if self._capsule:
      atexit.register(self.cleanup)

  def aquire_now(self, radio_controller: RadioControllerInterface) -> bool:
    if self._forwarder.forward_object == self._controller_stub:
      self._forwarder.forward_object = radio_controller
      return True
    else:
      return False

  def release(self) -> bool:
    if self._forwarder.forward_object != self._controller_stub:
      self._forwarder.forward_object = self._controller_stub
      return True
    else:
      return False

  def is_usable(self) -> bool:
    return self._capsule is not None

  def set_channel(self, channel: str, is_scan: bool = False) -> bool:
    if not self._capsule:
      return False
    else:
      return welle_io.set_channel(self._capsule, channel, is_scan)

  def subscribe_program(self, handler: ProgrammeHandlerInterface, service_id: int) -> bool:
    if not self._capsule:
      return False
    else:
      return welle_io.subscribe_program(self._capsule, handler, service_id)

  def unsubscribe_program(self, service_id: int) -> bool:
    if not self._capsule:
      return False
    else:
      return welle_io.unsubscribe_program(self._capsule, service_id)

  def cleanup(self) -> None:
    if self._capsule:
      welle_io.set_channel(self._capsule, '', False)
      welle_io.close_device(self._capsule)
      # wait for all c-lib callbacks to be processed in python. Otherwise we might deadlock
      time.sleep(0.1)
      welle_io.finalize(self._capsule)
      self._capsule = None

  def get_service_name(self, service_id: int) -> str:
    if not self._capsule:
      return None
    else:
      return welle_io.get_service_name(self._capsule, service_id)

  def all_channel_names() -> list[str]:
    return welle_io.all_channel_names()
