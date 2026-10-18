"""Observe real node accounts without inferring state from requested changes."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.models import Device, ManagedUser, UserHostAssociation
from backend.routers.users import _user_to_response
from backend.services.account_state import reconcile_accounts

spec = importlib.util.spec_from_file_location('inspect_accounts', Path(__file__).parents[1] / 'playbooks/files/inspect_accounts.py')
inventory = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inventory)


def account(name, uid=1001, shell='/bin/bash'):
    return SimpleNamespace(pw_name=name, pw_uid=uid, pw_gid=100, pw_shell=shell,
                           pw_gecos=f'{name} Full Name,Room 1', pw_dir=f'/home/{name}')


def test_inventory_excludes_system_and_disabled_logins_but_keeps_directory_users():
    accounts = [account('root', 0), account('daemon', 1, '/usr/sbin/nologin'),
                account('disabled', 1001, '/bin/false'), account('_apt', 42), account('_rpc', 32),
                account('nobody', 65534), account('directory.user', 100000), account('alice')]
    accounts.append(account('service', 2000))
    accounts[-1].pw_dir = '/var/lib/service'
    with patch.object(inventory, 'minimum_user_uid', return_value=1000), \
         patch.object(inventory.pwd, 'getpwall', return_value=accounts), \
         patch.object(inventory.grp, 'getgrall', return_value=[SimpleNamespace(gr_name='users', gr_gid=100, gr_mem=[])]), \
         patch.object(inventory.pathlib.Path, 'is_file', return_value=False), \
         patch.object(inventory.subprocess, 'run', return_value=SimpleNamespace(stdout='policy', stderr='')) as sudo:
        rows = inventory.inspect_accounts([])
    assert {r['username'] for r in rows} == {'directory.user', 'alice'}
    assert sudo.call_count == 2
    assert all(r['present'] and r['groups'] == ['users'] for r in rows)
    directory = next(r for r in rows if r['username'] == 'directory.user')
    assert directory['uid'] == 100000 and directory['full_name'] == 'directory.user Full Name'
    assert directory['home'] == '/home/directory.user' and directory['sudo_policy'] == 'policy'


def test_inventory_is_not_truncated_at_the_bulk_edit_limit():
    accounts = [account(f'user{i}') for i in range(501)]
    with patch.object(inventory, 'minimum_user_uid', return_value=1000), \
         patch.object(inventory.pwd, 'getpwall', return_value=accounts), \
         patch.object(inventory.grp, 'getgrall', return_value=[]), \
         patch.object(inventory.pathlib.Path, 'is_file', return_value=False), \
         patch.object(inventory.subprocess, 'run', side_effect=OSError):
        rows = inventory.inspect_accounts([])
    assert len(rows) == 501
    assert all('unknown' in r['sudo_policy'] for r in rows)


def test_targeted_missing_account_is_explicitly_absent():
    with patch.object(inventory.pwd, 'getpwnam', side_effect=KeyError), \
         patch.object(inventory.grp, 'getgrall', return_value=[]):
        assert inventory.inspect_accounts(['gone']) == [dict(username='gone', present=False, groups=[], managed_sudo=False)]


@pytest.fixture
def database():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine, autoflush=False)() as db:
        db.add_all([Device(hostname='one'), Device(hostname='two')])
        db.commit()
        yield db
    engine.dispose()


def report(host='one', scope='all', names=('alice', 'bob'), **values):
    return dict(report_type='accounts', hostname=host, scope=scope,
                accounts=[dict(username=name, present=True, groups=['users'], **values) for name in names])


def test_full_inventory_marks_removed_accounts_absent_only_on_observed_node(database):
    db = database
    reconcile_accounts(db, [report(), report('two')], ['one', 'two'])
    reconcile_accounts(db, [report(names=('alice',), full_name='Alice on One', uid=1000, home='/srv/alice')], ['one', 'two'])
    bob = db.query(ManagedUser).filter_by(username='bob').one()
    placements = _user_to_response(db, bob)['placements']
    assert [p['state'] for p in placements] == ['absent', 'observed']
    alice = db.query(ManagedUser).filter_by(username='alice').one()
    placement = _user_to_response(db, alice)['placements'][0]
    assert placement['full_name'] == 'Alice on One' and placement['home'] == '/srv/alice' and placement['uid'] == 1000
    reconcile_accounts(db, [report(names=())], ['one'])
    assert all(p.state == 'absent' for p in db.query(UserHostAssociation).filter_by(host_id=1))


@pytest.mark.parametrize('scope', ['selected', None])
def test_targeted_and_legacy_reports_keep_unrelated_accounts(database, scope):
    db = database
    reconcile_accounts(db, [report()], ['one'])
    reconcile_accounts(db, [report(scope=scope, names=('alice',))], ['one'])
    assert all(p.state == 'observed' for p in db.query(UserHostAssociation))


def test_missing_malformed_or_out_of_scope_inventory_never_erases_accounts(database):
    db = database
    reconcile_accounts(db, [report()], ['one'])
    reconcile_accounts(db, [dict(report_type='accounts', hostname='one', scope='all'),
                            dict(report_type='accounts', hostname='one', scope='all', accounts=[{}]),
                            report('two', names=())], ['one'])
    assert all(p.state == 'observed' for p in db.query(UserHostAssociation))


@pytest.mark.parametrize('uid_min,expected', [(500, True), (1000, False)])
def test_person_filter_honors_local_uid_min(uid_min, expected):
    assert inventory.is_person_account(account('legacy', 501), uid_min) is expected


@pytest.mark.parametrize('home,shell', [('/home', '/bin/bash'), ('/home/../var/service', '/bin/bash'),
    ('/var/lib/app', '/bin/bash'), ('/home/alice', ''), ('/home/alice', '/sbin/nologin'), ('/home/alice', '/bin/false')])
def test_non_person_homes_and_shells_are_excluded(home, shell):
    record = account('alice', shell=shell)
    record.pw_dir = home
    assert not inventory.is_person_account(record, 1000)


def test_login_defs_minimum_uid_is_read_without_shadow_or_home_access():
    with patch.object(inventory.pathlib.Path, 'read_text', return_value='# comment\nUID_MIN 500 # legacy\n'):
        assert inventory.minimum_user_uid() == 500
    with patch.object(inventory.pathlib.Path, 'read_text', side_effect=OSError):
        assert inventory.minimum_user_uid() == 1000


def test_filtered_inventory_retires_old_system_observations_without_claiming_deletion(database):
    reconcile_accounts(database, [report(names=('alice', '_apt')), report('two', names=('_apt',))], ['one', 'two'])
    reconcile_accounts(database, [report(scope='people', names=('alice',))], ['one'])
    system = database.query(ManagedUser).filter_by(username='_apt').one()
    placements = _user_to_response(database, system)['placements']
    assert [p['state'] for p in placements] == ['not_in_scope', 'observed']
    reconcile_accounts(database, [report(scope='people', names=())], ['one'])
    assert all(p.state == 'not_in_scope' for p in database.query(UserHostAssociation).filter_by(host_id=1))
