# Run:  python3 analysis.py
#
# Re-scores model-a vs model-b. Standard library only, deterministic (seeded bootstrap).
# Every number in writeup.md and answers.txt is printed by this script.
#
# Steps:
#   1. Recompute the true answer of every question from its text -> find wrong key rows.
#   2. Find questions asked twice under different IDs.
#   3. Pull the final number out of each response (model-b wraps answers in prose/markdown/commas).
#   4. Score: original method, then each fix applied one at a time.
#   5. Ask whether the gap is real: per-question paired comparison, sign test, bootstrap CI.
#   6. Look at how each model fails (consistent vs random), and the confound in the settings.

import csv
import random
import re
from collections import Counter, defaultdict
from math import comb

MODELS = ["model-a", "model-b"]
RUNS = ["1", "2", "3"]

OPS = {"+": lambda a, b: a + b, "-": lambda a, b: a - b, "×": lambda a, b: a * b}
QUESTION_RE = re.compile(r"^What is (\d+) ([+\-×]) (\d+)\?$")


def read_csv(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


questions = {r["question_id"]: r["question"] for r in read_csv("questions.csv")}
key = {r["question_id"]: r["expected"] for r in read_csv("answer_key.csv")}
results = read_csv("results.csv")


def parse_question(text):
    m = QUESTION_RE.match(text)
    if not m:
        raise ValueError(f"unrecognised question format: {text!r}")
    return int(m[1]), m[2], int(m[3])


# ---------------------------------------------------------------- 1. answer key
truth = {}
for qid, text in questions.items():
    a, op, b = parse_question(text)
    truth[qid] = OPS[op](a, b)

wrong_key = sorted(q for q in questions if str(truth[q]) != key[q].strip())
print("== 1. Answer key vs arithmetic")
for q in wrong_key:
    print(f"   {q}: {questions[q]!r:32} key={key[q]:>6}  correct={truth[q]}")

# ---------------------------------------------------------------- 2. duplicates
# Two questions are the same if they have the same operation and operands.
# + and × are commutative, so "47 × 49" and "49 × 47" would also count as the same.
def canonical(text):
    a, op, b = parse_question(text)
    return (op, min(a, b), max(a, b)) if op in "+×" else (op, a, b)

groups = defaultdict(list)
for qid in sorted(questions):
    groups[canonical(questions[qid])].append(qid)
dup_groups = [g for g in groups.values() if len(g) > 1]
# Keep the first-listed ID of each group; the later IDs are the duplicates.
duplicate_ids = sorted(q for g in dup_groups for q in g[1:])
unique_ids = sorted(g[0] for g in groups.values())
print("\n== 2. Same question under two IDs")
for g in dup_groups:
    print(f"   {' = '.join(g)}: {questions[g[0]]!r}")
print(f"   {len(questions)} IDs -> {len(unique_ids)} distinct questions")
print(f"   duplicate IDs (later copy): {','.join(duplicate_ids)}")
print(f"   wrong key IDs: {','.join(wrong_key)}")


# ---------------------------------------------------------------- 3. response parsing
# Take the LAST integer in the response, after removing thousands separators.
# Last, not first: "98 × 91 = 8198" must give 8198, not 98.
def extract_answer(response):
    text = re.sub(r"(?<=\d),(?=\d{3}\b)", "", response)  # "10,615" -> "10615"
    numbers = re.findall(r"-?\d+", text)
    return int(numbers[-1]) if numbers else None


# Label each response by its shape, so every format is seen and checked, not assumed.
def response_style(response):
    s = response.strip()
    if re.fullmatch(r"-?\d+", s):
        return "bare integer"
    if re.fullmatch(r"\*\*-?\d+\*\*", s):
        return "**bold**"
    if re.fullmatch(r"-?\d{1,3}(,\d{3})+", s):
        return "thousands comma"
    if "=" in s:
        return "'a op b = c'"
    if s.startswith("Sure!"):
        return "'Sure! ... equals c.'"
    if s.startswith("The answer is"):
        return "'The answer is c.'"
    return "OTHER"


for r in results:
    r["answer"] = extract_answer(r["response"])
    r["style"] = response_style(r["response"])

print("\n== 3. Response formats (168 rows per model)")
for m in MODELS:
    styles = Counter(r["style"] for r in results if r["model"] == m)
    print(f"   {m}: " + ", ".join(f"{k} {v}" for k, v in styles.most_common()))

print("   one example of each format -> extracted number:")
seen = set()
for r in results:
    if r["style"] not in seen:
        seen.add(r["style"])
        print(f"     {r['style']:24} {r['response']!r:38} -> {r['answer']}")

unparsed = [r for r in results if r["answer"] is None]
other = [r for r in results if r["style"] == "OTHER"]
print(f"   responses with no number: {len(unparsed)}; unrecognised formats: {len(other)}")


# ---------------------------------------------------------------- 4. scoring
def accuracy(model, ids, parse, expected):
    rows = [r for r in results if r["model"] == model and r["question_id"] in ids]
    if parse:
        hits = sum(r["answer"] == int(expected[r["question_id"]]) for r in rows)
    else:  # exactly what score.py does
        hits = sum(r["response"].strip() == str(expected[r["question_id"]]) for r in rows)
    return hits, len(rows)


all_ids = set(questions)
steps = [
    ("original score.py (exact string, given key, 56 IDs)", all_ids, False, key),
    ("+ extract final number from response",                  all_ids, True,  key),
    ("+ correct the 3 wrong key rows",                        all_ids, True,  truth),
    ("+ count each distinct question once (50)",              set(unique_ids), True, truth),
]
print("\n== 4. Accuracy, one fix at a time (runs pooled)")
for label, ids, parse, expected in steps:
    cells = []
    for m in MODELS:
        h, n = accuracy(m, ids, parse, expected)
        cells.append(f"{m} {100 * h / n:5.1f}% ({h}/{n})")
    print(f"   {label:52} " + "   ".join(cells))

final = {m: accuracy(m, set(unique_ids), True, truth) for m in MODELS}
print("   FINAL: " + ", ".join(f"{m} {100 * h / n:.1f}%" for m, (h, n) in final.items()))

print("   per run (out of 50):")
for m in MODELS:
    per_run = [sum(r["answer"] == truth[r["question_id"]] for r in results
                   if r["model"] == m and r["run"] == run and r["question_id"] in unique_ids)
               for run in RUNS]
    print(f"     {m}: {per_run}")


# ---------------------------------------------------------------- 5. is the gap real?
# The 3 runs are NOT 3x more data: model-a gives the identical answer every run (temp 0),
# so the unit of evidence is the question (n = 50), and runs are averaged within a question.
correct = {m: {q: [next(r["answer"] for r in results if r["model"] == m and r["run"] == run
                        and r["question_id"] == q) == truth[q] for run in RUNS]
               for q in unique_ids} for m in MODELS}
score = {m: {q: sum(correct[m][q]) / 3 for q in unique_ids} for m in MODELS}

a_better = [q for q in unique_ids if score["model-a"][q] > score["model-b"][q]]
b_better = [q for q in unique_ids if score["model-b"][q] > score["model-a"][q]]
ties = len(unique_ids) - len(a_better) - len(b_better)
k, n = len(a_better), len(a_better) + len(b_better)
# exact two-sided sign test on the questions where the models differ
p_sign = min(1.0, 2 * sum(comb(n, i) for i in range(0, min(k, n - k) + 1)) / 2 ** n)

rng = random.Random(41)
diffs = []
for _ in range(10_000):
    sample = [rng.choice(unique_ids) for _ in unique_ids]
    diffs.append(sum(score["model-a"][q] - score["model-b"][q] for q in sample) / len(sample))
diffs.sort()
lo, hi = diffs[249], diffs[9749]
observed = sum(score["model-a"][q] - score["model-b"][q] for q in unique_ids) / len(unique_ids)
share_a_ahead = sum(d > 0 for d in diffs) / len(diffs)

print("\n== 5. Paired comparison over the 50 distinct questions")
print(f"   a scores higher on {len(a_better)} questions, b higher on {len(b_better)}, tied on {ties}")
print(f"   exact sign test (two-sided): p = {p_sign:.2f}")
print(f"   a - b = {100 * observed:+.1f} points; 95% bootstrap CI over questions "
      f"[{100 * lo:+.1f}, {100 * hi:+.1f}]; a ahead in {100 * share_a_ahead:.0f}% of resamples")


# ---------------------------------------------------------------- 6. how they fail
print("\n== 6. Failure patterns")
settings = {m: sorted({r["temperature"] for r in results if r["model"] == m}) for m in MODELS}
print(f"   temperature: " + ", ".join(f"{m} {settings[m]}" for m in MODELS))
for m in MODELS:
    always = sum(all(correct[m][q]) for q in unique_ids)
    never = sum(not any(correct[m][q]) for q in unique_ids)
    flaky = len(unique_ids) - always - never
    identical = sum(len({next(r["answer"] for r in results if r["model"] == m and r["run"] == run
                              and r["question_id"] == q) for run in RUNS}) == 1 for q in unique_ids)
    # majority vote across the 3 runs; no answer given twice counts as wrong
    vote = 0
    for q in unique_ids:
        answers = Counter(next(r["answer"] for r in results if r["model"] == m and r["run"] == run
                               and r["question_id"] == q) for run in RUNS)
        best, count = answers.most_common(1)[0]
        vote += count >= 2 and best == truth[q]
    print(f"   {m}: right 3/3 on {always}, 0/3 on {never}, mixed on {flaky}; "
          f"same answer all 3 runs on {identical}/50; majority-of-3 vote {vote}/50 = {100 * vote / 50:.1f}%")

never_a = [q for q in unique_ids if not any(correct["model-a"][q])]
print(f"   questions model-a never gets right: {', '.join(never_a)}")
print("   model-b on those same questions: "
      + ", ".join(f"{q} {sum(correct['model-b'][q])}/3" for q in never_a))

bare = sum(response_style(r["response"]) == "bare integer" for r in results if r["model"] == "model-b")
print(f"   model-b replies as a bare integer in {bare}/168 rows ({100 * bare / 168:.1f}%); model-a 168/168")

lat = {m: sorted(int(r["latency_ms"]) for r in results if r["model"] == m) for m in MODELS}
print("   median latency: " + ", ".join(f"{m} {lat[m][len(lat[m]) // 2]} ms" for m in MODELS)
      + " (first call of every run is a ~8 s cold start)")
