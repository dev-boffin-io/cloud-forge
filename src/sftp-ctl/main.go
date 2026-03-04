package main

import (
	"encoding/json"
	"fmt"
	"net"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"sort"
	"strconv"
	"strings"
	"syscall"
	"time"
)

// ─── ANSI Colors ───────────────────────────────────────────────────────────────

const (
	Green   = "\033[1;32m"
	Red     = "\033[1;31m"
	Yellow  = "\033[1;33m"
	Cyan    = "\033[1;36m"
	Magenta = "\033[1;35m"
	NC      = "\033[0m"
)

// ─── Profile ──────────────────────────────────────────────────────────────────
// Must stay in sync with rclone_sftp_launcher.go ConfigProfile.

type ConfigProfile struct {
	Remote               string `json:"remote"`
	Port                 string `json:"port"`
	BindAddr             string `json:"bind_addr"`
	User                 string `json:"user"`
	PassObscured         string `json:"pass_obscured"`
	PidFile              string `json:"pid_file"`
	BufferSize           string `json:"buffer_size"`
	Transfers            int    `json:"transfers"`
	Checkers             int    `json:"checkers"`
	VfsCacheMode         string `json:"vfs_cache_mode"`
	VfsCacheSize         string `json:"vfs_cache_size"`
	VfsCacheAge          string `json:"vfs_cache_age"`
	VfsCacheDir          string `json:"vfs_cache_dir"`
	DirCache             string `json:"dir_cache"`
	PollInterval         string `json:"poll_interval"`
	VfsCachePollInterval string `json:"vfs_cache_poll_interval"`
	LogFile              string `json:"log_file"`
	LogLevel             string `json:"log_level"`
	AuthorizedKeys       string `json:"authorized_keys"`
	UseMmap              bool   `json:"use_mmap"`
	NoModtime            bool   `json:"no_modtime"`
}

// ─── Print helpers ────────────────────────────────────────────────────────────

func printError(msg string) { fmt.Fprintf(os.Stderr, "%s❌ %s%s\n", Red, msg, NC) }
func printWarn(msg string)  { fmt.Printf("%s⚠️  %s%s\n", Yellow, msg, NC) }
func printOK(msg string)    { fmt.Printf("%s✅ %s%s\n", Green, msg, NC) }

// ─── Usage ────────────────────────────────────────────────────────────────────

func usage() {
	fmt.Printf("%sUsage:%s sftp-controller {start|stop|restart|status} [remote_name|all]\n", Yellow, NC)
	fmt.Printf("  %sExamples:%s\n", Magenta, NC)
	fmt.Println("    sftp-controller start  gdrive")
	fmt.Println("    sftp-controller stop   all")
	fmt.Println("    sftp-controller status all")
}

// ─── Main ─────────────────────────────────────────────────────────────────────

func main() {
	if len(os.Args) < 2 {
		usage()
		os.Exit(1)
	}

	action := strings.ToLower(os.Args[1])
	target := "all"
	if len(os.Args) > 2 {
		target = os.Args[2]
	}

	// #5 — early rclone binary check before any work.
	if _, err := exec.LookPath("rclone"); err != nil {
		printError("rclone not found in PATH. Install from: https://rclone.org/downloads/")
		os.Exit(1)
	}

	// Validate action up-front so we never process targets only to fail later.
	// Fix #7 — unknown action is caught before any work is done.
	switch action {
	case "start", "stop", "restart", "status":
		// valid
	default:
		printError(fmt.Sprintf("Unknown action '%s'.", action))
		usage()
		os.Exit(1)
	}

	home, err := os.UserHomeDir()
	if err != nil {
		printError("Cannot determine home directory: " + err.Error())
		os.Exit(1)
	}
	profileDir := filepath.Join(home, ".rclone_lock", "profiles")

	// Collect target profile names.
	var targets []string
	if target == "all" {
		// Fix #1 — os.ReadDir replaces deprecated ioutil.ReadDir.
		entries, err := os.ReadDir(profileDir)
		if err != nil {
			printError("Cannot read profile directory: " + err.Error())
			os.Exit(1)
		}
		for _, e := range entries {
			if !e.IsDir() && filepath.Ext(e.Name()) == ".json" {
				targets = append(targets, strings.TrimSuffix(e.Name(), ".json"))
			}
		}
	} else {
		targets = append(targets, target)
	}

	// #4 — alphabetical order for consistent, readable output.
	sort.Strings(targets)

	if len(targets) == 0 {
		printWarn("No profiles found.")
		return
	}

	// Execute action on each target; collect summary counts for status.
	running, offline, failed := 0, 0, 0
	for _, name := range targets {
		profilePath := filepath.Join(profileDir, name+".json")
		profile, err := loadProfile(profilePath)
		if err != nil {
			// Fix #6 — distinguish missing file from bad JSON.
			if os.IsNotExist(err) {
				printError(fmt.Sprintf("Profile not found: %s", profilePath))
			} else {
				printError(fmt.Sprintf("Cannot parse profile '%s': %v", name, err))
			}
			failed++
			continue
		}

		switch action {
		case "start":
			if err := startServer(profile); err != nil {
				failed++
			}
		case "stop":
			if err := stopServer(profile); err != nil {
				failed++
			}
		case "restart":
			// #2 — if stop fails, don't attempt start.
			if err := stopServer(profile); err != nil {
				printError(fmt.Sprintf("Failed to stop '%s' before restart.", profile.Remote))
				failed++
				continue
			}
			if !waitForStop(profile.PidFile, 5*time.Second) {
				printWarn(fmt.Sprintf("'%s' stop timed out — forcing restart anyway.", profile.Remote))
			}
			if err := startServer(profile); err != nil {
				failed++
			}
		case "status":
			if statusServer(profile) {
				running++
			} else {
				offline++
			}
		}
	}

	// Fix #9 — summary line for multi-target status.
	if action == "status" && len(targets) > 1 {
		fmt.Printf("\n%s── Summary ──%s  running: %s%d%s  offline: %s%d%s",
			Cyan, NC,
			Green, running, NC,
			Red, offline, NC,
		)
		if failed > 0 {
			fmt.Printf("  errors: %s%d%s", Yellow, failed, NC)
		}
		fmt.Println()
	}
}

