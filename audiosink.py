from threading import Event, Lock
import logging
import io

import numpy as np
from scipy.io import wavfile
from pyaudio import PyAudio, paContinue, paComplete


class AudioSink:
    """ Asynchronous wav player based on portaudio
    
    Only works for 16 bits low-endian mono wav. The rate defaults to 16000.
    """

    player = None
    logger = logging.getLogger('AWavPlayer')

    # List of sound data to be mixed and played.
    _queue = None
    # The queue is used to communicate between two threads, so we need a lock.
    _queue_lock = None
    # Synchronisation primitive to resume the worker's activity
    _worker_wakeup = None

    def __init__(self, rate=16000):
        self.player = PyAudio()
        self._queue = list()
        self._queue_lock = Lock()
        self._worker_wakeup = Event()

        # This will patiently wait for sounds to be sent via #sink.
        self.player.open(
            format=8,
            channels=1,
            rate=rate,
            output=True,
            stream_callback=self._worker
        )

    def sink(self, sound):
        """ Send sound data to be mixed with currently playing sounds """
        _, data = wavfile.read(io.BytesIO(sound))
        with self._queue_lock:
            self._queue.append(data)
            # In case the worker was waiting for sounds.
            self._worker_wakeup.set()

    def _worker(self, in_data, frame_count, time_info, status):
        """ Function called by PyAudio each time it can play more sound """
        # The queue is also used by #sink, and since this callback runs into
        # a different thread, we need to lock it while we process it.
        self._queue_lock.acquire()

        if not self._queue:
            # Wait until #sink has put a sound into the queue.
            self.logger.debug('Worker\'s queue is empty')
            self._worker_wakeup.clear()
            # Release the lock so #sink can update it.
            self._queue_lock.release()
            self._worker_wakeup.wait()
            self._queue_lock.acquire()

        # Chunks of each sound of the size requested by portaudio
        # in frame_count. They'll be mixed together later.
        chunks = list()
        # Since we'll iterate on it, we'll avoid mutating the queue
        # and instead create a new one which will become the new queue
        # once the iteration has finished.
        new_queue = list()
        for sound in self._queue:
            length = len(sound)
            if length <= frame_count:
                # We reached the end of a sound, so pad it if needed
                # (as portaudio would otherwise stop working if it isn't the
                # right size) and don't put an empty array into the new queue
                sound = np.pad(sound, (0, frame_count - length), 'constant')
            else:
                # We didn't reach the end of that sound, so put what's left
                # into the new queue.
                new_queue.append(sound[frame_count:])

            chunks.append(sound[:frame_count])

        self._queue = new_queue

        self._queue_lock.release()

        # Put all chunks into a single array and lower their volume so their 
        # sum doesn't saturate the output.
        stack = np.stack(chunks, axis=0) // len(chunks)
        # Don't forget to force the int16 type else #tobytes() won't output
        # bytes with the correct format and the audio output will be garbled.
        data = np.sum(stack, axis=0, dtype=np.int16)

        return data.tobytes(), paContinue

    def close(self):
        """ Graceful shutdown """
        self.player.terminate()
