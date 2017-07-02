from asyncio import ensure_future
from functools import wraps

import urwid

# for all pokemon names in french, the max character length is 10
POKENAME_COLUMN_LENGTH = 11

def async_callback(corofunc):
    @wraps(corofunc)
    def callback(*args, **kwargs):
        # we lose the task this way, it could be useful
        # to queue it somewhere.
        ensure_future(corofunc(*args, **kwargs))
    return callback


class Prompt(urwid.Edit):

    @async_callback
    async def keypress(self, size, key):
        if key == "enter":
            # TODO : return the message to be sent
            self.set_edit_text("")
        else:
            super().keypress(size, key)


class Interface:

    def __init__(self):
        self.prompt = Prompt(">>>")
        self.history = urwid.Pile([])
        self.root_widget = urwid.Filler(urwid.Pile([self.history, urwid.Divider("-"), self.prompt]), 'bottom')

    def unhandled(self, key):
        if key == 'ctrl c':
            raise urwid.ExitMainLoop

    def run(self, loop):
        urwid_loop = urwid.MainLoop(
            self.root_widget,
            event_loop=urwid.AsyncioEventLoop(loop=loop),
            unhandled_input=self.unhandled,
        )

        return urwid_loop

    def add_msg(self, user_name, message):
        self.history.widget_list.append(urwid.Columns([('fixed', POKENAME_COLUMN_LENGTH, urwid.Text(user_name)),
                                                      urwid.Text(message)]))