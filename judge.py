import json

from pydantic import BaseModel
from typing import Literal
from openai import OpenAI
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI


class RelevanceVerdict(BaseModel):
    relevance: Literal["NON_RELEVANT", "RELEVANT"]
    explanation: str

judge_instructions = """
You are an expert evaluator for a RAG system.
Analyze the relevance of the generated answer to the given question.

Classify the answer as:
- RELEVANT: the answer addresses the question
- NON_RELEVANT: the answer does not address the question

If the answer only partially addresses the question, judge it by whether a
researcher would consider their question answered: if the key point is covered,
choose RELEVANT; otherwise choose NON_RELEVANT.
""".strip()

judge_prompt = """
Question: {question}
Generated Answer: {answer}
""".strip()


def evaluate_relevance(question, answer):
    llm = ChatOpenAI(model="gpt-5.4-mini")
    structured_llm = llm.with_structured_output(RelevanceVerdict, include_raw=True)

    prompt = judge_prompt.format(
        question=question,
        answer=answer
    )

    response = structured_llm.invoke(
        [
            ("system", judge_instructions),
            ("user", prompt)
        ],
    );
    relevance_score = {
            "RELEVANT": 1,
            "NON_RELEVANT": 0,
    }

    answer = response["parsed"]
    relevance = answer.relevance
    return relevance, relevance_score[relevance], answer.explanation