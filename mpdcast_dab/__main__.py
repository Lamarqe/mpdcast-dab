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
import signal
import asyncio
import argparse
import logging
import ifaddr
from aiohttp import web

from mpdcast_dab.dabserver.output_grabber import RedirectedStreams
from mpdcast_dab.mpdcast.mpd_caster import MpdCaster
try:
  from mpdcast_dab.dabserver.dab_server import DabServer
  WELLIO_IMPORT_ERROR = None
except (ModuleNotFoundError, ImportError, AttributeError) as error:
  WELLIO_IMPORT_ERROR = error

logger = logging.getLogger(__name__)

def get_first_ipv4_address():
  for iface in ifaddr.get_adapters():
    for addr in iface.ips:
      # Filter out link-local addresses.
      if addr.is_IPv4:
        if not (addr.ip.startswith('169.254.') or addr.ip == '127.0.0.1'):
          return addr.ip
  return None

def update_logger_config(verbose):
  internal_log_level = logging.INFO    if verbose else logging.WARNING
  external_log_level = logging.WARNING if verbose else logging.ERROR
  logging.basicConfig(format='%(name)s - %(levelname)s: %(message)s',
                      encoding='utf-8', level=internal_log_level,
                      stream=sys.stdout, force=True)
  logging.getLogger('aiohttp').setLevel(external_log_level)
  logging.getLogger('pychromecast').setLevel(external_log_level)
  logging.getLogger('zeroconf').setLevel(external_log_level)
  logging.getLogger('Welle.io').setLevel(external_log_level)
  logging.getLogger(__name__).setLevel(logging.INFO)

def get_args():
  parser = argparse.ArgumentParser(description='MPD Cast Device Agent',
                                   formatter_class=argparse.ArgumentDefaultsHelpFormatter)
  parser.add_argument('-p', '--port', help= 'Communication port to use.', type=int, default=8864)
  parser.add_argument('-c', '--conf', help= 'MPD config file to use.', default='/etc/mpd.conf')
  parser.add_argument('--disable-dabserver', help= 'Disable DAB server functionality', action='store_true')
  parser.add_argument('--disable-mpdcast', help= 'Disable MPD Cast functionality', action='store_true')
  parser.add_argument('-v', '--verbose', help= 'Enable verbose output', action='store_true')
  return vars(parser.parse_args())

def prepare_cast(options, web_app, prefix):
  if options['disable_mpdcast']:
    logger.warning('Disabling MPD cast functionality')
    return None

  my_ip = get_first_ipv4_address()
  if not my_ip:
    logger.error('Could not retrieve local IP address')
    return None

  mpd_caster = MpdCaster(options['conf'], my_ip, options['port'])
  if not mpd_caster.initialize():
    return None
  web_app.add_routes(mpd_caster.get_routes(prefix))
  return mpd_caster

def prepare_dab(options, web_app, prefix):
  if options['disable_dabserver']:
    logger.warning('Disabling DAB server functionality')
    return None
  if WELLIO_IMPORT_ERROR:
    logger.warning('Failed to load DAB+ library')
    logger.warning(str(WELLIO_IMPORT_ERROR))
    return None
  dab_server = DabServer(options['port'])
  if not dab_server.initialize():
    return None
  web_app.add_routes(dab_server.get_routes(prefix))
  return dab_server

async def setup_webserver(runner, port):
  try:
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port, shutdown_timeout=0.1)
    await site.start()
    return True
  except OSError as ex:
    logger.error(str(ex))
    return False

def main(run_from_local=False):
  options = get_args()

  redirectors = RedirectedStreams('Welle.io')
  if not options['disable_dabserver']:
    redirectors.redirect_out_streams()
  update_logger_config(options['verbose'])

  loop = asyncio.new_event_loop()
  asyncio.set_event_loop(loop)
  web_app = web.Application()
  prefix = 'src' if run_from_local else '/usr/share/mpdcast-dab'
  mpd_caster = prepare_cast(options, web_app, prefix)
  dab_server = prepare_dab (options, web_app, prefix)

  if not mpd_caster and not dab_server:
    logger.error('Fatal. Both MpdCast and DAB processing failed to initialize. Exiting.')
    redirectors.restore_out_streams()
    sys.exit(1)

  runner = web.AppRunner(web_app)
  if not loop.run_until_complete(setup_webserver(runner, options['port'])):
    logger.error('Fatal. Could not set up web server. Exiting')
    redirectors.restore_out_streams()
    sys.exit(1)

  if mpd_caster:
    loop.run_until_complete(mpd_caster.start())

  logger.info('Succesfully initialized MpdCast DAB')
  # prepare the main loop
  async def mainloop():
    while True:
      await asyncio.sleep(3600)
  mainloop_task = loop.create_task(mainloop())

  # set up cleanup handler...
  def sigterm_handler(signal_number, stack_frame):
    mainloop_task.cancel()
  # ... which handles SIGTERM
  signal.signal(signal.SIGTERM, sigterm_handler)

  try:
    loop.run_until_complete(mainloop_task)
  except (KeyboardInterrupt, asyncio.CancelledError):
    loop.run_until_complete(cleanup(mpd_caster, dab_server, runner))
    redirectors.restore_out_streams()

async def cleanup(mpd_caster, dab_server, runner):
  logger.info('Stopping MpdCast DAB as requested')
  if mpd_caster:
    await mpd_caster.stop()
  if dab_server:
    await dab_server.stop()
  await runner.cleanup()

if __name__ == '__main__':
  main(True)
