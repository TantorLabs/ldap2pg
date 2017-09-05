<h1>Cookbook</h1>

Here in this cookbook, you'll find some recipes for various use case of
`ldap2pg`.

If you struggle to find a way to setup `ldap2pg` for your needs, please [file an
issue](https://github.com/dalibo/ldap2pg/issues/new) so that we can update
*Cookbook* with new recipes ! Your contribution is welcome!


# Don't Synchronize Superusers

Say you don't want to manage superusers in the cluser with `ldap2pg`, just
regular users. E.g. you manage superusers through Ansible or another LDAP
directory. By default, `ldap2pg` will purge these users not in LDAP directory.

To avoid that, you can put all superusers in `postgres:blacklist` settings from
YAML file. The drawback is that you must keep it sync with the cluster.

Another option is to **customize the SQL query for roles inspection** with an
ad-hoc `WHERE` clause. Just as following.

``` yaml
postgres:
  roles_query: |
    SELECT
        role.rolname, array_agg(members.rolname) AS members,
        {options}
    FROM
        pg_catalog.pg_roles AS role
    LEFT JOIN pg_catalog.pg_auth_members ON roleid = role.oid
    LEFT JOIN pg_catalog.pg_roles AS members ON members.oid = member
    WHERE role.rolsuper IS FALSE
    GROUP BY role.rolname, {options}
    ORDER BY 1;
```

This way `ldap2pg` will ignore all superusers defined in the cluster. You are
safe. This customization can be used for other case where you want to split
roles in different sets with different policies.

The query must return a set of row with the rolname as first column, an array
with the name of all members of the role as second column, followed by columns
defined in `{options}` template variable. `{options}` contains the ordered
columns of managed role options as supported by `ldap2pg`. `ldpa2pg` user
Python's [*Format String
Syntax*](https://docs.python.org/3.7/library/string.html#formatstrings). Only
`options` substitution is available. `%` is safe.