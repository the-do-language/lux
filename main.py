import re
import sys
import readline
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Callable

# =============================================================================
# CORE: THE TABLE CLASS (EVERYTHING is a Table)
# =============================================================================
class Table:
    LEGACY_FIELD_ALIASES = {
        'num': '_num_',
        'str': '_str_',
        'bool': '_bool_',
        'self': '_self_',
        'call': '_call_',
        'add': '_add_',
        'sub': '_sub_',
        'mul': '_mul_',
        'div': '_div_',
        'mod': '_mod_',
        'pow': '_pow_',
        'eq': '_eq_',
        'lt': '_lt_',
        'le': '_le_',
        '__index': '_index_',
        '__newindex': '_newindex_',
        '__call': '_call_',
        '__add': '_add_',
        '__sub': '_sub_',
        '__mul': '_mul_',
        '__div': '_div_',
        '__mod': '_mod_',
        '__pow': '_pow_',
        '__eq': '_eq_',
        '__lt': '_lt_',
        '__le': '_le_',
    }

    def __init__(self, kind: str = 'nil', payload: Any = None):
        object.__setattr__(self, '_kind', kind)
        object.__setattr__(self, '_payload', payload)
        object.__setattr__(self, '_fields', {})
        object.__setattr__(self, '_metatable', None)
        self._setup_builtins()

    def _normalize_field_name(self, name: str) -> str:
        return self.LEGACY_FIELD_ALIASES.get(name, name)

    def _setup_builtins(self):
        fields = object.__getattribute__(self, '_fields')
        kind = object.__getattribute__(self, '_kind')
        payload = object.__getattribute__(self, '_payload')

        if kind == 'number':
            fields['_num_'] = payload
            fields['_self_'] = '_num_'
        elif kind == 'string':
            fields['_str_'] = payload
            fields['_self_'] = '_str_'
            # split returns Python list → later turned into Table array by make_value
            fields['split'] = lambda sep: [
                make_string(x) for x in payload.split(
                    sep._payload if isinstance(sep, Table) and sep._kind == 'string' else str(sep)
                )
            ]
        elif kind == 'boolean':
            fields['_bool_'] = payload
            fields['_self_'] = '_bool_'
        elif kind == 'function':
            fields['_self_'] = '_call_'
        elif kind == 'table':
            fields['_str_'] = 'table'

    def __getattr__(self, name: str):
        key = self._normalize_field_name(name)
        return self.get_by_key(key)

    def __setattr__(self, name: str, value: Any):
        if name in ('_kind', '_payload', '_fields', '_metatable'):
            object.__setattr__(self, name, value)
        else:
            key = self._normalize_field_name(name)
            self.set_by_key(key, value)

    @staticmethod
    def _table_key(key: Any) -> Any:
        if isinstance(key, Table):
            if key._kind == 'number':
                n = key._payload
                if float(n).is_integer():
                    return int(n)
                return float(n)
            if key._kind == 'string':
                return key._payload
            if key._kind == 'boolean':
                return bool(key._payload)
            if key._kind == 'nil':
                return None
            return key
        if isinstance(key, float) and key.is_integer():
            return int(key)
        if isinstance(key, str):
            return Table.LEGACY_FIELD_ALIASES.get(key, key)
        return key

    def raw_get(self, key: Any) -> 'Table':
        key = self._table_key(key)
        fields = object.__getattribute__(self, '_fields')
        val = fields.get(key)
        if val is None:
            return make_nil()
        return val if isinstance(val, Table) else make_value(val)

    def raw_set(self, key: Any, value: Any) -> 'Table':
        key = self._table_key(key)
        fields = object.__getattribute__(self, '_fields')
        fields[key] = value if isinstance(value, Table) else make_value(value)
        return self

    def get_by_key(self, key: Any) -> 'Table':
        resolved = self.raw_get(key)
        if resolved._kind != 'nil':
            return resolved

        metatable = object.__getattribute__(self, '_metatable')
        if isinstance(metatable, Table):
            index_handler = metatable.raw_get('_index_')
            if index_handler._kind != 'nil':
                if index_handler._kind == 'table':
                    return index_handler.get_by_key(key)
                return index_handler(self, make_value(key))
        return make_nil()

    def set_by_key(self, key: Any, value: Any):
        existing = self.raw_get(key)
        if existing._kind != 'nil':
            self.raw_set(key, value)
            return

        metatable = object.__getattribute__(self, '_metatable')
        if isinstance(metatable, Table):
            newindex_handler = metatable.raw_get('_newindex_')
            if newindex_handler._kind != 'nil':
                if newindex_handler._kind == 'table':
                    newindex_handler.set_by_key(key, value)
                    return
                newindex_handler(self, make_value(key), make_value(value))
                return
        self.raw_set(key, value)

    def __call__(self, *args):
        fields = object.__getattribute__(self, '_fields')
        if '_call_' in fields:
            call_val = fields['_call_']
            if isinstance(call_val, Table) and call_val._kind == 'function':
                return call_val(*args)
            if callable(call_val):
                result = call_val(*args)
                return make_value(result) if not isinstance(result, Table) else result
            return make_value(call_val)

        metatable = object.__getattribute__(self, '_metatable')
        if isinstance(metatable, Table):
            mt_fields = object.__getattribute__(metatable, '_fields')
            if '_call_' in mt_fields:
                call_handler = mt_fields['_call_']
                if isinstance(call_handler, Table) and call_handler._kind == 'function':
                    return call_handler(self, *args)
                if callable(call_handler):
                    result = call_handler(self, *args)
                    return make_value(result) if not isinstance(result, Table) else result

        self_key = fields.get('_self_')
        if isinstance(self_key, str) and self_key in fields:
            val = fields[self_key]
            return make_value(val) if not isinstance(val, Table) else val
        return make_nil()

    def get_str(self) -> str:
        fields = object.__getattribute__(self, '_fields')
        str_val = fields.get('_str_')
        if isinstance(str_val, str):
            return str_val
        self_key = fields.get('_self_')
        if isinstance(self_key, str) and self_key in fields:
            core = fields[self_key]
            auto = str(core) if not isinstance(core, Table) else core.get_str()
            fields['_str_'] = auto
            return auto
        return 'nil'

    def _coerce_number(self) -> Optional[float]:
        if self._kind == 'number':
            return float(self._payload)

        fields = object.__getattribute__(self, '_fields')
        num_val = fields.get('_num_')
        if isinstance(num_val, Table):
            if num_val._kind == 'number':
                return float(num_val._payload)
        elif isinstance(num_val, (int, float)):
            return float(num_val)

        self_key = fields.get('_self_')
        if isinstance(self_key, str) and self_key in fields:
            core = fields[self_key]
            if isinstance(core, Table):
                return core._coerce_number()
            if isinstance(core, (int, float)):
                return float(core)
        return None

    def __str__(self) -> str:
        return self.get_str()

    def __repr__(self) -> str:
        return f"<Table {self._kind} {self.get_str()}>"

    # Metamethods (add/sub/etc. can be Python callable OR a function Table)
    def _call_magic(self, name: str, other: 'Table') -> 'Table':
        magic = self.raw_get(name)
        if magic._kind == 'nil':
            metatable = object.__getattribute__(self, '_metatable')
            if isinstance(metatable, Table):
                magic = metatable.raw_get(name)
        if magic._kind != 'nil':
            if isinstance(magic, Table) and magic._kind == 'function':
                return magic(self, other)
            if callable(magic):
                result = magic(self, other)
                return make_value(result) if not isinstance(result, Table) else result
            return make_value(magic)
        return None

    def __add__(self, other: Any) -> 'Table':
        other = make_value(other)
        res = self._call_magic('_add_', other)
        if res is not None:
            return res
        left_num = self._coerce_number()
        right_num = other._coerce_number()
        if left_num is not None and right_num is not None:
            return make_number(left_num + right_num)
        raise TypeError(f"cannot add {self} and {other}")

    def __sub__(self, other: Any) -> 'Table':
        other = make_value(other)
        res = self._call_magic('_sub_', other)
        if res is not None:
            return res
        left_num = self._coerce_number()
        right_num = other._coerce_number()
        if left_num is not None and right_num is not None:
            return make_number(left_num - right_num)
        raise TypeError(f"cannot subtract {self} and {other}")

    def __mul__(self, other: Any) -> 'Table':
        other = make_value(other)
        res = self._call_magic('_mul_', other)
        if res is not None:
            return res
        left_num = self._coerce_number()
        right_num = other._coerce_number()
        if left_num is not None and right_num is not None:
            return make_number(left_num * right_num)
        raise TypeError(f"cannot multiply {self} and {other}")

    def __truediv__(self, other: Any) -> 'Table':
        other = make_value(other)
        res = self._call_magic('_div_', other)
        if res is not None:
            return res
        left_num = self._coerce_number()
        right_num = other._coerce_number()
        if left_num is not None and right_num is not None:
            return make_number(left_num / right_num)
        raise TypeError(f"cannot divide {self} and {other}")

    def __mod__(self, other: Any) -> 'Table':
        other = make_value(other)
        res = self._call_magic('_mod_', other)
        if res is not None:
            return res
        left_num = self._coerce_number()
        right_num = other._coerce_number()
        if left_num is not None and right_num is not None:
            return make_number(left_num % right_num)
        raise TypeError(f"cannot mod {self} and {other}")

    def __pow__(self, other: Any) -> 'Table':
        other = make_value(other)
        res = self._call_magic('_pow_', other)
        if res is not None:
            return res
        left_num = self._coerce_number()
        right_num = other._coerce_number()
        if left_num is not None and right_num is not None:
            return make_number(left_num ** right_num)
        raise TypeError(f"cannot pow {self} and {other}")

    def __eq__(self, other: Any) -> bool:
        other = make_value(other)
        res = self._call_magic('_eq_', other)
        if res is not None:
            return bool(res)
        if self._kind == other._kind and self._kind in ('number', 'string', 'boolean'):
            return self._payload == other._payload
        return False

    def __lt__(self, other: Any) -> bool:
        other = make_value(other)
        res = self._call_magic('_lt_', other)
        if res is not None:
            return bool(res)
        left_num = self._coerce_number()
        right_num = other._coerce_number()
        if left_num is not None and right_num is not None:
            return left_num < right_num
        raise TypeError(f"cannot compare < {self} and {other}")

    def __le__(self, other: Any) -> bool:
        other = make_value(other)
        res = self._call_magic('_le_', other)
        if res is not None:
            return bool(res)
        left_num = self._coerce_number()
        right_num = other._coerce_number()
        if left_num is not None and right_num is not None:
            return left_num <= right_num
        raise TypeError(f"cannot compare <= {self} and {other}")

    def __bool__(self) -> bool:
        fields = object.__getattribute__(self, '_fields')
        if '_bool_' in fields:
            bool_val = fields['_bool_']
            if isinstance(bool_val, Table):
                return bool(bool_val)
            return bool(bool_val)

        self_key = fields.get('_self_')
        if isinstance(self_key, str) and self_key in fields:
            core = fields[self_key]
            resolved = bool(core) if isinstance(core, Table) else bool(core)
            fields['_bool_'] = resolved
            return resolved

        if self._kind == 'nil':
            return False
        return True


