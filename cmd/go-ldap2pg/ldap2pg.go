package main

import (
	"context"
	"fmt"
	"os"
	"runtime"
	"runtime/debug"
	"time"

	"golang.org/x/exp/slog"

	"github.com/dalibo/ldap2pg/internal"
	"github.com/dalibo/ldap2pg/internal/config"
	"github.com/dalibo/ldap2pg/internal/perf"
	"github.com/mattn/go-isatty"
	"github.com/spf13/pflag"
	"github.com/spf13/viper"
)

func main() {
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	defer func() {
		r := recover()
		if r == nil {
			return
		}
		slog.Error("Panic!", "err", r)
		buf := debug.Stack()
		fmt.Fprintf(os.Stderr, "%s", buf)
		slog.Error("Aborting ldap2pg.", "err", r)
		slog.Error("Please file an issue at https://github.com/dalibo/ldap2pg/issue/new with full log.")
		os.Exit(1)
	}()

	// Bootstrap logging first to log in setup.
	internal.SetLoggingHandler(slog.LevelInfo, isatty.IsTerminal(os.Stderr.Fd()))
	setupViper()
	if viper.GetBool("help") {
		pflag.Usage()
		return
	} else if viper.GetBool("version") {
		showVersion()
		return
	}
	err := ldap2pg(ctx)
	if err != nil {
		slog.Error("Fatal error.", "err", err)
		os.Exit(1)
	}
}

func ldap2pg(ctx context.Context) (err error) {
	start := time.Now()

	controller, err := unmarshalController()
	if err != nil {
		return
	}

	internal.SetLoggingHandler(controller.LogLevel, controller.Color)
	slog.Info("Starting ldap2pg",
		"commit", internal.ShortRevision,
		"version", internal.Version,
		"runtime", runtime.Version())
	slog.Warn("go-ldap2pg is alpha software! Use at your own risks!")

	configPath := config.FindFile(controller.Config)
	slog.Info("Using YAML configuration file.", "path", configPath)
	c, err := config.Load(configPath)
	if slog.Default().Enabled(ctx, slog.LevelDebug) {
		c.Dump()
	}
	if err != nil {
		return
	}

	instance, err := c.Postgres.Build().Inspect(ctx)
	if err != nil {
		return
	}

	wanted, err := c.SyncMap.Wanted(&controller.LdapWatch, instance.RolesBlacklist)
	if err != nil {
		return
	}

	if controller.Real {
		slog.Info("Real mode. Postgres instance will modified.")
	} else {
		slog.Warn("Dry run. Postgres instance will be untouched.")
	}

	count, err := wanted.Sync(ctx, &controller.PostgresWatch, controller.Real, instance)

	vmPeak := perf.ReadVMPeak()
	elapsed := time.Since(start)
	logAttrs := []interface{}{
		"elapsed", elapsed,
		"mempeak", perf.FormatBytes(vmPeak),
		"postgres", controller.PostgresWatch.Total,
		"queries", count,
		"ldap", controller.LdapWatch.Total,
		"searches", controller.LdapWatch.Count,
	}
	if count > 0 {
		slog.Info("Comparison complete.", logAttrs...)
	} else {
		slog.Info("Nothing to do.", logAttrs...)
	}

	if err != nil {
		return
	}

	if controller.Check && count > 0 {
		os.Exit(1)
	}

	return
}

func showVersion() {
	fmt.Printf("go-ldap2pg %s\n", internal.Version)

	bi, ok := debug.ReadBuildInfo()
	if !ok {
		return
	}
	modmap := make(map[string]string)
	for _, mod := range bi.Deps {
		modmap[mod.Path] = mod.Version
	}
	modules := []string{
		"github.com/jackc/pgx/v5",
		"github.com/go-ldap/ldap/v3",
		"gopkg.in/yaml.v3",
	}
	for _, mod := range modules {
		fmt.Printf("%s %s\n", mod, modmap[mod])
	}

	fmt.Printf("%s %s %s\n", runtime.Version(), runtime.GOOS, runtime.GOARCH)
}