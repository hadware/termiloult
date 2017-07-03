from curses import wrapper, newwin
from curses.textpad import Textbox, rectangle
from threading import Thread, Lock
from itertools import count
from time import sleep


class ConcurrentCursesExample:
    """ An example on how to use the standard curses concurrently

    When you run it, it'll display a counter and a textbox; just start
    typing, hit enter or ^G and your text will appear above the counter.

    Only thread-based concurrency is shown here, if you want to
    interface with asyncio use AbstractEventLoop.call_soon_threadsafe
    and run_in_exectuor with a function that'll acquire locks without
    blocking the event loop's thread.
    """

    def __init__(self, root_window):
        # Curses' objects of course aren't thread-safe,
        # so we'll need a lock for every operation while
        # other threads are running.
        self.lock = Lock()

        self.root_window = root_window
        self.root_window.clear()

        # A box to input things.
        self.input_window = newwin(1, 110, 1, 1)
        rectangle(self.root_window, 0, 0, 2, 111)
        self.textbox = Textbox(self.input_window)

        # Draw what we just created.
        self.root_window.refresh()

        # Launch the thread which will get the user's input.
        self.input_thread = Thread(target=self.get_input)
        self.input_thread.start()

        # This will run in the main thread.
        self.main()

    def main(self):
        # Update the interface every 500 ms forever.
        for i in count(0):
            with self.lock:
                self.root_window.addstr(20, 20, str(i))
                self.root_window.refresh()
            sleep(0.5)

    def get_input(self):
        while True:
            msg = self.textbox.edit()
            with self.lock:
                self.root_window.addstr(19, 20, msg)

# Wrapper will set up everything and clean up after a crash.
wrapper(ConcurrentCursesExample)
