package main

import (
	"bufio"
	"compress/gzip"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"
)

// ==================== ভার্সন ====================

const VERSION = "1.0.0"

// ==================== কনফিগ স্ট্রাকচার ====================

type LightProfileConfig struct {
	BufferSize      string `json:"buffer_size"`
	Transfers       int    `json:"transfers"`
	Checkers        int    `json:"checkers"`
	SFTPConcurrency int    `json:"sftp_concurrency"`
	VFSCacheMode    string `json:"vfs_cache_mode"`
	Timeout         string `json:"timeout"`
	Description     string `json:"description"`
}

type BalancedProfileConfig struct {
	BufferSize      string `json:"buffer_size"`
	Transfers       int    `json:"transfers"`
	Checkers        int    `json:"checkers"`
	SFTPConcurrency int    `json:"sftp_concurrency"`
	VFSCacheMode    string `json:"vfs_cache_mode"`
	VFSCacheMaxSize string `json:"vfs_cache_max_size"`
	VFSCacheMaxAge  string `json:"vfs_cache_max_age"`
	VFSReadChunk    string `json:"vfs_read_chunk"`
	VFSReadAhead    string `json:"vfs_read_ahead"`
	Timeout         string `json:"timeout"`
	Contimeout      string `json:"contimeout"`
	LowLevelRetries int    `json:"low_level_retries"`
	Description     string `json:"description"`
}

type HeavyProfileConfig struct {
	BufferSize      string `json:"buffer_size"`
	Transfers       int    `json:"transfers"`
	Checkers        int    `json:"checkers"`
	SFTPConcurrency int    `json:"sftp_concurrency"`
	VFSCacheMode    string `json:"vfs_cache_mode"`
	VFSCacheMaxSize string `json:"vfs_cache_max_size"`
	VFSCacheMaxAge  string `json:"vfs_cache_max_age"`
	VFSReadChunk    string `json:"vfs_read_chunk"`
	VFSReadAhead    string `json:"vfs_read_ahead"`
	Timeout         string `json:"timeout"`
	Contimeout      string `json:"contimeout"`
	LowLevelRetries int    `json:"low_level_retries"`
	MaxConnections  int    `json:"max_connections"`
	Description     string `json:"description"`
}

type Config struct {
	ServerName   string `json:"server_name"`
	Remote       string `json:"remote"`
	Port         int    `json:"port"`
	User         string `json:"user"`
	Password     string `json:"password"`
	PasswordFile string `json:"password_file"`
	ConfigPath   string `json:"config_path"`
	Profile      string `json:"profile"` // "light", "balanced", "heavy"

	LightProfile    LightProfileConfig    `json:"light_profile"`
	BalancedProfile BalancedProfileConfig `json:"balanced_profile"`
	HeavyProfile    HeavyProfileConfig    `json:"heavy_profile"`

	CacheDir string `json:"cache_dir"`
	TempDir  string `json:"temp_dir"`
	LogDir   string `json:"log_dir"`

	LogSize     int64 `json:"log_size"`
	MaxLogFiles int   `json:"max_log_files"`
	MaxDiskMB   int64 `json:"max_disk_mb"`

	PortRangeFrom int `json:"port_range_from"`
	PortRangeTo   int `json:"port_range_to"`

	AutoRestart  bool `json:"auto_restart"`
	MaxRestarts  int  `json:"max_restarts"`
	RestartDelay int  `json:"restart_delay"`

	PlainPassword bool `json:"plain_password"`
	Verbose       bool `json:"verbose"`
}

// ==================== সার্ভার টাইপ ====================

type ServerStatus struct {
	Remote        string `json:"remote"`
	Port          int    `json:"port"`
	PID           int    `json:"pid"`
	Status        string `json:"status"`
	Profile       string `json:"profile"`
	Uptime        string `json:"uptime,omitempty"`
	LogSize       int64  `json:"log_size"`
	LogCount      int    `json:"log_count"`
	RestartCount  int    `json:"restart_count"`
	CacheSize     string `json:"cache_size"`
	TransferSpeed string `json:"transfer_speed"`
}

// ServerMeta — ডিস্কে persist হওয়া তথ্য (program restart-এর পরেও টিকে থাকে)
type ServerMeta struct {
	Remote    string    `json:"remote"`
	Port      string    `json:"port"`
	User      string    `json:"user"`
	Profile   string    `json:"profile"`
	StartTime time.Time `json:"start_time"`
	PID       int       `json:"pid"`
}

type ServerInfo struct {
	ServerMeta
	Password      string
	RestartCount  int
	LastExitCode  int
	logRotateStop chan bool
	rotateStopped bool
	mu            sync.Mutex
	cmd           *exec.Cmd
	bytesTotal    int64
	lastTime      time.Time
}

func (s *ServerInfo) stopRotator() {
	s.mu.Lock()
	defer s.mu.Unlock()
	if !s.rotateStopped && s.logRotateStop != nil {
		s.rotateStopped = true
		close(s.logRotateStop)
	}
}

// ==================== গ্লোবাল ভেরিয়েবল ====================

var (
	baseDir      string
	config       Config
	configMu     sync.RWMutex
	logRotateMu  sync.Mutex
	servers      = make(map[string]*ServerInfo)
	serversMu    sync.RWMutex
	rcloneBin    string
	logger       = log.New(os.Stdout, "", log.LstdFlags)
)

// ==================== ইনিট ====================

func init() {
	home, err := os.UserHomeDir()
	if err != nil {
		baseDir = "rclone_sftp_runtime"
	} else {
		baseDir = filepath.Join(home, ".local", "share", "rclone-sftp")
	}

	rcloneBin = os.Getenv("RCLONE_BINARY")
	if rcloneBin == "" {
		rcloneBin = "rclone"
	}

	for _, dir := range []string{baseDir, logsDir(), cacheDir(), tempDir(), metaDir()} {
		os.MkdirAll(dir, 0755)
	}

	loadConfig()
	loadAllMeta()
	startCacheSizeUpdater()
}

