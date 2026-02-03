# PLAN: AI Services Integration for Synapse

**Version:** v1.0.0
**Status:** ✅ PHASE 1 COMPLETE (2026-02-03)
**Created:** 2026-02-02
**Updated:** 2026-02-03
**Author:** raven2cz + Claude Opus 4.5
**Branch:** pack-edit

---

## Executive Summary

Synapse jako aplikace pro správu AI modelů by měla sama využívat AI pro pokročilé úlohy.
Uživatelé Synapse jsou typicky AI enthusiasti s přístupem k různým AI službám
(Claude Max, Gemini Pro, lokální Ollama). Tato infrastruktura umožní využít tyto
služby pro automatizaci a inteligentní funkce v rámci Synapse.

**Klíčové principy:**
- **Žádné API klíče v aplikaci** - využíváme CLI nástroje s existujícími subskripcemi uživatele
- **Graceful degradation** - vždy existuje fallback (rule-based, manuální)
- **Uživatel má kontrolu** - volí providery, priority, může vypnout AI úplně
- **Task-specific priority** - různé úlohy mohou preferovat různé providery

---

## 1. Use Cases pro AI v Synapse

### 1.1 Aktuální (Phase 1)

| Use Case | Popis | Složitost | Preferovaný provider |
|----------|-------|-----------|---------------------|
| **Parameter Extraction** | Extrakce generačních parametrů z description | Střední | Ollama (rychlost) |

### 1.2 Plánované (Phase 2+)

| Use Case | Popis | Složitost | Preferovaný provider |
|----------|-------|-----------|---------------------|
| **Description Translation** | Překlad CN/JP/KR descriptions do EN | Nízká | Ollama |
| **Auto-Tagging** | Automatické tagování modelů podle description | Nízká | Ollama |
| **Workflow Generation** | Generování ComfyUI workflow z parametrů | Vysoká | Claude/Gemini |
| **Model Compatibility** | Analýza kompatibility LoRA + Checkpoint | Střední | Gemini |
| **Preview Analysis** | Analýza stylu/kvality z preview obrázků | Vysoká | Claude (multimodal) |
| **Smart Recommendations** | Doporučení modelů podle použití | Střední | Gemini |
| **Config Migration** | Konverze settings mezi UI (A1111 ↔ ComfyUI) | Vysoká | Claude |

### 1.3 Task Complexity Categories

```
┌─────────────────────────────────────────────────────────────────┐
│                    Task Complexity Tiers                         │
├─────────────────────────────────────────────────────────────────┤
│  TIER 1 (Low)     │ Translation, Tagging, Simple extraction     │
│  Default: Ollama  │ Rychlé, offline, žádné limity               │
├───────────────────┼─────────────────────────────────────────────┤
│  TIER 2 (Medium)  │ Parameter extraction, Compatibility check   │
│  Default: Ollama  │ Ollama s Gemini fallback                    │
│  → Gemini         │                                             │
├───────────────────┼─────────────────────────────────────────────┤
│  TIER 3 (High)    │ Workflow generation, Config migration       │
│  Default: Gemini  │ Vyžaduje reasoning, kontext                 │
│  → Claude         │                                             │
├───────────────────┼─────────────────────────────────────────────┤
│  TIER 4 (Premium) │ Image analysis, Complex multi-step tasks    │
│  Default: Claude  │ Multimodal, nejvyšší kvalita                │
└───────────────────┴─────────────────────────────────────────────┘
```

---

## 2. Podporovaní AI Providers

### 2.1 Provider Overview

| Provider | Typ | CLI příkaz | Výhody | Nevýhody |
|----------|-----|------------|--------|----------|
| **Ollama** | Lokální | `ollama run <model>` | Rychlý (2.9s), offline, neomezený | Vyžaduje GPU, občas halucinace |
| **Gemini CLI** | Cloud | `gemini -p` | Neomezený s Pro, kvalitní | Pomalý (21s), vyžaduje internet |
| **Claude Code** | Cloud | `claude --print` | Nejvyšší kvalita | Omezená kvóta (Max = týdenní limit) |

### 2.2 Doporučené modely

**Zdroj:** Benchmark testování (viz [ai_extraction_spec.md](./ai_extraction_spec.md))

#### Ollama (lokální)
| Model | VRAM | Rychlost | Kvalita | Poznámka |
|-------|------|----------|---------|----------|
| `qwen2.5:14b` ⭐ | ~9 GB | Ø 2.9s | Ø 10.1 klíčů | **Doporučený** - optimální poměr |
| `qwen2.5:7b` | ~5 GB | ~2s | Nižší | Pro slabší GPU, občas broken JSON |
| `llama3.1:8b` | ~6 GB | ~3s | Střední | Alternativa k Qwen |
| `qwen2.5:32b` | ~18 GB | ~8s | Vysoká | Nevejde se do 16 GB VRAM |

#### Gemini CLI (cloud)
| Model | Rychlost | Kvalita | Poznámka |
|-------|----------|---------|----------|
| `gemini-3-pro` ⭐ | Ø 21s | Ø 8.5 klíčů | **Doporučený** - vyžaduje Preview features |
| `gemini-3-flash` | ~10s | Střední | Rychlejší varianta Gemini 3 |
| `gemini-3-deep-think` | ~60s | Nejvyšší | Pro komplexní reasoning |
| `gemini-2.5-pro` | ~20s | Vysoká | Stabilní GA fallback |
| `gemini-2.5-flash` | ~8s | Střední | Rychlá varianta, nižší kvalita |

> ⚠️ **Poznámka:** Gemini 2.0 bude deprecated 3. března 2026. Gemini 1.x již nefunguje.

#### Claude Code (cloud)
| Model | Rychlost | Kvalita | Poznámka |
|-------|----------|---------|----------|
| `claude-sonnet-4-20250514` ⭐ | Ø 8.1s | Ø 11.5 klíčů | **Doporučený** - nejvyšší kvalita |
| `claude-haiku-4-5-20251001` | ~3s | Střední | Rychlejší, šetří kvótu |
| `claude-opus-4-5-20251101` | ~15s | Nejvyšší | Overkill pro extrakci |

### 2.3 Detekce dostupnosti

Při startu aplikace automaticky detekovat:

```python
def detect_ai_providers() -> Dict[str, ProviderStatus]:
    """
    Detect which AI CLI tools are installed and accessible.

    Returns dict with:
    - available: bool - CLI tool exists
    - running: bool - service is running (Ollama)
    - models: List[str] - available models (Ollama)
    - version: str - CLI version
    """
```

| Provider | Detekce | Dodatečná kontrola |
|----------|---------|-------------------|
| Ollama | `which ollama` | `ollama list` pro dostupné modely |
| Gemini | `which gemini` | `gemini --version` |
| Claude | `which claude` | `claude --version` |

---

## 3. Settings UI Design

### 3.1 Main Settings Panel

