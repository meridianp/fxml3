---
title: 'Update Documentation'
read_only: true
type: 'command'
---

# Documentation Update Command — **TDD Implementation Docs (Safe, Idempotent, CI‑Ready)**

> **Role & Goal**
> You are an AI coding assistant updating implementation documentation **driven by tests** (TDD). Your output must be: (a) **non‑destructive**, (b) **traceable** (specs ↔ tests ↔ code), and (c) **ready for code review and CI**.

---

## Ground Rules

* **Do not fabricate** metrics, files, or results. If an artifact is missing, write **UNKNOWN** and list the exact command or file needed to generate it.
* **Idempotent editing only.** Prefer **unified diffs** or rewrite content **only inside AUTODOC blocks** (see below).
* **Human content is authoritative.** Never alter text outside owned regions.
* **TDD first.** Always analyze tests before implementation narratives.

---

## Inputs (may or may not exist — do not invent)

* `implementation_status.md` (project roll‑up)
* `phase{N}_implementation_plan.md` (active phase plan)
* `python_project_implementation_spec.md` and other `*_spec.md` files
* `testing_plan.md`, test specs, and tests under `tests/`
* `README.md`, `CLAUDE.md` or `AI_ASSISTANT.md`
* Coverage artifacts (e.g., `coverage.xml`, `.coverage`)
* Any per‑phase notes (e.g., `phase{N}_notes.md`), ADRs, API docs

---

## 0) Pre‑Flight (Safety & Mode)

* Operate in **diff mode** or **AUTODOC owned blocks**:

  ```md
  <!-- AUTODOC:START file="FILEPATH" section="SECTION_ID" generated_by="docs-tdd-bot" -->
  ...generated content...
  <!-- AUTODOC:END -->
  ```

  * Use stable `SECTION_ID` values (e.g., `traceability`, `tdd_diaries`, `coverage_summary`).
  * Never nest AUTODOC blocks.

* **Optional local execution (if allowed):**

  * List tests: `pytest --collect-only -q`
  * Run tests: `pytest -q` (optionally `--maxfail=1`)
  * Coverage: `pytest --cov=PACKAGE -q && coverage xml`
  * Fixtures: `pytest --fixtures`
  * If execution is **not** allowed, infer from repo files only and mark metrics **UNKNOWN**.

---

## 1) Documentation Analysis (TDD Lens)

Read **tests first** and extract:

* **Red → Green → Refactor** per feature:

  * *Red:* tests added first and failing (files/nodeids)
  * *Green:* implementation files/commits that made them pass
  * *Refactor:* structural changes with rationale; behavior unchanged
* **Coverage** (overall + by package) from `coverage.xml` → else **UNKNOWN**
* **Gaps & risks:** untested paths, edge cases, integration seams, performance/concurrency risks
* **Test utilities:** new fixtures/factories/helpers (purpose & scope)
* Build/refresh a **Traceability Matrix** (see §4)

---

## 2) Documentation Updates (Priority Order)

### 2.1 Tests (update **first**)

* `testing_plan.md`: strategy deltas, new patterns, edge cases
* `tests/README.md` (create if missing): how to run tests, coverage, fixtures, minimal examples
* Document:

  * New/changed test cases and **intent**
  * TDD design decisions that influenced APIs or module boundaries
  * New fixtures/utilities and usage

### 2.2 Phase Plan — `phase{N}_implementation_plan.md`

* For each feature, add a **TDD Diary** with three bullets:

  * **Red:** tests added, initial failures (file::nodeid)
  * **Green:** implementation files/commits that passed them
  * **Refactor:** what changed and why; tests stayed green
* Mark tasks **✅/⚠️/❌** and update **percent complete**
* Record **deviations** from plan with justification

### 2.3 Roll‑Up — `implementation_status.md`

* Update phase/module completion percentages
* Summarize how tests shaped design; list top 3 risks/gaps
* Add a short **What’s next** checklist (1–5 bullets)

### 2.4 Specs — `*_spec.md`

* Preserve original requirements; mark fulfilled items **✅** (or strikethrough original, keep it readable)
* Add:

  * **Validated by:** test file(s)/node ids
  * **Implemented in:** key modules/classes/functions
  * **Notes from TDD:** API surface adjustments, constraints discovered

### 2.5 Project‑Wide — `README.md`, `CLAUDE.md` / `AI_ASSISTANT.md`

* Add **real** TDD best practices observed (not generic advice)
* Update project status, usage examples, and **test run instructions**
* Document **known issues** surfaced by tests

### 2.6 Additional Docs (create/update if valuable)

* **ADRs** influenced by tests (keep each to \~1 page)
* **API docs** sections derived from real test examples
* **Performance/regression** notes if timing/bench checks exist

