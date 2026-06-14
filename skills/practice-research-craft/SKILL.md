---
name: practice-research-craft
description: "Build and train the craft behind original, rigorous research: choosing worthwhile problems, improving information inputs, forecasting results, keeping research logs, designing cheap falsifying experiments, inspecting failures, testing baselines and ablations, exploring adjacent fields, and cultivating useful collaborators and public explanations. Use when starting or reviewing a research project, selecting among research directions, planning experiments, diagnosing weak or stalled research, conducting a daily or weekly research review, or turning research ambitions into deliberate practice."
---

# Practice Research Craft

Treat research as a trainable stack of behaviors, not paper production or the appearance of novelty. Optimize for faster correction of wrong beliefs and compounding judgment.

## Choose The Mode

- **Problem selection**: compare candidate problems and write a problem thesis.
- **Research design**: turn a desired outcome into falsifiable questions and cheap experiments.
- **Experiment review**: analyze results, failures, baselines, and updated beliefs.
- **Practice review**: audit the user's research habits and prescribe drills.
- **Weekly review**: summarize learning velocity, changed beliefs, and next bets.

Infer the mode from the request. If ambiguity would materially change the work, ask one focused question.

## Core Workflow

Apply only the steps relevant to the selected mode, but never skip prediction, evidence inspection, or belief updating.

### 1. Own The Problem

Start from an outcome the user wants to exist, then reason backward.

- State the desired change in the world.
- Explain why it matters now and to whom.
- Separate the user's reasoning from borrowed prestige, trends, or advisor direction.
- Identify the user's unusual access, skill, curiosity, or constraint.
- Define what evidence would make the user continue, pivot, or stop.
- Prefer important, neglected, tractable questions over merely fashionable ones.

Produce a short **problem thesis**:

```text
I want [outcome] for [people/system] because [importance].
Current approaches fail because [mechanism or gap].
I believe [claim] because [evidence].
The cheapest evidence that could change my mind is [test].
I will stop or pivot if [condition].
```

### 2. Upgrade The Inputs

Build an input portfolio instead of relying on the same feed as everyone else.

- Read primary sources before summaries when feasible.
- Include foundational or old work, not only recent releases.
- Add at least one adjacent field that may offer a useful mechanism or analogy.
- Inspect appendices, limitations, methods, raw data, and implementation details.
- Seek disconfirming evidence and strong competing explanations.
- Distinguish observed evidence, author interpretation, and the user's inference.

Do not reward breadth measured only by item count. Prefer a small set of inputs that changes the model of the problem.

### 3. Forecast Before Looking

Force an explicit prediction before reading a result or running an experiment.

Record:

```text
Prediction:
Confidence:
Reasoning:
Result:
Surprise:
Updated belief:
Calibration lesson:
```

Never retrofit the prediction after seeing the evidence. Use repeated forecast-correction cycles to train taste.

### 4. Write The Research Ledger

Maintain one durable entry per meaningful investigation:

```text
Question:
Hypothesis:
Setup:
Expected result:
Observed result:
Failure cases:
Evidence against my view:
Updated belief:
Next cheapest test:
```

Write down inconvenient evidence immediately. Treat prose as a reasoning test: identify unsupported steps, contradictions, and assumptions hidden by vague language.

### 5. Tighten The Learning Loop

Research speed is the rate at which false beliefs are discovered and corrected.

- Shrink the question to the cheapest disposable test.
- Make each run reproducible from its inputs and configuration.
- Make comparison with a prior run quick and explicit.
- Validate the smallest case before scaling.
- Separate infrastructure friction from scientific uncertainty.
- Improve tooling when it increases the number or quality of learning cycles.

For technical experiments, require a minimal sanity check before expensive work. Examples include overfitting one batch, testing on a tiny fixture, or manually calculating one expected output.

### 6. Stare At The Outputs

Do not accept an aggregate metric as sufficient analysis.

- Inspect raw inputs before building.
- Sample concrete outputs, transcripts, residuals, or errors.
- Pull a bounded set of failures and classify them.
- Quantify the largest failure categories.
- Attack the largest actionable category first.
- Look at tails, anomalies, and counterexamples.
- Check whether the evaluation itself measures the intended behavior.

Prefer one revealing failure over another decimal place that does not change a decision.

### 7. Defend Against False Progress

- Tune strong baselines before claiming improvement.
- Compare against simple alternatives.
- Ablate components until the causal contributor is understood.
- Check leakage, confounding, selection effects, and underpowered comparisons.
- State uncertainty and what the evidence does not establish.
- Do not convert an interesting observation into a general claim without support.

### 8. Wander On Purpose

Reserve some effort for adjacent fields and disposable ideas.

- Run cheap probes before making long commitments.
- Track which domains energize the user and where their background creates leverage.
- Treat abandoned ideas as useful only when the reason for abandonment is recorded.
- Maintain breadth as insurance against a saturated direction, not as avoidance of depth.

### 9. Find The People And Explain The Work

- Identify people who can falsify the idea early.
- Replicate and share useful findings.
- Release reusable tools when appropriate.
- Explain hard ideas plainly enough that assumptions become visible.
- Share half-formed ideas only with clear uncertainty labels.
- Treat helpful criticism and collaboration as compounding assets.

Do not publish, message, upload, or disclose work without the user's authorization.

## Practice Drills

When the user asks to improve research ability, prescribe a small number of observable drills:

- Predict paper results before revealing them.
- Forecast which current ideas will matter and set a review date.
- Reconstruct a result from the method alone.
- Shrink a hard problem to a trivial version, solve it, then restore one difficulty.
- Categorize 50-100 failures from a real system.
- Reproduce a result and document deviations.
- Explain one concept publicly in plain language.
- Review old ledger entries for calibration and repeated mistakes.

Attach a cadence, evidence of completion, and review date to each drill.

## Output Contract

For substantial requests, return:

1. **Research objective**: the desired outcome and why it matters.
2. **Current model**: assumptions, evidence, and competing explanations.
3. **Prediction**: expected result and confidence before new evidence.
4. **Next cheapest test**: setup, metric, and stop/pivot condition.
5. **Inspection plan**: raw examples and failure slices to examine.
6. **Ledger entry**: a copy-ready record using the schema above.
7. **Practice prescription**: one recurring drill that improves the weakest research skill.

Keep advice specific to the user's actual project. Challenge borrowed goals, vague novelty claims, uninspected metrics, weak baselines, and experiments that are too expensive to teach quickly.
