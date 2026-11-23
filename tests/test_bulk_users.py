import asyncio
from unittest.mock import AsyncMock, patch

import pytest
import httpx
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.auth import get_current_user
from backend.database import Base, get_db
from backend.main import app
from backend.models import Device, ManagedUser
from backend.schemas import BulkUserAdd, BulkUserUpdate, UserInfo
from backend.services.csv_parser import CsvValidationError, parse_csv
from backend.services.ansible_runner import _apply_completion_action


def test_csv_add_bom_reordered_columns_quoted_commas_and_legacy():
    records = parse_csv('\ufeffemail,full_name,username,groups,shell\r\njane@example.com,"Doe, Jane",jane,"dev,docker",/bin/bash\r\n')
    assert records[0].username == 'jane'
    assert records[0].full_name == 'Doe, Jane'
    assert records[0].groups == 'dev,docker'
    assert parse_csv('Jane Doe,jane@example.com\n')[0].username == 'jane'
    assert parse_csv('username,full_name\nalice,Alice\n')[0].email is None


def test_csv_edit_maps_fields_by_header_and_keeps_blanks_unchanged():
    records = parse_csv('shell,username,groups,full_name\n/bin/zsh,jane,"dev, docker",\n', 'edit')
    assert records[0].model_dump(exclude_none=True) == dict(username='jane', groups='dev,docker', shell='/bin/zsh')


@pytest.mark.parametrize('content,mode,error', [
    ('username,full_name\njane,Jane\njane,Other\n','add','Row 3: duplicate'),
    ('full_name,email\nJane,jane@example.com\nBad,no-email\n','add','Row 3'),
    ('username,groups\njane,\n','edit','at least one update'),
    ('username,groups\njane,"unclosed\n','edit','malformed CSV'),
    ('username,groups\njane,dev,docker\n','edit','expected 2 columns'),
    ('username,password\njane,secret\n','edit','Unknown CSV columns'),
    ('username,username\njane,jane\n','edit','duplicate column'),
    ('username,shell\njane,/tmp/arbitrary\n','edit','allowed shell'),
    ('full_name,email\n','add','no users'),
    ('username,full_name\n../escape,Example\n','add','safe Linux'),
    ('jane,dev\n','edit','requires a header'),
    ('username,full_name\n'+'alice,Alice\n'*501,'add','at most 500'),
])
def test_csv_rejects_entire_invalid_file(content,mode,error):
    with pytest.raises(CsvValidationError,match=error):
        parse_csv(content,mode)


def test_manual_records_reject_duplicates_and_ambiguous_edit_formats():
    with pytest.raises(ValidationError,match='only once'):
        BulkUserAdd(users=[dict(full_name='Jane',email='jane@example.com'),dict(username='jane',full_name='Other')],device_ids=[1])
    with pytest.raises(ValidationError,match='either per-user'):
        BulkUserUpdate(users=[dict(username='jane',shell='/bin/sh')],usernames=['jane'],device_ids=[1])
    with pytest.raises(ValidationError,match='at least one update'):
        BulkUserUpdate(usernames=['jane'],device_ids=[1])
    assert BulkUserUpdate(usernames=['jane'],groups='dev, docker',device_ids=[1]).updates[0].groups == 'dev,docker'
    assert UserInfo(username='jane',full_name='Jane',email='jane.doe@example.com').username == 'jane'


@pytest.fixture
def api():
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions=sessionmaker(bind=engine)
    with sessions() as db:
        db.add_all([Device(hostname='one',transport='ssh',os_family='Debian',facts_stale=True,recovery_required=True),Device(hostname='two',transport='ssh'),Device(hostname='robot',transport='reachy_daemon')]);db.commit()
    def database():
        with sessions() as db:
            yield db
    app.dependency_overrides[get_db]=database
    app.dependency_overrides[get_current_user]=lambda:'tester'
    with patch('backend.routers.users.run_playbook',AsyncMock(return_value='test-job')) as runner:
        class Client:
            def request(self, method, url, **kwargs):
                async def execute():
                    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
                        return await client.request(method,url,**kwargs)
                return asyncio.run(execute())
            def post(self,url,**kwargs): return self.request('POST',url,**kwargs)
            def put(self,url,**kwargs): return self.request('PUT',url,**kwargs)
        yield Client(),runner,sessions
    app.dependency_overrides.clear();engine.dispose()


