"""Simulated-student evaluation: adaptive policy vs random, same question bank (EVAL_PLAN §C, EV-3).

    python -m eval.simulate --export-bank          # snapshot concepts + questions from the database
    python -m eval.simulate --seeds 10             # run, write CSV / charts / markdown to eval/out/

The learner model is the reserved `app.learner.bkt.update`, the duplicate check is the reserved
`app.assess.dedup.is_duplicate`; both can be injected so the harness is testable without them.
"""
import argparse
import csv
import json
import math
import random
import statistics
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.learner import policy, review

OUT = Path(__file__).resolve().parent / "out"
BANK_PATH = Path(__file__).resolve().parent / "bank.json"
SESSIONS, PER_SESSION = 8, 10
MASTERY_GOAL = 0.8
S_TRUE = 0.1  # slip probability of the simulated student


@dataclass(frozen=True)
class Profile:
    name: str
    learn: float
    forget: float  # per-day chance a known concept is forgotten


PROFILES = [
    Profile("strong", 0.15, 0.02), Profile("weak_foundations", 0.15, 0.02), Profile("uneven", 0.15, 0.02),
    Profile("fast_learner", 0.30, 0.02), Profile("forgetful", 0.15, 0.15),
]


def initial_knowledge(profile: str, bank: dict, rng: random.Random) -> dict[str, bool]:
    concepts = bank["concepts"]
    if profile == "strong":
        return {c: rng.random() < 0.8 for c in concepts}
    if profile == "weak_foundations":
        foundations = {p for deps in bank["prereqs"].values() for p in deps}
        return {c: c not in foundations and rng.random() < 0.3 for c in concepts}
    if profile == "uneven":
        topics = sorted(set(bank["topic_of"].values()))
        known_topics = set(rng.sample(topics, max(1, len(topics) // 2)))
        return {c: bank["topic_of"][c] in known_topics for c in concepts}
    if profile == "fast_learner":
        return {c: rng.random() < 0.3 for c in concepts}
    return {c: rng.random() < 0.5 for c in concepts}  # forgetful


def known_share(known: dict[str, bool]) -> float:
    return sum(known.values()) / len(known)


def mean_abs_error(p: dict[str, float], known: dict[str, bool]) -> float:
    return sum(abs(p[c] - float(known[c])) for c in known) / len(known)


def choose(policy_name: str, bank: dict, p: dict, due: set, seen: set[str], rng: random.Random) -> dict | None:
    open_questions = [q for q in bank["questions"] if q["id"] not in seen]
    if not open_questions:
        return None
    if policy_name == "random":
        return rng.choice(open_questions)
    by_concept: dict[str, list[dict]] = {}
    for q in open_questions:
        by_concept.setdefault(q["concept_id"], []).append(q)
    concept = policy.pick_next(sorted(by_concept), p, due, bank["prereqs"])
    target = policy.target_difficulty(p.get(concept, policy.DEFAULT_P0))
    return min(by_concept[concept], key=lambda q: (abs(q["difficulty"] - target), q["id"]))


def run_student(profile: Profile, seed: int, policy_name: str, bank: dict, update_fn: Callable, is_duplicate: Callable,
                sessions: int = SESSIONS, per_session: int = PER_SESSION) -> dict:
    state_rng = random.Random(f"{profile.name}-{seed}-state")   # identical hidden truth for both policies
    answer_rng = random.Random(f"{profile.name}-{seed}-answers")
    pick_rng = random.Random(f"{profile.name}-{seed}-{policy_name}")
    known = initial_knowledge(profile.name, bank, state_rng)
    p = {c: policy.DEFAULT_P0 for c in known}
    stability: dict[str, float] = {}
    last_day: dict[str, int] = {}
    seen: set[str] = set()
    served: list[list[float]] = []
    observations: dict[str, list[tuple[bool, float]]] = {}
    repeats = total = 0
    start_share = known_share(known)
    rows = []
    for session in range(1, sessions + 1):
        for c in known:  # a day passes between sessions
            if known[c] and answer_rng.random() < profile.forget:
                known[c] = False
        due = {c for c in known if c in last_day and review.is_due(p[c], stability.get(c), session - last_day[c])}
        for _ in range(per_session):
            q = choose(policy_name, bank, p, due, seen, pick_rng)
            if q is None:
                break
            seen.add(q["id"])
            c, guess = q["concept_id"], policy.bkt_params_for(q["qtype"], q["n_options"]).p_guess
            correct = answer_rng.random() < ((1 - S_TRUE) if known[c] else guess)
            total += 1
            repeats += bool(is_duplicate(q["embedding"], served))
            served.append(q["embedding"])
            observations.setdefault(c, []).append((correct, guess))
            p[c] = update_fn(p[c], correct, policy.bkt_params_for(q["qtype"], q["n_options"]), 1.0)
            stability[c] = review.next_stability(stability.get(c), correct, p[c])
            last_day[c] = session
            if not known[c] and answer_rng.random() < profile.learn:
                known[c] = True
        rows.append({"session": session, "known_share": known_share(known), "mae": mean_abs_error(p, known)})
    reached = next((r["session"] for r in rows if r["known_share"] >= MASTERY_GOAL), None)
    return {"rows": rows, "gain": known_share(known) - start_share, "repetition": repeats / max(1, total),
            "sessions_to_goal": reached, "observations": observations}


def fit_bkt(sequences: list[list[tuple[bool, float]]], p0: float = policy.DEFAULT_P0) -> tuple[float, float]:
    """Grid-search the (T, S) maximising the BKT likelihood of simulated answer sequences."""
    def loglik(t: float, s: float) -> float:
        total = 0.0
        for seq in sequences:
            p = p0
            for correct, g in seq:
                p_correct = p * (1 - s) + (1 - p) * g
                total += math.log(max(1e-12, p_correct if correct else 1 - p_correct))
                posterior = p * (1 - s) / p_correct if correct else p * s / (1 - p_correct)
                p = posterior + (1 - posterior) * t
        return total

    grid_t = [i / 100 for i in range(2, 42, 2)]
    grid_s = [i / 100 for i in range(1, 31, 1)]
    return max(((t, s) for t in grid_t for s in grid_s), key=lambda ts: loglik(*ts))


def mean_std(values: list[float]) -> str:
    return f"{statistics.mean(values):.3f} ± {statistics.pstdev(values):.3f}"


def run_all(bank: dict, seeds: int, update_fn: Callable, is_duplicate: Callable, sessions: int = SESSIONS, per_session: int = PER_SESSION) -> dict:
    results: dict[tuple[str, str], list[dict]] = {}
    for profile in PROFILES:
        for policy_name in ("adaptive", "random"):
            results[(profile.name, policy_name)] = [
                run_student(profile, seed, policy_name, bank, update_fn, is_duplicate, sessions, per_session) for seed in range(seeds)
            ]
    return results


def summary_table(results: dict, seeds: int) -> str:
    lines = [f"n = {seeds} seeds per profile and policy.", "",
             "| Profile | Policy | Mastery gain | Final MAE | Repetition | Sessions to 80% known |", "|---|---|---|---|---|---|"]
    for (profile, policy_name), runs in results.items():
        reached = [r["sessions_to_goal"] for r in runs if r["sessions_to_goal"]]
        lines.append(
            f"| {profile} | {policy_name} | {mean_std([r['gain'] for r in runs])} | {mean_std([r['rows'][-1]['mae'] for r in runs])} "
            f"| {mean_std([r['repetition'] for r in runs])} | {len(reached)}/{len(runs)} reached"
            + (f", median {statistics.median(reached)}" if reached else "") + " |"
        )
    return "\n".join(lines)


def write_outputs(results: dict, seeds: int, out: Path) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    with (out / "simulation.csv").open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["profile", "policy", "seed", "session", "known_share", "mae"])
        for (profile, policy_name), runs in results.items():
            for seed, run in enumerate(runs):
                writer.writerows([profile, policy_name, seed, r["session"], r["known_share"], r["mae"]] for r in run["rows"])
    sequences = [seq for runs in results.values() for run in runs for seq in run["observations"].values()]
    t, s = fit_bkt(sequences)
    report = summary_table(results, seeds) + f"\n\nBKT parameters fitted on the simulated answers (grid search): T = {t:.2f}, S = {s:.2f} "
    report += f"(simulated truth: T = 0.15 / 0.30 by profile, S = {S_TRUE})."
    (out / "simulation.md").write_text(report + "\n", encoding="utf-8")
    plot(results, out)
    return out / "simulation.md"


def plot(results: dict, out: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    def per_session(metric: str):
        curves: dict[str, list[list[float]]] = {}
        for (_, policy_name), runs in results.items():
            for run in runs:
                curves.setdefault(policy_name, []).append([r[metric] for r in run["rows"]])
        return {k: [statistics.mean(col) for col in zip(*v)] for k, v in curves.items()}

    for metric, title, name in (("known_share", "True share of concepts known", "mastery_gain"), ("mae", "|BKT estimate − truth|", "bkt_error")):
        fig, ax = plt.subplots(figsize=(6, 3.6))
        for policy_name, ys in per_session(metric).items():
            ax.plot(range(1, len(ys) + 1), ys, marker="o", label=policy_name)
        ax.set(xlabel="session", ylabel=title, title=f"{title} (mean over profiles and seeds)")
        ax.legend()
        fig.tight_layout()
        fig.savefig(out / f"{name}.png", dpi=140)
        plt.close(fig)
    fig, ax = plt.subplots(figsize=(6, 3.6))
    labels = [p.name for p in PROFILES]
    for i, policy_name in enumerate(("adaptive", "random")):
        ax.bar([x + i * 0.4 for x in range(len(labels))], [statistics.mean(r["repetition"] for r in results[(l, policy_name)]) for l in labels], 0.4, label=policy_name)
    ax.set_xticks([x + 0.2 for x in range(len(labels))], labels, rotation=20)
    ax.set(ylabel="near-duplicate share", title="Repetition rate")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out / "repetition.png", dpi=140)
    plt.close(fig)


def export_bank(path: Path) -> int:
    from app.db import as_floats, connect
    from app.kb.graph import load_graph

    graph = load_graph()
    with connect() as conn:
        rows = conn.execute("select id, concept_id, qtype, difficulty, options, embedding from questions where verified and embedding is not null").fetchall()
    questions = [{"id": r["id"], "concept_id": r["concept_id"], "qtype": r["qtype"], "difficulty": r["difficulty"],
                  "n_options": len(r["options"]) if r["options"] else 4, "embedding": as_floats(r["embedding"])} for r in rows]
    bank = {"concepts": sorted(graph.concepts), "prereqs": graph.prereqs,
            "topic_of": {c: v["topic_id"] for c, v in graph.concepts.items()}, "questions": questions}
    path.write_text(json.dumps(bank), encoding="utf-8")
    return len(questions)


def main() -> None:
    parser = argparse.ArgumentParser(description="Adaptive vs random simulated-student evaluation")
    parser.add_argument("--bank", type=Path, default=BANK_PATH)
    parser.add_argument("--export-bank", action="store_true")
    parser.add_argument("--seeds", type=int, default=10)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    if args.export_bank:
        print(f"exported {export_bank(args.bank)} questions to {args.bank}")
        return
    from app.assess.dedup import is_duplicate
    from app.config import get_settings
    from app.learner.bkt import update

    threshold = get_settings().dedup_threshold
    bank = json.loads(args.bank.read_text(encoding="utf-8"))
    results = run_all(bank, args.seeds, update, lambda new, seen: is_duplicate(new, seen, threshold))
    print(write_outputs(results, args.seeds, args.out).read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
