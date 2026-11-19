"""Check the refresh workflow's checkout and write behavior for each event."""
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
EVENTS = {'pull_request': False, 'push': True, 'schedule': True,
          'workflow_dispatch': True}


def event_allowed(condition, event):
    match = re.fullmatch(r"github\.event_name\s*(!=|==)\s*(['\"])(\w+)\2", condition)
    assert match, f'Write condition needs an explicit event comparison: {condition}'
    operator, _, expected = match.groups()
    return (event != expected) if operator == '!=' else (event == expected)


def main():
    workflow = (ROOT / '.github/workflows/refresh.yml').read_text(encoding='utf-8')
    steps = re.split(r'^      - ', workflow, flags=re.MULTILINE)[1:]
    checkout = next(step for step in steps if 'uses: actions/checkout@' in step)
    assert not re.search(r'^\s+ref:', checkout, re.MULTILINE), (
        'Use the default event checkout so fork pull requests use their merge ref.')
    writers = [step for step in steps if re.search(r'\bgit (push|commit)\b', step)]
    assert writers, 'The scheduled refresh must retain its commit step.'
    for step in writers:
        condition = re.search(r'^\s+if:\s*(.+)$', step, re.MULTILINE)
        assert condition, 'A git write step has no event guard.'
        for event, expected in EVENTS.items():
            assert event_allowed(condition[1], event) == expected, (
                f'Incorrect git write behavior for {event}.')
    assert re.search(r'^  pull_request:', workflow, re.MULTILINE), 'PR validation was removed.'
    assert re.search(r'^  schedule:', workflow, re.MULTILINE), 'Daily refresh was removed.'
    assert 'python3 scripts/build.py' in workflow, 'The profile generator is not exercised.'
    print('refresh workflow: fork PR checkout and four-event write contract passed')


if __name__ == '__main__':
    main()
