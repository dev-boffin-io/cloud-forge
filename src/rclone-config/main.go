package main

import (
	"bufio"
	"fmt"
	"os"
	"os/exec"
	"runtime"
	"strings"
)

// ─── ANSI Colors ───────────────────────────────────────────────────────────────

const (
	Red    = "\033[0;31m"
	Green  = "\033[0;32m"
	Yellow = "\033[1;33m"
	Blue   = "\033[0;34m"
	Purple = "\033[0;35m"
	Cyan   = "\033[0;36m"
	Bold   = "\033[1m"
	NC     = "\033[0m"
)

// ─── Print helpers ────────────────────────────────────────────────────────────

func printError(msg string) {
	fmt.Fprintf(os.Stderr, "%s❌ %s%s\n", Red, msg, NC)
}

func printSuccess(msg string) {
	fmt.Printf("%s✅ %s%s\n", Green, msg, NC)
}

func printInfo(msg string) {
	fmt.Printf("%sℹ️  %s%s\n", Cyan, msg, NC)
}

func printWarn(msg string) {
	fmt.Printf("%s⚠️  %s%s\n", Yellow, msg, NC)
}

// ─── Terminal helpers ─────────────────────────────────────────────────────────

func clearScreen() {
	var cmd *exec.Cmd
	if runtime.GOOS == "windows" {
		cmd = exec.Command("cmd", "/c", "cls")
	} else {
		cmd = exec.Command("clear")
	}
	cmd.Stdout = os.Stdout
	if err := cmd.Run(); err != nil {
		fmt.Println() // non-fatal fallback
	}
}

// prompt prints label, reads a line, and returns the trimmed result.
func prompt(reader *bufio.Reader, label string) (string, error) {
	fmt.Print(label)
	line, err := reader.ReadString('\n')
	if err != nil {
		return "", fmt.Errorf("failed to read input: %w", err)
	}
	return strings.TrimSpace(line), nil
}

// ─── rclone helpers ───────────────────────────────────────────────────────────

// checkRclone verifies rclone is on PATH.
// We do NOT auto-install: piping curl into bash is a security anti-pattern.
func checkRclone() error {
	_, err := exec.LookPath("rclone")
	if err != nil {
		return fmt.Errorf(
			"rclone not found in PATH\n" +
				"  Install from : https://rclone.org/downloads/\n" +
				"  Linux/macOS  : sudo -v && curl https://rclone.org/install.sh | sudo bash",
		)
	}
	return nil
}

// listRemoteNames returns configured remote names without the trailing colon.
func listRemoteNames() ([]string, error) {
	out, err := exec.Command("rclone", "listremotes").Output()
	if err != nil {
		return nil, fmt.Errorf("rclone listremotes failed: %w", err)
	}
	raw := strings.TrimSpace(string(out))
	if raw == "" {
		return []string{}, nil
	}
	lines := strings.Split(raw, "\n")
	names := make([]string, 0, len(lines))
	for _, l := range lines {
		l = strings.TrimSpace(l)
		if l != "" {
			names = append(names, strings.TrimSuffix(l, ":"))
		}
	}
	return names, nil
}

// printRemoteList prints the slice of remote names to stdout.
func printRemoteList(names []string) {
	fmt.Printf("%s%s📁 Configured remotes:%s\n", Bold, Blue, NC)
	for _, n := range names {
		fmt.Printf("  • %s\n", n)
	}
	fmt.Println()
}

// remoteExists checks whether name exists.
// #4 — rclone is case-sensitive; we warn if only a differently-cased match
// is found rather than silently returning false.
func remoteExists(name string) (bool, error) {
	names, err := listRemoteNames()
	if err != nil {
		return false, err
	}
	lower := strings.ToLower(name)
	for _, n := range names {
		if n == name {
			return true, nil
		}
		if strings.ToLower(n) == lower {
			printWarn(fmt.Sprintf(
				"Found '%s' but you typed '%s'. rclone is case-sensitive.", n, name,
			))
		}
	}
	return false, nil
}

// validateRemoteName returns a warning string if the name is problematic.
// Rules per rclone latest docs:
//   - may not start with '-' or space
//   - may not end with space
//   - ':' and '/' are always disallowed (break remote:path syntax)
//   - unicode, '+', '@', '.', '_', '-', space (mid-name) are all permitted
func validateRemoteName(name string) string {
	if strings.HasPrefix(name, "-") || strings.HasPrefix(name, " ") {
		return "Remote name may not start with '-' or space."
	}
	if strings.HasSuffix(name, " ") {
		return "Remote name may not end with space."
	}
	if strings.ContainsAny(name, ":/") {
		return "Remote name should not contain ':' or '/'."
	}
	return ""
}

