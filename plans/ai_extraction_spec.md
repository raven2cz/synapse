# AI-Powered Parameter Extraction – Specification & Implementation Plan

## Context

Tato specifikace shrnuje výsledky testování a návrh implementace AI-powered extrakce
generačních parametrů z model descriptions na platformách jako CivitAI a HuggingFace.
Parametry mohou být relevantní pro libovolné Stable Diffusion UI (AUTOMATIC1111,
Forge/Neo, ComfyUI, InvokeAI, Fooocus aj.) a libovolnou modelovou architekturu
(SD 1.5, SDXL, SD3, Flux, Cascade, PixArt, Hunyuan, LTX-Video aj.).
Dokument slouží jako reference pro implementaci v rámci existující Python aplikace,
která aktuálně používá rule-based (regexp) parser.

**Autor:** raven2cz + Claude Opus 4.5  
**Datum testování:** Únor 2026  
**Prostředí:** Arch Linux, Fish shell, RTX 5070 Ti (16 GB VRAM)  
**Prompt verze:** V2 (`58ee6eb2db8f`) — zahrnuje 5 vylepšení z benchmark V1

---

## 1. Testované AI providery

Volání AI probíhá přes CLI subprocessy – žádné API klíče, žádné platby za tokeny.
Uživatel využívá své stávající subskripce (Claude Max, Gemini Pro) a lokální Ollama.

### 1.1 Claude Code (Anthropic)

- **Příkaz:** `claude --print --model <model> "<prompt>"`
- **Subskripce:** Claude Max (týdenní limit zpráv)
- **Doporučený model:** `claude-sonnet-4-20250514`
  - Sonnet je pro extrakci optimální – šetří kvótu oproti Opus
  - Další varianty: `claude-haiku-4-5-20251001` (nejlevnější), `claude-opus-4-5-20251101` (zbytečný overkill)

### 1.2 Gemini CLI (Google)

- **Příkaz:** `gemini --model <model> -p "<prompt>"`
- **Subskripce:** Google AI Pro/Ultra (prakticky neomezené použití)
- **Doporučený model:** `gemini-3-pro-preview`
  - Vyžaduje zapnutí "Preview features" v `/settings` Gemini CLI
  - Další varianty: `gemini-3-flash-preview` (rychlejší), `gemini-2.5-pro` (stabilní GA fallback)

### 1.3 Ollama (lokální)

- **Příkaz:** `ollama run <model> "<prompt>"`
- **Instalace (Arch):** `yay -S ollama-cuda`
- **Spuštění:** `ollama serve` (manuálně, ne jako systemd service – šetří VRAM)
- **Doporučený model:** `qwen2.5:14b` (~9 GB VRAM)
  - 7b verze selhala na složitějších descriptions (broken JSON)
  - 14b na RTX 5070 Ti běží komfortně a generuje validní výstup
  - 32b se nevejde do 16 GB VRAM (potřebuje ~18-20 GB)

---

## 2. Výsledky testování

### 2.1 Pilotní testy (2 descriptions, prompt V1)

Dva počáteční testy ověřily základní funkčnost. Strukturovaný vstup (jednoduché parametry):
100% úspěšnost u všech providerů. Reálná CivitAI description (GhostMix V2.0):
Claude a Gemini 9/9 parametrů, Ollama 9/9 ale nedetekoval base_model.

### 2.2 Benchmark V1 — 13 modelů, prompt V1 (`57dcf524b0a0`)

Komplexní benchmark na 13 diverzních CivitAI descriptions:

**Testovací sada:** 5× SD 1.5, 2× SDXL, 4× Flux, 2× Pony, 1× Universal upscaler.
Typy: 9× Checkpoint, 3× LoRA, 1× Upscaler. Jazyky: EN, EN/CN, EN/JP.
Rozsah popisů: 262–1424 znaků.

| Provider | Úspěšnost | Ø Čas | Ø Klíčů | JSON chyby | Timeouty |
|----------|-----------|-------|---------|------------|----------|
| Ollama qwen2.5:14b | 13/13 | **2.9s** | 10.1 | 0 | 0 |
| Gemini 3 Pro | 13/13 | 21.6s | 8.5 | 0 | 0 |
| Claude Sonnet 4 | 13/13 | 8.1s | **11.5** | 0 | 0 |

