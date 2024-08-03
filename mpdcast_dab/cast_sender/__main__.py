#!/usr/bin/env python3
# coding=utf-8

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

"""Main class which starts cast sender and DAB server"""

import sys
import asyncio
import argparse
import logging
import ifaddr
from aiohttp import web

from mpdcast_dab.cast_sender.output_grabber import OutputGrabber
from mpdcast_dab.cast_sender.mpd_caster import MpdCaster
from mpdcast_dab.welle_python.dab_server import DabServer

logger = logging.getLogger(__name__)

WEB_PORT = 8080

class RedirectedStreams():
  def __init__(self):
    self._stdout_grabber = OutputGrabber(sys.stdout, 'Welle.io', logging.Logger.error)
    self._stderr_grabber = OutputGrabber(sys.stderr, 'Welle.io', logging.Logger.warning)

  def redirect_out_streams(self):
    sys.stdout = self._stdout_grabber.redirect_stream()
    sys.stderr = self._stderr_grabber.redirect_stream()

  def restore_out_streams(self):
    self._stdout_grabber.cleanup()
    self._stderr_grabber.cleanup()

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
  site = web.TCPSite(runner, '0.0.0.0', port, shutdown_timeout=0.1)
  await site.start()


def update_logger_config(verbose):
  internal_log_level = logging.INFO    if verbose else logging.WARNING
  external_log_level = logging.WARNING if verbose else logging.ERROR
  logging.basicConfig(format='%(name)s - %(levelname)s: %(message)s',
                      encoding='utf-8', level=internal_log_level,
                      stream=sys.stdout, force=True)
  logging.getLogger("aiohttp").setLevel(external_log_level)
  logging.getLogger("pychromecast").setLevel(external_log_level)
  logging.getLogger("zeroconf").setLevel(external_log_level)
  logging.getLogger("Welle.io").setLevel(external_log_level)

def get_args():
  parser = argparse.ArgumentParser(description='MPD Cast Device Agent')
  parser.add_argument('--verbose', help = 'Enable verbose output', action = 'store_true')
  parser.add_argument('--conf', help = 'mpd config file to use. Default: /etc/mpd.conf', default = '/etc/mpd.conf')
  return vars(parser.parse_args())

def main():
  args = get_args()
  redirectors = RedirectedStreams()
  redirectors.redirect_out_streams()
  update_logger_config(args['verbose'])

  my_ip = get_first_ipv4_address()
  mpd_caster = MpdCaster(args['conf'], my_ip, WEB_PORT)

  if not my_ip:
    logger.warning('Could not retrieve local IP address')
    # Set up fallback that can be used for DAB playlist creation
    my_ip = '127.0.0.1'

  dab_server = DabServer(my_ip, WEB_PORT)

  if not mpd_caster.init_okay() and not dab_server.init_okay:
    logger.error('Fatal. Both MpdCast and DAB processing failed to initialize. Exiting.')
    redirectors.restore_out_streams()
    sys.exit(1)

  web_app = web.Application()

  if mpd_caster.init_okay():
    web_app.add_routes(mpd_caster.get_routes())

  if dab_server.init_okay:
    web_app.add_routes(dab_server.get_routes())

  runner = web.AppRunner(web_app)
  try:
    loop = asyncio.get_event_loop()
    loop.run_until_complete(setup_webserver(runner, WEB_PORT))
  except Exception as ex:
    logger.error('Fatal. Could not set up web server. Exiting')
    logger.error(str(ex))
    redirectors.restore_out_streams()
    sys.exit(1)

  try:
    # run the webserver in parallel to the cast task
    while True:
      if mpd_caster.init_okay():
        # wait until we find the cast device in the network
        mpd_caster.waitfor_and_register_castdevice()
        # run the cast (until chromecast or MPD disconnect)
        loop.run_until_complete(mpd_caster.cast_until_connection_lost())
      else:
        # DAB processing is fully built into the web server. no additional tasks required
        loop.run_until_complete(asyncio.sleep(3600))

  except KeyboardInterrupt:
    if mpd_caster.init_okay():
      loop.run_until_complete(mpd_caster.stop())
    if dab_server.init_okay:
      loop.run_until_complete(dab_server.stop())
    loop.run_until_complete(runner.cleanup())
    redirectors.restore_out_streams()

if __name__ == '__main__':
  main()
