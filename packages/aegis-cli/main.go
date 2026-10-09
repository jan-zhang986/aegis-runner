package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"syscall"
	"time"
)

const Version = "1.1.0"

func printBanner(addr string) {
	fmt.Printf("\033[36m" + `
   ___    ______ _____ _____ ____       ________    ____
  /   |  / ____// ___//  _// ___/      / ____/ /   /  _/
 / /| | / __/  / __ \ / /  \__ \ _____/ /   / /    / /  
/ ___ |/ /___ / /_/ // /  ___/ //_____/ /___/ /____/ /   
/_/  |_/_____/ \____/___/ /____/       \____/_____/___/   
` + "\033[0m")
	fmt.Println("  Aegis Test-as-Code Local Companion Daemon v" + Version)
	fmt.Println("  -------------------------------------------------------------")
	fmt.Printf("  📡 HTTP/WS Server:  \033[32mhttp://%s\033[0m\n", addr)
	fmt.Printf("  🔌 WebSocket URL:   \033[32mws://%s/ws\033[0m\n", addr)
	fmt.Printf("  🌊 SSE Stream:      \033[32mhttp://%s/api/v1/stream\033[0m\n", addr)
	fmt.Printf("  📥 Event Receiver:  \033[32mhttp://%s/api/v1/events\033[0m\n", addr)
	fmt.Printf("  🏃 Task Runner:     \033[32mhttp://%s/api/v1/run\033[0m\n", addr)
	fmt.Println("  -------------------------------------------------------------")
	fmt.Println("  Ready to receive test executions from Web QA Studio IDE.")
	fmt.Println("  Press Ctrl+C to stop.")
	fmt.Println()
}

func main() {
	if len(os.Args) > 1 {
		subcmd := os.Args[1]
		if subcmd == "scaffold" || subcmd == "scan" || subcmd == "diff" || subcmd == "run" {
			execHarnessSubcommand(subcmd, os.Args[2:])
			return
		}
	}

	addrFlag := flag.String("addr", "127.0.0.1:8989", "Local Companion 监听地址与端口")
	versionFlag := flag.Bool("v", false, "查看版本号")
	flag.BoolVar(versionFlag, "version", false, "查看版本号")
	flag.Parse()

	if *versionFlag {
		fmt.Printf("aegis-cli version %s\n", Version)
		return
	}

	hub := NewHub()
	pm := NewProcessManager(hub)
	server := NewServer(hub, pm)

	httpServer := &http.Server{
		Addr:         *addrFlag,
		Handler:      server.SetupRoutes(),
		ReadTimeout:  15 * time.Second,
		WriteTimeout: 0, // 允许长期 WebSocket/SSE 长连接保持
	}

	printBanner(*addrFlag)

	// 优雅关机监听
	stopChan := make(chan os.Signal, 1)
	signal.Notify(stopChan, os.Interrupt, syscall.SIGTERM)

	go func() {
		if err := httpServer.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("Fatal error starting server: %v", err)
		}
	}()

	<-stopChan
	fmt.Println("\n⏹ Shutting down Aegis Local Companion gracefully...")

	// 停止可能仍在运行的任务
	pm.StopActiveTask()

	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()

	if err := httpServer.Shutdown(ctx); err != nil {
		log.Printf("Server shutdown error: %v", err)
	}
	fmt.Println("👋 Local Companion stopped.")
}

func execHarnessSubcommand(subcmd string, args []string) {
	pythonCmd := "python3"
	if p := os.Getenv("PYTHON_PATH"); p != "" {
		pythonCmd = p
	}

	// 智能定位 runner 源码目录
	exePath, err := os.Executable()
	defaultSrcDir := "/Users/zhangjian/vanguard-platform/aegis-runner/src"
	if err == nil {
		candidate := filepath.Clean(filepath.Join(filepath.Dir(exePath), "..", "..", "src"))
		if fi, err := os.Stat(candidate); err == nil && fi.IsDir() {
			defaultSrcDir = candidate
		}
	}
	sdkDir := filepath.Clean(filepath.Join(defaultSrcDir, "..", "packages", "aegis-sdk"))

	currPythonPath := os.Getenv("PYTHONPATH")
	newPythonPath := defaultSrcDir + ":" + sdkDir
	if currPythonPath != "" {
		newPythonPath = newPythonPath + ":" + currPythonPath
	}

	cmdArgs := append([]string{"-m", "runner.harness_cli", subcmd}, args...)
	cmd := exec.Command(pythonCmd, cmdArgs...)
	cmd.Stdin = os.Stdin
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	cmd.Env = append(os.Environ(), "PYTHONPATH="+newPythonPath)

	if err := cmd.Run(); err != nil {
		if exitErr, ok := err.(*exec.ExitError); ok {
			os.Exit(exitErr.ExitCode())
		}
		os.Exit(1)
	}
}
