"""CronTool — gestión de crontabs y launchd plists para macOS/Linux."""

from __future__ import annotations

import os
import re
import subprocess
import textwrap
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Literal, Optional

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field


# ── Input schema ──────────────────────────────────────────────────────────────

class CronInput(BaseModel):
    action: Literal["list", "add", "remove", "validate", "generate_plist"] = Field(
        description=(
            "Action to perform: "
            "'list' — show current crontab entries; "
            "'validate' — check a cron expression syntax and show next runs; "
            "'add' — add a new cron entry (requires expression + command); "
            "'remove' — remove entries matching a command pattern; "
            "'generate_plist' — generate a macOS launchd .plist file (requires plist_label + command)."
        )
    )
    expression: Optional[str] = Field(
        default=None,
        description="Cron expression with 5 fields: 'min hour day month weekday'. Example: '0 9 * * 1-5'",
    )
    command: Optional[str] = Field(
        default=None,
        description="Shell command to schedule or match for removal.",
    )
    description: Optional[str] = Field(
        default=None,
        description="Optional comment to add above the crontab entry.",
    )
    plist_label: Optional[str] = Field(
        default=None,
        description="Reverse-DNS label for the launchd plist, e.g. 'com.user.mytask'.",
    )
    plist_interval_seconds: Optional[int] = Field(
        default=None,
        description="If provided, use StartInterval (repeat every N seconds). Otherwise use cron expression via StartCalendarInterval.",
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

_CRON_FIELD_NAMES = ["minuto", "hora", "día-del-mes", "mes", "día-de-semana"]

def _validate_expression(expr: str) -> tuple[bool, str]:
    """Returns (ok, message)."""
    parts = expr.strip().split()
    if len(parts) != 5:
        return False, f"La expresión debe tener 5 campos, tiene {len(parts)}: {expr!r}"
    field_ranges = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 7)]
    for i, (part, (lo, hi)) in enumerate(zip(parts, field_ranges)):
        # Accept *, */n, n, n-m, n,m patterns — light validation
        if part == "*":
            continue
        tokens = re.split(r"[,/\-]", part)
        for t in tokens:
            if not t.isdigit():
                return False, f"Campo '{_CRON_FIELD_NAMES[i]}' contiene token inválido: {t!r}"
            val = int(t)
            if not (lo <= val <= hi):
                return False, (
                    f"Campo '{_CRON_FIELD_NAMES[i]}' valor {val} fuera de rango [{lo}-{hi}]"
                )
    return True, "OK"


def _next_runs(expr: str, n: int = 5) -> list[str]:
    """Approximate next N run times for a cron expression (minute precision)."""
    parts = expr.strip().split()
    minute_p, hour_p, dom_p, month_p, dow_p = parts

    results = []
    now = datetime.now().replace(second=0, microsecond=0)
    t = now + timedelta(minutes=1)
    attempts = 0

    while len(results) < n and attempts < 527040:  # max 1 year
        attempts += 1
        if not _matches(t.month, month_p, 1, 12):
            t += timedelta(hours=1)
            t = t.replace(minute=0)
            continue
        if not _matches(t.day, dom_p, 1, 31):
            t += timedelta(hours=1)
            t = t.replace(minute=0)
            continue
        if not _matches(t.weekday() + 1 if t.weekday() < 6 else 0, dow_p, 0, 7):
            t += timedelta(hours=1)
            t = t.replace(minute=0)
            continue
        if not _matches(t.hour, hour_p, 0, 23):
            t += timedelta(hours=1)
            t = t.replace(minute=0)
            continue
        if not _matches(t.minute, minute_p, 0, 59):
            t += timedelta(minutes=1)
            continue
        results.append(t.strftime("%Y-%m-%d %H:%M"))
        t += timedelta(minutes=1)

    return results


def _matches(value: int, pattern: str, lo: int, hi: int) -> bool:
    if pattern == "*":
        return True
    if pattern.startswith("*/"):
        step = int(pattern[2:])
        return value % step == 0
    if "," in pattern:
        return any(_matches(value, p.strip(), lo, hi) for p in pattern.split(","))
    if "-" in pattern:
        a, b = pattern.split("-", 1)
        return int(a) <= value <= int(b)
    return value == int(pattern)