# =============================================================================
# VALUE FACTORY
# =============================================================================
def make_nil() -> Table:
    return Table('nil')

def make_bool(b: bool) -> Table:
    t = Table('boolean', bool(b))
    t._setup_builtins()
    return t

def make_number(n: float) -> Table:
    t = Table('number', float(n))
    t._setup_builtins()
    return t

def make_string(s: str) -> Table:
    t = Table('string', str(s))
    t._setup_builtins()
    return t

def make_function(py_callable: Callable) -> Table:
    t = Table('function')
    t._fields['_call_'] = py_callable
    t._setup_builtins()
    return t

def make_array(items: List[Any]) -> Table:
    t = Table('table')
    for i, v in enumerate(items, 1):
        t._fields[i] = v if isinstance(v, Table) else make_value(v)
    return t

def make_value(v: Any) -> Table:
    if isinstance(v, Table):
        return v
    if v is None:
        return make_nil()
    if isinstance(v, bool):
        return make_bool(v)
    if isinstance(v, (int, float)):
        return make_number(v)
    if isinstance(v, str):
        return make_string(v)
    if callable(v):
        return make_function(v)
    if isinstance(v, list):
        return make_array(v)
    if isinstance(v, dict):
        t = Table('table')
        for k, val in v.items():
            t.raw_set(k, val)
        return t
    raise ValueError(f"Cannot convert {type(v)} to Table")


