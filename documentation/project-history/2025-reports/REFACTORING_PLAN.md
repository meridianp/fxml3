# FXML4 Codebase Refactoring Plan

## Overview
This document tracks the refactoring progress of the FXML4 codebase from its current fragmented state to a properly structured Python package.

## Current State Analysis

### Problem Summary
- **185 files** are importing from `fxml4.*` modules that don't exist in the root structure
- **483+ import statements** expect a package structure that was never created
- Code is scattered across three parallel structures:
  1. Root `/fxml4/` - Only has backtesting (recently refactored)
  2. Legacy `/fxml4-monorepo/legacy/fxml4/` - Complete old structure
  3. New `/fxml4-monorepo/packages/` - Target modular structure

### Systems Requiring Refactoring

| System | Current Location | Status | Import Count |
|--------|-----------------|---------|--------------|
| Backtesting | `/fxml4/backtesting/` | ✅ COMPLETED | Fixed |
| ML Models | `/fxml4-monorepo/legacy/fxml4/ml/` | ❌ Not migrated | 89 imports |
| Data Engineering | `/fxml4-monorepo/legacy/fxml4/data_engineering/` | ❌ Not migrated | 67 imports |
| Wave Analysis | `/fxml4-monorepo/legacy/fxml4/wave_analysis/` | ❌ Not migrated | 45 imports |
| API | Scattered in multiple locations | ❌ Not consolidated | 52 imports |
| Signal Generation | `/fxml4-monorepo/legacy/fxml4/signal_generation/` | ❌ Not migrated | 38 imports |
| Core Utilities | `/fxml4-monorepo/legacy/fxml4/core/` | ❌ Not migrated | 94 imports |
| Strategies | `/fxml4-monorepo/legacy/fxml4/strategies/` | ❌ Not migrated | 31 imports |
| Utils | `/fxml4-monorepo/legacy/fxml4/utils/` | ❌ Not migrated | 67 imports |

## Refactoring Phases

### Phase 1: Complete Module Migration ⏳ (In Progress)
**Priority: HIGH**
**Estimated Time: 2-3 hours**

- [ ] Create package structure at `/fxml4/`
  ```
  /fxml4/
  ├── __init__.py
  ├── backtesting/      ✅ (completed)
  ├── ml/               ❌
  ├── data_engineering/ ❌
  ├── wave_analysis/    ❌
  ├── api/              ❌
  ├── signal_generation/❌
  ├── core/             ❌
  ├── strategies/       ❌
  └── utils/            ❌
  ```

- [ ] Migrate modules from legacy structure
  - [ ] ML system (models, features, training)
  - [ ] Data engineering (feeds, processors)
  - [ ] Wave analysis (Elliott Wave analyzer)
  - [ ] API modules (routers, handlers)
  - [ ] Signal generation
  - [ ] Core utilities
  - [ ] Trading strategies
  - [ ] General utilities

### Phase 2: Fix Import Statements 📝 (Not Started)
**Priority: HIGH**
**Estimated Time: 1-2 hours**

- [ ] Scripts directory (357 imports to fix)
  - [ ] ML training scripts
  - [ ] Backtesting scripts
  - [ ] Data collection scripts
  - [ ] Analysis scripts

- [ ] Tests directory (67 imports to fix)
  - [ ] Unit tests
  - [ ] Integration tests
  - [ ] API tests

- [ ] Examples directory (26 imports to fix)
- [ ] Documentation examples (33 imports to fix)

### Phase 3: Consolidate Scattered Code 🔧 (Not Started)
**Priority: MEDIUM**
**Estimated Time: 3-4 hours**

- [ ] API Consolidation
  - [ ] Merge API implementations
  - [ ] Unify route definitions
  - [ ] Standardize middleware

- [ ] ML Pipeline Integration
  - [ ] Consolidate training scripts
  - [ ] Unify feature engineering
  - [ ] Standardize model interfaces

### Phase 4: Modernize to Monorepo Structure 🚀 (Future)
**Priority: LOW**
**Estimated Time: 1-2 days**

- [ ] Migrate to new namespace (`fxml4_*`)
- [ ] Update dependencies
- [ ] Implement proper package management
- [ ] Create deployment packages

### Phase 5: Cleanup and Documentation 📚 (Not Started)
**Priority: MEDIUM**
**Estimated Time: 2-3 hours**

- [ ] Remove duplicate code
  - [ ] Delete old `/ml/` directory
  - [ ] Remove legacy implementations
  - [ ] Clean up unused scripts

- [ ] Update documentation
  - [ ] Import examples
  - [ ] Architecture diagrams
  - [ ] API documentation
  - [ ] Migration guide

## Progress Tracking

### Completed Tasks ✅
1. **Backtesting System Refactoring** (2024-06-23)
   - Fixed Event initialization issues
   - Consolidated backtesting modules
   - Integrated advanced risk management
   - Created ML strategy bridge
   - Added TimescaleDB integration

### Current Tasks 🔄
- Analyzing full scope of refactoring needs
- Creating migration scripts
- Planning module structure

### Blocked Tasks 🚫
- None currently

## Scripts and Tools

### Available Scripts
1. `scripts/identify_missing_modules.py` - Analyzes import gaps
2. `scripts/migrate_modules.py` - Automates module migration
3. `scripts/refactor_imports_enhanced.py` - Updates import statements

### Commands to Execute

```bash
# Step 1: Analyze current state
python scripts/identify_missing_modules.py

# Step 2: Migrate modules
python scripts/migrate_modules.py

# Step 3: Fix imports
python scripts/refactor_imports_enhanced.py --focus scripts
python scripts/refactor_imports_enhanced.py --focus tests
python scripts/refactor_imports_enhanced.py --focus examples

# Step 4: Run tests
pytest tests/
```

## Risk Assessment

### High Risk Areas
1. **Import Dependencies**: 483+ imports need updating
2. **Test Coverage**: Tests expect non-existent modules
3. **Production Scripts**: May break if imports fail

### Mitigation Strategies
1. Keep legacy structure intact during migration
2. Test incrementally after each phase
3. Use automated tools for import refactoring
4. Maintain rollback capability

## Success Criteria

- [ ] All imports resolve correctly
- [ ] Tests pass without import errors
- [ ] CI/CD pipeline succeeds
- [ ] No duplicate code remains
- [ ] Documentation is updated
- [ ] Package structure follows Python best practices

## Timeline

| Phase | Start Date | End Date | Status |
|-------|------------|----------|---------|
| Phase 1 | 2024-06-23 | TBD | In Progress |
| Phase 2 | TBD | TBD | Not Started |
| Phase 3 | TBD | TBD | Not Started |
| Phase 4 | TBD | TBD | Future |
| Phase 5 | TBD | TBD | Not Started |

## Notes

- Backtesting system successfully refactored as proof of concept
- Import refactoring can be automated with provided scripts
- Legacy code preserved in `/fxml4-monorepo/legacy/` for reference
- New monorepo structure ready for future migration

---

Last Updated: 2024-06-23
Next Review: After Phase 1 completion
