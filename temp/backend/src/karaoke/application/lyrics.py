from ..domain.lrc import parse_lrc,InvalidLRC

class LyricsService:
    def __init__(self,store,provider):self.store=store;self.provider=provider
    def search(self,song_id):
        s=self.store.get_song(song_id)
        if not s.title.strip() or not s.artist.strip():
            raise ValueError('Corrija o título e o artista antes da busca de letras')
        result=self.provider.search(s.title.strip(),s.artist.strip())
        return [{'id':r.get('id'),'track_name':r.get('trackName') or r.get('name'),
                 'artist_name':r.get('artistName'),'duration':r.get('duration'),
                 'synced':bool(r.get('syncedLyrics')),'plain':bool(r.get('plainLyrics')),
                 'preview':(r.get('syncedLyrics') or r.get('plainLyrics') or '')[:500]} for r in result]
    def choose(self,song_id,record_id):
        self.store.get_song(song_id)
        record=self.provider.by_id(record_id)
        if not record:raise ValueError('Letra não encontrada na LRCLIB')
        raw=record.get('syncedLyrics') or record.get('plainLyrics') or ''
        try:lines=parse_lrc(raw);status='LETRA_SINCRONIZADA'
        except InvalidLRC:lines=[];status='LETRA_NAO_SINCRONIZADA'
        if not raw:raise ValueError('Registro sem letra')
        self.store.save_lyrics(song_id,status,raw,'LRCLIB',str(record_id),[(l.ms,l.text) for l in lines])
        return self.store.get_lyrics(song_id)
    def import_lrc(self,song_id,content):
        self.store.get_song(song_id)
        lines=parse_lrc(content)
        self.store.save_lyrics(song_id,'LETRA_SINCRONIZADA',content,'UPLOAD_AUTORIZADO',None,[(l.ms,l.text) for l in lines])
        return self.store.get_lyrics(song_id)
