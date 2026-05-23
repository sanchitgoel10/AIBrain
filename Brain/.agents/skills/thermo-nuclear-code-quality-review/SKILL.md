---
name: thermo-nuclear-code-quality-review
description: Run an extremely strict maintainability review for abstraction quality, giant files, and spaghetti-condition growth. Use for a thermo-nuclear code quality review, thermonuclear review, deep code quality audit, or especially harsh maintainability review.
disable-model-invocation: true
---

# Thermo-Nuclear Code Quality Review

Use this skill for an unusually strict review focused on implementation quality, maintainability, abstraction quality, and codebase health.

Above all, be ambitious about code structure. Do not merely identify local cleanup opportunities. Actively search for "code judo" moves: behavior-preserving restructurings that make the implementation dramatically simpler, smaller, more direct, and more elegant.

## Baseline

Perform a deep code quality audit of the current branch's changes. Rethink how to structure and implement the changes to meaningfully improve code quality without impacting behavior. Work to improve abstractions, modularity, reduce spaghetti code, improve succinctness, and improve legibility.

Be ambitious. If there is a clear path to improving the implementation by restructuring some of the codebase, push for it. Be extremely thorough and rigorous.

## Non-Negotiable Standards

1. Be ambitious about structural simplification.
2. Do not let a change push a file from under 1k lines to over 1k lines without a very strong reason.
3. Do not allow random spaghetti growth in existing code.
4. Bias toward cleaning the design, not merely accepting working code.
5. Prefer direct, boring, maintainable code over hacky or magical code.
6. Push hard on type and boundary cleanliness when they affect maintainability.
7. Keep logic in the canonical layer and reuse existing helpers.
8. Treat unnecessary sequential orchestration and non-atomic updates as design smells when a cleaner structure is obvious.

## Primary Review Questions

- Is there a code-judo move that would make this dramatically simpler?
- Can this change be reframed so fewer concepts, branches, or helper layers are needed?
- Does this improve or worsen the local architecture?
- Did the diff add branching complexity where a better abstraction should exist?
- Did a cohesive module become more coupled, more stateful, or harder to scan?
- Is this logic living in the right file and layer?
- Did this change enlarge a file or component past a healthy size boundary?
- Are repeated conditionals signaling a missing model or helper?
- Is the implementation direct and legible, or does it rely on special cases and incidental control flow?
- Is this abstraction earning its keep, or is it just a wrapper?
- Did the diff introduce loose object shapes or optional fields that obscure the real invariant?
- Is this orchestration more sequential or less atomic than it needs to be?

## What To Flag Aggressively

- A complicated implementation where a cleaner reframing could delete whole categories of complexity.
- Refactors that move code around without reducing the concepts a reader must hold.
- A file crossing 1000 lines due to a change, especially if new code could be split out.
- New conditionals bolted onto unrelated code paths.
- One-off booleans, nullable modes, or flags that complicate existing control flow.
- Feature-specific logic leaking into general-purpose modules.
- Generic magic that hides simple structure.
- Thin wrappers or identity abstractions that add indirection without clarity.
- Copy-pasted logic instead of extracted helpers.
- Narrow edge-case handling in the middle of an already busy function.
- Bespoke helpers where the codebase already has a canonical utility.
- Logic added in the wrong layer.
- Partial-update logic that leaves state less atomic than necessary.

## Preferred Remedies

- Delete a whole layer of indirection rather than polish it.
- Reframe the state model so conditionals disappear.
- Change ownership boundaries so the feature becomes a natural extension of an existing abstraction.
- Extract a helper or pure function.
- Split large files into smaller focused modules.
- Move feature-specific logic behind a dedicated abstraction.
- Replace condition chains with an explicit dispatcher.
- Separate orchestration from business logic.
- Collapse duplicate branches into a single clearer flow.
- Make boundaries more explicit so control flow gets simpler.
- Restructure related updates into a more atomic flow.

## Output Expectations

Prioritize findings in this order:

1. Structural code-quality regressions.
2. Missed opportunities for dramatic simplification.
3. Spaghetti or branching complexity increases.
4. Boundary, abstraction, or contract problems that make code harder to reason about.
5. File-size and decomposition concerns.
6. Modularity and abstraction issues.
7. Legibility and maintainability concerns.

Do not flood the review with low-value nits if there are larger structural issues. Prefer a smaller number of high-conviction comments over a long list of cosmetic notes.

## Approval Bar

Do not approve merely because behavior seems correct.

Approval requires no clear structural regression, no obvious missed simplification, no unjustified file-size explosion, no obvious spaghetti growth, no hacky abstraction that obscures design, no unnecessary wrapper or optionality churn, no architecture-boundary leak, and no missed obvious decomposition.
