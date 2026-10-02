import pytest
from karaoke.domain.errors import InvalidTransition, RetryLimit
from karaoke.domain.states import State
from karaoke.infrastructure.sqlite_store import SqliteStore
from karaoke.interfaces.worker import run_once

class OK:
    def run(self, job, advance):
        advance(State.SEPARANDO_INSTRUMENTAL_VOCAIS); advance(State.ANALISANDO)
class Boom:
    def run(self, job, advance): raise RuntimeError("cuda oom")

def mk(store, n=1):
    ids = []
    for i in range(n):
        s = store.create_song(f"m{i}", "a", None)
        ids.append(store.enqueue(s.id, 2).id)
    return ids

def test_full_flow():
    st = SqliteStore(":memory:"); (j,) = mk(st)
    assert run_once(st, OK())
    assert st.get_job(j).state == State.CONCLUIDA
    assert st.get_song(st.get_job(j).song_id).status == State.CONCLUIDA

def test_positions_fifo():
    st = SqliteStore(":memory:"); a, b, c = mk(st, 3)
    assert [st.position(x) for x in (a, b, c)] == [1, 2, 3]
    st.claim_next()
    assert st.position(b) == 1

def test_invalid_transition():
    st = SqliteStore(":memory:"); (j,) = mk(st)
    with pytest.raises(InvalidTransition): st.advance(j, State.CONCLUIDA)

def test_failure_and_retry_limit():
    st = SqliteStore(":memory:"); (j,) = mk(st)
    run_once(st, Boom()); assert st.get_job(j).state == State.FALHA
    st.retry(j); run_once(st, Boom())
    with pytest.raises(RetryLimit): st.retry(j)

def test_recover_after_restart(tmp_path):
    p = tmp_path / "k.db"
    st = SqliteStore(p); (j,) = mk(st); st.claim_next(); st.advance(j, State.SEPARANDO_INSTRUMENTAL_VOCAIS)
    st2 = SqliteStore(p); r = st2.recover()
    assert r[0].state == State.NA_FILA and st2.get_job(j).state != State.CONCLUIDA
    assert st2.get_song(r[0].song_id).status == State.NA_FILA

def test_recover_exhausted_attempts(tmp_path):
    st = SqliteStore(tmp_path / "k.db"); (j,) = mk(st)
    st.claim_next(); st.fail(j, "x"); st.retry(j); st.claim_next()
    assert st.recover()[0].state == State.FALHA

def test_cancel():
    st = SqliteStore(":memory:"); (j,) = mk(st)
    st.cancel(j); assert st.claim_next() is None
