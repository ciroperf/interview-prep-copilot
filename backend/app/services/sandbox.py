"""Esecuzione dei test su codice scritto dall'utente.

ATTENZIONE: eseguire codice arbitrario e' intrinsecamente rischioso. Questo
runner applica difese di base (processo separato, limiti di CPU e memoria,
timeout, interprete isolato) ma NON e' una sandbox di sicurezza completa: non
isola la rete ne' il filesystem.

Per questo `enable_code_execution` e' False di default e in Azure resta spento.
Vedi docs/security.md per le condizioni in cui e' ragionevole accenderlo.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
import tempfile
from pathlib import Path

from ..domain.models import CodingProblem, TestOutcome

logger = logging.getLogger(__name__)

# Lo script di test viene generato a runtime: riceve il codice utente e i casi di
# prova, li esegue e stampa una riga JSON su stdout.
HARNESS = '''
import json, sys, resource

def _limit(cpu_seconds, memory_bytes):
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
    resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1 << 20, 1 << 20))
    try:
        resource.setrlimit(resource.RLIMIT_NPROC, (64, 64))
    except (ValueError, OSError):
        pass

payload = json.loads(sys.stdin.read())
_limit(payload["cpu_seconds"], payload["memory_bytes"])

namespace = {"__name__": "__candidate__"}
results = []
try:
    exec(compile(payload["code"], "<soluzione>", "exec"), namespace)
except BaseException as exc:
    print(json.dumps({"fatal": f"{type(exc).__name__}: {exc}"}))
    raise SystemExit(0)

func = namespace.get(payload["function_name"])
if not callable(func):
    print(json.dumps({"fatal": "Funzione %s non definita" % payload["function_name"]}))
    raise SystemExit(0)

for index, case in enumerate(payload["tests"]):
    entry = {"index": index, "passed": False, "actual": "", "error": ""}
    try:
        got = func(**case["kwargs"])
        entry["actual"] = repr(got)
        entry["passed"] = got == case["expected"]
    except BaseException as exc:
        entry["error"] = f"{type(exc).__name__}: {exc}"
    results.append(entry)

print(json.dumps({"results": results}))
'''


class ExecutionResult:
    def __init__(
        self,
        executed: bool,
        outcomes: list[TestOutcome],
        fatal: str = "",
    ) -> None:
        self.executed = executed
        self.outcomes = outcomes
        self.fatal = fatal

    @property
    def passed(self) -> int:
        return sum(1 for o in self.outcomes if o.passed)

    def report(self) -> str:
        """Riassunto testuale, passato al modello insieme al codice."""
        if self.fatal:
            return f"Il codice non è stato eseguito: {self.fatal}"
        if not self.outcomes:
            return "Nessun test eseguito."
        lines = [f"{self.passed}/{len(self.outcomes)} test superati."]
        for outcome in self.outcomes:
            if outcome.passed:
                continue
            detail = outcome.error or f"atteso {outcome.expected}, ottenuto {outcome.actual}"
            lines.append(f"- FALLITO {outcome.name}: {detail}")
        return "\n".join(lines)


def run_tests(
    problem: CodingProblem,
    code: str,
    *,
    timeout_seconds: float = 5.0,
    memory_mb: int = 256,
) -> ExecutionResult:
    payload = {
        "code": code,
        "function_name": problem.function_name,
        "cpu_seconds": max(1, int(timeout_seconds)),
        "memory_bytes": memory_mb * 1024 * 1024,
        "tests": [{"kwargs": t.kwargs, "expected": t.expected} for t in problem.tests],
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        harness_path = Path(tmpdir) / "harness.py"
        harness_path.write_text(HARNESS, encoding="utf-8")
        try:
            completed = subprocess.run(
                # -I isola l'interprete: niente sys.path dell'utente, niente variabili PYTHON*.
                [sys.executable, "-I", str(harness_path)],
                input=json.dumps(payload),
                capture_output=True,
                text=True,
                timeout=timeout_seconds + 2,
                cwd=tmpdir,
            )
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                executed=True,
                outcomes=[],
                fatal=f"Timeout: l'esecuzione ha superato {timeout_seconds:.0f} secondi",
            )
        except Exception as exc:  # pragma: no cover - dipende dall'ambiente
            logger.exception("Esecuzione del codice non riuscita")
            return ExecutionResult(executed=False, outcomes=[], fatal=str(exc))

    stdout = (completed.stdout or "").strip().splitlines()
    if not stdout:
        stderr = (completed.stderr or "").strip()[-500:]
        return ExecutionResult(
            executed=True, outcomes=[], fatal=stderr or "Nessun output dal processo di test"
        )

    try:
        data = json.loads(stdout[-1])
    except json.JSONDecodeError:
        return ExecutionResult(executed=True, outcomes=[], fatal="Output del runner illeggibile")

    if "fatal" in data:
        return ExecutionResult(executed=True, outcomes=[], fatal=str(data["fatal"]))

    outcomes: list[TestOutcome] = []
    for entry in data.get("results", []):
        index = int(entry.get("index", 0))
        case = problem.tests[index] if index < len(problem.tests) else None
        outcomes.append(
            TestOutcome(
                name=f"test {index + 1}" + (" (nascosto)" if case and case.hidden else ""),
                passed=bool(entry.get("passed")),
                expected=repr(case.expected) if case else "",
                actual=str(entry.get("actual", "")),
                error=str(entry.get("error", "")),
            )
        )
    return ExecutionResult(executed=True, outcomes=outcomes)
