import requests


message = { "text" : """'file': "306024280_按文本_莞香文化传承与宣传现状_101_101.csv",'rate':0.8,'prompt':筛选掉回答时间小于200s的数据""" }

# Send a POST request to the API

response = requests.post(
    "http://localhost:7777/api",
    json=message
)

print(response.json())

