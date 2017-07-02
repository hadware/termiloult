import argparse
import json
import logging
from asyncio import get_event_loop

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

# for all pokemon names in french, the max character length is 10
POKENAME_COLUMN_LENGTH = 11


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

    async def listen(self):
        async with websockets.connect('wss://%s/socket/%s' % (self.server, self.channel),
                                      extra_headers={"cookie": "id=%s" % self.cookie}) as ws:
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


if __name__ == "__main__":
    # parsing cmd line arguments
    args = argparser.parse_args()

    # setting up the pseudo-graphical urwid interface, and the websocket client object
    interface = Interface()
    ws_client = WebsocketClient(args.server, args.channel, args.cookie, interface)

    # firing up the event loop and scheduling the listening task
    loop = get_event_loop()
    urwid_loop = interface.run(loop)
    ensure_future(ws_client.listen(), loop=loop)
    urwid_loop.run()
