import re
from dataclasses import dataclass

STAMP = re.compile(r'^\[(\d{1,3}):(\d{2})(?:\.(\d{1,3}))?\]')
META = re.compile(r'^\[[A-Za-z][A-Za-z0-9_-]*:.*\]$')

class InvalidLRC(ValueError): pass

@dataclass(frozen=True)
class Line:
    ms: int
    text: str

def parse_lrc(content: str) -> list[Line]:
    if not isinstance(content,str) or len(content.encode('utf-8')) > 256_000:
        raise InvalidLRC('LRC vazio ou maior que 256 KB')
    lines=[]
    for row in content.replace('\r\n','\n').split('\n'):
        row=row.strip().lstrip('\ufeff')
        if not row or META.fullmatch(row): continue
        stamps=[]
        while (m:=STAMP.match(row)):
            mins,secs,frac=m.groups()
            if int(secs)>=60: raise InvalidLRC('segundos fora do intervalo')
            ms=int(frac.ljust(3,'0')[:3]) if frac else 0
            stamps.append((int(mins)*60+int(secs))*1000+ms)
            row=row[m.end():]
        if not stamps: raise InvalidLRC('linha sem timestamp: '+row[:40])
        for ms in stamps: lines.append(Line(ms,row.strip()))
    if not lines: raise InvalidLRC('nenhum timestamp encontrado')
    return sorted(lines,key=lambda x:x.ms)

def at_time(lines: list[Line], current_ms: int, offset_ms: int=0) -> int:
    from bisect import bisect_right
    return bisect_right([x.ms for x in lines],current_ms+offset_ms)-1
