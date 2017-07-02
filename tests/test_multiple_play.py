import logging
from time import sleep

from tools.audiosink import AudioSink

demo = logging.getLogger('Demo')

logging.basicConfig(level=logging.DEBUG)


p = AudioSink()

with open("sample.wav", 'rb') as f:
    a = f.read()
demo.info("add the first track")
p.add(a, "a")

sleep(2)

with open("sample.wav", 'rb') as f:
    b = f.read()
demo.info("add a second track")
p.add(b,"b")

sleep(5)

demo.info("remove the first track")
p.remove("a")

sleep(5)

demo.info("lower the volume to 40%")
p.volume = 40

sleep(15)

demo.info("close the AudioSink")
p.close()
