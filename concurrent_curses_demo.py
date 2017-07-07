from curses import wrapper, newwin
from curses.textpad import Textbox, rectangle
from threading import Thread, Lock
from itertools import count
from time import sleep
from typing import Tuple, List
import argparse
import json
import logging
from asyncio import get_event_loop
import asyncio

import html
from asyncio.tasks import ensure_future

import websockets

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


class MessageLog:
    """Widget that handles the message list"""

    def __init__(self, height, width, x_offset = 0, y_offset = 0):
        self.root_window = newwin(height, width)
        self.dimensions = (height, width)
        self.offsets = (x_offset, y_offset)
        self.message_log = []  # type: List[Tuple[str,str]]

    def _refresh(self):
        self.root_window.refresh()

    def add_message(self, username, message):
        """Adds a message to the log, redraws the full message list to add that message
        at the bottom of it"""
        pass

class Interface:
    """ An example on how to use the standard curses concurrently

    When you run it, it'll display a counter and a textbox; just start
    typing, hit enter or ^G and your text will appear above the counter.

    Only thread-based concurrency is shown here, if you want to
    interface with asyncio use AbstractEventLoop.call_soon_threadsafe
    and run_in_executor with a function that'll acquire locks without
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
        height, width = self.root_window.getmaxyx()

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
                loop.call_soon_threadsafe(input_future, msg)
                self.root_window.addstr(19, 20, msg)

    def add_message(self, nickname, message):
        pass


class WebsocketClient:

    def __init__(self, server : str, channel : str, cookie : str, interface : Interface):
        self.server = server
        self.channel = channel
        self.cookie = cookie
        self.sink = AudioSink()
        self.user_list = None
        self.interface = interface

    async def _send_message(self, websocket, message):
        if message is not None:
            data = {"lang": "fr", "msg": message, "type": "msg"}
            await websocket.send(json.dumps(data))

    async def _consumer(self, websocket):
        while True:
            data = await ws.recv()
            if isinstance(data, bytes):
                self.sink.add(data)
            else:
                msg_data = json.loads(data, encoding="utf-8")
                msg_type = msg_data["type"]
                if msg_type == "userlist":
                    self.user_list = UserList(msg_data["users"])
                    logging.info(str(self.user_list))

                elif msg_type == "msg":
                    msg_data["msg"] = html.unescape(msg_data["msg"])  # removing HTML shitty encoding
                    self.interface.add_msg(self.user_list.name(msg_data["userid"]), msg_data["msg"])

                elif msg_type == "connect":
                    # registering the user to the user list
                    self.user_list.add_user(msg_data["userid"], msg_data["params"])

                elif msg_type == "disconnect":
                    # removing the user from the userlist
                    self.user_list.del_user(msg_data["userid"])

    async def _producer(self, websocket):
        while True:
            message = await loop.run_in_executor()
            await websocket.send(message)

    async def _handler(self, websocket):
        consumer_task = asyncio.ensure_future(self._consumer(websocket))
        producer_task = asyncio.ensure_future(self._producer(websocket))
        done, pending = await asyncio.wait(
            [consumer_task, producer_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()

    async def listen(self):
        async with websockets.connect('wss://%s/socket/%s' % (self.server, self.channel),
                                      extra_headers={"cookie": "id=%s" % self.cookie}) as ws:
            await self._handler(ws)

loop = get_event_loop()

if __name__ == "__main__":
    # parsing cmd line arguments
    args = argparser.parse_args()

    # Wrapper will set up everything and clean up after a crash.
    wrapper(Interface)
    ws_client = WebsocketClient(args.server, args.channel, args.cookie, interface)

    # future for the input function
    input_future = loop.create_future()

    # firing up the event loop
    loop.run_until_complete(ws_client.listen())
