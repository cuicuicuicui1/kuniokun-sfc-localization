"""Validate portable-workbench revisions without changing ROMs or build inputs."""
from pathlib import Path
import argparse
import hashlib
import json
import re

TOKEN = re.compile(r'\{([0-9A-Fa-f]{2,4})\}')
FORMAT = 'kunio-workbench-revisions-v1'


def strict_object(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError('JSON 重复字段：'+key)
        out[key] = value
    return out


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'), object_pairs_hook=strict_object)


def fingerprint(entries):
    seed = '\n'.join(e['key']+'|'+e['source_hash']+'|'+e['base_hash'] for e in entries)
    return hashlib.sha256(seed.encode('utf8')).hexdigest()


def validate(catalog, document):
    if catalog.get('format') != 'kunio-workbench-catalog-v1':
        raise ValueError('对照底稿格式不匹配')
    entries = catalog['entries']
    if catalog['fingerprint'] != fingerprint(entries):
        raise ValueError('对照底稿身份已改变')
    bykey = {e['key']: e for e in entries}
    if len(bykey) != len(entries):
        raise ValueError('对照底稿含重复条目')
    for e in entries:
        for field, source in [('source_hash', 'original'), ('base_hash', 'translation')]:
            if hashlib.sha256(e[source].encode('utf8')).hexdigest() != e[field]:
                raise ValueError('对照底稿文本校验失败：'+e['key'])
    if document.get('format') != FORMAT or document.get('catalog_fingerprint') != catalog['fingerprint']:
        raise ValueError('修订稿不是这份对照底稿的版本')
    revisions = document.get('revisions')
    if not isinstance(revisions, dict):
        raise ValueError('修订记录必须是对象')
    changes, reviewed = [], []
    for key, row in revisions.items():
        if key not in bykey or not isinstance(row, dict):
            raise ValueError('未知条目或记录格式错误：'+key)
        e = bykey[key]
        for field in ['source_hash', 'base_hash', 'original']:
            if row.get(field) != e[field]:
                raise ValueError('原文身份不一致：'+key)
        if row.get('base_translation') != e['translation'] or row.get('target') != e['target']:
            raise ValueError('基准译文或目标不一致：'+key)
        text = row.get('translation')
        if not isinstance(text, str) or len(text) > 5000:
            raise ValueError('修订文字格式或长度错误：'+key)
        if not e['editable'] and text != e['translation']:
            raise ValueError('空内容／结束边界不可修改：'+key)
        if e['target']['kind'] == 'name':
            if not 1 <= len(text) <= 2 or re.search(r'[\s{}]', text):
                raise ValueError('人物名需一至两个字：'+key)
        else:
            if TOKEN.findall(text) != TOKEN.findall(e['translation']):
                raise ValueError('游戏控制标记发生变化：'+key)
            if re.search(r'[{}\r\n]', TOKEN.sub('', text)):
                raise ValueError('含非法花括号或换行：'+key)
        if re.search(r'[\x00-\x08\x0B-\x1F\x7F]', text):
            raise ValueError('含不可显示控制字符：'+key)
        if row.get('status') not in ['unreviewed', 'reviewed', 'flagged']:
            raise ValueError('校对状态错误：'+key)
        if not isinstance(row.get('note'), str) or len(row['note']) > 2000:
            raise ValueError('备注格式错误：'+key)
        reviewed.append(dict(key=key, status=row['status'], note=row['note']))
        if text != e['translation']:
            changes.append(dict(key=key, target=e['target'], original=e['original'],
                                before=e['translation'], after=text,
                                source_hash=e['source_hash'], base_hash=e['base_hash'],
                                status=row['status'], note=row['note']))
    return dict(format='kunio-workbench-proposed-changes-v1', status='validated',
                catalog_fingerprint=catalog['fingerprint'], base_version=catalog['base_version'],
                changed_count=len(changes), record_count=len(reviewed),
                changes=changes, review_records=reviewed,
                scope='文字修订提案；未改变译文构建输入或 ROM，仍须维护者合入和验证')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('revisions', type=Path)
    p.add_argument('--catalog', type=Path, required=True)
    p.add_argument('--output', type=Path)
    a = p.parse_args()
    try:
        result = validate(load(a.catalog), load(a.revisions))
        if a.output:
            a.output.parent.mkdir(parents=True, exist_ok=True)
            with a.output.open('x', encoding='utf8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
        print('校验通过：%d 条校对记录，%d 条译文修订。未修改 ROM。' %
              (result['record_count'], result['changed_count']))
    except (KeyError, TypeError, ValueError, OSError) as error:
        p.exit(1, '校验失败：'+str(error)+'\n')


if __name__ == '__main__':
    main()
