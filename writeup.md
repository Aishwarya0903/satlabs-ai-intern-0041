**What was wrong**

1. **Exact string match.** model-b's formats (`**600**`, `7,315`, `Sure! … equals 600.`) turned 47 correct answers into misses.
2. **Wrong key.** Recomputing from the question text, q007, q041 and q046 are wrong. model-a was right on all three in every run and was still marked wrong.
3. **Duplicates.** q008=q020, q011=q033, q013=q047, q016=q037, q018=q034 and q053=q056 each count twice.
4. **Settings differ.** model-a ran at temperature 0.0 and model-b at 0.7. That compares configurations, not models.
5. **Sample size is overstated.** model-a answers identically in all 3 runs. The evidence is 50 questions, not 168 responses.

**What I changed:** I score the last integer in each reply, take the expected answer from the arithmetic and count each question once. Pooled over 3 runs: **model-a 82.0%, model-b 78.0%**. `analysis.py` prints the effect of each fix.

**Is model-a better?** That isn't shown. The gap is +4.0 points, and the 95% bootstrap CI over questions is −8 to +16. A sign test does favour model-a: it does better on 23 questions, model-b on 9 (p=0.02). That mostly reflects consistency. model-a fails the *same* 9 questions every run. model-b's errors are scattered: no question is wrong in all 3 runs, and a majority vote of its runs scores 90.0%. My confidence that model-a is more accurate is low. My confidence that it is more consistent and cleaner to parse is high.

**What this does not prove**

- How model-b does at temperature 0, which is the fair test.
- Anything beyond 50 small +, −, × questions.
- Whether model-b's wordy replies break a downstream parser. If a bare number is required, that is a real weakness of model-b.

**Assumptions:** "Accuracy" means correct ÷ responses over distinct questions, runs pooled. Duplicate IDs are the later copy of each pair.