// ─── Profile loader ───────────────────────────────────────────────────────────

// loadProfile reads and parses a JSON profile file.
// Fix #1 — os.ReadFile replaces deprecated ioutil.ReadFile.
// Fix #6 — returns raw os error so callers can use os.IsNotExist().
func loadProfile(path string) (*ConfigProfile, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var p ConfigProfile
	if err := json.Unmarshal(data, &p); err != nil {
		return nil, fmt.Errorf("JSON parse error: %w", err)
	}
	return &p, nil
}

// ─── Server actions ───────────────────────────────────────────────────────────

// startServer launches rclone serve sftp for the given profile.
func startServer(p *ConfigProfile) error {
	// Check if already running via PID file + process probe.
	if pidData, err := os.ReadFile(p.PidFile); err == nil {
		pid, _ := strconv.Atoi(strings.TrimSpace(string(pidData)))
		if processExists(pid) {
			printWarn(fmt.Sprintf("'%s' is already running (PID: %d).", p.Remote, pid))
			return nil
		}
		os.Remove(p.PidFile) // stale PID file
	}

	// Resolve bind address — fall back to "0.0.0.0" for older profiles.
	bindAddr := p.BindAddr
	if bindAddr == "" {
		bindAddr = "0.0.0.0"
	}

	// #1 — TCP port probe: catch ports held by non-rclone processes (no PID file).
	if isPortListening(":" + p.Port) {
		printError(fmt.Sprintf("Port %s is already in use by another process.", p.Port))
		return fmt.Errorf("port %s in use", p.Port)
	}

	// #6 — verify the log file directory is writable before starting.
	if p.LogFile != "" {
		logDir := filepath.Dir(p.LogFile)
		if err := os.MkdirAll(logDir, 0700); err != nil {
			printError(fmt.Sprintf("Cannot create log directory '%s': %v", logDir, err))
			return err
		}
		// Write a zero-byte test file to confirm write permission.
		testFile := filepath.Join(logDir, ".write_test")
		if err := os.WriteFile(testFile, nil, 0600); err != nil {
			printError(fmt.Sprintf("Log directory '%s' is not writable: %v", logDir, err))
			return err
		}
		os.Remove(testFile)
	}

	// Resolve log level — fall back to "INFO" for older profiles.
	logLevel := p.LogLevel
	if logLevel == "" {
		logLevel = "INFO"
	}

	args := []string{
		"serve", "sftp", p.Remote + ":",
		"--addr", bindAddr + ":" + p.Port,
		"--user", p.User,
		"--pass", p.PassObscured,
		"--vfs-cache-mode", p.VfsCacheMode,
		"--vfs-cache-max-size", p.VfsCacheSize,
		"--vfs-cache-max-age", p.VfsCacheAge,
		"--buffer-size", p.BufferSize,
		"--transfers", strconv.Itoa(p.Transfers),
		"--checkers", strconv.Itoa(p.Checkers),
		"--dir-cache-time", p.DirCache,
		"--poll-interval", p.PollInterval,
	}
	// Optional flags — only add when the profile value is non-empty / true.
	if p.VfsCacheDir != "" {
		args = append(args, "--cache-dir", p.VfsCacheDir)
	}
	if p.VfsCachePollInterval != "" {
		args = append(args, "--vfs-cache-poll-interval", p.VfsCachePollInterval)
	}
	if p.LogFile != "" {
		args = append(args, "--log-file", p.LogFile, "--log-level", logLevel)
	}
	if p.AuthorizedKeys != "" {
		args = append(args, "--authorized-keys", p.AuthorizedKeys)
	}
	if p.UseMmap {
		args = append(args, "--use-mmap")
	}
	if p.NoModtime {
		args = append(args, "--no-modtime")
	}

	cmd := exec.Command("rclone", args...)
	if runtime.GOOS != "windows" {
		cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
	}

	if err := cmd.Start(); err != nil {
		printError(fmt.Sprintf("Failed to start '%s': %v", p.Remote, err))
		return err
	}

	pid := cmd.Process.Pid

	// Reap child to avoid zombie process.
	go func() { _ = cmd.Wait() }()

	// Fix #1 & Fix #2 — os.WriteFile with error check.
	if err := os.WriteFile(p.PidFile, []byte(strconv.Itoa(pid)), 0600); err != nil {
		printError(fmt.Sprintf("Started '%s' (PID %d) but failed to write PID file: %v", p.Remote, pid, err))
		return err
	}

	fmt.Printf("%s🚀 Started%s  %-15s  port %-5s  PID %d\n",
		Green, NC, p.Remote, p.Port, pid)
	return nil
}

