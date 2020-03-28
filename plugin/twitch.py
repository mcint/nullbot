import asyncio
import httpx
import os
import re
import asyncpg

from datetime import datetime
from functools import partial
from nio import RoomMessageText
from nio.responses import RoomResolveAliasError
from asyncpg.exceptions import UniqueViolationError

# https://dev.twitch.tv/docs/api/reference#get-streams
TWITCH_STREAMS = 'https://api.twitch.tv/helix/streams'
TWITCH_TV = 'https://twitch.tv'
TWITCH_DATE_FMT = '%Y-%m-%dT%H:%M:%SZ'

twitch_re = re.compile(r'^!twitch (add|rm) (.+)$')

async def monitor_streams(bot, room, twitch_client_id):
    conn = bot.pgc
    headers = { 'Client-ID': twitch_client_id }

    live = frozenset()
    while True:
        rows = await conn.fetch("select username from twitch")
        users = [ r['username'] for r in rows ]
        params = { 'user_login': users }
        async with httpx.AsyncClient() as client:
            resp = await client.get(TWITCH_STREAMS, headers=headers,  params=params)
        if resp.is_error:
            print(f'error: Could not GET {TWITCH_STREAMS}: {resp.reason}')
        else:
            stream_data = resp.json()['data']
            _live = frozenset(d['user_name'] for d in stream_data)
            smap = { d['user_name'] : d for d in stream_data }
            now = datetime.utcnow()
            for streamer in (_live - live):
                starttime = datetime.strptime(
                    smap[streamer]['started_at'],
                    TWITCH_DATE_FMT
                )
                delta = now - starttime
                if delta.seconds <= 60:
                    msg = f'{streamer} is live at {TWITCH_TV}/{streamer}!'
                    await bot.send_room(room, msg)
            live = _live
        await asyncio.sleep(20)

async def twitch_db(bot, room, event):
    conn = bot.pgc

    async def twitch_add(users):
        users_s = " ".join(users)
        try:
            async with conn.transaction():
                for user in users:
                    await conn.execute("insert into twitch (username) values ($1)", user)
                await bot.send_room(room, f'Added users: {users_s}')
        except UniqueViolationError as e:
            await bot.send_room(room, 'error: Cannot add duplicate user')

    async def twitch_rm(users):
        users_s = " ".join(users)
        try:
            await conn.execute("delete from twitch where username = any($1)", users)
            await bot.send_room(room, f'Removed users: {users_s}')
        except Exception as e:
            await bot.send_room(room, f'error: Could not remove {users_s}')
            print(e)

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
        stream_room = os.environ['STREAM_ROOM']
        resolve = await bot.client.room_resolve_alias(stream_room)
        if not isinstance(resolve, RoomResolveAliasError):
            wrapped_room = bot.room_from_id(resolve.room_id)
            asyncio.create_task(monitor_streams(bot, wrapped_room, twitch_client_id))
        else:
            print('warn: Not monitoring streams. '
                  'Could not resolve room alias: ', stream_room)
    except KeyError:
        print(
            'warn: Not monitoring streams. '
             'TWITCH_CLIENT_ID and STREAM_ROOM required'
        )
    bot.client.add_event_callback(partial(twitch_db, bot), RoomMessageText)
