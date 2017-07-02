import urwid
import random

def gen_text_flpe():
    return urwid.Text("Flpe " * random.randint(1,40))

def gen_text_user():
    return urwid.Text(random.choice(["Scorplane", 'Bulbizarre', 'Feurisson', "Marill"]))

def gen_row():
    return urwid.Columns([('fixed', 11, gen_text_user()), gen_text_flpe()])

class Prompt(urwid.Edit):

    def keypress(self, size, key):
        if key == "enter":
            history.widget_list.append(urwid.Columns([('fixed', 11, gen_text_user()),
                                                      urwid.Text(self.edit_text)]))
            prompt.set_edit_text("")
        else:
            super().keypress(size, key)
prompt = Prompt(">>> ")
history = urwid.Pile([gen_row() for i in range(10)])
loop = urwid.MainLoop(urwid.Filler(urwid.Pile([history, urwid.Divider("-"), prompt]), 'bottom'))
loop.run()