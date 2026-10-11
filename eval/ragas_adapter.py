"""RAGAS wired to the project's cached LLM layer, so judge calls obey CLAUDE.md rule 2.

Judge = the OpenRouter model (a different provider than the Gemini generator); embeddings = Gemini.
Written against the ragas 0.2.x interface (pinned in requirements-eval.txt).
"""
import asyncio

from langchain_core.outputs import Generation, LLMResult
from ragas import EvaluationDataset, evaluate
from ragas.embeddings.base import BaseRagasEmbeddings
from ragas.llms.base import BaseRagasLLM
from ragas.metrics import Faithfulness, LLMContextPrecisionWithReference, LLMContextRecall, ResponseRelevancy
from ragas.run_config import RunConfig

from app.llm import embed, verify_chat


class CachedJudge(BaseRagasLLM):
    def generate_text(self, prompt, n=1, temperature=1e-8, stop=None, callbacks=None) -> LLMResult:
        text = verify_chat(prompt.to_string(), temperature=0.0)  # cached and deterministic: n copies
        return LLMResult(generations=[[Generation(text=text)] * n])

    async def agenerate_text(self, prompt, n=1, temperature=1e-8, stop=None, callbacks=None) -> LLMResult:
        return await asyncio.to_thread(self.generate_text, prompt, n, temperature, stop, callbacks)

    def is_finished(self, response: LLMResult) -> bool:
        return True


class CachedEmbeddings(BaseRagasEmbeddings):
    def embed_query(self, text: str) -> list[float]:
        return embed([text], task_type="RETRIEVAL_QUERY")[0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return embed(texts)

    async def aembed_query(self, text: str) -> list[float]:
        return await asyncio.to_thread(self.embed_query, text)

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        return await asyncio.to_thread(self.embed_documents, texts)


def ragas_scores(rows: list[dict]) -> dict[str, float]:
    """rows: {question, answer, contexts, reference}. Returns mean score per RAGAS metric."""
    dataset = EvaluationDataset.from_list([
        {"user_input": r["question"], "response": r["answer"], "retrieved_contexts": r["contexts"], "reference": r["reference"]}
        for r in rows
    ])
    judge, embeddings = CachedJudge(), CachedEmbeddings()
    result = evaluate(
        dataset,
        metrics=[Faithfulness(), ResponseRelevancy(), LLMContextPrecisionWithReference(), LLMContextRecall()],
        llm=judge, embeddings=embeddings, run_config=RunConfig(max_workers=2, timeout=120), show_progress=False,
    )
    frame = result.to_pandas()
    return {c: float(frame[c].mean()) for c in frame.columns if c not in {"user_input", "response", "retrieved_contexts", "reference"}}
