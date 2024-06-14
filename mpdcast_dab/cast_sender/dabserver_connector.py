import time
import aiohttp
import yarl
import logging
logger = logging.getLogger(__name__)

class DabserverStation():
  """
  Connector to interact with Dabserver.
  Handle playlist items like: http://<dab_server>:8080/stream/11D/BAYERN%203
  """

  def __init__(self, song_urlstring):
    self.song_url = yarl.URL(song_urlstring)
    self._initialized = False
    self.image_url = 'https://www.worlddab.org/image/content/2054/400x235_DABplus_Logo_Farbe_sRGB.png'
    self.label = ''

  async def initialize(self):
    logger.info('initializing dab server')
    self._initialized = True
    channel_path_items = self.song_url.parts

    if (len(channel_path_items) == 4
      and channel_path_items[1] == 'stream'):
      self.channel_name = channel_path_items[2]
      self.station_name = channel_path_items[3]
      # validate the dab server presence by checking the initial label
      label_path = 'label/current/' + self.channel_name + '/' + self.station_name
      label_url = self.song_url.with_path(label_path)
      
      try:
        async with aiohttp.ClientSession() as session:
          async with session.get(label_url, timeout=300) as label_response:
            self.label = await label_response.text()
            logger.info('return true')
            return True

      except (aiohttp.client_exceptions.ServerDisconnectedError, TimeoutError):
        logger.info('return false, exception')
        return False
    else:
      logger.info('return false, not 4 items')
      return False
    
  async def new_label(self):
    label_path = 'label/next/' + self.channel_name + '/' + self.station_name
    label_url = self.song_url.with_path(label_path)

    async with aiohttp.ClientSession() as session:
      while True:
        async with session.get(label_url, timeout=None) as label_response:
          if label_response.status == 200:
            self.label = await label_response.text()
            return
          else:
            await asyncio.sleep(1)
        
  async def new_image(self):
    image_path = 'image/next/' + self.channel_name + '/' + self.station_name
    image_url = self.song_url.with_path(image_path)

    async with aiohttp.ClientSession() as session:
      while True:
        async with session.get(image_url, timeout=None) as image_response:
          if image_response.status == 200:
            image_path = 'image/current/' + self.channel_name + '/' + self.station_name
            image_url = self.song_url.with_path(image_path).with_query(str(int(time.time())))
            self.image_url = str(image_url)
            return
          else:
            await asyncio.sleep(1)