// ==================== ডিরেক্টরি হেল্পার ====================

func logsDir() string  { return filepath.Join(baseDir, "logs") }
func cacheDir() string { return filepath.Join(baseDir, "cache") }
func tempDir() string  { return filepath.Join(baseDir, "temp") }
func metaDir() string  { return filepath.Join(baseDir, "meta") }

// ==================== কনফিগ ====================

func loadConfig() {
	configMu.Lock()
	defer configMu.Unlock()
	data, err := os.ReadFile(filepath.Join(baseDir, "config.json"))
	if err != nil || json.Unmarshal(data, &config) != nil {
		config = defaultConfig()
		writeConfig()
	}
}

func saveConfig() {
	configMu.Lock()
	defer configMu.Unlock()
	writeConfig()
}

func writeConfig() {
	data, _ := json.MarshalIndent(config, "", "  ")
	os.WriteFile(filepath.Join(baseDir, "config.json"), data, 0644)
}

func defaultConfig() Config {
	return Config{
		ServerName: "default",
		Profile:    "balanced",

		LightProfile: LightProfileConfig{
			BufferSize:      "16M",
			Transfers:       2,
			Checkers:        4,
			SFTPConcurrency: 2,
			VFSCacheMode:    "off",
			Timeout:         "30m",
			Description:     "Light usage - small files, low memory",
		},

		BalancedProfile: BalancedProfileConfig{
			BufferSize:      "32M",
			Transfers:       4,
			Checkers:        8,
			SFTPConcurrency: 4,
			VFSCacheMode:    "writes",
			VFSCacheMaxSize: "50G",
			VFSCacheMaxAge:  "72h",
			VFSReadChunk:    "32M",
			VFSReadAhead:    "64M",
			Timeout:         "1h",
			Contimeout:      "2m",
			LowLevelRetries: 10,
			Description:     "Balanced - medium files, good performance",
		},

		HeavyProfile: HeavyProfileConfig{
			BufferSize:      "64M",
			Transfers:       8,
			Checkers:        16,
			SFTPConcurrency: 8,
			VFSCacheMode:    "full",
			VFSCacheMaxSize: "200G",
			VFSCacheMaxAge:  "168h",
			VFSReadChunk:    "64M",
			VFSReadAhead:    "128M",
			Timeout:         "2h",
			Contimeout:      "5m",
			LowLevelRetries: 20,
			MaxConnections:  20,
			Description:     "Heavy - large files 100GB+, max performance",
		},

		CacheDir: filepath.Join(baseDir, "cache"),
		TempDir:  filepath.Join(baseDir, "temp"),
		LogDir:   filepath.Join(baseDir, "logs"),

		LogSize:     50 * 1024 * 1024,
		MaxLogFiles: 5,
		MaxDiskMB:   1024,

		PortRangeFrom: 8022,
		PortRangeTo:   9000,

		AutoRestart:  false,
		MaxRestarts:  5,
		RestartDelay: 10,

		PlainPassword: true,
		Verbose:       false,
	}
}

// ==================== সার্ভার মেটা (ডিস্ক persist) ====================

func metaFile(remote, port string) string {
	return filepath.Join(metaDir(), fmt.Sprintf("%s_%s.json", remote, port))
}

func saveMeta(si *ServerInfo) {
	data, _ := json.MarshalIndent(si.ServerMeta, "", "  ")
	os.WriteFile(metaFile(si.Remote, si.Port), data, 0600)
}

func deleteMeta(remote, port string) {
	os.Remove(metaFile(remote, port))
}

func loadAllMeta() {
	files, _ := filepath.Glob(filepath.Join(metaDir(), "*.json"))
	for _, f := range files {
		data, err := os.ReadFile(f)
		if err != nil {
			continue
		}
		var meta ServerMeta
		if json.Unmarshal(data, &meta) != nil {
			continue
		}
		if !isProcessAlive(meta.PID) {
			os.Remove(f)
			continue
		}
		key := serverKey(meta.Remote, meta.Port)
		serversMu.Lock()
		servers[key] = &ServerInfo{
			ServerMeta:    meta,
			logRotateStop: make(chan bool),
			lastTime:      time.Now(),
		}
		serversMu.Unlock()

		logFile := filepath.Join(config.LogDir, fmt.Sprintf("%s_%s.log", meta.Remote, meta.Port))
		si := servers[key]
		go startLogRotator(logFile, si.logRotateStop)
	}
}

// ==================== ইউটিলিটি ====================

func serverKey(remote, port string) string { return remote + ":" + port }

func splitRemotePort(name string) (remote, port string, ok bool) {
	idx := strings.LastIndex(name, "_")
	if idx == -1 {
		return "", "", false
	}
	return name[:idx], name[idx+1:], true
}

func isProcessAlive(pid int) bool {
	if pid <= 0 {
		return false
	}
	return exec.Command("kill", "-0", strconv.Itoa(pid)).Run() == nil
}

func isPortFree(port int) bool {
	ln, err := net.Listen("tcp", fmt.Sprintf(":%d", port))
	if err != nil {
		return false
	}
	ln.Close()
	return true
}

func findFreePort() int {
	for p := config.PortRangeFrom; p <= config.PortRangeTo; p++ {
		if isPortFree(p) {
			return p
		}
	}
	return 0
}

