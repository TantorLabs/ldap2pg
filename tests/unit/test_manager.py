from __future__ import unicode_literals

import pytest


def test_query_ldap(mocker):
    from ldap2pg.manager import SyncManager, UserError

    manager = SyncManager(ldapconn=mocker.Mock())
    manager.ldapconn.search_s.return_value = [
        ('dn=a', {}),
        ('dn=b', {'member': ['m']}),
        (None, {'ref': True}),
        (None, ['ldap://list_ref']),
    ]

    entries = manager.query_ldap(
        base='ou=people,dc=global', filter='(objectClass=*)',
        scope=2, joins={}, attributes=['cn'],
        allow_missing_attributes=['member'],
    )

    assert 2 == len(entries)
    assert [] == entries[0].attributes['member']

    manager.ldapconn.search_s.return_value = [('dn=a', {'a': b'\xbb'})]
    with pytest.raises(UserError):
        manager.query_ldap(
            base='ou=people,dc=global', filter='(objectClass=*)',
            scope=2, joins={}, attributes=['cn'],
        )


def test_query_ldap_joins_ok(mocker):
    from ldap2pg.manager import SyncManager, LDAPEntry

    search_result = [
        ('cn=A,ou=people,dc=global', {
            'cn': ['A'], 'member': ['cn=P,ou=people,dc=global']}),
        ('cn=B,ou=people,dc=global', {
            'cn': ['B'], 'member': ['cn=P,ou=people,dc=global']}),
    ]

    sub_search_result = [
        ('cn=P,ou=people,dc=global', {'sAMAccountName': ['P']}),
    ]

    manager = SyncManager(ldapconn=mocker.Mock())
    manager.ldapconn.search_s.side_effect = [
            search_result, sub_search_result]

    entries = manager.query_ldap(
        base='ou=people,dc=global',
        filter='(objectClass=group)',
        scope=2,
        attributes=['cn', 'member'],
        joins={'member': dict(
            base='ou=people,dc=global',
            scope=2,
            filter='(objectClass=people)',
            attributes=['sAMAccountName'],
        )},
    )

    assert 2 == manager.ldapconn.search_s.call_count

    expected_entries = [
        LDAPEntry(
            'cn=A,ou=people,dc=global',
            {
                'cn': ['A'],
                'member': ['cn=P,ou=people,dc=global'],
            },
            {
                'member': [LDAPEntry('cn=P,ou=people,dc=global', {
                    'samaccountname': ['P'],
                })],
            },
        ),
        LDAPEntry(
            'cn=B,ou=people,dc=global',
            {
                'cn': ['B'],
                'member': ['cn=P,ou=people,dc=global'],
            },
            {
                'member': [LDAPEntry('cn=P,ou=people,dc=global', {
                    'samaccountname': ['P'],
                })],
            },
        ),
    ]

    assert expected_entries == entries


def test_query_ldap_joins_filtered_allowed(mocker):
    from ldap2pg.manager import SyncManager, LDAPEntry

    search_result = [
        ('cn=A,ou=people,dc=global', {
            'cn': ['A'], 'member': ['cn=P,ou=people,dc=global']}),
    ]

    sub_search_result = [
    ]

    manager = SyncManager(ldapconn=mocker.Mock())
    manager.ldapconn.search_s.side_effect = [
            search_result, sub_search_result]

    entries = manager.query_ldap(
        base='ou=people,dc=global',
        filter='(objectClass=group)',
        scope=2,
        attributes=['cn', 'member'],
        joins={'member': dict(
            base='ou=people,dc=global',
            scope=2,
            filter='(objectClass=group)',
            attributes=['cn'],
            allow_missing_attributes=[],
        )},
        allow_missing_attributes=['member'],
    )

    assert 2 == manager.ldapconn.search_s.call_count

    expected_entries = [
        LDAPEntry(
            'cn=A,ou=people,dc=global',
            {
                'cn': ['A'],
                'member': ['cn=P,ou=people,dc=global'],
            },
            {
                'member': [],
            },
        ),
    ]

    assert expected_entries == entries


