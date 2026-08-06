"""Role Matrix — dashboard module registry.

Only the Trainer role is ever meaningfully restricted here. Admins always
get full access in code (see require_module in app/api/deps.py) so the
Head Coach / Super Admin account can never accidentally lock itself out
of its own console by mis-toggling a rule.

"Messages" is intentionally not a module here: it's a shared client <->
trainer channel a trainer needs for their own assigned clients regardless
of role, not a business record like Payments or Site Content, so it isn't
something the Role Matrix hides.

MODULE_KEYS / DEFAULT_TRAINER_ACCESS double as the fallback used whenever
a role_permissions row hasn't been seeded yet for some reason, so these
defaults are the real security boundary, not just seed-script window
dressing — see require_module.
"""
from typing import NamedTuple


class ModuleDef(NamedTuple):
    key: str
    label: str
    default_trainer_access: bool


MODULES: list[ModuleDef] = [
    ModuleDef("overview", "Overview", True),
    ModuleDef("clients", "Clients", True),
    ModuleDef("bookings", "Bookings", True),
    ModuleDef("payments", "Payments", False),
    ModuleDef("content", "Site Content", False),
]

MODULE_KEYS: tuple[str, ...] = tuple(m.key for m in MODULES)
MODULE_LABELS: dict[str, str] = {m.key: m.label for m in MODULES}
DEFAULT_TRAINER_ACCESS: dict[str, bool] = {m.key: m.default_trainer_access for m in MODULES}