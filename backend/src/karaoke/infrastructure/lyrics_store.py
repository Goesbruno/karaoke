import json

MIGRATION="""
CREATE TABLE IF NOT EXISTS song_lyrics (
 song_id TEXT PRIMARY KEY REFERENCES songs(id) ON DELETE CASCADE,
 status TEXT NOT NULL, content TEXT NOT NULL, source TEXT NOT NULL,
 external_id TEXT, lines_json TEXT NOT NULL, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

def install(store):
    with store._tx() as c:
        c.execute('CREATE TABLE IF NOT EXISTS song_lyrics (song_id TEXT PRIMARY KEY REFERENCES songs(id) ON DELETE CASCADE, status TEXT NOT NULL, content TEXT NOT NULL, source TEXT NOT NULL, external_id TEXT, lines_json TEXT NOT NULL, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)')

def save(store,song_id,status,content,source,external_id,lines):
    with store._tx() as c:
        c.execute('INSERT INTO song_lyrics(song_id,status,content,source,external_id,lines_json) VALUES(?,?,?,?,?,?) ON CONFLICT(song_id) DO UPDATE SET status=excluded.status,content=excluded.content,source=excluded.source,external_id=excluded.external_id,lines_json=excluded.lines_json,updated_at=CURRENT_TIMESTAMP',
                  (song_id,status,content,source,external_id,json.dumps(lines,ensure_ascii=False)))

def get(store,song_id):
    store.get_song(song_id)
    with store.lock:r=store.db.execute('SELECT * FROM song_lyrics WHERE song_id=?',(song_id,)).fetchone()
    if not r:return {'status':'SEM_LETRA','content':'','source':None,'external_id':None,'lines':[]}
    return {'status':r['status'],'content':r['content'],'source':r['source'],'external_id':r['external_id'],'lines':json.loads(r['lines_json'])}

class LyricsRepository:
    def __init__(self,store):self.store=store;install(store)
    def get_song(self,id):return self.store.get_song(id)
    def save_lyrics(self,*args):return save(self.store,*args)
    def get_lyrics(self,id):return get(self.store,id)