func getPassword(pass, passwordFile string) (string, error) {
	switch {
	case passwordFile != "":
		data, err := os.ReadFile(passwordFile)
		if err != nil {
			return "", err
		}
		return strings.TrimSpace(string(data)), nil
	case pass != "":
		return pass, nil
	case os.Getenv("RCLONE_SFTP_PASS") != "":
		return os.Getenv("RCLONE_SFTP_PASS"), nil
	default:
		return "", fmt.Errorf("password required: use --password-file or set RCLONE_SFTP_PASS")
	}
}

// ==================== ক্যাশ সাইজ (background update) ====================

var (
	cachedCacheSize    int64
	cacheSizeMu        sync.RWMutex
)

// init()-এ একবার call হয়, তারপর প্রতি ৫ মিনিটে update করে।
// প্রতিবার full walk না করে cached value ফেরত দেয়।
func startCacheSizeUpdater() {
	update := func() {
		var total int64
		filepath.Walk(config.CacheDir, func(_ string, info os.FileInfo, err error) error {
			if err == nil && !info.IsDir() {
				total += info.Size()
			}
			return nil
		})
		cacheSizeMu.Lock()
		cachedCacheSize = total
		cacheSizeMu.Unlock()
	}

	update() // প্রথমবার সাথে সাথে
	go func() {
		ticker := time.NewTicker(5 * time.Minute)
		defer ticker.Stop()
		for range ticker.C {
			update()
		}
	}()
}

func calcCacheSize() int64 {
	cacheSizeMu.RLock()
	defer cacheSizeMu.RUnlock()
	return cachedCacheSize
}

func profileDescription(profile string) string {
	switch profile {
	case "light":
		return config.LightProfile.Description
	case "heavy":
		return config.HeavyProfile.Description
	default:
		return config.BalancedProfile.Description
	}
}

// ==================== rclone আর্গুমেন্ট বিল্ড ====================

func buildArgs(remote, port, user, pass, profile string) []string {
	args := []string{
		"serve", "sftp", remote + ":",
		"--addr", ":" + port,
		"--user", user,
		"--pass", pass,
	}

	switch profile {
	case "light":
		p := config.LightProfile
		args = append(args,
			"--buffer-size", p.BufferSize,
			"--transfers", strconv.Itoa(p.Transfers),
			"--checkers", strconv.Itoa(p.Checkers),
			"--sftp-concurrency", strconv.Itoa(p.SFTPConcurrency),
			"--vfs-cache-mode", p.VFSCacheMode,
			"--timeout", p.Timeout,
		)
	case "heavy":
		p := config.HeavyProfile
		args = append(args,
			"--buffer-size", p.BufferSize,
			"--transfers", strconv.Itoa(p.Transfers),
			"--checkers", strconv.Itoa(p.Checkers),
			"--sftp-concurrency", strconv.Itoa(p.SFTPConcurrency),
			"--vfs-cache-mode", p.VFSCacheMode,
			"--vfs-cache-max-size", p.VFSCacheMaxSize,
			"--vfs-cache-max-age", p.VFSCacheMaxAge,
			"--vfs-read-chunk-size", p.VFSReadChunk,
			"--vfs-read-ahead", p.VFSReadAhead,
			"--timeout", p.Timeout,
			"--contimeout", p.Contimeout,
			"--low-level-retries", strconv.Itoa(p.LowLevelRetries),
			"--max-connections", strconv.Itoa(p.MaxConnections), // BUG FIX: আগে missing ছিল
		)
	default: // balanced
		p := config.BalancedProfile
		args = append(args,
			"--buffer-size", p.BufferSize,
			"--transfers", strconv.Itoa(p.Transfers),
			"--checkers", strconv.Itoa(p.Checkers),
			"--sftp-concurrency", strconv.Itoa(p.SFTPConcurrency),
			"--vfs-cache-mode", p.VFSCacheMode,
			"--vfs-cache-max-size", p.VFSCacheMaxSize,
			"--vfs-cache-max-age", p.VFSCacheMaxAge,
			"--vfs-read-chunk-size", p.VFSReadChunk,
			"--vfs-read-ahead", p.VFSReadAhead,
			"--timeout", p.Timeout,
			"--contimeout", p.Contimeout,
			"--low-level-retries", strconv.Itoa(p.LowLevelRetries),
		)
	}

	if config.CacheDir != "" {
		args = append(args, "--cache-dir", config.CacheDir)
	}
	if config.TempDir != "" {
		args = append(args, "--temp-dir", config.TempDir)
	}

	if config.ConfigPath != "" {
		args = append(args, "--config", config.ConfigPath)
	} else if envCfg := os.Getenv("RCLONE_CONFIG"); envCfg != "" {
		args = append(args, "--config", envCfg)
	}

	if config.Verbose {
		args = append(args, "-vv")
	} else {
		args = append(args, "-v")
	}

	return args
}

// ==================== সার্ভার স্টার্ট ====================

