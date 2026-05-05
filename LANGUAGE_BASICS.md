# Lux Language Basics

This document explains the syntax and runtime behavior implemented in `main.py`.

## 1) Core value model

Everything in Lux is represented as a `Table` runtime object with one of these kinds:

- `number`
- `string`
- `boolean`
- `nil`
- `function`
- `table`

Tables may hold:

- Direct fields (e.g. `t.name = "lux"`)
- Array-like indices (`t[1]`, `t[2]`, ...)
- An optional metatable with hooks (`_index_`, `_newindex_`, `_call_`, arithmetic/comparison hooks)

## 2) Lexical basics

### Comments

Single-line comments start with `--`.

```lux
-- this is a comment
```

### Identifiers

Identifiers follow this shape:

- Start: letter or `_`
- Continue: letters, digits, or `_`

### Keywords

Reserved keywords include:

`if`, `elseif`, `else`, `end`, `then`, `while`, `do`, `for`, `repeat`, `until`, `local`, `function`, `return`, `and`, `or`, `not`, `true`, `false`, `nil`, `but`

## 3) Literals

### Numbers

```lux
42
3.14
.5
```

### Strings

Single or double quoted:

```lux
"hello"
'world'
```

### Booleans and nil

```lux
true
false
nil
```

## 4) Expressions and operators

Lux supports these expression classes.

### Arithmetic

```lux
1 + 2
7 - 3
4 * 5
8 / 2
9 % 4
2 ^ 3
```

### Concatenation

Use `..` to concatenate string representations:

```lux
"value=" .. 10
```

### Comparisons

```lux
x == y
x ~= y
x < y
x <= y
x > y
x >= y
```

### Boolean logic

```lux
a and b
a or b
not a
```

`and` and `or` short-circuit.

### Unary operators

- `-x` numeric negation
- `#x` length
  - string: character count
  - table: contiguous array length from index `1`

### Custom `but` operator

`left but right` creates a new value with **left's core type/payload** and then mixes in fields from both sides.

Operationally (matching `main.py`):

1. Start from a copy of `left` (kind, payload, and fields).
2. Copy every field from `right` into the new value except `_self_`.
3. If a field exists on both sides, **right currently overwrites left** in this implementation.

That means `but` behaves like a field-mixing operation, not a nil-coalescing operator. For example, `5 but "five"` keeps numeric identity/payload from `5`, but can gain string fields/methods from `"five"`.

Equivalent behavior is exposed via the global `but(left, right)` function.

## 5) Variables and assignment

### Global assignment

```lux
x = 10
name = "lux"
```

### Local assignment

```lux
local x = 10
```

> Note: the current interpreter keeps a single environment dictionary and does not enforce full lexical scoping semantics beyond function-local copies.

## 6) Tables

### Constructor syntax

```lux
t = {1, 2, 3}
obj = {name = "lux", version = 1}
mix = {10, 20, name = "demo", ["k"] = 9}
```

### Field and index access

```lux
print(obj.name)
print(obj["name"])
print(t[1])
```

### Mutation

```lux
obj.name = "new"
obj["flag"] = true
```

## 7) Control flow

### If / elseif / else

```lux
if x > 10 then
   print("big")
elseif x == 10 then
   print("equal")
else
   print("small")
end
```

### While

```lux
i = 1
while i <= 3 do
   print(i)
   i = i + 1
end
```

### Repeat until

```lux
i = 1
repeat
   print(i)
   i = i + 1
until i > 3
```

### Numeric for

```lux
for i = 1, 5 do
   print(i)
end

for i = 10, 2, -2 do
   print(i)
end
```

## 8) Functions

### Named function definitions

```lux
function add(a, b)
   return a + b
end

print(add(2, 3))
```

### Anonymous function literals

```lux
square = function(x)
   return x * x
end

print(square(4))
```

### Calls

```lux
result = add(1, 2)
```

## 9) Built-ins

Provided by the interpreter:

- `print(...)`: prints string representations with spaces.
- `str(v)`: returns Lux string value from `v`.
- `but(l, r)`: mix fields from both values into a new value (left kind/payload, right field overlay except `_self_`).
- `setmetatable(t, mt)`: set table metatable.
- `getmetatable(t)`: fetch metatable or `nil`.
- `rawget(t, key)`: bypass metatable lookup.
- `rawset(t, key, value)`: bypass metatable write hook.

## 10) Metatables and metamethods

Supported metatable fields include:

- `_index_` for missing-key reads
- `_newindex_` for writes to missing keys
- `_call_` for call behavior
- Arithmetic/comparison aliases via internal fields like `_add_`, `_sub_`, `_mul_`, `_div_`, `_mod_`, `_pow_`, `_eq_`, `_lt_`, `_le_`

Legacy aliases such as `__add`, `__call`, `num`, `str`, etc. are normalized internally.

## 11) REPL behavior

When running `python3 main.py` without a file argument:

- Prompt is `>>>` for top-level and `...` inside blocks.
- Type `exit` or `quit` to leave.
- Block indentation is auto-normalized to 3 spaces per level.
- Input is buffered until block structure closes (`end` / `until`).

## 12) Known limitations

Current implementation constraints:

- Single-file prototype (no package/module system).
- Error messages are basic `SyntaxError`/runtime exceptions.
- Partial scoping model (`local` is parsed, but environment handling is simplified).
- No break/continue statements.
- No standard library beyond the few built-ins listed above.

