import hashlib
import requests
def baidu_translate(query, from_lang='zh', to_lang='en'):
    from random import randint
    if len(query)>=6000:
        return "翻译失败：字符数量超出6000"

    
    # API基本信息
    app_id = '20241112002200406'
    secret_key = 'ACeoAJRRtmVlpVegwIJ6'
    # 请求URL
    url = "https://fanyi-api.baidu.com/api/trans/vip/translate"
    
    # 生成salt和签名
    salt = str(randint(32768, 65536))
    sign = hashlib.md5((app_id + query + salt + secret_key).encode()).hexdigest()
    
    # 请求参数
    params = {
        'q': query,
        'from': from_lang,
        'to': to_lang,
        'appid': app_id,
        'salt': salt,
        'sign': sign
    }
    
    # 发起请求
    response = requests.get(url, params=params)
    
    # 解析返回的JSON数据
    if response.status_code == 200:
        result = response.json()
        if "trans_result" in result:
            # 返回翻译结果
            res = ''
            for item in result['trans_result']:
                res += item["dst"]
            return res
        else:
            return "翻译失败，原因：" + result.get("error_msg", "未知错误")
    else:
        return f"请求失败，状态码：{response.status_code}"