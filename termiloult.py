import argparse
from asyncio import get_event_loop, gather, CancelledError
from collections import deque
from curses import (
        wrapper, newwin, initscr, noecho, cbreak,
        start_color, nocbreak, endwin, echo
    )
from curses.textpad import Textbox, rectangle
from functools import wraps
import html
import json
import logging
from threading import Thread, Lock
from time import sleep
from typing import Tuple, List
from contextlib import closing

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


def daemon_thread(method):
    """ Make a method launch itself into a daemon tread on invocation

    If the object has a "threads" property which is a list, then every
    new thread will be appended to it.
    """
    @wraps(method)
    def wrapped(self, *args, **kwargs):

        thread = Thread(target=method, args=(self, *args), kwargs=kwargs)
        thread.daemon = True
        thread.start()

        if isinstance(self.threads, list):
            self.threads.append(thread)

    return wrapped


class Interface:
    """ View object which asynchronously prints and gets messages

        #input: an awaitable which returns what the user has entered.
        #output: a coroutine which sends data to be displayed.
    """

    def __init__(self):
        # Set up the terminal
        self.root_window = initscr()
        noecho()
        cbreak()
        self.root_window.keypad(1)
        try:
            start_color()
        except:
            pass

        # Curses' objects of course aren't thread-safe,
        # so we'll need a lock for every operation while
        # other threads are running.
        self.lock = Lock()
        # Those objects allow communication between threads
        # and coroutines, as well as between coroutines.
        self.input = Channel()
        self.output = Channel()

        self.threads = list()

        # This might cause the sound system to produce logs we
        # can't control; the solution is to let them be and then
        # draw on top of them later.
        self.sink = AudioSink()

        self.root_window.clear()
        # A box to input things.
        self.input_window = newwin(1, 110, 1, 1)
        rectangle(self.root_window, 0, 0, 2, 111)
        self.textbox = Textbox(self.input_window)

        # Draw what we just created.
        self.root_window.refresh()

        # Launch threads which update the interface and get the user's input
        self.get_input()
        self.add_messages()

    def close(self):
        """ Change the terminal back to normal """
        self.root_window.keypad(1)
        echo()
        nocbreak()
        endwin()

    @daemon_thread
    def get_input(self):
        while True:
            msg = self.textbox.edit()
            self.input.send(msg)

    @daemon_thread
    def add_messages(self):
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

    async def get_messages(self) :
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

    async def send_messages(self):
        async for msg in self.interface.input:
            data = {"lang": "fr", "msg": msg, "type": "msg"}
            await self.ws.send(json.dumps(data))

    @sync
    async def listen(self):
        url = 'wss://%s/socket/%s' % (self.server, self.channel)
        extra_headers = {"cookie": "id=%s" % self.cookie}
        async with websockets.connect(url, extra_headers=extra_headers) as ws:
            self.ws = ws
            tasks = gather(self.send_messages(), self.get_messages())
            try:
                await tasks
            except CancelledError:
                tasks.cancel()

if __name__ == "__main__":
    # parsing cmd line arguments
    args = argparser.parse_args()
    with closing(Interface()) as interface:
        ws_client = WebsocketClient(args.server, args.channel,
                                    args.cookie, interface)
        ws_client.listen()
