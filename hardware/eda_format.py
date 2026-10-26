"""Small lossless reader for official EasyEDA Pro V3 records.

Uses JSON boundaries, not splitlines: library text can contain Unicode line
separators. This module does not implement or guess electrical rules.
"""
import json

def parse_records(text):
    dec=json.JSONDecoder(); pos=0
    while pos<len(text):
        while pos<len(text) and (text[pos].isspace() or text[pos]=='|'): pos+=1
        if pos==len(text): break
        head,pos=dec.raw_decode(text,pos)
        while pos<len(text) and text[pos].isspace(): pos+=1
        if text[pos:pos+2]!='||': raise ValueError(f'Missing record separator at {pos}')
        pos+=2
        body,pos=dec.raw_decode(text,pos)
        yield head,body

def serialize(records):
    return ''.join(json.dumps(h,separators=(',',':'))+'||'+json.dumps(b,ensure_ascii=False,separators=(',',':'))+'|\n' for h,b in records)
