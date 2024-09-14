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

"""This module is used to redirect stdout/stderr streams to a python logger."""

import io
import os
import sys
import threading
import logging
import typing

class OutputGrabber:
  _ESC_CHAR = b'\b'

  def __init__(self, stream: typing.TextIO, log_name: str, log_method: typing.Callable) -> None:
    self._logger = logging.getLogger(log_name)
    self._pipe_out, self._pipe_in = os.pipe()
    self._logger_thread: threading.Thread | None = None
    self._log_method = log_method

    # store the original stream
    self._orig_stream = stream
    # replicate the original stream using a new FD
    self._replica_stream = os.fdopen(os.dup(self._orig_stream.fileno()), 'w')

  def _log_pipe(self) -> None:
    captured_stream = ''
    while True:
      char = os.read(self._pipe_out, 1)
      if char == self._ESC_CHAR:
        break
      data = char.decode()
      if data == '\n':
        self._log_method(self._logger, captured_stream)
        captured_stream = ''
      else:
        captured_stream += data

  def redirect_stream(self) -> io.TextIOWrapper:
    if self._logger_thread:
      raise ValueError('stream is already redirected')

    self._logger_thread = threading.Thread(target=self._log_pipe)
    self._logger_thread.start()
    # make the pipe input available under the original FD, for C code
    os.dup2(self._pipe_in, self._orig_stream.fileno())
    # return the replicated stream for use in python code
    return self._replica_stream

  def restore_stream(self) -> typing.TextIO:
    if not self._logger_thread:
      raise ValueError('stream not redirected')

    # Print the escape character to make the readOutput method stop:
    self._orig_stream.buffer.write(self._ESC_CHAR)
    self._orig_stream.flush()
    self._logger_thread.join()
    self._logger_thread = None
    # make the replicated stream available again under the original FD, for C code
    os.dup2(self._replica_stream.fileno(), self._orig_stream.fileno())
    # return the original stream for use in python code
    return self._orig_stream

  def cleanup(self) -> None:
    if self._logger_thread:
      self.restore_stream()

class RedirectedStreams():
  def __init__(self, log_name: str) -> None:
    self._stdout_grabber = OutputGrabber(sys.stdout, log_name, logging.Logger.error)
    self._stderr_grabber = OutputGrabber(sys.stderr, log_name, logging.Logger.warning)

  def redirect_out_streams(self) -> None:
    sys.stdout = self._stdout_grabber.redirect_stream()
    sys.stderr = self._stderr_grabber.redirect_stream()

  def restore_out_streams(self) -> None:
    self._stdout_grabber.cleanup()
    self._stderr_grabber.cleanup()
