import requests
import json
import pandas as pd
import os

HEADERS = {
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.99 Safari/537.36'}


def getTikiLink(pageIdx):
    return f"https://tiki.vn/api/personalish/v1/blocks/listings?limit=48&include=advertisement&aggregations=2&trackity_id=bb3235db-4422-c2e6-cd73-004d43b4111e&category=316&page={pageIdx}&urlKey=sach-truyen-tieng-viet"


def getBookLink(_id, spid):
    return f'https://tiki.vn/api/v2/products/{_id}?platform=web&spid={spid}'


def scrapeDetailsOfItem(item):
    """Request the book's page and return data or None"""

    _id = item['id']
    spid = item['seller_product_id']

    if _id and spid:
        print(f"\tFetching details of item #{_id}")

        res = requests.get(getBookLink(_id, spid), headers=HEADERS)

        if res.status_code == requests.codes.ok:
            resContent = res.json()

            if resContent.get("inventory_status") == "available":
                details = {
                    "productset_group_name": resContent.get("productset_group_name"),
                    "number_of_page": None,
                    "publisher": None,
                    "manufacturer": None
                }

                if "current_seller" in resContent:
                    details["current_seller"] = resContent["current_seller"].get(
                        "name")
                else:
                    details["current_seller"] = None

                for specs in resContent.get("specifications"):
                    if specs.get("name") == "Thông tin chung":
                        for attr in specs.get("attributes"):
                            if attr.get("code") == "number_of_page":
                                details["number_of_page"] = attr.get("value")
                            elif attr.get("code") == "publisher_vn":
                                details["publisher"] = attr.get("value")
                            elif attr.get("code") == "manufacturer":
                                details["manufacturer"] = attr.get("value")

                return details

    return None


def extractBookInfo(item):
    """Create a dict with wanted fields from item"""

    result = {
        'id': item.get('id'),
        'name': item.get('name'),
        'author_name': item.get('author_name'),
        'short_description': item.get('short_description'),
        'price': item.get('price'),
        'discount': item.get('discount'),
        'discount_rate': item.get('discount_rate'),
        'original_price': item.get('original_price')
    }

    if item.get('book_cover'):
        result['book_cover'] = item['book_cover'].get('value')
    else:
        result['book_cover'] = None

    return result


def scrapeTikiData(flash_sale: bool = False, last_page: int = None):

    lpt = None

    if os.path.exists("./lowest_price_tracking.pkl"):
        lpt = pd.read_pickle("lowest_price_tracking.pkl")
        
    data = []
    curPage = 1
    
    # to be added to lpt
    new_items = []
    lpt_update_count = 0


    while True:
        print(f"Fetching page {curPage}.")
        res = requests.get(getTikiLink(curPage), headers=HEADERS)

        if res.status_code == requests.codes.ok:
            resContent = res.json()

            if 'data' in resContent and len(resContent['data']) > 0:
                for bookItem in resContent['data']:
                    entry = extractBookInfo(bookItem)

                    if (lpt is not None) and (entry["id"] in lpt.index):
                            if (lpt.loc[entry["id"], "lowest_price"] > entry["price"]).any():
                                lpt_update_count += 1

                                print("---> Update price of item {}".format(entry["id"]))

                                lpt.at[entry["id"], "lowest_price"] = entry["price"]
                                lpt.at[entry["id"], "lowest_discount"] = entry["discount"]
                                lpt.at[entry["id"], "lowest_discount_rate"] = entry["discount_rate"]
                    else:
                        print("---> Add new item to lpt.")
                        copied_entry = entry.copy()

                        details = scrapeDetailsOfItem(bookItem)
                        
                        if details is not None:
                            copied_entry.update(details)
                            new_items.append(copied_entry)
                            
                    data.append(entry)
            else:
                print(f"WARNING: No data found in page {curPage}")
                break


            if 'paging' not in resContent:
                break
            
            if resContent['paging']['last_page'] > curPage:
                curPage += 1
            else:
                break

        else:
            break

    print("Finish fetching!")


    if lpt_update_count > 0 or len(new_items) > 0:
        if lpt_update_count > 0: 
            print(f"\n{lpt_update_count} updates in lpt")
        
        if len(new_items) > 0:
            print(f"Adding {len(new_items)} new items to lpt")
            
            new_items_df = pd.DataFrame(new_items)
            new_items_df.set_index("id", inplace=True)
            new_items_df.rename(columns={
                "price": "lowest_price",
                "discount": "lowest_discount",
                "discount_rate": "lowest_discount_rate"
            }, inplace=True)

            if lpt is None:
                lpt = new_items_df
            else: 
                lpt = pd.concat([lpt, new_items_df])

        print("\nExport new lowest_price_tracking.pkl")
        lpt.to_pickle("lowest_price_tracking.pkl")
    else:
        print("\nNo update on lowest_price_tracking.pkl")

    if len(data) > 0:
        df = pd.DataFrame(data)
        df.set_index("id", inplace=True)

        return df
    
    return pd.DataFrame()


if __name__ == "__main__":
    df = scrapeTikiData()
    
    if not df.empty:
        total, _ = df.shape
        print(f"Collected {total} items.")

        print("Making pickle file.")

        df.to_pickle("tiki_data.pkl")
    else:
        print("Data is empty!")

    print("Done!")
