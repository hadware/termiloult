import wave
from threading import Event
from collections import deque
from asyncio import get_event_loop, ensure_future, sleep, gather
from kawaiisync import aiocontext

from pyaudio import PyAudio, paContinue, paComplete


class AWavPlayer:
    """ Asynchronous wav player based on portaudio """

    wave = None # wave.Wave_read object
    player = None
    sample_width = 0
    _queue = None
    _stop_next = False
    _block_next = False
    _done = None # future signaling end of play
    _worker_blocked = False
    buffer_size = 0

    def __init__(self, fd=None, *, buffer_size=2**16, loop=None):
        """ Init audio stream """
        self.player = PyAudio()
        self.loop = loop or get_event_loop()
        self.buffer_size = buffer_size
        self._queue = deque()
        self._worker_wakeup = Event()

        if fd:
            self.play_file(fd)
            self.close()

    def _worker(self, in_data, frame_count, time_info, status):
        # Caution, this callback is running into a separate thread!

        if self._stop_next:
            self._stop_next = False
            self.loop.call_soon_threadsafe(self._done.set_result, None)
            return b'', paComplete

        if self._block_next:
            self._block_next = False
            self.loop.call_soon_threadsafe(self._signal_worker_block)
            self._worker_wakeup.wait()
            self._worker_wakeup.clear()

        expected_size = frame_count * self.sample_width
        actual_size = 0

        frames = list()
        while actual_size < expected_size:
            try:
                frame = self._queue.popleft()
            except IndexError:
                self._block_next = True
                break
            if not frame:
                self._stop_next = True
                break
            frames.append(frame)
            actual_size += len(frame)

        data = b''.join(frames)
        if actual_size > expected_size:
            self._queue.appendleft(data[expected_size:])
            data = data[:expected_size]
        else:
            data = self._frame_pad(data, frame_count)

        return data, paContinue

    def _frame_pad(self, frame, frame_count=1):
        """ Pad a frame for PyAudio which else would stop """
        return frame.ljust(self.sample_width * frame_count, b'\x00')

    def _signal_worker_block(self):
        self._worker_blocked = True

    def enqueue(self, frame):
        """ Enqueue a frame to be played as soon as possible.

        If you pass an empty byte array the player will stop once
        it reaches it.
        """
        self._queue.append(frame)

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
            self.enqueue(wf.readframes(self.buffer_size))
            await sleep(0)
            if self._worker_blocked:
                self._worker_wakeup.set()
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
