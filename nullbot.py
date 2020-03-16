import asyncio
from dataclasses import dataclass
from nio import AsyncClient
import os
import pkgutil

@dataclass
class NullBot:
    homeserver: str
    username: str
    password: str

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

def main():
    try:
        homeserver = os.environ['MATRIX_HOMESERVER']
        username = os.environ['MATRIX_USERNAME']
        password = os.environ['MATRIX_PASSWORD']

        bot = NullBot(homeserver, username, password)
        asyncio.run(bot.bot_main())
    except KeyError:
        print(
            'You must provide environment variables '
            'MATRIX_HOMESERVER, MATRIX_USERNAME, MATRIX_PASSWORD'
        )

if __name__ == '__main__':
    main()
