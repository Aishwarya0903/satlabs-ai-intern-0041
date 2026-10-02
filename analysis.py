# Run:  python3 analysis.py
#
# Re-scores model-a vs model-b. Standard library only.
#
# Steps:
#   1. Recompute the true answer of every question from its text -> find wrong key rows.
#   2. Find questions asked twice under different IDs.
#   3. Pull the final number out of each response (model-b wraps answers in prose/markdown/commas).

import csv
import re
from collections import Counter, defaultdict

MODELS = ["model-a", "model-b"]

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
