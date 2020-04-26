from functools import partial
from nio import RoomMessageText
import random
import re

choose_re = re.compile(r'!choose([^ ]?) (.+)')

async def message_cb(bot, room, event):
    if (match := choose_re.fullmatch(event.body)) is not None:
        char = match.group(1) if match.group(1) else ','
        choice = random.choice(match.group(2).split(char))
        await bot.send_room(room, choice)

async def register(bot):
    bot.client.add_event_callback(partial(message_cb, bot), RoomMessageText)
