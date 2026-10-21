# Algorithm Research Protocol

## 1. Purpose

Use this protocol for non-trivial algorithm design, algorithm replacement, or substantial improvements in correctness, robustness, scalability, or performance.

The objective is to produce an algorithm that is justified by a clear problem model, explicit assumptions, appropriate alternatives, known failure boundaries, and reproducible verification.

This protocol does not require a new framework or subsystem. Use existing repository architecture, interfaces, utilities, and validation infrastructure wherever suitable.

## 2. Establish the Problem Model

Before selecting an algorithm, establish:

- **Inputs:** data structures, dimensionality, coordinate systems, units, and valid input ranges.
- **Outputs:** required results, output invariants, and acceptable approximation.
- **Constraints:** functional requirements, geometric or numerical constraints, API restrictions, runtime limits, and memory limits.
- **Objective:** what must be minimized, maximized, preserved, or guaranteed.
- **Success criteria:** measurable correctness, quality, robustness, and performance thresholds.
- **Known limitations:** unavailable data, uncertain assumptions, unsupported cases, and environmental dependencies.

Separate verified facts from assumptions and hypotheses.

Do not proceed with an under-specified objective when the missing information could change the algorithm choice. Resolve the ambiguity using available evidence or request only the essential clarification.

## 3. Inspect the Existing Implementation

Before proposing a replacement:

1. Trace the actual execution path and identify the algorithm currently used.
2. Inspect relevant data structures, callers, invariants, and failure-handling behavior.
3. Determine which limitations are confirmed by code or tests and which remain hypotheses.
4. Identify reusable components and the smallest appropriate integration point.
5. Preserve existing behavior unless the requirements explicitly authorize changing it.

Do not duplicate an existing capability or redesign unrelated architecture without evidence that it is necessary.

## 4. Generate and Compare Candidate Algorithms

Consider multiple materially different approaches when alternatives exist.

For each plausible candidate, assess:

- Correctness assumptions and applicable problem domain.
- Expected solution quality and approximation error.
- Time and space complexity, including important worst cases.
- Robustness to degenerate, noisy, incomplete, or adversarial inputs.
- Implementation complexity and integration cost.
- Compatibility with available data, APIs, and runtime constraints.
- Verification difficulty and observable failure modes.

Use a comparison table when it improves clarity.

Do not invent alternatives merely to satisfy a fixed count. If only one approach is viable, explain why and identify the assumptions on which that conclusion depends.

Record the comparison, not just the winner:

- State the **baseline** each candidate is judged against — the current implementation, or the simplest correct method when none exists.
- For every candidate **rejected**, state the specific criterion that eliminated it (a violated constraint, a worse failure boundary, unacceptable complexity, or evidence that contradicts an assumption). "Less elegant" is not a rejection reason.
- Confirm the candidates differ in a way that can change the result: a different correctness assumption, failure boundary, or complexity class. Two variants of the same idea are one candidate.

Select the approach using the stated objectives and constraints, not familiarity or implementation convenience alone. The selection is provisional until the distinguishing tests in section 7 have been run.

## 5. Derive the Algorithm

Specify the selected algorithm precisely enough to implement and independently review it.

As appropriate, include:

- Mathematical formulation and notation.
- Objective function, constraints, and assumptions.
- Core equations, geometric constructions, or decision rules.
- Data structures and their invariants.
- Step-by-step algorithm or pseudocode.
- Termination conditions and convergence requirements.
- Numerical tolerances and their rationale.
- Complexity analysis and expected bottlenecks.

Distinguish proven properties from engineering heuristics. Do not claim global optimality, convergence, completeness, or correctness without adequate justification.

## 6. Analyze Failure Modes and Counterexamples

Explicitly examine relevant difficult cases, including:

- Empty, invalid, incomplete, or degenerate inputs.
- Boundary conditions and tolerance-sensitive cases.
- Symmetry, ties, duplicate elements, and ambiguous solutions.
- Worst-case complexity or pathological input distributions.
- Numerical instability, accumulated error, or non-convergence.
- Cases where the chosen representation loses essential information.
- Cases where an approximation produces false positives or false negatives.

Construct concrete counterexamples for the most consequential failure modes whenever feasible.

Prefer counterexamples that **distinguish competing hypotheses**. When two candidates predict different results for the same input, construct that input and record which prediction holds. A case both candidates handle identically does not help choose between them; a case where they diverge does.

For each identified failure mode, define the expected behavior: valid result, bounded approximation, explicit rejection, fallback, or reported uncertainty.

## 7. Define Independent Verification Before Implementation

Create a verification plan before coding.

Include relevant categories:

