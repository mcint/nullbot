import asyncio
from dataclasses import dataclass
from nio import AsyncClient
import os
import psycopg2
import pkgutil
from typing import Any

@dataclass
class NullBot:
    homeserver: str
    username: str
    password: str
    pgc: Any

    async def bot_main(self):
        self.client = AsyncClient(self.homeserver, self.username)
        await self.client.login(self.password)

        # Do an initial sync and ignore it, to throw out old messages
        await self.client.sync()

        for importer, mod_name, _ in pkgutil.iter_modules(['plugin']):
            mod = importer.find_module(mod_name).load_module(mod_name)
            register = getattr(mod, 'register', None)
            if register is not None:
                asyncio.create_task(register(self))

        await self.client.sync_forever(timeout=3000, full_state=True)

    async def send_room(self, room, message):
        await self.client.room_send(
            room_id=room.room_id,
            message_type='m.room.message',
            content={
                'msgtype': 'm.text',
                'body': message,
            }
        )

def main():
    try:
        homeserver = os.environ['MATRIX_HOMESERVER']
        username = os.environ['MATRIX_USERNAME']
        password = os.environ['MATRIX_PASSWORD']
    except KeyError:
        print(
            'You must provide environment variables '
            'MATRIX_HOMESERVER, MATRIX_USERNAME, MATRIX_PASSWORD'
        )

    try:
        conn = psycopg2.connect('')
    except:
        print("Cannot connect to database!")
        exit(1)


    # Start the bot
    bot = NullBot(homeserver, username, password, conn)
    asyncio.run(bot.bot_main())

if __name__ == '__main__':
    main()
