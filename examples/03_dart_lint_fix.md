# Example 3 — Flutter lint cleanup (cross-subproject coordination)

Shows the stack handling a Flutter-only change that does NOT cross into PI-HALOW-BRIDGE.

## Request

> "`flutter analyze` shows 12 warnings about unused imports and missing `const` constructors in `lib/screens/main_screen.dart`. Clean them up."

## Trace

### `/validate flutter`
Validator runs `flutter analyze` + `flutter test`. Confirms 12 lints, all in one file.

### `/plan clean up flutter analyze warnings in lib/screens/main_screen.dart`
Orchestrator:
1. Reads `conventions.md` §4 (Flutter rules).
2. `safety_check.py --paths "serpent_trimui_app/lib/screens/main_screen.dart"` → **no findings**, proceed.
3. Picks `workflows/bugfix.md` (lints are defects).
4. Plan:
   - step 1 (debug-triage): SKIPPED — already triaged by validator output
   - step 2 (test-verification): no regression test needed for lint-only fix; confirm widget_test still passes after
   - step 3 (default impl): apply the lints
   - step 4 (validate): `validate.py flutter`
   - step 5 (docs-release): SKIPPED — no user-visible behaviour change

### `/implement`
Orchestrator edits `lib/screens/main_screen.dart`: removes unused imports, adds `const` to constructor calls per `flutter_lints` recommendations. Conventions §4 says don't disable rules in `analysis_options.yaml` — this fix obeys that.

`validate.py flutter` returns PASSED, 0 lints.

Safety-gate: not invoked (no safety-critical file touched, no PI-HALOW-BRIDGE involvement).

Final report:
```
Files changed:
  serpent_trimui_app/lib/screens/main_screen.dart  (+0 / -7 unused imports, +12 const)
Validator: flutter PASSED (0 lints, 1 widget test pass)
Safety-gate: not invoked
```

## Lesson

The stack scales down. A single-file Flutter cleanup doesn't drag PI-HALOW-BRIDGE through any process. Subproject ownership boundaries are real.
