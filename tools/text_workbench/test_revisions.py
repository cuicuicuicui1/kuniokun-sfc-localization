"""Independent revision-file identity/control checks, including rejection cases."""
from pathlib import Path
import copy
import json
import sys

from check_revisions import validate, strict_object


def main():
    catalog = json.loads(Path(sys.argv[1]).read_text(encoding='utf8'))
    exported = json.loads(Path(sys.argv[2]).read_text(encoding='utf8'))
    good = validate(catalog, exported)
    assert good['changed_count'] == 1
    assert good['changes'][0]['target'] == {'kind': 'extended', 'message': 0x302}
    assert '究竟' in good['changes'][0]['after']
    key = next(iter(exported['revisions']))
    failures = []
    def rejects(name, mutate):
        document = copy.deepcopy(exported)
        mutate(document)
        try:
            validate(catalog, document)
        except (KeyError, TypeError, ValueError):
            failures.append(name)
        else:
            raise AssertionError('invalid case accepted: '+name)
    rejects('wrong catalog', lambda d: d.update(catalog_fingerprint='wrong'))
    rejects('unknown entry', lambda d: d['revisions'].update(unknown=d['revisions'][key]))
    rejects('source identity', lambda d: d['revisions'][key].update(source_hash='wrong'))
    rejects('baseline prose', lambda d: d['revisions'][key].update(base_translation='wrong'))
    rejects('target identity', lambda d: d['revisions'][key].update(target={'kind':'extended','message':9999}))
    rejects('removed macro', lambda d: d['revisions'][key].update(translation=d['revisions'][key]['translation'].replace('{E2}', '')))
    rejects('added control', lambda d: d['revisions'][key].update(translation=d['revisions'][key]['translation']+'{F2F6}'))
    rejects('unsupported newlines', lambda d: d['revisions'][key].update(translation=d['revisions'][key]['translation']+'\n'))
    rejects('bad status', lambda d: d['revisions'][key].update(status='unknown'))
    rejects('bad note', lambda d: d['revisions'][key].update(note=7))
    entry = next(e for e in catalog['entries'] if e['target']['kind']=='name')
    document = copy.deepcopy(exported)
    document['revisions'][entry['key']] = dict(source_hash=entry['source_hash'],base_hash=entry['base_hash'],
        original=entry['original'],base_translation=entry['translation'],translation='国夫君',
        target=entry['target'],status='reviewed',note='')
    try:
        validate(catalog,document)
    except ValueError:
        failures.append('name too wide')
    else:
        raise AssertionError('three-character name accepted')
    try:
        json.loads('{"a":1,"a":2}',object_pairs_hook=strict_object)
    except ValueError:
        failures.append('duplicate JSON keys')
    else:
        raise AssertionError('duplicate key accepted')
    empty = dict(format=exported['format'],catalog_fingerprint=catalog['fingerprint'],revisions={})
    assert validate(catalog,empty)['changed_count']==0
    result={'status':'pass','UI_handler_export_validated':True,'exact_change_count':1,
            'reject_cases':failures,'baseline_rows':len(catalog['entries']),
            'empty_export_accepted':True,'ROM_and_build_inputs_modified':False}
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
