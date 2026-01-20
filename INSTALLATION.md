# 🧙 Import Wizard v2.6.0 - Installation Guide

Tato feature přidává **Import Wizard** do Browse Civitai stránky - modal pro výběr verzí, preview options a thumbnail.

---

## 📋 Co je v balíčku

```
synapse-import-wizard-v2.6.0/
├── INSTALLATION.md                    # Tento soubor
├── apps/web/src/components/
│   ├── ui/
│   │   └── ImportWizardModal.tsx      # ✅ Hlavní modal komponenta
│   └── modules/
│       └── BROWSE_PAGE_PATCH.tsx      # 📝 Instrukce pro BrowsePage
├── src/api/
│   └── IMPORT_WIZARD_ENDPOINTS.py     # 📝 Backend endpointy (patch)
└── tests/
    └── test_import_wizard.py          # ✅ Testy
```

---

## 🔧 Instalace - Krok za krokem

### 1️⃣ Kopíruj ImportWizardModal.tsx

```bash
cp apps/web/src/components/ui/ImportWizardModal.tsx \
   /path/to/synapse/apps/web/src/components/ui/
```

### 2️⃣ Přidej Backend Endpoint do src/store/api.py

Otevři `src/store/api.py` a přidej tento endpoint do `v2_packs_router`:

```python
# Přidej tyto imports na začátek
from fastapi import Query
import re

# Přidej tento endpoint PŘED existující @v2_packs_router.post("/import")
@v2_packs_router.get("/import/preview")
def import_preview(url: str = Query(..., description="Civitai model URL")):
    """Fetch model info for Import Wizard."""
    from config.settings import get_config
    from src.clients.civitai_client import CivitaiClient
    
    # Parse model ID from URL
    match = re.search(r'civitai\.com/models/(\d+)', url)
    if not match:
        raise HTTPException(status_code=400, detail="Invalid Civitai URL")
    
    model_id = int(match.group(1))
    
    # Fetch from Civitai
    config = get_config()
    client = CivitaiClient(api_token=config.api.civitai_token)
    model_data = client.get_model(model_id)
    
    if not model_data:
        raise HTTPException(status_code=404, detail="Model not found")
    
    # Build response
    versions = []
    thumbnails = []
    
    for v in model_data.get("modelVersions", []):
        files = [{"id": f.get("id"), "name": f.get("name"), "sizeKB": f.get("sizeKB")} 
                 for f in v.get("files", [])]
        
        versions.append({
            "id": v.get("id"),
            "name": v.get("name"),
            "base_model": v.get("baseModel"),
            "files": files,
            "image_count": len([i for i in v.get("images", []) if not i.get("url", "").endswith(".mp4")]),
            "video_count": len([i for i in v.get("images", []) if i.get("url", "").endswith(".mp4")]),
        })
        
        for img in v.get("images", [])[:10]:
            url = img.get("url", "")
            thumbnails.append({
                "url": url,
                "version_id": v.get("id"),
                "nsfw": img.get("nsfw", False),
                "type": "video" if ".mp4" in url or "transcode=true" in url else "image",
            })
    
    creator = model_data.get("creator", {})
    
    return {
        "model_id": model_id,
        "model_name": model_data.get("name"),
        "creator": creator.get("username") if isinstance(creator, dict) else None,
        "model_type": model_data.get("type"),
        "base_model": versions[0]["base_model"] if versions else None,
        "versions": versions,
        "thumbnail_options": thumbnails[:20],
    }
```

### 3️⃣ Rozšiř Import Endpoint o Wizard Parametry

Najdi existující `import_pack` endpoint a rozšiř `ImportRequest`:

```python
# Uprav ImportRequest class - přidej tyto fieldy:
class ImportRequest(BaseModel):
    url: str
    download_previews: bool = True
    add_to_global: bool = True
    # NOVÉ FIELDY PRO WIZARD:
    version_ids: Optional[List[int]] = None
    download_images: bool = True
    download_videos: bool = True
    include_nsfw: bool = True
    thumbnail_url: Optional[str] = None
```

### 4️⃣ Integruj Wizard do BrowsePage.tsx

Otevři `apps/web/src/components/modules/BrowsePage.tsx`:

#### 4.1 Přidej Imports

```tsx
import { ImportWizardModal, type ModelVersion, type ImportOptions } from '@/components/ui/ImportWizardModal'
import { Sparkles } from 'lucide-react'
```

#### 4.2 Přidej State

```tsx
// Přidej do BrowsePage function:
const [showImportWizard, setShowImportWizard] = useState(false)
const [wizardModelData, setWizardModelData] = useState<{
  modelId: number
  modelName: string
  versions: ModelVersion[]
} | null>(null)
const [isLoadingWizardPreview, setIsLoadingWizardPreview] = useState(false)
```

#### 4.3 Přidej Funkce

