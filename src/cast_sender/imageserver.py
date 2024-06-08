from aiohttp import web
import urllib


class ImageRequestHandler():
  URL_PREFIX = 'mpd_image/'
  
  def __init__(self, my_ip, port):
    self.my_ip  = my_ip
    self.port   = port
    self.images = {}

  def get_routes(self):
    return [web.get(r'/mpd_image/{song_path:.+}', self._http_handler)]

  def store_song_picture(self, song_path, picture_dict):
    self.images[song_path] = picture_dict
    return self._song_to_image_url(song_path)  
  
  # Chromecast will use this http interface to get the actual images
  async def _http_handler(self, request):
    song_path = request.match_info['song_path']
    
    if song_path in self.images:
      return web.Response(
        content_type = self.images[song_path]['type'],
        body         = self.images[song_path]['binary'])
    else:
      raise web.HTTPMovedPermanently('https://www.musicpd.org/logo.png')

  def _song_to_image_url(self, song_path):
    image_path = urllib.parse.quote(song_path)
    return 'http://' + self.my_ip + ':' + str(self.port) + '/' + ImageRequestHandler.URL_PREFIX + image_path
