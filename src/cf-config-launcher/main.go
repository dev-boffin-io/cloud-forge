package main

import (
	"fmt"
	"os"
	"os/exec"
	"runtime"
	"strings"
)

// buildRcloneArgs converts cf-config-launcher arguments to a rclone command.
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

// findLinuxTerminal returns (termPath, launchFunc) where launchFunc(cmdStr)
// produces the full argument list to exec. Every terminal uses "bash -c CMD"
// so that multi-word commands are passed correctly regardless of terminal.
func findLinuxTerminal() (string, func(string) []string) {
	type termDef struct {
		name    string
		mkArgs  func(cmdStr string) []string
	}

	terms := []termDef{
		// Each terminal opens bash -c "<cmd>; exec bash" so the window stays
		// open and the user can read output / interact with prompts.
		{"xfce4-terminal", func(c string) []string {
			return []string{"-e", "bash -c " + shellQuote(c+"; exec bash")}
		}},
		{"xterm", func(c string) []string {
			return []string{"-e", "bash", "-c", c + "; exec bash"}
		}},
		{"gnome-terminal", func(c string) []string {
			return []string{"--", "bash", "-c", c + "; exec bash"}
		}},
		{"konsole", func(c string) []string {
			return []string{"-e", "bash", "-c", c + "; exec bash"}
		}},
		{"mate-terminal", func(c string) []string {
			return []string{"-e", "bash -c " + shellQuote(c+"; exec bash")}
		}},
		{"lxterminal", func(c string) []string {
			return []string{"-e", "bash -c " + shellQuote(c+"; exec bash")}
		}},
		{"alacritty", func(c string) []string {
			return []string{"-e", "bash", "-c", c + "; exec bash"}
		}},
		{"kitty", func(c string) []string {
			return []string{"-e", "bash", "-c", c + "; exec bash"}
		}},
		{"x-terminal-emulator", func(c string) []string {
			return []string{"-e", "bash", "-c", c + "; exec bash"}
		}},
	}

	for _, t := range terms {
		if path, err := exec.LookPath(t.name); err == nil {
			name := t.name
			mk := t.mkArgs
			_ = name
			return path, mk
		}
	}
	return "", nil
}

// shellQuote wraps s in single quotes, escaping any single quotes inside.
func shellQuote(s string) string {
	return "'" + strings.ReplaceAll(s, "'", "'\\''") + "'"
}

// shellEscapeArgs joins args into a shell-safe command string.
// Each argument is individually single-quoted so spaces and special
// characters in remote names or paths are handled correctly.
func shellEscapeArgs(args []string) string {
	quoted := make([]string, len(args))
	for i, a := range args {
		quoted[i] = shellQuote(a)
	}
	return strings.Join(quoted, " ")
}

func main() {
	if _, err := exec.LookPath("rclone"); err != nil {
		fmt.Fprintln(os.Stderr, "❌ rclone not found in PATH")
		os.Exit(1)
	}

	rcloneArgs := buildRcloneArgs()
	cmdStr := shellEscapeArgs(rcloneArgs)

	var cmd *exec.Cmd

	switch runtime.GOOS {

	case "linux":
		termPath, mkArgs := findLinuxTerminal()
		if termPath != "" {
			termArgs := mkArgs(cmdStr)
			cmd = exec.Command(termPath, termArgs...)
			fmt.Printf("🚀 Launching via %s: %s\n", termPath, cmdStr)
		} else {
			// No terminal found — run directly (PRoot / headless)
			fmt.Fprintln(os.Stderr, "⚠ No terminal found, running directly...")
			cmd = exec.Command(rcloneArgs[0], rcloneArgs[1:]...)
			cmd.Stdin = os.Stdin
			cmd.Stdout = os.Stdout
			cmd.Stderr = os.Stderr
		}

	case "darwin":
		script := fmt.Sprintf(`tell application "Terminal"
	do script %s
	activate
end tell`, shellQuote(cmdStr))
		cmd = exec.Command("osascript", "-e", script)
		fmt.Println("🚀 Opening Terminal.app...")

	case "windows":
		if _, err := exec.LookPath("powershell"); err == nil {
			cmd = exec.Command("powershell", "-NoExit", "-Command",
				cmdStr+`; Read-Host 'Press Enter to exit'`)
			fmt.Println("🚀 Opening PowerShell...")
		} else {
			cmd = exec.Command("cmd", "/K", cmdStr)
			fmt.Println("🚀 Opening CMD...")
		}

	default:
		fmt.Fprintln(os.Stderr, "❌ Unsupported OS")
		os.Exit(1)
	}

	if err := cmd.Start(); err != nil {
		fmt.Fprintln(os.Stderr, "❌ Failed to launch:", err)
		os.Exit(1)
	}

	fmt.Println("✅ Launched:", cmdStr)
}
