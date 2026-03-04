package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"net"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"syscall"

	"golang.org/x/term"
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

type ConfigProfile struct {
	Remote         string `json:"remote"`
	Port           string `json:"port"`
	BindAddr       string `json:"bind_addr"`
	User           string `json:"user"`
	PassObscured   string `json:"pass_obscured"`
	PidFile        string `json:"pid_file"`
	BufferSize     string `json:"buffer_size"`
	Transfers      int    `json:"transfers"`
	Checkers       int    `json:"checkers"`
	VfsCacheMode   string `json:"vfs_cache_mode"`
	VfsCacheSize   string `json:"vfs_cache_size"`
	VfsCacheAge    string `json:"vfs_cache_age"`
	VfsCacheDir    string `json:"vfs_cache_dir"`
	DirCache       string `json:"dir_cache"`
	PollInterval          string `json:"poll_interval"`
	VfsCachePollInterval  string `json:"vfs_cache_poll_interval"`
	LogFile        string `json:"log_file"`
	LogLevel       string `json:"log_level"`
	AuthorizedKeys string `json:"authorized_keys"`
}

// ─── Print helpers ────────────────────────────────────────────────────────────

func printError(msg string) { fmt.Fprintf(os.Stderr, "%s❌ %s%s\n", Red, msg, NC) }
func printWarn(msg string)  { fmt.Printf("%s⚠️  %s%s\n", Yellow, msg, NC) }
func printOK(msg string)    { fmt.Printf("%s✅ %s%s\n", Green, msg, NC) }
func printInfo(msg string)  { fmt.Printf("%s%s%s\n", Cyan, msg, NC) }

// ─── Input helpers ────────────────────────────────────────────────────────────

// inputDefault prints label and returns user input, or def if input is empty.
func inputDefault(reader *bufio.Reader, label, def string) string {
	fmt.Print(label)
	line, err := reader.ReadString('\n')
	if err != nil {
		return def
	}
	line = strings.TrimSpace(line)
	if line == "" {
		return def
	}
	return line
}

// readPassword reads a password without echoing it.
// Falls back to plain readline for non-TTY contexts (scripts, pipes).
func readPassword(label string) (string, error) {
	fmt.Print(label)
	if term.IsTerminal(int(os.Stdin.Fd())) {
		pw, err := term.ReadPassword(int(os.Stdin.Fd()))
		fmt.Println()
		if err != nil {
			return "", fmt.Errorf("reading password: %w", err)
		}
		return strings.TrimSpace(string(pw)), nil
	}
	reader := bufio.NewReader(os.Stdin)
	line, err := reader.ReadString('\n')
	if err != nil {
		return "", fmt.Errorf("reading password: %w", err)
	}
	return strings.TrimSpace(line), nil
}

// readInt prompts for an integer, validates range, returns default on empty input.
func readInt(reader *bufio.Reader, label string, def, min, max int) (int, error) {
	raw := inputDefault(reader, label, strconv.Itoa(def))
	v, err := strconv.Atoi(raw)
	if err != nil {
		return 0, fmt.Errorf("'%s' is not a valid integer", raw)
	}
	if v < min || v > max {
		return 0, fmt.Errorf("%d is out of range [%d, %d]", v, min, max)
	}
	return v, nil
}

// ensureSuffix appends suffix when s is a bare integer (e.g. "30" -> "30s").
func ensureSuffix(s, suffix string) string {
	if _, err := strconv.Atoi(s); err == nil {
		return s + suffix
	}
	return s
}

// ─── rclone helpers ───────────────────────────────────────────────────────────

// remoteExists does an exact line match against `rclone listremotes` output.
func remoteExists(name string) (bool, error) {
	out, err := exec.Command("rclone", "listremotes").Output()
	if err != nil {
		return false, fmt.Errorf("rclone listremotes failed: %w", err)
	}
	for _, line := range strings.Split(strings.TrimSpace(string(out)), "\n") {
		if strings.TrimSuffix(strings.TrimSpace(line), ":") == name {
			return true, nil
		}
	}
	return false, nil
}

// isPortListening returns true when something is already bound to addr.
// #7 — catches stale PID files where the process died but the file remains.
func isPortListening(addr string) bool {
	ln, err := net.Listen("tcp", addr)
	if err != nil {
		return true
	}
	ln.Close()
	return false
}

