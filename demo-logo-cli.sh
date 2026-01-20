#!/bin/bash
# ⬢ Synapse CLI Logo Demo
# Demonstrates colored icon variants for terminal use

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║     ⬢ SYNAPSE CLI ICON COLOR VARIANTS                     ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# 1. Standard Magenta (ANSI 35) - naše hlavní barva
echo -e "1. Standard Magenta:   \033[35m⬢\033[0m Synapse v2.1.8"

# 2. Bright Magenta (ANSI 95) - živější
echo -e "2. Bright Magenta:     \033[95m⬢\033[0m Synapse v2.1.8"

# 3. Bold Magenta (nejlepší viditelnost!)
echo -e "3. Bold Magenta:       \033[1;35m⬢\033[0m Synapse v2.1.8  ← DOPORUČENÉ!"

# 4. Blue (alternativa)
echo -e "4. Blue:               \033[34m⬢\033[0m Synapse v2.1.8"

# 5. Bright Blue
echo -e "5. Bright Blue:        \033[94m⬢\033[0m Synapse v2.1.8"

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║     REALISTIC CLI USAGE EXAMPLES                           ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Startup banner
echo -e "\033[1;35m⬢\033[0m \033[1mSynapse\033[0m v2.1.8"
echo "  Pack-first model manager for generative UIs"
echo ""
echo "  Store: ~/.synapse/store"
echo "  Active profile: work__MyPack (3 packs)"
echo "  Connected to: ComfyUI, Forge"
echo ""

# Progress example
echo -e "\033[1;35m⬢\033[0m Importing pack from Civitai..."
sleep 0.3
echo "  → Fetching metadata..."
sleep 0.3
echo "  → Downloading previews... 8/15"
sleep 0.3
echo "  → Processing videos..."
sleep 0.3
echo "  → Building lock file..."
sleep 0.3
echo -e "\033[1;32m✓\033[0m Import complete: \033[1mMyAwesomePack\033[0m"
echo ""

# Notifications
echo -e "\033[1;35m⬢\033[0m Pack update available: CoolPack v2.1.0 → v2.2.0"
echo -e "\033[1;35m⬢\033[0m 3 new models added to store"
echo -e "\033[1;35m⬢\033[0m Profile synced successfully"
echo ""

echo "╔════════════════════════════════════════════════════════════╗"
echo "║     ALTERNATIVE SYMBOLS (all with bold magenta)            ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

echo -e "\033[1;35m⬢\033[0m Synapse  (Black Hexagon - VYBRANÝ!)"
echo -e "\033[1;35m⬡\033[0m Synapse  (White Hexagon)"
echo -e "\033[1;35m⎔\033[0m Synapse  (Hexagon Bold)"
echo -e "\033[1;35m⌬\033[0m Synapse  (Benzene Ring - chemie vibes)"
echo -e "\033[1;35m⎈\033[0m Synapse  (Helm Symbol)"
echo -e "\033[1;35m◬\033[0m Synapse  (Hex with Dot)"
echo ""

echo "╔════════════════════════════════════════════════════════════╗"
echo "║     SIZE COMPARISON (may vary by terminal font)            ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

echo -e "Small:    \033[1;35m⬢\033[0m ⬡ ◬"
echo -e "Medium:   \033[1;35m⎔\033[0m ⌬ ⎈"
echo -e "Letters:  A B C D (for reference)"
echo ""

echo "╔════════════════════════════════════════════════════════════╗"
echo "║     RECOMMENDATION                                         ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo -e "  Symbol:  \033[1;35m⬢\033[0m (Black Hexagon, Unicode U+2B22)"
echo "  Color:   ANSI Bold Magenta (\\033[1;35m)"
echo "  Fallback: If too small, use ⎔ (Hexagon Bold)"
echo ""
echo -e "  Example: \033[1;35m⬢\033[0m \033[1mSynapse\033[0m - Pack-first model manager"
echo ""