func startServer(remote, port, user, pass, passwordFile, profile string) {
	// ডিস্ক স্পেস চেক
	if config.MaxDiskMB > 0 {
		var stat syscall.Statfs_t
		if err := syscall.Statfs(baseDir, &stat); err == nil {
			freeMB := int64(stat.Bavail) * int64(stat.Bsize) / (1024 * 1024)
			if freeMB < config.MaxDiskMB {
				logger.Fatalf("[ERROR] Insufficient disk space: %dMB free, need %dMB", freeMB, config.MaxDiskMB)
			}
		}
	}

	// পোর্ট অটো-অ্যাসাইন
	if port == "auto" {
		p := findFreePort()
		if p == 0 {
			logger.Fatal("[ERROR] No free port available")
		}
		port = strconv.Itoa(p)
		fmt.Printf("[INFO] Auto-assigned port: %s\n", port)
	}

	finalPass, err := getPassword(pass, passwordFile)
	if err != nil {
		logger.Fatal("[ERROR] ", err)
	}

	// PID চেক — আগে থেকে চলছে কিনা
	pidFile := filepath.Join(baseDir, fmt.Sprintf("%s_%s.pid", remote, port))
	if data, err := os.ReadFile(pidFile); err == nil {
		if pid, _ := strconv.Atoi(strings.TrimSpace(string(data))); isProcessAlive(pid) {
			logger.Fatalf("[ERROR] Server already running with PID %d", pid)
		}
		os.Remove(pidFile)
	}

	// লগ ফাইল
	logFile := filepath.Join(config.LogDir, fmt.Sprintf("%s_%s.log", remote, port))
	logF, err := os.OpenFile(logFile, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0644)
	if err != nil {
		logger.Fatal("[ERROR] Cannot create log file: ", err)
	}
	defer logF.Close()

	startTime := time.Now()
	fmt.Fprintf(logF, "\n=== Server started at %s ===\n", startTime.Format("2006-01-02 15:04:05"))
	fmt.Fprintf(logF, "Remote: %s, Port: %s, User: %s, Profile: %s\n", remote, port, user, profile)
	fmt.Fprintf(logF, "Cache dir: %s\n", config.CacheDir)

	// rclone প্রসেস
	args := buildArgs(remote, port, user, finalPass, profile)
	cmd := exec.Command(rcloneBin, args...)
	cmd.Stdout = logF
	cmd.Stderr = logF
	cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}

	fmt.Printf("[INFO] Starting %s server on port %s with %s profile...\n", remote, port, profile)
	if err := cmd.Start(); err != nil {
		fmt.Fprintf(logF, "Failed to start: %v\n", err)
		logger.Fatal("[ERROR] Failed to start: ", err)
	}

	pid := cmd.Process.Pid
	fmt.Fprintf(logF, "PID: %d\n", pid)

	// PID ফাইল লিখি
	os.WriteFile(pidFile, []byte(strconv.Itoa(pid)), 0644)

	// প্রসেস ডিট্যাচ
	cmd.Process.Release()

	// in-memory + disk meta সেভ
	si := &ServerInfo{
		ServerMeta: ServerMeta{
			Remote:    remote,
			Port:      port,
			User:      user,
			Profile:   profile,
			StartTime: startTime,
			PID:       pid,
		},
		Password:      finalPass,
		logRotateStop: make(chan bool),
		cmd:           cmd,
		lastTime:      time.Now(),
	}

	key := serverKey(remote, port)
	serversMu.Lock()
	servers[key] = si
	serversMu.Unlock()

	saveMeta(si) // BUG FIX: ডিস্কে persist করি

	go startLogRotator(logFile, si.logRotateStop) // BUG FIX: si সরাসরি ব্যবহার

	fmt.Printf("[OK] Server started: %s:%s (PID: %d)\n", remote, port, pid)
	fmt.Printf("[INFO] Profile: %s\n", profile)
	fmt.Printf("[INFO] Log file: %s\n", logFile)
}

// ==================== সার্ভার স্টপ ====================

func stopServer(remote, port string, silent bool) bool {
	pidFile := filepath.Join(baseDir, fmt.Sprintf("%s_%s.pid", remote, port))
	data, err := os.ReadFile(pidFile)
	if err != nil {
		if !silent {
			fmt.Printf("[ERROR] Server not found: %s:%s\n", remote, port)
		}
		return false
	}

	pid, _ := strconv.Atoi(strings.TrimSpace(string(data)))

	cleanup := func() {
		os.Remove(pidFile)
		deleteMeta(remote, port)

		// stopRotator() নিজেও s.mu.Lock() নেয়।
		// serversMu ধরা অবস্থায় ডাকলে lock ordering সমস্যা হতে পারে।
		// তাই আগে map থেকে বের করি, তারপর lock ছেড়ে stopRotator ডাকি।
		key := serverKey(remote, port)
		serversMu.Lock()
		si, exists := servers[key]
		if exists {
			delete(servers, key)
		}
		serversMu.Unlock()

		if exists {
			si.stopRotator() // lock-এর বাইরে
		}
	}

	if !isProcessAlive(pid) {
		cleanup()
		return true
	}

	if !silent {
		fmt.Printf("[INFO] Stopping server %s:%s (PID: %d)...\n", remote, port, pid)
	}

	exec.Command("kill", "-TERM", strconv.Itoa(pid)).Run()
	for i := 0; i < 10; i++ {
		time.Sleep(time.Second)
		if !isProcessAlive(pid) {
			break
		}
	}
	if isProcessAlive(pid) {
		exec.Command("kill", "-KILL", strconv.Itoa(pid)).Run()
		time.Sleep(time.Second)
	}

	if !isProcessAlive(pid) {
		cleanup()
		if !silent {
			fmt.Println("[OK] Server stopped")
		}
		return true
	}

	if !silent {
		fmt.Println("[ERROR] Failed to stop server")
	}
	return false
}

func stopAllServers() {
	files, _ := filepath.Glob(filepath.Join(baseDir, "*.pid"))
	if len(files) == 0 {
		fmt.Println("[INFO] No servers running")
		return
	}
	fmt.Printf("[INFO] Stopping %d servers...\n", len(files))
	for _, file := range files {
		name := strings.TrimSuffix(filepath.Base(file), ".pid")
		remote, port, ok := splitRemotePort(name) // BUG FIX: LastIndex দিয়ে split
		if ok {
			stopServer(remote, port, true)
		}
	}
	fmt.Println("[OK] All servers stopped")
}

// ==================== স্ট্যাটাস ====================

