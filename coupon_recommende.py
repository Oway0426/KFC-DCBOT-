import json
import copy
import sys
import heapq

sys.setrecursionlimit(100_000)
sys.stdout = open("output.txt", "w")
sys.stdout.reconfigure(encoding='utf-8')
with open("coupon.txt", "r", encoding="utf-8") as f:
    data = json.load(f)
big_menu = data['coupon_by_code']

with open("log_full.txt", "r", encoding="utf-8") as f:
    menu = json.load(f)
big_menu.update(menu)

want: dict[str, int] = {'咔啦脆雞': 1, '原味蛋撻': 8, '瓶裝百事可樂': 2}

equal: dict[str, str] = {
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
ignore: set[str] = {"不需刀叉及手套", "需要刀叉及手套", "響應環保不需叉子", "需要叉子", "響應環保不需湯匙", "糖醋醬", "需要湯匙"}

for key in list(want):
    mult: int = want.pop(key)
    for i in key.split('+'):
        i: str = i.strip()
        num: int = -1
        num_str: str = ""
        if i[0].isdigit():
            for c in i:
                if c.isdigit():
                    num_str += c
                else:
                    break
            num = int(num_str)
        want[i[int(num != -1) + len(num_str):]] = want.get(i[int(num != -1) + len(num_str):], 0) + mult * (num if num != -1 else 1)
for key in list(want):
    if key in equal:
        want[equal[key]] = want.pop(key)
for key in list(big_menu):
    if key.find("優惠券") != -1:
        del big_menu[key]
        continue
    if key in equal:
        big_menu[equal[key]] = big_menu.pop(key)
        key: str = equal[key]
    big_menu[key]['items'] = [_ for _ in big_menu[key]['items'] if _ != {}]
    for i in big_menu[key]['items']:
        i['name'] = equal.get(i['name'], i['name'])
        for j in i['flavors']:
            j['name'] = equal.get(j['name'], j['name'])
    if big_menu[key]['name'].find("前供應") != -1:
        big_menu[key]['name'] = big_menu[key]['name'][big_menu[key]['name'].find("前供應") + 3:]
    if big_menu[key]['name'].find("點心盒-") != -1:
        big_menu[key]['name'] = big_menu[key]['name'].replace("點心盒-", "")
    if big_menu[key]['name'].find("限時優惠-") != -1:
        big_menu[key]['name'] = big_menu[key]['name'].replace("限時優惠-", "")
    big_menu[key]['items'] = [_ for _ in big_menu[key]['items'] if _['name'] not in ignore]
    if len(big_menu[key]['items']) <= 1 and not key.isdigit():
        new_items = []
        for i in big_menu[key]['name'].split('+'):
            i: str = i.strip()
            i = equal.get(i, i)
            num: int = -1
            num_str: str = ""
            if i[0].isdigit() and i.find('（') == -1:
                for c in i:
                    if c.isdigit():
                        num_str += c
                    else:
                        break
                num = int(num_str)
            new_items.append({
                'name': i[int(num != -1) + len(num_str):],
                'count': num if num != -1 else 1,
                'addition_price': 0,
                'flavors': []
            })
            new_items[-1]['name'] = equal.get(new_items[-1]['name'], new_items[-1]['name'])
        new_items.extend(big_menu[key]['items'])
        big_menu[key]['items'] = new_items
    if key == "4塊上校雞塊":
        big_menu["上校雞塊"] = big_menu[key]
for key in list(big_menu):
    for i in big_menu[key]['items']:
        i['name'] = equal.get(i['name'], i['name'])
    if key in equal:
        big_menu[equal[key]] = big_menu.pop(key)

def modify_str(s: str) -> list[dict]:
    ret: list[dict] = []
    s = equal.get(s, s)
    if s.find("前供應") != -1:
        s = s[s.find("前供應") + 3:]
    if s.find("點心盒-") != -1:
       s = s.replace("點心盒-", "")
    if s.find("限時優惠-") != -1:
        s = s.replace("限時優惠-", "")
    if s.find("(1份餐限加點1個)") != -1:
        s = s.replace("(1份餐限加點1個)", "")
    for i in s.split('+'):
        i: str = i.strip()
        num: int = -1
        num_str: str = ""
        if i[0].isdigit():
            for c in i:
                if c.isdigit():
                    num_str += c
                else:
                    break
            num = int(num_str)
        ret.append({
            "name": i[int(num != -1) + len(num_str):],
            "count": num if num != -1 else 1,
            "addition_price": 0,
            "flavors": []
        })
        ret[-1]['name'] = equal.get(ret[-1]['name'], ret[-1]['name'])
    return ret
adding_dict: dict = {}
for _ in big_menu:
    new_items: list = []
    for i in big_menu[_]['items']:
        if i['count'] > 0:
            tmp_main_item = modify_str(i['name'])
            for j in i['flavors']:
                tmp_flavor = modify_str(j['name'])[0]
                tmp_flavor['count'] *= i['count']
                tmp_flavor['addition_price'] = j['addition_price']
                for j in tmp_main_item:
                    j['flavors'].append(tmp_flavor)
            for j in tmp_main_item:
                j['count'] *= i['count']
                j['addition_price'] = i['addition_price']
            new_items.extend(tmp_main_item)
        elif len(adding_dict) == 0:
            adding_dict['name'] = i['addition_price']
            for j in i['flavors']:
                adding_dict[j['name']] = j['addition_price']
    big_menu[_]['items'] = new_items

heap: list = []
st: set = set()
prev: str = ""
lst: dict[str, str] = {}
for _ in big_menu:
    if prev != "":
        lst[prev] = _
    prev = _
def dfs(current: str, last: dict[str, int] = copy.copy(want), ans: dict[str, list[dict]] = {}, cur_price: int = 0, all_price: int = 0, adding: bool = False) -> None:
    global big_menu, heap, lst
    #print(current, end = " ")
    #print(cur_price, end = " ")
    #print(all_price)
    #print(last)
    #print(heap)
    current_coupon = big_menu[current] # current_coupon = dict[name, price, items...]
    tmpdict: dict = {}
    originalpay: int = 0
    extrapay: int = 0
    tmp_all_price: int = all_price
    tmp_cur_price: int = cur_price
    cpydict: dict[str, int] = copy.copy(last)
    cpyans: dict = copy.copy(ans)
    tmp_ans = copy.copy(ans)
    tmp_last: dict[str, int] = copy.copy(last)
    for i in cpydict:
        if cpydict[i] > 0:
            dct: dict = {}
            tmp_all_price += (big_menu[i]['price'] if i in big_menu else 0) * (cpydict[i] // (big_menu[i]['items'][0]['count'] if i in big_menu else 1))
            if adding == True:
                for key in adding_dict:
                    items: list = modify_str(key)
                    count: int = int(1e10)
                    for _ in items:
                        count = min(cpydict.get(_['name'], 0) // _['count'], count)
                    for _ in items:
                        cpydict[_['name']] -= count * _['count']
                    tmp_cur_price += count * adding_dict['addition_price']
                    if count > 0:
                        if key in dct:
                            dct[key] += count
                        else:
                            dct[key] = count
                cpyans['超值加點'] = [copy.copy(dct)]
            tmp_cur_price += (big_menu[i]['price'] if i in big_menu else 10000) * (cpydict[i] // (big_menu[i]['items'][0]['count'] if i in big_menu else 1))
            cpyans[i] = [{i: cpydict[i]}]
    if len(heap) == 10 and tmp_cur_price >= -heap[0][0]:
        return None
    x: tuple = (-tmp_cur_price, tmp_all_price, -len(cpyans), str(cpyans))
    if x not in st:
        heapq.heappush(heap, x)
        st.add(x)
        if len(st) > 10:
            st.remove(heapq.heappop(heap))
        if current in lst:
            dfs(lst[current], copy.copy(last), copy.copy(tmp_ans), cur_price, all_price, adding)
    for j in current_coupon['items']: # j = dict[name, count, addition_price, flavors]
        if j['count'] < 0:
            adding = True
            continue
        tmpcnt = min(j['count'], last.get(j['name'], 0) - tmpdict.get(j['name'], 0))
        if tmpcnt > 0:
            if j['name'] in tmpdict:
                tmpdict[j['name']] += tmpcnt
            else:
                tmpdict[j['name']] = tmpcnt
            if j['name'] in big_menu:
                originalpay += big_menu[j['name']]['price'] * tmpcnt
            extrapay += j['addition_price'] * tmpcnt
        for k in j['flavors']: # k = dict[name, addition_price]
            if tmpcnt >= j['count']:
                break
            num: int = min(j['count'] - tmpcnt, tmp_last.get(k['name'], 0) - tmpdict.get(k['name'], 0))
            if num > 0:
                if k['name'] in tmpdict:
                    tmpdict[k['name']] += num
                else:
                    tmpdict[k['name']] = num
                tmpcnt += num
                if k['name'] in big_menu:
                    originalpay += big_menu[k['name']]['price'] * num
                extrapay += k['addition_price'] * num
        if tmpcnt < j['count']:
            if j['name'] in tmpdict:
                tmpdict[j['name']] += j['count'] - tmpcnt
            else:
                tmpdict[j['name']] = j['count'] - tmpcnt
            tmp_last[j['name']] = tmp_last.get(j['name'], 0) + j['count'] - tmpcnt
            tmpcnt = j['count']
            extrapay += j['addition_price'] * (j['count'] - tmpcnt)
    for _ in list(tmpdict):
        if tmpdict[_] <= 0:
            del tmpdict[_]
    if extrapay + current_coupon['price'] <= originalpay:
        for j in tmpdict:
            tmp_last[j] -= tmpdict[j]
            all_price += (big_menu[j]['price'] if j in big_menu else 0) * (tmpdict[j] // (big_menu[j]['items'][0]['count'] if j in big_menu else 1))
            if tmp_last[j] <= 0:
                del tmp_last[j]
        cur_price += extrapay + current_coupon['price']
        if len(heap) == 10 and cur_price > -heap[0][0]:
            return None
        if current in tmp_ans:
            tmp_ans[current].append(copy.copy(tmpdict))
        else:
            tmp_ans[current] = [copy.copy(tmpdict)]
        tmp_all_price: int = all_price
        tmp_cur_price: int = cur_price
        cpydict = copy.copy(tmp_last)
        cpyans: dict = copy.copy(tmp_ans)
        for i in cpydict:
            if cpydict[i] > 0:
                tmp_all_price += (big_menu[i]['price'] if i in big_menu else 0) * (cpydict[i] // (big_menu[i]['items'][0]['count'] if i in big_menu else 1))
                dct: dict = {}
                if adding == True:
                    for key in adding_dict:
                        items: list = modify_str(key)
                        count: int = int(1e10)
                        for _ in items:
                            count = min(cpydict.get(_['name'], 0) // _['count'], count)
                        for _ in items:
                            cpydict[_['name']] -= count * _['count']
                        tmp_cur_price += count * adding_dict['addition_price']
                        if count > 0:
                            if key in dct:
                                dct[key] += count
                            else:
                                dct[key] = count
                    cpyans['超值加點'] = [copy.copy(dct)]
                tmp_cur_price += (big_menu[i]['price'] if i in big_menu else 10000) * (cpydict[i] // (big_menu[i]['items'][0]['count'] if i in big_menu else 1))
                cpyans[i] = [{i: cpydict[i]}]
        if len(heap) == 10 and tmp_cur_price >= -heap[0][0]:
            return None
        x = (-tmp_cur_price, tmp_all_price, -len(cpyans), str(cpyans))
        if x not in st:
            heapq.heappush(heap, x)
            st.add(x)
            if len(st) > 10:
                st.remove(heapq.heappop(heap))
            dfs(current, copy.copy(tmp_last), copy.copy(tmp_ans), cur_price, all_price, adding)
    return None


equal_rev: dict[str, str] = {
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

def coupon_recommender(_want):
    global heap, lst, st
    heap = []
    st = set()
    for i in lst:
        dfs(i, last=copy.copy(_want))
    l: list = []

    while heap:
        a, b, c, ans_dict = heapq.heappop(heap)
        my_dict = json.loads(ans_dict.replace('\'', '\"'))
        for _ in my_dict:
            for i in my_dict[_]:
                for j in i:
                    for k in j:
                        if k in equal_rev:
                            j[equal_rev[k]] = j.pop(k)
        l.append({
            "total_price": -a,
            "original_price": b,
            "packages": my_dict
        })
    return l[::-1]

if __name__ == '__main__':
    print(json.dumps(coupon_recommender(want), indent = 4, ensure_ascii = False))