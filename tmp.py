"""感謝作者https://winedays.github.io/KCouper/
提供API
"""
# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, timezone
import time
import json
import logging
import sys
import requests

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36'

FORMAT = '[%(levelname)s] %(asctime)s %(filename)s(%(lineno)d): %(message)s'
fileHandler = logging.FileHandler('debug.log', mode='w')
streamHandler = logging.StreamHandler(sys.stdout)
logging.basicConfig(level=logging.INFO, format=FORMAT, handlers=[fileHandler, streamHandler])
LOG: logging.Logger = logging.getLogger('kcouper')
SHOP_CODE = "TWI104"


def get_date(dt: str) -> str:
    date_obj: datetime = datetime.strptime(dt, '%Y/%m/%d %H:%M:%S')
    return datetime.strftime(date_obj, '%Y-%m-%d')


def api_caller(session: requests.Session, url: str, body: dict, msg_prefix: str, retry: int = 0):
    resp: requests.Response = session.post(url, json=body)
    if resp.status_code == 502:
        if retry > 10:
            raise Exception('abort with api retry count > 10')
        retry += 1
        LOG.warning(f'{msg_prefix} 502 error, {retry=}')
        time.sleep(30)
        return api_caller(session, url, body, msg_prefix, retry)
    if resp.status_code != 200:
        msg: str = f'{msg_prefix} error, status code: {resp.status_code}, text: {resp.text}'
        LOG.error(msg)
        raise Exception(msg)
    return resp.json()


def convertCouponData(data: dict, coupon_code: str):
    try:
        detail = data['FoodDetail']
    except KeyError:
        LOG.error(f'food detail not found in {data=}')
        raise
    if len(detail) != 1:
        LOG.error(f'unknown food detail format, {detail=}')
        raise ValueError(f'unknown food detail format, {detail=}')
    detail = detail[0]

    # food details
    items = []
    price = detail['Original_Price']
    for food in detail['Details']:
        main_item = food['MList'][0]
        item = {
            'name': main_item['Name'],
            'count': food['MinCount'],
            'addition_price': main_item['AddPrice'],
            'flavors': [],
        }
        price += main_item['MListPrice'] * food['MinCount']
        for flavor in food['MList'][1:]:
            item['flavors'].append({
                'name': flavor['Name'],
                'addition_price': flavor['AddPrice'],
            })
        items.append(item)

    return {
        'name': detail['Name'],
        'product_code': detail['Fcode'],
        'coupon_code': coupon_code,
        'price': price,
        'items': items,
        'start_date': get_date(detail['StartDate']),
        'end_date': get_date(detail['EndDate']),
    }


def initSession() -> requests.Session:
    session = requests.Session()
    session.headers['User-Agent'] = USER_AGENT
    session.headers['origin'] = 'https://www.kfcclub.com.tw'
    session.headers['referer'] = 'https://www.kfcclub.com.tw/'
    return session


def initDeliveryInfo(session: requests.Session):
    resp = api_caller(
        session,
        'https://olo-api.kfcclub.com.tw/menu/v1/QueryDeliveryShops',
        {'shopCode': 'TWI104', 'orderType': '2', 'platform': '1'},
        'get shop info',
    )
    if resp.get('Message') != 'OK' or not resp.get('Success'):
        msg = f'get shop info response error, json: {resp}'
        LOG.error(msg)
        raise Exception(msg)

    resp = api_caller(
        session,
        'https://olo-api.kfcclub.com.tw/menu/v1/QueryDeliveryTime',
        {'shopCode': 'TWI104', 'orderType': '2', 'orderDate': '2025/01/13', 'addQt': '0', 'sdeQt': '0'},
        'get time info',
    )
    if resp.get('Message') != 'OK' or not resp.get('Success'):
        msg: str = f'get time info response error, json: {resp}'
        LOG.error(msg)
        raise Exception(msg)


def getCouponData(session: requests.Session, coupon_code: str) -> dict:
    resp = api_caller(
        session,
        'https://olo-api.kfcclub.com.tw/customer/v1/getEVoucherAPI',
        {
            'voucherNo': coupon_code,
            'phone': '',
            'memberId': '',
            'orderType': '2',
            'mealPeriod': '3',
            'shopCode': SHOP_CODE,
        },
        'get voucher info',
    )
    if resp.get('Message') == '無效的票劵':
        LOG.debug(f'coupon code({coupon_code}) is invalid')
        return None
    if resp.get('Message') != 'OK' or not resp.get('Success'):
        msg = f'get voucher info response error, json: {resp}'
        LOG.error(msg)
        raise Exception(msg)

    try:
        product_code = resp['Data']['productCode']
    except KeyError:
        LOG.error(f'get product code error: coupon code: {coupon_code}, json: {resp}')
        return None

    date: str = datetime.now(timezone(timedelta(hours=8))).strftime("%Y/%m/%d")
    for period in range(1, 5):
        resp = api_caller(
            session,
            'https://olo-api.kfcclub.com.tw/customer/v1/checkCouponProduct',
            {
                'orderDate': date,
                'orderType': '2',
                'mealPeriod': f'{period}',
                'shopCode': SHOP_CODE,
                'couponCode': coupon_code,
                'memberId': '',
            },
            'check voucher valid',
        )
        if resp.get('Message') == 'OK' and resp.get('Success') is True:
            meal_period = f'{period}'
            break
    else:
        LOG.debug(f'coupon code({coupon_code}) is invalid in all periods')
        return None

    resp = api_caller(
        session,
        'https://olo-api.kfcclub.com.tw/menu/v1/GetQueryFoodDetail',
        {
            'shopcode': SHOP_CODE,
            'fcode': product_code,
            'menuid': '',
            'mealperiod': meal_period,
            'ordertype': '2',
            'orderdate': date,
        },
        'get voucher food',
    )
    if resp.get('Message') != 'OK' or not resp.get('Success'):
        msg = f'get voucher food response error, json: {resp}'
        LOG.error(msg)
        raise Exception(msg)

    return resp.get('Data')


def main():
    session: requests.Session = initSession()
    initDeliveryInfo(session)

    coupon_by_code = {}
    ranges: tuple[tuple[int, int], tuple[int, int], tuple[int, int], tuple[int, int]] = ((24000, 26000), (40000, 41000), (50000, 51000), (13000, 15000))
    #ranges = ((24300, 24350),)
    for r in ranges:
        for coupon_code in range(r[0], r[1]):
            LOG.info(f'getting coupon {coupon_code}...')
            try:
                data = getCouponData(session, coupon_code)
            except (KeyError, ValueError) as e:
                LOG.error(str(e))
                continue
            if not data:
                continue

            try:
                food_data = convertCouponData(data, coupon_code)
            except (KeyError, ValueError) as e:
                LOG.error(str(e))
                continue
            if food_data:
                coupon_by_code[coupon_code] = food_data
            time.sleep(0.3)
        time.sleep(1)

    coupon_list = sorted(coupon_by_code.values(), key=lambda x: x["price"])
    utc_plus_eight_time: datetime = datetime.now(timezone.utc) + timedelta(hours=8)
    coupon_dict = {
        'coupon_by_code': coupon_by_code,
        'coupon_list': coupon_list,
        'count': len(coupon_list),
        'last_update': utc_plus_eight_time.strftime('%Y-%m-%d %H:%M:%S')
    }

    formatted_output: str = json.dumps(coupon_dict, ensure_ascii=False, indent=4)
    with open('coupon.txt', 'w', encoding='utf-8') as fp:
        fp.write(formatted_output)


if __name__ == '__main__':
    main()