// stopCommand returns the platform-appropriate stop instruction string.
// #8 — Windows uses taskkill; Unix uses kill.
func stopCommand(pid int, pidFile string) string {
	if runtime.GOOS == "windows" {
		return fmt.Sprintf("taskkill /PID %d /F  &&  del %s", pid, pidFile)
	}
	return fmt.Sprintf("kill %d && rm %s", pid, pidFile)
}

// ─── Main ─────────────────────────────────────────────────────────────────────

func main() {
	reader := bufio.NewReader(os.Stdin)

	home, err := os.UserHomeDir()
	if err != nil {
		printError("Cannot determine home directory: " + err.Error())
		os.Exit(1)
	}
	lockDir := filepath.Join(home, ".rclone_lock")
	profileDir := filepath.Join(lockDir, "profiles")
	if err := os.MkdirAll(profileDir, 0700); err != nil {
		printError("Cannot create lock/profile directory: " + err.Error())
		os.Exit(1)
	}

	fmt.Printf("%s🌩️  Rclone SFTP Server Launcher%s\n", Cyan, NC)
	fmt.Println("═══════════════════════════════════")
	fmt.Println()


	// ── rclone version + serve sftp support check ───────────────────────────
	// Ensures rclone is present and new enough to support "serve sftp".
	verOut, verErr := exec.Command("rclone", "version").Output()
	if verErr != nil || !strings.Contains(string(verOut), "rclone v") {
		printError("rclone not found or returned unexpected output. Is it installed correctly?")
		os.Exit(1)
	}
	helpOut, _ := exec.Command("rclone", "serve", "sftp", "--help").Output()
	if strings.Contains(string(helpOut), "unknown command") || len(helpOut) == 0 {
		printError("Your rclone version does not support 'serve sftp'. Please update rclone.")
		os.Exit(1)
	}
	printOK("rclone supports 'serve sftp'.")
	fmt.Println()

	// ── Performance tuning ────────────────────────────────────────────────────
	fmt.Printf("%s── Performance ──%s\n", Magenta, NC)

	bufferSize := inputDefault(reader, "Buffer size                  [128M]: ", "128M")
	vfsCacheSize := inputDefault(reader, "VFS cache max size            [5G] : ", "5G")
	vfsCacheAge := inputDefault(reader, "VFS cache max age            [10h] : ", "10h")
	dirCache := inputDefault(reader, "Dir cache time               [12h] : ", "12h")

	// #3 — custom VFS cache dir prevents $HOME from filling up.
	defaultCacheDir := filepath.Join(home, ".cache", "rclone")
	vfsCacheDir := inputDefault(reader,
		fmt.Sprintf("VFS cache dir        [%s]: ", defaultCacheDir),
		defaultCacheDir,
	)

	// #1 — warn on problematic cache modes.
	vfsCacheMode := inputDefault(reader,
		"VFS cache mode (off/minimal/writes/full) [writes]: ", "writes")
	switch strings.ToLower(vfsCacheMode) {
	case "off":
		printWarn("Cache mode 'off' disables VFS caching. Writes may fail on some remotes.")
	case "full":
		printWarn("Cache mode 'full' uses significant disk space and I/O.")
	case "minimal", "writes":
		// fine
	default:
		printWarn(fmt.Sprintf("Unknown cache mode '%s'. Valid: off/minimal/writes/full.", vfsCacheMode))
	}

	transfers, err := readInt(reader, "Transfers                      [4]  : ", 4, 1, 64)
	if err != nil {
		printError("Transfers: " + err.Error())
		os.Exit(1)
	}
	checkers, err := readInt(reader, "Checkers                       [8]  : ", 8, 1, 64)
	if err != nil {
		printError("Checkers: " + err.Error())
		os.Exit(1)
	}

	pollRaw := inputDefault(reader, "Poll interval                 [30s] : ", "30s")
	pollInterval := ensureSuffix(pollRaw, "s")

	// VFS cache poll interval — how often rclone checks for stale cache entries.
	pollCacheRaw := inputDefault(reader, "VFS cache poll interval        [1m] : ", "1m")
	pollCacheInterval := ensureSuffix(pollCacheRaw, "s")

	// #6 — configurable log level.
	logLevel := strings.ToUpper(inputDefault(reader,
		"Log level (ERROR/INFO/DEBUG)  [INFO] : ", "INFO"))
	switch logLevel {
	case "ERROR", "INFO", "DEBUG":
		// valid
	default:
		printWarn(fmt.Sprintf("Unknown log level '%s', defaulting to INFO.", logLevel))
		logLevel = "INFO"
	}

	fmt.Println()

	// ── Remote ────────────────────────────────────────────────────────────────
	fmt.Printf("%s── Remote ──%s\n", Magenta, NC)
	fmt.Print("Remote name: ")
	remote, _ := reader.ReadString('\n')
	remote = strings.TrimSpace(remote)
	if remote == "" {
		printError("No remote entered. Exiting.")
		os.Exit(1)
	}

	exists, err := remoteExists(remote)
	if err != nil {
		printError(err.Error())
		os.Exit(1)
	}
	if !exists {
		printError(fmt.Sprintf("Remote '%s' not found. Configure it with: rclone config", remote))
		os.Exit(1)
	}
	fmt.Println()

	// ── Network ───────────────────────────────────────────────────────────────
	fmt.Printf("%s── Network ──%s\n", Magenta, NC)

	// #2 — configurable bind address with validation.
	// Reject input that looks like a port number (pure digits) — a common
	// mistake when the user enters the port into the bind address field.
	bindAddr := inputDefault(reader,
		"Bind address (0.0.0.0=all interfaces, 127.0.0.1=local only) [0.0.0.0]: ",
		"0.0.0.0",
	)
	if _, numErr := strconv.Atoi(bindAddr); numErr == nil {
		printError(fmt.Sprintf(
			"'%s' looks like a port number, not an IP address. Leave blank for default (0.0.0.0).",
			bindAddr,
		))
		os.Exit(1)
	}
	if bindAddr == "0.0.0.0" {
		printWarn("Binding to 0.0.0.0 exposes the server on all interfaces. Ensure your firewall is configured.")
	}

	portStr := inputDefault(reader, "Port (1024-65535): ", "")
	if portStr == "" {
		printError("Port is required.")
		os.Exit(1)
	}
	portInt, err := strconv.Atoi(portStr)
	if err != nil || portInt < 1024 || portInt > 65535 {
		printError("Invalid port. Must be an integer between 1024 and 65535.")
		os.Exit(1)
	}

	listenAddr := bindAddr + ":" + portStr
	pidFile := filepath.Join(lockDir, portStr+".pid")
	logFile := filepath.Join(lockDir, remote+"-"+portStr+".log")
	profileFile := filepath.Join(profileDir, remote+".json")

	// #7 — dual check: PID file + actual TCP port probe.
	if _, statErr := os.Stat(pidFile); statErr == nil {
		// PID file found — check if the port is actually busy.
		if isPortListening(":" + portStr) {
			printError(fmt.Sprintf("Port %s is already in use. Exiting.", portStr))
			os.Exit(1)
		}
		// Port is free — PID file is stale; remove it and continue.
		printWarn("PID file is stale (process no longer running). Removing and continuing.")
		os.Remove(pidFile)
	} else if isPortListening(":" + portStr) {
		// No PID file but port is busy (another process).
		printError(fmt.Sprintf("Port %s is already in use by another process. Exiting.", portStr))
		os.Exit(1)
	}
	fmt.Println()

	// ── Credentials ───────────────────────────────────────────────────────────
	fmt.Printf("%s── Credentials ──%s\n", Magenta, NC)
	fmt.Print("Username: ")
	username, _ := reader.ReadString('\n')
	username = strings.TrimSpace(username)

	password, err := readPassword("Password: ")
	if err != nil {
		printError(err.Error())
		os.Exit(1)
	}
	if username == "" || password == "" {
		printError("Username and password are required.")
		os.Exit(1)
	}

	obscRaw, err := exec.Command("rclone", "obscure", password).Output()
	if err != nil {
		printError("Failed to obscure password: " + err.Error())
		os.Exit(1)
	}
	obscPass := strings.TrimSpace(string(obscRaw))
	fmt.Println()

	// ── Authorized keys (optional) ────────────────────────────────────────────
	authChoice := inputDefault(reader, "Use authorized_keys? (y/N): ", "n")
	authKeys := ""
	authKeyFlag := ""
	if strings.ToLower(authChoice) == "y" {
		// #5 — custom path instead of hardcoded ~/.ssh/authorized_keys.
		defaultKeyPath := filepath.Join(home, ".ssh", "authorized_keys")
		authKeys = inputDefault(reader,
			fmt.Sprintf("authorized_keys path [%s]: ", defaultKeyPath),
			defaultKeyPath,
		)
		if _, err := os.Stat(authKeys); err != nil {
			printWarn(fmt.Sprintf("authorized_keys not found at '%s' — skipping.", authKeys))
			authKeys = ""
		} else {
			authKeyFlag = "--authorized-keys"
		}
	}
	fmt.Println()

// ── Build and start rclone ────────────────────────────────────────────────
	fmt.Printf("%s🚀 Starting SFTP server '%s' on %s …%s\n", Green, remote, listenAddr, NC)

	args := []string{
		"serve", "sftp", remote + ":",
		"--addr", listenAddr,
		"--user", username,
		"--pass", password, // ✅ FIXED
		"--vfs-cache-mode", vfsCacheMode,
		"--vfs-cache-max-size", vfsCacheSize,
		"--vfs-cache-max-age", vfsCacheAge,
		"--cache-dir", vfsCacheDir,
		"--buffer-size", bufferSize,
		"--transfers", strconv.Itoa(transfers),
		"--checkers", strconv.Itoa(checkers),
		"--dir-cache-time", dirCache,
		"--poll-interval", pollInterval,
		"--vfs-cache-poll-interval", pollCacheInterval,
		"--log-file", logFile,
		"--log-level", logLevel,
	}

	if authKeyFlag != "" {
		args = append(args, authKeyFlag, authKeys)
	}

	cmd := exec.Command("rclone", args...)

	// Detach from current process group (Unix nohup equivalent).
	// #8 — SysProcAttr is Unix-only; Windows fallback noted in stop command.
	if runtime.GOOS != "windows" {
		cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
	}

	if err := cmd.Start(); err != nil {
		printError("Failed to start server: " + err.Error())
		os.Exit(1)
	}

	pid := cmd.Process.Pid

	// Reap child in background to avoid zombie process.
	go func() { _ = cmd.Wait() }()

	if err := os.WriteFile(pidFile, []byte(strconv.Itoa(pid)), 0600); err != nil {
		printError("Failed to write PID file: " + err.Error())
		// Server is running — warn but do not kill it.
	}

	printOK(fmt.Sprintf("'%s' running on %s (PID: %d).", remote, listenAddr, pid))
	printInfo(fmt.Sprintf("📄 Log    : %s", logFile))
	printInfo(fmt.Sprintf("💽 Cache  : %s", vfsCacheDir))
	printInfo(fmt.Sprintf("🛑 Stop   : %s", stopCommand(pid, pidFile))) // #8
	fmt.Println()

	// ── Save profile ──────────────────────────────────────────────────────────
	profile := ConfigProfile{
		Remote:         remote,
		Port:           portStr,
		BindAddr:       bindAddr,
		User:           username,
		PassObscured:   obscPass,
		PidFile:        pidFile,
		BufferSize:     bufferSize,
		Transfers:      transfers,
		Checkers:       checkers,
		VfsCacheMode:   vfsCacheMode,
		VfsCacheSize:   vfsCacheSize,
		VfsCacheAge:    vfsCacheAge,
		VfsCacheDir:    vfsCacheDir,
		DirCache:       dirCache,
		PollInterval:          pollInterval,
		VfsCachePollInterval:  pollCacheInterval,
		LogFile:        logFile,
		LogLevel:       logLevel,
		AuthorizedKeys: authKeys,
	}

	profileData, err := json.MarshalIndent(profile, "", "  ")
	if err != nil {
		printError("Failed to marshal profile: " + err.Error())
		return
	}
	if err := os.WriteFile(profileFile, profileData, 0600); err != nil {
		printError("Failed to save profile: " + err.Error())
		return
	}
	printInfo(fmt.Sprintf("💾 Profile: %s", profileFile))
}
