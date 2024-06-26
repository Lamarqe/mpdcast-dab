import json
import aiohttp
import yarl
import logging
logger = logging.getLogger(__name__)

supported_stream_links = {'channelnumber': 'number', 'channelname': 'name', 'channel': 'uuid'}

class TvheadendChannel():
  """
  Connector to interact with Tvheadend.
  Handle playlist items like: http://<tvh_server>:9981/stream/channelname/BAYERN%203
  """

  def __init__(self, song_urlstring):
    self.song_url = yarl.URL(song_urlstring)
    self._initialized = False
    self._channel_data = None

  async def initialize(self):
    logger.info('initializing tvheadend server')
    self._initialized = True
    channel_path_items = self.song_url.path_qs.split('/')

    if (len(channel_path_items) == 4 
      and channel_path_items[1] == 'stream' 
      and channel_path_items[2] in supported_stream_links):
      
      filter_field = supported_stream_links[channel_path_items[2]]
      channel_id = channel_path_items[3]
      
      data = {}
      data['start'] = '0'
      data['limit'] ='1'
      data['sort']  ='name'
      data['dir']    = 'ASC'
      filter1 = {}
      filter1['type'] = 'string'
      filter1['value'] = channel_id
      filter1['field'] = filter_field
      filter2 = {}
      filter2['type'] = 'string'
      filter2['value'] = 'Radio'
      filter2['field'] = 'tags'
      filters = [filter1, filter2]
      data['filter'] = json.dumps(filters)
      channel_url = self.song_url.with_path('api/channel/grid')
      
      async with aiohttp.ClientSession() as session:
        async with session.post(channel_url, data=data) as channel_response:
          channel_json = await channel_response.json()
          
      # Make sure the channel id is really equal (dont use "QVC ZWEI" instead of "QVC")
      for entry in channel_json['entries']:
        if entry[filter_field] == channel_id:
          self._channel_data = entry
          return True
    # channel was not found
    return False
            
  def name(self):
    return self._channel_data['name']
  
  async def current_show(self):
    if not self._initialized:
      await self.initialize()
    
    if self._channel_data:
      data = {}
      data['start']   = '0'
      data['limit']   ='1'
      data['sort']    ='channelnumber'
      data['dir']     = 'ASC'
      data['mode']    = 'now'
      data['channel'] = self._channel_data['uuid']
      epg_url = self.song_url.with_path('api/epg/events/grid')
      
      async with aiohttp.ClientSession() as session:
        async with session.post(epg_url, data=data) as epg_response:
          epg_json = await epg_response.json()
      
      if 'entries' in epg_json and len(epg_json['entries']) > 0:
        return epg_json['entries'][0]
    
    else:
      return None

  async def image_url(self):
    if not self._initialized:
      await self.initialize()
    
    if self._channel_data:
      if 'icon_public_url' in self._channel_data:
          image_path = self._channel_data['icon_public_url']
      else:
        image_path = 'static/img/logobig.png'
      
      return str(self.song_url.with_path(image_path))

    else:
      return None