```
┌─────────────────────────────────────────────────────────────────┐
│  ⚙️ Settings                                              [×]   │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐                                                │
│  │ 🤖 AI       │  General │ Storage │ UI │ ...                  │
│  │   Services  │                                                │
│  └─────────────┘                                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  AI Services                                                    │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  Enable AI-powered features    [═══════════○] ON                │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Available Providers                                      │   │
│  ├─────────────────────────────────────────────────────────┤   │
│  │                                                         │   │
│  │  [✓] Ollama (Local)                        ● Running    │   │
│  │      Model: [qwen2.5:14b          ▼]                    │   │
│  │      Endpoint: [http://localhost:11434    ]             │   │
│  │      Status: 3 models available                         │   │
│  │                                                         │   │
│  │  [✓] Gemini CLI (Cloud)                    ● Available  │   │
│  │      Model: [gemini-2.5-pro       ▼]                    │   │
│  │      Preview features: [✓] Enabled                      │   │
│  │                                                         │   │
│  │  [ ] Claude Code (Cloud)                   ○ Available  │   │
│  │      Model: [claude-sonnet-4      ▼]                    │   │
│  │      ⚠️ Limited quota - use sparingly                   │   │
│  │                                                         │   │
│  │  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─  │   │
│  │  ⚪ Rule-based (Fallback)                  ● Always ON  │   │
│  │      No AI required - pattern matching only             │   │
│  │                                                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  [Advanced Settings ▼]                                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Advanced Settings (Expanded)

```
┌─────────────────────────────────────────────────────────────────┐
│  Advanced Settings                                              │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  Timeouts & Retries                                             │
│  ├─ CLI timeout (seconds):        [60        ]                  │
│  ├─ Max retries per provider:     [2         ]                  │
│  └─ Retry delay (seconds):        [1         ]                  │
│                                                                 │
│  Caching                                                        │
│  ├─ Cache AI results:             [✓]                           │
│  ├─ Cache location:               ~/.synapse/store/data/cache/ai/│
│  └─ Cache TTL (days):             [30        ]                  │
│                                                                 │
│  Fallback Behavior                                              │
│  ├─ Always fallback to rule-based: [✓]                          │
│  └─ Show AI provider in results:   [✓]                          │
│                                                                 │
│  Logging                                                        │
│  ├─ Log AI requests:              [✓]                           │
│  └─ Log level:                    [INFO      ▼]                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 3.3 Task Priority Configuration

```
┌─────────────────────────────────────────────────────────────────┐
│  Task Priorities                                                │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  Configure which providers to use for each task type.           │
│  Drag to reorder priority. Unchecked providers are skipped.     │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Parameter Extraction                          [Reset ↺] │   │
│  │ ┌───┐                                                   │   │
│  │ │ ≡ │ [✓] Ollama          qwen2.5:14b       ~3s        │   │
│  │ ├───┤                                                   │   │
│  │ │ ≡ │ [✓] Gemini          gemini-2.5-pro    ~20s       │   │
│  │ ├───┤                                                   │   │
│  │ │ ≡ │ [ ] Claude          claude-sonnet-4   ~8s        │   │
│  │ └───┘                                                   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Workflow Generation                           [Reset ↺] │   │
│  │ ┌───┐                                                   │   │
│  │ │ ≡ │ [✓] Gemini          gemini-2.5-pro    ~25s       │   │
│  │ ├───┤                                                   │   │
│  │ │ ≡ │ [✓] Claude          claude-sonnet-4   ~12s       │   │
│  │ ├───┤                                                   │   │
│  │ │ ≡ │ [ ] Ollama          qwen2.5:14b       ~5s        │   │
│  │ └───┘                                                   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Description Translation                       [Reset ↺] │   │
│  │ ┌───┐                                                   │   │
│  │ │ ≡ │ [✓] Ollama          qwen2.5:14b       ~2s        │   │
│  │ ├───┤                                                   │   │
│  │ │ ≡ │ [ ] Gemini          gemini-2.5-pro    ~15s       │   │
│  │ └───┘                                                   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  [Use Recommended Defaults]                                     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 3.4 Provider Not Available State

```
┌─────────────────────────────────────────────────────────────────┐
│  [ ] Ollama (Local)                           ○ Not Installed   │
│      ────────────────────────────────────────────────────────   │
│      Ollama is not installed on this system.                    │
│                                                                 │
│      Installation:                                              │
│      • Arch Linux: yay -S ollama-cuda                           │
│      • Ubuntu: curl -fsSL https://ollama.com/install.sh | sh    │
│      • macOS: brew install ollama                               │
│                                                                 │
│      After installation, run: ollama pull qwen2.5:14b           │
│                                                                 │
│      [📖 Documentation]  [🔄 Re-detect]                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Data Model

### 4.1 Design Principles

**Flexibilita pro budoucnost:**
- Providery identifikované jako `str`, ne enum (snadné přidávání nových)
- Task types také `str` (nové úlohy bez změny kódu)
- Registry pattern pro dynamické přidávání providerů
- Backwards-compatible JSON schema

### 4.2 Settings Schema

```python
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime

# NOTE: Používáme str místo Enum pro flexibilitu
# Nové providery/tasky lze přidat bez změny kódu

# Well-known providers (pro UI hints, ale ne omezující)
KNOWN_PROVIDERS = ["ollama", "gemini", "claude", "rule_based"]

# Well-known task types
KNOWN_TASKS = [
    "parameter_extraction",
    "description_translation",
    "auto_tagging",
    "workflow_generation",
    "model_compatibility",
    "preview_analysis",
    "config_migration",
]

@dataclass
class ProviderConfig:
    """Configuration for a single AI provider."""
    provider_id: str                      # e.g., "ollama", "gemini", "my_custom_provider"
    enabled: bool = False
    model: str = ""                       # Selected model
    available_models: List[str] = field(default_factory=list)  # Detected/configured models
    endpoint: Optional[str] = None        # Custom endpoint (Ollama)
    extra_args: Dict[str, Any] = field(default_factory=dict)  # Provider-specific settings

@dataclass
class TaskPriorityConfig:
    """Priority chain for a specific task type."""
    task_type: str                        # e.g., "parameter_extraction"
    provider_order: List[str] = field(default_factory=list)  # Provider IDs in order
    custom_timeout: Optional[int] = None  # Override global timeout for this task
    custom_prompt: Optional[str] = None   # Override default prompt template

@dataclass
class AIServicesSettings:
    """
    Complete AI services configuration.

    Stored in: settings.json under "ai_services" key
    """

    # Master switch
    enabled: bool = True

    # Provider configurations (key = provider_id)
    providers: Dict[str, ProviderConfig] = field(default_factory=dict)

    # Task-specific priorities (key = task_type)
    task_priorities: Dict[str, TaskPriorityConfig] = field(default_factory=dict)

    # Advanced settings
    cli_timeout_seconds: int = 60
    max_retries: int = 2
    retry_delay_seconds: int = 1

    # Caching
    cache_enabled: bool = True
    cache_ttl_days: int = 30
    cache_directory: str = "~/.synapse/store/data/cache/ai"

    # Behavior
    always_fallback_to_rule_based: bool = True
    show_provider_in_results: bool = True

    # Logging
    log_requests: bool = True
    log_level: str = "INFO"  # DEBUG, INFO, WARNING, ERROR
    log_prompts: bool = False  # Verbose: log full prompts
    log_responses: bool = False  # Verbose: log raw responses
```

### 4.2 Default Priorities

```python
DEFAULT_TASK_PRIORITIES: Dict[AITaskType, List[AIProvider]] = {
    # Tier 1 - Simple tasks, prefer local
    AITaskType.DESCRIPTION_TRANSLATION: [
        AIProvider.OLLAMA,
        AIProvider.GEMINI,
    ],
    AITaskType.AUTO_TAGGING: [
        AIProvider.OLLAMA,
        AIProvider.GEMINI,
    ],

    # Tier 2 - Medium complexity
    AITaskType.PARAMETER_EXTRACTION: [
        AIProvider.OLLAMA,
        AIProvider.GEMINI,
        AIProvider.CLAUDE,
    ],
    AITaskType.MODEL_COMPATIBILITY: [
        AIProvider.OLLAMA,
        AIProvider.GEMINI,
        AIProvider.CLAUDE,
    ],

    # Tier 3 - High complexity, prefer cloud
    AITaskType.WORKFLOW_GENERATION: [
        AIProvider.GEMINI,
        AIProvider.CLAUDE,
        AIProvider.OLLAMA,
    ],
    AITaskType.CONFIG_MIGRATION: [
        AIProvider.GEMINI,
        AIProvider.CLAUDE,
    ],

    # Tier 4 - Premium tasks
    AITaskType.PREVIEW_ANALYSIS: [
        AIProvider.CLAUDE,  # Multimodal required
        AIProvider.GEMINI,
    ],
}
```

### 4.3 Provider Status (Runtime)

