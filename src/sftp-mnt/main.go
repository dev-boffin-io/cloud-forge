package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"sort"
	"strconv"
	"strings"
	"syscall"
)

// ─── ANSI Colors ───────────────────────────────────────────────────────────────

const (
	Green  = "\033[1;32m"
	Red    = "\033[1;31m"
	Yellow = "\033[1;33m"
	Cyan   = "\033[1;36m"
	NC     = "\033[0m"
)

// ─── Profile ──────────────────────────────────────────────────────────────────
// Subset of rclone_sftp_launcher.go ConfigProfile — only fields needed here.

type ConfigProfile struct {
	Remote         string `json:"remote"`
	Port           string `json:"port"`
	BindAddr       string `json:"bind_addr"`
	User           string `json:"user"`
	PidFile        string `json:"pid_file"`
	AuthorizedKeys string `json:"authorized_keys"`
}

// ─── Print helpers ────────────────────────────────────────────────────────────

func printError(msg string) { fmt.Fprintf(os.Stderr, "%s❌ %s%s\n", Red, msg, NC) }
func printWarn(msg string)  { fmt.Printf("%s⚠️  %s%s\n", Yellow, msg, NC) }
func printInfo(msg string)  { fmt.Printf("%s%s%s\n", Cyan, msg, NC) }

// ─── Main ─────────────────────────────────────────────────────────────────────

