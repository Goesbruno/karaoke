Sessão compartilhada LAN

Antes de instalar: pare API e worker, faça backup de data/ e frontend/src.
1. Extraia este pacote numa pasta temporária fora de data/, por exemplo temp-sessao.
2. Na raiz karaoke: uv run python temp-sessao/instalar-sessao-backend.py
3. uv run pytest backend/tests/test_live_session.py backend/tests/test_live_ws.py ; uv run pytest
4. uv run python temp-sessao/instalar-sessao-frontend.py
5. cd frontend; npm test; npm run build; cd ..
6. Reinicie API e worker com uv run --env-file .env ...; recarregue as páginas.

O backend pressupõe FastAPI single process e SQLite compartilhado; não rode uvicorn --workers >1.
Somente host escolhe música, fundo e offset. Todos controlam play/pause/busca/volumes. Convidado nunca constrói AudioContext em Cantar.
Imagens compartilhadas limitadas a 256 KB, armazenadas como data URL no SQLite e distribuídas por WebSocket: protótipo LAN, não armazenamento escalável.
Primeiro host escolhe música e clica Habilitar áudio do host (gesto). Somente após 'host pronto' convidados podem dar play.
Host desconectado pausa estado; reentrada exige novo gesto para habilitar áudio.

Limites: rede / browser variam; sincronismo não é de amostra entre telas; WebSocket autenticado após abertura e fecha em 5s se não houver token; conferir conexões remotas no próprio hardware.
