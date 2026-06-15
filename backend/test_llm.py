import asyncio
from dotenv import load_dotenv
load_dotenv()

from schemas.remap_schema import BatchRemapResult
from services.AI_extract_service import get_structured_llm
from langchain_core.messages import HumanMessage, SystemMessage

async def main():
    try:
        structured_llm = get_structured_llm(BatchRemapResult)
        res = await structured_llm.ainvoke([
            SystemMessage(content="You are a helpful assistant."),
            HumanMessage(content="Test")
        ])
        print("Success!", res)
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
