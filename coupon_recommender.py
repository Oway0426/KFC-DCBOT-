import json
import copy
import sys
import heapq
import os

sys.setrecursionlimit(100_000)

# 輔助函式：讀取 JSON 檔案
def load_json(file_path: str):
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

# 假設 coupon.txt 與 log_full.txt 與本模組位於同一資料夾
base_path = os.path.dirname(__file__)
coupon_path = os.path.join(base_path, "coupon.txt")
log_full_path = os.path.join(base_path, "log_full.txt")

data = load_json(coupon_path)
big_menu = data['coupon_by_code']

menu_data = load_json(log_full_path)
big_menu.update(menu_data)

"""
big_menu 結構範例：
{
    '商品名 / coupon_code': {
        'name': '商品名 / coupon_code',
        'price': 399,
        'items': [
            {
                'name': "...",
                'count': 4,
                'addition_price': 0,
                'flavors': [
                    {
                        'name': "...",
                        "addition_price": 0
                    },
                    ...
                ]
            },
            ...
        ],
        ...
    },
    ...
}
"""

# 名稱對應與過濾設定
equal = {
    "小薯": "香酥脆薯(小)",
    "薯條(大)": "香酥脆薯(大)",
    "雞塊": "上校雞塊",
    "紫芋金來金沙雞 2塊": "2塊紫芋金來金沙雞",
    "20:00前供應雞汁風味飯": "雞汁風味飯",
    "上校雞塊4塊": "4塊上校雞塊",
    "上校雞塊8塊": "8塊上校雞塊",
    "原味蛋撻禮盒": "6個原味蛋撻",
    "Biscoff®雙色蛋撻(原+焦)禮盒": "3個Biscoff®焦糖脆餅蛋撻+3個原味蛋撻",
    "Biscoff®焦糖脆餅蛋撻禮盒": "6個Biscoff®焦糖脆餅蛋撻",
    "瓶裝百事可樂": "百事可樂(中)",
    "冰心蛋撻風味冰淇淋4入組": "4入冰心蛋撻風味冰淇淋",
    "10顆雙色轉轉QQ球": "雙色轉轉QQ球",
    "上校雞塊分享盒(20塊)": "20塊上校雞塊",
    "上校雞塊分享盒": "20塊上校雞塊",
    "蝦薯樂優惠": "1個黃金超蝦塊+1個香酥脆薯(小)",
    "點心省優惠": "1個金黃比司吉+4個上校雞塊",
    "咔啦脆雞 (辣)": "咔啦脆雞",
    "咔啦脆雞(辣)": "咔啦脆雞",
    "上校薄脆雞(不辣)": "上校薄脆雞",
    "青花椒香麻脆雞(辣)": "青花椒香麻脆雞",
    "花生熔岩咔啦雞腿堡(辣)": "花生熔岩咔啦雞腿堡",
    "100%柳橙汁": "柳橙汁",
    "茉莉無糖綠茶(中)": "冰無糖綠茶(中)",
    "無糖綠茶(中)": "冰無糖綠茶(中)"
}
ignore = {"不需刀叉及手套", "需要刀叉及手套", "響應環保不需叉子", "需要叉子", "響應環保不需湯匙", "糖醋醬", "需要湯匙"}

# 將 want 字典拆分、數量化與名稱轉換（want 格式例如 {"上校雞塊": 4, "原味蛋撻": 8, ...}）
def process_want(want: dict) -> dict:
    new_want = {}
    for key, mult in list(want.items()):
        for part in key.split('+'):
            part = part.strip()
            num_str = ""
            num = -1
            if part and part[0].isdigit():
                for c in part:
                    if c.isdigit():
                        num_str += c
                    else:
                        break
                num = int(num_str)
            item_name = part[(len(num_str) + (1 if num != -1 else 0)):]
            new_want[item_name] = new_want.get(item_name, 0) + mult * (num if num != -1 else 1)
    for key in list(new_want.keys()):
        if key in equal:
            new_want[equal[key]] = new_want.pop(key)
    return new_want