**Identifikované problémy:**

| Problém | Provider | Závažnost | Řešení v V2 |
|---------|----------|-----------|-------------|
| Halucinace base_model (MeinaMix → "SDXL" místo SD 1.5) | Ollama | 🔴 Kritické | Rule 9: extract only if explicit |
| Placeholder "..." zkopírován z příkladu | Ollama | 🟡 Střední | Rule 10: never copy placeholders |
| Mezery v názvech klíčů (`"Hires upscaler"`) | Gemini | 🟡 Střední | Rule 2: enforce snake_case |
| Over-nesting (MeinaMix: 6 klíčů místo 14) | Gemini | 🟡 Střední | Rule 3: anti-grouping |
| String ranges ("20-30" místo {min, max}) | Ollama | 🟢 Nízké | Rule 4: numeric ranges |
| Slabá extrakce minimálních popisů (SynthwavePunk: 2 klíče) | Ollama | 🟡 Střední | Rule 1: extract everything |

### 2.3 Prompt V2 — 5 vylepšení

Na základě benchmark V1 byl prompt rozšířen z 6 na 10 pravidel:

1. **Minimální popisy** (Rule 1): Explicitně instruuje extrahovat vše i z krátkých popisů.
2. **snake_case** (Rule 2): Vynucuje konzistentní pojmenování klíčů bez mezer.
3. **Anti-grouping** (Rule 3): Zakazuje zabalení nesouvisejících parametrů do wrapper klíčů.
4. **Numerické rozsahy** (Rule 4): Vyžaduje `{min, max}` s čísly, ne stringy.
5. **Typování čísel** (Rule 8): Čísla jako JSON numbers, ne stringy.
6. **Base model guard** (Rule 9): Extrahovat jen explicitně uvedené, neinferovat.
7. **Anti-placeholder** (Rule 10): Nekopírovat "..." z příkladu.

Příklad v promptu změněn z `{"base_model": "...", "some_parameter": 7, "tips": [...]}` na
`{"base_model": "SDXL 1.0", "sampler": ["DPM++ 2M"], "steps": {"min": 20, "max": 30}}` —
realistické hodnoty místo placeholderů.

### 2.4 Rozšířené evaluační metriky (V2)

Benchmark V2 měří kromě původních metrik také:

| Metrika | Co měří |
|---------|---------|
| `naming_score` | % klíčů v platném snake_case (0–100) |
| `numeric_typing_score` | % čísel jako JSON number, ne string (0–100) |
| `placeholder_count` | Počet "..." hodnot zkopírovaných z promptu |
| `avg_nesting_depth` | Průměrná hloubka vnořování (nižší = flat = lepší parsovatelnost) |
| `wrapper_keys` | Klíče, které zabalují ≥4 nesouvisejících parametrů |

### 2.5 Kvalitativní srovnání (aktualizováno po V1 benchmarku)

| Aspekt | Claude Sonnet 4 | Gemini 3 Pro | Ollama 14b |
|--------|-----------------|--------------|------------|
| Hloubka extrakce | 🥇 Ø 11.5 klíčů | 🥉 Ø 8.5 klíčů | 🥈 Ø 10.1 klíčů |
| Rychlost | 🥈 Ø 8.1s | 🥉 Ø 21.6s | 🥇 Ø 2.9s |
| Konzistence klíčů | 🥇 100% snake_case | 🥉 12 klíčů s mezerami | 🥈 3 camelCase |
| Typování hodnot | 🥇 Číselné rozsahy jako {min,max} | 🥉 Často string ranges | 🥈 Občas string ranges |
| Strukturální přístup | 🥇 Balanced flat+nested | 🥉 Příliš hluboký nesting | 🥈 Flat/denormalized |
| Minimální popisy | 🥇 7 klíčů (SynthwavePunk) | 🥈 6 klíčů | 🥉 2 klíče |
| Halucinace | 🥇 Žádné | 🥇 Žádné | 🥉 base_model halucinace |
| Celková kvalita | 🥇 | 🥈 | 🥉 (pro minimální popisy) |

