# Canonical tags

One tag per line: `#tag: definition (aliases: a, b)`. Tags are lower-case words joined by
hyphens. The validator refuses an entry whose tag is not on this list, and suggests the closest
match, so a tag only exists once it is defined here. Add a line before using a new tag, keep
definitions to one sentence, and prefer widening an existing tag over adding a near-duplicate.
Aliases are the spellings you tend to reach for; the validator maps them to the canonical tag.

This file is a starter set, not a fixed vocabulary. The "Subjects" below suit math-heavy
academic work; replace them with whatever your own domain needs. Keep the "Objects and moves"
and "Work and process" sections, which apply to any field, and keep the format of the lines,
which is what the validator reads.

## Subjects

#linear-algebra: vector spaces, matrices, decompositions, eigenvalues (aliases: linalg, la, eigen, eigenvalues)
#spectral-theorem: spectral decomposition and its consequences, variational characterisations (aliases: spectral)
#real-analysis: limits, continuity, differentiation and integration on the reals (aliases: analysis)
#measure-theory: sigma-algebras, measures, Lebesgue integration (aliases: measure)
#functional-analysis: normed and Hilbert spaces, operators, duality (aliases: functional)
#topology: open sets, compactness, connectedness, metric spaces
#probability: probability spaces, random variables, limit theorems (aliases: prob)
#statistics: estimation, testing, inference (aliases: stats)
#optimization: optimisation problems, algorithms, duality (aliases: optimisation, optim)
#convexity: convex sets, convex functions, convex analysis (aliases: convex)
#numerical-methods: floating point, conditioning, iterative solvers, discretisation (aliases: numerics, numerical)
#machine-learning: models, training, generalisation (aliases: ml)
#information-theory: entropy, mutual information, coding (aliases: info-theory)
#graph-theory: graphs, spectra of graphs, combinatorial structure (aliases: graphs)
#algebra: groups, rings, fields, modules
#differential-equations: ODEs and PDEs, existence, stability (aliases: ode, pde)

## Objects and moves

#definition: a definition worth having exactly right
#theorem: a theorem statement and what it needs
#proof-technique: a reusable argument pattern (aliases: technique, trick)
#counterexample: an example that kills a plausible claim
#computation: a worked calculation or numerical experiment
#pitfall: a mistake made or nearly made, and how to avoid it (aliases: mistake, gotcha)

## Work and process

#thesis: the thesis project itself
#coursework: assignments and exam preparation (aliases: homework, exam)
#seminar: talks given or attended
#methodology: how the work is done: tooling, workflow, this memory system (aliases: tooling, workflow, meta)