// runInteractive runs a command with full stdin/stdout/stderr (interactive TTY).
func runInteractive(name string, args ...string) error {
	cmd := exec.Command(name, args...)
	cmd.Stdin = os.Stdin
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	return cmd.Run()
}

// ─── JSON helpers (no encoding/json import) ───────────────────────────────────

// printRemoteFromDump parses `rclone config dump` JSON and pretty-prints only
// the section for remoteName.
//
// Uses a proper state-machine tokenizer so that:
//   - escaped quotes inside string values are handled correctly         (#1)
//   - values containing commas or colons are not split wrongly          (#2)
//   - nested JSON objects (e.g. OAuth token blobs) are printed as-is   (#1)
func printRemoteFromDump(jsonStr, remoteName string) {
	// Locate the top-level key: "remoteName":{
	marker := fmt.Sprintf("%q:{", remoteName)
	idx := strings.Index(jsonStr, marker)
	if idx == -1 {
		printWarn("Remote section not found in config dump.")
		return
	}

	// Advance past the marker to the opening '{' of this remote's object.
	blockStart := idx + len(marker) - 1
	depth, i := 0, blockStart
	for ; i < len(jsonStr); i++ {
		ch := jsonStr[i]
		if ch == '\\' {
			i++ // skip escaped char — don't count as structural
		} else if ch == '{' {
			depth++
		} else if ch == '}' {
			depth--
			if depth == 0 {
				break
			}
		}
	}
	block := jsonStr[blockStart : i+1] // includes surrounding { }
	n := len(block)

	// readString: pos points to opening '"'; returns content and next pos.
	readString := func(pos int) (string, int) {
		var sb strings.Builder
		pos++ // skip opening '"'
		for pos < n {
			ch := block[pos]
			if ch == '\\' && pos+1 < n {
				pos++
				switch block[pos] {
				case '"':
					sb.WriteByte('"')
				case '\\':
					sb.WriteByte('\\')
				case 'n':
					sb.WriteByte('\n')
				case 't':
					sb.WriteByte('\t')
				default:
					sb.WriteByte('\\')
					sb.WriteByte(block[pos])
				}
			} else if ch == '"' {
				pos++ // skip closing '"'
				break
			} else {
				sb.WriteByte(ch)
			}
			pos++
		}
		return sb.String(), pos
	}

	// readRaw: reads a non-string token (number, bool, null, nested object/array).
	readRaw := func(pos int) (string, int) {
		start := pos
		d := 0
		for pos < n {
			ch := block[pos]
			if ch == '{' || ch == '[' {
				d++
			} else if ch == '}' || ch == ']' {
				if d == 0 {
					break
				}
				d--
			} else if d == 0 && (ch == ',' || ch == '}') {
				break
			}
			pos++
		}
		return strings.TrimSpace(block[start:pos]), pos
	}

	type kv struct{ key, val string }
	var pairs []kv

	j := 1 // skip opening '{'
	for j < n-1 {
		// skip whitespace and commas
		for j < n && (block[j] == ' ' || block[j] == '\n' || block[j] == '\t' || block[j] == ',') {
			j++
		}
		if j >= n-1 || block[j] != '"' {
			j++
			continue
		}
		key, next := readString(j)
		j = next
		for j < n && (block[j] == ' ' || block[j] == ':') {
			j++
		}
		var val string
		if j < n && block[j] == '"' {
			val, j = readString(j)
		} else {
			val, j = readRaw(j)
		}
		if key != "" {
			pairs = append(pairs, kv{key, val})
		}
	}

	for _, p := range pairs {
		fmt.Printf("  %-22s : %s\n", p.key, p.val)
	}
}

// humanBytes converts a byte count to a human-readable string.
func humanBytes(b float64) string {
	if b <= 0 {
		return "N/A"
	}
	const unit = 1024.0
	if b < unit {
		return fmt.Sprintf("%.0f B", b)
	}
	div, exp := unit, 0
	for v := b / unit; v >= unit; v /= unit {
		div *= unit
		exp++
	}
	return fmt.Sprintf("%.1f %cB", b/div, "KMGTPE"[exp])
}