func showStatus(jsonOutput bool) {
	files, _ := filepath.Glob(filepath.Join(config.LogDir, "*.log"))
	var list []ServerStatus

	for _, file := range files {
		name := strings.TrimSuffix(filepath.Base(file), ".log")
		remote, port, ok := splitRemotePort(name) // BUG FIX: LastIndex দিয়ে split
		if !ok {
			continue
		}

		pidFile := filepath.Join(baseDir, fmt.Sprintf("%s_%s.pid", remote, port))
		pidData, _ := os.ReadFile(pidFile)
		pid, _ := strconv.Atoi(strings.TrimSpace(string(pidData)))
		portInt, _ := strconv.Atoi(port)

		logInfo, _ := os.Stat(file)
		rotated, _ := filepath.Glob(file + ".*.gz")

		// BUG FIX: pid==0 হলে "running" দেখানো যাবে না
		if pid <= 0 {
			continue
		}

		st := ServerStatus{
			Remote:   remote,
			Port:     portInt,
			PID:      pid,
			LogSize:  logInfo.Size(),
			LogCount: len(rotated),
		}

		if isProcessAlive(pid) {
			st.Status = "running"
			key := serverKey(remote, port)
			serversMu.RLock()
			if s, ok := servers[key]; ok {
				st.Uptime = time.Since(s.StartTime).Round(time.Second).String()
				st.RestartCount = s.RestartCount
				st.Profile = s.Profile
				if s.bytesTotal > 0 {
					speed := float64(s.bytesTotal) / time.Since(s.StartTime).Seconds()
					st.TransferSpeed = fmt.Sprintf("%.2f MB/s", speed/(1024*1024))
				}
			}
			serversMu.RUnlock()

			if cs := calcCacheSize(); cs > 0 {
				st.CacheSize = fmt.Sprintf("%dMB", cs/(1024*1024))
			}
		} else {
			st.Status = "stopped"
			os.Remove(pidFile)
			deleteMeta(remote, port)
		}

		list = append(list, st)
	}

	if jsonOutput {
		json.NewEncoder(os.Stdout).Encode(list)
		return
	}
	if len(list) == 0 {
		fmt.Println("No active servers")
		return
	}
	fmt.Println("\nREMOTE\tPORT\tPID\tPROFILE\tSTATUS\tUPTIME\tCACHE\tSPEED")
	fmt.Println("------\t----\t---\t-------\t------\t------\t-----\t-----")
	for _, s := range list {
		fmt.Printf("%s\t%d\t%d\t%s\t%s\t%s\t%s\t%s\n",
			s.Remote, s.Port, s.PID, s.Profile, s.Status,
			s.Uptime, s.CacheSize, s.TransferSpeed)
	}
}

// ==================== লগ ====================

func showLogs(remote, port string, lines int) {
	logFile := filepath.Join(config.LogDir, fmt.Sprintf("%s_%s.log", remote, port))
	file, err := os.Open(logFile)
	if err != nil {
		fmt.Printf("[ERROR] Log file not found: %s\n", logFile)
		return
	}
	defer file.Close()

	var buf []string
	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		buf = append(buf, scanner.Text())
		if len(buf) > lines {
			buf = buf[1:]
		}
	}
	fmt.Printf("=== Last %d lines of %s ===\n", len(buf), logFile)
	for _, l := range buf {
		fmt.Println(l)
	}
}

// ==================== লগ রোটেশন ====================

func startLogRotator(logPath string, stopChan chan bool) {
	ticker := time.NewTicker(5 * time.Minute)
	defer ticker.Stop()
	for {
		select {
		case <-ticker.C:
			rotateLogIfNeeded(logPath)
		case <-stopChan:
			return
		}
	}
}

func rotateLogIfNeeded(logPath string) {
	logRotateMu.Lock()
	defer logRotateMu.Unlock()

	info, err := os.Stat(logPath)
	if err != nil || info.Size() <= config.LogSize {
		return
	}

	timestamp := time.Now().Format("20060102-150405")
	rotatedPath := logPath + "." + timestamp
	gzPath := rotatedPath + ".gz"

	if err := os.Rename(logPath, rotatedPath); err != nil {
		return
	}
	newLog, err := os.Create(logPath)
	if err != nil {
		os.Rename(rotatedPath, logPath)
		return
	}
	newLog.Close()

	go func() {
		if compressFile(rotatedPath, gzPath) == nil {
			os.Remove(rotatedPath)
			pruneOldLogs(logPath)
		}
	}()
}

func compressFile(src, dst string) error {
	in, err := os.Open(src)
	if err != nil {
		return err
	}
	defer in.Close()

	out, err := os.Create(dst)
	if err != nil {
		return err
	}
	defer out.Close()

	gz := gzip.NewWriter(out)
	defer gz.Close()
	_, err = io.Copy(gz, in)
	return err
}

func pruneOldLogs(logPath string) {
	if config.MaxLogFiles <= 0 {
		return
	}
	files, _ := filepath.Glob(logPath + ".*.gz")
	if len(files) <= config.MaxLogFiles {
		return
	}
	for _, f := range files[:len(files)-config.MaxLogFiles] {
		os.Remove(f)
	}
}

// ==================== চেক ====================

