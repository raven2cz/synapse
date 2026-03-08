# Synapse Project Memory

## KRITICKÁ PRAVIDLA (NIKDY NEPORUŠOVAT)

### 1. VŽDY POUŽÍVAT EXISTUJÍCÍ SYSTÉMY A SLUŽBY
**NIKDY nevytvářet paralelní/separátní implementace** když existuje zavedený systém!

Před implementací JAKÉKOLIV nové funkcionality:
1. **PROHLEDAT CODEBASE** — existuje už služba/komponenta pro tento účel?
2. **NAPOJIT SE** na existující systém, ne vytvářet nový
3. **Zeptat se uživatele** pokud si nejsi jistý

**Konkrétní příklady existujících systémů v Synapse:**
- **Download systém** → `POST /api/packs/{pack}/download-asset` + `_active_downloads` dict + DownloadsPage.tsx polling
  - NIKDY nepoužívat `BackgroundTasks` pro vlastní download cestu!
  - Viz `download-system.md` pro kompletní architektutu
- **Toast notifikace** → `stores/toastStore.ts`
- **Inventory** → `inventory_service.py` + `InventoryPage.tsx`
- **Backup** → `backup_service.py` + API endpointy

### 2. VŽDY ČÍST EXISTUJÍCÍ SPECIFIKACI PŘED IMPLEMENTACÍ
**NIKDY nezačínat implementaci bez přečtení hlavní specifikace!**

Před začátkem práce na JAKÉKOLIV feature:
1. **PROHLEDAT /plans/** — `ls plans/` + `git log --all -- plans/`
2. **PROHLEDAT VŠECHNY BRANCHE** — `git branch -a` + `git log --all --oneline -- plans/PLAN-*.md`
3. **Najít HLAVNÍ specifikaci** — ta co má detailní design, byla reviewovaná Gemini+Codex
4. **NIKDY nevytvářet vlastní PLAN soubor** pokud už existuje specifikace pro danou feature
5. **Zeptat se uživatele** pokud si nejsi jistý která spec je aktivní

**AKTIVNÍ SPECIFIKACE:**
- **Resolve Model Redesign** → `plans/PLAN-Resolve-Model.md` (v0.7.1, 1769 řádků)
  - Reviewováno: Gemini 3.1 (2x) + Codex 5.4 (3x)
  - Stav: SPECIFIKACE HOTOVA — implementace začíná od nuly (Phase 0)
  - Branch: `feat/resolve-model-redesign`

### 3. PO KAŽDÉ FÁZI: 3 REVIEW + VŠECHNY TESTY
**POVINNÝ postup po dokončení každé fáze implementace:**

1. **Claude review** — projít KAŽDÝ nový/změněný soubor, zkontrolovat chyby
2. **Gemini 3.1 review** — `gemini -p "Review these files: <seznam>..." --yolo`
3. **Codex 5.4 review** — `codex review --commit <SHA>` nebo `codex exec "Review..."`
4. **Opravit VŠECHNY nalezené issues** z review
5. **Spustit VŠECHNY testy** — unit + integration + smoke (dle test pyramid)
6. **Teprve potom** commitnout a pokračovat další fází

**NIKDY nepřeskakovat review!** NIKDY nepokračovat další fází bez dokončení review předchozí!

### 4. VŽDY PSÁT TESTY
Každá nová feature MUSÍ mít testy (unit + integration + API-level).
Testy nesmí být povrchní — musí testovat REÁLNÉ chování, ne jen happy path.

### 5. AKTUALIZOVAT PLAN
Po každé změně aktualizovat příslušný PLAN soubor (aditivně, nemazat).

### 6. SESSION BACKUP — VŽDY KOMPLETNÍ ARCHIV
**Při záloze session VŽDY zálohovat CELÝ adresář** `~/.claude/projects/-home-box-git-github-synapse/` jako jeden tar.gz.
- Cílový adresář: `plans/session/`
- Formát: `claude-session-synapse-YYYY-MM-DD.tar.gz`
- VŽDY přepsat/aktualizovat `plans/session/README.md` s instrukcemi pro obnovu
- NIKDY nezálohovat jen jednotlivé `.jsonl` soubory — vždy celý adresář (včetně memory/, sessions-index.json, subdirectories)
- **VŽDY zkopírovat memory soubory i ZVLÁŠŤ** do `plans/session/` (MEMORY.md, download-system.md, patterns.md atd.) — pro snadnou obnovu bez rozbalení celého archivu
- Pozor: archiv bývá ~90 MB, GitHub varuje nad 50 MB (zvážit Git LFS)

### 7. UI DROPDOWNY — ŽÁDNÉ NATIVNÍ `<select>`
**NIKDY nepoužívat nativní `<select>` elementy!** Vždy použít custom themed dropdown (`ThemedSelect` z `components/ui/ThemedSelect.tsx`).
Nativní `<select>` nemá theme aplikace a vypadá cize. Platí pro VŠECHNY dropdowny v celé aplikaci.

## Důležité soubory a systémy

Viz samostatné soubory:
- `download-system.md` — architektura download systému
- `patterns.md` — opakující se vzory a konvence
