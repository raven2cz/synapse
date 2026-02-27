"""
Practical verification: avatar-engine for multi-task architecture.

Tests:
1. Engine restart with different system prompts
2. Markdown skill as system prompt for structured extraction
3. Provider compatibility (same prompt → same output format)

Run: cd ~/git/github/avatar-engine && uv run python ~/git/github/synapse/tests/experiments/test_engine_tasks.py
"""

import json
import sys
import time

import pytest

# These tests require a running AI provider and are not for CI
pytestmark = pytest.mark.external

# ─── Test data ───────────────────────────────────────────────────────────────

EXTRACTION_SYSTEM_PROMPT = """# Parameter Extraction Task

You are a parameter extraction engine for AI image generation models.

## Instructions

Given a model description, extract ALL generation parameters mentioned.

## Output Format

Return ONLY valid JSON with snake_case keys. No markdown, no explanation.

## Rules

1. Extract ALL parameters (steps, cfg_scale, sampler, scheduler, width, height, clip_skip, denoise, etc.)
2. Use snake_case for all keys
3. Numbers as JSON numbers, not strings
4. If a range is given, use {"min": N, "max": N}
5. If multiple values, use arrays
6. Never invent values not in the description
"""

TRANSLATION_SYSTEM_PROMPT = """# Translation Task

You are a translation engine for AI model descriptions.

## Instructions

Translate the given text to English. Preserve technical terms (model names, parameter names).

## Output Format

Return ONLY valid JSON: {"translation": "...", "source_language": "...", "confidence": 0.0-1.0}

No markdown, no explanation. Just the JSON object.
"""

TEST_DESCRIPTION = """
<p>Great model for anime portraits!</p>
<p>Recommended settings: CFG 7.5, Steps 25-30, Sampler: DPM++ 2M Karras</p>
<p>Resolution: 512x768, Clip Skip 2</p>
<p>Works best with VAE: vae-ft-mse-840000</p>
"""

TEST_TRANSLATION_INPUT = """
这是一个非常好的动漫模型。推荐使用CFG 7，Steps 20-30。
适合生成高质量的二次元插画。
"""


def test_engine_restart_different_prompts(provider: str):
    """Test 1: Can we restart engine with different system prompt?"""
    from avatar_engine import AvatarEngine

    print(f"\n{'='*60}")
    print(f"TEST 1: Engine restart with different prompts ({provider})")
    print(f"{'='*60}")

    engine = AvatarEngine(
        provider=provider,
        system_prompt=EXTRACTION_SYSTEM_PROMPT,
        timeout=120,
        safety_instructions="unrestricted",
    )

    # Phase A: Parameter extraction
    print("\n[Phase A] Starting engine with EXTRACTION prompt...")
    t0 = time.time()
    engine.start_sync()
    print(f"  Engine started in {time.time()-t0:.1f}s")

    print("  Sending extraction request...")
    t0 = time.time()
    resp = engine.chat_sync(TEST_DESCRIPTION)
    dt = time.time() - t0
    print(f"  Response in {dt:.1f}s, success={resp.success}")
    if resp.success:
        print(f"  Content preview: {resp.content[:300]}")
        try:
            parsed = json.loads(resp.content.strip().strip('```json').strip('```').strip())
            print(f"  Parsed keys: {list(parsed.keys())}")
        except json.JSONDecodeError:
            print(f"  [WARN] Could not parse as JSON")
    else:
        print(f"  ERROR: {resp.error}")

    # Stop engine
    print("\n  Stopping engine...")
    engine.stop_sync()
    print("  Engine stopped.")

    # Phase B: Change system prompt and restart
    print("\n[Phase B] Restarting with TRANSLATION prompt...")
    engine._system_prompt = TRANSLATION_SYSTEM_PROMPT
    t0 = time.time()
    engine.start_sync()
    print(f"  Engine restarted in {time.time()-t0:.1f}s")

    print("  Sending translation request...")
    t0 = time.time()
    resp = engine.chat_sync(TEST_TRANSLATION_INPUT)
    dt = time.time() - t0
    print(f"  Response in {dt:.1f}s, success={resp.success}")
    if resp.success:
        print(f"  Content preview: {resp.content[:300]}")
        try:
            parsed = json.loads(resp.content.strip().strip('```json').strip('```').strip())
            print(f"  Parsed keys: {list(parsed.keys())}")
            if "translation" in parsed:
                print(f"  Translation: {parsed['translation'][:100]}")
        except json.JSONDecodeError:
            print(f"  [WARN] Could not parse as JSON")
    else:
        print(f"  ERROR: {resp.error}")

    engine.stop_sync()
    print("\n  [DONE] Engine restart test complete.")
    return True


