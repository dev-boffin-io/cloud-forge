package main

import (
	"fmt"
	"os"
	"os/exec"
	"runtime"
	"strings"
)

// ------------------------------
// Helper: detect terminal name safely
// ------------------------------
func isGnomeTerminal(path string) bool {
	return strings.Contains(path, "gnome-terminal")
}

// ------------------------------
// Shell escape for safe shell interpolation
// ------------------------------
func shellEscape(args []string) string {
	var escaped []string
	for _, a := range args {
		escaped = append(escaped, fmt.Sprintf("%q", a))
	}
	return strings.Join(escaped, " ")
}

// ------------------------------
// Terminal Detection (Linux)
// ------------------------------
func findLinuxTerminal() (string, []string) {
	terms := []struct {
		name string
		args []string
	}{
		{"x-terminal-emulator", []string{"-e"}},
		{"gnome-terminal", []string{"--", "bash", "-c"}},
		{"konsole", []string{"-e"}},
		{"xfce4-terminal", []string{"-e"}},
		{"mate-terminal", []string{"-e"}},
		{"lxterminal", []string{"-e"}},
		{"alacritty", []string{"-e"}},
		{"kitty", []string{"-e"}},
		{"xterm", []string{"-e"}},
	}

	for _, t := range terms {
		if path, err := exec.LookPath(t.name); err == nil {
			return path, t.args
		}
	}
	return "", nil
}

// ------------------------------
// Build the rclone command to run
// ------------------------------
// Usage:
//
//	cf-config-launcher                  → rclone config
//	cf-config-launcher reconnect NAME   → rclone config reconnect NAME:
func buildRcloneArgs() []string {
	args := os.Args[1:]
	if len(args) == 0 {
		return []string{"rclone", "config"}
	}
	switch args[0] {
	case "reconnect":
		name := ""
		if len(args) >= 2 {
			name = strings.TrimSuffix(args[1], ":") + ":"
		}
		return []string{"rclone", "config", "reconnect", name}
	default:
		return append([]string{"rclone"}, args...)
	}
}

// ------------------------------
// Main Launcher
// ------------------------------
func main() {

	// Check rclone exists
	if _, err := exec.LookPath("rclone"); err != nil {
		fmt.Println("❌ rclone not found in PATH")
		os.Exit(1)
	}

	rcloneArgs := buildRcloneArgs()

	// ✅ FIX 1: shell-escaped string — safe against injection
	cmdStr := shellEscape(rcloneArgs)

	var cmd *exec.Cmd

	switch runtime.GOOS {

	// ---------------- LINUX ----------------
	case "linux":
		term, args := findLinuxTerminal()

		if term != "" {
			var cmdArgs []string
			if isGnomeTerminal(term) {
				cmdArgs = append(args, cmdStr+"; exec bash")
			} else {
				cmdArgs = append(args, rcloneArgs...)
			}
			cmd = exec.Command(term, cmdArgs...)
			fmt.Printf("🚀 Launching via %s: %s\n", term, cmdStr)
		} else {
			fmt.Println("⚠ No terminal found, running directly...")
			cmd = exec.Command(rcloneArgs[0], rcloneArgs[1:]...)
			cmd.Stdin = os.Stdin
			cmd.Stdout = os.Stdout
			cmd.Stderr = os.Stderr
		}

	// ---------------- macOS ----------------
	case "darwin":
		// ✅ FIX 2: AppleScript-safe quoting — escape \, " and $
		safeCmd := cmdStr
		safeCmd = strings.ReplaceAll(safeCmd, `\`, `\\`)
		safeCmd = strings.ReplaceAll(safeCmd, `"`, `\"`)
		safeCmd = strings.ReplaceAll(safeCmd, `$`, `\$`)

		script := fmt.Sprintf(`tell application "Terminal"
	do script "%s"
	activate
end tell`, safeCmd)
		cmd = exec.Command("osascript", "-e", script)
		fmt.Println("🚀 Opening Terminal.app...")

	// ---------------- WINDOWS ----------------
	case "windows":
		if _, err := exec.LookPath("powershell"); err == nil {
			cmd = exec.Command("powershell", "-NoExit", "-Command",
				cmdStr+`; Read-Host 'Press Enter to exit'`)
			fmt.Println("🚀 Opening PowerShell...")
		} else {
			cmd = exec.Command("cmd", "/K", cmdStr)
			fmt.Println("🚀 Opening CMD...")
		}

	// ---------------- UNKNOWN ----------------
	default:
		fmt.Println("❌ Unsupported OS")
		os.Exit(1)
	}

	err := cmd.Start()
	if err != nil {
		fmt.Println("❌ Failed to launch:", err)
		os.Exit(1)
	}

	fmt.Println("✅ Launched:", cmdStr)
}
