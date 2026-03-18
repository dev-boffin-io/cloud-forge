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
// Terminal Detection (Linux)
// ------------------------------
func findLinuxTerminal() (string, []string) {
	terms := []struct {
		name string
		args []string
	}{
		{"x-terminal-emulator", []string{"-e"}},
		{"gnome-terminal", []string{"--", "bash", "-c"}}, // proper handling
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
// Main Launcher
// ------------------------------
func main() {

	// ✅ Check rclone exists
	if _, err := exec.LookPath("rclone"); err != nil {
		fmt.Println("❌ rclone not found in PATH")
		os.Exit(1)
	}

	var cmd *exec.Cmd

	switch runtime.GOOS {

	// ---------------- LINUX ----------------
	case "linux":
		term, args := findLinuxTerminal()

		if term != "" {

			var cmdArgs []string

			// ✅ safer gnome-terminal detection
			if isGnomeTerminal(term) {
				cmdArgs = append(args, "rclone config; exec bash")
			} else {
				cmdArgs = append(args, "rclone", "config")
			}

			cmd = exec.Command(term, cmdArgs...)
			fmt.Printf("🚀 Launching via %s...\n", term)

		} else {
			fmt.Println("⚠ No terminal found, running directly...")
			cmd = exec.Command("rclone", "config")
			cmd.Stdin = os.Stdin
			cmd.Stdout = os.Stdout
			cmd.Stderr = os.Stderr
		}

	// ---------------- macOS ----------------
	case "darwin":
		script := `tell application "Terminal"
	do script "rclone config"
	activate
end tell`
		cmd = exec.Command("osascript", "-e", script)
		fmt.Println("🚀 Opening Terminal.app...")

	// ---------------- WINDOWS ----------------
	case "windows":
		if _, err := exec.LookPath("powershell"); err == nil {
			cmd = exec.Command("powershell", "-NoExit", "-Command", "rclone config; Read-Host 'Press Enter to exit'")
			fmt.Println("🚀 Opening PowerShell...")
		} else {
			cmd = exec.Command("cmd", "/K", "rclone config")
			fmt.Println("🚀 Opening CMD...")
		}

	// ---------------- UNKNOWN ----------------
	default:
		fmt.Println("❌ Unsupported OS")
		os.Exit(1)
	}

	// ---------------- Run ----------------
	err := cmd.Start()
	if err != nil {
		fmt.Println("❌ Failed to launch:", err)
		os.Exit(1)
	}

	fmt.Println("✅ rclone config launched successfully")
}
