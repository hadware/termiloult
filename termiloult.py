import argparse
from asyncio import get_event_loop, gather, CancelledError
from collections import deque
from curses import wrapper, newwin
from curses.textpad import Textbox, rectangle
import html
import json
import logging
from threading import Thread, Lock
from time import sleep
from typing import Tuple, List

import websockets
from kawaiisync import sync, Channel

from tools.audiosink import AudioSink
from tools.interface import Interface
from tools.userlist import UserList

argparser = argparse.ArgumentParser()
argparser.add_argument("--channel", "-c",
                       help="Loult channel on which to connect. Defaults to main channel",
                       default="",
                       type=str)
argparser.add_argument("--server", "-s",
                       help="Server on which to connect. Defaults to the 'Official' channel, loult.family",
                       default="loult.family",
                       type=str)
argparser.add_argument("--cookie", "-ck",
                       help="Sets the user cookie",
                       default="flpe",
                       type=str)


#class MessageLog:
#    """Widget that handles the message list"""
#
#    def __init__(self, height, width, x_offset = 0, y_offset = 0):
#        self.root_window = newwin(height, width)
#        self.dimensions = (height, width)
#        self.offsets = (x_offset, y_offset)
#        self.message_log = []  # type: List[Tuple[str,str]]
#
#    def _refresh(self):
#        self.root_window.refresh()
#
#    def add_message(self, username, message):
#        """Adds a message to the log, redraws the full message list to add that message
#        at the bottom of it"""
#        pass

class Interface:
    """ View object which asynchronously prints and gets messages

        #input: an awaitable which returns what the user has entered.
        #add_message: a coroutine function which adds a message to be
                displayed.
    """

    def __init__(self):
        # Wrapper will set up everything and clean up after a crash.
        wrapper(self._actual_init)

    def _actual_init(self, root_window):
        # Curses' objects of course aren't thread-safe,
        # so we'll need a lock for every operation while
        # other threads are running.
        self.lock = Lock()
        # Those objects allow communication between threads
        # and coroutines, as well as between coroutines.
        self.input = Channel()
        self.output = Channel()

        # This might cause the sound system to produce logs we
        # can't control; the solution is to let them be and then
        # draw on top of them later.
        self.sink = AudioSink()

        self.root_window = root_window
        self.root_window.clear()

        # A box to input things.
        self.input_window = newwin(1, 110, 1, 1)
        rectangle(self.root_window, 0, 0, 2, 111)
        self.textbox = Textbox(self.input_window)

        # Draw what we just created.
        self.root_window.refresh()

        # Launch threads which update the interface and get the user's input
        self._daemonize(self._get_input)
        self._daemonize(self._add_messages)

    @staticmethod
    def _daemonize(func):
        thread = Thread(target=func)
        thread.daemon = True
        thread.start()

    def _get_input(self):
        while True:
            msg = self.textbox.edit()
            self.input.send(msg)

    def _add_messages(self):
        for nickname, message in self.output:
            with self.lock:
                self.root_window.addstr(10, 1, message)
                self.root_window.refresh()


class WebsocketClient:

    def __init__(self, server : str, channel : str, cookie : str, interface : Interface):
        self.server = server
        self.channel = channel
        self.cookie = cookie
        self.user_list = None
        self.interface = interface

    async def send_message(self, message):
        if message is not None:
            data = {"lang": "fr", "msg": message, "type": "msg"}
            await self.ws.send(json.dumps(data))

    async def _consumer(self) :
        while True:
            data = await self.ws.recv()
            if isinstance(data, bytes):
                self.interface.sink.add(data)
            else:
                msg_data = json.loads(data, encoding="utf-8")
                msg_type = msg_data["type"]
                if msg_type == "userlist":
                    self.user_list = UserList(msg_data["users"])
                    logging.info(str(self.user_list))

                elif msg_type == "msg":
                    msg = html.unescape(msg_data["msg"])  # removing HTML shitty encoding
                    nickname = self.user_list.name(msg_data["userid"])
                    await self.interface.output((nickname, msg))

                elif msg_type == "connect":
                    # registering the user to the user list
                    self.user_list.add_user(msg_data["userid"], msg_data["params"])

                elif msg_type == "disconnect":
                    # removing the user from the userlist
                    self.user_list.del_user(msg_data["userid"])

    async def _producer(self):
        while True:
            msg = await self.interface.input
            await self.send_message(msg)

    @sync
    async def listen(self):
        url = 'wss://%s/socket/%s' % (self.server, self.channel)
        extra_headers = {"cookie": "id=%s" % self.cookie}
        async with websockets.connect(url, extra_headers=extra_headers) as ws:
            self.ws = ws
            tasks = gather(self._consumer(), self._producer())
            try:
                await tasks
            except CancelledError:
                tasks.cancel()

if __name__ == "__main__":
    # parsing cmd line arguments
    args = argparser.parse_args()
    interface = Interface()
    ws_client = WebsocketClient(args.server, args.channel,
                                args.cookie, interface)
    ws_client.listen()
