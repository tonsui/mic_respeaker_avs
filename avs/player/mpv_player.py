# -*- coding: utf-8 -*-

"""Player using MPV"""

import os
import subprocess
import threading

if os.system('which mpv >/dev/null') != 0:
    raise ImportError('mpv not found, install it first')


class Player(object):
    def __init__(self):
        self.callbacks = {}
        self.process = None
        self.state = 'NULL'
        self.audio = None
        self.tty = None

        self.event = threading.Event()
        t = threading.Thread(target=self._run)
        t.daemon = True
        t.start()

    def _run(self):
        while True:
            self.event.wait()
            self.event.clear()
            print('Playing {}'.format(self.audio))

            master, slave = os.openpty()
            self.process = subprocess.Popen(['mpv', '--no-video', self.audio], stdin=master)
            self.tty = slave

            self.process.wait()
            print('Finished {}'.format(self.audio))

            if not self.event.is_set():
                self.on_eos()

    def play(self, uri):
        self.audio = uri
        self.event.set()

        if self.process and self.process.poll() == None:
            os.write(self.tty, b'q')

        self.state = 'PLAYING'

    def stop(self):
        if self.process and self.process.poll() == None:
            os.write(self.tty, b'q')
        self.state = 'NULL'

    def pause(self):
        if self.state == 'PLAYING':
            self.state = 'PAUSED'
            os.write(self.tty, ' ')

        print('pause()')

    def resume(self):
        if self.state == 'PAUSED':
            self.state = 'PLAYING'
            os.write(self.tty, b' ')

    # name: {eos, ...}
    def add_callback(self, name, callback):
        if not callable(callback):
            return

        self.callbacks[name] = callback

    def on_eos(self):
        self.state = 'NULL'
        if 'eos' in self.callbacks:
            self.callbacks['eos']()

    @property
    def duration(self):
        return 0

    @property
    def position(self):
        return 0