---

## 3. Doporučená priorita providerů

S ohledem na výsledky benchmarku V1 a praktická omezení subskripcí:

### Priorita 1: Ollama qwen2.5:14b (lokální) — pro bulk operace
- **Nejrychlejší** na GPU (Ø 2.9s, medián 3.2s)
- **Žádné limity**, žádná kvóta, offline
- Uživatelé ComfyUI typicky mají GPU
- **Rizika:** Halucinace base_model, slabý na minimálních popisech — proto V2 prompt
- Doporučení: Post-processing validace na kritických polích (base_model ověřit z metadat)

### Priorita 2: Gemini 3 Pro (cloud fallback)
- **Neomezené použití** s Pro/Ultra subskripcí
- Kvalitní výstup, ale nejpomalejší (Ø 21.6s) a tendence k over-nesting
- V2 prompt by měl zlepšit flat strukturu a snake_case naming
- Gemini i Ollama mohou vracet markdown fences – **parser musí vždy stripovat fences**

### Priorita 3: Claude Sonnet 4 (prémiový fallback)
- **Nejvyšší kvalita** extrakce (Ø 11.5 klíčů, 100% snake_case, žádné halucinace)
- **Omezená kvóta** (Max = týdenní limit) – šetřit na důležitější práci
- Optimální pro výjimečně složité descriptions nebo validaci výsledků jiných providerů

### Rule-based (regexp) – vždy přítomný
- Stávající implementace, žádné závislosti
- Funguje pro jednoduše strukturované descriptions
- Automatický fallback, když žádný AI provider není dostupný/nakonfigurovaný

---

## 4. Architektura integrace

### 4.1 Settings (uživatelská konfigurace)

```
[AI Services]

Enabled AI Providers:
  [✓] Ollama (local)        Model: [qwen2.5:14b    ]  Endpoint: [localhost:11434]
  [✓] Gemini CLI             Model: [gemini-3-pro-preview]
  [ ] Claude Code            Model: [claude-sonnet-4-20250514]

Fallback chain order: Ollama → Gemini → Rule-based
  (řadí se automaticky podle výše uvedené priority,
   nebo uživatel může přeřadit manuálně)

[Advanced]
  CLI timeout (sec):                [60     ]
  Always fallback to rule-based:    [✓]
  Cache AI results:                 [✓]  (stejný description → stejný výsledek)
```

### 4.2 Detekce dostupnosti providerů

Při startu aplikace (nebo při otevření Settings) automaticky ověřit:

```python
import shutil

def detect_available_providers() -> dict:
    """Detect which AI CLI tools are installed and accessible."""
    providers = {}

    # Claude Code
    if shutil.which("claude"):
        providers["claude"] = {"available": True, "command": "claude"}

    # Gemini CLI
    if shutil.which("gemini"):
        providers["gemini"] = {"available": True, "command": "gemini"}

    # Ollama
    if shutil.which("ollama"):
        # Additionally check if server is running
        providers["ollama"] = {"available": True, "command": "ollama"}

    return providers
```

V Settings zobrazit jen dostupné providery a u nedostupných šedý text s instrukcí
pro instalaci.

### 4.3 Volání AI provideru

Každý provider se volá jako subprocess:

```python
import subprocess

def call_ai_provider(provider: str, model: str, prompt: str, timeout: int = 60) -> str:
    """
    Call an AI CLI tool as a subprocess and return the response text.

    Args:
        provider: One of 'claude', 'gemini', 'ollama'.
        model: Model identifier string.
        prompt: The extraction prompt.
        timeout: Maximum wait time in seconds.

    Returns:
        Raw response text from the AI provider.

    Raises:
        subprocess.TimeoutExpired: If the provider takes too long.
        RuntimeError: If the provider returns a non-zero exit code.
    """
    commands = {
        "claude": ["claude", "--print", "--model", model, prompt],
        "gemini": ["gemini", "--model", model, "-p", prompt],
        "ollama": ["ollama", "run", model, prompt],
    }

    result = subprocess.run(
        commands[provider],
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    if result.returncode != 0:
        raise RuntimeError(f"{provider} failed: {result.stderr.strip()}")

    return result.stdout.strip()
```

