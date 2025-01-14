package inspect

import (
	"context"
	"fmt"

	"github.com/dalibo/ldap2pg/internal/privilege"
	"github.com/jackc/pgx/v5"
	"golang.org/x/exp/slices"
	"golang.org/x/exp/slog"
)

func (instance *Instance) InspectStage2(ctx context.Context, pc Config) (err error) {
	pgconn, err := pgx.Connect(ctx, "")
	if err != nil {
		return
	}
	defer pgconn.Close(ctx)

	err = instance.InspectGrants(ctx, pgconn, pc.ManagedPrivileges)
	if err != nil {
		return
	}
	return
}

func (instance *Instance) InspectGrants(ctx context.Context, pgconn *pgx.Conn, managedPrivileges map[string][]string) error {
	var databases []string
	for _, database := range instance.Databases {
		databases = append(databases, database.Name)
	}

	for _, p := range privilege.Map {
		managedTypes := managedPrivileges[p.Object]
		if 0 == len(managedTypes) {
			continue
		}

		slog.Debug("Inspecting grants.", "scope", p.Scope, "object", p.Object, "types", managedTypes)
		slog.Debug("Executing SQL query:\n"+p.Inspect, "arg", managedTypes)
		rows, err := pgconn.Query(ctx, p.Inspect, managedTypes)
		if err != nil {
			return fmt.Errorf("bad query: %w", err)
		}
		for rows.Next() {
			grant, err := privilege.RowTo(rows)
			if err != nil {
				return fmt.Errorf("bad row: %w", err)
			}

			// Filter Database object. We don't pass databases as parameter because it's only relevant for database query.
			if "" != grant.Database && !slices.Contains(databases, grant.Database) {
				continue
			}

			grant.Target = p.Object
			grant.Normalize()

			slog.Debug("Grant found.", "grant", grant)
			instance.Grants = append(instance.Grants, grant)
		}
		if err := rows.Err(); err != nil {
			return fmt.Errorf("%s: %w", p, err)
		}
	}
	return nil
}