def test_query_ldap_joins_filtered_not_allowed(mocker):
    from ldap2pg.manager import SyncManager, LDAPEntry

    search_result = [
        ('cn=A,ou=people,dc=global', {
            'cn': ['A'], 'member': ['cn=P,ou=people,dc=global']}),
    ]

    sub_search_result = [
    ]

    manager = SyncManager(ldapconn=mocker.Mock())
    manager.ldapconn.search_s.side_effect = [
            search_result, sub_search_result]

    entries = manager.query_ldap(
        base='ou=people,dc=global',
        filter='(objectClass=group)',
        scope=2,
        attributes=['cn', 'member'],
        joins={'member': dict(
            base='ou=people,dc=global',
            scope=2,
            filter='(objectClass=group)',
            attributes=['cn'],
        )},
        allow_missing_attributes=[],
    )

    assert 2 == manager.ldapconn.search_s.call_count

    expected_entries = [
        LDAPEntry(
            'cn=A,ou=people,dc=global',
            {
                'cn': ['A'],
                'member': ['cn=P,ou=people,dc=global'],
            },
        ),
    ]

    assert expected_entries == entries


def test_query_ldap_joins_missing(mocker):
    from ldap2pg.manager import SyncManager, UserError

    search_result = [(
        'cn=A,ou=people,dc=global', {
            'cn': ['A'],
        }
    )]

    manager = SyncManager(ldapconn=mocker.Mock())
    manager.ldapconn.search_s.side_effect = [search_result]

    with pytest.raises(UserError) as ei:
        manager.query_ldap(
            base='ou=people,dc=global', filter='(objectClass=group)',
            scope=2, joins={'member': dict(
                filter='(objectClass=people)',
                attributes=['sAMAccountName'],
            )},
            attributes=['cn', 'member'],
        )
    assert "Missing attribute member" in str(ei.value)


def test_query_ldap_bad_filter(mocker):
    from ldap2pg.manager import SyncManager, LDAPError, UserError

    manager = SyncManager(ldapconn=mocker.Mock())
    manager.ldapconn.search_s.side_effect = LDAPError()

    with pytest.raises(UserError):
        manager.query_ldap(
            base='dc=unit', filter='(broken',
            scope=2, joins={}, attributes=[],
        )

    assert manager.ldapconn.search_s.called is True


def test_inspect_ldap_unexpected_dn(mocker):
    ql = mocker.patch('ldap2pg.manager.SyncManager.query_ldap')

    from ldap2pg.manager import SyncManager, UserError, LDAPEntry
    from ldap2pg.role import RoleRule

    manager = SyncManager()

    ql.return_value = [
        LDAPEntry('dn0', {
            'member': ['cn=member0', 'baddn=o0', 'cn=member1'],
        })]

    list(manager.inspect_ldap([dict(
        description="Test query desc",
        ldapsearch=dict(on_unexpected_dn='warn'),
        roles=[RoleRule(names=['{member.cn}'])],
    )]))

    list(manager.inspect_ldap([dict(
        ldapsearch=dict(on_unexpected_dn='ignore'),
        roles=[RoleRule(names=['{member.cn}'])]
    )]))

    with pytest.raises(UserError):
        list(manager.inspect_ldap([dict(
            ldapsearch=dict(),
            roles=[RoleRule(names=['{member.cn}'])],
        )]))


def test_inspect_ldap_missing_attribute(mocker):
    ql = mocker.patch('ldap2pg.manager.SyncManager.query_ldap')

    from ldap2pg.manager import SyncManager, UserError, LDAPEntry
    from ldap2pg.role import RoleRule

    manager = SyncManager()

    # Don't return member attribute.
    ql.return_value = [LDAPEntry('dn0')]

    with pytest.raises(UserError) as ei:
        list(manager.inspect_ldap([dict(
            ldap=dict(base='...'),
            # Request member attribute.
            roles=[RoleRule(names=['{member.cn}'])],
        )]))
    assert 'Missing attribute: member' in str(ei.value)


