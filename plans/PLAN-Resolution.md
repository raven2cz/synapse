# PLAN: Smart Resolution - Model Discovery & Download

**Version:** v0.1.0
**Status:** DRAFT / FUTURE
**Priority:** Medium
**Created:** 2026-02-19
**Author:** raven2cz + Claude Opus 4.6

---

## 1. Goal

Smart resolution for unresolved pack dependencies: automatically discover, match, and download missing model files.

This plan was extracted from Dependencies Phase 5 (PLAN-Dependencies.md) to give it dedicated scope.

---

## 2. Planned Features

### 2a: Local Model Scanning & Matching
- Scan ComfyUI/Forge/A1111 model directories
- Match local files against unresolved dependencies by filename, hash, or metadata
- Auto-resolve deps that already exist on disk but aren't registered

### 2b: Avatar-Engine AI Recommendations
- Integration with avatar-engine AI agents
- AI suggests correct models for a pack based on description, style, workflow
- Confidence scoring for recommendations

### 2c: Auto-detect Dependencies from Descriptions
- Parse pack/model descriptions for dependency hints
- Extract model references from Civitai descriptions (HTML parsing)
- Suggest dependencies based on workflow analysis

### 2d: Download Orchestration
- Queue-based download system for unresolved deps
- Progress tracking per-dependency
- Retry logic, bandwidth limiting
- Priority ordering (required deps first)

### 2e: Dependency Tree Resolution
- Walk full dependency tree and identify all unresolved items
- Batch resolution suggestions
- One-click "resolve all" for simple cases

---

## 3. Prerequisites

- ✅ Dependencies Phase 1-3 (PLAN-Dependencies.md)
- ✅ Dependencies Phase 4 (UI Polish)
- Blob inventory system (PLAN-Model-Inventory.md)

---

## 4. Open Questions

| Question | Status |
|----------|--------|
| Which model directories to scan? | OPEN - configurable per-UI |
| How to match by hash vs filename? | OPEN - hash preferred, filename fallback |
| Avatar-engine API contract? | OPEN - needs avatar-engine design |
| Download concurrency limits? | OPEN - likely 2-3 concurrent |

---

*Created: 2026-02-19*
*Last Updated: 2026-02-19*