// extractJSONFloat extracts a numeric field from a JSON string.
// #3 — handles null and missing fields; returns (value, ok) so callers can
// distinguish "field is 0" from "field is absent or null".
func extractJSONFloat(raw, field string) (float64, bool) {
	key := fmt.Sprintf("%q:", field)
	i := strings.Index(raw, key)
	if i == -1 {
		return 0, false
	}
	start := i + len(key)
	// skip whitespace
	for start < len(raw) && (raw[start] == ' ' || raw[start] == '\n' || raw[start] == '\t') {
		start++
	}
	// null → field is present but not available
	if start < len(raw) && strings.HasPrefix(raw[start:], "null") {
		return 0, false
	}
	var val float64
	if _, err := fmt.Sscanf(raw[start:], "%f", &val); err != nil {
		return 0, false
	}
	return val, true
}

// printQuota calls `rclone about --json` and prints Total / Used / Free.
// #3 — null/missing fields show "N/A" instead of "0 B".
// #6 — called for every remote regardless of the lsd connectivity result.
func printQuota(remote string) {
	out, err := exec.Command("rclone", "about", "--json", remote+":").Output()
	if err != nil || len(out) == 0 {
		printInfo("Quota info not supported by this backend.")
		return
	}
	raw := string(out)
	fmtField := func(field string) string {
		v, ok := extractJSONFloat(raw, field)
		if !ok {
			return "N/A"
		}
		return humanBytes(v)
	}
	fmt.Printf("  %sQuota%s — Total: %s  Used: %s  Free: %s\n",
		Cyan, NC, fmtField("total"), fmtField("used"), fmtField("free"))
}

// ─── Menu actions ─────────────────────────────────────────────────────────────

func createNewRemote(reader *bufio.Reader) {
	clearScreen()
	fmt.Printf("%s%s🆕  New Remote Creator%s\n\n", Bold, Yellow, NC)

	name, err := prompt(reader, "📛 Remote name (e.g. gdrive, mega, s3): ")
	if err != nil {
		printError(err.Error())
		return
	}
	if name == "" {
		printError("Remote name cannot be empty.")
		return
	}
	// #5 — extended validation
	if warn := validateRemoteName(name); warn != "" {
		printWarn(warn)
	}

	exists, err := remoteExists(name)
	if err != nil {
		printError(err.Error())
		return
	}
	if exists {
		printWarn(fmt.Sprintf("Remote '%s' already exists. Use 'Edit' instead.", name))
		return
	}

	fmt.Printf("\n%srclone config will open. Follow these steps:%s\n", Blue, NC)
	fmt.Println("  1. Enter  n  → New remote")
	fmt.Printf("  2. Name:  %s\n", name)
	fmt.Println("  3. Choose your cloud type (drive / s3 / mega / …)")
	fmt.Println("  4. Fill in credentials as prompted")

	launch, err := prompt(reader, "\n🚀 Launch rclone config now? (y/N): ")
	if err != nil {
		printError(err.Error())
		return
	}
	if strings.ToLower(launch) != "y" {
		printInfo("Aborted.")
		return
	}

	if err := runInteractive("rclone", "config"); err != nil {
		printError(fmt.Sprintf("rclone config exited with error: %v", err))
		return
	}

	// Verify the remote was saved.
	exists, err = remoteExists(name)
	if err != nil {
		printError(err.Error())
		return
	}
	if !exists {
		printWarn(fmt.Sprintf("Remote '%s' not found after config. Did you save it?", name))
		return
	}
	printSuccess(fmt.Sprintf("Remote '%s' created!", name))
	printInfo(fmt.Sprintf("Quick connectivity test: rclone lsd %s:", name))

	testCmd := exec.Command("rclone", "lsd", name+":")
	testCmd.Stdout = os.Stdout
	testCmd.Stderr = os.Stderr
	if err := testCmd.Run(); err != nil {
		printWarn(fmt.Sprintf("Test failed. Verify manually: rclone lsd %s:", name))
	}
}