def test_inspect_ldap_grants(mocker):
    from ldap2pg.manager import SyncManager
    from ldap2pg.privilege import Grant, NspAcl
    from ldap2pg.utils import make_group_map

    privileges = dict(ro=NspAcl(name='ro'))
    manager = SyncManager(
        pool=mocker.Mock(), ldapconn=mocker.Mock(), privileges=privileges,
        privilege_aliases=make_group_map(privileges),
        inspector=mocker.Mock(name='inspector'),
    )
    manager.inspector.roles_blacklist = ['blacklisted']
    rule = mocker.Mock(name='grant', attributes_map={})
    rule.generate.return_value = [
        Grant('ro', 'postgres', None, 'alice'),
        Grant('ro', 'postgres', None, 'blacklisted'),
    ]
    syncmap = [dict(roles=[], grant=[rule])]

    _, grants = manager.inspect_ldap(syncmap=syncmap)

    assert 1 == len(grants)


def test_postprocess_grants():
    from ldap2pg.inspector import Database, Schema
    from ldap2pg.manager import SyncManager
    from ldap2pg.privilege import DefAcl, Grant, Acl

    manager = SyncManager(
        privileges=dict(ro=DefAcl(name='ro')),
        privilege_aliases=dict(ro=['ro']),
    )

    # No owners
    acl = manager.postprocess_acl(Acl(), databases=dict())
    assert 0 == len(acl)

    acl = Acl([Grant(privilege='ro', dbname=['db'], schema=None)])
    db = Database('db', 'postgres')
    db.schemas['public'] = Schema('public', ['postgres', 'owner'])
    db.schemas['ns'] = Schema('public', ['owner'])
    acl = manager.postprocess_acl(acl, databases=[db])

    # One grant per schema, per owner
    assert 3 == len(acl)


def test_postprocess_acl_bad_database():
    from ldap2pg.inspector import Database, Schema
    from ldap2pg.manager import SyncManager, UserError
    from ldap2pg.privilege import NspAcl, Grant, Acl
    from ldap2pg.utils import make_group_map

    privileges = dict(ro=NspAcl(name='ro', inspect='SQL'))
    manager = SyncManager(
        privileges=privileges, privilege_aliases=make_group_map(privileges),
    )

    acl = Acl([Grant('ro', ['inexistantdb'], None, 'alice')])
    db = Database('db', 'postgres')
    db.schemas['public'] = Schema('public', ['postgres'])

    with pytest.raises(UserError) as ei:
        manager.postprocess_acl(acl, [db])
    assert 'inexistantdb' in str(ei.value)


def test_postprocess_acl_inexistant_privilege():
    from ldap2pg.inspector import Database, Schema
    from ldap2pg.manager import SyncManager, UserError
    from ldap2pg.privilege import Acl, Grant

    manager = SyncManager()
    db = Database('postgres', 'postgres')
    db.schemas['public'] = Schema('public', ['postgres'])

    with pytest.raises(UserError):
        manager.postprocess_acl(
            acl=Acl([Grant('inexistant')]),
            databases=[db],
        )


def test_inspect_ldap_roles(mocker):
    ql = mocker.patch('ldap2pg.manager.SyncManager.query_ldap')

    from ldap2pg.manager import LDAPEntry, SyncManager
    from ldap2pg.role import Role

    ql.return_value = [LDAPEntry('dn')]

    manager = SyncManager(
        ldapconn=mocker.Mock(),
        inspector=mocker.Mock(name='inspector'),
    )
    manager.inspector.roles_blacklist = ['blacklisted']

    rule0 = mocker.Mock(name='rule0', attributes_map={})
    rule0.generate.return_value = [Role('alice', options=dict(LOGIN=True))]
    rule1 = mocker.Mock(name='rule1', attributes_map={})
    rule1.generate.return_value = [Role('bob')]
    rule2 = mocker.Mock(name='rule2', attributes_map={})
    rule2.generate.return_value = [Role('blacklisted')]

    # Minimal effective syncmap
    syncmap = [
        dict(roles=[]),
        dict(
            ldap=dict(base='ou=users,dc=tld', filter='*', attributes=['cn']),
            roles=[rule0, rule1, rule2],
        ),
    ]

    ldaproles, _ = manager.inspect_ldap(syncmap=syncmap)

    assert 'alice' in ldaproles
    assert 'bob' in ldaproles


