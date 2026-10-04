# Synthetic test cases

`synthetic_cases.json` contains nine fictional service cases for automated
tests. These records are separate from the assignment sample.

They cover:

- English, German, French and Italian descriptions;
- two equipment families;
- error-code variants;
- outcome evidence with an explicit negative finding;
- equipment-family fallback.

The tests use a deterministic embedder to verify retrieval behaviour.
They do not measure the real embedding model's multilingual accuracy.

These cases must not be used to estimate diagnostic probabilities or
real-world repair frequencies.