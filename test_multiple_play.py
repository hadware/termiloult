from asyncio import get_event_loop, ensure_future, sleep
from collections import deque
from threading import Event
import logging
import wave

from pyaudio import PyAudio, paContinue, paComplete


class AWavPlayer:
    """ Asynchronous wav player based on portaudio """

    player = None
    # needed by the worker to compute how long is the requested data
    sample_width = 0
    # a queue to communicate between the main thread and the worker's thread
    _queue = None
    # will next call the worker stop?
    _stop_next = False
    # will next call the worker wait for chunks?
    _block_next = False
    # future signaling end of play
    _done = None
    # is the worker waiting for chunks?
    _worker_blocked = False
    # duration of a chunk of sound in seconds
    chunk_duration = 0.2
    # synchronisation primitive to resume the worker's activity
    _worker_wakeup = None
    logger = logging.getLogger('AWavPlayer')

    def __init__(self, fd=None, loop=None):
        """ Init audio stream """
        self.player = PyAudio()
        self.loop = loop or get_event_loop()
        # deque's popleft, pop, append and appendleft are atomic operations
        self._queue = deque()
        self._worker_wakeup = Event()

        if fd:
            self.play_file(fd)
            self.close()

    def _worker(self, in_data, frame_count, time_info, status):
        """ Function called by PyAudio each time it can play more sound

        It stops once it reaches an empty array of bytes in its queue.
        If it doesn't, it blocks its thread until another one sets
        #_worker_wakeup.

        Caution, this callback is running into a separate thread!
        This is why, when the queue of chunks is empty we are using
        a synchronisation primitive to wake it up. It's *not* running
        in asyncio's event loop, and as such to interact with it it needs
        to use AbstractEventLoop.call_soon_threadsafe.

        Since it *has* to be fast else there will be small interuptions during
        playback, which is quite unpleasant and can go as far as making any
        sound impossible to identify. Therefore several tricks had to be used
        to make it fast enough:

            - use thread-related functions as scarcely as possible since they
              have a really high cpu-time cost
            - use a deque to communicate between threads, since its append/pop
              operations are atomic and thus don't need locking
            - make this worker able to cope with arbitrary-sized chunks sent
              into the deque so that the main thread's code can avoid sending
              many small chunks
            - don't use bytes concatenation as it's really slow; instead, put
              chunks into a list and join it once it's at least as long as
              requested by the `frame_count` parameter. Since deque is as
              performant for right append as for left appends, we can put
              again any leftover back into it.
            - use additions to keep track of the sum of the length
              of each chunk in the list of chuncks, which is really fast
        """

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

        chunks = list()
        while actual_size < expected_size:
            try:
                chunk = self._queue.popleft()
            except IndexError:
                self.logger.debug('Queue empty; worker will block next call')
                self._block_next = True
                break
            if not chunk:
                self._stop_next = True
                break
            chunks.append(chunk)
            actual_size += len(chunk)

        data = b''.join(chunks)
        if actual_size > expected_size:
            self._queue.appendleft(data[expected_size:])
            data = data[:expected_size]
        else:
            # portaudio will stop working if the data we send back is too short
            data = data.ljust(expected_size, b'\x00')

        return data, paContinue

    def _signal_worker_block(self):
        """ Helper for call_soon_threadsafe """
        self._worker_blocked = True

    def _check_worker_sleep(self):
        if self._worker_blocked:
            self._worker_wakeup.set()

    async def play(self, channels, rate, sample_width):
        """ Creates an asynchronous player and waits for it to complete """
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
        # TODO: there still are micro-interrupts on the first few seconds,
        # right when CPU usage is at its max. If you look at the logs,
        # you'll see that the worker's queue gets emptied a few times
        # before it stabilizes and CPU usage goes down. Maybe this could
        # be fixed by sending more chuncks on the first tens of milliseconds?
        # Or maybe we'll have to redesign the worker again.
        wf = wave.open(fd, 'rb')

        framerate = wf.getframerate()
        frames_per_chunk = framerate // int(1 / self.chunk_duration)

        play_coro = self.play(wf.getnchannels(), framerate,
                              wf.getsampwidth())
        play_task = ensure_future(play_coro, loop=self.loop)

        for i in range(wf.getnframes() // frames_per_chunk):
            self._queue.append(wf.readframes(frames_per_chunk))
            self._check_worker_sleep()
            # Instead of just waiting, mixing of incoming messages
            # could happend here. It is necessary to do the mixing
            # in the application else the OS's sound systemd will have
            # to take care of many short-lived audio sources, which
            # makes CPU usage go up, sometimes a lot. I guess numpy should
            # be performant enough to handle that?
            await sleep(self.chunk_duration - 0.02)
        self._queue.append(b'')

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
    logging.basicConfig(level=logging.DEBUG)
    fname = argv[1] if len(argv) > 1 else "sample.wav"
    AWavPlayer(fname)
