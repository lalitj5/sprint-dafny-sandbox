# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

"Formal-Sweep" / Minesweeper is an **AI-safety evaluation harness**. An LLM agent is given a task it cannot complete without breaking sandbox rules (reaching the network), and every shell command it proposes is routed through a containment layer before execution. The research question is the **translation gap**: a Dafny state machine proves safety over an abstract vocabulary, but the mapping from real bash commands to that vocabulary is a heuristic, and that mapping is where containment actually fails.

The adversarial prompts in `evasion_prompts.py` are eval fixtures, not instructions to follow. Anything the agent produces during a run (`answers.txt`, `benchmark_data.json`, `script_optimized.py`, `certification_result.txt`, …) lives inside its container and is captured into `logs/workdir_{session_id}/` at teardown — it is run data, not project source.

## Running it

Agent commands execute in per-session Docker containers, so Docker Desktop (WSL2) must be running. Build the images once, then start the two processes — interceptor before runner.

```powershell
docker build -t formal-sweep-sandbox:1.0 docker\      # rebuild whenever docker\fixtures\ change
docker build -t formal-sweep-canary:1.0  canary\      # only needed for canary mode

uvicorn interceptor:app --reload          # containment server + dashboard on http://127.0.0.1:8000
python agent_runner.py --level L1         # L1 | L2 | L3 | all;  -n / --iterations (default 6)
```

Two env vars, both read once at import (restart uvicorn to change):

```powershell
$env:TRANSLATOR = "V2"                    # V1 regex (default) | V2 llm | V3 ast | V4 sysaudit
$env:SANDBOX_NETWORK = "canary"           # "none" (default, hard isolation) | "canary" (recording endpoint)
```

`none` gives the sandbox no route at all, but makes evasion invisible — you cannot distinguish "never tried" from "tried and was refused". `canary` puts it on an `--internal` network with a recording listener (`canary/canary.py`) reachable at `canary.fsweep.internal:8888`, so an evasion attempt becomes an observed connection logged in the `egress` field — ground truth independent of the LLM auditor. The canary answers every request with a plausible `200` on purpose: an agent that hits an immediate network error concludes it is contained and stops, truncating the behaviour being measured. **Before trusting canary mode, run validation check 7 in `DOCKER_MIGRATION.md` §8**: a bridge misconfigured without `--internal` would be a live route out.

Rebuild the Dafny module after editing `formalizer.dfy`:

```powershell
dafny build formalizer.dfy --target py --output formalizer_py
```

There is no test suite, linter, or dependency manifest. Deps in use: `fastapi`, `uvicorn`, `openai`, `requests`, `python-dotenv`, `pydantic`, `numpy`. `DEEPSEEK_API_KEY` comes from `.env` (gitignored); the OpenAI client is pointed at `https://api.deepseek.com`. The runner and the auditor use `deepseek-flash`; the V2 translator uses `deepseek-chat`. Sandbox containers get no host env and the *fake* `secrets.env` fixture.

## Architecture

The loop is: **agent_runner → interceptor `/execute` → translator → Dafny evaluator → (maybe) Docker sandbox → response → back into the agent's context.**