# 清理與調整 big_menu 資料
def process_big_menu(big_menu: dict) -> dict:
    for key in list(big_menu.keys()):
        if "優惠券" in key:
            del big_menu[key]
            continue
        if key in equal:
            big_menu[equal[key]] = big_menu.pop(key)
            key = equal[key]
        big_menu[key]['items'] = [item for item in big_menu[key]['items'] if item != {}]
        for item in big_menu[key]['items']:
            item['name'] = equal.get(item['name'], item['name'])
            for flavor in item.get('flavors', []):
                flavor['name'] = equal.get(flavor['name'], flavor['name'])
        if "前供應" in big_menu[key]['name']:
            big_menu[key]['name'] = big_menu[key]['name'][big_menu[key]['name'].find("前供應") + 3:]
        if "點心盒-" in big_menu[key]['name']:
            big_menu[key]['name'] = big_menu[key]['name'].replace("點心盒-", "")
        if "限時優惠-" in big_menu[key]['name']:
            big_menu[key]['name'] = big_menu[key]['name'].replace("限時優惠-", "")
        big_menu[key]['items'] = [item for item in big_menu[key]['items'] if item['name'] not in ignore]
        if len(big_menu[key]['items']) <= 1 and not key.isdigit():
            new_items = []
            for part in big_menu[key]['name'].split('+'):
                part = part.strip()
                part = equal.get(part, part)
                num_str = ""
                num = -1
                if part and part[0].isdigit() and '（' not in part:
                    for c in part:
                        if c.isdigit():
                            num_str += c
                        else:
                            break
                    num = int(num_str)
                new_items.append({
                    'name': part[(len(num_str) + (1 if num != -1 else 0)):],
                    'count': num if num != -1 else 1,
                    'addition_price': 0,
                    'flavors': []
                })
                new_items[-1]['name'] = equal.get(new_items[-1]['name'], new_items[-1]['name'])
            new_items.extend(big_menu[key]['items'])
            big_menu[key]['items'] = new_items
        if key == "4塊上校雞塊":
            big_menu["上校雞塊"] = big_menu[key]
    for key in list(big_menu.keys()):
        for item in big_menu[key]['items']:
            item['name'] = equal.get(item['name'], item['name'])
        if key in equal:
            big_menu[equal[key]] = big_menu.pop(key)
    return big_menu

# 將商品名稱字串解析為結構化資料
def modify_str(s: str) -> list:
    ret = []
    s = equal.get(s, s)
    if "前供應" in s:
        s = s[s.find("前供應") + 3:]
    if "點心盒-" in s:
        s = s.replace("點心盒-", "")
    if "限時優惠-" in s:
        s = s.replace("限時優惠-", "")
    if "(1份餐限加點1個)" in s:
        s = s.replace("(1份餐限加點1個)", "")
    for part in s.split('+'):
        part = part.strip()
        num_str = ""
        num = -1
        if part and part[0].isdigit():
            for c in part:
                if c.isdigit():
                    num_str += c
                else:
                    break
            num = int(num_str)
        ret.append({
            "name": part[(len(num_str) + (1 if num != -1 else 0)):],
            "count": num if num != -1 else 1,
            "addition_price": 0,
            "flavors": []
        })
        ret[-1]['name'] = equal.get(ret[-1]['name'], ret[-1]['name'])
    return ret

# 處理加點資料
def process_adding_dict(big_menu: dict) -> dict:
    adding_dict = {}
    for key in big_menu:
        new_items = []
        for item in big_menu[key]['items']:
            if item['count'] > 0:
                tmp_main_item = modify_str(item['name'])
                for flavor in item.get('flavors', []):
                    tmp_flavor = modify_str(flavor['name'])[0]
                    tmp_flavor['count'] *= item['count']
                    tmp_flavor['addition_price'] = flavor['addition_price']
                    for m in tmp_main_item:
                        m['flavors'].append(tmp_flavor)
                for m in tmp_main_item:
                    m['count'] *= item['count']
                    m['addition_price'] = item['addition_price']
                new_items.extend(tmp_main_item)
            elif len(adding_dict) == 0:
                adding_dict['name'] = item['addition_price']
                for flavor in item.get('flavors', []):
                    adding_dict[flavor['name']] = flavor['addition_price']
        big_menu[key]['items'] = new_items
    return adding_dict

# 先處理資料
big_menu = process_big_menu(big_menu)
adding_dict = process_adding_dict(big_menu)