- **Invariant tests:** validate mathematical, geometric, or structural properties.
- **Positive cases:** representative inputs where the algorithm should succeed.
- **Negative cases:** invalid or unsupported inputs.
- **Boundary cases:** degeneracies, tolerances, and extreme values.
- **Counterexample regressions:** tests targeting known weaknesses in the previous or candidate algorithms.
- **Differential tests:** compare against a trusted reference implementation or independent method when available.
- **Property-based tests:** verify general properties across generated inputs when feasible.
- **Performance tests:** measure runtime and memory against representative workload sizes.
- **Integration tests:** verify behavior through the actual application interfaces.

Specify expected outcomes and measurable acceptance criteria. A test that only confirms execution without failure is not sufficient to establish algorithmic correctness.

Design the plan to **discriminate**, not merely to pass:

- Include at least one case, where alternatives exist, on which the candidates predict different outcomes, so the result selects between them rather than confirming all of them.
- Include inputs outside the cases the chosen algorithm is already known to handle. A suite built only from the algorithm's known successes cannot reveal its limits.
- The reasoning that produced the algorithm is not evidence that it works. Verification must be reproducible by someone who did not design it, from the recorded inputs and expected outcomes alone.

Do not treat two implementations sharing the same underlying assumption or defect as fully independent evidence. A reference implementation is independent only to the extent that it does not inherit the assumption under test.

## 8. Implement Incrementally

After the algorithm and verification plan are sufficiently justified:

1. Implement the smallest coherent change using existing project conventions.
2. Separate pure algorithmic logic from environment-dependent integration where practical.
3. Preserve explicit input validation, failure reporting, and numerical tolerance semantics.
4. Add regression tests for confirmed defects.
5. Avoid unrelated refactoring and new abstractions unless they are required by the solution.
6. Run the relevant existing tests as well as the new tests.

If implementation evidence invalidates a core assumption, stop and reassess the algorithm instead of accumulating local patches around a flawed approach.

## 9. Evaluate and Compare Results

Evaluate the implementation against the pre-defined criteria.

Report separately:

- Functional correctness and invariant results.
- Quality or accuracy of the computed solution.
- Runtime and memory measurements, including workload conditions.
- Robustness across representative and adversarial cases.
- Regression results.
- Known limitations and unsupported inputs.

Compare against the previous algorithm or a trusted baseline when available. Ensure comparisons use equivalent inputs, constraints, and measurement conditions.

Treat the criteria as a constrained optimization, not a single score:

- Separate **hard constraints** (correctness, invariants, output validity, API and runtime limits) from **objectives** (accuracy, robustness, runtime, memory). An improvement that violates a hard constraint is not an improvement.
- Do not collapse the objectives into one number, and do not judge from a single average. Report the distribution that matters — worst case, tail, or variance — alongside the mean, and state the workload it was measured on.
- Repeat performance measurements; a single run is not a measurement. Record the conditions (input size, hardware, build configuration) so the result can be reproduced.
- When an iteration regresses, keep the last version that satisfied every hard constraint and record why the newer attempt was not adopted. Do not overwrite a verified result with an unverified one.

Do not claim an improvement without evidence that supports the specific claim.

## 10. Evidence and Completion Status

Clearly distinguish:

- **Proposed:** a design has been described but not implemented.
- **Implemented:** code changes exist but sufficient verification has not completed.
- **Locally verified:** specified local checks passed.
- **Integration verified:** behavior was verified through the relevant application integration.
- **Runtime verified:** the target application or runtime was actually exercised.
- **Performance verified:** performance claims were supported by recorded measurements.

Use only the status supported by the evidence. Passing unit tests does not prove target-runtime compatibility, and successful execution does not by itself prove correctness or optimality.

For every unresolved issue, state its impact, available evidence, and the verification still required.

## 11. Final Deliverable

For a substantial algorithm task, provide a concise report covering:

1. Problem definition and acceptance criteria.
2. Existing algorithm and confirmed limitations.
3. Candidate approaches and selection rationale.
4. Chosen algorithm and key correctness assumptions.
5. Complexity and important failure boundaries.
6. Implementation scope and changed files.
7. Verification performed and its actual results.
8. Performance evidence, if performance improvement was an objective.
9. Remaining risks, unsupported cases, and required follow-up.

Do not report planned checks as completed checks.

## 12. Scope and Proportionality

Apply this protocol proportionally to task complexity.

A localized bug fix may require only a focused explanation and regression test. A major algorithm replacement may require mathematical derivation, comparative evaluation, counterexamples, and extensive verification.

Do not introduce new capabilities, playbooks, lifecycle states, services, or governance layers solely to implement this protocol.

Follow existing repository instructions, API evidence boundaries, and user authorization requirements at all times.