def _read_crontab() -> str:
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    if result.returncode != 0:
        # No crontab for user is exit code 1 with specific message
        if "no crontab" in result.stderr.lower():
            return ""
        raise RuntimeError(f"Error leyendo crontab: {result.stderr.strip()}")
    return result.stdout


def _write_crontab(content: str) -> None:
    proc = subprocess.run(
        ["crontab", "-"],
        input=content,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Error escribiendo crontab: {proc.stderr.strip()}")


# ── CronTool ──────────────────────────────────────────────────────────────────

class CronTool(BaseTool):
    name: str = "manage_cron"
    description: str = (
        "Gestiona crontabs del sistema y launchd plists en macOS/Linux. "
        "Acciones disponibles: "
        "'list' — listar entradas actuales del crontab; "
        "'validate' — validar expresión cron y ver próximas ejecuciones; "
        "'add' — agregar nueva tarea programada (requiere expression + command); "
        "'remove' — eliminar entradas que coincidan con un comando; "
        "'generate_plist' — generar archivo .plist para launchd de macOS."
    )
    args_schema: type[BaseModel] = CronInput
    risk_level: int = 0  # default; overridden per-action in _run

    def _run(self, **kwargs) -> str:  # type: ignore[override]
        action = kwargs.get("action", "list")
        try:
            if action == "list":
                return self._list()
            elif action == "validate":
                return self._validate(kwargs.get("expression"))
            elif action == "add":
                return self._add(
                    kwargs.get("expression"),
                    kwargs.get("command"),
                    kwargs.get("description"),
                )
            elif action == "remove":
                return self._remove(kwargs.get("command"))
            elif action == "generate_plist":
                return self._generate_plist(
                    kwargs.get("plist_label"),
                    kwargs.get("command"),
                    kwargs.get("expression"),
                    kwargs.get("plist_interval_seconds"),
                    kwargs.get("description"),
                )
            else:
                return f"Acción desconocida: {action!r}. Usa: list, add, remove, validate, generate_plist."
        except Exception as exc:
            return f"Error en CronTool({action}): {exc}"

    # ── actions ───────────────────────────────────────────────────────────────

    def _list(self) -> str:
        content = _read_crontab()
        if not content.strip():
            return "No hay entradas en el crontab actual."
        lines = content.strip().splitlines()
        result = [f"Crontab actual ({len([l for l in lines if l.strip() and not l.startswith('#')])} tareas):"]
        for i, line in enumerate(lines, 1):
            result.append(f"  {i:3}. {line}")
        return "\n".join(result)

    def _validate(self, expression: Optional[str]) -> str:
        if not expression:
            return "Error: se requiere 'expression' para validar."
        ok, msg = _validate_expression(expression)
        if not ok:
            return f"Expresion inválida: {msg}"
        next_runs = _next_runs(expression)
        lines = [f"Expresión válida: {expression!r}", "Próximas ejecuciones:"]
        for run in next_runs:
            lines.append(f"  • {run}")
        return "\n".join(lines)

    def _add(
        self,
        expression: Optional[str],
        command: Optional[str],
        description: Optional[str],
    ) -> str:
        if not expression:
            return "Error: se requiere 'expression' para agregar una tarea."
        if not command:
            return "Error: se requiere 'command' para agregar una tarea."

        ok, msg = _validate_expression(expression)
        if not ok:
            return f"Expresión inválida, tarea no agregada: {msg}"

        current = _read_crontab()

        new_lines = []
        if description:
            new_lines.append(f"# {description}")
        new_lines.append(f"{expression} {command}")
        new_entry = "\n".join(new_lines)

        separator = "\n" if current.endswith("\n") else "\n\n"
        updated = current + separator + new_entry + "\n"

        _write_crontab(updated)

        next_runs = _next_runs(expression, 3)
        result = [
            f"Tarea agregada al crontab:",
            f"  Expresión : {expression}",
            f"  Comando   : {command}",
        ]
        if description:
            result.append(f"  Descripción: {description}")
        result.append("Próximas ejecuciones:")
        for r in next_runs:
            result.append(f"  • {r}")
        return "\n".join(result)

    def _remove(self, command: Optional[str]) -> str:
        if not command:
            return "Error: se requiere 'command' (patrón) para eliminar entradas."

        current = _read_crontab()
        if not current.strip():
            return "El crontab está vacío, nada que eliminar."

        lines = current.splitlines(keepends=True)
        removed = []
        kept = []
        skip_next_comment = False

        for i, line in enumerate(lines):
            stripped = line.strip()
            # Check if next non-comment line matches (to remove preceding comment)
            if stripped.startswith("#"):
                # Lookahead: check if next entry line matches
                for j in range(i + 1, len(lines)):
                    next_line = lines[j].strip()
                    if not next_line.startswith("#") and next_line:
                        if command in next_line:
                            skip_next_comment = True
                        break
                if skip_next_comment:
                    removed.append(line.rstrip())
                    skip_next_comment = False
                    continue
                kept.append(line)
            elif command in stripped:
                removed.append(line.rstrip())
            else:
                kept.append(line)

        if not removed:
            return f"No se encontraron entradas que contengan: {command!r}"

        _write_crontab("".join(kept))
        result = [f"Eliminadas {len(removed)} línea(s) del crontab:"]
        for r in removed:
            result.append(f"  - {r}")
        return "\n".join(result)

    def _generate_plist(
        self,
        label: Optional[str],
        command: Optional[str],
        expression: Optional[str],
        interval_seconds: Optional[int],
        description: Optional[str],
    ) -> str:
        if not label:
            return "Error: se requiere 'plist_label' (ej. 'com.usuario.mitarea')."
        if not command:
            return "Error: se requiere 'command' para el plist."

        # Build plist XML
        plist = ET.Element("plist", version="1.0")
        dct = ET.SubElement(plist, "dict")

        def kv(parent: ET.Element, key: str, value_el: str, value_text: str = "") -> None:
            ET.SubElement(parent, "key").text = key
            el = ET.SubElement(parent, value_el)
            if value_text:
                el.text = value_text

        kv(dct, "Label", "string", label)

        # ProgramArguments
        ET.SubElement(dct, "key").text = "ProgramArguments"
        arr = ET.SubElement(dct, "array")
        ET.SubElement(arr, "string").text = "/bin/sh"
        ET.SubElement(arr, "string").text = "-c"
        ET.SubElement(arr, "string").text = command

        if interval_seconds:
            kv(dct, "StartInterval", "integer", str(interval_seconds))
        elif expression:
            ok, msg = _validate_expression(expression)
            if not ok:
                return f"Expresión cron inválida para plist: {msg}"
            parts = expression.strip().split()
            minute_p, hour_p, dom_p, month_p, dow_p = parts
            ET.SubElement(dct, "key").text = "StartCalendarInterval"
            cal = ET.SubElement(dct, "dict")
            field_map = [
                ("Minute", minute_p),
                ("Hour", hour_p),
                ("Day", dom_p),
                ("Month", month_p),
                ("Weekday", dow_p),
            ]
            for fname, fval in field_map:
                if fval != "*":
                    kv(cal, fname, "integer", fval)
        else:
            return "Error: se requiere 'expression' o 'plist_interval_seconds' para generar el plist."

        kv(dct, "RunAtLoad", "false")
        kv(dct, "StandardOutPath", "string", f"/tmp/{label}.out.log")
        kv(dct, "StandardErrorPath", "string", f"/tmp/{label}.err.log")

        # Format XML
        ET.indent(plist, space="    ")
        xml_header = '<?xml version="1.0" encoding="UTF-8"?>\n'
        xml_header += '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
        xml_body = ET.tostring(plist, encoding="unicode")
        xml_content = xml_header + xml_body + "\n"

        # Save to ~/Library/LaunchAgents/
        agents_dir = os.path.expanduser("~/Library/LaunchAgents")
        os.makedirs(agents_dir, exist_ok=True)
        plist_path = os.path.join(agents_dir, f"{label}.plist")
        with open(plist_path, "w", encoding="utf-8") as f:
            f.write(xml_content)

        load_cmd = f"launchctl load {plist_path}"
        unload_cmd = f"launchctl unload {plist_path}"
        result = textwrap.dedent(f"""
            Plist generado y guardado en:
              {plist_path}

            Para cargar (activar):
              {load_cmd}

            Para desactivar:
              {unload_cmd}

            Contenido del plist:
            {xml_content}
        """).strip()

        if description:
            result = f"# {description}\n\n" + result

        return result
