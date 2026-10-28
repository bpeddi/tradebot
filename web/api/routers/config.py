import json

from fastapi import APIRouter, HTTPException

import trading_bot
from web.api.schemas import ConfigModel

router = APIRouter()
CONFIG_PATH = trading_bot._data_path("config.json")


@router.get("")
async def get_config():
    with open(CONFIG_PATH) as f:
        raw = json.load(f)
    # Parse through ConfigModel so fields added after older configs were
    # written (e.g. rotation_weakness_pct) show their default instead of
    # being missing/blank in the UI, without silently rewriting the file.
    return ConfigModel(**raw).model_dump()


@router.put("")
async def update_config(cfg: ConfigModel):
    if cfg.short_window >= cfg.long_window:
        raise HTTPException(400, detail="short_window must be less than long_window")
    if not cfg.symbols:
        raise HTTPException(400, detail="symbols cannot be empty")
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg.model_dump(), f, indent=2)
    return cfg.model_dump()