# =============================================================================
# 'but' MIXIN
# =============================================================================
def but(left: Any, right: Any) -> Table:
    left = make_value(left)
    right = make_value(right)
    new = Table(left._kind, left._payload)
    new._fields = object.__getattribute__(left, '_fields').copy()
    right_fields = object.__getattribute__(right, '_fields')
    for key, value in right_fields.items():
        if key == '_self_':
            continue
        new._fields[key] = value
    return new


# =============================================================================
# LEXER
# =============================================================================
class Token:
    def __init__(self, typ: str, val: str):
        self.type = typ
        self.value = val

    def __repr__(self):
        return f"Token({self.type}, {self.value!r})"


class Lexer:
    def __init__(self, text: str):
        self.text = text
        self.tokens: List[Token] = []
        self._tokenize()

    def _tokenize(self):
        token_spec = [
            ('NUMBER',   r'\d+\.?\d*|\.\d+'),
            ('STRING',   r'"([^"\\]|\\.)*"|\'([^\'\\]|\\.)*\''), 
            ('BUT',      r'\bbut\b'),
            ('KEYWORD',  r'\b(if|elseif|else|end|then|while|do|for|repeat|until|local|function|return|and|or|not|true|false|nil)\b'),
            ('IDENT',    r'[a-zA-Z_][a-zA-Z0-9_]*'),
            ('COMMENT',  r'--.*'),
            ('OP',       r'==|~=|<=|>=|::|\.\.|->|\+|-|\*|/|%|\^|#|<|>|<=|>=|=|,|;|\.|\[|\]|\{|\}|\(|\)'),
            ('WHITESPACE', r'\s+'),
        ]
        pattern = '|'.join(f'(?P<{name}>{regex})' for name, regex in token_spec)
        for mo in re.finditer(pattern, self.text, re.MULTILINE):
            kind = mo.lastgroup
            value = mo.group(kind)
            if kind in ('WHITESPACE', 'COMMENT'):
                continue
            if kind == 'STRING':
                value = value[1:-1].replace('\\"', '"').replace("\\'", "'")
                self.tokens.append(Token('STRING', value))
            elif kind == 'NUMBER':
                self.tokens.append(Token('NUMBER', value))
            elif kind == 'BUT':
                self.tokens.append(Token('OP', 'but'))
            else:
                self.tokens.append(Token(kind, value))
        self.tokens.append(Token('EOF', ''))