def test_inspect_roles_merge_duplicates(mocker):
    from ldap2pg.manager import SyncManager
    from ldap2pg.role import RoleRule

    manager = SyncManager()

    syncmap = [
        dict(roles=[
            RoleRule(names=['group0']),
            RoleRule(names=['group1']),
            RoleRule(names=['bob'], parents=['group0']),
            RoleRule(names=['bob'], parents=['group1']),
        ]),
    ]

    ldaproles, _ = manager.inspect_ldap(syncmap=syncmap)

    ldaproles = {r: r for r in ldaproles}
    assert 'group0' in ldaproles
    assert 'group1' in ldaproles
    assert 'bob' in ldaproles
    assert 3 == len(ldaproles)
    assert 2 == len(ldaproles['bob'].parents)


def test_inspect_roles_duplicate_differents_options(mocker):
    from ldap2pg.manager import SyncManager, UserError
    from ldap2pg.role import RoleRule

    manager = SyncManager()

    syncmap = [dict(roles=[
        RoleRule(names=['group0']),
        RoleRule(names=['group1']),
        RoleRule(names=['bob'], options=dict(LOGIN=True)),
        RoleRule(names=['bob'], options=dict(LOGIN=False)),
    ])]

    with pytest.raises(UserError):
        manager.inspect_ldap(syncmap=syncmap)


def test_inspect_ldap_roles_comment_error(mocker):
    ql = mocker.patch('ldap2pg.manager.SyncManager.query_ldap')

    from ldap2pg.manager import LDAPEntry, SyncManager, UserError
    from ldap2pg.role import CommentError

    ql.return_value = [LDAPEntry('dn')]

    rule = mocker.Mock(name='rule', attributes_map={})
    rule.generate.side_effect = CommentError("message")
    rule.comment.formats = ['From {desc}']

    mapping = dict(
        ldap=dict(base='ou=users,dc=tld', filter='*', attributes=['cn']),
        roles=[rule],
    )

    manager = SyncManager()
    with pytest.raises(UserError):
        manager.inspect_ldap(syncmap=[mapping])


def test_empty_sync_map(mocker):
    from ldap2pg.manager import SyncManager, RoleSet

    manager = SyncManager(
        inspector=mocker.Mock(name='inspector'),
        pool=mocker.Mock(name='pool'),
    )
    eq = mocker.patch('ldap2pg.manager.execute_queries')
    eq.return_value = 0
    manager.inspector.fetch_databases.return_value = []
    manager.inspector.fetch_me.return_value = 'me', True
    manager.inspector.fetch_roles_blacklist.return_value = []
    manager.inspector.fetch_roles.return_value = RoleSet(), RoleSet()
    manager.inspector.filter_roles.return_value = RoleSet(), RoleSet()

    manager.sync([])


