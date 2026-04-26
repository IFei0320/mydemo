import requests
import json
import csv

headers = {
    "accept": "*/*",
    "accept-language": "zh-CN,zh;q=0.9",
    "content-type": "application/json",
    "cookieorigin": "https://you.ctrip.com",
    "origin": "https://you.ctrip.com",
    "priority": "u=1, i",
    "referer": "https://you.ctrip.com/sight/shanghai2.html",
    "sec-ch-ua": "\"Not A(Brand\";v=\"8\", \"Chromium\";v=\"132\", \"Google Chrome\";v=\"132\"",
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": "\"Windows\"",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
    "x-ctx-ubt-pageid": "10650142842",
    "x-ctx-ubt-pvid": "5",
    "x-ctx-ubt-sid": "1",
    "x-ctx-ubt-vid": "1769071777467.23fgm4",
    "x-ctx-wclient-req": "8339d695c90743049ae90d97d28fbc31"
}

cookies = {
    "_ubtstatus": "%7B%22vid%22%3A%221769071777467.23fgm4%22%2C%22sid%22%3A1%2C%22pvid%22%3A1%2C%22pid%22%3A0%7D",
    "_gid": "GA1.2.1401386696.1769071778",
    "_RGUID": "a1e4c215-6592-4cfa-9aa9-2420cd161e0f",
    "_bfaStatusPVSend": "1",
    "_bfaStatus": "send",
    "Hm_lvt_a8d6737197d542432f4ff4abc6e06384": "1769071779",
    "Hm_lpvt_a8d6737197d542432f4ff4abc6e06384": "1769071779",
    "HMACCOUNT": "0DC950B447FD89F4",
    "UBT_VID": "1769071777467.23fgm4",
    "MKT_CKID": "1769071779847.jh8rc.9ccz",
    "GUID": "09031139119390784596",
    "_ga": "GA1.1.1414316783.1769071778",
    "MKT_Pagesource": "PC",
    "_ga_5DVRDQD429": "GS2.1.s1769071777$o1$g1$t1769071795$j42$l0$h1650724153",
    "_ga_B77BES1Z8Z": "GS2.1.s1769071777$o1$g1$t1769071795$j42$l0$h0",
    "_ga_9BZF483VNQ": "GS2.1.s1769071780$o1$g1$t1769071795$j45$l0$h0",
    "nfes_isSupportWebP": "1",
    "_bfa": "1.1769071777467.23fgm4.1.1769071797879.1769071799591.1.5.10650142842",
    "_jzqco": "%7C%7C%7C%7C1769071780037%7C1.1724036744.1769071779849.1769071797494.1769071800064.1769071797494.1769071800064.undefined.0.0.3.3"
}

url = "https://m.ctrip.com/restapi/soa2/18109/json/getAttractionList"
params = {
    "_fxpcqlniredt": "09031139119390784596",
    "x-traceID": "09031139119390784596-1769071881016-8437814"
}


def get_json(k, v, page):
    data = {
        "head": {
            "cid": "09031139119390784596",
            "ctok": "",
            "cver": "1.0",
            "lang": "01",
            "sid": "8888",
            "syscode": "999",
            "auth": "",
            "xsid": "",
            "extension": []
        },
        "scene": "online",
        "districtId": v,
        "index": page,
        "sortType": 1,
        "count": 10,
        "filter": {
            "filterItems": [
                '0'
            ]
        },
        "returnModuleType": "product"
    }
    data = json.dumps(data, separators=(',', ':'))
    response = requests.post(url, headers=headers, cookies=cookies, params=params, data=data)
    return response.json()


def get_data_info(resp, k):
    feeds = resp.get('attractionList', [])

    with open("data.csv", "a", newline='', encoding="utf-8") as csvfile:
        csvwriter = csv.writer(csvfile)
        for feed in feeds:
            card = feed.get("card", {})
            coordinate = card.get("coordinate", {})
            poiId = card.get('poiId', '')
            zoneName = card.get('zoneName', '')
            poiName = card.get('poiName', '')
            commentCount = card.get('commentCount', '')
            commentScore = card.get('commentScore', '')
            isAdvertisement = card.get('isAdvertisement', '')
            isRecommend = card.get('isRecommend', '')
            districtName = card.get('districtName', '')
            coverImageUrl = card.get('coverImageUrl', '')
            distanceStr = card.get('distanceStr', '')
            tagNameList = card.get('tagNameList', [])
            tagNameList = '|'.join(tagNameList) if tagNameList else ''
            detailUrl = card.get('detailUrl', '')
            marketPrice = card.get('marketPrice', '')
            preferentialPrice = card.get('preferentialPrice', '')
            preferentialDesc = card.get('preferentialDesc', '')
            price = card.get('price', '免费')
            priceType = card.get('priceType', '')
            priceTypeDesc = card.get('priceTypeDesc', '')
            isFree = card.get('isFree', '')
            latitude = coordinate.get('latitude', '')
            longitude = coordinate.get('longitude', '')
            heatScore = card.get('heatScore', '')

            # 每条数据单独写入一行
            row = [poiId, poiName, zoneName, commentCount, commentScore, isAdvertisement, isRecommend,
                   districtName, coverImageUrl, distanceStr, tagNameList, detailUrl, marketPrice,
                   preferentialPrice, preferentialDesc, price, priceType, priceTypeDesc, isFree,
                   latitude, longitude, heatScore, k]
            csvwriter.writerow(row)


def write_header():
    """写入表头"""
    with open("data.csv", "w", newline='', encoding="utf-8") as csvfile:
        csvwriter = csv.writer(csvfile)
        header = ['poiId', 'poiName', 'zoneName', 'commentCount', 'commentScore', 'isAdvertisement',
                  'isRecommend', 'districtName', 'coverImageUrl', 'distanceStr', 'tagNameList',
                  'detailUrl', 'marketPrice', 'preferentialPrice', 'preferentialDesc', 'price',
                  'priceType', 'priceTypeDesc', 'isFree', 'latitude', 'longitude', 'heatScore', 'city']
        csvwriter.writerow(header)


if __name__ == '__main__':
    cityDict = {
        "上海": 2,
        # "北京": 1,
        # "广州": 100051,
        # "青岛": 5,
    }

    # 先写入表头
    # write_header()

    for k, v in cityDict.items():
        for page in range(1, 30):
            print(f"正在获取 {k} 第 {page} 页...")
            resp = get_json(k, v, page)
            get_data_info(resp, k)

    print("数据采集完成！")