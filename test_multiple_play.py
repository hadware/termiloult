import wave
from asyncio import get_event_loop, ensure_future, sleep
from queue import Queue

from pyaudio import PyAudio, paContinue, paComplete


class AWavPlayer:
    """ Asynchronous wav player based on portaudio """

    wave = None # wave.Wave_read object
    player = None
    sample_width = 0
    _queue = None
    _stop_next = False
    _done = None # future signaling end of play

    def __init__(self, fd=None, loop=None):
        """ Init audio stream """
        self.player = PyAudio()
        self.loop = loop or get_event_loop()
        self._queue = Queue()

        if fd:
            self.play_file(fd)
            self.close()

    def _worker(self, in_data, frame_count, time_info, status):
        # Caution, this callback is running into a separate thread!
        if self._stop_next:
            self._stop_next = False
            self.loop.call_soon_threadsafe(self._done.set_result, None)
            return b'', paComplete

        expected_size = frame_count * self.sample_width

        frames = list()
        for _ in range(frame_count):
            frame = self._queue.get()
            frames.append(frame)
            self._queue.task_done()
            if not frame:
                self._stop_next = True
                break

        data = self._frame_pad(b''.join(frames), frame_count)
        return data, paContinue

    def _frame_pad(self, frame, frame_count=1):
        """ Pad a frame for PyAudio which else would stop """
        return frame.ljust(self.sample_width * frame_count, b'\x00')

    def enqueue(self, frame):
        """ Enqueue a frame to be played as soon as possible.

        If you pass an empty byte array the player will stop once
        it reaches it.
        """
        self._queue.put_nowait(frame)

    async def play(self, channels, rate, sample_width):
        self._done = self.loop.create_future()
        self.sample_width = sample_width

        wav_format = self.player.get_format_from_width(sample_width)
        self.player.open(
            format=wav_format,
            channels=channels,
            rate=rate,
            output=True,
            stream_callback=self._worker
        )

        return await self._done

    async def aplay_file(self, fd):
        """ Play a file or a file-like object asynchronously

        This will block while reading the file unless you pass a file-like
        object already in memory.
        """
        self._done = self.loop.create_future()
        wf = wave.open(fd, 'rb')

        play_coro = self.play(wf.getnchannels(), wf.getframerate(),
                              wf.getsampwidth())
        play_task = ensure_future(play_coro, loop=self.loop)

        for i in range(wf.getnframes()):
            self.enqueue(wf.readframes(1))
            await sleep(0)
        self.enqueue(b'')

        await play_task
        wf.close()

    def play_file(self, fd):
        """ Play a file or a file-like object synchronously """
        return self.loop.run_until_complete(self.aplay_file(fd))

    def close(self):
        """ Graceful shutdown """
        self.player.terminate()


if __name__ == '__main__':
    from sys import argv
    fname = argv[1] if len(argv) > 1 else "sample.wav"
    AWavPlayer(fname)