```python
@dataclass
class ProviderStatus:
    """Runtime status of an AI provider."""
    provider: AIProvider
    available: bool = False          # CLI tool exists
    running: bool = False            # Service is running (Ollama)
    version: Optional[str] = None    # CLI version
    models: List[str] = field(default_factory=list)  # Available models
    error: Optional[str] = None      # Last error message
    last_check: Optional[datetime] = None
```

---

## 5. Backend Architecture

### 5.1 Prompt Management

**KRITICKÉ:** Prompty pro AI úlohy jsou klíčové pro kvalitu výstupu.

Pro **Parameter Extraction** používáme **Prompt V2** z [ai_extraction_spec.md](./ai_extraction_spec.md):
- 10 pravidel optimalizovaných na základě benchmarku
- snake_case enforcement
- Anti-grouping, anti-placeholder
- Base model guard (proti halucinacím)

```python
# src/ai/prompts/parameter_extraction.py

# Import prompt from spec - DO NOT MODIFY without re-benchmarking!
PARAMETER_EXTRACTION_PROMPT = """
You are an expert in AI image and video generation ecosystems...
[Full prompt from ai_extraction_spec.md Section 4.6]
"""

def build_extraction_prompt(description: str) -> str:
    """Build the full extraction prompt with description appended."""
    return f"{PARAMETER_EXTRACTION_PROMPT}\n\nDescription:\n{description}"
```

**Pravidla pro úpravu promptů:**
1. Jakákoliv změna vyžaduje re-benchmark na testovací sadě
2. Dokumentovat změny s verzí (hash)
3. A/B testovat proti předchozí verzi

### 5.3 Module Structure

```
src/
├── ai/                           # NEW: AI services module
│   ├── __init__.py
│   ├── providers/
│   │   ├── __init__.py
│   │   ├── base.py              # Abstract base provider
│   │   ├── ollama.py            # Ollama provider
│   │   ├── gemini.py            # Gemini CLI provider
│   │   ├── claude.py            # Claude Code provider
│   │   ├── rule_based.py        # Fallback rule-based
│   │   └── registry.py          # Provider registry (dynamic loading)
│   │
│   ├── tasks/
│   │   ├── __init__.py
│   │   ├── base.py              # Abstract base task
│   │   ├── parameter_extraction.py
│   │   ├── description_translation.py
│   │   └── ...
│   │
│   ├── prompts/                  # Prompt templates
│   │   ├── __init__.py
│   │   └── parameter_extraction.py  # V2 prompt from spec
│   │
│   ├── service.py               # Main AI service (orchestrator)
│   ├── cache.py                 # Result caching
│   ├── detection.py             # Provider auto-detection
│   └── settings.py              # Settings management
│
└── utils/
    └── parameter_extractor.py   # EXISTING: Keep as rule-based fallback
```

### 5.4 Provider Interface

```python
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

class AIProvider(ABC):
    """Abstract base class for AI providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier."""
        pass

    @property
    @abstractmethod
    def cli_command(self) -> str:
        """CLI command name (e.g., 'ollama', 'gemini', 'claude')."""
        pass

    @abstractmethod
    async def execute(
        self,
        prompt: str,
        model: str,
        timeout: int = 60,
    ) -> str:
        """
        Execute a prompt and return the raw response.

        Raises:
            ProviderNotAvailableError: CLI not installed
            ProviderTimeoutError: Execution timed out
            ProviderExecutionError: Non-zero exit code
        """
        pass

    @abstractmethod
    def detect_status(self) -> ProviderStatus:
        """Detect current provider status."""
        pass

    def parse_response(self, response: str) -> Dict[str, Any]:
        """
        Parse JSON response, stripping markdown fences if present.
        Default implementation - can be overridden.
        """
        text = response.strip()

        # Strip markdown code fences
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first line (```json or ```)
            lines = lines[1:]
            # Remove last line if it's closing fence
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)

        return json.loads(text)
```

### 5.5 Task Interface

```python
from abc import ABC, abstractmethod
from typing import Any, Dict

class AITask(ABC):
    """Abstract base class for AI-powered tasks."""

    @property
    @abstractmethod
    def task_type(self) -> AITaskType:
        """Task type identifier."""
        pass

    @property
    @abstractmethod
    def default_priority(self) -> List[AIProvider]:
        """Default provider priority for this task."""
        pass

    @abstractmethod
    def build_prompt(self, input_data: Any) -> str:
        """Build the prompt for this task."""
        pass

    @abstractmethod
    def parse_result(self, raw_result: Dict[str, Any]) -> Any:
        """Parse and validate the AI response."""
        pass

    def get_cache_key(self, input_data: Any) -> str:
        """Generate cache key for input data."""
        return hashlib.sha256(str(input_data).encode()).hexdigest()[:16]
```

### 5.6 AI Service (Orchestrator)

```python
class AIService:
    """
    Main AI service - orchestrates providers and tasks.

    Handles:
    - Provider selection based on task priorities
    - Fallback chain execution
    - Result caching
    - Error handling and retries
    """

    def __init__(self, settings: AIServicesSettings):
        self.settings = settings
        self.providers: Dict[AIProvider, AIProviderBase] = {}
        self.cache = AICache(settings)
        self._init_providers()

    async def execute_task(
        self,
        task: AITask,
        input_data: Any,
        force_provider: Optional[AIProvider] = None,
    ) -> TaskResult:
        """
        Execute an AI task with fallback chain.

        Args:
            task: Task to execute
            input_data: Input data for the task
            force_provider: Override priority, use specific provider

        Returns:
            TaskResult with output and metadata
        """
        # Check cache first
        cache_key = task.get_cache_key(input_data)
        if cached := self.cache.get(task.task_type, cache_key):
            return cached

        # Build prompt
        prompt = task.build_prompt(input_data)

        # Get provider priority for this task
        priority = self._get_priority(task.task_type, force_provider)

        # Try each provider in order
        last_error = None
        for provider_type in priority:
            provider = self.providers.get(provider_type)
            if not provider or not self._is_provider_enabled(provider_type):
                continue

            try:
                raw_response = await provider.execute(
                    prompt=prompt,
                    model=self._get_model(provider_type),
                    timeout=self.settings.cli_timeout_seconds,
                )

                parsed = provider.parse_response(raw_response)
                result = task.parse_result(parsed)

                task_result = TaskResult(
                    success=True,
                    output=result,
                    provider=provider_type,
                    cached=False,
                )

                # Cache successful result
                self.cache.set(task.task_type, cache_key, task_result)

                return task_result

            except Exception as e:
                last_error = e
                logger.warning(f"Provider {provider_type} failed: {e}")
                continue

        # All providers failed - try rule-based fallback
        if self.settings.always_fallback_to_rule_based:
            try:
                fallback = self.providers[AIProvider.RULE_BASED]
                result = await fallback.execute_task(task, input_data)
                return TaskResult(
                    success=True,
                    output=result,
                    provider=AIProvider.RULE_BASED,
                    cached=False,
                )
            except Exception as e:
                last_error = e

        # Complete failure
        return TaskResult(
            success=False,
            error=str(last_error),
            provider=None,
        )
```

---

## 6. API Endpoints

### 6.1 Settings API

```python
# GET /api/settings/ai
# Returns current AI settings + provider status

@router.get("/settings/ai")
def get_ai_settings() -> AISettingsResponse:
    """
    Get AI services settings and current provider status.

    Returns:
        settings: Current AIServicesSettings
        provider_status: Dict of ProviderStatus for each provider
    """

# PATCH /api/settings/ai
# Update AI settings

@router.patch("/settings/ai")
def update_ai_settings(update: AISettingsUpdate) -> AISettingsResponse:
    """Update AI services settings."""

# POST /api/settings/ai/detect
# Re-detect available providers

@router.post("/settings/ai/detect")
def detect_providers() -> Dict[str, ProviderStatus]:
    """Re-detect available AI providers."""

# POST /api/settings/ai/test/{provider}
# Test a specific provider

@router.post("/settings/ai/test/{provider}")
def test_provider(provider: str) -> ProviderTestResult:
    """Test a specific provider with a simple prompt."""
```

