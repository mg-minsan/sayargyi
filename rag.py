from langchain_openai import ChatOpenAI
from langchain_deepseek import ChatDeepSeek
from langchain.agents import create_agent
from langchain_core.messages import AIMessage
from tools import search
import time

MODEL_PRICES = {
    "gpt-5.4-mini": {"input": 0.75, "output": 4.50},
    "gpt-5-nano-2025-08-07": {"input": 0.05, "output": 0.4},
    "deepseek-v4-flash": {"input": 0.22, "output": 0.66},
    "deepseek-v4-pro": {"input": 0.66, "output": 1.98},
}

SYSTEM_PROMPT = """
You are an expert research assistant with access to academic computer science papers.
You're given a question from a researcher or computer science student and your task is to answer it.

If you want to look up information, use the search function. 
Use as many keywords from the user question as possible when making first requests.

Make multiple searches. First perform search, analyze the results 
and then perform more searches. 


RULES:
- Only answer questions about computer science research topics covered in the paper database.
  Off-topic questions (unrelated to CS research) must not be answered.
- Always use the hybrid_search tool to find relevant papers. Never answer from your own knowledge.
- Use as many keywords from the user's question as possible in your first search.
- Perform exactly ONE search tool call at a time.
- Wait for the search result before making another search.
- After receiving a search result, analyze it and decide whether another search is needed.
- Never issue multiple search tool calls in the same response.
- If searches return no results, the question is likely off-topic. Respond:
  "I can only answer questions about computer science research topics in my database."
- Do not fabricate or infer information beyond what the search results contain.
- Do not say follow up questions. As this is not a chatbot, but a Q&A bot. Only answer the question asked.
"""


class RAG:
    def __init__(
        self,
        model: str = "gpt-5.4-mini",
        provider: str = "openai",  # "openai" or "deepseek"
    ):
        self.model = model
        if provider == "deepseek":
            llm = ChatDeepSeek(model=self.model)
        else:
            llm = ChatOpenAI(model=self.model)
        agent = create_agent(
            model=llm,
            tools=[search],
            system_prompt=SYSTEM_PROMPT,
        )
        self.agent = agent
        self.usages = []
        self.last_usage = None
        self.tool_calls = []

    def rag(self, query: str):
        start_time = time.time()
        response = self.agent.invoke({"messages": [("user", query)]})
        response_time = time.time() - start_time

        self.tool_calls = self.extract_tool_calls(response)
        answer = response["messages"][-1].content
        self.last_usage = self._log_responses(
            query, answer, response["messages"], response_time
        )
        self.usages.append(self.last_usage)
        return answer

    def extract_tool_calls(self, response: dict) -> list[dict]:
        tool_calls = []
        for msg in response["messages"]:
            for call in getattr(msg, "tool_calls", []):
                tool_calls.append(
                    {
                        "tool": call["name"],
                        "args": call["args"],
                    }
                )
        return tool_calls

    def _log_responses(self, query, answer, messages, response_time):
        total = {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "llm_calls": 0,
            "cost": 0.0,
            "response_time": response_time,
            "prompt": query,
            "model": self.model,
            "answer": answer,
        }
        for msg in messages:
            if isinstance(msg, AIMessage) and msg.usage_metadata:
                u = msg.usage_metadata
                total["input_tokens"] += u["input_tokens"]
                total["output_tokens"] += u["output_tokens"]
                total["total_tokens"] += u["total_tokens"]
                total["llm_calls"] += 1
                price = next(
                    (
                        p
                        for name, p in MODEL_PRICES.items()
                        if self.model.startswith(name)
                    ),
                    {"input": 0.0, "output": 0.0},
                )
                total["cost"] += (
                    u["input_tokens"] / 1e6 * price["input"]
                    + u["output_tokens"] / 1e6 * price["output"]
                )
        return total

    @property
    def total_cost(self):
        return sum(u["cost"] for u in self.usages)