# =============================================================================
# AST
# =============================================================================
class ASTNode: pass

class Literal(ASTNode):
    def __init__(self, kind: str, value: Any):
        self.kind = kind
        self.value = value

class Variable(ASTNode):
    def __init__(self, name: str):
        self.name = name

class BinOp(ASTNode):
    def __init__(self, op: str, left: ASTNode, right: ASTNode):
        self.op = op
        self.left = left
        self.right = right

class ButOp(ASTNode):
    def __init__(self, left: ASTNode, right: ASTNode):
        self.left = left
        self.right = right

class FieldAccess(ASTNode):
    def __init__(self, obj: ASTNode, key: Union[str, ASTNode]):
        self.obj = obj
        self.key = key

class Call(ASTNode):
    def __init__(self, func: ASTNode, args: List[ASTNode]):
        self.func = func
        self.args = args

class TableConstructor(ASTNode):
    def __init__(self, fields: List[tuple], array_items: List[ASTNode]):
        self.fields = fields
        self.array_items = array_items

class AssignStmt(ASTNode):
    def __init__(self, left: ASTNode, right: ASTNode, is_local: bool = False):
        self.left = left
        self.right = right
        self.is_local = is_local

class IfStmt(ASTNode):
    def __init__(self, condition: ASTNode, then_block: List[ASTNode],
                 elseif: List[tuple], else_block: Optional[List[ASTNode]]):
        self.condition = condition
        self.then_block = then_block
        self.elseif = elseif
        self.else_block = else_block

class WhileStmt(ASTNode):
    def __init__(self, condition: ASTNode, block: List[ASTNode]):
        self.condition = condition
        self.block = block

class RepeatStmt(ASTNode):
    def __init__(self, block: List[ASTNode], until_condition: ASTNode):
        self.block = block
        self.until_condition = until_condition

class ForStmt(ASTNode):
    def __init__(self, var: str, start: ASTNode, stop: ASTNode, step: ASTNode, block: List[ASTNode]):
        self.var = var
        self.start = start
        self.stop = stop
        self.step = step
        self.block = block

class FunctionDef(ASTNode):
    def __init__(self, name: str, params: List[str], block: List[ASTNode]):
        self.name = name
        self.params = params
        self.block = block

class FunctionLiteral(ASTNode):          # NEW: anonymous functions
    def __init__(self, params: List[str], block: List[ASTNode]):
        self.params = params
        self.block = block

class ReturnStmt(ASTNode):
    def __init__(self, expr: Optional[ASTNode]):
        self.expr = expr

class ExprStmt(ASTNode):
    def __init__(self, expr: ASTNode):
        self.expr = expr