def test_upload_preview_has_no_remote_side_effects_then_explicit_bulk_add(api):
    client,runner,_=api
    response=client.post('/api/v2/users/csv-preview',files={'file':('users.csv',b'username,full_name\njane,Jane\n')},data={'mode':'add'})
    assert response.status_code==200,response.text
    runner.assert_not_awaited()
    response=client.post('/api/v2/users/bulk-add',json={'device_ids':[1,2],'users':response.json()['users'],'request_key':'bulk-add-request-123'})
    assert response.status_code==200,response.text
    assert runner.call_args.kwargs['hosts']==['one','two']
    assert not runner.call_args.kwargs['all_hosts']
    assert runner.call_args.kwargs['extra_vars']['user_records']==[dict(username='jane',full_name='Jane')]
    assert runner.call_args.kwargs['request_key']=='bulk-add-request-123'


def test_csv_edits_use_same_bulk_request_as_manual_rows(api):
    client,runner,_=api
    preview=client.post('/api/v2/users/csv-preview',files={'file':('edit.csv',b'username,groups,shell\njane,"dev,docker",/bin/bash\n')},data={'mode':'edit'})
    response=client.put('/api/v2/users/bulk-update',json={'users':preview.json()['users'],'device_ids':[1]})
    assert response.status_code==200,response.text
    assert runner.call_args.kwargs['extra_vars']['user_updates']==[dict(username='jane',groups='dev,docker',shell='/bin/bash')]
    assert runner.call_args.kwargs['hosts']==['one']


@pytest.mark.parametrize('file,status',[(b'username,groups\njane,\n',400),(b'\xff\xfe',400),(b'a'*1048577,413)])
def test_bad_upload_never_queues_work(api,file,status):
    client,runner,_=api
    response=client.post('/api/v2/users/csv-preview',files={'file':('users.csv',file)},data={'mode':'edit'})
    assert response.status_code==status,response.text
    runner.assert_not_awaited()


@pytest.mark.parametrize('scope',[{}, {'all_devices':True}, {'device_ids':[1,999]}, {'device_ids':[1,3]}])
def test_scope_errors_never_silently_drop_devices(api,scope):
    client,runner,_=api
    response=client.post('/api/v2/users/bulk-add',json={**scope,'users':[{'username':'jane','full_name':'Jane'}]})
    assert response.status_code in {400,404,422},response.text
    runner.assert_not_awaited()


def test_account_routes_require_authentication(api):
    client,runner,_=api
    app.dependency_overrides.pop(get_current_user)
    response=client.post('/api/v2/users/csv-preview',files={'file':('users.csv',b'username,full_name\njane,Jane\n')})
    assert response.status_code in {401,403}
    runner.assert_not_awaited()


def test_edit_metadata_updates_only_after_remote_completion(api):
    client,runner,sessions=api
    response=client.put('/api/v2/users/bulk-update',json={'device_ids':[1], 'users':[{'username':'jane','full_name':'Jane Changed','email':'jane@example.com'}]})
    assert response.status_code==200
    with sessions() as db: assert db.query(ManagedUser).count()==0
    with patch('backend.services.ansible_runner.SessionLocal',sessions):
        _apply_completion_action(runner.call_args.kwargs['completion_action'])
    with sessions() as db:
        account=db.query(ManagedUser).one()
        assert account.full_name=='Jane Changed'
        assert account.email=='jane@example.com'


def test_sudo_csv_import_and_api_preserve_explicit_per_user_grants(api):
    client,runner,_=api
    preview=client.post('/api/v2/users/csv-preview',files={'file':('users.csv',b'username,full_name,grant_sudo\nsam,Sam,true\nalice,Alice,false\nbob,Bob,\n')},data={'mode':'add'})
    assert preview.status_code==200,preview.text
    records=preview.json()['users']
    assert records[0]['grant_sudo'] is True
    assert records[1]['grant_sudo'] is False
    assert 'grant_sudo' not in records[2]
    response=client.post('/api/v2/users/bulk-add',json={'device_ids':[1], 'users':records})
    assert response.status_code==200,response.text
    assert runner.call_args.kwargs['extra_vars']['user_records']==records
    response=client.put('/api/v2/users/bulk-update',json={'device_ids':[1], 'users':[{'username':'jane','grant_sudo':True}]})
    assert response.status_code==200,response.text
    assert runner.call_args.kwargs['extra_vars']['user_updates']==[{'username':'jane','grant_sudo':True}]