func editRemote(reader *bufio.Reader) {
	clearScreen()
	fmt.Printf("%s%s✏️   Edit Remote%s\n\n", Bold, Yellow, NC)

	names, err := listRemoteNames()
	if err != nil {
		printError(err.Error())
		return
	}
	if len(names) == 0 {
		printInfo("No remotes configured yet.")
		return
	}
	printRemoteList(names)

	name, err := prompt(reader, "📛 Which remote to edit: ")
	if err != nil {
		printError(err.Error())
		return
	}
	if name == "" {
		printError("Remote name cannot be empty.")
		return
	}

	exists, err := remoteExists(name)
	if err != nil {
		printError(err.Error())
		return
	}
	if !exists {
		printError(fmt.Sprintf("Remote '%s' does not exist.", name))
		return
	}

	// Show current config.
	// #3 primary  — rclone config dump (reliable on all modern versions).
	// #4 fallback — rclone config show (older rclone versions still support it).
	fmt.Printf("\n%sCurrent config for '%s':%s\n", Cyan, name, NC)
	dumpOut, dumpErr := exec.Command("rclone", "config", "dump").Output()
	if dumpErr == nil && len(dumpOut) > 0 {
		printRemoteFromDump(string(dumpOut), name)
	} else {
		// #4 fallback
		showCmd := exec.Command("rclone", "config", "show", name)
		showCmd.Stdout = os.Stdout
		showCmd.Stderr = os.Stderr
		if err := showCmd.Run(); err != nil {
			printWarn("Could not retrieve config. Try: rclone config show " + name)
		}
	}

	fmt.Printf("\n%sEdit options:%s\n", Blue, NC)
	fmt.Println("  1. Interactive edit  (rclone config → e → select remote)")
	fmt.Println("  2. Reconnect / reauth  (rclone config reconnect)")
	fmt.Println("  3. Update single option  (rclone config update)")
	fmt.Println("  4. Cancel")

	// #1 normalize; #2 empty Enter → default to cancel
	choice, err := prompt(reader, "Choice (1-4): ")
	if err != nil {
		printError(err.Error())
		return
	}
	choice = strings.ToLower(strings.TrimSpace(choice))
	if choice == "" {
		choice = "4"
	}

	switch choice {
	case "1":
		printInfo("In rclone config: choose  e  → edit existing remote → select '" + name + "'.")
		if err := runInteractive("rclone", "config"); err != nil {
			printError(fmt.Sprintf("rclone config error: %v", err))
			return
		}
		printSuccess("Edit session complete.")

	case "2":
		printInfo(fmt.Sprintf("Re-authenticating '%s'…", name))
		if err := runInteractive("rclone", "config", "reconnect", name+":"); err != nil {
			printError(fmt.Sprintf("Reconnect failed: %v", err))
			return
		}
		printSuccess(fmt.Sprintf("'%s' re-authenticated.", name))

	case "3":
		key, err := prompt(reader, "Option key (e.g. token, client_id): ")
		if err != nil || key == "" {
			printError("Key cannot be empty.")
			return
		}
		val, err := prompt(reader, "New value: ")
		if err != nil {
			printError(err.Error())
			return
		}
		updateCmd := exec.Command("rclone", "config", "update", name, key, val)
		updateCmd.Stdout = os.Stdout
		updateCmd.Stderr = os.Stderr
		if err := updateCmd.Run(); err != nil {
			printError(fmt.Sprintf("Update failed: %v", err))
			return
		}
		printSuccess(fmt.Sprintf("'%s' → %s updated.", name, key))

	default:
		printInfo("Cancelled.")
	}
}

func deleteRemote(reader *bufio.Reader) {
	clearScreen()
	fmt.Printf("%s%s🗑️   Delete Remote%s\n\n", Bold, Red, NC)

	names, err := listRemoteNames()
	if err != nil {
		printError(err.Error())
		return
	}
	if len(names) == 0 {
		printInfo("No remotes configured yet.")
		return
	}
	printRemoteList(names)

	name, err := prompt(reader, "📛 Which remote to delete: ")
	if err != nil {
		printError(err.Error())
		return
	}
	if name == "" {
		printError("Remote name cannot be empty.")
		return
	}

	exists, err := remoteExists(name)
	if err != nil {
		printError(err.Error())
		return
	}
	if !exists {
		printError(fmt.Sprintf("Remote '%s' does not exist.", name))
		return
	}

	confirm, err := prompt(reader,
		fmt.Sprintf("⚠️  Delete '%s'? This cannot be undone. (yes/N): ", name))
	if err != nil {
		printError(err.Error())
		return
	}
	if strings.ToLower(confirm) != "yes" {
		printInfo("Deletion cancelled.")
		return
	}

	delCmd := exec.Command("rclone", "config", "delete", name)
	delCmd.Stderr = os.Stderr
	if err := delCmd.Run(); err != nil {
		printError(fmt.Sprintf("Delete failed: %v", err))
		return
	}

	// Verify deletion.
	exists, err = remoteExists(name)
	if err != nil {
		printError(err.Error())
		return
	}
	if exists {
		printError(fmt.Sprintf("'%s' still present after delete — check rclone config file.", name))
		return
	}
	printSuccess(fmt.Sprintf("Remote '%s' deleted.", name))
}

