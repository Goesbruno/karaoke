"""Rotas da imagem de fundo por música (somente quem pode editar músicas)."""
from fastapi import Depends, File, HTTPException, UploadFile

from ..infrastructure.song_backgrounds import MAX_BYTES, InvalidBackground


def register_background_routes(app, backgrounds, require_edit, require_read):
    @app.get("/api/backgrounds")
    def list_backgrounds(role=Depends(require_read)):
        return {"song_ids": backgrounds.ids()}

    @app.put("/api/songs/{song_id}/background")
    async def put_background(song_id: str, file: UploadFile = File(...), role=Depends(require_edit)):
        raw = await file.read(MAX_BYTES + 1)
        try:
            backgrounds.set(song_id, raw)
        except InvalidBackground as e:
            raise HTTPException(422, str(e))
        return {"has_background": True}

    @app.delete("/api/songs/{song_id}/background")
    def delete_background(song_id: str, role=Depends(require_edit)):
        backgrounds.clear(song_id)
        return {"has_background": False}