func checkServer(remote, port string) {
	fmt.Printf("\n=== Checking %s:%s ===\n", remote, port)

	portInt, _ := strconv.Atoi(port)
	if portInt <= 0 {
		fmt.Println("[ERROR] Invalid port")
		return
	}

	if isPortFree(portInt) {
		fmt.Printf("Port %s: FREE\n", port)
	} else {
		fmt.Printf("Port %s: IN USE\n", port)
	}

	pidFile := filepath.Join(baseDir, fmt.Sprintf("%s_%s.pid", remote, port))
	data, err := os.ReadFile(pidFile)
	if err != nil {
		fmt.Println("PID file: NOT FOUND")
	} else {
		pid, _ := strconv.Atoi(strings.TrimSpace(string(data)))
		if isProcessAlive(pid) {
			fmt.Printf("PID %d: RUNNING\n", pid)
			key := serverKey(remote, port)
			serversMu.RLock()
			if s, ok := servers[key]; ok {
				fmt.Printf("Profile: %s\n", s.Profile)
				fmt.Printf("Uptime: %s\n", time.Since(s.StartTime).Round(time.Second))
			}
			serversMu.RUnlock()
		} else {
			fmt.Printf("PID %d: NOT RUNNING\n", pid)
			os.Remove(pidFile)
			deleteMeta(remote, port)
		}
	}

	if cs := calcCacheSize(); cs > 0 {
		fmt.Printf("Cache size: %d MB\n", cs/(1024*1024))
	}
}

// ==================== পোর্ট ====================

func showPorts() {
	// শুধু pid ফাইল আছে এমন পোর্ট দেখাই — full scan স্লো
	fmt.Println("\nActive ports:")
	fmt.Println("PORT\tSTATUS\tSERVER")
	fmt.Println("----\t------\t------")

	files, _ := filepath.Glob(filepath.Join(baseDir, "*.pid"))
	if len(files) == 0 {
		fmt.Println("(none)")
		return
	}
	for _, file := range files {
		name := strings.TrimSuffix(filepath.Base(file), ".pid")
		remote, port, ok := splitRemotePort(name)
		if !ok {
			continue
		}
		portInt, _ := strconv.Atoi(port)
		data, _ := os.ReadFile(file)
		pid, _ := strconv.Atoi(strings.TrimSpace(string(data)))

		status := "STOPPED"
		if isProcessAlive(pid) && !isPortFree(portInt) {
			status = "IN USE"
		}
		fmt.Printf("%s\t%s\t%s\n", port, status, remote)
	}
}

// ==================== হেলথ ====================

func healthCheck(jsonOutput bool) {
	type serverEntry struct {
		Remote  string `json:"remote"`
		Port    string `json:"port"`
		PID     int    `json:"pid"`
		Profile string `json:"profile"`
		Alive   bool   `json:"alive"`
	}
	type healthReport struct {
		RcloneInstalled bool                   `json:"rclone_installed"`
		BaseDir         string                 `json:"base_dir"`
		DefaultProfile  string                 `json:"default_profile"`
		FreeDiskGB      int64                  `json:"free_disk_gb"`
		Profiles        map[string]string      `json:"profiles"`
		TotalServers    int                    `json:"total_servers"`
		Servers         []serverEntry          `json:"servers"`
		Errors          []string               `json:"errors"`
	}

	h := healthReport{
		BaseDir:        baseDir,
		DefaultProfile: config.Profile,
		Profiles: map[string]string{
			"light":    config.LightProfile.Description,
			"balanced": config.BalancedProfile.Description,
			"heavy":    config.HeavyProfile.Description,
		},
		Errors: []string{},
	}

	if _, err := exec.LookPath(rcloneBin); err == nil {
		h.RcloneInstalled = true
	} else {
		h.Errors = append(h.Errors, "rclone not found in PATH")
	}

	var stat syscall.Statfs_t
	if err := syscall.Statfs(baseDir, &stat); err == nil {
		h.FreeDiskGB = int64(stat.Bavail) * int64(stat.Bsize) / (1024 * 1024 * 1024)
	}

	files, _ := filepath.Glob(filepath.Join(baseDir, "*.pid"))
	h.TotalServers = len(files)

	for _, file := range files {
		name := strings.TrimSuffix(filepath.Base(file), ".pid")
		remote, port, ok := splitRemotePort(name)
		if !ok {
			continue
		}
		data, _ := os.ReadFile(file)
		pid, _ := strconv.Atoi(strings.TrimSpace(string(data)))

		profile := "unknown"
		serversMu.RLock()
		if s, ok := servers[serverKey(remote, port)]; ok {
			profile = s.Profile
		}
		serversMu.RUnlock()

		h.Servers = append(h.Servers, serverEntry{
			Remote:  remote,
			Port:    port,
			PID:     pid,
			Profile: profile,
			Alive:   isProcessAlive(pid),
		})
	}

	if jsonOutput {
		json.NewEncoder(os.Stdout).Encode(h)
		return
	}

	fmt.Println("\n=== Health Check ===")
	fmt.Printf("Rclone installed : %v\n", h.RcloneInstalled)
	fmt.Printf("Base directory   : %s\n", h.BaseDir)
	fmt.Printf("Free disk space  : %d GB\n", h.FreeDiskGB)
	fmt.Printf("Default profile  : %s\n", h.DefaultProfile)
	fmt.Printf("Active servers   : %d\n", h.TotalServers)
	fmt.Println("\nAvailable Profiles:")
	fmt.Printf("  light    : %s\n", config.LightProfile.Description)
	fmt.Printf("  balanced : %s\n", config.BalancedProfile.Description)
	fmt.Printf("  heavy    : %s\n", config.HeavyProfile.Description)
	if len(h.Errors) > 0 {
		fmt.Println("\nErrors:")
		for _, e := range h.Errors {
			fmt.Printf("  - %s\n", e)
		}
	}
}

// ==================== প্রোফাইল দেখানো ====================