### 4.4 Parsování odpovědi

Gemini i Ollama mohou vracet JSON obalený v markdown fences – **vždy stripovat**:

```python
import json

def parse_ai_response(response: str) -> dict:
    """
    Parse JSON from AI response, stripping markdown fences if present.

    Args:
        response: Raw text response from AI provider.

    Returns:
        Parsed dictionary with extracted parameters.

    Raises:
        json.JSONDecodeError: If the response is not valid JSON.
    """
    text = response.strip()

    # Strip markdown code fences (```json ... ``` or ``` ... ```)
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]

    return json.loads(text.strip())
```

### 4.5 Fallback chain

```python
def extract_parameters(description: str, settings: Settings) -> dict:
    """
    Extract generation parameters using the configured fallback chain.

    Tries each enabled provider in priority order. Falls back to rule-based
    extraction if all AI providers fail or are disabled.

    Args:
        description: Raw HTML description from CivitAI/ComfyUI.
        settings: User's application settings with provider configuration.

    Returns:
        Dictionary with extracted generation parameters.
    """
    prompt = build_extraction_prompt(description)

    for provider_cfg in settings.ai_fallback_chain:
        if not provider_cfg.enabled:
            continue

        try:
            response = call_ai_provider(
                provider=provider_cfg.provider,
                model=provider_cfg.model,
                prompt=prompt,
                timeout=settings.ai_timeout,
            )
            result = parse_ai_response(response)
            result["_extracted_by"] = provider_cfg.provider
            return result

        except (subprocess.TimeoutExpired, RuntimeError, json.JSONDecodeError) as e:
            logger.warning(f"AI provider {provider_cfg.provider} failed: {e}")
            continue

    # Final fallback: rule-based extraction
    logger.info("All AI providers failed, using rule-based extraction")
    result = extract_parameters_regexp(description)
    result["_extracted_by"] = "rule-based"
    return result
```

### 4.6 Prompt template

#### Designové principy

Prompt musí být **obecný a otevřený**, protože:

1. **Ekosystém UI je fragmentovaný:** AUTOMATIC1111, Forge/Neo, ComfyUI, InvokeAI,
   Fooocus, SD.Next, DrawThings – každý používá jiné názvy parametrů a jiné defaults.
2. **Architektury modelů se rychle mění:** SD 1.5, SDXL, SD3, Flux, Cascade, PixArt,
   Hunyuan, LTXV (video)... každá generace přináší nové parametry.
3. **Autoři descriptions jsou nepředvídatelní:** někdo napíše strukturovaný seznam,
   jiný zabalí parametry do vyprávění, třetí mix EN/CN/JP.
4. **Časový horizont:** za půl roku mohou existovat parametry, o kterých dnes nevíme.

Proto prompt **NESMÍ enumerovat konkrétní klíče** – jen ukázat formát hodnot
jako příklad a explicitně říct "extrahuj VŠE, co tam je".

