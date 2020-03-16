from functools import partial
from nio import RoomMessageText
import random
import re

choose_re = re.compile(r'!choose (.+)')

async def message_cb(client, room, event):
    if (match := choose_re.fullmatch(event.body)) is not None:
        choice = random.choice(match.group(1).split(','))

        await client.room_send(
            room_id=room.room_id,
            message_type='m.room.message',
            content={
                'msgtype': 'm.text',
                'body': f'{choice}',
            }
        )

async def register(bot):
    bot.client.add_event_callback(partial(message_cb, bot.client), RoomMessageText)
