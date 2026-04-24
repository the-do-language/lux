# Lux

Lux is a small, Lua-inspired scripting language implemented in a single Python file (`main.py`). It includes:

- A dynamic `Table` value model (numbers, strings, booleans, nil, functions, and tables).
- A lexer, parser, and AST-based interpreter.
- Control flow (`if`, `while`, `repeat`, numeric `for`).
- Functions (named and anonymous).
- Table constructors and metatable hooks.
- A REPL with automatic block indentation.

## Project status

This repository is a compact prototype/interpreter intended for experimentation and learning. It is not packaged for production use.

## Requirements

- Python 3.10+ (recommended)
- No third-party dependencies

## Quick start

### Run the REPL

```bash
python3 main.py
```

### Run a Lux file

```bash
python3 main.py path/to/script.lux
```

If the first CLI argument is an existing file path, Lux reads and runs that file; otherwise it starts the interactive REPL.

## Language overview

See [LANGUAGE_BASICS.md](./LANGUAGE_BASICS.md) for detailed syntax and behavior. Highlights:

- Literals: numbers, strings, booleans, `nil`
- Expressions: arithmetic, comparisons, boolean ops, concatenation (`..`), length (`#`), unary negation (`-`)
- Statement forms: assignment, local assignment, return, control flow blocks
- Tables with keyed fields and array-like entries
- Metatable operations via:
  - `setmetatable(table, metatable)`
  - `getmetatable(table)`
  - `rawget(table, key)`
  - `rawset(table, key, value)`

## Built-in globals

Lux initializes these globals:

- `print(...)`
- `str(value)`
- `but(left, right)`
- `setmetatable(target, metatable)`
- `getmetatable(target)`
- `rawget(target, key)`
- `rawset(target, key, value)`

## Repository layout

```text
.
├── main.py               # Interpreter, parser, lexer, REPL
├── README.md             # Project overview and usage
├── LANGUAGE_BASICS.md    # Language documentation
├── contributing.md       # Contribution workflow
└── LICENSE               # BSD 3-Clause license
```

## Contributing

Please read [contributing.md](./contributing.md) before opening a pull request.

## License

This project is licensed under the BSD 3-Clause License. See [LICENSE](./LICENSE).
