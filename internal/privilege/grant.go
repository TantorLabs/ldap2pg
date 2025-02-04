package privilege

import (
	"strings"

	"github.com/jackc/pgx/v5"
)

// Grant holds privilege informations from Postgres inspection or Grant rule.
//
// Not to confuse with Privilege. A Grant references a privilege, an object and
// roles. It's more like aclitem object in PostgreSQL.
type Grant struct {
	Target   string // Name of the target object: DATABASE, TABLES, etc.
	Grantor  string
	Grantee  string // "" means default privilege for Grantor.
	Type     string
	Database string // "" for instance grant.
	Schema   string // "" for database grant.
	Object   string // "" for both schema and database grants.
	Partial  bool   // Used for ALL TABLES permissions.
}

func RowTo(row pgx.CollectableRow) (g Grant, err error) {
	err = row.Scan(&g.Grantor, &g.Grantee, &g.Type, &g.Database, &g.Schema, &g.Object, &g.Partial)
	return
}

// Normalize ensures grant fields are consistent with privilege scope.
//
// This way grants from wanted state and from inspect are comparables.
func (g *Grant) Normalize() {
	p := g.Privilege()

	// For now, drop grantor, to remove Grantor from comparison with wanted grant.
	g.Grantor = ""

	if "instance" == p.Scope {
		// Allow to use Database as object name for database.
		if "" == g.Object {
			g.Object = g.Database
			g.Database = ""
		}
	}

	// For now, drop schema. We'll need it only for schema objects in the
	// future.
	g.Schema = ""
}

func (g Grant) Privilege() Privilege {
	return Map[g.Target]
}

func (g Grant) String() string {
	b := strings.Builder{}
	if g.Partial {
		b.WriteString("PARTIAL ")
	}
	if "" == g.Grantee {
		b.WriteString("DEFAULT ")
	}
	b.WriteString(g.Type)
	b.WriteString(" ON ")
	b.WriteString(g.Target)
	b.WriteByte(' ')

	o := strings.Builder{}
	o.WriteString(g.Database)
	if "" != g.Schema {
		if o.Len() > 0 {
			o.WriteByte('.')
		}
		o.WriteString(g.Schema)
	}
	if "" != g.Object {
		if o.Len() > 0 {
			o.WriteByte('.')
		}
		o.WriteString(g.Object)
	}

	b.WriteString(o.String())
	if "" != g.Grantee {
		b.WriteString(" TO ")
		b.WriteString(g.Grantee)
	}
	if "" != g.Grantor {
		b.WriteString(" GRANTED BY ")
		b.WriteString(g.Grantor)
	}

	return b.String()
}