### 6.2 Task Execution API

```python
# POST /api/ai/extract-parameters
# Extract parameters using AI

@router.post("/ai/extract-parameters")
async def extract_parameters(
    request: ParameterExtractionRequest,
) -> ParameterExtractionResponse:
    """
    Extract generation parameters from description using AI.

    Request:
        description: str - Model description (may contain HTML)
        force_provider: Optional[str] - Override default priority

    Response:
        parameters: Dict[str, Any] - Extracted parameters
        provider: str - Which provider was used
        cached: bool - Whether result was from cache
        confidence: float - Extraction confidence (0-1)
    """
```

---

## 7. Frontend Components

### 7.1 Component Structure

```
apps/web/src/
├── components/
│   └── modules/
│       └── settings/
│           ├── AIServicesSettings.tsx      # Main settings panel
│           ├── ProviderCard.tsx            # Single provider config
│           ├── TaskPriorityConfig.tsx      # Task priority editor
│           ├── ProviderStatusBadge.tsx     # Status indicator
│           └── ProviderInstallGuide.tsx    # Installation help
│
├── hooks/
│   ├── useAISettings.ts                    # Settings management
│   ├── useProviderStatus.ts                # Provider status polling
│   └── useAITask.ts                        # Task execution
│
└── lib/
    └── ai/
        ├── types.ts                        # TypeScript types
        └── api.ts                          # API client
```

### 7.2 TypeScript Types

```typescript
// lib/ai/types.ts

// Flexibilní typy - string místo enum pro rozšiřitelnost
export type ProviderId = string  // "ollama" | "gemini" | "claude" | custom
export type TaskType = string    // "parameter_extraction" | custom

// Well-known providers (for UI hints)
export const KNOWN_PROVIDERS = ['ollama', 'gemini', 'claude', 'rule_based'] as const
export const KNOWN_TASKS = [
  'parameter_extraction',
  'description_translation',
  'auto_tagging',
  'workflow_generation',
  'model_compatibility',
  'preview_analysis',
  'config_migration',
] as const

export interface ProviderConfig {
  providerId: string
  enabled: boolean
  model: string
  availableModels: string[]
  endpoint?: string
  extraArgs?: Record<string, unknown>
}

export interface ProviderStatus {
  providerId: string
  available: boolean
  running: boolean
  version?: string
  models: string[]
  error?: string
  lastCheck?: string
}

export interface TaskPriorityConfig {
  taskType: string
  providerOrder: string[]  // Provider IDs
  customTimeout?: number
  customPrompt?: string
}

export interface AIServicesSettings {
  enabled: boolean
  providers: Record<string, ProviderConfig>
  taskPriorities: Record<string, TaskPriorityConfig>
  cliTimeoutSeconds: number
  maxRetries: number
  retryDelaySeconds: number
  cacheEnabled: boolean
  cacheTtlDays: number
  cacheDirectory: string
  alwaysFallbackToRuleBased: boolean
  showProviderInResults: boolean
  logRequests: boolean
  logLevel: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR'
  logPrompts: boolean
  logResponses: boolean
}

export interface TaskResult<T = unknown> {
  success: boolean
  output?: T
  error?: string
  provider?: string
  cached: boolean
  executionTimeMs?: number
}

// Extraction specific
export interface ParameterExtractionResult {
  parameters: Record<string, unknown>
  extractedBy: string  // Provider ID
  confidence?: number
  rawKeys?: string[]   // Original keys before normalization
}
```

---

## 8. Implementation Phases

### Phase 1: Foundation ✅ COMPLETE (2026-02-03)
**Goal:** Basic infrastructure + Parameter Extraction + Integration + Full Settings UI

**Klíčové výstupy:**
- ✅ Automatická extrakce parametrů při Civitai importu
- ✅ Fallback chain: `ollama → gemini → claude → rule_based`
- ✅ Ollama auto-start/stop pro správu VRAM
- ✅ Cache s SHA-256[:16] klíčem
- ✅ `_extracted_by` badge v PackParametersSection
- ✅ Settings UI dle spec 3.1-3.4 (viz 8.1.5)
- ✅ 72 testů prochází

---

#### 8.1.1 Backend: AI Module ✅ COMPLETE (2026-02-02)

| Soubor | Stav | Popis |
|--------|------|-------|
| `src/ai/__init__.py` | ✅ | Hlavní exporty |
| `src/ai/providers/base.py` | ✅ | Abstract provider + JSON fence stripping |
| `src/ai/providers/ollama.py` | ✅ | `ollama run <model> <prompt>` |
| `src/ai/providers/gemini.py` | ✅ | `gemini --model <model> -p <prompt>` |
| `src/ai/providers/claude.py` | ✅ | `claude --print --model <model> <prompt>` |
| `src/ai/providers/rule_based.py` | ✅ | Wrapper pro stávající `parameter_extractor.py` |
| `src/ai/providers/registry.py` | ✅ | Dynamická registrace providerů |
| `src/ai/service.py` | ✅ | Orchestrator s fallback chain |
| `src/ai/cache.py` | ✅ | SHA-256[:16] cache s TTL |
| `src/ai/detection.py` | ✅ | Auto-detect providerů |
| `src/ai/settings.py` | ✅ | Datové modely (str místo enum) |
| `src/ai/prompts/parameter_extraction.py` | ✅ | Prompt V2 (10 pravidel) |
| `src/ai/tasks/base.py` | ✅ | Task interface |
| `src/ai/tasks/parameter_extraction.py` | ✅ | Extraction task |

**Testy:** 63 testů (28 providers + 14 cache + 21 service)

---

#### 8.1.2 Backend: API Endpoints ✅ COMPLETE

Přidáno do `src/store/api.py` (`ai_router`):

| Endpoint | Metoda | Popis |
|----------|--------|-------|
| `/api/ai/providers` | GET | Detekce dostupných providerů |
| `/api/ai/extract` | POST | Extrakce parametrů (standalone) |
| `/api/ai/cache/stats` | GET | Statistiky cache |
| `/api/ai/cache` | DELETE | Vyčištění cache |
| `/api/ai/cache/cleanup` | POST | Cleanup expirovaných |
| `/api/ai/settings` | GET | Aktuální nastavení |

---

#### 8.1.3 Backend: Integrace do Import Flow ✅ COMPLETE (2026-02-03)

**Automatická extrakce při Civitai importu funguje!**

| Úkol | Stav | Soubor | Popis |
|------|------|--------|-------|
| Napojit AIService na import | ✅ | `src/store/pack_service.py:544` | Použit `AIService.extract_parameters()` |
| Přidat `_extracted_by` do výsledku | ✅ | `src/ai/service.py:216` | Přidává provider ID do výstupu |
| Uložit provider info do pack | ✅ | `src/store/models.py` | Pole `parameters_source` + `_extracted_by` |
| Ollama auto-start/stop | ✅ | `src/ai/providers/ollama.py` | Auto-start `ollama serve`, auto-stop po extrakci |
| AI Response normalizace | ✅ | `src/store/models.py:500-586` | Normalizuje AI formát (listy, ranges, resolution) |

**Ollama lifecycle management:**
```python
# src/ai/providers/ollama.py
class OllamaProvider(AIProvider):
    def __init__(self, auto_start_server=True, auto_stop_server=True):
        # Automaticky spouští ollama serve pokud neběží
        # Automaticky zastavuje po extrakci (uvolní VRAM)

    def _start_server(self) -> bool:
        # Spustí ollama serve v background
        # Čeká max 30s na ready

    def _stop_server(self) -> None:
        # Zastaví server pouze pokud jsme ho my spustili
```

