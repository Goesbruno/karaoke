import json,threading,time,urllib.error,urllib.parse,urllib.request
from email.utils import parsedate_to_datetime
from datetime import datetime,timezone

class LyricsProviderError(Exception):
    def __init__(self,message,retry_after=None):
        super().__init__(message);self.retry_after=retry_after

def retry_seconds(value):
    if not value:return 60
    try:return max(1,min(3600,int(value)))
    except ValueError:
        try:return max(1,min(3600,int((parsedate_to_datetime(value)-datetime.now(timezone.utc)).total_seconds())))
        except (ValueError,TypeError,OverflowError):return 60

class LrclibProvider:
    BASE='https://lrclib.net/api/'
    def __init__(self,identity,opener=None,clock=time.monotonic):
        if not identity or ('(' not in identity and '@' not in identity):
            raise ValueError('identifique cliente: nome/versao (contato ou URL)')
        self.identity=identity;self.opener=opener or urllib.request.urlopen
        self.clock=clock;self.lock=threading.Lock();self.next_at=0.0
    def _get(self,path,params=None):
        url=self.BASE+path
        if params:url+='?'+urllib.parse.urlencode(params)
        req=urllib.request.Request(url,headers={'User-Agent':self.identity,'Accept':'application/json'})
        with self.lock:
            now=self.clock()
            if now<self.next_at:
                raise LyricsProviderError('Aguarde antes de consultar novamente',int(self.next_at-now)+1)
            self.next_at=now+0.35
        try:
            with self.opener(req,timeout=10) as r:
                data=r.read(1_000_001)
                if len(data)>1_000_000:raise LyricsProviderError('Resposta da LRCLIB muito grande')
                return json.loads(data)
        except urllib.error.HTTPError as e:
            if e.code==429:
                wait=retry_seconds(e.headers.get('Retry-After'))
                with self.lock:self.next_at=max(self.next_at,self.clock()+wait)
                raise LyricsProviderError('Limite da LRCLIB; aguarde antes de repetir',wait)
            if e.code==404:return None
            raise LyricsProviderError(f'LRCLIB respondeu {e.code}')
        except (urllib.error.URLError,TimeoutError,OSError):
            raise LyricsProviderError('LRCLIB indisponível; internet necessária')
        except (ValueError,UnicodeError):
            raise LyricsProviderError('Resposta inválida da LRCLIB')
    def search(self,title,artist):
        result=self._get('search',{'track_name':title,'artist_name':artist})
        if not isinstance(result,list):raise LyricsProviderError('Resposta inesperada da LRCLIB')
        return sorted(result,key=lambda r:(not bool(r.get('syncedLyrics')),r.get('duration') or 0))[:20]
    def by_id(self,record_id):
        if not isinstance(record_id,int) or record_id<=0:raise ValueError('ID inválido')
        return self._get('get/'+str(record_id))
