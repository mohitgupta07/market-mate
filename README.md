# Architecture:

- Used fastapi as backend server, react for frontend, litellm for llm gateway/proxy/rate-limiter.
- used gemini api for testing (best for free tiered) as well it supports tool calling.
- used fastapi-user for authentication (supports sso/oauth as well)

Backend:
- uses fastapi, fastapi-user for auth
- used sqlalchemy to the db crud. For testing, it creates a local sqlite db.
- used litellm proxy for handling the rate limiter but I couldn't completely explore how to complete the implementation.
- used langgraph for Chain of thoughts, funcation/tool calling. Made everything async for better performance. We can do streaming but for now preferred till async part. 
[System prompt -> summary (if any) -> last k messages -> user query]  is the order message it would look like
- COT has conditional edge to tool_node that will trigger the function call as a response/ask from the llm. Once done, COT would go for another hop and see if anything more is required. Once no more calls are required, summarizer node would be called to return the final output.

Frontend:
- used gemini to create the UI with the given backend endpoints, it's not furnished but works fine.

LLM Gateway:
- used LiteLLM as a gateway for doing rate limiting(not functional yet), letting litellm internally handle the LLM calls and other api secrets internally making system loosely coupled.

# LLM used:
For getting the gemini key: https://aistudio.google.com/apikey (this repo has used gemini api)

# To run the llm proxy:

litellm --config litellm_configs/proxy_config.yaml 


# for running the server: 

d:/localLLM/market-mate/.venv/Scripts/python.exe d:/localLLM/market-mate/src/main.py


# for running the UI:
 
cd market-mate_ui && npm run dev