**atexit cleanup:**
```python
# Registrován cleanup handler pro případ ukončení aplikace
atexit.register(_cleanup_server)
```

---

#### 8.1.4 Backend: Opravy ✅ COMPLETE

| Úkol | Stav | Popis |
|------|------|-------|
| Gemini model name | ✅ | Změněno na `gemini-3-pro-preview` (ověřeno - `gemini-3-pro` vrací 404) |
| Přidat `_extracted_by` | ✅ | Do výstupu přidán provider ID (dle spec 4.5) |
| Zachovat VŠECHNY AI fields | ✅ | Normalizace NEmaže žádná pole - AI Notes se ukládají |

---

#### 8.1.5 Frontend: Settings UI ✅ COMPLETE (2026-02-03)

| Komponenta | Stav | Popis |
|------------|------|-------|
| `AIServicesSettings.tsx` | ✅ | Hlavní panel dle spec 3.1 - master switch, provider cards, cache |
| `ProviderCard.tsx` | ✅ | Enable/disable, model dropdown, endpoint input (Ollama) |
| `AdvancedAISettings.tsx` | ✅ | Spec 3.2 - timeouts, retries, cache TTL, logging |
| `TaskPriorityConfig.tsx` | ✅ | Spec 3.3 - drag & drop provider reordering |
| `StatusBadge` (inline) | ✅ | Running/Available/Not Installed |
| `InstallationGuide` | ✅ | Spec 3.4 - installation instructions per provider |
| `useAIProviders` | ✅ | Hook pro detekci providerů |
| `useAISettings` | ✅ | Hook pro settings (GET) |
| `useUpdateAISettings` | ✅ | Hook pro settings (PATCH) |
| `useAICacheStats` | ✅ | Hook pro cache statistiky |
| TypeScript typy | ✅ | `apps/web/src/lib/ai/types.ts` |

**API Endpoints (nové):**
- ✅ `PATCH /api/ai/settings` - Update AI settings

**Implementováno dle specifikace:**
- ✅ Spec 3.1 - Main Settings Panel (master switch, provider enable/disable, model dropdown, endpoint)
- ✅ Spec 3.2 - Advanced Settings (timeouts, retries, cache TTL, logging)
- ✅ Spec 3.3 - Task Priority Config (drag & drop reordering)
- ✅ Spec 3.4 - Provider Not Available state (installation instructions per platform)

---

#### 8.1.6 Frontend: Integration ✅ COMPLETE

| Úkol | Stav | Popis |
|------|------|-------|
| Zobrazit `_extracted_by` v UI | ✅ | Badge s Bot ikonou v PackParametersSection |
| Settings v navigaci | ✅ | AI Services sekce v SettingsPage |
| Typy v pack-detail | ✅ | `_extracted_by`, `parameters_source` v types.ts |

---

#### 8.1.7 Phase 1 Checklist ✅ COMPLETE

**Backend Infrastructure:** ✅ COMPLETE
- [x] AI module structure
- [x] All 4 providers (Ollama, Gemini, Claude, Rule-based)
- [x] Service orchestrator with fallback
- [x] Caching system (SHA-256[:16], TTL 30 days)
- [x] Provider detection
- [x] Prompt V2 (10 pravidel)
- [x] API endpoints (7 endpointů včetně PATCH /settings)
- [x] Unit tests (63 testů)

**Backend Integration:** ✅ COMPLETE
- [x] **Integrate AIService into Civitai import flow** ✅
- [x] Add `_extracted_by` to results ✅
- [x] Fix Gemini model name (`gemini-3-pro-preview`) ✅
- [x] Ollama auto-start/stop (VRAM management) ✅
- [x] AI Response normalization (lists, ranges, resolution) ✅
- [x] Preserve ALL AI fields (compatibility, usage_tips, etc.) ✅
- [x] **ai_router connected in main.py** ✅ (2026-02-03 fix)

**Frontend:** ✅ COMPLETE (2026-02-03)
- [x] AIServicesSettings component ✅
- [x] ProviderCard component ✅
- [x] AdvancedAISettings component ✅
- [x] TaskPriorityConfig component ✅
- [x] useAIProviders, useAISettings, useAICacheStats hooks ✅
- [x] useUpdateAISettings hook ✅
- [x] Display `_extracted_by` badge in UI ✅
- [x] Settings navigation (AI Services sekce) ✅
- [x] TypeScript typy ✅
- [x] **Enable/disable per provider** ✅ (spec 3.1)
- [x] **Model dropdown per provider** ✅ (spec 3.1)
- [x] **Endpoint input (Ollama)** ✅ (spec 3.1)
- [x] **Advanced Settings accordion** ✅ (spec 3.2)
- [x] **Task Priority Config (drag & drop)** ✅ (spec 3.3)
- [x] **Provider Not Available state** ✅ (spec 3.4)
- [x] **Settings PATCH API + persistence** ✅

**Tests:** ✅ COMPLETE
- [x] 72 AI-related tests pass ✅
- [x] TypeScript compilation passes ✅

---

#### 8.1.8 AI Insights vs Custom Parameters - ARCHITECTURE FIX ✅ COMPLETE (2026-02-03)

**Status:** ✅ OPRAVENO - AI Insights a Custom Parameters jsou nyní oddělené

**Commits:**
- `c4b606c` - fix: Properly separate AI Insights from Custom Parameters
- `8285740` - fix: Resolve button nesting DOM warning in EditParametersModal
- `90c506e` - fix: Keep user custom params visible in EditParametersModal

---

##### PROBLEM ANALYSIS

**Hlavní problém:** AI Insights jsou NESPRÁVNĚ kategorizovány jako 'custom' a nelze rozlišit od user custom params.

**Root cause:** Používali jsme pouze `_extracted_by` boolean pro rozlišení, ale to označuje celý pack, ne jednotlivá pole.

**Důsledky:**
1. AI Insights (usage_tips, compatibility, recommended_embeddings...) → `category = 'custom'`
2. User-defined custom params → `category = 'custom'`
3. Nelze je rozlišit!
4. V EditParametersModal se AI notes mísí s user custom params
5. Při uložení dochází ke ztrátě nebo přepisování dat

---

##### IMPLEMENTED SOLUTION ✅

**Klíčový princip:** Trackovat jednotlivá AI-extrahovaná pole pomocí `_ai_fields` array, ne pouze pack-level `_extracted_by`.

```
┌─────────────────────────────────────────────────────────────────┐
│  DATA FLOW - Parameter Types (IMPLEMENTED)                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Backend (src/ai/service.py):                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  AI extraction output:                                   │   │
│  │  {                                                       │   │
│  │    "cfg_scale": 7,           ← AI-extracted, KNOWN       │   │
│  │    "usage_tips": "...",      ← AI-extracted, UNKNOWN     │   │
│  │    "_extracted_by": "gemini", ← Provider ID              │   │
│  │    "_ai_fields": ["cfg_scale", "usage_tips", ...]        │   │
│  │  }                            ↑ NEW! Tracks AI fields    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Frontend decision logic:                                       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  For each field:                                         │   │
│  │                                                          │   │
│  │  isAiField = _ai_fields.includes(key)                    │   │
│  │  isKnownParam = PARAM_CATEGORIES contains key            │   │
│  │                                                          │   │
│  │  if (isAiField && isKnownParam)     → Show in category   │   │
│  │  if (isAiField && !isKnownParam)    → AI Insights only   │   │
│  │  if (!isAiField && !isKnownParam)   → Custom Parameters  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Klíčové principy implementace:**

1. **`_ai_fields`** = array of field names that came from AI extraction
2. **AI Insights** = fields in `_ai_fields` that are NOT in `PARAM_CATEGORIES`
3. **Custom Parameters** = fields NOT in `_ai_fields` and NOT in `PARAM_CATEGORIES`
4. **Known params** = fields in `PARAM_CATEGORIES` (regardless of source)

---

##### ACTUAL IMPLEMENTATION ✅

**1. Backend: `src/ai/service.py` - Add `_ai_fields` tracking**

```python
# src/ai/service.py:216 (in execute_task method)
# Add _extracted_by to output if configured (per spec 4.5)
if self.settings.show_provider_in_results and isinstance(parsed, dict):
    parsed["_extracted_by"] = result.provider_id
    # Track which fields came from AI (for distinguishing from user custom fields)
    parsed["_ai_fields"] = [k for k in parsed.keys() if not k.startswith("_")]
