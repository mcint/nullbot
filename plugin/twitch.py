import asyncio
import os
import re
import requests
import psycopg2

from datetime import datetime
from functools import partial
from nio import RoomMessageText
from psycopg2.errors import UniqueViolation

# https://dev.twitch.tv/docs/api/reference#get-streams
TWITCH_STREAMS = 'https://api.twitch.tv/helix/streams'
TWITCH_TV = 'https://twitch.tv'
TWITCH_DATE_FMT = '%Y-%m-%dT%H:%M:%SZ'

twitch_re = re.compile(r'^!twitch (add|rm) (.+)$')

async def monitor_streams(bot, room_id, twitch_client_id):
    conn = bot.pgc
    headers = { 'Client-ID': twitch_client_id }

    live = set()
    with conn.cursor() as cur:
        while True:
            cur.execute("select username from twitch")
            users = [ r[0] for r in cur.fetchall() ]
            params = { 'user_login': users }
            resp = requests.get(TWITCH_STREAMS, headers=headers, params=params)
            if resp.status_code != 200:
                print(f'error: Could not GET {TWITCH_STREAMS}: {resp.reason}')
            else:
                stream_data = resp.json()['data']
                _live = set([ d['user_name'] for d in stream_data ])
                smap = { d['user_name'] : d for d in stream_data }
                new = _live - live
                now = datetime.utcnow()
                for streamer in (_live - live):
                    starttime = datetime.strptime(
                        smap[streamer]['started_at'],
                        TWITCH_DATE_FMT
                    )
                    delta = now - starttime
                    if delta.seconds <= 60:
                        msg = f'{streamer} is live at {TWITCH_TV}/{streamer}!'
                        await bot.client.room_send(
                            room_id=room_id,
                            message_type='m.room.message',
                            content={
                                'msgtype': 'm.text',
                                'body': msg,
                            }
                        )
                live = _live
            await asyncio.sleep(20)

async def twitch_db(bot, room, event):
    conn = bot.pgc

    async def twitch_add(users):
        with conn.cursor() as cur:
            try:
                for user in users:
                    cur.execute("insert into twitch (username) values (%s)", (user,))
                conn.commit()
                added = " ".join(users)
                await bot.send_room(room, f'Added users: {added}')
            except UniqueViolation as e:
                await bot.send_room(room, 'error: Cannot add duplicate user')
                conn.rollback()

    async def twitch_rm(users):
        with conn.cursor() as cur:
            try:
                cur.execute("delete from twitch where username in %s",
                        (tuple(users),))
                conn.commit()
                rmed = " ".join(users)
                await bot.send_room(room, f'Removed users: {rmed}')
            except psycopg2.DatabaseError as e:
                print(e)
                conn.rollback()

    if (match := twitch_re.fullmatch(event.body)):
        action = match.group(1)
        users = match.group(2).split()
        if action == "add":
            await twitch_add(users)
        else:
            await twitch_rm(users)

async def register(bot):
    try:
        twitch_client_id = os.environ['TWITCH_CLIENT_ID']
        stream_room_id = os.environ['STREAM_ROOM_ID']
        asyncio.create_task(monitor_streams(bot, stream_room_id, twitch_client_id))
    except KeyError:
        print(
            'warn: Not monitoring streams. '
             'TWITCH_CLIENT_ID and STREAM_ROOM_ID required'
        )
    bot.client.add_event_callback(partial(twitch_db, bot), RoomMessageText)
