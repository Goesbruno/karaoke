Modulo 6A - Letras (backend)

1. Pare API e worker; faça backup de data/ (banco e músicas).
2. Extraia o pacote em pasta temporária; execute o instalador com PowerShell na raiz karaoke: uv run python "CAMINHO_PARA_PASTA_EXTRAIDA\instalar-letras-backend.py".
3. Defina no .env KARAOKE_LRCLIB_CLIENT_ID=KaraokeLAN/0.6 (seu-email@exemplo.org) (nome, versão e contato/URL; não compartilhe dados pessoais se preferir URL).
4. uv run pytest backend/tests/test_lyrics_module.py backend/tests/test_lyrics_api.py ; uv run pytest.
5. Inicie API e worker com uv run --env-file .env ...; LRCLIB depende de internet, biblioteca local continua offline.

API: GET /api/songs/{id}/lyrics/suggestions (host/guest), GET /api/songs/{id}/lyrics (host/guest), PUT /api/songs/{id}/lyrics/lrclib/{record_id} (host), POST /api/songs/{id}/lyrics/import-lrc multipart file (host).
Letra sem timestamps nao e sincronizada; trocar letra não reprocessa audio. Limite 256 KB; timestamps em ms e texto salvos no SQLite.

Esta fase nao inclui interface React nem tela de karaoke; não anuncie canto. Tests com mocks nao confirmam acesso real LRCLIB.
