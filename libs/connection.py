import asyncio
from aiohttp import ClientSession, ClientTimeout, ClientConnectionError, ClientResponse
from yarl import URL
from typing import Any
from http.cookies import SimpleCookie
from urllib.parse import unquote
from os.path import isfile
from .encryption import system_encrypt, system_decrypt



class Connection:
    def __init__(self):
        self.logged_in = False
        self.sess = ClientSession(
            timeout=ClientTimeout(total=5),
            headers={
                "Accept": "*/*",
                "Sec-Ch-Ua": '"Not.A/Brand";v="8", "Chromium";v="115"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Windows"',
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
            },
        )

    def save_steam_cookie(self):
        if not self.logged_in:
            return False

        try:
            with open("cookie", "wb") as f:
                cookie_string = self.sess.cookie_jar.filter_cookies("https://steamcommunity.com").output(None, "", ";")
                encrypted_cookie_string = system_encrypt(cookie_string.encode("utf-8"))
                f.write(encrypted_cookie_string)
        except OSError:
            print("Error: Failed to save cookies into the cookie file")
            return False

        return True

    async def close(self):
        await self.sess.close()
        if self.logged_in:
            self.save_steam_cookie()

    async def __aenter__(self, *args):
        pass

    async def __aexit__(self, *args):
        await self.close()

    async def get(self, url: str, *, allow_redirects: bool = True, **kwargs: Any) -> ClientResponse:
        while True:
            res = None
            try:
                res = await self.sess.get(url, allow_redirects=allow_redirects, **kwargs)
                if res.status == 429:
                    res.close()
                    print("ERROR: Got rate-limited, retrying after a minute...")
                    await asyncio.sleep(65)
                elif res.status != 200 and res.status != 400 and res.status != 302:
                    res.close()
                    print(f"ERROR: Got {res.status}, retrying in a second...")
                    await asyncio.sleep(1)
                else:
                    return res
            except (ClientConnectionError, TimeoutError):
                print("ERROR: Connection failed, retrying...")

                if not res.closed:
                    res.close()

                await asyncio.sleep(1)

    async def get_text(self, url: str, *, allow_redirects: bool = True, **kwargs: Any) -> str:
        while True:
            try:
                async with self.sess.get(url, allow_redirects=allow_redirects, **kwargs) as res:
                    if res.status == 429:
                        print("ERROR: Got rate-limited, retrying after a minute...")
                        await asyncio.sleep(65)
                    elif res.status != 200 and res.status != 400:
                        print(f"ERROR: Got {res.status}, retrying in a second...")
                        await asyncio.sleep(1)
                    else:
                        return await res.text()
            except (ClientConnectionError, TimeoutError):
                print("ERROR: Connection failed, retrying...")
                await asyncio.sleep(1)

    async def steam_auth(self, cookie_string):
        if cookie_string:
            simple_cookie = SimpleCookie()
            simple_cookie.load(cookie_string)
            cookie_dict = {key: unquote(value.value)  for key, value in simple_cookie.items()}
            self.sess.cookie_jar.update_cookies(cookie_dict, URL("https://steamcommunity.com/"))

        response = await self.get("https://steamcommunity.com/login/home", allow_redirects=False)
        result = "Location" in response.headers and (response.headers["Location"].startswith("https://steamcommunity.com/my") or response.headers["Location"].startswith("https://steamcommunity.com/id"))
        response.close()
        return result

    async def steam_auto_auth(self):
        cookie_string = ""
        other_error = False
        if not isfile("cookie"):
            print("In order to proceed, steam authentication is required.")
            print("This is because of steam's strict api rate limits.")
            print("The cookie will be saved locally encrypted using device and OS information.")
            print("In order to get the cookie, login at")
            print("https://steamcommunity.com/ -> F12 -> F5 -> Network -> go to the first request -> copy the 'cookie' string value.")
            cookie_string = input("Please insert your steam cookie here:").strip()
        else:
            try:
                with open("cookie", "rb") as f:
                    cookie_string = system_decrypt(f.read()).decode("utf-8")
            except (OSError, UnicodeDecodeError):
                other_error = True
                print("Error: Failed to extract cookies from the cookie file")

        while not await self.steam_auth(cookie_string):
            if not other_error:
                print("Error: Authentication failed.")
            other_error = False
            cookie_string = input("Please insert your steam cookie here:").strip()

        self.logged_in = True
