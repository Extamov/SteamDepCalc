import asyncio
import json
import re
import os
import sys
import shutil
from os.path import join, isfile
from time import time, sleep
from urllib.parse import quote
from tabulate import tabulate
from .connection import Connection
from .currencies import CURRENCIES, currency_string
from .essential import app_path, set_terminal_title
from importlib import resources

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
    presets = [[1, 12, 14, 11, 8, 9, 18, 19, 20], [10], [5, 6, 7, 4, 3, 2, 13]]
    while preset not in [1, 2, 3]:
        print("[1]: All skins except guns and stickers [Fast]")
        print("[2]: All skins except guns [Regular]")
        print("[3]: All skins [Very slow]")
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

    await connection.steam_auto_auth()
    connection.save_steam_cookie()

    # =================================== cs.money items fetch ===================================

    new_data = {}

    i = 0
    while True:
        t1 = time()
        set_terminal_title(f"Fetching cs.money prices: #{i}")
        data = json.loads(await connection.get_text("https://cs.money/5.0/load_bots_inventory/730", params={
            "hasTradeLock": "false",
            "limit": 60,
            "minPrice": min_price,
            "maxPrice": max_price,
            "offset": i*60,
            "order": "asc",
            "sort": "price",
            "type": item_types,
        }))

        if ("error" in data) and (data["error"] == 2):
            break

        if "items" in data:
            for item in data["items"]:
                item_name = item["fullName"]
                item_price = item["price"]

                # Some items contain more information in the name which doesn't appear on steam
                if " Doppler" in item_name:
                    item_name = re.sub(r" Doppler (Phase \d|Emerald|Sapphire|Ruby)", " Doppler", item_name)

                if (item_name not in new_data) or (item_price < new_data[item_name]["price"]):
                    new_data[item_name] = { "name": item_name, "price": item_price }
        elif ("error" in data) and (data["error"] == 429):
            print("ERROR: Got rate-limited, retrying after a minute...")
            await asyncio.sleep(65)
            continue
        else:
            raise ValueError(json.dumps(data))

        i += 1
        wait_time = 4 - (time() - t1)
        await asyncio.sleep(wait_time)

    # =================================== steam item id fetch ===================================

    id_list_path = join(app_path(), "steam_id_data")

    if not isfile(id_list_path):
        shutil.copyfile(join(resources.files("steamdepcalc"), "default_steam_id_data.txt"), id_list_path)

    item_id_hashtable = {}
    with open(id_list_path, "r", encoding="utf-8") as f:
        id_list_data = [x.split("//") for x in f.read().split("\n")]
        for steam_item in id_list_data:
            item_id_hashtable[steam_item[0]] = steam_item[1]

    i = 0
    for item in new_data.values():
        set_terminal_title(f"Fetching steam item ids: {i}/{len(new_data)}")

        if item["name"] not in item_id_hashtable:
            initial_metadata = await connection.get_text(f"https://steamcommunity.com/market/listings/730/{quote(item['name'], safe='')}", headers={
                "Referer": "https://steamcommunity.com/market/search?q=",
            })

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

        t1 = time()
        set_terminal_title(f"Fetching steam prices: {i}/{len(new_data)}")

        data = json.loads(await connection.get_text("https://steamcommunity.com/market/itemordershistogram", params={
            "country": currency[:2],
            "language": "english",
            "currency": CURRENCIES[currency]["id"],
            "item_nameid": item["id"],
            "two_factor": 0,
        }, headers={
            "Referer": f"https://steamcommunity.com/market/listings/730/{quote(item['name'], safe='')}",
            "X-Requested-With": "XMLHttpRequest",
        }))

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

        wait_time = 0.9 - (time() - t1)
        if wait_time > 0:
            await asyncio.sleep(wait_time)
        i += 1

    # ================================ calculation results print ================================

    await connection.close()

    final_res.sort(key=lambda x: x["ratio"], reverse=True)

    table = [["Name", "Buy", "Sell", "Get", "Ratio"], *[[item["name"], f'${item["price"]:.2f}', currency_string(item["taxless_steam_price"], currency), currency_string(item["steam_price"], currency), f'{currency_string(item["ratio"], currency)}/$'] for item in final_res]]

    beautiful_table = tabulate(table[:17], headers='firstrow', tablefmt='fancy_grid', numalign="left")
    full_beautiful_table = tabulate(table, headers='firstrow', tablefmt='fancy_grid', numalign="left")

    os.system("clear" if os.name == "posix" else "cls")
    # os.system(f"mode con: cols={beautiful_table.index('╕') + 1} lines={len(table[:17])*2 + 2}")
    set_terminal_title("Steam skins conversion table results")
    with open("results.log", "w", encoding="utf-8") as f:
        f.write(full_beautiful_table)
    print(beautiful_table)

def entrypoint():
    if sys.platform in ["win32", "cygwin", "msys"]:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())

if __name__ == "__main__":
    entrypoint()