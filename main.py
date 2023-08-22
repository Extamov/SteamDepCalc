import asyncio
import json
import re
import os
from time import time, sleep
from urllib.parse import quote
from libs.tabulate import tabulate
from libs.connection import Connection
from libs.currencies import CURRENCIES, currency_string

async def main():
    print("Steam Wallet Deposit Calculator")
    print("It calculates prices of buying steam skins from 3rd party services into steam")
    print("Made for skins from cs.money")
    print("Beware that cs.money has 30% discount on deposits which is counted in the calculations")
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
    presets = [[1, 12, 14, 11, 8, 9, 18, 19], [10], [5, 6, 7, 4, 3]]
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
        os.system(f"title Fetching cs.money prices: #{i}")
        data = json.loads(await connection.get_text("https://inventories.cs.money/5.0/load_bots_inventory/730", params={
            "hasTradeLock": "false",
            "isMarket": "false",
            "limit": 60,
            "minPrice": min_price*1.3,
            "maxPrice": max_price*1.3,
            "offset": i*60,
            "order": "asc",
            "priceWithBonus": 30,
            "sort": "price",
            "type": item_types,
            "withStack": "true",
        }))

        if ("error" in data) and (data["error"] == 2):
            break

        if "items" in data:
            for item in data["items"]:
                item_name = item["fullName"]
                item_price = item["priceWithBonus"]
                if (item_name not in new_data) or (item_price < new_data[item_name]["price"]):
                    new_data[item_name] = { "name": item_name, "price": item_price }
        elif ("error" not in data) or (data["error"] != 2):
            print("ERROR!!")
            print(json.dumps(data))
            quit(1)

        if i == 60:
            i = 0
            min_price = data["items"][-1]["price"]

        i += 1

    # =================================== cs.money items fetch ===================================

    async def the_worker(item, semaphore):
        initial_metadata = await connection.get_text(f"https://steamcommunity.com/market/listings/730/{quote(item['name'], safe='')}", headers={
                "Referer": "https://steamcommunity.com/market/search?q=",
        })
        item_steam_id = ""
        try:
            item_steam_id = re.findall(r"Market_LoadOrderSpread\( (\d+?) \);", initial_metadata)[0]
        except IndexError:
            print(f"Error: Failed to fetch id of '{item['name']}'")
            semaphore.release()
            return
        item["id"] = item_steam_id
        semaphore.release()

    tasks = []
    semaphore = asyncio.Semaphore(6)
    i = 0
    for item in new_data.values():
        os.system(f"title Fetching steam item ids: {i}/{len(new_data)}")
        await semaphore.acquire()
        tasks += [asyncio.create_task(the_worker(item, semaphore))]
        i += 1

    await asyncio.wait(tasks)

    # ================================================================================================================

    final_res = []

    i = 0
    for item in new_data.values():
        if "id" not in item:
            continue

        t1 = time()
        os.system(f"title Fetching steam prices: {i}/{len(new_data)}")

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

    # ================================================================================================================

    await connection.close()

    final_res.sort(key=lambda x: x["ratio"], reverse=True)

    table = [["Name", "Buy", "Sell", "Get", "Ratio"], *[[item["name"], f'${item["price"]:.2f}', currency_string(item["taxless_steam_price"], currency), currency_string(item["steam_price"], currency), f'{currency_string(item["ratio"], currency)}/$'] for item in final_res]]

    beautiful_table = tabulate(table[:17], headers='firstrow', tablefmt='fancy_grid', numalign="left")
    full_beautiful_table = tabulate(table, headers='firstrow', tablefmt='fancy_grid', numalign="left")

    os.system("clear" if os.name == "posix" else "cls")
    # os.system(f"mode con: cols={beautiful_table.index('╕') + 1} lines={len(table[:17])*2 + 2}")
    os.system("title Steam skins conversion table results")
    with open("results.txt", "w", encoding="utf-8") as f:
        f.write(full_beautiful_table)
    print(beautiful_table)

if __name__ == "__main__":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
    sleep(2000000000)