# =============================================================================
# PARSER (FIXED operator loops + table ctors + anonymous functions)
# =============================================================================
class Parser:
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0

    def current(self) -> Token:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else Token('EOF', '')

    def peek(self, offset: int = 1) -> Token:
        idx = self.pos + offset
        return self.tokens[idx] if idx < len(self.tokens) else Token('EOF', '')

    def advance(self):
        self.pos += 1

    def match(self, typ: str, val: Optional[str] = None) -> Optional[Token]:
        tok = self.current()
        if tok.type == typ and (val is None or tok.value == val):
            self.advance()
            return tok
        return None

    def expect(self, typ: str, val: Optional[str] = None) -> Token:
        tok = self.match(typ, val)
        if not tok:
            raise SyntaxError(f"Expected {typ} {val!r}, got {self.current()}")
        return tok

    def parse_program(self) -> List[ASTNode]:
        stmts = []
        while self.current().type != 'EOF':
            stmts.append(self.parse_statement())
        return stmts

    def parse_block(self) -> List[ASTNode]:
        stmts = []
        while self.current().type != 'EOF':
            if self.current().value in ('end', 'elseif', 'else', 'until'):
                break
            stmts.append(self.parse_statement())
        return stmts

    def parse_statement(self) -> ASTNode:
        if self.match('KEYWORD', 'local'):
            return self.parse_local_assign()
        if self.match('KEYWORD', 'if'):
            return self.parse_if()
        if self.match('KEYWORD', 'while'):
            return self.parse_while()
        if self.match('KEYWORD', 'repeat'):
            return self.parse_repeat()
        if self.match('KEYWORD', 'for'):
            return self.parse_for()
        if self.match('KEYWORD', 'do'):
            block = self.parse_block()
            self.expect('KEYWORD', 'end')
            return ExprStmt(Literal('nil', None))
        if self.match('KEYWORD', 'function'):
            return self.parse_function_def(is_local=False)
        if self.match('KEYWORD', 'return'):
            expr = self.parse_expression() if self.current().type != 'EOF' else None
            return ReturnStmt(expr)
        left = self.parse_expression()
        if self.match('OP', '='):
            right = self.parse_expression()
            return AssignStmt(left, right)
        return ExprStmt(left)

    def parse_local_assign(self) -> ASTNode:
        left = self.parse_expression()
        self.expect('OP', '=')
        right = self.parse_expression()
        return AssignStmt(left, right, is_local=True)

    def parse_if(self) -> IfStmt:
        cond = self.parse_expression()
        self.expect('KEYWORD', 'then')
        then_block = self.parse_block()
        elseif = []
        while self.match('KEYWORD', 'elseif'):
            econd = self.parse_expression()
            self.expect('KEYWORD', 'then')
            eblock = self.parse_block()
            elseif.append((econd, eblock))
        else_block = None
        if self.match('KEYWORD', 'else'):
            else_block = self.parse_block()
        self.expect('KEYWORD', 'end')
        return IfStmt(cond, then_block, elseif, else_block)

    def parse_while(self) -> WhileStmt:
        cond = self.parse_expression()
        self.expect('KEYWORD', 'do')
        block = self.parse_block()
        self.expect('KEYWORD', 'end')
        return WhileStmt(cond, block)

    def parse_repeat(self) -> RepeatStmt:
        block = self.parse_block()
        self.expect('KEYWORD', 'until')
        cond = self.parse_expression()
        return RepeatStmt(block, cond)

    def parse_for(self) -> ForStmt:
        var = self.expect('IDENT').value
        self.expect('OP', '=')
        start = self.parse_expression()
        self.expect('OP', ',')
        stop = self.parse_expression()
        step = Literal('number', 1)
        if self.match('OP', ','):
            step = self.parse_expression()
        self.expect('KEYWORD', 'do')
        block = self.parse_block()
        self.expect('KEYWORD', 'end')
        return ForStmt(var, start, stop, step, block)

    def parse_function_def(self, is_local: bool = False) -> FunctionDef:
        name = self.expect('IDENT').value
        self.expect('OP', '(')
        params = []
        while not self.match('OP', ')'):
            if self.current().type == 'IDENT':
                params.append(self.current().value)
                self.advance()
            if not self.match('OP', ','):
                break
        self.expect('OP', ')')
        block = self.parse_block()
        self.expect('KEYWORD', 'end')
        return FunctionDef(name, params, block)

    # -------------------------- Expressions --------------------------
    def parse_expression(self) -> ASTNode:
        return self.parse_but()

    def parse_but(self) -> ASTNode:
        left = self.parse_or()
        while self.match('OP', 'but'):
            right = self.parse_or()
            left = ButOp(left, right)
        return left

    def parse_or(self) -> ASTNode:
        left = self.parse_and()
        while self.match('KEYWORD', 'or'):
            right = self.parse_and()
            left = BinOp('or', left, right)
        return left

    def parse_and(self) -> ASTNode:
        left = self.parse_cmp()
        while self.match('KEYWORD', 'and'):
            right = self.parse_cmp()
            left = BinOp('and', left, right)
        return left

    def parse_cmp(self) -> ASTNode:
        left = self.parse_add()
        ops = {'<', '>', '<=', '>=', '==', '~='}
        while True:
            op_tok = self.current()
            if op_tok.type != 'OP' or op_tok.value not in ops:
                break
            self.advance()
            right = self.parse_add()
            left = BinOp(op_tok.value, left, right)
        return left

    def parse_add(self) -> ASTNode:
        left = self.parse_mul()
        ops = {'+', '-', '..'}          # .. added (string concat)
        while True:
            op_tok = self.current()
            if op_tok.type != 'OP' or op_tok.value not in ops:
                break
            self.advance()
            right = self.parse_mul()
            left = BinOp(op_tok.value, left, right)
        return left

    def parse_mul(self) -> ASTNode:
        left = self.parse_unary()
        ops = {'*', '/', '%'}
        while True:
            op_tok = self.current()
            if op_tok.type != 'OP' or op_tok.value not in ops:
                break
            self.advance()
            right = self.parse_unary()
            left = BinOp(op_tok.value, left, right)
        return left

    def parse_unary(self) -> ASTNode:
        if self.match('KEYWORD', 'not'):
            return BinOp('not', self.parse_unary(), None)
        op_tok = self.current()
        if op_tok.type == 'OP' and op_tok.value in ('-', '#'):
            self.advance()
            return BinOp(op_tok.value, self.parse_unary(), None)
        return self.parse_postfix()

    def parse_postfix(self) -> ASTNode:
        left = self.parse_primary()
        while True:
            if self.match('OP', '.'):
                ident = self.expect('IDENT').value
                left = FieldAccess(left, ident)
            elif self.match('OP', '['):
                key = self.parse_expression()
                self.expect('OP', ']')
                left = FieldAccess(left, key)
            elif self.match('OP', '('):
                args = []
                if self.current().value != ')':
                    args.append(self.parse_expression())
                    while self.match('OP', ','):
                        args.append(self.parse_expression())
                self.expect('OP', ')')
                left = Call(left, args)
            else:
                break
        return left

    def parse_primary(self) -> ASTNode:
        if tok := self.match('NUMBER'):
            return Literal('number', float(tok.value))
        if tok := self.match('STRING'):
            return Literal('string', tok.value)
        if self.match('KEYWORD', 'true'):
            return Literal('boolean', True)
        if self.match('KEYWORD', 'false'):
            return Literal('boolean', False)
        if self.match('KEYWORD', 'nil'):
            return Literal('nil', None)
        if tok := self.match('IDENT'):
            return Variable(tok.value)
        if self.match('OP', '('):
            expr = self.parse_expression()
            self.expect('OP', ')')
            return expr
        if self.match('OP', '{'):
            return self.parse_table_constructor()
        if self.match('KEYWORD', 'function'):          # NEW: anonymous functions
            return self._parse_function_literal()
        raise SyntaxError(f"Unexpected token in primary: {self.current()}")

    def _parse_function_literal(self) -> FunctionLiteral:
        self.expect('OP', '(')
        params = []
        while not self.match('OP', ')'):
            if self.current().type == 'IDENT':
                params.append(self.current().value)
                self.advance()
            if not self.match('OP', ','):
                break
        self.expect('OP', ')')
        block = self.parse_block()
        self.expect('KEYWORD', 'end')
        return FunctionLiteral(params, block)

    def parse_table_constructor(self) -> TableConstructor:
        fields = []
        array_items = []
        while self.current().value not in ('}', 'EOF'):
            if self.match('OP', '['):
                key = self.parse_expression()
                self.expect('OP', ']')
                self.expect('OP', '=')
                val = self.parse_expression()
                fields.append((key, val))
            elif self.current().type == 'IDENT' and self.peek().value == '=':
                key = self.current().value
                self.advance()
                self.expect('OP', '=')
                val = self.parse_expression()
                fields.append((key, val))
            else:
                array_items.append(self.parse_expression())
            self.match('OP', ',') or self.match('OP', ';')
        self.expect('OP', '}')
        return TableConstructor(fields, array_items)