```tsx
// Přidej po existujících handlerech:
const openImportWizard = useCallback(async (modelId: number, modelName: string) => {
  setIsLoadingWizardPreview(true)
  try {
    const res = await fetch(`/api/packs/import/preview?url=https://civitai.com/models/${modelId}`)
    if (!res.ok) throw new Error('Failed to fetch')
    const data = await res.json()
    
    const versions: ModelVersion[] = (data.versions || []).map((v: any) => ({
      id: v.id,
      name: v.name,
      baseModel: v.base_model,
      files: v.files || [],
      images: (data.thumbnail_options || [])
        .filter((t: any) => t.version_id === v.id)
        .map((t: any) => ({ url: t.url, nsfw: t.nsfw, type: t.type })),
    }))
    
    // Pokud první verze nemá images, přiřaď všechny thumbnails
    if (versions.length > 0 && versions[0].images.length === 0) {
      versions[0].images = (data.thumbnail_options || []).map((t: any) => ({
        url: t.url, nsfw: t.nsfw, type: t.type
      }))
    }
    
    setWizardModelData({ modelId: data.model_id, modelName: data.model_name, versions })
    setShowImportWizard(true)
  } catch (error) {
    addToast('error', 'Failed to load model data')
    if (confirm('Import directly?')) importMutation.mutate(`https://civitai.com/models/${modelId}`)
  } finally {
    setIsLoadingWizardPreview(false)
  }
}, [addToast, importMutation])

const handleWizardImport = useCallback(async (
  selectedVersionIds: number[],
  options: ImportOptions,
  thumbnailUrl?: string
) => {
  if (!wizardModelData) return
  
  const res = await fetch('/api/packs/import', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      url: `https://civitai.com/models/${wizardModelData.modelId}`,
      version_ids: selectedVersionIds,
      download_images: options.downloadImages,
      download_videos: options.downloadVideos,
      include_nsfw: options.includeNsfw,
      thumbnail_url: thumbnailUrl,
    }),
  })
  
  const data = await res.json()
  if (!data.success) throw new Error(data.message || 'Import failed')
  
  addToast('success', `Imported ${data.pack_name}`)
  queryClient.invalidateQueries({ queryKey: ['packs'] })
  setShowImportWizard(false)
  setSelectedModel(null)
}, [wizardModelData, addToast, queryClient])
```

#### 4.4 Nahraď Import Tlačítko

Najdi v modal detail tlačítko pro import a nahraď:

```tsx
<Button
  onClick={() => openImportWizard(modelDetail.id, modelDetail.name)}
  disabled={isLoadingWizardPreview}
>
  {isLoadingWizardPreview ? <Loader2 className="animate-spin" /> : <Sparkles />}
  Import...
</Button>
```

#### 4.5 Přidej Wizard Modal

Na konec JSX, před poslední `</div>`:

```tsx
{wizardModelData && (
  <ImportWizardModal
    isOpen={showImportWizard}
    onClose={() => { setShowImportWizard(false); setWizardModelData(null) }}
    onImport={handleWizardImport}
    modelName={wizardModelData.modelName}
    versions={wizardModelData.versions}
    isLoading={importMutation.isPending}
  />
)}
```

---

## 🧪 Testování

```bash
# Backend testy
pytest tests/test_import_wizard.py -v

# Frontend build
cd apps/web && npm run build

# Ruční test
1. Spusť aplikaci: ./scripts/start-all.sh
2. Jdi na Browse Civitai
3. Vyhledej model
4. Klikni na model → klikni "Import..."
5. Wizard by se měl otevřít s verzemi a options
```

---

## 📡 API Endpoints

### GET /api/packs/import/preview

Získá info o modelu pro wizard.

**Query:** `url=https://civitai.com/models/12345`

**Response:**
```json
{
  "model_id": 12345,
  "model_name": "Model Name",
  "versions": [
    {"id": 67890, "name": "v1.0", "files": [...], "image_count": 5}
  ],
  "thumbnail_options": [
    {"url": "...", "type": "image", "nsfw": false}
  ]
}
```

### POST /api/packs/import

Import s wizard options.

**Body:**
```json
{
  "url": "https://civitai.com/models/12345",
  "version_ids": [67890],
  "download_images": true,
  "download_videos": true,
  "include_nsfw": false,
  "thumbnail_url": "https://..."
}
```

---

## ⚠️ Troubleshooting

| Problém | Řešení |
|---------|--------|
| Wizard se neotevře | Zkontroluj konzoli pro chyby, ověř že endpoint existuje |
| "Failed to fetch" | Ověř že backend běží a Civitai API token je nastaven |
| TypeScript chyby | Zkontroluj že ImportWizardModal exportuje správné typy |
| Import nefunguje | Ověř že ImportRequest má nové fieldy (version_ids, etc.) |

---

## ✅ Checklist

- [ ] ImportWizardModal.tsx zkopírován do `components/ui/`
- [ ] `/api/packs/import/preview` endpoint přidán
- [ ] `ImportRequest` rozšířen o wizard fieldy
- [ ] BrowsePage má nové state proměnné
- [ ] BrowsePage má `openImportWizard` a `handleWizardImport` funkce
- [ ] Import tlačítko volá `openImportWizard`
- [ ] `<ImportWizardModal>` přidán do JSX
- [ ] Build projde bez chyb
- [ ] Wizard se otevře a funguje

---

**Happy Importing! 🚀**
