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

"""DAB Web request processing module."""

import asyncio
import json
import logging
from aiohttp import web

from mpdcast_dab.welle_python.radio_controller import RadioController
from mpdcast_dab.welle_python.dab_scanner import DabScanner
from mpdcast_dab.welle_python.wav_programme_handler import UnsubscribedError
from mpdcast_dab.welle_python.welle_io import DabDevice

logger = logging.getLogger(__name__)

class DabServer():

  def __init__(self, my_ip, port):
    self.my_ip = my_ip
    self.port = port
    device = DabDevice('auto')
    if device.is_usable():
      self.radio_controller = RadioController(device)
      self.scanner = DabScanner(device)
    else:
      self.radio_controller = None
      self.scanner = None

    self.handlers = {}
    self._shutdown_in_progress = False

  def get_routes(self):
    return [web.get('/DAB.m3u8', self.get_scanner_playlist),
            web.get('/get_scanner_details', self.get_scanner_details),
            web.post('/start_scan', self.start_scan),
            web.post('/stop_scan', self.stop_scan),
            web.get(r'/stream/{channel:[0-9]{1,2}[A-Z]}/{program:.+}', self.get_audio),
            web.get(r'/image/current/{channel:[0-9]{1,2}[A-Z]}/{program:.+}', self.get_current_image),
            web.get(r'/label/current/{channel:[0-9]{1,2}[A-Z]}/{program:.+}', self.get_current_label),
            web.get(r'/image/next/{channel:[0-9]{1,2}[A-Z]}/{program:.+}', self.get_next_image),
            web.get(r'/label/next/{channel:[0-9]{1,2}[A-Z]}/{program:.+}', self.get_next_label)]

  async def get_scanner_playlist(self, request):
    resp = self.scanner.get_playlist(self.my_ip, self.port)
    return web.Response(body = resp, content_type = 'audio/x-mpegurl')

  async def start_scan(self, request):
    resp = await self.scanner.start_scan()
    return web.Response(body = json.dumps(resp), content_type = 'application/json')

  async def stop_scan(self, request):
    resp = self.scanner.stop_scan()
    return web.Response(body = json.dumps(resp), content_type = 'application/json')

  async def get_scanner_details(self, request):
    resp = self.scanner.status()
    return web.Response(body = json.dumps(resp), content_type = 'application/json')

  async def stop(self):
    self._shutdown_in_progress = True
    await self.radio_controller.unsubscribe_all_programs()


  # is_float should only be true if the audio data is in 32-bit floating-point format.
  def wav_header(self, is_float, channels, bit_rate, sample_rate):
    bo = 'little'
    enc = 'ascii'
    # RIFF header
    return (bytes('RIFF', enc)                                         # Chunk ID
          + (0).to_bytes(4, bo)                                        # Chunk size: stream -> set to zero
          + bytes('WAVE', enc)                                         # Format

          # Sub-chunk 1
          + bytes('fmt ', enc)                                         # Sub-chunk 1 ID
          + (16).to_bytes(4, bo)                                       # Sub-chunk 1 size
          + (3 if is_float else 1).to_bytes(2, bo)                     # Audio format (floating point (3) or PCM (1))
          + channels.to_bytes(2, bo)                                   # Channels
          + sample_rate.to_bytes(4, bo)                                # Sample rate
          + (sample_rate * channels * (bit_rate // 8)).to_bytes(4, bo) # Bytes rate
          + (channels * (bit_rate // 8)).to_bytes(2, bo)               # Block align
          + bit_rate.to_bytes(2, bo)                                   # Bits per sample

          # Sub-chunk 2
          + bytes('data', enc)                                         # Sub-chunk 2 ID
          + (0).to_bytes(4, bo))                                       # Sub-chunk 2 size: stream -> set to zero

  async def get_next_image(self, request):
    channel = request.match_info['channel']
    program = request.match_info['program']
    logger.debug('get_next_image: channel: %s program: %s', channel, program)
    if program in self.handlers:
      try:
        image = await self.handlers[program].new_picture()
        return web.Response(body = image['data'],
                            content_type = image['type'],
                            headers={'Cache-Control': 'no-cache', 'Connection': 'Close'})
      except UnsubscribedError as exc:
        raise web.HTTPBadRequest() from exc
    else:
      raise web.HTTPNotFound()


  async def get_next_label(self, request):
    channel = request.match_info['channel']
    program = request.match_info['program']
    logger.debug('get_next_label: channel: %s program: %s', channel, program)
    if program in self.handlers:
      try:
        label = await self.handlers[program].new_label()
        return web.Response(text=label,
                            headers={'Cache-Control': 'no-cache', 'Connection': 'Close'})
      except UnsubscribedError as exc:
        raise web.HTTPBadRequest() from exc
    else:
      raise web.HTTPNotFound()


  async def get_current_image(self, request):
    channel = request.match_info['channel']
    program = request.match_info['program']
    logger.debug('get_current_image: channel: %s program: %s', channel, program)
    if (program in self.handlers and len(self.handlers[program].data.picture['data']) > 0):
      return web.Response(body = self.handlers[program].data.picture['data'],
                          content_type = self.handlers[program].data.picture['type'],
                          headers={'Cache-Control': 'no-cache', 'Connection': 'Close'})
    # no data found
    raise web.HTTPNotFound()


  async def get_current_label(self, request):
    channel = request.match_info['channel']
    program = request.match_info['program']
    logger.debug('get_current_label: channel: %s program: %s', channel, program)
    if program in self.handlers:
      return web.Response(text=self.handlers[program].data.label,
                          headers={'Cache-Control': 'no-cache', 'Connection': 'Close'})
    # no data found
    raise web.HTTPNotFound()


  async def get_audio(self, request, retry = True):
    if self._shutdown_in_progress:
      raise web.HTTPServiceUnavailable()

    channel = request.match_info['channel']
    program = request.match_info['program']
    if program.startswith('cover.'):
      raise web.HTTPNotFound()
    logger.info('new audio request for %s', program)

    # Check if the device is busy with streaming another channel
    if retry and self.radio_controller.get_current_channel() and self.radio_controller.get_current_channel() != channel:
      # This might be a program switch with the new subscription request coming faster then the unsubscribe.
      # So lets check by waiting for half a second and then retry.
      # In case of a switch, the unsubscribe will be processed then
      await asyncio.sleep(0.5)
      await self.get_audio(request, False)

    handler = await self.radio_controller.subscribe_program(channel, program)
    if not handler:
      raise web.HTTPServiceUnavailable()

    # from here on, the device sends us the audio stream
    # send it via stream response until the user cancels it
    self.handlers[program] = handler
    try:
      response = web.StreamResponse(
        status=200,
        reason='OK',
        headers={'Content-Type': 'audio/wav','Cache-Control': 'no-cache', 'Connection': 'Close'})
      await response.prepare(request)

      # prepend the wav header to the initial response
      next_audio_frame, audio = await handler.new_audio()
      header = self.wav_header(False, 2, 16, handler.data.sample_rate)
      await response.write(header + audio)

      while True:
        next_audio_frame, audio = await handler.new_audio(next_audio_frame)
        await response.write(audio)
#        await asyncio.sleep(0.1)  # consider using this for performance gains
    except (asyncio.exceptions.CancelledError,
            asyncio.exceptions.TimeoutError,
            ConnectionResetError):
      # user cancelled the stream, so unsubscribe
      await self.radio_controller.unsubscribe_program(program)
      if not self.radio_controller.is_playing(program):
        del self.handlers[program]
      return response
    except UnsubscribedError:
      return response

    # Make sure above that this line remains unreachable
    raise web.HTTPInternalServerError()