# =============================================================================
# INTERPRETER (FIXED return support + table ctor + metamethods)
# =============================================================================
class Interpreter:
    def __init__(self):
        self.global_env: Dict[str, Table] = {}
        self.global_env['print'] = make_function(
            lambda *args: print(' '.join(a.get_str() for a in args)) or make_nil()
        )
        self.global_env['str'] = make_function(
            lambda value: make_string(value.get_str() if isinstance(value, Table) else str(value))
        )
        self.global_env['but'] = make_function(lambda l, r: but(l, r))
        self.global_env['setmetatable'] = make_function(self._set_metatable)
        self.global_env['getmetatable'] = make_function(self._get_metatable)
        self.global_env['rawget'] = make_function(self._raw_get)
        self.global_env['rawset'] = make_function(self._raw_set)

    def _set_metatable(self, target: Table, metatable: Table) -> Table:
        target._metatable = metatable
        return target

    def _get_metatable(self, target: Table) -> Table:
        mt = target._metatable
        return mt if isinstance(mt, Table) else make_nil()

    def _raw_get(self, target: Table, key: Table) -> Table:
        return target.raw_get(key)

    def _raw_set(self, target: Table, key: Table, value: Table) -> Table:
        target.raw_set(key, value)
        return target

    def execute(self, program: List[ASTNode], capture_results: bool = False) -> List[Table]:
        env = self.global_env
        results: List[Table] = []
        for stmt in program:
            if isinstance(stmt, ExprStmt):
                value = self._eval_expr(stmt.expr, env)
            else:
                ret = self._exec_stmt(stmt, env)
                value = ret if ret is not None else make_nil()
            if capture_results:
                results.append(value if isinstance(value, Table) else make_value(value))
        return results

    def _exec_stmt(self, stmt: ASTNode, env: Dict[str, Table]) -> Optional[Table]:
        if isinstance(stmt, AssignStmt):
            value = self._eval_expr(stmt.right, env)
            if isinstance(stmt.left, Variable):
                env[stmt.left.name] = value
            elif isinstance(stmt.left, FieldAccess):
                obj = self._eval_expr(stmt.left.obj, env)
                key = self._key_to_str(stmt.left.key, env)
                obj.set_by_key(key, value)
            return None
        elif isinstance(stmt, IfStmt):
            if bool(self._eval_expr(stmt.condition, env)):
                for s in stmt.then_block:
                    ret = self._exec_stmt(s, env)
                    if ret is not None:
                        return ret
            else:
                for econd, eblock in stmt.elseif:
                    if bool(self._eval_expr(econd, env)):
                        for s in eblock:
                            ret = self._exec_stmt(s, env)
                            if ret is not None:
                                return ret
                        break
                else:
                    if stmt.else_block:
                        for s in stmt.else_block:
                            ret = self._exec_stmt(s, env)
                            if ret is not None:
                                return ret
            return None
        elif isinstance(stmt, WhileStmt):
            while bool(self._eval_expr(stmt.condition, env)):
                for s in stmt.block:
                    ret = self._exec_stmt(s, env)
                    if ret is not None:
                        return ret   # (early return not propagated in loops for this prototype)
            return None
        elif isinstance(stmt, RepeatStmt):
            while True:
                for s in stmt.block:
                    ret = self._exec_stmt(s, env)
                    if ret is not None:
                        return ret
                if bool(self._eval_expr(stmt.until_condition, env)):
                    break
            return None
        elif isinstance(stmt, ForStmt):
            start = float(self._eval_expr(stmt.start, env)._payload)
            stop = float(self._eval_expr(stmt.stop, env)._payload)
            step = float(self._eval_expr(stmt.step, env)._payload)
            i = start
            while (i <= stop) if step > 0 else (i >= stop):
                env[stmt.var] = make_number(i)
                for s in stmt.block:
                    ret = self._exec_stmt(s, env)
                    if ret is not None:
                        return ret
                i += step
            return None
        elif isinstance(stmt, FunctionDef):
            def py_func(*args):
                local_env = env.copy()
                for p, a in zip(stmt.params, args):
                    local_env[p] = a if isinstance(a, Table) else make_value(a)
                for s in stmt.block:
                    ret = self._exec_stmt(s, local_env)
                    if ret is not None:
                        return ret
                return make_nil()
            env[stmt.name] = make_function(py_func)
            return None
        elif isinstance(stmt, ReturnStmt):
            if stmt.expr:
                return self._eval_expr(stmt.expr, env)
            return make_nil()
        elif isinstance(stmt, ExprStmt):
            self._eval_expr(stmt.expr, env)
            return None
        return None

    def _key_to_str(self, key_node: Union[str, ASTNode], env: Dict[str, Table]) -> Any:
        if isinstance(key_node, str):
            return key_node
        key_val = self._eval_expr(key_node, env)
        return Table._table_key(key_val)

    def _eval_expr(self, expr: ASTNode, env: Dict[str, Table]) -> Table:
        if isinstance(expr, Literal):
            if expr.kind == 'number':
                return make_number(expr.value)
            if expr.kind == 'string':
                return make_string(expr.value)
            if expr.kind == 'boolean':
                return make_bool(expr.value)
            if expr.kind == 'nil':
                return make_nil()
            return make_nil()

        if isinstance(expr, Variable):
            return env.get(expr.name, make_nil())

        if isinstance(expr, BinOp):
            left = self._eval_expr(expr.left, env)
            if expr.op in ('and', 'or'):
                if expr.op == 'and':
                    return left if not bool(left) else self._eval_expr(expr.right, env)
                return left if bool(left) else self._eval_expr(expr.right, env)
            if expr.op == 'not':
                return make_bool(not bool(left))
            if expr.op == '-':
                if expr.right is None:
                    return make_number(-float(left._payload))
            if expr.op == '#':
                if left._kind == 'string':
                    return make_number(len(left._payload))
                if left._kind == 'table':
                    n = 0
                    while left.raw_get(n + 1)._kind != 'nil':
                        n += 1
                    return make_number(n)
                return make_number(0)
            right = self._eval_expr(expr.right, env)
            if expr.op == '..':
                lstr = left.get_str() if isinstance(left, Table) else str(left)
                rstr = right.get_str() if isinstance(right, Table) else str(right)
                return make_string(lstr + rstr)
            if expr.op == '+': return left + right
            if expr.op == '-': return left - right
            if expr.op == '*': return left * right
            if expr.op == '/': return left / right
            if expr.op == '%': return left % right
            if expr.op == '^': return left ** right
            if expr.op == '==': return make_bool(left == right)
            if expr.op == '~=': return make_bool(left != right)
            if expr.op == '<':  return make_bool(left < right)
            if expr.op == '>':  return make_bool(left > right)
            if expr.op == '<=': return make_bool(left <= right)
            if expr.op == '>=': return make_bool(left >= right)
            return make_nil()

        if isinstance(expr, ButOp):
            left = self._eval_expr(expr.left, env)
            right = self._eval_expr(expr.right, env)
            return but(left, right)

        if isinstance(expr, FieldAccess):
            obj = self._eval_expr(expr.obj, env)
            key = self._key_to_str(expr.key, env)
            return obj.get_by_key(key)

        if isinstance(expr, Call):
            func = self._eval_expr(expr.func, env)
            args = [self._eval_expr(a, env) for a in expr.args]
            return func(*args)

        if isinstance(expr, TableConstructor):
            t = Table('table')
            for index, item in enumerate(expr.array_items, 1):
                t.raw_set(index, self._eval_expr(item, env))
            for k_node, v_node in expr.fields:
                key = self._key_to_str(k_node, env)
                val = self._eval_expr(v_node, env)
                t.set_by_key(key, val)
            return t

        if isinstance(expr, FunctionLiteral):
            def py_func(*call_args):
                local_env = env.copy()
                for p, a in zip(expr.params, call_args):
                    local_env[p] = a if isinstance(a, Table) else make_value(a)
                for s in expr.block:
                    ret = self._exec_stmt(s, local_env)
                    if ret is not None:
                        return ret
                return make_nil()
            return make_function(py_func)

        return make_nil()


