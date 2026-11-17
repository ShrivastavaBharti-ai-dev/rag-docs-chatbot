"""Compare the naive baseline with the optimised setup on 30 labelled questions.

    python eval/run_eval.py                  # full run (retrieval + answers)
    python eval/run_eval.py --retrieval-only # embeddings only, no chat calls
    python eval/run_eval.py --offline        # no API key needed (plumbing check only)

Writes eval/results.md and eval/results.json. A live (Gemini) full run also
updates the results table in README.md.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from docanswer.engine import BASELINE, OPTIMIZED, RagEngine  # noqa: E402
from docanswer.evaluation import evaluate, load_questions, summarise  # noqa: E402
from docanswer.loaders import load_folder  # noqa: E402
from docanswer.providers import OfflineAnswerModel, OfflineEmbedder, make_providers  # noqa: E402

METRICS = [
    ("retrieval_hit_rate", "Right passage retrieved (%)", True),
    ("mrr", "Mean reciprocal rank", True),
    ("answer_accuracy", "Correct answers (%)", True),
    ("correct_citation_rate", "Cited the right page/section (%)", True),
    ("wrongly_refused", "Refused an answerable question (%)", False),
    ("refused_when_should", "Refused when the answer isn't there (%)", True),
]
README_START, README_END = "<!-- RESULTS:START -->", "<!-- RESULTS:END -->"


def describe(config) -> str:
    chunks = (f"sentence-aware {config.chunk_size}-char chunks, {config.chunk_overlap}-sentence overlap"
              if config.chunking == "sentence" else f"fixed {config.chunk_size}-char chunks, no overlap")
    headers = "document title + page added to each chunk" if config.contextual_headers else "raw chunks"
    search = {"hybrid": "hybrid search (meaning + keywords, fused with RRF)",
              "dense": "embedding search only", "bm25": "keyword search only"}[config.retrieval]
    return f"{chunks}; {headers}; {search}; top {config.top_k} passages"


def table(base: dict, best: dict) -> str:
    lines = ["| Metric | Baseline | Optimised |", "|---|---:|---:|"]
    for key, label, higher_is_better in METRICS:
        if key not in base:
            continue
        a, b = base[key], best[key]
        better = (b > a) if higher_is_better else (b < a)
        lines.append(f"| {label} | {a} | {'**' + str(b) + '**' if better else b} |")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--retrieval-only", action="store_true", help="skip answer generation (no chat calls)")
    parser.add_argument("--offline", action="store_true", help="use offline models (no API key needed)")
    parser.add_argument("--pause", type=float, default=None,
                        help="seconds between chat calls (default 4 when live, to respect free-tier limits)")
    parser.add_argument("--no-readme", action="store_true", help="don't update README.md")
    args = parser.parse_args()

    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except ImportError:
        pass

    if args.offline:
        embedder, model, live = OfflineEmbedder(), OfflineAnswerModel(), False
    else:
        embedder, model, live = make_providers()
        if not live:
            print("No GOOGLE_API_KEY found, using offline models. Numbers are a plumbing check only.\n")
    pause = args.pause if args.pause is not None else (4.0 if live else 0.0)

    pages = load_folder(ROOT / "sample_docs")
    questions = load_questions(ROOT / "eval" / "questions.jsonl")
    answer = not args.retrieval_only

    results = {}
    for label, config in (("baseline", BASELINE), ("optimised", OPTIMIZED)):
        engine = RagEngine(embedder, model, config, business="Saffron & Thread",
                           cache_path=ROOT / ".cache" / "embeddings.json").build(pages)
        print(f"Running {label}: {len(engine.chunks)} chunks, {len(questions)} questions…", flush=True)
        rows = evaluate(engine, questions, answer=answer, pause_seconds=pause if answer else 0.0)
        results[label] = {"config": describe(config), "summary": summarise(rows), "rows": [asdict(r) for r in rows]}

    base, best = results["baseline"]["summary"], results["optimised"]["summary"]
    models = (f"Gemini `{model.model}` (answers) + `{embedder.model}` (embeddings)"
              if live else "offline word-overlap stand-ins (plumbing check, not real quality)")
    report = "\n".join([
        f"Measured on {date.today():%d %b %Y} with {models}, on {base['questions']} questions "
        f"({sum(q.answerable for q in questions)} answerable from the documents, "
        f"{sum(not q.answerable for q in questions)} not).",
        "",
        table(base, best),
        "",
        f"- **Baseline:** {results['baseline']['config']}.",
        f"- **Optimised:** {results['optimised']['config']}; answers without a valid citation are refused.",
    ])

    failures = [r for r in results["optimised"]["rows"]
                if (r["answerable"] and answer and not r["answered_correctly"])
                or (not r["answerable"] and answer and not r["refused"])
                or (r["answerable"] and not r["hit"])]
    detail = ["", "## Questions the optimised setup still gets wrong", ""]
    by_id = {q.id: q for q in questions}
    detail += [f"- `{r['id']}` {by_id[r['id']].question} → {r['answer'] or '(retrieval miss)'}" for r in failures] or ["- None."]

    (ROOT / "eval" / "results.md").write_text("# Evaluation results\n\n" + report + "\n" + "\n".join(detail) + "\n",
                                               encoding="utf-8")
    (ROOT / "eval" / "results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\n" + report + "\n\nSaved eval/results.md and eval/results.json")

    readme = ROOT / "README.md"
    if live and answer and not args.no_readme and readme.exists():
        text = readme.read_text(encoding="utf-8")
        if README_START in text and README_END in text:
            head, rest = text.split(README_START, 1)
            _, tail = rest.split(README_END, 1)
            readme.write_text(f"{head}{README_START}\n{report}\n{README_END}{tail}", encoding="utf-8")
            print("Updated the results table in README.md")


if __name__ == "__main__":
    main()
