import ctypes
import os
import sys
import threading
import time
import logging

class OutputGrabber:
  escape_char = b'\b'

  def __init__(self, name, target):
    self.c_logger = logging.getLogger(name)
    self.pipe_out, self.pipe_in = os.pipe()
    self.logger_thread = None

    # store the original stream
    self.orig_stream    = target
    # replicate the original stream using a new FD
    self.replica_stream = os.fdopen(os.dup(self.orig_stream.fileno()), 'w')

  def log_pipe(self):
    captured_stream = ''
    while True:
      char = os.read(self.pipe_out, 1)
      if char == self.escape_char:
        break
      data = char.decode()
      if data == '\n':
        self.c_logger.info(captured_stream)
        captured_stream = ''
      else:
        captured_stream += data

  def redirect_stream(self):
    if self.logger_thread:
      raise ValueError('stream is already redirected')

    self.logger_thread = threading.Thread(target=self.log_pipe)
    self.logger_thread.start()
    # make the pipe input available under the original FD, for C code
    os.dup2(self.pipe_in, self.orig_stream.fileno())
    # return the replicated stream for use in python code
    return self.replica_stream

  def restore_stream(self):
    if not self.logger_thread:
      raise ValueError('stream not redirected')

    # Print the escape character to make the readOutput method stop:
    self.orig_stream.buffer.write(self.escape_char)
    self.orig_stream.flush()
    self.logger_thread.join()
    self.logger_thread = None
    # make the replicated stream available again under the original FD, for C code
    os.dup2(self.replica_stream.fileno(), self.orig_stream.fileno())
    # return the original stream for use in python code
    return self.orig_stream

  def cleanup(self):
    if self.logger_thread:
      return self.restore_stream()

def updateLoggerConfig():
  logging.basicConfig(encoding='utf-8', level=logging.INFO, stream=sys.stdout, force=True)

def main():
  stdoutGrabber = OutputGrabber('c_stdout', sys.stdout)
  stderrGrabber = OutputGrabber('c_stderr', sys.stderr)

  liba = ctypes.cdll.LoadLibrary('./libtest.dylib')

  ##############################################################################
  #why is the following call necessary?
  liba.init()  # Will print at least one char via C to stdout
  ##############################################################################


  try:
    while True:
      sys.stdout = stdoutGrabber.redirect_stream()
      sys.stderr = stderrGrabber.redirect_stream()
      updateLoggerConfig()

      liba.hello_stdout()
      time.sleep(1)
      liba.hello_stderr()
      time.sleep(1)

      sys.stdout = stdoutGrabber.restore_stream()
      sys.stderr = stderrGrabber.restore_stream()
      updateLoggerConfig()
    
      liba.hello_stdout()
      time.sleep(1)
      liba.hello_stderr()
      time.sleep(1)

  except KeyboardInterrupt:
    stderrGrabber.cleanup()
    stdoutGrabber.cleanup()
  print('exiting...')

if __name__ == '__main__':
  main()