func testAllRemotes() {
	clearScreen()
	fmt.Printf("%s%s🧪 Testing All Remotes%s\n\n", Bold, Green, NC)

	names, err := listRemoteNames()
	if err != nil {
		printError(err.Error())
		return
	}
	if len(names) == 0 {
		printInfo("No remotes to test.")
		return
	}

	passed, failed := 0, 0
	for _, name := range names {
		fmt.Printf("%s── %s ──%s\n", Blue, name, NC)

		lsdCmd := exec.Command("rclone", "lsd", name+":")
		lsdCmd.Stdout = os.Stdout
		lsdCmd.Stderr = os.Stderr
		if err := lsdCmd.Run(); err != nil {
			printError(fmt.Sprintf("'%s' connectivity test failed: %v", name, err))
			failed++
		} else {
			printSuccess(fmt.Sprintf("'%s' reachable.", name))
			passed++
		}
		// #6 — quota is independent of lsd; attempt for every remote.
		printQuota(name)
		fmt.Println()
	}

	summaryColor := Green
	if failed > 0 {
		summaryColor = Yellow
	}
	fmt.Printf("%s%sSummary: %d passed, %d failed%s\n",
		Bold, summaryColor, passed, failed, NC)
}

// ─── Main ─────────────────────────────────────────────────────────────────────

func main() {
	clearScreen()
	fmt.Printf("%s%s🌩️  Rclone Multi-Cloud Config Manager%s\n", Bold, Yellow, NC)
	fmt.Println("═══════════════════════════════════════")
	fmt.Println()

	if err := checkRclone(); err != nil {
		printError(err.Error())
		os.Exit(1)
	}
	printSuccess("rclone found.")
	fmt.Println()

	reader := bufio.NewReader(os.Stdin)

	for {
		names, listErr := listRemoteNames()
		hasRemotes := listErr == nil && len(names) > 0

		if !hasRemotes {
			// #6 — no remotes: skip full menu, prompt to add the first one.
			printInfo("No remotes configured yet.")
			fmt.Printf("%sPress Enter to add your first remote, or 'q' to quit: %s", Yellow, NC)
			line, _ := reader.ReadString('\n')
			if strings.ToLower(strings.TrimSpace(line)) == "q" {
				fmt.Printf("%s👋 Bye!%s\n", Green, NC)
				return
			}
			createNewRemote(reader)
			clearScreen()
			continue
		}

		printRemoteList(names)
		fmt.Printf("%s%s➕  Main Menu%s\n", Bold, Purple, NC)
		fmt.Println("  1. Add New Remote")
		fmt.Println("  2. Edit Existing Remote")
		fmt.Println("  3. Delete Remote")
		fmt.Println("  4. Test All Remotes")
		fmt.Println("  5. Quit")
		fmt.Println()

		// #1 — normalize: trim + lowercase eliminates newline/case issues.
		choice, err := prompt(reader, "Choice (1-5): ")
		if err != nil {
			printError(fmt.Sprintf("Input error: %v", err))
			continue
		}
		choice = strings.ToLower(strings.TrimSpace(choice))
		fmt.Println()

		// #7 — quit exits immediately; no "Back to menu?" prompt.
		if choice == "5" {
			fmt.Printf("%s👋 Bye! Stay safe in the clouds ☁️%s\n", Green, NC)
			os.Exit(0)
		}

		switch choice {
		case "1":
			createNewRemote(reader)
		case "2":
			editRemote(reader)
		case "3":
			deleteRemote(reader)
		case "4":
			testAllRemotes()
		default:
			printWarn(fmt.Sprintf("'%s' is not a valid choice.", choice))
		}

		fmt.Println()
		cont, err := prompt(reader, "⏭️  Back to menu? (Enter/y = yes, n = quit): ")
		if err != nil {
			break
		}
		if strings.ToLower(cont) == "n" {
			fmt.Printf("%s👋 Bye!%s\n", Green, NC)
			break
		}
		clearScreen()
	}
}
