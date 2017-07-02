import logging
from time import sleep

from audiosink import AudioSink

logging.basicConfig(level=logging.DEBUG)

p = AudioSink()

with open("sample.wav", 'rb') as f:
    a = f.read()
p.sink(a)

sleep(2)

with open("sample.wav", 'rb') as f:
    b = f.read()
p.sink(b)

sleep(25)

p.close()