func main() {
	home, err := os.UserHomeDir()
	if err != nil {
		printError("Cannot determine home directory: " + err.Error())
		os.Exit(1)
	}

	profileDir := filepath.Join(home, ".rclone_lock", "profiles")
	fmt.Printf("%s🌐 Interactive Multi-SFTP Launcher%s\n", Yellow, NC)
	fmt.Println()

	// ── Load profiles ─────────────────────────────────────────────────────────
	entries, err := os.ReadDir(profileDir)
	if err != nil {
		printError("Profile directory not found: " + profileDir)
		printInfo("Run rclone_sftp_launcher first to create profiles.")
		os.Exit(1)
	}

	var profiles []ConfigProfile
	for _, e := range entries {
		if e.IsDir() || filepath.Ext(e.Name()) != ".json" {
			continue
		}
		p, err := loadProfile(filepath.Join(profileDir, e.Name()))
		if err != nil {
			// #6 — report corrupt profiles instead of silently skipping.
			printWarn(fmt.Sprintf("Skipping '%s': %v", e.Name(), err))
			continue
		}
		if p.Remote != "" {
			profiles = append(profiles, p)
		} else {
			// #4 — specific warn for profiles missing the 'remote' field.
			printWarn(fmt.Sprintf("'%s' has no 'remote' field — skipping.", e.Name()))
		}
	}

	if len(profiles) == 0 {
		printError("No valid profiles found.")
		os.Exit(1)
	}

	// Alphabetical sort for consistent display.
	sort.Slice(profiles, func(i, j int) bool {
		return profiles[i].Remote < profiles[j].Remote
	})

	// ── Display menu ──────────────────────────────────────────────────────────
	fmt.Printf("%sAvailable SFTP servers:%s\n", Green, NC)
	for i, p := range profiles {
		status := fmt.Sprintf("%s● offline%s", Red, NC)
		if isServerRunning(p.PidFile) {
			status = fmt.Sprintf("%s● running%s", Green, NC)
		}
		fmt.Printf("  [%2d] %-18s  port %-5s  %s\n", i+1, p.Remote, p.Port, status)
	}
	fmt.Println()

	// ── User selection ────────────────────────────────────────────────────────
	// #3 — bufio.Reader instead of fmt.Scanln to handle spaces in input.
	fmt.Printf("%sSelect profiles to open (e.g. 1,3,5 or 'all'): %s", Green, NC)
	reader := bufio.NewReader(os.Stdin)
	rawInput, err := reader.ReadString('\n')
	if err != nil {
		printError("Failed to read input: " + err.Error())
		os.Exit(1)
	}
	input := strings.TrimSpace(rawInput)

	if input == "" {
		printWarn("No selection made. Exiting.")
		return
	}

	// Build list of selected indices.
	var selected []int
	if strings.ToLower(input) == "all" {
		for i := range profiles {
			selected = append(selected, i)
		}
	} else {
		for _, tok := range strings.Split(input, ",") {
			tok = strings.TrimSpace(tok)
			idx, err := strconv.Atoi(tok)
			if err != nil || idx < 1 || idx > len(profiles) {
				printWarn(fmt.Sprintf("Invalid choice '%s' — skipping.", tok))
				continue
			}
			selected = append(selected, idx-1)
		}
	}

	// #2 — deduplicate: "1,1,3" should open 1 and 3, not 1 twice.
	seen := make(map[int]bool)
	uniq := selected[:0]
	for _, idx := range selected {
		if !seen[idx] {
			seen[idx] = true
			uniq = append(uniq, idx)
		}
	}
	selected = uniq

	if len(selected) == 0 {
		printError("No valid selections. Exiting.")
		os.Exit(1)
	}

	// Confirm selection so the user can verify before opening.
	fmt.Printf("%sSelected:%s ", Green, NC)
	for j, idx := range selected {
		if j > 0 {
			fmt.Print(", ")
		}
		fmt.Printf("%s%s%s", Cyan, profiles[idx].Remote, NC)
	}
	fmt.Println()
	fmt.Println()

	// ── Open selected servers ─────────────────────────────────────────────────
	opened, skippedOffline := 0, 0
	for _, i := range selected {
		p := profiles[i]

		if !isServerRunning(p.PidFile) {
			// #1 — distinguish "not running" from "already open" in messaging.
			printWarn(fmt.Sprintf("'%s' is not running — skipping.", p.Remote))
			skippedOffline++
			continue
		}

		// #5 — use BindAddr from profile; fall back to localhost for older profiles.
		host := p.BindAddr
		if host == "" || host == "0.0.0.0" {
			host = "localhost"
		}

		sftpURL := fmt.Sprintf("sftp://%s@%s:%s/", p.User, host, p.Port)
		printInfo(fmt.Sprintf("Opening: %s", sftpURL))

		if p.AuthorizedKeys != "" {
			fmt.Printf("%s🔑 Key-based auth detected.%s\n", Green, NC)
		} else {
			fmt.Printf("%s🔐 Password auth — your file manager may prompt for a password.%s\n", Yellow, NC)
		}

		// #7 — report openURL failures to the user.
		if err := openURL(sftpURL); err != nil {
			printError(fmt.Sprintf("Failed to open '%s': %v", sftpURL, err))
			// #5 — show the URL so the user can open it manually.
			fmt.Printf("%s💡 Try manually: %s%s\n", Yellow, sftpURL, NC)
			continue
		}
		opened++
	}

	fmt.Println()
	if opened > 0 {
		fmt.Printf("%s✅ Opened %d connection(s).%s\n", Green, opened, NC)
	}
	// #3 — specific message when every selected server was offline.
	if skippedOffline > 0 && opened == 0 {
		printWarn("None of the selected servers are running. Start them with: sftp-controller start <name>")
	} else if opened == 0 {
		printWarn("No connections were opened.")
	}
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

// loadProfile reads and unmarshals a JSON profile file.
func loadProfile(path string) (ConfigProfile, error) {
	var p ConfigProfile
	data, err := os.ReadFile(path)
	if err != nil {
		return p, err
	}
	if err := json.Unmarshal(data, &p); err != nil {
		return p, fmt.Errorf("JSON parse error: %w", err)
	}
	return p, nil
}

// isServerRunning returns true if the PID recorded in pidFile is alive.
// #1 fix — syscall import added.
// #2 fix — no double cast; syscall.Signal already implements os.Signal.
// #4 fix — Windows uses tasklist instead of signal(0).
func isServerRunning(pidFile string) bool {
	data, err := os.ReadFile(pidFile)
	if err != nil {
		return false
	}
	pid, err := strconv.Atoi(strings.TrimSpace(string(data)))
	if err != nil || pid <= 0 {
		return false
	}

	if runtime.GOOS == "windows" {
		// signal(0) is unsupported on Windows — use tasklist to probe.
		out, err := exec.Command("tasklist", "/FI",
			fmt.Sprintf("PID eq %d", pid), "/NH").Output()
		if err != nil {
			return false
		}
		return strings.Contains(string(out), strconv.Itoa(pid))
	}

	// Unix: signal 0 checks liveness without disturbing the process.
	process, err := os.FindProcess(pid)
	if err != nil {
		return false
	}
	return process.Signal(syscall.Signal(0)) == nil
}

// openURL opens a URL with the platform's default handler.
// #7 — returns an error so callers can report failures.
func openURL(url string) error {
    var cmd *exec.Cmd

    switch runtime.GOOS {
    case "linux":
        cmd = exec.Command("xdg-open", url)
    case "darwin":
        cmd = exec.Command("open", url)
    case "windows":
        cmd = exec.Command("rundll32", "url.dll,FileProtocolHandler", url)
    default:
        return fmt.Errorf("unsupported platform: %s", runtime.GOOS)
    }

    cmd.Stdout = os.Stdout
    cmd.Stderr = os.Stderr

    if err := cmd.Start(); err != nil {
        return err
    }

    go cmd.Wait()
    return nil
}
