# Download System Architecture

## Klíčový princip
**VŠECHNY downloady v Synapse MUSÍ jít přes download-asset endpoint.**
Nikdy nevytvářet separátní download cesty (BackgroundTasks, vlastní threading atd.).

## Hlavní endpoint
`POST /api/packs/{pack_name}/download-asset` (`src/store/api.py` ~line 2342)

### Request
```python
class DownloadAssetRequest:
    asset_name: str
    asset_type: Optional[str]    # checkpoint, lora, vae, etc.
    url: Optional[str]           # download URL
    filename: Optional[str]
    group_id: Optional[str]      # pro grupování v UI
    group_label: Optional[str]
```

### Flow
1. Vytvoří entry v `_active_downloads` dict (status: pending)
2. Spustí daemon thread pro download
3. Thread volá `blob_store.download()` s progress callback
4. Progress callback aktualizuje speed/ETA každých 0.5s
5. Po dokončení: symlink, lock update, status: completed

## Tracking endpoints
- `GET /api/packs/downloads/active` — všechny aktivní downloady
- `GET /api/packs/downloads/{id}/progress` — progress jednoho
- `DELETE /api/packs/downloads/completed` — vyčistit dokončené
- `DELETE /api/packs/downloads/{id}` — zrušit download

## Frontend
- **DownloadsPage.tsx** — hlavní Downloads tab s kartami
- **usePackDownloads.ts** — hook pro pack-level download management
- Polling: 2s když aktivní, 10s jinak
- Toast notifikace při dokončení/chybě

## Pro inventory re-download
Správný způsob: volat `POST /api/packs/{pack}/download-asset` s URL z lock filu.
NIKDY: vlastní BackgroundTasks endpoint.