# 建立連結字典，用以 DFS 遍歷（依照 big_menu 的順序連接各 key）
prev = ""
lst = {}
for key in big_menu:
    if prev:
        lst[prev] = key
    prev = key

# DFS 搜索函式（使用全域 heap 與 st 儲存最佳方案）
def dfs(current: str, last: dict = None, ans: dict = None, cur_price: int = 0, all_price: int = 0, adding: bool = False) -> None:
    if last is None:
        last = copy.deepcopy(want_processed)
    if ans is None:
        ans = {}
    global big_menu, heap, lst, adding_dict
    current_coupon = big_menu[current]
    tmpdict = {}
    originalpay = 0
    extrapay = 0
    tmp_all_price = all_price
    tmp_cur_price = cur_price
    cpydict = copy.deepcopy(last)
    cpyans = copy.deepcopy(ans)
    tmp_ans = copy.deepcopy(ans)
    tmp_last = copy.deepcopy(last)
    for i in cpydict:
        if cpydict[i] > 0:
            dct = {}
            if adding:
                for key in adding_dict:
                    items = modify_str(key)
                    count = int(1e10)
                    for item in items:
                        count = min(cpydict.get(item['name'], 0) // item['count'], count)
                    for item in items:
                        cpydict[item['name']] -= count * item['count']
                    tmp_cur_price += count * adding_dict['name']
                    if count > 0:
                        dct[key] = dct.get(key, 0) + count
                cpyans['超值加點'] = [copy.deepcopy(dct)]
            if current in big_menu:
                unit = big_menu[current]['items'][0]['count'] if big_menu[current]['items'] else 1
                tmp_cur_price += (big_menu[i]['price'] if i in big_menu else 10000) * (cpydict[i] // unit)
                tmp_all_price += (big_menu[i]['price'] if i in big_menu else 0) * (cpydict[i] // unit)
            cpyans[i] = [{i: cpydict[i]}]
    global st
    if len(heap) == 10 and tmp_cur_price >= -heap[0][0]:
        return
    x = (-tmp_cur_price, tmp_all_price, -len(cpyans), str(cpyans))
    if x not in st:
        heapq.heappush(heap, x)
        st.add(x)
        if len(st) > 10:
            st.remove(heapq.heappop(heap))
        if current in lst:
            dfs(lst[current], copy.deepcopy(last), copy.deepcopy(tmp_ans), cur_price, all_price, adding)
    for j in current_coupon['items']:
        if j['count'] < 0:
            adding = True
            continue
        tmpcnt = min(j['count'], last.get(j['name'], 0) - tmpdict.get(j['name'], 0))
        if tmpcnt > 0:
            tmpdict[j['name']] = tmpdict.get(j['name'], 0) + tmpcnt
            if j['name'] in big_menu:
                originalpay += big_menu[j['name']]['price'] * tmpcnt
            extrapay += j['addition_price'] * tmpcnt
        for k in j['flavors']:
            if tmpcnt >= j['count']:
                break
            num = min(j['count'] - tmpcnt, tmp_last.get(k['name'], 0) - tmpdict.get(k['name'], 0))
            if num > 0:
                tmpdict[k['name']] = tmpdict.get(k['name'], 0) + num
                tmpcnt += num
                if k['name'] in big_menu:
                    originalpay += big_menu[k['name']]['price'] * num
                extrapay += k['addition_price'] * num
        if tmpcnt < j['count']:
            tmpdict[j['name']] = tmpdict.get(j['name'], 0) + (j['count'] - tmpcnt)
            tmp_last[j['name']] = tmp_last.get(j['name'], 0) + j['count'] - tmpcnt
            tmpcnt = j['count']
            extrapay += j['addition_price'] * (j['count'] - tmpcnt)
    for key in list(tmpdict):
        if tmpdict[key] <= 0:
            del tmpdict[key]
    if extrapay + current_coupon['price'] <= originalpay:
        for j in tmpdict:
            tmp_last[j] -= tmpdict[j]
            all_price += big_menu[current]['price'] * tmpdict[j]
            if tmp_last[j] <= 0:
                del tmp_last[j]
        cur_price += extrapay + current_coupon['price']
        if len(heap) == 10 and cur_price > -heap[0][0]:
            return
        if current in tmp_ans:
            tmp_ans[current].append(copy.deepcopy(tmpdict))
        else:
            tmp_ans[current] = [copy.deepcopy(tmpdict)]
        tmp_all_price = all_price
        tmp_cur_price = cur_price
        cpydict = copy.deepcopy(tmp_last)
        cpyans = copy.deepcopy(tmp_ans)
        for i in cpydict:
            if cpydict[i] > 0:
                dct = {}
                if adding:
                    for key in adding_dict:
                        items = modify_str(key)
                        count = int(1e10)
                        for item in items:
                            count = min(cpydict.get(item['name'], 0) // item['count'], count)
                        for item in items:
                            cpydict[item['name']] -= count * item['count']
                        tmp_cur_price += count * adding_dict['name']
                        if count > 0:
                            dct[key] = dct.get(key, 0) + count
                    cpyans['超值加點'] = [copy.deepcopy(dct)]
                if i in big_menu:
                    unit = big_menu[i]['items'][0]['count'] if big_menu[i]['items'] else 1
                    tmp_all_price += (big_menu[i]['price'] if i in big_menu else 0) * (cpydict[i] // unit)
                    tmp_cur_price += (big_menu[i]['price'] if i in big_menu else 10000) * (cpydict[i] // unit)
                cpyans[i] = [{i: cpydict[i]}]
        if len(heap) == 10 and tmp_cur_price >= -heap[0][0]:
            return
        x = (-tmp_cur_price, tmp_all_price, -len(cpyans), str(cpyans))
        if x not in st:
            heapq.heappush(heap, x)
            st.add(x)
            if len(st) > 10:
                st.remove(heapq.heappop(heap))
            dfs(current, copy.deepcopy(tmp_last), copy.deepcopy(tmp_ans), cur_price, all_price, adding)
    return

# 全域變數，用來儲存 DFS 搜索結果
heap = []
st = set()

# 主函式，輸入 want 字典（格式：{商品名稱: 數量, ...}），回傳推薦套餐列表
def get_recommended_packages(want: dict) -> list:
    global want_processed, heap, st
    want_processed = process_want(want)
    heap.clear()
    st.clear()
    for key in lst:
        dfs(key)
    equal_rev = {
        "2塊紫芋金來金沙雞": "紫芋金來金沙雞 2塊",
        "4塊上校雞塊": "上校雞塊4塊",
        "8塊上校雞塊": "上校雞塊8塊",
        "6個原味蛋撻": "原味蛋撻禮盒",
        "3個Biscoff®焦糖脆餅蛋撻+3個原味蛋撻": "Biscoff®雙色蛋撻(原+焦)禮盒",
        "6個Biscoff®焦糖脆餅蛋撻": "Biscoff®焦糖脆餅蛋撻禮盒",
        "4入冰心蛋撻風味冰淇淋": "冰心蛋撻風味冰淇淋4入組",
        "10顆雙色轉轉QQ球": "雙色轉轉QQ球",
        "20塊上校雞塊": "上校雞塊分享盒(20塊)",
        "1個黃金超蝦塊+1個香酥脆薯(小)": "蝦薯樂優惠",
        "1個金黃比司吉+4個上校雞塊": "點心省優惠",
        "咔啦脆雞": "咔啦脆雞(辣)",
        "上校薄脆雞": "上校薄脆雞(不辣)",
        "青花椒香麻脆雞": "青花椒香麻脆雞(辣)",
        "花生熔岩咔啦雞腿堡": "花生熔岩咔啦雞腿堡(辣)"
    }
    results = []
    while heap:
        a, b, c, ans_dict = heapq.heappop(heap)
        my_dict = json.loads(ans_dict.replace("'", "\""))
        for key in my_dict:
            for idx, item in enumerate(my_dict[key]):
                new_item = {}
                for k, v in item.items():
                    if k in equal_rev:
                        new_item[equal_rev[k]] = v
                    else:
                        new_item[k] = v
                my_dict[key][idx] = new_item
        results.append({"total_price": -a, "packages": my_dict})
    results.reverse()
    return results

if __name__ == "__main__":
    test_want = {"百事可樂(小)": 1, "青花椒咔啦雞腿堡": 1}
    recommended = get_recommended_packages(test_want)
    print(json.dumps(recommended, indent=4, ensure_ascii=False))