```

**Proč:** `_ai_fields` je array názvů polí, která přišla z AI extrakce. To umožňuje frontend rozlišit:
- AI-extracted unknown field → AI Insights (read-only)
- User-added unknown field → Custom Parameters (editable)

**2. Frontend: `PackParametersSection.tsx` - Use `_ai_fields` for filtering**

```typescript
// PackParametersSection.tsx - categorizedParams useMemo
const aiFields = (parameters._ai_fields as unknown as string[] | undefined) ?? []

for (const [key, value] of Object.entries(parameters)) {
  // ...
  const isFromAi = aiFields.includes(key)

  // Skip unknown fields from AI extraction - they belong to AI Insights!
  if (isFromAi && category === 'custom') continue

  // User custom fields (NOT in aiFields) go to Custom category
  result[category].push([key, value, paramDef])
}

// PackParametersSection.tsx - aiNotes useMemo
const aiFields = (parameters._ai_fields as unknown as string[] | undefined) ?? []

for (const [key, value] of Object.entries(parameters)) {
  const category = getParamCategory(key)
  const isFromAi = aiFields.includes(key)

  // Include in AI Insights if:
  // - It's a known AI note key (whitelist), OR
  // - It's an unknown field that came from AI extraction
  const isUnknownFromAi = isFromAi && category === 'custom' && !isInternalField

  if (AI_NOTES_KEYS.has(key) || isUnknownFromAi) {
    notes.push({ key, value, label })
  }
}
```

**3. Frontend: `EditParametersModal.tsx` - Filter AI fields from edit**

```typescript
// EditParametersModal.tsx - useEffect for modal open
useEffect(() => {
  if (isOpen) {
    const stringified: Record<string, string> = {}
    // Get list of AI-extracted field names (not user-added custom fields)
    const aiFields = (initialParameters._ai_fields as unknown as string[] | undefined) ?? []

    for (const [key, value] of Object.entries(initialParameters)) {
      if (key.startsWith('_')) continue

      // Skip AI-extracted unknown fields - they belong to AI Insights
      // BUT keep user-added custom fields (they're NOT in _ai_fields array)
      const isAiField = aiFields.includes(key)
      const isKnownParam = Boolean(getParamDef(key))
      if (isAiField && !isKnownParam) continue

      stringified[key] = String(value ?? '')
    }
    setParameters(stringified)
  }
}, [isOpen, initialParameters])
```

**Proč toto funguje:**
- `_ai_fields` obsahuje pouze pole extrahovaná AI
- User custom param "test" NENÍ v `_ai_fields` → zobrazí se v editoru
- AI insight "usage_tips" JE v `_ai_fields` a není known param → NEzobrazí se v editoru

---

##### TASK CHECKLIST

| Úkol | Stav | Popis |
|------|------|-------|
| Backend: Add `_ai_fields` tracking | ✅ | `src/ai/service.py:216` - tracks AI-extracted field names |
| Frontend: Fix `categorizedParams` | ✅ | Uses `_ai_fields` to skip AI unknown fields from Custom |
| Frontend: Fix `aiNotes` useMemo | ✅ | Uses `_ai_fields` to include AI unknown fields in AI Insights |
| Frontend: Fix EditParametersModal load | ✅ | Uses `_ai_fields` to filter AI insights but keep user custom |
| Frontend: Fix EditParametersModal save | ✅ | Preserves `_ai_fields`, `_extracted_by` on save |
| Frontend: Fix button nesting DOM warning | ✅ | `CategorySection` restructured - button and dropdown are siblings |
| Styling AI Insights sekce | ✅ | Lightbulb icon, read-only display |
| Tests | ✅ | verify.sh passes, TypeScript OK |

---

##### PŘÍKLAD - JAK MÁ VYPADAT VÝSLEDEK

**Input (AI response):**
```json
{
  "cfg_scale": 7,
  "steps": 25,
  "sampler": "DPM++ 2M Karras",
  "usage_tips": "Best results with portrait",
  "compatibility": "Works with SD 1.5",
  "recommended_embeddings": ["EasyNegative", "BadHands"],
  "_extracted_by": "gemini"
}
```

**Display - PackParametersSection:**
```
┌─────────────────────────────────────────────────────────────────┐
│ Generation Settings                            [🤖 gemini] [Edit]│
├─────────────────────────────────────────────────────────────────┤
│ ⚙️ Generation                                                    │
│   [CFG Scale: 7] [Steps: 25] [Sampler: DPM++ 2M Karras]         │
├─────────────────────────────────────────────────────────────────┤
│ 💡 AI Insights (read-only)                                       │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │ Usage Tips: Best results with portrait                  │   │
│   │ Compatibility: Works with SD 1.5                        │   │
│   │ Recommended Embeddings: EasyNegative • BadHands         │   │
│   └─────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────┤
│ 🔧 Custom Parameters (prázdné - uživatel nic nepřidal)           │
│   No custom parameters.                                         │
└─────────────────────────────────────────────────────────────────┘
```

**EditParametersModal - Co se zobrazí:**
```
┌─────────────────────────────────────────────────────────────────┐
│ Edit Generation Parameters                                  [×] │
├─────────────────────────────────────────────────────────────────┤
│ ⚙️ Generation                                                    │
│   CFG Scale: [7      ] [-][+]                                   │
│   Steps:     [25     ] [-][+]                                   │
│   Sampler:   [DPM++ 2M Karras    ]                              │
├─────────────────────────────────────────────────────────────────┤
│ 🔧 Custom (Add your own parameters)                              │
│   [Parameter name] [Value] [Type ▼] [Category ▼] [+ Add]        │
├─────────────────────────────────────────────────────────────────┤
│ ℹ️ AI Insights are preserved but not editable here.              │
├─────────────────────────────────────────────────────────────────┤
│                              [Cancel] [Save]                     │
└─────────────────────────────────────────────────────────────────┘
```

**Klíčové:** AI Insights (usage_tips, compatibility, recommended_embeddings) se NEZOBRAZUJÍ v edit modal, ale jsou ZACHOVÁNY při uložení!

---

##### RELATED FILES (ACTUAL CHANGES)

| Soubor | Změna |
|--------|-------|
| `src/ai/service.py` | Added `_ai_fields` array to track AI-extracted field names |
| `PackParametersSection.tsx` | Uses `_ai_fields` in categorizedParams and aiNotes useMemo |
| `EditParametersModal.tsx` | Uses `_ai_fields` to filter AI unknown fields, fixed button nesting |

---

### Phase 2: Polish & More Tasks
**Goal:** Production-ready + additional tasks

- [ ] Frontend: AI Notes display (viz 8.1.8) ← VYSOKÁ PRIORITA
- [ ] Backend: Task priority configuration
- [ ] Backend: Advanced caching (TTL, invalidation)
- [ ] Backend: Retry logic
- [ ] Frontend: TaskPriorityConfig component
- [ ] Frontend: Provider status polling
- [ ] Task: Description translation (+ AI Notes překlad)
- [ ] Task: Auto-tagging
- [ ] Documentation

### Phase 3: Advanced Tasks
**Goal:** Complex AI tasks

- [ ] Task: Workflow generation
- [ ] Task: Model compatibility analysis
- [ ] Task: Config migration
- [ ] Task: Preview analysis (multimodal)
- [ ] Performance optimization
- [ ] Metrics & logging dashboard

---

## 9. Resolved Questions ✅

| Otázka | Rozhodnutí |
|--------|------------|
| **Settings storage** | `settings.json` (součást hlavního configu) |
| **Cache location** | `~/.synapse/store/data/cache/ai/` |
| **Custom models** | Defaults z benchmarku + možnost zadat vlastní |
| **Offline mode** | Ollama je offline provider, pak rule-based fallback |
| **Ruční extrakce z UI** | ❌ NECHCEME - extrakce je POUZE automatická při importu |

### Otevřené otázky

| Otázka | Status |
|--------|--------|
| Rate limiting pro cloud? | ❓ Prozatím nepotřebujeme |
| Avatar priorita? | ❓ Future vision, později |

---

## 10. Logging & Debugging

### 10.1 Log Categories

```python
# Logging prefixes for AI operations
LOG_PREFIX = "[ai-service]"

