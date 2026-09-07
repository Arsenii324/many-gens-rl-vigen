"""Every global name each eval_grid function uses must actually exist at module level.

Twice in one day a change to `scripts/eval_grid.py` passed its tests and then raised at runtime:

    NameError: name 'declared_image_size' is not defined

`_run_grid` referenced a local of `main()`. Every rlvigen cell in two separate validation waves
failed on it, while the other six families passed the identical wave because they take earlier
branches of the same dispatch. Both changes were covered by tests that read the source as TEXT, and
a text test cannot see a name resolved at call time.

This is the cheap general guard: compile the module and check that every global name each function
references is either a module attribute or a builtin. It catches the exact class of defect --
a function reaching for something only another function defines -- without importing torch, JAX or
any family's dependencies.
"""
from __future__ import annotations

import builtins
import pathlib
import symtable

ROOT = pathlib.Path(__file__).resolve().parents[1]
TARGETS = ("scripts/eval_grid.py", "scripts/eval_across_scenes.py",
           "datasphere/native/family.py", "datasphere/native/plan_production.py")


def _unresolved(path: pathlib.Path) -> list[str]:
    source = path.read_text()
    table = symtable.symtable(source, str(path), "exec")
    module_names = set(table.get_identifiers()) | set(dir(builtins))
    problems = []

    def walk(node, trail):
        for child in node.get_children():
            if child.get_type() == "function":
                local = set(child.get_identifiers())
                for symbol in child.get_symbols():
                    name = symbol.get_name()
                    # A GLOBAL reference the module never defines is the failure we want. Locals,
                    # parameters, imports inside the function and closure variables are all fine.
                    if (symbol.is_global() and not symbol.is_assigned()
                            and name not in module_names):
                        problems.append(f"{'.'.join(trail + [child.get_name()])}: {name}")
                del local
            walk(child, trail + [child.get_name()] if child.get_type() == "function" else trail)

    walk(table, [])
    return problems


def test_no_function_reaches_for_a_name_the_module_does_not_define():
    failures = {}
    for relative in TARGETS:
        path = ROOT / relative
        if not path.is_file():
            continue
        problems = _unresolved(path)
        if problems:
            failures[relative] = problems
    assert not failures, (
        "a function references a global the module never defines; this is the "
        "`declared_image_size` class of defect, which raises only when that branch runs:\n"
        + "\n".join(f"  {k}: {v}" for k, v in failures.items()))