# =============================================================================
# RUNNER
# =============================================================================
def run_code(source: str):
    lexer = Lexer(source)
    parser = Parser(lexer.tokens)
    program = parser.parse_program()
    interp = Interpreter()
    interp.execute(program)


def _block_delta(source: str) -> int:
    delta = 0
    tokens = Lexer(source).tokens
    for tok in tokens:
        if tok.type != 'KEYWORD':
            continue
        if tok.value in {'if', 'while', 'for', 'function', 'do', 'repeat'}:
            delta += 1
        elif tok.value in {'end', 'until'}:
            delta -= 1
    return delta


def _expected_indent(block_depth: int, line: str) -> int:
    stripped = line.strip()
    if stripped.startswith('end') or stripped.startswith('until'):
        return max(block_depth - 1, 0) * 3
    return max(block_depth, 0) * 3


def _normalize_line_indent(block_depth: int, line: str) -> str:
    stripped = line.strip()
    if not stripped:
        return ''
    return (' ' * _expected_indent(block_depth, line)) + stripped


def _read_repl_line(prompt: str, block_depth: int) -> str:
    seed = ' ' * (block_depth * 3)

    def startup_hook():
        if seed:
            readline.insert_text(seed)
            readline.redisplay()

    readline.set_startup_hook(startup_hook)
    try:
        return input(prompt)
    finally:
        readline.set_startup_hook()


