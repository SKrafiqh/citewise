"""Run eval/testset.json through the real QA pipeline (EVAL_PLAN §A, EV-1, EV-2, EV-4).

    python -m eval.run_rag_eval --tune-gate        # pick COVERAGE_THRESHOLD on a 70% split, report on 30%
    python -m eval.run_rag_eval                    # retrieval + answer metrics, ablations, RAGAS
    python -m eval.run_rag_eval --no-ragas         # skip the (slow, paid) RAGAS judge
"""
import argparse
import json
from pathlib import Path

from eval.metrics import citation_accuracy, locator_matches
from eval.rag_eval_core import Item, best_threshold, load_testset, refusal_scores, split_for_tuning

HERE = Path(__file__).resolve().parent
TESTSET = HERE / "testset.json"
OUT = HERE / "out"
HIT_K = 5
VARIANTS = [("vector", True), ("hybrid", True), ("hybrid", False)]  # (retrieval mode, claim check)


def as_ref(hit_like) -> dict:
    return {"source_id": hit_like["source_id"], "modality": hit_like["modality"], "locator": hit_like["locator"]}


def hit_at_k(retrieved: list[dict], gold: list[dict], k: int = HIT_K) -> bool:
    return any(locator_matches(as_ref(h), g) for h in retrieved[:k] for g in gold)


def retrieved_refs(unit_ids: list[str]) -> list[dict]:
    from app.db import connect
    from app.qa.retrieve import fetch_hits

    with connect() as conn:
        return [{"source_id": h.source_id, "modality": h.modality, "locator": h.locator, "text": h.text, "figure_desc": h.figure_desc}
                for h in fetch_hits(conn, unit_ids)]


def evaluate_variant(items: list[Item], mode: str, claim_check: bool, ragas: bool) -> dict:
    from app.qa.chat import ask

    answerable = [i for i in items if i.expected == "answer"]
    expected, predicted, hits, cites, figure_ok, rows = [], [], [], [], [], []
    for item in items:
        response = ask(item.question, mode=mode, use_claim_check=claim_check)
        expected.append(item.expected == "decline")
        predicted.append(response["declined"])
        if item.expected != "answer":
            continue
        refs = retrieved_refs(response["retrieved"])
        gold = [g.model_dump() for g in item.gold]
        hits.append(hit_at_k(refs, gold))
        acc = citation_accuracy([as_ref(c) for c in response["citations"]], gold) if not response["declined"] else 0.0
        cites.append(acc)
        if item.needs_figure:
            figure_ok.append(acc > 0)
        if not response["declined"]:
            rows.append({"question": item.question, "answer": " ".join(s["text"] for s in response["sentences"]),
                         "contexts": [f"{r['text']} {r['figure_desc'] or ''}" for r in refs], "reference": item.reference_answer})
    share = lambda xs: sum(xs) / len(xs) if xs else None
    result = {"mode": mode, "claim_check": claim_check, "n_answerable": len(answerable), "n_total": len(items),
              f"hit@{HIT_K}": share(hits), "citation_accuracy": share(cites), "figure_accuracy": share(figure_ok),
              "n_figure": len(figure_ok), "refusal": refusal_scores(expected, predicted), "n_answered_for_ragas": len(rows)}
    if ragas and rows:
        from eval.ragas_adapter import ragas_scores

        result["ragas"] = ragas_scores(rows)
    return result


def tune_gate(items: list[Item], seed: int) -> dict:
    from app.qa.retrieve import retrieve

    sims = [retrieve(i.question, "vector").top_sim for i in items]
    should_decline = [i.expected == "decline" for i in items]
    tune, held = split_for_tuning(len(items), seed)
    tau = best_threshold([sims[i] for i in tune], [should_decline[i] for i in tune])
    held_pred = [sims[i] < tau for i in held]
    return {"threshold": tau, "tuned_on": len(tune), "held_out": len(held),
            "held_out_refusal": refusal_scores([should_decline[i] for i in held], held_pred),
            "note": "set COVERAGE_THRESHOLD to this value; report the held-out numbers, not the tuning ones"}


def fmt(value) -> str:
    return "n/a" if value is None else f"{value:.3f}"


def to_markdown(results: list[dict]) -> str:
    lines = ["| Retrieval | Claim check | n | hit@5 | Citation acc. | Figure acc. (n) | Refusal P | Refusal R |", "|---|---|---|---|---|---|---|---|"]
    for r in results:
        lines.append(f"| {r['mode']} | {'on' if r['claim_check'] else 'off'} | {r['n_total']} | {fmt(r[f'hit@{HIT_K}'])} | {fmt(r['citation_accuracy'])} "
                     f"| {fmt(r['figure_accuracy'])} ({r['n_figure']}) | {fmt(r['refusal']['precision'])} | {fmt(r['refusal']['recall'])} |")
    ragas_rows = [r for r in results if "ragas" in r]
    if ragas_rows:
        names = sorted(ragas_rows[0]["ragas"])
        lines += ["", "| Retrieval | Claim check | " + " | ".join(names) + " |", "|---|---|" + "---|" * len(names)]
        for r in ragas_rows:
            lines.append(f"| {r['mode']} | {'on' if r['claim_check'] else 'off'} | " + " | ".join(fmt(r["ragas"][n]) for n in names) + " |")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="RAG evaluation on the hand-written test set")
    parser.add_argument("--testset", type=Path, default=TESTSET)
    parser.add_argument("--tune-gate", action="store_true")
    parser.add_argument("--no-ragas", action="store_true")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--allow-unchecked", action="store_true", help="debug only: include items not marked author_checked")
    args = parser.parse_args()
    items = load_testset(args.testset, require_checked=not args.allow_unchecked)
    if not items:
        raise SystemExit("eval/testset.json is empty; write items per docs/TESTSET_FORMAT.md first")
    OUT.mkdir(exist_ok=True)
    if args.tune_gate:
        print(json.dumps(tune_gate(items, args.seed), indent=2))
        return
    results = [evaluate_variant(items, mode, claim, not args.no_ragas) for mode, claim in VARIANTS]
    (OUT / "rag_eval.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    table = to_markdown(results)
    (OUT / "rag_eval.md").write_text(f"n = {len(items)} items. Judge: OpenRouter model; generator: Gemini.\n\n{table}\n", encoding="utf-8")
    print(table)


if __name__ == "__main__":
    main()
