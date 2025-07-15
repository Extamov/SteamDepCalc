import asyncio
import pickle
import curl_cffi
import typing
import os.path
import urllib.parse
from .encryption import system_encrypt, system_decrypt
from .essential import app_path

COOKIES_PATH = os.path.join(app_path(), "cookie")

class Connection:
    sess: curl_cffi.AsyncSession

    def __init__(self):
        self.sess = curl_cffi.AsyncSession(impersonate="chrome136")

    @property
    def cookies(self):
        return self.sess.cookies

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.sess.close()
        return None

    async def close(self):
        await self.sess.close()

    def save_cookies(self):
        with open(COOKIES_PATH, "wb") as f:
            f.write(system_encrypt(pickle.dumps(self.cookies.jar._cookies)))

    def load_cookies(self):
        if os.path.isfile(COOKIES_PATH):
            with open(COOKIES_PATH, "rb") as f:
                data = system_decrypt(f.read())
                if data is not None:
                    self.cookies.jar._cookies.update(pickle.loads(data))

    async def steam_auth(self, first_time=True):
        response = await self.get("https://steamcommunity.com/login/home", allow_redirects=False)
        is_logged_in = "Location" in response.headers and (response.headers["Location"].startswith("https://steamcommunity.com/my") or response.headers["Location"].startswith("https://steamcommunity.com/id"))

        if not is_logged_in:
            if first_time:
                print("In order to proceed, Steam authentication is required.")
                print("This is because of Steam's strict api rate limits.")
                print("The cookie will be saved locally encrypted using device and OS information.")
                print("In order to get the cookie, login to Steam through the browser and follow the instructions below:")
                print("https://steamcommunity.com/ -> F12 -> F5 -> Network -> go to the first request -> 'Headers' section -> copy the value of cookie.")
            else:
                print("Authentication failed, try again.")
            cookie_string = input("Please insert your Steam cookie here:").strip()
            self.cookies.clear("steamcommunity.com")
            for cookie_line in cookie_string.split(";"):
                (key, value) = [urllib.parse.unquote(x) for x in cookie_line.strip().split("=")]
                self.cookies.set(key, value, "steamcommunity.com", secure=True)
            return await self.steam_auth(False)

    async def get(
        self,
        url: str,
        params: dict | list | tuple | None = None,
        data: dict[str, str] | list[tuple] | str | bytes | None = None,
        json: dict | list | None = None,
        headers: curl_cffi.HeaderTypes | None = None,
        allow_redirects: bool | None = None,
        raise_for_status: bool = True,

    ):
        return await self.request("GET", url, params, data, json, headers, allow_redirects, raise_for_status)

    async def post(
        self,
        url: str,
        params: dict | list | tuple | None = None,
        data: dict[str, str] | list[tuple] | str | bytes | None = None,
        json: dict | list | None = None,
        headers: curl_cffi.HeaderTypes | None = None,
        allow_redirects: bool | None = None,
        raise_for_status: bool = True,
    ):
        return await self.request("POST", url, params, data, json, headers, allow_redirects, raise_for_status)

    async def request(
        self,
        method: typing.Literal["GET", "POST"],
        url: str,
        params: dict | list | tuple | None = None,
        data: dict[str, str] | list[tuple] | str | bytes | None = None,
        json: dict | list | None = None,
        headers: curl_cffi.HeaderTypes | None = None,
        allow_redirects: bool | None = None,
        raise_for_status: bool = True,
        _retry_count=0,
    ):
        try:
            response = await self.sess.request(method, url, params, data, json, headers, allow_redirects=allow_redirects)
            if response.status_code == 429:
                print("ERROR: Got rate-limited, retrying after a minute...")
                await asyncio.sleep(65)
                return await self.request(
                    method, url, params, data, json, headers, _retry_count
                )
            if response.status_code != 200 and response.status_code != 302 and raise_for_status:
                raise curl_cffi.exceptions.RequestException(f'Got status code {response.status_code} while fetching "{url}"')
            return response
        except curl_cffi.exceptions.ConnectionError as e:
            if _retry_count > 10:
                raise e
            await asyncio.sleep(5)
            return await self.request(
                method, url, params, data, json, headers, _retry_count + 1
            )
