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

class TranslationRequest(BaseModel):
    text: str

class ConstitutionRequest(BaseModel):
    text: str

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

@app.post("/api/translation")
async def translate(request: TranslationRequest):
    """翻译接口"""
    try:
        first_messages = [
            {"role": "system", "content": """
            你是一名专业的中医，请根据接下来的病例描述，给出详细的诊断意见以及治疗方案。
            请注意：
            1. 使用中医术语回答。
            2. 包括病因分析、症状描述、诊断结论和具体的治疗方案。
            3. 治疗方案可包括中药处方、中成药处方、针灸建议和其他中医治疗方法。
            4. 请确保回答完整，详细，专业。
            5. 要求使用markdown格式回答,但是不要出现markdown代码块的标识符，如'''markdown'''。
            6. 响应格式请用{"response" : "回复信息"}的json格式回答,但是注意，一定不要添加代码块标识符'''json'''。
            """},
            {"role": "user", "content": request.text}
        ]
        logger.info(f"Calling model API with messages: {first_messages}")
        first_response = await call_model(first_messages)
        first_result = first_response["choices"][0]["message"]["content"]
        # 清理字符串头部的```json\n和尾部的\n```(如果有的话)
        data = first_result.lstrip("```json\n").rstrip("\n```")
        logger.info(f"data: {data}")

        try:
            # 使用更安全的方式解析JSON，处理可能的控制字符
            parsed_data = json.loads(data)
            return parsed_data
        except json.JSONDecodeError as json_error:
            logger.warning(f"Failed to parse JSON directly: {json_error}")
            
            # 尝试清理JSON字符串中可能的控制字符
            import re
            # 移除或替换控制字符
            cleaned_data = re.sub(r'[\x00-\x1F\x7F]', '', data)
            try:
                parsed_data = json.loads(cleaned_data)
                logger.info("Successfully parsed JSON after cleaning control characters")
                return parsed_data
            except json.JSONDecodeError:
                # 如果仍然失败，尝试构建一个新的响应
                logger.warning("Still failed to parse JSON, returning raw response")
                return {"response": data}
                
        # 以下代码可能不需要了，因为我们已经在上面返回了结果
        # 第二次调用：格式化为JSON
        # second_messages = [
        #     {"role": "system", "content": config["prompt"]["prompt_content"]},
        #     {"role": "user", "content": json.dumps(data)}
        # ]
        # second_response = await call_model(second_messages)
        # final_result = second_response["choices"][0]["message"]["content"]

    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON: {e}")
        raise HTTPException(status_code=500, detail=f"JSON解析错误: {e}")
    except Exception as e:
        logger.error(f"Error in translation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api")
async def constitution_analysis(request: TranslationRequest):
    """体质分析接口"""
    try:
        # 判断是否为体质测试数据
        if "体质测试时间" in request.text and "体质症状评分" in request.text:
            # 体质测试专用提示词
            messages = [
                {"role": "system", "content": """
                你是一名专业的中医体质专家，请根据接下来的体质测试数据，给出详细的体质分析报告。

                请按照以下格式进行分析：

                ## 🌟 体质分析结果

                ### 主要体质类型
                根据九种体质分类法（平和质、气虚质、阳虚质、阴虚质、痰湿质、湿热质、血瘀质、气郁质、特禀质），判断用户的主要体质类型。

                ### 📊 体质特征分析
                详细分析用户的体质特点，包括：
                - 主要症状表现
                - 体质偏向程度
                - 可能的健康隐患

                ### 🍃 个性化养生方案

                #### 1. 饮食调理
                - 推荐食物（具体食材和做法）
                - 避免食物
                - 饮食原则

                #### 2. 运动建议
                - 适合的运动类型
                - 运动强度和频率
                - 注意事项

                #### 3. 生活起居
                - 作息建议
                - 情绪调节
                - 环境适应

                #### 4. 中医调理
                - 推荐中药材（日常保健用）
                - 穴位按摩
                - 季节养生要点

                ### 📅 21天养生打卡计划

                制定一个为期21天的具体养生计划，包括：
                - 每日必做项目（如饮食、运动、作息）
                - 每周重点调理项目
                - 阶段性目标

                ### ⚠️ 注意事项
                - 体质调理的注意要点
                - 什么情况下需要就医
                - 长期调理建议

                请确保：
                1. 分析基于中医理论，准确专业
                2. 建议具体可操作，便于执行
                3. 考虑用户的具体情况（年龄、性别、生活习惯等）
                4. 使用温和鼓励的语气
                5. 响应格式用{"response" : "回复信息"}的json格式
                """},
                {"role": "user", "content": request.text}
            ]
        else:
            # 普通中医问诊提示词
            messages = [
                {"role": "system", "content": """
                你是一名专业的中医，请根据接下来的病例描述，给出详细的诊断意见以及治疗方案。
                请注意：
                1. 使用中医术语回答。
                2. 包括病因分析、症状描述、诊断结论和具体的治疗方案。
                3. 治疗方案可包括中药处方、中成药处方、针灸建议和其他中医治疗方法。
                4. 请确保回答完整，详细，专业。
                5. 要求使用markdown格式回答,但是不要出现markdown代码块的标识符，如'''markdown'''。
                6. 响应格式请用{"response" : "回复信息"}的json格式回答,但是注意，一定不要添加代码块标识符'''json'''。
                """},
                {"role": "user", "content": request.text}
            ]

        logger.info(f"Calling model API for constitution/medical analysis")
        response = await call_model(messages)
        result = response["choices"][0]["message"]["content"]
        
        # 清理字符串
        data = result.lstrip("```json\n").rstrip("\n```")
        logger.info(f"data: {data}")

        try:
            parsed_data = json.loads(data)
            return parsed_data
        except json.JSONDecodeError as json_error:
            logger.warning(f"Failed to parse JSON directly: {json_error}")
            
            import re
            cleaned_data = re.sub(r'[\x00-\x1F\x7F]', '', data)
            try:
                parsed_data = json.loads(cleaned_data)
                logger.info("Successfully parsed JSON after cleaning control characters")
                return parsed_data
            except json.JSONDecodeError:
                logger.warning("Still failed to parse JSON, returning raw response")
                return {"response": data}

    except Exception as e:
        logger.error(f"Error in constitution analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host=config["server"]["host"],
        port=config["server"]["port"],
        reload=True
    )