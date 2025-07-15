import asyncio
import json
import re
import os
import sys
import shutil
import os.path
import time
import urllib.parse
import tabulate
import importlib
from .connection import Connection
from .currencies import CURRENCIES, currency_string
from .essential import app_path, set_terminal_title

async def main():
    print("Steam Wallet Deposit Calculator")
    print("It calculates prices of buying steam skins from 3rd party services into steam")
    print("Made for skins from cs.money")
    print("Make sure to close any steam page that checks item prices to minimize rate limit")


    min_price = -1
    while min_price < 0 or min_price > 100000:
        try:
            min_price = float(input("Type minimum price (in dollars) [recommended at least 5]:").strip())
        except ValueError:
            pass

    max_price = -1
    while max_price < 1 or max_price > 100000:
        try:
            max_price = float(input("Type maximum price (in dollars):").strip())
        except ValueError:
            pass

    preset = 0
    presets = [["Keys", "Other", "Keychains"], ["Sticker"], ["Knives", "Pistols", "SMGs", "Assault Rifles", "Sniper Rifles", "Shotguns", "Machineguns", "Gloves"]]
    while preset not in [1, 2, 3]:
        print("[1]: Fetch keys and others [Very fast]")
        print("[2]: Fetch keys, others and stickers [Fast]")
        print("[3]: Fetch keys, others, stickers and guns [Very slow]")
        try:
            preset = int(input("Select preset:").strip())
        except ValueError:
            pass

    item_types = []
    for i in range(preset):
        item_types += presets[i]

    currency = ""
    while currency not in CURRENCIES:
        currency = input("Type the desired currency (3 letter code):").upper().strip()

    connection = Connection()

    connection.load_cookies()
    await connection.steam_auth()
    connection.save_cookies()

    # =================================== CS.MONEY items fetch ===================================

    new_data = {}

    for item_type in item_types:
        current_price = min_price
        while max_price > current_price:
            set_terminal_title(f"Fetching items from CS.MONEY {item_type} - ${current_price}")
            page_data = (await connection.get("https://cs.money/csgo/trade/", params={
                "hasTradeLock": "false",
                "minPrice": current_price,
                "maxPrice": max_price,
                "order": "asc",
                "sort": "price",
                "type": item_type,
            })).text

            page_data = json.loads(re.findall(r'<script id="__NEXT_DATA__" type="application/json" crossorigin="anonymous">([^<]+)</script>', page_data)[0])
            items = page_data["props"]["pageProps"]["botInitData"]["skinsInfo"]["skins"]

            for item in items:
                item_name = item["fullName"]
                item_price = item["price"]

                # Some items contain more information in the name which doesn't appear on steam
                if " Doppler" in item_name:
                    item_name = re.sub(r" Doppler (Phase \d|Emerald|Sapphire|Ruby)", " Doppler", item_name)

                if (item_name not in new_data) or (item_price < new_data[item_name]["price"]):
                    new_data[item_name] = { "name": item_name, "price": item_price }

            if len(items) < 60:
                break

            current_price = items[-1]["price"]
            if items[-1]["price"] <= items[0]["price"]:
                current_price += 0.0078125

            await asyncio.sleep(1.3)

    # =================================== steam item id fetch ===================================

    id_list_path = os.path.join(app_path(), "steam_id_data")

    if not os.path.isfile(id_list_path):
        shutil.copyfile(os.path.join(importlib.resources.files("steamdepcalc"), "default_steam_id_data.txt"), id_list_path)

    item_id_hashtable = {}
    with open(id_list_path, "r", encoding="utf-8") as f:
        id_list_data = [x.split("//") for x in f.read().split("\n")]
        for steam_item in id_list_data:
            item_id_hashtable[steam_item[0]] = steam_item[1]

    i = 0
    for item in new_data.values():
        set_terminal_title(f"Fetching item ids from Steam {i}/{len(new_data)}")

        if item["name"] not in item_id_hashtable:
            initial_metadata = (await connection.get(f"https://steamcommunity.com/market/listings/730/{urllib.parse.quote(item['name'], safe='')}", headers={
                "Referer": "https://steamcommunity.com/market/search?q=",
            })).text

            try:
                item_steam_id = re.findall(r"Market_LoadOrderSpread\( (\d+?) \);", initial_metadata)[0]
            except IndexError:
                print(f"Error: Failed to fetch id of '{item['name']}'")
                continue

            item_id_hashtable[item["name"]] = item_steam_id

        item["id"] = item_id_hashtable[item["name"]]
        i += 1

    with open(id_list_path, "w", encoding="utf-8") as f:
        f.write("\n".join(["//".join(x) for x in item_id_hashtable.items()]))

    # ================================== steam item price fetch ==================================

    final_res = []

    i = 0
    for item in new_data.values():
        if "id" not in item:
            continue

        t1 = time.time()
        set_terminal_title(f"Fetching items from Steam {i}/{len(new_data)}")

        data = (await connection.get("https://steamcommunity.com/market/itemordershistogram", params={
            "country": currency[:2],
            "language": "english",
            "currency": CURRENCIES[currency]["id"],
            "item_nameid": item["id"],
            "two_factor": 0,
        }, headers={
            "Referer": f"https://steamcommunity.com/market/listings/730/{urllib.parse.quote(item['name'], safe='')}",
            "X-Requested-With": "XMLHttpRequest",
        })).json()

        if "buy_order_graph" not in data or len(data["buy_order_graph"]) == 0 or len(data["buy_order_graph"][0]) == 0:
            print(f"Error: Failed to fetch item price market of '{item['name']}'")
            item["taxless_steam_price"] = 0
            item["steam_price"] = 0
            item["ratio"] = 0
            final_res.append(item)

        else:
            steam_price = round(data["buy_order_graph"][0][0] / 1.15, 2)
            item["taxless_steam_price"] = data["buy_order_graph"][0][0]
            item["steam_price"] = steam_price
            item["ratio"] = round(steam_price / item["price"], 2)
            final_res.append(item)

        wait_time = 0.9 - (time.time() - t1)
        if wait_time > 0:
            await asyncio.sleep(wait_time)
        i += 1

    # ================================ calculation results print ================================

    connection.save_cookies()
    await connection.close()

    final_res.sort(key=lambda x: x["ratio"], reverse=True)

    table = [["Name", "Buy", "Sell", "Get", "Ratio"], *[[item["name"], f'${item["price"]:.2f}', currency_string(item["taxless_steam_price"], currency), currency_string(item["steam_price"], currency), f'{currency_string(item["ratio"], currency)}/$'] for item in final_res]]

    beautiful_table = tabulate.tabulate(table[:17], headers='firstrow', tablefmt='fancy_grid', numalign="left")
    set_terminal_title("Steam skins conversion table results")
    print(beautiful_table)

def entrypoint():
    if sys.platform in ["win32", "cygwin", "msys"]:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())

if __name__ == "__main__":
    entrypoint()