def test_markdown_as_system_prompt(provider: str):
    """Test 2: Does a full markdown skill file work as system prompt?"""
    from avatar_engine import AvatarEngine
    from pathlib import Path

    print(f"\n{'='*60}")
    print(f"TEST 2: Markdown skill as system prompt ({provider})")
    print(f"{'='*60}")

    # Load actual skill file + append task instructions
    skill_path = Path(__file__).parent.parent.parent / "config" / "avatar" / "skills" / "generation-params.md"
    if not skill_path.exists():
        print(f"  [SKIP] Skill file not found: {skill_path}")
        return False

    skill_content = skill_path.read_text()
    combined_prompt = f"""{skill_content}

---

# Task Instructions

You are a parameter extraction engine. Given a model description, extract ALL generation parameters.
Return ONLY valid JSON with snake_case keys. No markdown, no explanation.
Use the parameter reference above to identify and categorize parameters correctly.
"""

    print(f"  Skill file: {skill_path.name} ({len(skill_content)} bytes)")
    print(f"  Combined prompt: {len(combined_prompt)} bytes")

    engine = AvatarEngine(
        provider=provider,
        system_prompt=combined_prompt,
        timeout=120,
        safety_instructions="unrestricted",
    )

    print("  Starting engine...")
    t0 = time.time()
    engine.start_sync()
    print(f"  Engine started in {time.time()-t0:.1f}s")

    print("  Sending extraction request...")
    t0 = time.time()
    resp = engine.chat_sync(TEST_DESCRIPTION)
    dt = time.time() - t0
    print(f"  Response in {dt:.1f}s, success={resp.success}")

    if resp.success:
        print(f"  Content: {resp.content[:500]}")
        # Try to extract JSON
        content = resp.content.strip()
        # Remove markdown fences if present
        if content.startswith("```"):
            lines = content.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            content = "\n".join(lines)
        try:
            parsed = json.loads(content)
            print(f"\n  PARSED SUCCESSFULLY!")
            print(f"  Keys: {list(parsed.keys())}")
            for k, v in parsed.items():
                print(f"    {k}: {v}")
        except json.JSONDecodeError as e:
            print(f"  [WARN] JSON parse failed: {e}")
    else:
        print(f"  ERROR: {resp.error}")

    engine.stop_sync()
    print("\n  [DONE] Markdown skill test complete.")
    return True


def test_provider_compatibility():
    """Test 3: Same prompt → compare outputs across providers."""
    from avatar_engine import AvatarEngine

    print(f"\n{'='*60}")
    print(f"TEST 3: Provider compatibility")
    print(f"{'='*60}")

    providers = ["gemini", "claude", "codex"]
    results = {}

    for provider in providers:
        print(f"\n--- Testing {provider} ---")
        engine = AvatarEngine(
            provider=provider,
            system_prompt=EXTRACTION_SYSTEM_PROMPT,
            timeout=120,
            safety_instructions="unrestricted",
        )

        try:
            t0 = time.time()
            engine.start_sync()
            startup_time = time.time() - t0
            print(f"  Started in {startup_time:.1f}s")

            t0 = time.time()
            resp = engine.chat_sync(TEST_DESCRIPTION)
            response_time = time.time() - t0

            if resp.success:
                content = resp.content.strip()
                # Clean markdown fences
                if content.startswith("```"):
                    lines = content.split("\n")
                    lines = [l for l in lines if not l.strip().startswith("```")]
                    content = "\n".join(lines).strip()

                try:
                    parsed = json.loads(content)
                    results[provider] = {
                        "success": True,
                        "keys": sorted(parsed.keys()),
                        "values": parsed,
                        "time": response_time,
                        "startup": startup_time,
                    }
                    print(f"  Response in {response_time:.1f}s")
                    print(f"  Keys: {sorted(parsed.keys())}")
                except json.JSONDecodeError:
                    results[provider] = {
                        "success": False,
                        "error": "JSON parse failed",
                        "raw": content[:200],
                    }
                    print(f"  [WARN] JSON parse failed")
                    print(f"  Raw: {content[:200]}")
            else:
                results[provider] = {"success": False, "error": resp.error}
                print(f"  ERROR: {resp.error}")

        except Exception as e:
            results[provider] = {"success": False, "error": str(e)}
            print(f"  EXCEPTION: {e}")
        finally:
            try:
                engine.stop_sync()
            except Exception:
                pass

    # Compare results
    print(f"\n{'='*60}")
    print("COMPARISON")
    print(f"{'='*60}")

    successful = {k: v for k, v in results.items() if v.get("success")}
    if len(successful) >= 2:
        all_keys = set()
        for r in successful.values():
            all_keys.update(r["keys"])

        print(f"\nAll extracted keys: {sorted(all_keys)}")
        print(f"\nPer-provider coverage:")
        for provider, r in successful.items():
            coverage = len(set(r["keys"]) & all_keys) / len(all_keys) * 100
            print(f"  {provider}: {len(r['keys'])} keys ({coverage:.0f}% coverage), {r['time']:.1f}s response, {r['startup']:.1f}s startup")

        # Key overlap
        if len(successful) >= 2:
            providers_list = list(successful.keys())
            for i in range(len(providers_list)):
                for j in range(i+1, len(providers_list)):
                    p1, p2 = providers_list[i], providers_list[j]
                    shared = set(successful[p1]["keys"]) & set(successful[p2]["keys"])
                    print(f"  {p1} ∩ {p2}: {len(shared)} shared keys: {sorted(shared)}")

    return results


def main():
    provider = sys.argv[1] if len(sys.argv) > 1 else "gemini"
    test_num = int(sys.argv[2]) if len(sys.argv) > 2 else 0

    print(f"Avatar-Engine Multi-Task Verification")
    print(f"Provider: {provider}")
    print(f"Test: {'all' if test_num == 0 else test_num}")

    if test_num == 0 or test_num == 1:
        test_engine_restart_different_prompts(provider)

    if test_num == 0 or test_num == 2:
        test_markdown_as_system_prompt(provider)

    if test_num == 3:
        test_provider_compatibility()

    print(f"\n{'='*60}")
    print("ALL TESTS COMPLETE")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
