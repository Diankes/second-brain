# Entry templates

Every curated entry is: one title line, the labelled lines for its kind in this order, then the
final `tags:` line. A label's value may run over several lines, so display math fits under
`Claim:` or `Why:`. `Rejected:`, `Open:`, `Questions:` and `In progress:` may be `none`; the
others must say something. Optional link lines (`Builds on:`, `Supersedes:`, `Corrects:`,
`Answers:`) go just before `tags:`. The validator (`scripts/validate_entry.py`) enforces exactly
these labels; `tests/test_plugin_files.py` keeps this file and the validator in step.

## insight

```text
<title, one line>
Context: what we were working on and why this came up
Claim: the insight itself, math in LaTeX
Why: the derivation or argument, the step that makes it true
Rejected: the earlier belief or alternative this rules out, and why | none
Open: what this does not settle | none
Source: <key §locator>[; <key locator>] | discussion
Builds on: #<id> [#<id>]
tags: #a #b
```

## decision

```text
<title, one line>
Context: the question and the constraints
Options: A: ...; B: ...
Rejected: B because ...
Decision: A, stated precisely
Revisit when: the condition that would reopen it
Source: <key locator> | discussion
Supersedes: #<id>
tags: #a #b
```

## reading

```text
<source key and section, one line>
Source: <key §locator>
Claim: what the text establishes, in LaTeX
Argument: how, in three to six lines
Fits: how it connects to what we already have; name the ids
Questions: what is unclear or worth checking | none
Builds on: #<id>
tags: #a #b
```

## open-question

```text
<the question, one line>
Context: where it came up
Why it matters: what depends on the answer
Would settle it: the observation, proof or computation that decides it
Source: <key locator> | discussion
tags: #a #b
```

## note

```text
<title, one line>
free text, still LaTeX for math; use this only when no other kind fits
tags: #a #b
```

## checkpoint

The `summary` argument of the `checkpoint` tool:

```text
Goal: what this stretch of work is toward
Done: since the last checkpoint, with event ids
In progress: the current thread and its exact state | none
Open: pending questions and decisions
Next: the first concrete step when resuming
tags: #a #b
```

## Worked example

```text
Spectral theorem gives the variational characterisation of eigenvalues
Context: comparing two proofs of the Courant-Fischer theorem for the seminar on 2026-10-02
Claim: for symmetric $A \in \mathbb{R}^{n \times n}$ with eigenvalues $\lambda_1 \ge \dots \ge \lambda_n$,
$$\lambda_k = \max_{\dim S = k} \; \min_{x \in S,\, \|x\| = 1} x^\top A x .$$
Why: the spectral theorem gives an orthonormal eigenbasis; restricting to the span of the first $k$ eigenvectors gives $\ge \lambda_k$, and any $k$-dimensional $S$ meets the span of the last $n-k+1$ eigenvectors, which gives $\le \lambda_k$.
Rejected: the induction on $n$ in the lecture notes; it hides the dimension-counting step that does the real work.
Open: whether the same argument survives for compact self-adjoint operators without modification.
Source: strang-la §6.4; mit-18.06 lec24 12:30
Builds on: #41
tags: #linear-algebra #spectral-theorem
```
