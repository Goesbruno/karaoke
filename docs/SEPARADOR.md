# Separador de audio (modulo 4)

## Ambiente validado no computador do usuario (Windows 11, GTX 1650 4 GB)
- Python 3.12.14, PyTorch 2.14.0+cu126 (CUDA disponivel), audio-separator 0.47.0, audioread 3.1.0,
  onnxruntime 1.30.0 (CPU), FFmpeg 9.0.2.
- O separador roda em um ambiente proprio (o `sep-test`), chamado por subprocesso via KARAOKE_SEPARATOR_CMD.
  O projeto nao depende de torch; isso isola VRAM/RAM e evita conflitos de versao de Python.
- Recomendado: mover esse ambiente para um caminho curto fora do OneDrive (ex.: C:\karaoke-separator) e atualizar o .env.

## Checkpoint (etapa 1)
- Arquivo: model_bs_roformer_ep_317_sdr_12.9755.ckpt (~639 MB), tipo MDXC, "BS-Roformer-Viperx-1297".
- SHA-256: 5b84f37e8d444c8cb30c79d77f613a41c05868ff9c9ac6c7049c00aefae115aa
  (calculado localmente; igual ao informado por uma copia publica no Hugging Face).
- Licenca dos pesos: NAO VERIFICADA. audio-separator e MIT. Confira a fonte antes de qualquer uso alem do pessoal/educacional.
- O worker recusa iniciar se o checksum divergir.

## Medicoes (clipe de 41,35 s)
| Configuracao | Tempo | Pico VRAM |
|---|---|---|
| autocast, sobreposicao padrao | 7:37 | 2423 MiB |
| fp32, sobreposicao padrao | 1:52 | 3003 MiB |
| autocast, sobreposicao 2 | 4:14 | 2423 MiB |
| fp32, sobreposicao 2 (padrao do projeto) | 1:02 | 3003 MiB |
| fp32, sobreposicao 4 | 1:52 | 3003 MiB |
Extrapolacao (nao medida em musica inteira): ~1,5x a duracao da musica.

## Comportamento sem memoria
1. GPU com parametros padrao. 2. GPU com segmento 128. 3. GPU com segmento 64. 4. CPU (CUDA_VISIBLE_DEVICES=-1).
Erros que nao sao de memoria falham na hora. Cada tentativa fica registrada em processing.json.

## Etapa 2 (lead/backing)
Nao implementada: nenhum modelo foi validado. Instrumental e vocais ficam disponiveis; processing.json marca lead/backing como indisponiveis.
A porta LeadBackingSplitter ja existe para um modelo futuro.

## Tom estimado
Krumhansl-Schmuckler sobre cromagrama (numpy). Retorna "inconclusivo" (sem tom) quando a correlacao ou a margem sao baixas,
e avisa ambiguidade com o tom relativo. Limiares sao heuristicas iniciais, testadas so com sinais sinteticos.

## Arquivos por musica (songs/<uuid>/)
original.<ext>, instrumental.wav, vocals.wav, processing.json (modelo, checksum, parametros, tentativa, dispositivo, tom, avisos).
Publicacao atomica: tudo e validado em .work/ e so entao movido; falhas apagam qualquer arquivo parcial.