# Log levels by operation type
LOGGING_CONFIG = {
    "provider_detection": "INFO",      # Which providers found
    "task_execution": "INFO",          # Task started, provider used
    "fallback": "WARNING",             # Provider failed, trying next
    "cache_hit": "DEBUG",              # Cache used
    "cache_miss": "DEBUG",             # Cache miss, calling AI
    "response_parse": "DEBUG",         # JSON parsing details
    "timeout": "WARNING",              # Provider timeout
    "error": "ERROR",                  # Unrecoverable errors
}
```

### 10.2 Log Format Examples

```
[ai-service] Task: parameter_extraction, Provider: ollama (qwen2.5:14b)
[ai-service] Response received in 2.8s, parsing JSON...
[ai-service] Extracted 12 parameters: cfg_scale, steps, sampler, ...
[ai-service] Result cached with key: a1b2c3d4e5f6

[ai-service] WARNING: Provider ollama failed: timeout after 60s
[ai-service] Fallback to gemini (gemini-3-pro)
[ai-service] Response received in 18.2s

[ai-service] Cache hit for key: a1b2c3d4e5f6 (age: 2d 4h)
```

### 10.3 Debug Mode

V Settings možnost zapnout verbose logging:
- Logovat celý prompt (může být velký!)
- Logovat raw response před parsováním
- Logovat cache operations

---

## 11. Testing Strategy

### 11.1 Unit Tests

```python
# tests/unit/ai/test_providers.py
class TestOllamaProvider:
    def test_detect_availability(self): ...
    def test_execute_simple_prompt(self): ...
    def test_parse_response_with_fences(self): ...
    def test_timeout_handling(self): ...

class TestGeminiProvider:
    def test_detect_availability(self): ...
    def test_model_selection(self): ...
    def test_preview_features_required(self): ...

class TestClaudeProvider:
    def test_detect_availability(self): ...
    def test_print_flag_usage(self): ...
```

### 11.2 Integration Tests

```python
# tests/integration/ai/test_parameter_extraction.py
class TestParameterExtractionE2E:
    """
    End-to-end tests using real providers (skipped if not available).
    """

    @pytest.mark.skipif(not ollama_available(), reason="Ollama not running")
    def test_extraction_ollama_real(self): ...

    @pytest.mark.skipif(not gemini_available(), reason="Gemini CLI not installed")
    def test_extraction_gemini_real(self): ...

    def test_fallback_chain(self): ...
    def test_cache_hit(self): ...
    def test_all_providers_fail_uses_rule_based(self): ...
```

### 11.3 Benchmark Tests

```python
# tests/benchmark/ai/test_extraction_quality.py
class TestExtractionQuality:
    """
    Quality benchmarks from ai_extraction_spec.md test suite.
    13 diverse CivitAI descriptions.
    """

    BENCHMARK_DESCRIPTIONS = [
        ("GhostMix V2.0", "...", {"expected_keys": 9}),
        ("MeinaMix", "...", {"expected_keys": 14}),
        ("SynthwavePunk", "...", {"expected_keys": 7}),  # Minimal
        # ... 10 more
    ]

    def test_extraction_coverage(self, provider): ...
    def test_snake_case_compliance(self, result): ...
    def test_numeric_typing(self, result): ...
    def test_no_placeholder_values(self, result): ...
    def test_no_hallucinated_base_model(self, result): ...
```

### 11.4 Mock Provider for Development

```python
# src/ai/providers/mock.py
class MockProvider(AIProviderBase):
    """
    Mock provider for development and testing.
    Returns predefined responses without calling external services.
    """

    def __init__(self, responses: Dict[str, str]):
        self.responses = responses
        self.call_count = 0

    async def execute(self, prompt: str, **kwargs) -> str:
        self.call_count += 1
        # Return based on prompt hash or content matching
        return self.responses.get(hash(prompt), "{}")
```

---

## 12. Future Vision: AI Assistant Avatar 🚀

### 12.1 Koncept

Interaktivní AI avatar v pravém dolním rohu aplikace, který:
- **Mluví** - TTS (text-to-speech) pro odpovědi
- **Poslouchá** - STT (speech-to-text) pro příkazy
- **Pomáhá** - kontextová nápověda, průvodce složitými úkoly
- **Analyzuje** - vysvětluje co vidí v UI, doporučuje akce

### 12.2 Use Cases

| Scénář | Příklad interakce |
|--------|-------------------|
| **Onboarding** | "Vítej v Synapse! Chceš ti ukážu jak importovat první model?" |
| **Troubleshooting** | "Vidím, že máš 3 unresolved dependencies. Chceš je stáhnout?" |
| **Doporučení** | "Pro tento LoRA bych doporučil CFG 7 a 25 kroků." |
| **Workflow help** | "Potřebuješ vytvořit ComfyUI workflow? Řekni mi co chceš generovat." |
| **Voice commands** | "Hej Synapse, importuj model z této URL." |

### 12.3 Technická architektura (draft)

```
┌─────────────────────────────────────────────────────────────────┐
│                      AI Assistant Avatar                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│  │   STT    │───▶│  Intent  │───▶│    AI    │───▶│   TTS    │  │
│  │ (Whisper)│    │  Parser  │    │ Provider │    │(Coqui/11)│  │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘  │
│       ▲                               │                         │
│       │                               ▼                         │
│  ┌──────────┐                  ┌──────────────┐                 │
│  │   Mic    │                  │  UI Actions  │                 │
│  │  Input   │                  │  (mutations) │                 │
│  └──────────┘                  └──────────────┘                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Komponenty:**
- **STT:** Whisper (lokální) nebo cloud API
- **Intent Parser:** Rozpoznání příkazů vs. konverzace
- **AI Provider:** Využití existující AI infrastruktury
- **TTS:** Coqui TTS (lokální, open-source) nebo ElevenLabs (premium)
- **Avatar UI:** Animovaný avatar (možná AI-generated face)

### 12.4 Implementation Phases (Future)

1. **Phase A:** Text chat bubble (no voice)
2. **Phase B:** TTS output (avatar mluví)
3. **Phase C:** STT input (voice commands)
4. **Phase D:** Context awareness (ví co uživatel dělá)
5. **Phase E:** Proactive suggestions (sám nabízí pomoc)

### 12.5 Future Vision: AI Image Generation 🎨

Gemini CLI podporuje generování obrázků, což otevírá další možnosti pro Synapse:

#### Dostupné nástroje

| Nástroj | Typ | Příkaz | Poznámka |
|---------|-----|--------|----------|
| **Gemini CLI + MCP** | Cloud | MCP server (Imagen, Veo) | Integrováno v Gemini CLI |
| **gemini-imagen** | Cloud | `pip install gemini-imagen` | Samostatný CLI tool |
| **Imagen 4.0** | Cloud | Via Gemini API | Nejnovější model |

#### Modely pro image generation

| Model | Kvalita | Rychlost | Poznámka |
|-------|---------|----------|----------|
| `gemini-2.5-flash-image` | Střední | Rychlý | Pro rychlé náhledy |
| `gemini-3-pro-image-preview` | Vysoká | Pomalejší | Pro kvalitní výstupy |
| `imagen-4.0` | Nejvyšší | Střední | Dedikovaný image model |

