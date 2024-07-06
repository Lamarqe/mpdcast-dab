#!/usr/bin/env python3
# coding=utf-8

import io
import os
import sys
import asyncio
import argparse
import socket
import ifaddr
import time
import logging

import threading
import traceback

if __name__ == '__main__':
  sys.path.append(os.path.dirname(__file__)  + '/../..')

from mpdcast_dab.cast_sender.OutputGrabber import *
import mpdcast_dab.cast_sender.imageserver as imageserver
from mpdcast_dab.cast_sender.mpd_caster import *

from mpdcast_dab.welle_python.dabserver import *

def get_first_ipv4_address():
  for iface in ifaddr.get_adapters():
    for addr in iface.ips:
      # Filter out link-local addresses.
      if addr.is_IPv4:
        if not (addr.ip.startswith('169.254.') or addr.ip == '127.0.0.1'):
          return addr.ip
  return None

async def setup_webserver(runner, port):
  await runner.setup()
  site = web.TCPSite(runner, '0.0.0.0', port)
  await site.start()

def updateLoggerConfig():
  logging.basicConfig(format='%(message)s', encoding='utf-8', level=logging.INFO, stream=sys.stdout, force=True)
#  logging.basicConfig(encoding='utf-8', level=logging.INFO, stream=sys.stdout, force=True)

def main():
  CAST_PATH = '/cast_receiver'
  CAST_PAGE = 'receiver.html'
  WEB_PORT = 8080

  parser = argparse.ArgumentParser(description='MPD Cast Device Agent')
  parser.add_argument('--verbose', help = 'Enable verbose output', action = 'store_true')
  parser.add_argument('--conf', help = 'mpd config file to use. Default: /etc/mpd.conf', default = '/etc/mpd.conf')

  args = vars(parser.parse_args())

  my_ip = get_first_ipv4_address()
  if not my_ip:
    print ('Fatal: could not retrieve local IP address')
    return

  mpdConfig = load_mpd_config(args['conf'])
  
  image_request_handler = imageserver.ImageRequestHandler(my_ip, WEB_PORT)
  # In order to allow C console logs to be forwarded, it requires a message from C to stdout.
	# This is why we create the DabServer already here (before setting up logging), 
	# as it initializes the C lib and with it send some messages to stdout
  dab_server = DabServer(my_ip, WEB_PORT)

  ##############################################################################
  #why is the following call necessary?
  #liba = ctypes.cdll.LoadLibrary('./libtest.dylib')
  #liba.init()  # Will print at least one char via C to stdout
  ##############################################################################
  stdoutGrabber = OutputGrabber('c_stdout', sys.stdout)
  stderrGrabber = OutputGrabber('c_stderr', sys.stderr)
  sys.stdout = stdoutGrabber.redirect_stream()
  sys.stderr = stderrGrabber.redirect_stream()
  updateLoggerConfig()
  
  dab_server.init_dab_device()

  web_app = web.Application()
  web_app.add_routes([web.static(CAST_PATH, '/usr/share/dab2chromecast/cast_receiver')])
  web_app.add_routes(image_request_handler.get_routes())
  web_app.add_routes(dab_server.get_routes())
  runner = web.AppRunner(web_app)
  
  cast_receiver_url = 'http://' + my_ip + ':' + str(WEB_PORT) + CAST_PATH + '/' + CAST_PAGE
    
  try:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(setup_webserver(runner, WEB_PORT))

    # run the webserver in parallel to the cast task
    while True:
      # wait until we find the cast device in the network
      mpd_caster = MpdCaster(mpdConfig, my_ip, image_request_handler, cast_receiver_url)
      
      mpd_caster.waitfor_and_register_device()
      # run the cast (until chromecast disconnects)
      loop.run_until_complete(mpd_caster.cast_forever())

  except KeyboardInterrupt:
    mpd_caster.stop()
    loop.run_until_complete(runner.cleanup())
    loop.run_until_complete(dab_server.stop())
    stdoutGrabber.cleanup()
    stderrGrabber.cleanup()

if __name__ == '__main__':
  main()
