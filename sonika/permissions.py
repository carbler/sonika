from enum import Enum, auto
from typing import Optional

class PermissionMode(Enum):
    PLAN = auto()
    ASK = auto()
    AUTO = auto()

class PermissionManager:
    def __init__(self, mode: PermissionMode = PermissionMode.ASK):
        self.current_mode = mode

    def set_mode(self, mode: PermissionMode):
        self.current_mode = mode

    def cycle_mode(self):
        if self.current_mode == PermissionMode.PLAN:
            self.current_mode = PermissionMode.ASK
        elif self.current_mode == PermissionMode.ASK:
            self.current_mode = PermissionMode.AUTO
        else:
            self.current_mode = PermissionMode.PLAN
        return self.current_mode

    def get_mode_name(self) -> str:
        if self.current_mode == PermissionMode.PLAN:
            return "PLAN"
        elif self.current_mode == PermissionMode.ASK:
            return "ASK"
        else:
            return "AUTO"

    def should_ask(self) -> bool:
        return self.current_mode == PermissionMode.ASK

    def should_execute(self) -> bool:
        return self.current_mode != PermissionMode.PLAN
