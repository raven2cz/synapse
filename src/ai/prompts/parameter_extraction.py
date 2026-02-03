"""
Parameter Extraction Prompt

Prompt V2 for AI-powered parameter extraction from model descriptions.

Based on benchmark results from ai_extraction_spec.md:
- 10 optimized rules
- snake_case enforcement
- Anti-grouping, anti-placeholder
- Base model guard (prevents hallucinations)

DO NOT MODIFY without re-benchmarking on the test suite!
Prompt hash: 58ee6eb2db8f (V2)
"""

# fmt: off
PARAMETER_EXTRACTION_PROMPT = """\
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
# fmt: on


def build_extraction_prompt(description: str) -> str:
    """
    Build the full extraction prompt with description appended.

    Args:
        description: Raw model description (may contain HTML)

    Returns:
        Complete prompt ready for AI provider
    """
    return f"{PARAMETER_EXTRACTION_PROMPT}{description}"


# Prompt metadata for tracking and versioning
PROMPT_VERSION = "V2"
PROMPT_HASH = "58ee6eb2db8f"
