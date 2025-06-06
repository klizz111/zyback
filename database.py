import pymongo
import toml
from openai import OpenAI

""" config = toml.load("config.toml")

db = pymongo.MongoClient(config["mongodb"]["host"])[config["mongodb"]["user_name"]]
dict = {"name": "test", "age": 19}
db["test"].update_one({"name": "test"}, {"$set": {"age": 19}})

res = db["test"].find_one({"name": "test"})
print(res) """

client = OpenAI(
    api_key="MOONSHOT_API_KEY", # 在这里将 MOONSHOT_API_KEY 替换为你从 Kimi 开放平台申请的 API Key
    base_url="https://api.moonshot.cn/v1",
)

tools = [
	{
		"type": "function", # 约定的字段 type，目前支持 function 作为值
		"function": { # 当 type 为 function 时，使用 function 字段定义具体的函数内容
			"name": "search", # 函数的名称，请使用英文大小写字母、数据加上减号和下划线作为函数名称
			"description": """ 
				通过搜索引擎搜索互联网上的内容。
 
				当你的知识无法回答用户提出的问题，或用户请求你进行联网搜索时，调用此工具。请从与用户的对话中提取用户想要搜索的内容作为 query 参数的值。
				搜索结果包含网站的标题、网站的地址(URL)以及网站简介。
			""", # 函数的介绍，在这里写上函数的具体作用以及使用场景，以便 Kimi 大模型能正确地选择使用哪些函数
			"parameters": { # 使用 parameters 字段来定义函数接收的参数
				"type": "object", # 固定使用 type: object 来使 Kimi 大模型生成一个 JSON Object 参数
				"required": ["query"], # 使用 required 字段告诉 Kimi 大模型哪些参数是必填项
				"properties": { # properties 中是具体的参数定义，你可以定义多个参数
					"query": { # 在这里，key 是参数名称，value 是参数的具体定义
						"type": "string", # 使用 type 定义参数类型
						"description": """
							用户搜索的内容，请从用户的提问或聊天上下文中提取。
						""" # 使用 description 描述参数以便 Kimi 大模型更好地生成参数
					}
				}
			}
		}
	},
]

completion = client.chat.completions.create(
    model="moonshot-v1-8k",
    messages=[
        {"role": "system", "content": "你是 Kimi，由 Moonshot AI 提供的人工智能助手，你更擅长中文和英文的对话。你会为用户提供安全，有帮助，准确的回答。同时，你会拒绝一切涉及恐怖主义，种族歧视，黄色暴力等问题的回答。Moonshot AI 为专有名词，不可翻译成其他语言。"},
        {"role": "user", "content": "请联网搜索 Context Caching，并告诉我它是什么。"} # 在提问中要求 Kimi 大模型联网搜索
    ],
    temperature=0.3,
    tools=tools, # <-- 我们通过 tools 参数，将定义好的 tools 提交给 Kimi 大模型
)
 
print(completion.choices[0].model_dump_json(indent=4))