@pytest.mark.parametrize('value',['true','false','yes',1])
def test_json_sudo_grant_requires_a_boolean(value):
    with pytest.raises(ValidationError):
        UserInfo(username='sam',full_name='Sam',grant_sudo=value)


def test_sudo_edit_validation_rejects_ambiguous_or_empty_requests():
    with pytest.raises(ValidationError,match='at least one update'):
        BulkUserUpdate(users=[dict(username='jane',grant_sudo=False)],device_ids=[1])
    with pytest.raises(ValidationError,match='shared changes'):
        BulkUserUpdate(users=[dict(username='jane',grant_sudo=True)],grant_sudo=False,device_ids=[1])
    assert BulkUserUpdate(usernames=['jane'],grant_sudo=True,device_ids=[1]).updates[0].grant_sudo is True
    with pytest.raises(CsvValidationError,match='grant_sudo must be'):
        parse_csv('username,grant_sudo\njane,maybe\n','edit')


def test_inspection_accepts_explicit_devices_with_stale_facts(api):
    client,runner,_=api
    response=client.post('/api/v2/users/inspect',json={'device_ids':[1,2]})
    assert response.status_code==200,response.text
    assert runner.call_args.args[1]=='access_inspect.yml'
    assert runner.call_args.kwargs['hosts']==['one','two']


@pytest.fixture
def public_key():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    return Ed25519PrivateKey.generate().public_key().public_bytes(Encoding.OpenSSH, PublicFormat.OpenSSH).decode() + ' jane@example.com'


def test_edit_credentials_only_request_and_redaction(api, public_key):
    from backend.services.ansible_runner import redact_extra_vars
    client, runner, _ = api
    password = 'Temporary-password-123!'
    response = client.put('/api/v2/users/bulk-update', json={
        'device_ids': [1], 'users': [{'username': 'jane', 'password': password, 'public_key': public_key}],
    })
    assert response.status_code == 200, response.text
    kwargs = runner.call_args.kwargs
    assert kwargs['extra_vars']['user_updates'][0]['password'] == password
    assert kwargs['extra_vars']['user_updates'][0]['public_key'] == public_key
    assert password not in redact_extra_vars(kwargs['extra_vars'])
    assert 'password' not in kwargs['completion_action']['users'][0]


def test_public_key_add_edit_and_csv(api, public_key):
    client, runner, _ = api
    for mode in ['add', 'edit']:
        header = 'username,full_name,public_key' if mode == 'add' else 'username,public_key'
        row = f'jane,Jane,{public_key}' if mode == 'add' else f'jane,{public_key}'
        records = parse_csv(f'{header}\n{row}\n', mode)
        assert records[0].public_key == public_key
        payload = {'device_ids': [1], 'users': [record.model_dump(exclude_none=True) for record in records]}
        response = client.post('/api/v2/users/bulk-add', json=payload) if mode == 'add' else client.put('/api/v2/users/bulk-update', json=payload)
        assert response.status_code == 200, response.text
        key = 'user_records' if mode == 'add' else 'user_updates'
        assert runner.call_args.kwargs['extra_vars'][key][0]['public_key'] == public_key
    shared = BulkUserUpdate(usernames=['jane'], public_key=public_key, device_ids=[1])
    assert shared.updates[0].public_key == public_key


@pytest.mark.parametrize('key', ['ssh-ed25519 not-a-key', 'https://example.com/key.pub',
                                  '-----BEGIN PRIVATE KEY-----', 'ssh-rsa AAAA',
                                  'ssh-ed25519 AAAA\nssh-ed25519 AAAA', '{{ lookup("pipe", "id") }}'])
def test_invalid_public_key_never_queues_work(api, key):
    client, runner, _ = api
    for path, method, record in [('/bulk-add', client.post, {'full_name': 'Jane'}), ('/bulk-update', client.put, {})]:
        response = method('/api/v2/users' + path, json={'device_ids': [1], 'users': [dict(username='jane', public_key=key, **record)]})
        assert response.status_code == 422, response.text
    runner.assert_not_awaited()


@pytest.mark.parametrize('password', ['short', 'long-enough-{{bad}}', 'long-enough\npassword'])
def test_invalid_edit_password_never_queues_work(api, password):
    client, runner, _ = api
    response = client.put('/api/v2/users/bulk-update', json={'device_ids': [1], 'users': [{'username': 'jane', 'password': password}]})
    assert response.status_code == 422, response.text
    runner.assert_not_awaited()