func showProfiles() {
	fmt.Println("\n=== Performance Profiles ===")

	lp := config.LightProfile
	fmt.Println("\n[LIGHT] Small files, low memory")
	fmt.Printf("  %s\n", lp.Description)
	fmt.Printf("  Buffer: %s | Transfers: %d | Checkers: %d | Cache: %s | Timeout: %s\n",
		lp.BufferSize, lp.Transfers, lp.Checkers, lp.VFSCacheMode, lp.Timeout)

	bp := config.BalancedProfile
	fmt.Println("\n[BALANCED] Medium files, good performance  (DEFAULT)")
	fmt.Printf("  %s\n", bp.Description)
	fmt.Printf("  Buffer: %s | Transfers: %d | Checkers: %d | Cache: %s\n",
		bp.BufferSize, bp.Transfers, bp.Checkers, bp.VFSCacheMode)
	fmt.Printf("  CacheMax: %s | CacheAge: %s | Chunk: %s | ReadAhead: %s\n",
		bp.VFSCacheMaxSize, bp.VFSCacheMaxAge, bp.VFSReadChunk, bp.VFSReadAhead)

	hp := config.HeavyProfile
	fmt.Println("\n[HEAVY] Large files 100GB+, max performance")
	fmt.Printf("  %s\n", hp.Description)
	fmt.Printf("  Buffer: %s | Transfers: %d | Checkers: %d | Cache: %s\n",
		hp.BufferSize, hp.Transfers, hp.Checkers, hp.VFSCacheMode)
	fmt.Printf("  CacheMax: %s | CacheAge: %s | Chunk: %s | ReadAhead: %s\n",
		hp.VFSCacheMaxSize, hp.VFSCacheMaxAge, hp.VFSReadChunk, hp.VFSReadAhead)
	fmt.Printf("  MaxConnections: %d\n", hp.MaxConnections)

	fmt.Printf("\nCurrent default: %s\n", config.Profile)
}

// ==================== কনফিগ কমান্ড ====================

func handleConfig(args []string) {
	if len(args) == 0 {
		data, _ := json.MarshalIndent(config, "", "  ")
		fmt.Println(string(data))
		return
	}

	// একটি শব্দ = প্রোফাইল সেট
	if len(args) == 1 {
		switch args[0] {
		case "light", "balanced", "heavy":
			config.Profile = args[0]
			saveConfig()
			fmt.Printf("[OK] Default profile: %s — %s\n", args[0], profileDescription(args[0]))
			return
		}
	}

	configMu.Lock()
	for _, arg := range args {
		kv := strings.SplitN(arg, "=", 2)
		if len(kv) != 2 {
			fmt.Printf("[ERROR] Bad format (expected key=value): %s\n", arg)
			continue
		}
		applyConfigKey(kv[0], kv[1])
	}
	configMu.Unlock()

	writeConfig()
	fmt.Println("[OK] Config saved")
	fmt.Printf("Current default profile: %s\n", config.Profile)
}

func applyConfigKey(key, value string) {
	switch {
	case strings.HasPrefix(key, "light."):
		setLightKey(strings.TrimPrefix(key, "light."), value)
	case strings.HasPrefix(key, "balanced."):
		setBalancedKey(strings.TrimPrefix(key, "balanced."), value)
	case strings.HasPrefix(key, "heavy."):
		setHeavyKey(strings.TrimPrefix(key, "heavy."), value)
	default:
		setGlobalKey(key, value)
	}
}

func setGlobalKey(key, value string) {
	switch key {
	case "profile":
		if value == "light" || value == "balanced" || value == "heavy" {
			config.Profile = value
		}
	case "config_path":
		config.ConfigPath = value
	case "cache_dir":
		config.CacheDir = value
		os.MkdirAll(value, 0755)
	case "temp_dir":
		config.TempDir = value
	case "log_dir":
		config.LogDir = value
		os.MkdirAll(value, 0755)
	case "log_size":
		if n, err := strconv.ParseInt(value, 10, 64); err == nil {
			config.LogSize = n * 1024 * 1024
		}
	case "max_log_files":
		if n, err := strconv.Atoi(value); err == nil {
			config.MaxLogFiles = n
		}
	case "max_disk_mb":
		if n, err := strconv.ParseInt(value, 10, 64); err == nil {
			config.MaxDiskMB = n
		}
	case "port_range_from":
		if n, err := strconv.Atoi(value); err == nil {
			config.PortRangeFrom = n
		}
	case "port_range_to":
		if n, err := strconv.Atoi(value); err == nil {
			config.PortRangeTo = n
		}
	case "plain_password":
		config.PlainPassword = value == "true"
	case "verbose":
		config.Verbose = value == "true"
	default:
		fmt.Printf("[WARN] Unknown config key: %s\n", key)
	}
}

func setLightKey(key, value string) {
	p := &config.LightProfile
	switch key {
	case "buffer_size":
		p.BufferSize = value
	case "transfers":
		if n, err := strconv.Atoi(value); err == nil {
			p.Transfers = n
		}
	case "checkers":
		if n, err := strconv.Atoi(value); err == nil {
			p.Checkers = n
		}
	case "sftp_concurrency":
		if n, err := strconv.Atoi(value); err == nil {
			p.SFTPConcurrency = n
		}
	case "vfs_cache_mode":
		p.VFSCacheMode = value
	case "timeout":
		p.Timeout = value
	}
}

func setBalancedKey(key, value string) {
	p := &config.BalancedProfile
	switch key {
	case "buffer_size":
		p.BufferSize = value
	case "transfers":
		if n, err := strconv.Atoi(value); err == nil {
			p.Transfers = n
		}
	case "checkers":
		if n, err := strconv.Atoi(value); err == nil {
			p.Checkers = n
		}
	case "sftp_concurrency":
		if n, err := strconv.Atoi(value); err == nil {
			p.SFTPConcurrency = n
		}
	case "vfs_cache_mode":
		p.VFSCacheMode = value
	case "vfs_cache_max_size":
		p.VFSCacheMaxSize = value
	case "vfs_cache_max_age":
		p.VFSCacheMaxAge = value
	case "vfs_read_chunk":
		p.VFSReadChunk = value
	case "vfs_read_ahead":
		p.VFSReadAhead = value
	case "timeout":
		p.Timeout = value
	case "contimeout":
		p.Contimeout = value
	case "low_level_retries":
		if n, err := strconv.Atoi(value); err == nil {
			p.LowLevelRetries = n
		}
	}
}

