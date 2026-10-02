import json
import pytest
from karaoke.application.search import SearchService
from karaoke.domain.errors import InvalidUrl, NotFound, ProviderUnavailable
from karaoke.domain.youtube import parse_iso_duration, parse_youtube_url
from karaoke.infrastructure.youtube_api import YouTubeDataApi

VID = "dQw4w9WgXcQ"

@pytest.mark.parametrize("url", [
    f"https://www.youtube.com/watch?v={VID}", f"http://youtube.com/watch?v={VID}&t=10",
    f"https://m.youtube.com/watch?v={VID}", f"https://music.youtube.com/watch?v={VID}",
    f"https://youtu.be/{VID}", f"https://youtu.be/{VID}?si=abc", f"https://www.youtube.com/shorts/{VID}",
    f"https://www.youtube.com/embed/{VID}", f"https://www.youtube.com/live/{VID}", f"www.youtube.com/watch?v={VID}",
])
def test_valid_urls(url): assert parse_youtube_url(url) == VID

@pytest.mark.parametrize("url", [
    f"https://youtube.com.evil.com/watch?v={VID}", f"https://evil.com/watch?v={VID}",
    f"https://user:pw@www.youtube.com/watch?v={VID}", f"https://www.youtube.com:8080/watch?v={VID}",
    f"javascript:alert(1)//youtube.com/watch?v={VID}", f"ftp://www.youtube.com/watch?v={VID}",
    "https://www.youtube.com/watch?v=curto", "https://www.youtube.com/watch", "https://youtu.be/",
    f"https://www.youtube.com/playlist?list={VID}", f"https://notyoutube.com/watch?v={VID}",
    "http://127.0.0.1/watch?v=" + VID, f"https://www.youtube.com/watch?v={VID}x",
])
def test_invalid_urls(url):
    with pytest.raises(InvalidUrl): parse_youtube_url(url)

@pytest.mark.parametrize("s,v", [("PT3M25S", 205), ("PT1H", 3600), ("PT1H2M3S", 3723), ("P1DT1S", 86401), ("PT45S", 45),
                                 ("P0D", None), ("", None), (None, None), ("lixo", None)])
def test_iso_duration(s, v): assert parse_iso_duration(s) == v

def vids(ids):
    return {"items": [{"id": i, "snippet": {"title": f"T{i}", "channelTitle": "Canal",
            "thumbnails": {"medium": {"url": f"https://i/{i}.jpg"}}},
            "contentDetails": {"duration": "PT3M"}, "status": {"embeddable": i != "b" * 11}} for i in ids]}

def fake(calls, status=200, body=None):
    def get(url, timeout):
        calls.append(url)
        if status != 200: return status, json.dumps(body or {})
        if "/search?" in url: return 200, json.dumps({"items": [{"id": {"videoId": i}} for i in ("a" * 11, "b" * 11)]})
        ids = url.split("id=")[1].split("&")[0].replace("%2C", ",").split(",")
        return 200, json.dumps(vids(ids))
    return get

def test_text_search_maps_and_orders():
    calls = []; r = YouTubeDataApi("K", fake(calls)).search("queen")
    assert [i["video_id"] for i in r] == ["a" * 11, "b" * 11]
    assert r[0]["channel"] == "Canal" and r[0]["duration_s"] == 180 and r[1]["embeddable"] is False
    assert "maxResults=5" in calls[0] and "www.googleapis.com" in calls[0] and "key=K" in calls[0]

def test_quota_and_generic_errors():
    q = {"error": {"errors": [{"reason": "quotaExceeded"}]}}
    with pytest.raises(ProviderUnavailable) as e: YouTubeDataApi("K", fake([], 403, q)).search("x")
    assert e.value.code == "youtube_cota"
    with pytest.raises(ProviderUnavailable) as e: YouTubeDataApi("K", fake([], 400, {})).search("x")
    assert e.value.code == "youtube_erro"

def test_offline():
    def get(url, timeout): raise OSError("sem rede")
    with pytest.raises(ProviderUnavailable) as e: YouTubeDataApi("K", get).search("x")
    assert e.value.code == "sem_internet"

class Prov:
    def __init__(self): self.calls = []
    def search(self, q): self.calls.append(("search", q)); return [{"video_id": "x"}]
    def details(self, ids): self.calls.append(("details", ids)); return [{"video_id": ids[0]}] if ids[0] != "z" * 11 else []

def test_url_mode_never_text_searches():
    p = Prov(); r = SearchService(p).run(f"https://youtu.be/{VID}")
    assert r["mode"] == "url" and p.calls == [("details", [VID])] and r["attribution"] == "YouTube"

def test_text_mode_and_validation():
    p = Prov(); assert SearchService(p).run("  queen  ")["mode"] == "text" and p.calls == [("search", "queen")]
    for bad in ("", "  ", "x" * 201):
        with pytest.raises(ValueError): SearchService(p).run(bad)

def test_bad_url_and_missing_video_and_no_key():
    with pytest.raises(InvalidUrl): SearchService(Prov()).run("https://evil.com/watch?v=" + VID)
    with pytest.raises(NotFound): SearchService(Prov()).run(f"https://youtu.be/{'z' * 11}")
    with pytest.raises(ProviderUnavailable) as e: SearchService(None).run("queen")
    assert e.value.code == "youtube_nao_configurado"
