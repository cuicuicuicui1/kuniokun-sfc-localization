"""gen_proof.py - bilingual proofreading sheets for the final build.

Writes into the delivery dir:
  校对文档.csv        all 1013 texts: table, index, rom offset, original, translation, flags
  校对摘要.md         stats + only the flagged entries, for quick human review
Flag kinds: JP-KEPT (110 item names kept Japanese), CODES (control-code count
differs from the original), LONG/SHORT (translation length ratio vs original
out of 0.4..1.6), EMPTY (no translation in cn_translation.json).
"""
import csv
import json
import re
import os

BASE = r'F:\BaiduNetdiskDownload\SFC deepseek\初代热血硬派-汉化'
TABLE_NAMES = {
    0x0193B5: '表1 主文本(对话/战斗讯息)',
    0x01DBC5: '表2 道具名(按设计保留日文)',
    0x01E098: '表3',
    0x01E1D5: '表4',
    0x01E4CE: '表5',
}
SEP = re.compile(r'\{F[0-9A-F]{1,3}\}')
CODE = re.compile(r'\{[0-9A-F]{1,4}\}')


def visible_len(s):
    return len(CODE.sub('', SEP.sub('', s)).replace(' ', ''))


def main():
    texts = json.load(open('kuniokun_text.json', encoding='utf-8'))
    trans = json.load(open('cn_translation.json', encoding='utf-8'))
    texts.sort(key=lambda r: (r['table_rom_off'], r['index']))

    rows = []
    for r in texts:
        toff = r['table_rom_off']
        key = '%06X' % r['text_rom_off']
        orig = r['text']
        if toff == 0x01DBC5:
            tr, flags = orig, ['JP-KEPT']
        else:
            tr = trans.get(key, '')
            flags = []
            if not tr:
                flags.append('EMPTY')
            else:
                oc = sorted(c for c in CODE.findall(orig) if not SEP.fullmatch(c))
                tc = sorted(c for c in CODE.findall(tr) if not SEP.fullmatch(c))
                if oc != tc:
                    flags.append('CODES:%s/%s' % (len(oc), len(tc)))
                lo, lt = visible_len(orig), visible_len(tr)
                if lo:
                    ratio = lt / lo
                    if ratio > 1.6:
                        flags.append('LONG:%.2f' % ratio)
                    elif ratio < 0.4:
                        flags.append('SHORT:%.2f' % ratio)
        rows.append((TABLE_NAMES[toff], r['index'], key, orig, tr, ';'.join(flags)))

    with open(os.path.join(BASE, '校对文档.csv'), 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['表', '序号', 'ROM偏移', '原文', '译文', '标记'])
        w.writerows(rows)

    by_table = {}
    for t, i, k, o, tr, fl in rows:
        by_table.setdefault(t, [0, 0])
        by_table[t][0] += 1
        if fl:
            by_table[t][1] += 1
        elif t != TABLE_NAMES[0x01DBC5]:
            by_table[t][1] += 0

    lines = ['# 全量文本校对摘要（最终版 BB13930A）', '',
             '全量逐条见同目录 `校对文档.csv`（UTF-8 BOM，Excel 可直接打开）。', '',
             '| 表 | 条数 | 有标记 |', '|---|---|---|']
    for t, (n, nf) in by_table.items():
        lines.append('| %s | %d | %d |' % (t, n, nf))
    flagged = [r for r in rows if r[5] and r[5] != 'JP-KEPT' and not r[5].startswith('SHORT')]
    shorts = [r for r in rows if r[5].startswith('SHORT')]
    lines += ['', '## 需人工过目的条目（%d 条）' % len(flagged), '',
              '控制码是运行期占位符（人名槽/数值/换页等），缺码或换码可能导致运行时插错名字或数值。', '']
    if not flagged:
        lines.append('（无。）')
    for t, i, k, o, tr, fl in flagged:
        oc = [c for c in CODE.findall(o) if not SEP.fullmatch(c)]
        tc = [c for c in CODE.findall(tr) if not SEP.fullmatch(c)]
        miss = [c for c in oc if c not in tc]
        extra = [c for c in tc if c not in oc]
        note = ''
        if miss or extra:
            note = '（缺失 %s，多出 %s）' % (miss or '无', extra or '无')
        lines += ['- **%s #%d** `%s` 标记=%s %s' % (t, i, k, fl, note),
                  '  - 原：`%s`' % o,
                  '  - 译：`%s`' % tr]
    lines += ['', '## 偏短条目（%d 条，标记 SHORT）' % len(shorts), '',
              '中文比日文假名天然紧凑，短不等于漏译；只列出来供抽查语气是否过省。详见 CSV。', '']
    for t, i, k, o, tr, fl in shorts:
        lines.append('- %s #%d `%s`：`%s` ⇒ `%s`（%s）' % (t, i, k, o, tr, fl))
    kept = [r for r in rows if r[5] == 'JP-KEPT']
    lines += ['', '## 保留日文的道具名（%d 条）' % len(kept), '']
    lines.append('、'.join(r[4] for r in kept))
    out = os.path.join(BASE, '校对摘要.md')
    open(out, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    print('csv rows:', len(rows), 'flagged:', len(flagged), 'kept:', len(kept))
    print(out)


if __name__ == '__main__':
    main()
