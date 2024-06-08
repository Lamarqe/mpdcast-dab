import asyncio
import zeroconf
import pychromecast

class CastFinder(pychromecast.discovery.AbstractCastListener):  
  def __init__(self, deviceName):
    self._deviceName = deviceName

  def add_cast(self, uuid, _service):
    if (self._deviceName == self._browser.services[uuid].friendly_name):
      self.device = self._browser.services[uuid]
      self._my_task.set()

  def remove_cast(self, uuid, _service, cast_info): pass
  def update_cast(self, uuid, _service): pass
  
  def doDiscovery (self):
    asyncio.run(self._doDiscovery())

  async def _doDiscovery (self):
    self._browser = pychromecast.discovery.CastBrowser(self, zeroconf.Zeroconf(), None)
    self._my_task = asyncio.Event()
    self._browser.start_discovery()
    await self._waitForDiscoveryEnd()
    self._browser.stop_discovery()    

  async def _waitForDiscoveryEnd(self):
    await self._my_task.wait()