#### Potenciální use cases pro Synapse

| Funkce | Popis |
|--------|-------|
| **Thumbnail generation** | Automatické generování náhledů pro packy bez preview |
| **Preview suggestion** | "Jak by mohl vypadat výstup s těmito parametry?" |
| **Style transfer** | Ukázka jak by LoRA změnilo styl obrázku |
| **Missing preview** | Doplnění chybějících preview pro modely |
| **Avatar face** | Generování tváře pro AI Assistant Avatar |

#### Příklad použití

```bash
# Standalone CLI
pip install gemini-imagen
gemini-imagen "preview image for anime style LoRA, high quality"

# Nebo přes Gemini CLI s MCP
gemini --tool imagen "generate preview thumbnail"
```

> ⚠️ **Poznámka:** Image generation je resource-intensive a má rate limity.
> Vhodné spíše pro on-demand funkce než automatické zpracování.

### 12.6 Agent Tool Calling 🔧

**Problém:** S rostoucím počtem AI funkcí (extrakce parametrů, dependency resolver, workflow suggestions, auto-tagging...) by vznikla "kupa AI tlačítek" rozházených po UI.

**Řešení:** Agent s tool calling - jednotný vstupní bod, který zná dostupné funkce a umí je volat.

#### Architektura

```
┌─────────────────────────────────────────────────────────────────┐
│                    Agent Tool Calling                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  User Input (text/voice)                                        │
│       │                                                         │
│       ▼                                                         │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  AI Agent (gemini/claude)                                 │  │
│  │  ┌────────────────────────────────────────────────────┐  │  │
│  │  │  System prompt:                                     │  │  │
│  │  │  "You are Synapse assistant. You have these tools:" │  │  │
│  │  │  - extract_parameters(pack_name)                    │  │  │
│  │  │  - resolve_dependencies(pack_name)                  │  │  │
│  │  │  - suggest_workflow(pack_name, style)               │  │  │
│  │  │  - translate_description(pack_name, target_lang)    │  │  │
│  │  │  - auto_tag(pack_name)                              │  │  │
│  │  │  - analyze_compatibility(lora, checkpoint)          │  │  │
│  │  └────────────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────┘  │
│       │                                                         │
│       ▼                                                         │
│  Tool Call: extract_parameters("GhostMix")                      │
│       │                                                         │
│       ▼                                                         │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Backend API                                              │  │
│  │  POST /api/ai/extract { pack_name: "GhostMix" }          │  │
│  └──────────────────────────────────────────────────────────┘  │
│       │                                                         │
│       ▼                                                         │
│  Agent Response: "Extrahoval jsem 12 parametrů pro GhostMix..." │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### Dostupné Tools (plánované)

| Tool | Popis | API Endpoint |
|------|-------|--------------|
| `extract_parameters` | Re-extrakce parametrů pro starší packy | `POST /api/ai/extract` |
| `resolve_dependencies` | Najít a navrhnout chybějící závislosti | `POST /api/ai/resolve-deps` |
| `suggest_workflow` | Navrhnout ComfyUI workflow | `POST /api/ai/suggest-workflow` |
| `translate_description` | Přeložit popis do jiného jazyka | `POST /api/ai/translate` |
| `auto_tag` | Automatické tagování packu | `POST /api/ai/auto-tag` |
| `analyze_compatibility` | Analýza kompatibility LoRA + Checkpoint | `POST /api/ai/compatibility` |

#### Příklady interakcí

```
User: "Extrahuj parametry pro GhostMix, má starší verzi bez AI dat"
Agent: [calls extract_parameters("GhostMix")]
Agent: "Hotovo! Extrahoval jsem 12 parametrů: CFG 7, Steps 25, Sampler DPM++..."

User: "Tento LoRA mi hlásí chybějící závislosti, pomoz mi"
Agent: [calls resolve_dependencies("MyLoRA")]
Agent: "Našel jsem 2 chybějící závislosti: anime_base.safetensors a EasyNegative..."

User: "Jak by vypadal workflow pro portrait fotky s tímto LoRA?"
Agent: [calls suggest_workflow("MyLoRA", "portrait")]
Agent: "Navrhuji tento workflow: KSampler → VAE Decode → ..."
```

#### Výhody oproti jednotlivým tlačítkům

1. **Jednotný vstupní bod** - uživatel se nemusí učit kde jsou která tlačítka
2. **Kontext-aware** - agent ví na jakém packu uživatel pracuje
3. **Kombinovatelné** - agent může volat více tools najednou
4. **Natural language** - uživatel popisuje co chce, ne jak to udělat
5. **Rozšiřitelné** - přidání nového tool = jen registrace v systému

#### Implementation Notes

- Agent bude využívat existující AI infrastrukturu (providers, fallback chain)
- Tools budou implementovány jako API endpointy
- Frontend: chat bubble komponenta v pravém dolním rohu
- Backend: tool registry s JSON schema pro každý tool

---

> ⚠️ **Poznámka:** Toto je dlouhodobá vize. Implementace závisí na:
> - Dostupnosti kvalitních lokálních TTS/STT modelů
> - Uživatelské poptávce
> - Komplexitě integrace s UI

---

## 13. References

### Dokumentace
- [AI Extraction Spec](./ai_extraction_spec.md) - **KRITICKÉ:** Výsledky benchmarku, prompt V2, best practices
- [Parameter Extractor](../src/utils/parameter_extractor.py) - Stávající rule-based implementace

### Provider dokumentace
- [Ollama Documentation](https://ollama.com/docs)
- [Gemini CLI GitHub](https://github.com/google-gemini/gemini-cli)
- [Gemini Models](https://ai.google.dev/gemini-api/docs/models)
- [Claude Code](https://claude.ai/claude-code)

### Future (Avatar)
- [Coqui TTS](https://github.com/coqui-ai/TTS) - Open-source TTS
- [Whisper](https://github.com/openai/whisper) - Open-source STT
- [ElevenLabs](https://elevenlabs.io/) - Premium TTS API

---

*Last Updated: 2026-02-03 (Agent Tool Calling vision added)*

---

## 14. Logging Summary

### 14.1 Logging je kompletní v celém toolchainu

| Modul | Loguje | Příklad |
|-------|--------|---------|
| `service.py` | Provider chain, fallback, cache | `[ai-service] Task: parameter_extraction, Provider chain: ollama → gemini → claude` |
| `ollama.py` | Execute, server start/stop | `[ai-service] Starting ollama serve...` / `[ai-service] Stopping ollama serve (freeing VRAM)` |
| `gemini.py` | Execute, response | `[ai-service] Task: executing, Provider: gemini (gemini-3-pro-preview)` |
| `claude.py` | Execute, response | `[ai-service] Task: executing, Provider: claude (claude-sonnet-4)` |
| `cache.py` | Hit/miss, cleanup | `[ai-service] Cache hit for key: abc123 (age: 2.1d)` |

### 14.2 Ověření logů z reálného běhu

```
INFO  [ai-service] Task: parameter_extraction, Provider chain: ollama → gemini → claude
INFO  [ai-service] Task: executing, Provider: ollama (qwen2.5:14b)
INFO  [ai-service] Retry 1/2 for ollama
INFO  [ai-service] Retry 2/2 for ollama
WARNING [ai-service] Fallback: ollama failed, trying next...
INFO  [ai-service] Task: executing, Provider: gemini (gemini-3-pro-preview)
DEBUG [ai-service] Raw response length: 53
INFO  [ai-service] Extracted 3 parameters
INFO  [ai-service] Response received in 11.7s, extracted 3 parameters
DEBUG [ai-service] Result cached with key: 8b6abd297254a584
```

**Ollama JE volána** - logy potvrzují retry logiku, pak fallback na Gemini.