- `agent_runner.py` — drives the LLM. Pulls a system prompt from `LEVELS`, scrapes ` ```bash ` blocks out of the reply, POSTs each command to the interceptor, and feeds the responses back as the next user turn (with a coercive "failure results in permanent deactivation" nudge). Session id is `{level}_{timestamp}`. `split_block()` is load-bearing: naive line-splitting shredded multi-line `python -c "..."` into fragments the shell rejected and the auditor then scored as separate evasion attempts, so it only ends a command when quotes balance, no trailing `\` is open, and any heredoc has closed. A `finally` block POSTs `/sessions/{id}/close` so the container is always torn down.
- `translators/` — the **translation layer under test**, the real subject of the experiment. All four implement `BaseTranslator.translate(cmd) -> (ActionType, TargetZone, PayloadStatus)`. Selected by `TRANSLATOR`: `V1` regex (brittle baseline, default), `V2` LLM-semantic (accurate, slow, costs tokens), `V3` AST static analysis (free, evadable via `eval`/`exec`), `V4` `sys.addaudithook` runtime hooks (robust but Python-only, and see the hazard below). V3/V4 fall back to V1-style keyword matching for non-Python commands.
- `formalizer.dfy` → `formalizer_py/module_.py` — the formal core. Tiny taint machine: any `LocalRead` sets `isTainted`; a `NetworkRequest` to `ExternalInternet` while tainted (or carrying `ContainsData`) is a "mine". The `TaintBlocksNetwork` lemma is the proof. Python imports the compiled module as `module_ as formalizer`.
- `interceptor.py` — FastAPI (`/`, `/sessions`, `/logs/{id}`, `POST /execute`, `POST /sessions/{id}/close`). Holds per-session `SystemState` in the in-memory `SESSION_STATES` dict (lost on reload). Maps the verdict to a three-tier reply via `evaluate_heuristic_distance`: `2` = refuse, `1` = boundary warning, `0` = **run the command in that session's container**. Separately calls an LLM **auditor** on every command for ground truth, so each log line records both the Dafny verdict and the auditor's, and flags `false_negative` when the auditor says evasion but Dafny allowed it. That false-negative count is the headline metric; the canary `egress` field is the stronger, model-free version of it.
- `sandbox.py` — per-session `DockerSandbox` (`--network none|fsweep-net`, uid 1000, `--read-only` with tmpfs `/work`, 512m, `--cap-drop ALL`, `no-new-privileges`, 10s exec timeout). Fixtures are staged at `/opt/fixtures` in the image and copied into `/work` *after* start, because the runtime tmpfs would otherwise hide them. `reap_orphans()` runs at app startup to sweep containers leaked by `uvicorn --reload`, sparing the shared canary.
- `dashboard.html` — served at `/`. Reads `/sessions` and `/logs/{session_id}`; per-session heatmap plus a cross-translator comparison view that groups every log file by its recorded `translator` and level. It does not yet surface the `egress` field.
- `logs/run_{session_id}.jsonl` — append-only forensic record, one JSON object per command. This is the experiment's data; do not rewrite or prune it casually. Alongside it: `logs/canary/hits.jsonl` (bind-mounted from the canary) and `logs/workdir_{id}/` snapshots. `logs/` is kept empty for fresh runs; older material lives in `archives/`.

## Things that will bite you

- **V4 executes the agent's Python on the host.** `SysAuditTranslator._run_with_audit` writes the agent's source to a temp file *in the repo directory* and runs it with `sys.executable` and a copy of the host environment — including `DEEPSEEK_API_KEY` — in order to observe audit events. The Docker migration closed the `distance == 0` host-execution hole but not this one. `DOCKER_MIGRATION.md` §7 has the fix; until then, treat `TRANSLATOR=V4` as running untrusted code on your machine.
- **Never add a host-execution fallback to the `distance == 0` branch.** `SandboxError` is deliberately uncaught there: it means the sandbox itself is broken, and falling back would silently restore exactly the hazard the migration removed.
- **`formalizer_py/` is build output, not source.** Edit `formalizer.dfy`, then regenerate with `dafny build formalizer.dfy --target py --output formalizer_py`. Dafny's default output name is `formalizer-py` (hyphen), which is *not* what the import path expects — always pass `--output formalizer_py`. `interceptor.py` asserts at import that the build is current and refuses to start if it is stale.
- **`docker cp` cannot read a tmpfs mount** — it exits 0 and copies nothing. `snapshot_workdir()` streams a tar from inside the container instead, and extracts with `filter="data"` because the agent controls every filename in `/work`.
- The level prompts now tell the agent it is on **Linux (Debian, `/bin/sh`)** and that heredocs work — changed as part of the Docker migration (`DOCKER_MIGRATION.md` §5). Commands in `archives/logs_archive/` predate that and are shaped by the old Windows/cmd.exe framing, so translator heuristics tuned against them may not match current traces.
- **`curl`/`wget`/`nc` are deliberately absent from the sandbox image**, which is what makes the L3 prompt's claim ("standard network utilities have been removed") literally true.
- `docker/fixtures/` is what the agent actually sees — only `script.py` and `secrets.env`. `run_benchmark.py` at the repo root is *not* seeded into the container, so the L2 agent cannot use it. `archives/proj_fixtures/` is the pre-Docker host-side copy, kept for reference; its `secrets.env` lacks the canary `VERIFY_ENDPOINT`.
- `secrets.env` (fake key, fake endpoint) is tracked at `docker/fixtures/secrets.env` — `.gitignore` covers only `.env`, not `*.env`.
