import asyncio
import httpx
import os
import re
import asyncpg

from datetime import datetime
from datetime import timedelta
from functools import partial
from nio import RoomMessageText
from nio.responses import RoomResolveAliasError
from asyncpg.exceptions import UniqueViolationError

# https://dev.twitch.tv/docs/api/reference#get-streams
TWITCH_TV = 'https://twitch.tv'
TWITCH_STREAMS = 'https://api.twitch.tv/helix/streams'
TWITCH_USERS = 'https://api.twitch.tv/helix/users'
TWITCH_DATE_FMT = '%Y-%m-%dT%H:%M:%SZ'
twitch_add_re = re.compile(r'^!twitch (add|rm) (.+)$')
twitch_ls_re = re.compile(r'^!twitch ls(?: ([a-zA-Z0-9]+))?$')

async def monitor_streams(bot, room, twitch_client_id):
    conn = bot.pgc
    headers = {
        'Client-ID': twitch_client_id,
        'Cache-Control': 'no-cache, max-age= 0',
    }

    live = frozenset()
    timeout = 1
    while True:
        rows = await conn.fetch("select username from twitch")
        users = [ r['username'] for r in rows ]
        params = { 'user_login': users }
        resp = None
        async with httpx.AsyncClient(http2=True) as client:
            try:
                resp = await client.get(TWITCH_STREAMS, headers=headers,  params=params)
                timeout = 1
            except asyncio.exceptions.TimeoutError as e:
                print(f"Timeout when contacting {TWITCH_STREAMS}. Consecutive={timeout}")
                await asyncio.sleep(timeout * 100)
                timeout += timeout
                continue

        if resp.is_error:
            print(f'error: Could not GET {TWITCH_STREAMS}: {resp.reason}')
        else:
            stream_data = resp.json()['data']
            _live = frozenset(d['user_name'] for d in stream_data)
            streamers = { d['user_name'] : d for d in stream_data }
            now = datetime.utcnow()
            for streamer in (_live - live):
                stream_data = streamers[streamer]
                starttime = datetime.strptime(
                    stream_data['started_at'],
                    TWITCH_DATE_FMT
                )
                delta = now - starttime
                if timedelta(0) < delta <= timedelta(minutes=5):
                    title = stream_data['title']
                    msg = f'{streamer} is playing {title} at {TWITCH_TV}/{streamer}!'
                    await bot.send_room(room, msg)
            live = _live
        await asyncio.sleep(30)

async def twitch_db(bot, twitch_client_id, room, event):
    conn = bot.pgc

    async def twitch_add(users):
        params = { 'login': users }
        headers = {
            'Client-ID': twitch_client_id,
            'Cache-Control': 'no-cache, max-age= 0',
        }
        resp = None
        async with httpx.AsyncClient(http2=True) as client:
            try:
                resp = await client.get(TWITCH_USERS, headers=headers,
                        params=params)
            except asyncio.exceptions.TimeoutError as e:
                print(f"""Could not contact {TWITCH_USERS}. Cowardly refusing to
                        add users""")
                return
        if not resp or resp.is_error:
            print(f"""Could not contact {TWITCH_USERS}. Cowardly refusing to
                        add users""")
            return
        user_data = resp.json()['data']
        valid_users = { u['login'] for u in user_data }
        invalid_users = set(users) - valid_users
        invalid_userss = ", ".join(invalid_users)
        await bot.send_room(room, f"{invalid_userss} not known to Twitch API. Skipping!")

        if not valid_users:
            return

        userss = " ".join(valid_users)
        try:
            async with conn.transaction():
                for user in valid_users:
                    await conn.execute("""insert into twitch (username) values
                            ($1) on conflict do nothing""", user)
                await bot.send_room(room, f'Added users: {userss}')
        except Exception as e:
            await bot.send_room(room, 'error: Could not add users')
            print(e)

    async def twitch_rm(users):
        userss = " ".join(users)
        try:
            await conn.execute("delete from twitch where username = any($1)", users)
            await bot.send_room(room, f'Removed users: {userss}')
        except Exception as e:
            await bot.send_room(room, f'error: Could not remove {userss}')
            print(e)

    if (match := twitch_add_re.fullmatch(event.body)):
        action = match.group(1)
        users = match.group(2).split()
        if action == "add":
            await twitch_add(users)
        else:
            await twitch_rm(users)

    if (match := twitch_ls_re.fullmatch(event.body)):
        q = "%" if not match.group(1) else "%" + match.group(1) + "%"
        try:
            rows = await conn.fetch("""select * from twitch where
                username ilike $1""", q)
            user_list = "\n".join(r['username'] for r in rows)
            await bot.send_room(room, f"Monitoring streams:\n{user_list}")
        except Exception as e:
            await bot.send_room(room, f'error: could not fetch users')
            print(e)


async def register(bot):
    try:
        twitch_client_id = os.environ['TWITCH_CLIENT_ID']
        stream_room = os.environ['STREAM_ROOM']
        resolve = await bot.client.room_resolve_alias(stream_room)
        if not isinstance(resolve, RoomResolveAliasError):
            wrapped_room = bot.room_from_id(resolve.room_id)
            asyncio.create_task(monitor_streams(bot, wrapped_room,
                twitch_client_id))
        else:
            print('warn: Not monitoring streams. '
                  'Could not resolve room alias: ', stream_room)
        bot.client.add_event_callback(partial(twitch_db, bot, twitch_client_id),
                RoomMessageText)
    except KeyError:
        print(
            'warn: Not monitoring streams. '
             'TWITCH_CLIENT_ID and STREAM_ROOM required'
        )
