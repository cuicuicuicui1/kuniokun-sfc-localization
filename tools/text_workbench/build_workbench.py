"""Create one portable, offline HTML from the actual optimized text build.

Reads generated text and native inventory; no ROM or private dependencies are
embedded. The output has no fetches, external assets, or absolute source paths.
"""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import re

HERE = Path(__file__).resolve().parent
TOKEN = re.compile(r"\{([0-9A-Fa-f]{2,4})\}")
GROUPS = {0x193B5: '剧情与战斗', 0x1DBC5: '道具', 0x1E098: '属性与技能',
          0x1E1D5: '地名', 0x1E4CE: '提示与片尾'}


def digest(s):
    return hashlib.sha256(s.encode('utf8')).hexdigest()


def live(s):
    """Discard unreachable prose after the first F3, keeping that terminator."""
    m = re.search(r'\{(?:F2)?F3\}', s)
    return s[:m.end()] if m else s


def load_catalog(build):
    build = Path(build)
    inv = json.loads((build/'inventory-worker/native-inventory.json').read_text(encoding='utf8'))
    main = json.loads((build/'native-dialogues.json').read_text(encoding='utf8'))
    tr = json.loads((build/'source/cn_translation.json').read_text(encoding='utf8'))
    names = json.loads((build/'source/name_hanzi.json').read_text(encoding='utf8'))
    entries = []

    def add(key, group, label, jp, cn, target, note=''):
        jp, cn = live(jp), live(cn)
        readable = TOKEN.sub('', jp).strip()
        entries.append(dict(key=key, group=group, label=label, original=jp,
                            translation=cn, source_hash=digest(jp), base_hash=digest(cn),
                            target=target, note=note, editable=bool(readable)))

    for table in inv['tables']:
        off = table['table_rom_off']
        for rec in table['records']:
            index = rec['index']
            message = rec.get('id')
            cn = (main[str(int(message, 16))]['text'] if off == 0x193B5
                  else tr['%06X' % int(rec['text_rom_off'], 16)])
            key = 'table:%06X:%04d' % (off, index)
            label = ('消息 ' + message[2:]) if message else ('条目 %03d' % (index+1))
            note = '优化版修改了原有内容' if rec.get('text_changed') else ''
            if message in ('0x186', '0x187', '0x189', '0x18A', '0x274'):
                note += ('；' if note else '') + '与下一条连续读取，请结合相邻条目校对'
            add(key, GROUPS[off], label, rec['text'], cn,
                dict(kind='table', table=off, index=index, message=message), note)
    for rec in inv['extended_table']['records']:
        if rec['null_slot']:
            continue
        mid = int(rec['id'], 16)
        add('message:%03X' % mid, '优化版新增', '消息 %03X' % mid,
            rec['text'], main[str(mid)]['text'], dict(kind='extended', message=mid),
            '前导结束标记，原游戏不会显示后面的文本' if mid == 0x348 else '优化版扩展表')
    assert len(entries) == 1088
    for index, (jp, cn) in enumerate(names.items()):
        add('name:'+jp, '人物名', '人物名 %03d' % (index+1), jp, cn,
            dict(kind='name', kana=jp), '共享姓名词条：同一读音的所有人物记录会一起采用此译名；最多两个字')
    assert len({e['key'] for e in entries}) == len(entries)
    seed = '\n'.join(e['key']+'|'+e['source_hash']+'|'+e['base_hash'] for e in entries)
    return dict(format='kunio-workbench-catalog-v1', title='初代热血硬派 · 汉化校对工作台',
                base_version='优化版 v2.0-rc2', date='2026-10-14',
                base_rom_crc32='1F37BC30', fingerprint=digest(seed), entries=entries,
                text_count=1088, name_count=len(names),
                categories=list(GROUPS.values())+['优化版新增', '人物名'])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--catalog', type=Path)
    p.add_argument('--base-version', help='ROM version label for this catalog')
    p.add_argument('--date', help='Catalog date, YYYY-MM-DD')
    p.add_argument('--base-rom-crc32', help='Eight hexadecimal digits')
    a = p.parse_args()
    data = load_catalog(a.build)
    if a.base_version:
        data['base_version'] = a.base_version
    if a.date:
        datetime.date.fromisoformat(a.date)
        data['date'] = a.date
    if a.base_rom_crc32:
        if not re.fullmatch('[0-9A-Fa-f]{8}', a.base_rom_crc32):
            p.error('--base-rom-crc32 requires eight hexadecimal digits')
        data['base_rom_crc32'] = a.base_rom_crc32.upper()
    raw = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    safe = raw.replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e')
    template = (HERE/'workbench.html').read_text(encoding='utf8')
    assert template.count('@@CATALOG@@') == 1
    html = template.replace('@@CATALOG@@', safe)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(html, encoding='utf8')
    if a.catalog:
        a.catalog.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps({'entries': len(data['entries']), 'text': data['text_count'],
                      'names': data['name_count'], 'fingerprint': data['fingerprint'],
                      'output': str(a.output)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