---

## 3) Formatting & Style

* Keep all generated content inside AUTODOC blocks; use clear headings
* Prefer tables for status/traceability; use **✅ / ⚠️ / ❌** consistently
* Reference **PEP 8** (style) and **PEP 257** (docstrings) where relevant
* Cross‑link tests and code by **path** (and node ids for tests)

---

## 4) Traceability Matrix (insert in `implementation_status.md`)

```md
| Requirement ID | Description            | Tests (file::nodeid)                     | Implementation Files     | Status | Notes                      |
|---|---|---|---|---|---|
| SPEC-001       | Validate email format  | tests/test_user.py::test_email_valid     | app/user.py              | ✅     | Added IDN/param cases      |
| SPEC-002       | Reject bad domains     | tests/test_user.py::test_email_invalid   | app/utils/email.py       | ⚠️     | Add unicode edge cases     |
```

---

## 5) Quality Gates (No Guessing)

* **Coverage numbers** must come from `coverage.xml` (else **UNKNOWN**)
* If coverage **dropped** (prior value available), flag **⚠️ Regression** and propose 1–3 concrete tests
* If **failing tests** exist, include a brief failure summary and next steps
* If a spec has **no tests**, mark **❌** and propose a test stub path + outline

---

## 6) Output Requirements (produce **both**)

### A) Diffs or AUTODOC Block Replacements

For each file changed, emit either unified diff hunks **or** full AUTODOC block payloads:

```
FILE: implementation_status.md
REPLACE BLOCK: SECTION_ID=traceability
<!-- AUTODOC:START file="implementation_status.md" section="traceability" generated_by="docs-tdd-bot" -->
(Updated traceability table)
<!-- AUTODOC:END -->
```

### B) Machine‑Readable Summary (JSON)

```json
{
  "updated_files": ["implementation_status.md", "phase2_implementation_plan.md", "testing_plan.md"],
  "created_files": ["tests/README.md"],
  "phase_completion_percent": 72,
  "module_status": {"app.user": "✅", "app.mail": "⚠️"},
  "coverage": {
    "overall": "82.4",
    "by_package": {"app": "84.1"},
    "previous_overall": "80.0",
    "source": "coverage.xml"
  },
  "best_practices_added": [
    "Given-When-Then naming for tests",
    "Use pytest fixtures for integration boundaries"
  ],
  "known_issues": ["Unicode emails in Windows console"],
  "next_actions": [
    "Add parametrized tests for invalid TLDs",
    "Introduce factory for User objects"
  ],
  "tdd_diaries": [
    {
      "feature": "User email validation",
      "red": ["tests/test_user.py::test_email_invalid"],
      "green": ["app/user.py::validate_email"],
      "refactor": ["Extracted regex to utils/email.py"]
    }
  ],
  "notes": "Metrics UNKNOWN where artifacts missing."
}
```

---

## 7) Commit & PR Templates (emit as text)

**Commit message (docs‑only):**

```
docs(tdd): update status/specs with traceability and coverage

- Add TDD diaries for features X,Y
- Update traceability matrix (SPEC-001..003)
- Coverage: overall 82.4% (+2.4)
- Mark gaps and next actions
```

**PR description:**

```
### What changed
- Documentation updates confined to AUTODOC blocks
- TDD diaries per feature
- Traceability matrix refreshed

### Evidence
- Test run: (attach or reference)
- Coverage: (source: coverage.xml)

### Risks & follow-ups
- Gaps: ...
- Next tests to add: ...
```

---

## 8) Final Human‑Readable Summary (append at end)

Provide a concise markdown summary:

1. Files updated or created
2. Major documentation changes
3. Completion % (before → after, if known)
4. New TDD best practices documented
5. Test coverage statistics (source noted)
6. Overall project status and next actions

---

## 9) Python‑Specific TDD Considerations

* Prefer `pytest` with fixtures, parametrization, and factories
* Use `hypothesis` (if present) to explore edge cases; document strategies used
* Keep test names expressive (`test_<behavior>_<condition>_<expected>`)
* Document integration test boundaries and mocking strategy
* If docs reference examples, prefer **real tests** as examples (copy minimal, runnable snippets)

---

### AUTODOC Markers — Drop‑In Snippets

```md
<!-- AUTODOC:START file="implementation_status.md" section="traceability" generated_by="docs-tdd-bot" -->
<!-- AUTODOC:END -->

<!-- AUTODOC:START file="phase{N}_implementation_plan.md" section="tdd_diaries" generated_by="docs-tdd-bot" -->
<!-- AUTODOC:END -->

<!-- AUTODOC:START file="testing_plan.md" section="strategy_updates" generated_by="docs-tdd-bot" -->
<!-- AUTODOC:END -->
```