func setHeavyKey(key, value string) {
	p := &config.HeavyProfile
	switch key {
	case "buffer_size":
		p.BufferSize = value
	case "transfers":
		if n, err := strconv.Atoi(value); err == nil {
			p.Transfers = n
		}
	case "checkers":
		if n, err := strconv.Atoi(value); err == nil {
			p.Checkers = n
		}
	case "sftp_concurrency":
		if n, err := strconv.Atoi(value); err == nil {
			p.SFTPConcurrency = n
		}
	case "vfs_cache_mode":
		p.VFSCacheMode = value
	case "vfs_cache_max_size":
		p.VFSCacheMaxSize = value
	case "vfs_cache_max_age":
		p.VFSCacheMaxAge = value
	case "vfs_read_chunk":
		p.VFSReadChunk = value
	case "vfs_read_ahead":
		p.VFSReadAhead = value
	case "timeout":
		p.Timeout = value
	case "contimeout":
		p.Contimeout = value
	case "low_level_retries":
		if n, err := strconv.Atoi(value); err == nil {
			p.LowLevelRetries = n
		}
	case "max_connections":
		if n, err := strconv.Atoi(value); err == nil {
			p.MaxConnections = n
		}
	}
}

// ==================== সিগন্যাল হ্যান্ডলার ====================

func setupSignalHandler() {
	c := make(chan os.Signal, 1)
	signal.Notify(c, os.Interrupt, syscall.SIGTERM)
	go func() {
		<-c
		fmt.Println("\n[INFO] Signal received, shutting down...")
		stopAllServers()
		os.Exit(0)
	}()
}

// ==================== ইউসেজ ====================

func usage() {
	fmt.Printf("╔════════════════════════════════════════════════════════════╗\n")
	fmt.Printf("║     Rclone SFTP Manager v%-35s║\n", VERSION)
	fmt.Printf("╚════════════════════════════════════════════════════════════╝\n")
	fmt.Print(`
Commands:
  start REMOTE [PORT|auto] USER [PASS] [--password-file FILE] [--profile PROFILE]
  stop REMOTE PORT
  stop-all
  restart REMOTE PORT USER [PASS] [--profile PROFILE]
  status [--json]
  logs REMOTE PORT [LINES]
  check REMOTE PORT
  ports
  health [--json]
  config [KEY=VALUE ...]
  profiles

Profiles:
  light     - Small files, low memory
  balanced  - Medium files, good performance  (DEFAULT)
  heavy     - Large files 100GB+, max performance

Examples:
  rclone-sftp start gdrive auto sumit pass --profile heavy
  rclone-sftp config light
  rclone-sftp config heavy.vfs_cache_max_size=500G heavy.transfers=16
  rclone-sftp profiles
  rclone-sftp health
`)
}

// ==================== মেইন ====================

func parseStartArgs(osArgs []string, defaultProfile string) (pass, passwordFile, profile string) {
	profile = defaultProfile
	for i := 0; i < len(osArgs); i++ {
		switch {
		case osArgs[i] == "--password-file" && i+1 < len(osArgs):
			passwordFile = osArgs[i+1]
			i++
		case osArgs[i] == "--profile" && i+1 < len(osArgs):
			profile = osArgs[i+1]
			i++
		case !strings.HasPrefix(osArgs[i], "--"):
			pass = osArgs[i]
		}
	}
	return
}

func main() {
	setupSignalHandler()

	if len(os.Args) < 2 {
		usage()
		return
	}

	switch os.Args[1] {
	case "start":
		if len(os.Args) < 5 {
			usage()
			return
		}
		pass, pwFile, profile := parseStartArgs(os.Args[5:], config.Profile)
		startServer(os.Args[2], os.Args[3], os.Args[4], pass, pwFile, profile)

	case "stop":
		if len(os.Args) < 4 {
			usage()
			return
		}
		stopServer(os.Args[2], os.Args[3], false)

	case "stop-all":
		stopAllServers()

	case "restart":
		if len(os.Args) < 5 {
			usage()
			return
		}
		pass, pwFile, profile := parseStartArgs(os.Args[5:], config.Profile)
		stopServer(os.Args[2], os.Args[3], true)
		time.Sleep(2 * time.Second)
		startServer(os.Args[2], os.Args[3], os.Args[4], pass, pwFile, profile)

	case "status":
		showStatus(len(os.Args) >= 3 && os.Args[2] == "--json")

	case "logs":
		if len(os.Args) < 4 {
			usage()
			return
		}
		lines := 50
		if len(os.Args) >= 5 {
			if n, err := strconv.Atoi(os.Args[4]); err == nil && n > 0 {
				lines = n
			}
		}
		showLogs(os.Args[2], os.Args[3], lines)

	case "check":
		if len(os.Args) < 4 {
			usage()
			return
		}
		checkServer(os.Args[2], os.Args[3])

	case "ports":
		showPorts()

	case "health":
		healthCheck(len(os.Args) >= 3 && os.Args[2] == "--json")

	case "profiles":
		showProfiles()

	case "config":
		handleConfig(os.Args[2:])

	case "install-service":
		execPath, _ := os.Executable()
		fmt.Printf(`# ~/.bashrc এ যোগ করুন:
alias rclone-sftp="%s"

# ডিরেক্টরি তৈরি:
mkdir -p ~/.local/share/rclone-sftp/{cache,temp,logs,meta}

# ডিফল্ট প্রোফাইল সেট:
%s config balanced
`, execPath, execPath)

	default:
		usage()
	}
}
