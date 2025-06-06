from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from loguru import logger
import httpx
import toml
import os
from dotenv import load_dotenv
import asyncio  
import json
from time import sleep

# 加载环境变量
load_dotenv()
api_key = os.getenv("API_KEY")
print(api_key)
# 加载配置文件
config = toml.load("config.toml")

# 配置日志
logger.add(
    "logs/app.log",
    rotation=config["log"]["rotation"],
    level=config["log"]["level"]
)

app = FastAPI()

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class DatabaseRequest(BaseModel):
    text: str

"""调用模型API，支持重试"""
async def call_model(messages, retry_count=2):
    """调用模型API，支持重试"""

    if not api_key:
        raise HTTPException(status_code=500, detail="API key not found")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": config["model"]["name"],
        "messages": messages,
        "temperature": config["model"]["temperature"]
    }

    # 获取API URL，确保去除可能的尾部空格
    api_url = config["model"]["url"].strip()
    logger.info(f"API URL: {api_url}")

    for attempt in range(retry_count + 1):
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                logger.info(f"Attempt {attempt+1}/{retry_count+1} - sending request to model API: {api_url}")
                logger.info(f"using model: {config['model']['name']}")
                
                # 先尝试ping域名，检查连接性
                try:
                    await client.get(f"https://{api_url.split('://')[1].split('/')[0]}", timeout=5.0)
                except Exception as ping_error:
                    logger.warning(f"API域名连接测试失败: {str(ping_error)}")
                
                response = await client.post(
                    api_url,
                    headers=headers,
                    json=data,
                    timeout=60.0
                )
                
                response.raise_for_status()
                return response.json()
            except httpx.ConnectError as e:
                logger.error(f"连接错误 (尝试 {attempt+1}/{retry_count+1}): {str(e)}")
                if attempt < retry_count:
                    wait_time = 2 ** attempt  # 指数退避
                    logger.info(f"等待 {wait_time} 秒后重试...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error("所有重试尝试均失败")
                    raise HTTPException(
                        status_code=503, 
                        detail=f"无法连接到API服务器: {str(e)}. 请检查网络连接和API配置。"
                    )
            except httpx.HTTPError as e:
                logger.error(f"HTTP错误: {str(e)}")
                raise HTTPException(status_code=500, detail=f"API请求错误: {str(e)}")
            except Exception as e:
                logger.error(f"调用API时发生错误: {str(e)}")
                raise HTTPException(status_code=500, detail=f"模型API调用错误: {str(e)}")

@app.get("/")
async def root():
    return {"message": "request received"}

"""后端接口"""
@app.post("/api")
async def database_ai(request: DatabaseRequest):
    logger.info(f"Received request: {request.text}")
    logger.info(f"Sending request to \033[31mdeepseek-reasoning\033[0m model")
    sleep(5)
    logger.info(f"Resolving data······")
    sleep(10.5)
    logger.info(f"Data resolved")
    return True

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "fake:app",
        host=config["server"]["host"],
        port=config["server"]["port"],
        reload=True
    )