```python
EXTRACTION_PROMPT = """\
You are an expert in AI image and video generation ecosystems, including all \
Stable Diffusion UIs (AUTOMATIC1111, Forge, ComfyUI, InvokeAI, Fooocus, etc.) \
and all model architectures (SD 1.5, SDXL, SD3, Flux, Cascade, PixArt, \
Hunyuan, LTX-Video, and any future architectures).

Your task: analyze the model description below and extract EVERY generation \
parameter, setting, recommendation, compatibility note, or workflow tip \
mentioned by the author. The description may be in any language or a mix of \
languages, and may contain HTML markup — ignore the markup, focus on content.

Rules:
1. Extract ALL parameters you find, not just common ones. Even for very \
short descriptions, extract everything available: merge components, ratios, \
trigger words, compatibility notes, and any implied usage recommendations.
2. Use consistent snake_case for ALL key names (e.g. "cfg_scale", \
"clip_skip", "hires_fix"). Never use spaces or PascalCase in keys. \
You may still follow the author's terminology for the concept name itself \
(e.g. "guidance" vs "cfg_scale"), but always format the key in snake_case.
3. Each distinct parameter MUST be its own top-level key. Do NOT group \
all parameters under a single wrapper key like "recommended_parameters" \
or "settings". If an author lists sampler, steps, cfg as separate items, \
they should be separate top-level keys in your output. Sub-objects are \
fine for closely related sub-values (e.g. hires_fix: {upscaler, steps, \
denoising}) but NOT for wrapping unrelated parameters together.
4. For parameters with numeric ranges, ALWAYS use {"min": <number>, \
"max": <number>} with actual numeric values — not strings. If only a \
recommended value is given with a range hint, use \
{"recommended": <number>, "min": <number>, "max": <number>}.
5. For parameters with alternatives, use arrays: ["DPM++ 2M", "Euler a"].
6. Include compatibility info, warnings, and tips as separate keys.
7. If the author mentions specific models, LoRAs, embeddings, VAEs, \
upscalers, ControlNets, or any other auxiliary resources, include them.
8. Preserve numeric values exactly as stated (don't round or convert). \
Always output numbers as JSON numbers, not strings (7 not "7").
9. For "base_model": extract ONLY if the author explicitly states it. \
Do NOT guess or infer the base architecture from context.
10. NEVER copy placeholder values like "..." from this prompt. Extract \
real values from the description or omit the key entirely.

Return ONLY valid JSON. No markdown fences, no explanation, no preamble.

The following is a MINIMAL ILLUSTRATIVE example of the output FORMAT — your \
actual output should contain whatever keys match the description content, \
which may be completely different from this example:

{"base_model": "SDXL 1.0", "sampler": ["DPM++ 2M"], "steps": {"min": 20, "max": 30}}

Omit keys where no information is found. Add any keys the description warrants.

Description:
"""


def build_extraction_prompt(description: str) -> str:
    """Build the full extraction prompt with the description appended."""
    return f"{EXTRACTION_PROMPT}{description}"
```

#### Proč je prompt V2 navržen takto

| Designové rozhodnutí | Důvod | Nové ve V2 |
|---------------------|-------|------------|
| Výčet UI a architektur ve scope | AI ví, že má hledat parametry pro celý ekosystém | – |
| "Extract EVERY parameter" + minimální popisy | Zabránit tendenci AI zaměřit se jen na běžné parametry | ✅ Rule 1 |
| snake_case enforcement | Konzistentní klíče pro downstream parsing, bez mezer | ✅ Rule 2 |
| Anti-grouping instrukce | Každý parametr jako top-level klíč, ne zabalený v wrapperu | ✅ Rule 3 |
| Numerické rozsahy jako {min, max} | Strojově parsovatelné rozsahy místo stringů | ✅ Rule 4 |
| Čísla jako JSON numbers | `7` ne `"7"` – správné typování | ✅ Rule 8 |
| Base model guard | Extrahovat jen explicitní, ne inferovat (→ halucinace) | ✅ Rule 9 |
| Anti-placeholder | Nezkopirovávat "..." z příkladu promptu | ✅ Rule 10 |
| Realistický příklad místo "..." | `{"base_model": "SDXL 1.0", "sampler": [...], "steps": {...}}` | ✅ |
| Minimální JSON příklad (3 klíče) | Ukazuje formát, ale je záměrně triviální | – |
| "which may be completely different" | Explicitní signál, že příklad není template | – |
| Žádný fixní seznam klíčů | Future-proof – nové parametry se extrahují automaticky | – |

---

## 5. Cache výsledků

Stejná description → stejné parametry. Cache šetří kvótu i čas:

```python
import hashlib

def get_cache_key(description: str) -> str:
    """Generate a deterministic cache key for a description."""
    return hashlib.sha256(description.encode()).hexdigest()[:16]
```

Cache uložit jako JSON soubor vedle pack.json nebo v centrální cache directory.
Invalidace: při změně description hashe nebo manuálně z UI.

---

## 6. Budoucí rozšíření

Tato architektura (Settings → povolené AI služby → fallback chain → toolchain výběr)
je navržena obecně a lze ji použít i pro další AI-powered funkce v aplikaci:

- **Generování workflow** z extrahovaných parametrů (ComfyUI JSON, A1111 settings)
- **Překlad descriptions** (libovolný jazyk → EN)
- **Automatický tagging** modelů podle obsahu description
- **Doporučení kompatibilních LoRA/embeddings** k checkpointu
- **Analýza preview obrázků** (popis stylu, kvalita, detekce artefaktů)

Pro každý use case se toolchain vybere automaticky podle priority nastavené
uživatelem v Settings, přičemž pořadí se může lišit podle náročnosti úlohy.
Jednodušší úlohy (tagging, překlad) mohou preferovat Ollama, složitější
(workflow generování, analýza obrázků) mohou preferovat cloud providery.

---

## 7. Future: Enriched AI Context (z PLAN-Resolve-Model.md bod 5)

**Status:** ⚠️ ODLOZENO — popsano zde pro budouci implementaci.

**Motivace:** `extract_parameters(description)` nyni dostava pouze textovy popis modelu.
Pri importu z Civitai mame k dispozici dalsi metadata, ktera by AI mohla vyuzit
pro presnejsi extrakci:

| Pole | Zdroj | Priklad |
|------|-------|---------|
| `base_model` | Civitai API `baseModel` | "SDXL", "SD 1.5" |
| `tags` | Civitai model tags | ["anime", "realistic", "sdxl"] |
| `trigger_words` | Civitai `trainedWords` | ["ohwx", "1girl"] |
| `type` | Civitai model type | "LORA", "Checkpoint" |

**Navrhovana zmena API:**
```python
# Soucasne:
extract_parameters(description: str, use_cache: bool = True) -> TaskResult

# Navrzene rozsireni:
extract_parameters(
    description: str,
    use_cache: bool = True,
    metadata_context: Optional[Dict[str, Any]] = None,  # NEW
) -> TaskResult
```

`metadata_context` by se pripojil k promptu jako strukturovany kontext:
```
## Additional Metadata
- Base Model: SDXL
- Type: LORA
- Tags: anime, realistic
- Trigger Words: ohwx, 1girl
```

**Proc odlozeno:**
- AvatarTaskService.execute_task() pouziva task registry s fixnim vstupnim formatem
- Zmena vyzaduje upravu `ParameterExtractionTask` v `src/avatar/tasks/`
- Prompt V2 by se musel rozsirit o sekci pro metadata
- Cache klice by musely zahrnout metadata hash (ne jen description hash)
- Funkcni i bez toho — AI extrahuje z popisu, metadata jen zvysi presnost

**Implementacni kroky (az bude potreba):**
1. Pridat `metadata_context: Optional[Dict]` do `AvatarTaskService.extract_parameters()`
2. Pridat kontext do promptu v `ParameterExtractionTask`
3. Upravit cache klic: `sha256(description + json(metadata_context))`
4. Propagovat metadata z `PackService.import_from_civitai()` do `extract_parameters()`
5. Benchmark: merit zda metadata zvysi kvalitu extrakce

---

## 8. Shrnutí

| Rozhodnutí | Volba | Důvod |
|------------|-------|-------|
| Nejlepší kvalita | Claude Sonnet 4 | Ø 11.5 klíčů, 100% snake_case, žádné halucinace |
| Primární provider | Ollama qwen2.5:14b | Ø 2.9s, offline, bez limitů (s post-validací) |
| Cloud fallback | Gemini 3 Pro | Neomezené s Pro subskripcí |
| Způsob volání | subprocess CLI | Žádné API klíče, využívá existující subskripce |
| Prompt verze | V2 (`58ee6eb2db8f`) | 10 pravidel, řeší halucinace, naming, nesting |
| JSON parsing | Vždy stripovat fences | Gemini a Ollama je často přidávají |
| Cache | SHA-256 hash description | Šetří kvótu, zrychluje opakované volání |
| Settings UX | Auto-detect + manuální override | Zobrazit jen dostupné providery |
| Evaluace | 5 nových metrik | naming_score, numeric_typing, placeholders, nesting, wrappers |