def test_entry_build_vars():
    from ldap2pg.ldap import LDAPEntry
    from ldap2pg.manager import SyncManager

    entry = LDAPEntry(
        dn='cn=my0,uo=gr0,dc=acme,dc=tld',
        attributes=dict(
            cn=['my0'],
            member=[
                'cn=m0,uo=gr0',
                'cn=m1,uo=gr0',
            ],
            simple=[
                'cn=s0,uo=gr1',
                'cn=s1,uo=gr1',
                'cn=s2,uo=gr1',
            ],
        ),
        children=dict(member=[
            LDAPEntry(
                'cn=m0,uo=gr0',
                dict(mail=['m0@acme.tld', 'm00@acme.tld']),
            ),
            LDAPEntry(
                'cn=m1,uo=gr0',
                dict(mail=['m1@acme.tld']),
            ),
        ]),
    )

    map_ = dict(
        __self__=['dn', 'cn', 'dn.cn'],
        member=['cn', 'dn', 'mail', 'dn.cn'],
        simple=['cn'],
    )

    manager = SyncManager()
    vars_ = manager.build_format_vars(entry, map_, on_unexpected_dn='fail')
    wanted = dict(
        __self__=[dict(
            dn=[dict(
                dn="cn=my0,uo=gr0,dc=acme,dc=tld",
                cn="my0",
            )],
            cn=["my0"],
        )],
        member=[
            dict(
                dn=[dict(dn="cn=m0,uo=gr0", cn="m0")],
                cn=["m0"],
                mail=["m0@acme.tld", "m00@acme.tld"],
            ),
            dict(
                dn=[dict(dn="cn=m1,uo=gr0", cn="m1")],
                cn=["m1"],
                mail=["m1@acme.tld"],
            ),
        ],
        simple=[
            dict(
                dn=["cn=s0,uo=gr1"],
                cn=["s0"],
            ),
            dict(
                dn=["cn=s1,uo=gr1"],
                cn=["s1"],
            ),
            dict(
                dn=["cn=s2,uo=gr1"],
                cn=["s2"],
            ),
        ],
    )

    assert wanted == vars_


def test_sync(mocker):
    from ldap2pg.manager import RoleOptions, RoleSet, SyncManager, UserError
    from ldap2pg.inspector import Database, Schema

    mod = 'ldap2pg.manager'
    mocker.patch(
        mod + '.RoleOptions.SUPPORTED_COLUMNS',
        RoleOptions.SUPPORTED_COLUMNS[:],
    )

    cls = mod + '.SyncManager'
    il = mocker.patch(cls + '.inspect_ldap', autospec=True)
    mocker.patch(cls + '.postprocess_acl', autospec=True)

    eq = mocker.patch(mod + '.execute_queries')
    # No privileges to sync, one query
    eq.return_value = 1

    pool = mocker.Mock(name='pool')
    inspector = mocker.Mock(name='inspector')
    manager = SyncManager(dry=True, pool=pool, inspector=inspector)

    inspector.fetch_databases.return_value = ['postgres']
    inspector.fetch_me.return_value = ('postgres', False)
    inspector.fetch_roles_blacklist.return_value = ['pg_*']
    inspector.fetch_roles.return_value = RoleSet(), RoleSet()
    pgroles = mocker.Mock(name='pgroles')
    # Simple diff with one query
    pgroles.diff.return_value = qry = [
        mocker.Mock(name='qry', args=(), message='hop')]
    inspector.filter_roles.return_value = RoleSet(), pgroles
    il.return_value = (mocker.Mock(name='ldaproles'), RoleSet())
    qry[0].expand.return_value = [qry[0]]
    db = Database('postgres', 'postgres')
    db.schemas['ns'] = Schema('ns', ['owner'])
    inspector.fetch_schemas.return_value = [db]
    inspector.fetch_grants.return_value = pgacl = mocker.Mock(name='pgacl')
    pgacl.diff.return_value = []

    count = manager.sync(syncmap=[])
    assert pgroles.diff.called is True
    assert pgacl.diff.called is False
    assert 1 == count

    # With privileges
    manager.privileges = dict(ro=mocker.Mock(name='ro'))
    count = manager.sync(syncmap=[])
    assert pgroles.diff.called is True
    assert pgacl.diff.called is True
    assert 2 == count

    # Dry run with roles and ACL
    manager.dry = True
    manager.sync(syncmap=[])

    # Nothing to do
    eq.return_value = 0
    count = manager.sync(syncmap=[])
    assert 0 == count

    # resolve_membership failure
    il.return_value[0].resolve_membership.side_effect = ValueError()
    with pytest.raises(UserError):
        manager.sync(syncmap=[])
