# Contributing to Lux

Thanks for your interest in contributing.

## Development setup

1. Ensure Python 3.10+ is installed.
2. Clone the repository.
3. Run the interpreter directly:

```bash
python3 main.py
```

There are currently no third-party dependencies.

## Project goals

Lux is a compact interpreter prototype. Contributions are most helpful when they improve one or more of:

- Language correctness and predictable behavior
- Parser/interpreter readability
- Documentation quality and examples
- Error reporting and developer ergonomics

## Recommended workflow

1. Create a branch from `main`.
2. Make focused changes (small PRs are easier to review).
3. Update docs for any language/runtime behavior change.
4. Run quick local checks.
5. Open a pull request with rationale and sample code.

## Coding guidelines

- Keep implementation self-contained and clear.
- Prefer explicit names over clever abstractions.
- Maintain compatibility with existing language behavior unless intentionally changing it.
- If behavior changes, include before/after examples in the PR description.

## Documentation expectations

When updating language semantics, update:

- `README.md` (high-level overview)
- `LANGUAGE_BASICS.md` (syntax/runtime specifics)

## Manual test checklist

Use this lightweight checklist before submitting:

```bash
python3 -m py_compile main.py
python3 main.py <<'EOF'
print("hello")
x = {1,2,3}
print(#x)
function add(a,b)
   return a+b
end
print(add(2,3))
quit
EOF
```

Verify:

- REPL starts and exits cleanly.
- Basic expressions evaluate correctly.
- Table operations and function calls work.
- No syntax regressions for core constructs.

## Pull request guidelines

Please include:

- **What changed** (short summary)
- **Why it changed** (motivation/problem)
- **How it was tested** (commands + outcomes)
- **Any compatibility impact** (if behavior changed)

## Reporting issues

When filing a bug, include:

- Reproducible code snippet
- Expected vs. actual behavior
- Python version
- OS/environment details

Thank you for helping improve Lux.
