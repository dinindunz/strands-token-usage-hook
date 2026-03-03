import os
from dotenv import load_dotenv
from strands import Agent
from strands.models.bedrock import BedrockModel, CacheConfig
from strands_tools import shell, editor
from tools import calculator, temperature_converter
from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn
from hooks.token_usage_tracker import TokenUsageTracker


app = FastAPI()


SYSTEM_PROMPT = """
You are a helpful assistant. Always use the available tools to accomplish tasks:
- Use shell tools to execute commands and navigate the system
- Use editor tools to read, write, and modify files
- Use calculator for mathematical operations
- Use temperature_converter for temperature conversions
"""

MODEL_ID = "au.anthropic.claude-sonnet-4-5-20250929-v1:0"

agent = Agent(
    model=BedrockModel(
        model_id=MODEL_ID,
        cache_config=CacheConfig(strategy="auto")
    ),
    system_prompt=SYSTEM_PROMPT,
    hooks=[TokenUsageTracker(model_id=MODEL_ID)],
    tools=[calculator, temperature_converter, shell, editor],
)


class InvokeRequest(BaseModel):
    prompt: str


@app.post("/invoke")
async def invoke_agent(request: InvokeRequest):
    """Invoke the agent with a prompt"""
    try:
        result = agent(request.prompt)
        message_text = result.message.get("content", [{}])[0].get(
            "text", str(result.message)
        )

        response_data = {"result": message_text}

        return response_data
    except Exception as e:
        return {"error": str(e)}


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    port = int(os.getenv("AGENT_PORT", 8888))
    print(f"Starting a FastAPI agent server on 0.0.0.0:{port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)
