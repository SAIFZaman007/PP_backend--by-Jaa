"""
Role Matrix — dashboard module registry.
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
    ModuleDef("notes", "Client Notes", True),
    ModuleDef("nutrition", "Nutrition Plans", True),
    ModuleDef("workouts", "Workout Plans", True),
    ModuleDef("payments", "Payments", False),
    ModuleDef("content", "Site Content", False),
]

MODULE_KEYS: tuple[str, ...] = tuple(m.key for m in MODULES)
MODULE_LABELS: dict[str, str] = {m.key: m.label for m in MODULES}
DEFAULT_TRAINER_ACCESS: dict[str, bool] = {m.key: m.default_trainer_access for m in MODULES}