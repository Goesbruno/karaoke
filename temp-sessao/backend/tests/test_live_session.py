import pytest
from karaoke.application.live_session import LiveSession,SessionError
from karaoke.infrastructure.sqlite_store import SqliteStore

def test_version_order_clock_and_restart(tmp_path):
    now=[100_000];db=SqliteStore(tmp_path/'data.db');song=db.create_song('T','A',None);x=LiveSession(db,lambda:now[0])
    x.state.song_id=song.id;x.host(True)
    x.command('host','ready')
    assert x.command('guest','play')['playing']
    now[0]+=1120
    assert x.snapshot()['position_ms']==0  # ponto base; visual soma intervalo
    assert x.state.position(now[0])==1000
    a=x.command('guest','pause');assert a['position_ms']==1000
    b=x.command('guest','seek',3000);assert b['version']>a['version']
    assert x.state.position(now[0])==3000
    y=LiveSession(SqliteStore(tmp_path/'data.db'),lambda:now[0])
    assert y.snapshot()['position_ms']==3000 and not y.snapshot()['playing'] and not y.snapshot()['host_online']

def test_role_validation_and_host_disconnect(tmp_path):
    x=LiveSession(SqliteStore(tmp_path/'db'),lambda:1000)
    with pytest.raises(SessionError):x.command('guest','background','x')
    with pytest.raises(SessionError):x.command('guest','offset',200)
    with pytest.raises(SessionError):x.command('guest','play')
    x.state.song_id='s';x.host(True);x.command('host','ready');x.command('guest','volume',{'stem':'vocals','level':.4})
    assert x.snapshot()['vocals']==.4
    x.command('guest','play');assert not x.host(False)['playing']
    with pytest.raises(SessionError):x.command('guest','play')

def test_rejects_invalid_volume_image_and_seek(tmp_path):
    x=LiveSession(SqliteStore(tmp_path/'db'),lambda:1000);x.state.song_id='s';x.host(True);x.command('host','ready')
    for cmd,val in [('volume',{'stem':'vocals','level':2}),('volume',{'stem':'backing','level':.5}),('seek',-1)]:
        with pytest.raises(SessionError):x.command('guest',cmd,val)
    with pytest.raises(SessionError):x.command('host','background','data:image/png;base64,QQ==')
