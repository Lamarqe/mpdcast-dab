from abc import ABC, abstractmethod

import mpdcast_dab.welle_python.libwelle_py as welle_io

class ProgrammeHandlerInterface(ABC):

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


class RadioControllerInterface(ABC):

  def onSNR(self, snr: float) -> None:
    pass
    
  def onFrequencyCorrectorChange(self, fine: int, coarse: int) -> None:
    pass
    
  def onSyncChange(self, isSync: int) -> None:
    pass
    
  def onSignalPresence(self, isSignal: int) -> None:
    pass
    
  def onServiceDetected(self, sId: int) -> None:
    pass
    
  def onNewEnsemble(self, eId: int) -> None:
    pass
    
  def onSetEnsembleLabel(self, label: str) -> None:
    pass

  def onDateTimeUpdate(self, timestamp: int) -> None:
    pass

  def onFIBDecodeSuccess(self, crcCheckOk: int, fib: int) -> None:
    pass
    
  def onMessage(self, text: str, text2: str, isError: int) -> None:
    pass


class DabDevice():
  def __init__(self):
    self._capsule = None

  def initialized(self) -> bool:
    return self._capsule is not None

  def init_device(self, controller: RadioControllerInterface, device_name: str, gain: int = -1) -> bool:
    if not self._capsule:
      self._capsule = welle_io.init_device(controller, device_name, gain)
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

  def close_device(self) -> bool:
    if not self._capsule:
      return False
    else:
      welle_io.close_device(self._capsule)
      return True

  def finalize(self) -> bool:
    if not self._capsule:
      return False
    else:
      welle_io.finalize(self._capsule)
      self._capsule = None
      return True

  def get_service_name(self, service_id: int) -> str:
    if not self._capsule:
      return None
    else:
      return welle_io.get_service_name(self._capsule, service_id)

  def all_channel_names() -> list[str]:
    return welle_io.all_channel_names()
