import base64
import logging
import os
import tempfile
import threading
import uuid

# prefer mpg123 player as it is more responsive than mpv and gstreamer
if os.system('which mpg123 >/dev/null') == 0:
    from avs.player.mpg123_player import Player
else:
    from avs.player import Player

logger = logging.getLogger('SpeechSynthesizer')


class SpeechSynthesizer(object):
    STATES = {'PLAYING', 'FINISHED'}

    def __init__(self, alexa):
        self.alexa = alexa
        self.token = ''
        self._state = 'FINISHED'
        self.finished = threading.Event()

        self.player = Player()
        self.player.add_callback('eos', self.SpeechFinished)
        self.player.add_callback('error', self.SpeechFinished)
        self.mp3_file = None

    def stop(self):
        self.finished.set()
        self.player.stop()
        self._state = 'FINISHED'

    def wait(self):
        self.finished.wait()

    # {
    #     "directive": {
    #         "header": {
    #             "namespace": "SpeechSynthesizer",
    #             "name": "Speak",
    #             "messageId": "{{STRING}}",
    #             "dialogRequestId": "{{STRING}}"
    #         },
    #         "payload": {
    #             "url": "{{STRING}}",
    #             "format": "AUDIO_MPEG",
    #             "token": "{{STRING}}"
    #         }
    #     }
    # }
    # Content-Type: application/octet-stream
    # Content-ID: {{Audio Item CID}}
    # {{BINARY AUDIO ATTACHMENT}}
    def Speak(self, directive):
        # directive from dueros may not have the dialogRequestId
        if 'dialogRequestId' in directive['header']:
            dialog_request_id = directive['header']['dialogRequestId']
            if self.alexa.SpeechRecognizer.dialog_request_id != dialog_request_id:
                return

        if self.alexa.Alerts.state == 'FOREGROUND':
            logger.info('stop alert(s)')
            self.alexa.Alerts.stop()
        elif self.alexa.AudioPlayer.state == 'PLAYING':
            logger.info('pause audio player')
            self.alexa.AudioPlayer.pause()

        self.token = directive['payload']['token']
        url = directive['payload']['url']
        if url.startswith('cid:'):
            filename = base64.urlsafe_b64encode(url[4:].encode('utf-8'))[:8].decode('utf-8')
            mp3_file = os.path.join(tempfile.gettempdir(), filename + '.mp3')
            if os.path.isfile(mp3_file):
                self.mp3_file = mp3_file

                self.finished.clear()
                self.SpeechStarted()
                # os.system('mpv "{}"'.format(mp3_file))
                self.player.play('file://{}'.format(mp3_file))

                logger.info('playing {}'.format(filename))

                self.alexa.state_listener.on_speaking()

                # will be set at SpeechFinished() if the player reaches the End Of Stream or gets a error
                # self.finished.wait()
            else:
                logger.warning('not find {}'.format(mp3_file))

    def SpeechStarted(self):
        self._state = 'PLAYING'
        event = {
            "header": {
                "namespace": "SpeechSynthesizer",
                "name": "SpeechStarted",
                "messageId": uuid.uuid4().hex
            },
            "payload": {
                "token": self.token
            }
        }
        self.alexa.send_event(event)

    def SpeechFinished(self):
        if os.path.isfile(self.mp3_file):
            os.system('rm -rf "{}"'.format(self.mp3_file))

        self.finished.set()
        self._state = 'FINISHED'

        # repeated operation, will cause bug when we try to listen() at 'on_speaking' state
        # self.alexa.state_listener.on_finished()

        if self.alexa.AudioPlayer.state == 'PAUSED':
            self.alexa.AudioPlayer.resume()

        event = {
            "header": {
                "namespace": "SpeechSynthesizer",
                "name": "SpeechFinished",
                "messageId": uuid.uuid4().hex
            },
            "payload": {
                "token": self.token
            }
        }
        self.alexa.send_event(event)

    @property
    def state(self):
        if self._state == 'PLAYING' and self.player.state == 'PLAYING':
            s = 'PLAYING'
        else:
            s = 'FINISHED'

        # logger.debug('speech synthesizer is {}'.format(s))
        return s

    @property
    def context(self):
        state = self.state
        offset = self.player.position if state == 'PLAYING' else 0

        return {
            "header": {
                "namespace": "SpeechSynthesizer",
                "name": "SpeechState"
            },
            "payload": {
                "token": self.token,
                "offsetInMilliseconds": offset,
                "playerActivity": state
            }
        }