// stopServer sends SIGTERM to the process recorded in the PID file and waits
// for it to exit (up to 5 s), then falls back to SIGKILL.
// Fix #3 — verifies the process actually stopped before returning.
func stopServer(p *ConfigProfile) error {
	pidData, err := os.ReadFile(p.PidFile)
	if err != nil {
		printWarn(fmt.Sprintf("'%s' is not running (no PID file).", p.Remote))
		return nil
	}

	pid, err := strconv.Atoi(strings.TrimSpace(string(pidData)))
	if err != nil || pid <= 0 {
		os.Remove(p.PidFile)
		printWarn(fmt.Sprintf("'%s': invalid PID file — removed.", p.Remote))
		return nil
	}

	process, err := os.FindProcess(pid)
	if err != nil {
		os.Remove(p.PidFile)
		return nil
	}

	// Fix #4 — Windows does not support SIGTERM; use os.Process.Kill() instead.
	if runtime.GOOS == "windows" {
		if err := process.Kill(); err != nil {
			printError(fmt.Sprintf("Failed to kill '%s' (PID %d): %v", p.Remote, pid, err))
			return err
		}
	} else {
		if err := process.Signal(syscall.SIGTERM); err != nil {
			// Process may have already exited.
			os.Remove(p.PidFile)
			printWarn(fmt.Sprintf("'%s' (PID %d) already gone.", p.Remote, pid))
			return nil
		}
		// Wait up to 5 s for graceful exit, then SIGKILL.
		if !waitForStop(p.PidFile, 5*time.Second) {
			printWarn(fmt.Sprintf("'%s' (PID %d) did not stop in time — sending SIGKILL.", p.Remote, pid))
			_ = process.Signal(syscall.SIGKILL)
		}
	}

	os.Remove(p.PidFile)
	fmt.Printf("%s⛔ Stopped%s   %-15s  PID %d\n", Red, NC, p.Remote, pid)
	return nil
}

// statusServer prints running/offline status and returns true if running.
func statusServer(p *ConfigProfile) bool {
	pidData, err := os.ReadFile(p.PidFile)
	if err == nil {
		pid, _ := strconv.Atoi(strings.TrimSpace(string(pidData)))
		if processExists(pid) {
			fmt.Printf("%s🟢 %-15s%s  port %-5s  PID %d\n",
				Green, p.Remote, NC, p.Port, pid)
			return true
		}
	}
	fmt.Printf("%s🔴 %-15s%s  port %-5s  offline\n", Red, p.Remote, NC, p.Port)
	return false
}

// ─── Process helpers ──────────────────────────────────────────────────────────

// processExists reports whether a process with the given PID is alive.
// Fix #4 — Windows path uses OpenProcess instead of signal(0).
func processExists(pid int) bool {
	if pid <= 0 {
		return false
	}
	if runtime.GOOS == "windows" {
		// On Windows os.FindProcess always succeeds; exec a lightweight check.
		err := exec.Command("tasklist", "/FI",
			fmt.Sprintf("PID eq %d", pid), "/NH").Run()
		return err == nil
	}
	// Unix: signal 0 checks existence without disturbing the process.
	process, err := os.FindProcess(pid)
	if err != nil {
		return false
	}
	return process.Signal(syscall.Signal(0)) == nil
}

// waitForStop polls the PID file and process liveness until the process exits
// or the timeout elapses. Returns true if the process stopped in time.
// Fix #3 & Fix #8 — used by both stopServer and restart to confirm exit.
func waitForStop(pidFile string, timeout time.Duration) bool {
	deadline := time.Now().Add(timeout)
	for time.Now().Before(deadline) {
		pidData, err := os.ReadFile(pidFile)
		if err != nil {
			return true // PID file gone — process exited
		}
		pid, _ := strconv.Atoi(strings.TrimSpace(string(pidData)))
		if !processExists(pid) {
			return true
		}
		time.Sleep(200 * time.Millisecond)
	}
	return false
}

// isPortListening returns true when something is already bound to addr.
// #1 — catches cases where a process holds the port without a PID file.
func isPortListening(addr string) bool {
	ln, err := net.Listen("tcp", addr)
	if err != nil {
		return true
	}
	ln.Close()
	return false
}
