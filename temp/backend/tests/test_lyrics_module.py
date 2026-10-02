import pytest
from karaoke.domain.lrc import parse_lrc,at_time,InvalidLRC
from karaoke.infrastructure.lrclib_client import LrclibProvider,LyricsProviderError,retry_seconds
from karaoke.infrastructure.lyrics_store import install,save,get,LyricsRepository
from karaoke.infrastructure.sqlite_store import SqliteStore
from karaoke.application.lyrics import LyricsService

def test_lrc_and_offset():
    l=parse_lrc('[ar:X]\n[00:01.20][00:02.005] Olá\n[01:03] Fim')
    assert [(x.ms,x.text) for x in l]==[(1200,'Olá'),(2005,'Olá'),(63000,'Fim')]
    assert at_time(l,1000)==-1 and at_time(l,1000,200)==0 and at_time(l,2000,-800)==0

@pytest.mark.parametrize('text',['sem tempo','[01:70.12] erro','[ar:meta]',''])
def test_invalid_lrc(text):
    with pytest.raises(InvalidLRC):parse_lrc(text)

def test_retry_seconds():
    assert retry_seconds('30')==30 and retry_seconds(None)==60

def test_provider_throttle_and_selection():
    class Response:
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def read(self,n):return b'[{' + b'"id":1,"syncedLyrics":null},{"id":2,"syncedLyrics":"[00:01]hi"}' + b']'
    calls=[]
    def opener(req,timeout):calls.append((req.full_url,req.get_header('User-agent')));return Response()
    c=LrclibProvider('Karaoke/0.6 (admin@example.org)',opener,lambda:0)
    assert c.search('Titulo','Artista')[0]['id']==2
    assert 'track_name=Titulo' in calls[0][0] and calls[0][1]
    with pytest.raises(LyricsProviderError) as exc:c.search('Titulo','Artista')
    assert exc.value.retry_after

def test_store_persistence_and_replacement(tmp_path):
    p=tmp_path/'k.db'; db=SqliteStore(p);install(db);s=db.create_song('T','A',None)
    save(db,s.id,'LETRA_NAO_SINCRONIZADA','sem tempo','LRCLIB','12',[])
    save(db,s.id,'LETRA_SINCRONIZADA','[00:01]Oi','UPLOAD_AUTORIZADO',None,[(1000,'Oi')])
    db2=SqliteStore(p);install(db2)
    assert get(db2,s.id)['lines']==[[1000,'Oi']] and get(db2,s.id)['source']=='UPLOAD_AUTORIZADO'

class Provider:
    def search(self,*a):return [{'id':1,'trackName':'T','artistName':'A','duration':120,'plainLyrics':'texto','syncedLyrics':None}]
    def by_id(self,id):return {'id':id,'plainLyrics':'texto','syncedLyrics':None}

def test_plain_never_sync(tmp_path):
    db=SqliteStore(tmp_path/'k.db');install(db);s=db.create_song('T','A',None)
    svc=LyricsService(LyricsRepository(db),Provider())
    assert not svc.search(s.id)[0]['synced']
    assert svc.choose(s.id,1)['status']=='LETRA_NAO_SINCRONIZADA'
    assert svc.import_lrc(s.id,'[00:01.25] Olá')['status']=='LETRA_SINCRONIZADA'