def repl():
    print("Lux REPL (type 'exit' or 'quit' to leave)")
    interp = Interpreter()
    buffer: List[str] = []
    block_depth = 0

    while True:
        prompt = '>>> ' if block_depth == 0 else '... '
        try:
            line = _read_repl_line(prompt, block_depth)
        except EOFError:
            print()
            break

        stripped = line.strip()
        if block_depth == 0 and not stripped:
            continue
        if block_depth == 0 and stripped in ("exit", "quit"):
            break

        line = _normalize_line_indent(block_depth, line)
        buffer.append(line)
        block_depth += _block_delta(line)

        if block_depth > 0:
            continue
        if block_depth < 0:
            print("Error: unexpected block terminator")
            buffer.clear()
            block_depth = 0
            continue

        source = "\n".join(buffer)
        try:
            lexer = Lexer(source)
            parser = Parser(lexer.tokens)
            program = parser.parse_program()
            for result in interp.execute(program, capture_results=True):
                print(result.get_str() if isinstance(result, Table) else str(result))
        except Exception as exc:
            print(f"Error: {exc}")
        finally:
            buffer.clear()
            block_depth = 0


# =============================================================================
# ENTRYPOINT
# =============================================================================
if __name__ == "__main__":
    first_arg = sys.argv[1] if len(sys.argv) > 1 else None
    if first_arg and Path(first_arg).is_file():
        with open(first_arg, "r", encoding="utf-8") as f:
            run_code(f.read())
    else:
        repl()
