package main

import (
	"context"
	"encoding/hex"
	"fmt"
	"net"
	"os"
	"os/signal"
	"runtime/debug"
	"syscall"
	"time"

	"github.com/spf13/cobra"

	"tcp-fuzzer/internal/crash"
	"tcp-fuzzer/internal/distributed"
	"tcp-fuzzer/internal/feedback"
	"tcp-fuzzer/internal/jira"
	"tcp-fuzzer/internal/protocol"
	"tcp-fuzzer/internal/symbolic"
	networkpkg "tcp-fuzzer/pkg/network"
	"tcp-fuzzer/internal/worker"
)

var (
	protoFile     string
	targetHost    string
	targetPort    int
	numWorkers    int
	timeout       time.Duration
	queueDir      string
	crashDir      string
	anomalyDir    string
	baseSeed      int64
	maxTests      uint64
	duration      time.Duration
	enableJira    bool
	jiraURL       string
	jiraUser      string
	jiraToken     string
	jiraProject   string
	jiraComponent string
	jiraAssignee  string
	verbose       bool

	enableSymbolic bool
	perturbProfile string
	customLatency  time.Duration
	customLossRate float64

	masterHost    string
	masterPort    int
	agentName     string
	agentWorkers  int
)

func main() {
	var rootCmd = &cobra.Command{
		Use:   "tcp-fuzzer",
		Short: "TCP协议模糊测试工具 - 针对自定义TCP协议的智能模糊测试",
		Long: `tcp-fuzzer 是一个用于基于TCP的自定义协议模糊测试工具。
支持自定义协议描述（JSON格式），多种变异策略，
AFL-style队列反馈机制，多worker并发，以及JIRA Bug自动上报。
新增功能：符号执行约束求解、网络扰动模拟、分布式master-worker架构。`,
		Run: func(cmd *cobra.Command, args []string) {
			if err := runFuzzer(); err != nil {
				fmt.Fprintf(os.Stderr, "Error: %v\n", err)
				os.Exit(1)
			}
		},
	}

	rootCmd.PersistentFlags().StringVarP(&protoFile, "protocol", "p", "", "协议描述JSON文件路径 (必填)")
	rootCmd.PersistentFlags().StringVarP(&targetHost, "host", "H", "127.0.0.1", "目标主机地址")
	rootCmd.PersistentFlags().IntVarP(&targetPort, "port", "P", 502, "目标端口")
	rootCmd.PersistentFlags().IntVarP(&numWorkers, "workers", "w", 10, "并发worker数量")
	rootCmd.PersistentFlags().DurationVarP(&timeout, "timeout", "t", 5*time.Second, "连接和读写超时")
	rootCmd.PersistentFlags().StringVar(&queueDir, "queue-dir", "queue", "队列种子存储目录")
	rootCmd.PersistentFlags().StringVar(&crashDir, "crash-dir", "crashes", "崩溃样本存储目录")
	rootCmd.PersistentFlags().StringVar(&anomalyDir, "anomaly-dir", "anomalies", "异常样本存储目录")
	rootCmd.PersistentFlags().Int64Var(&baseSeed, "seed", 0, "随机数种子 (0表示使用当前时间)")
	rootCmd.PersistentFlags().Uint64Var(&maxTests, "max-tests", 0, "最大测试次数 (0表示无限制)")
	rootCmd.PersistentFlags().DurationVar(&duration, "duration", 0, "测试持续时间 (0表示无限制)")
	rootCmd.PersistentFlags().BoolVar(&enableJira, "enable-jira", false, "启用JIRA Bug自动上报")
	rootCmd.PersistentFlags().StringVar(&jiraURL, "jira-url", "", "JIRA API基础URL")
	rootCmd.PersistentFlags().StringVar(&jiraUser, "jira-user", "", "JIRA用户名")
	rootCmd.PersistentFlags().StringVar(&jiraToken, "jira-token", "", "JIRA API令牌")
	rootCmd.PersistentFlags().StringVar(&jiraProject, "jira-project", "", "JIRA项目Key")
	rootCmd.PersistentFlags().StringVar(&jiraComponent, "jira-component", "", "JIRA组件名称")
	rootCmd.PersistentFlags().StringVar(&jiraAssignee, "jira-assignee", "", "JIRA经办人")
	rootCmd.PersistentFlags().BoolVarP(&verbose, "verbose", "v", false, "启用详细输出")

	rootCmd.PersistentFlags().BoolVar(&enableSymbolic, "enable-symbolic", false, "启用符号执行约束求解（自动绕过校验和）")
	rootCmd.PersistentFlags().StringVar(&perturbProfile, "perturb-profile", "", "网络扰动配置文件: ideal, wan, cellular_3g, cellular_4g, satellite, lossy, unreliable, throttled")
	rootCmd.PersistentFlags().DurationVar(&customLatency, "perturb-latency", 0, "自定义网络延迟（覆盖profile设置）")
	rootCmd.PersistentFlags().Float64Var(&customLossRate, "perturb-loss-rate", -1, "自定义丢包率0-1（覆盖profile设置，-1表示不覆盖）")

	rootCmd.MarkPersistentFlagRequired("protocol")

	var masterCmd = &cobra.Command{
		Use:   "master",
		Short: "运行分布式Master节点",
		Long: `以Master模式运行，管理分布式Agent节点，分发任务并汇总结果。`,
		Run: func(cmd *cobra.Command, args []string) {
			if err := runMaster(); err != nil {
				fmt.Fprintf(os.Stderr, "Error: %v\n", err)
				os.Exit(1)
			}
		},
	}
	masterCmd.Flags().StringVar(&masterHost, "master-host", "0.0.0.0", "Master监听地址")
	masterCmd.Flags().IntVar(&masterPort, "master-port", 7777, "Master监听端口")

	var agentCmd = &cobra.Command{
		Use:   "agent",
		Short: "运行分布式Agent节点",
		Long: `以Agent模式运行，连接到Master并执行模糊测试任务。`,
		Run: func(cmd *cobra.Command, args []string) {
			if err := runAgent(); err != nil {
				fmt.Fprintf(os.Stderr, "Error: %v\n", err)
				os.Exit(1)
			}
		},
	}
	agentCmd.Flags().StringVar(&masterHost, "master-host", "127.0.0.1", "Master地址")
	agentCmd.Flags().IntVar(&masterPort, "master-port", 7777, "Master端口")
	agentCmd.Flags().StringVar(&agentName, "agent-name", "", "Agent名称（默认自动生成）")
	agentCmd.Flags().IntVar(&agentWorkers, "agent-workers", 10, "Agent的Worker数量")

	rootCmd.AddCommand(masterCmd)
	rootCmd.AddCommand(agentCmd)

	if err := rootCmd.Execute(); err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}
}

func runFuzzer() error {
	fmt.Println("========================================")
	fmt.Println("  TCP协议模糊测试工具 v2.0")
	fmt.Println("========================================")

	fmt.Printf("\n[配置] 协议文件: %s\n", protoFile)
	fmt.Printf("[配置] 目标: %s:%d\n", targetHost, targetPort)
	fmt.Printf("[配置] Worker数量: %d\n", numWorkers)
	fmt.Printf("[配置] 超时: %v\n", timeout)
	if baseSeed == 0 {
		baseSeed = time.Now().UnixNano()
	}
	fmt.Printf("[配置] 随机种子: %d\n", baseSeed)

	if enableJira {
		fmt.Println("[配置] JIRA集成: 已启用")
	}
	if enableSymbolic {
		fmt.Println("[配置] 符号执行引擎: 已启用")
	}
	if perturbProfile != "" {
		fmt.Printf("[配置] 网络扰动: %s\n", perturbProfile)
	}

	proto, err := protocol.LoadProtocolDescription(protoFile)
	if err != nil {
		return fmt.Errorf("加载协议描述失败: %w", err)
	}
	fmt.Printf("[协议] 名称: %s\n", proto.Name)
	fmt.Printf("[协议] 版本: %s\n", proto.Version)
	fmt.Printf("[协议] 最小消息: %d bytes, 最大消息: %d bytes\n", proto.MinMsgSize, proto.MaxMsgSize)

	gen := protocol.NewMessageGenerator(proto, baseSeed)
	initialSeed, err := gen.Generate()
	if err != nil {
		return fmt.Errorf("生成初始种子失败: %w", err)
	}
	fmt.Printf("[种子] 初始种子: %s (%d bytes)\n", hex.EncodeToString(initialSeed[:min(16, len(initialSeed))]), len(initialSeed))

	feedbackQueue, err := feedback.NewQueue(feedback.QueueConfig{
		QueueDir:    queueDir,
		InitialSeed: initialSeed,
		BaseSeed:    baseSeed,
	})
	if err != nil {
		return fmt.Errorf("创建反馈队列失败: %w", err)
	}

	crashRecorder, err := crash.NewRecorder(crash.RecorderConfig{
		CrashDir:    crashDir,
		AnomalyDir:  anomalyDir,
		EnableDedup: true,
		MaxCrashes:  1000,
	})
	if err != nil {
		return fmt.Errorf("创建崩溃记录器失败: %w", err)
	}

	var jiraClient *jira.Client
	if enableJira {
		jiraClient, err = jira.NewClient(jira.Config{
			BaseURL:    jiraURL,
			Username:   jiraUser,
			APIToken:   jiraToken,
			ProjectKey: jiraProject,
			Component:  jiraComponent,
			Assignee:   jiraAssignee,
			Labels:     []string{"fuzzing", "security"},
		})
		if err != nil {
			return fmt.Errorf("创建JIRA客户端失败: %w", err)
		}

		if err := jiraClient.TestConnection(); err != nil {
			fmt.Printf("[警告] JIRA连接测试失败: %v\n", err)
			fmt.Println("[警告] 将继续模糊测试，但不会自动上报Bug")
			jiraClient = nil
		} else {
			fmt.Println("[JIRA] 连接测试成功")
		}
	}

	var symbolicEngine *symbolic.Engine
	if enableSymbolic {
		symbolicEngine = symbolic.NewEngine(symbolic.EngineConfig{
			Proto:    proto,
			BaseSeed: baseSeed,
		})
		fmt.Println("[符号引擎] 约束求解引擎已初始化")
	}

	var perturbConfig *networkpkg.PerturbationConfig
	if perturbProfile != "" {
		perturbConfig = networkpkg.GetPerturbationProfile(perturbProfile)
		if perturbConfig == nil {
			return fmt.Errorf("无效的扰动配置文件: %s", perturbProfile)
		}
		if customLatency > 0 {
			perturbConfig.BaseLatency = customLatency
		}
		if customLossRate >= 0 && customLossRate <= 1 {
			perturbConfig.LossRate = customLossRate
		}
		fmt.Printf("[网络扰动] 配置: %s, 延迟: %v, 丢包率: %.2f%%\n",
			perturbProfile, perturbConfig.BaseLatency, perturbConfig.LossRate*100)
	}

	workerPool, err := worker.NewWorkerPool(worker.WorkerPoolConfig{
		NumWorkers:     numWorkers,
		TargetHost:     targetHost,
		TargetPort:     targetPort,
		Timeout:        timeout,
		Proto:          proto,
		FeedbackQueue:  feedbackQueue,
		CrashRecorder:  crashRecorder,
		SymbolicEngine: symbolicEngine,
		PerturbConfig:  perturbConfig,
		BaseSeed:       baseSeed,
	})
	if err != nil {
		return fmt.Errorf("创建Worker池失败: %w", err)
	}

	ctx, cancel := context.WithCancel(context.Background())
	if duration > 0 {
		ctx, cancel = context.WithTimeout(ctx, duration)
		defer cancel()
	}

	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		sig := <-sigChan
		fmt.Printf("\n[信号] 收到信号: %v, 正在停止...\n", sig)
		cancel()
	}()

	fmt.Println("\n========================================")
	fmt.Println("  开始模糊测试...")
	fmt.Println("========================================")
	fmt.Println("  按 Ctrl+C 停止测试")
	fmt.Println()

	workerPool.Start(ctx)

	go func() {
		ticker := time.NewTicker(5 * time.Second)
		defer ticker.Stop()

		var lastTotalTests uint64
		startTime := time.Now()

		for {
			select {
			case <-ctx.Done():
				return
			case <-ticker.C:
				totalStats := workerPool.TotalStats()
				queueEntries, totalTests, totalPaths := feedbackQueue.Stats()
				numCrashes, numAnomalies := crashRecorder.Stats()

				elapsed := time.Since(startTime)
				testsPerSec := float64(totalTests-lastTotalTests) / 5.0
				lastTotalTests = totalTests

				symbolicStr := ""
				if enableSymbolic {
					symbolicStr = "  [符号:开]"
				}
				perturbStr := ""
				if perturbProfile != "" {
					perturbStr = fmt.Sprintf("  [扰动:%s]", perturbProfile)
				}

				fmt.Printf("\r[状态] 时间: %-10s  测试: %-10d  速率: %-8.1f/s  崩溃: %-4d  异常: %-4d  路径: %-6d  队列: %-6d  发送: %.1fMB%s%s",
					formatDuration(elapsed),
					totalTests,
					testsPerSec,
					numCrashes,
					numAnomalies,
					totalPaths,
					queueEntries,
					float64(totalStats.BytesSent)/1024/1024,
					symbolicStr,
					perturbStr,
				)

				if maxTests > 0 && totalTests >= maxTests {
					fmt.Println("\n[完成] 达到最大测试次数")
					cancel()
					return
				}

				if jiraClient != nil {
					go reportUnreportedCrashes(jiraClient, crashRecorder)
				}
			}
		}
	}()

	<-ctx.Done()
	fmt.Println("\n\n========================================")
	fmt.Println("  正在停止Worker...")
	fmt.Println("========================================")

	workerPool.Stop()

	totalStats := workerPool.TotalStats()
	queueEntries, totalTests, totalPaths := feedbackQueue.Stats()
	numCrashes, numAnomalies := crashRecorder.Stats()

	fmt.Println("\n========================================")
	fmt.Println("  模糊测试完成")
	fmt.Println("========================================")
	fmt.Printf("总测试次数:     %d\n", totalTests)
	fmt.Printf("总执行时间:     %s\n", formatDuration(time.Since(time.Unix(0, baseSeed))))
	fmt.Printf("发现崩溃:       %d\n", numCrashes)
	fmt.Printf("发现异常:       %d\n", numAnomalies)
	fmt.Printf("发现路径:       %d\n", totalPaths)
	fmt.Printf("队列大小:       %d\n", queueEntries)
	fmt.Printf("发送数据:       %.2f MB\n", float64(totalStats.BytesSent)/1024/1024)
	fmt.Printf("接收数据:       %.2f MB\n", float64(totalStats.BytesReceived)/1024/1024)

	summaryPath := "fuzzing_summary.txt"
	if err := crashRecorder.WriteSummary(summaryPath); err != nil {
		fmt.Fprintf(os.Stderr, "\n[警告] 写入摘要失败: %v\n", err)
	} else {
		fmt.Printf("\n摘要已保存到:   %s\n", summaryPath)
	}

	if jiraClient != nil {
		reportUnreportedCrashes(jiraClient, crashRecorder)
	}

	if numCrashes > 0 {
		fmt.Printf("\n崩溃样本目录:   %s/\n", crashDir)
	}
	if numAnomalies > 0 {
		fmt.Printf("异常样本目录:   %s/\n", anomalyDir)
	}

	return nil
}

func runMaster() error {
	fmt.Println("========================================")
	fmt.Println("  分布式Master节点 v2.0")
	fmt.Println("========================================")

	masterAddr := fmt.Sprintf("%s:%d", masterHost, masterPort)
	fmt.Printf("\n[Master] 监听地址: %s\n", masterAddr)

	master, err := distributed.NewMaster(distributed.MasterConfig{
		ListenAddr:  masterAddr,
		MaxTasks:    100,
		MaxAgents:   50,
		QueueDir:    queueDir,
		CrashDir:    crashDir,
		AnomalyDir:  anomalyDir,
	})
	if err != nil {
		return fmt.Errorf("创建Master失败: %w", err)
	}

	master.OnAgentRegister = func(agent *distributed.AgentInfo) {
		fmt.Printf("\n[Master] Agent注册: %s (%s)\n", agent.Name, agent.Address)
	}

	master.OnAgentDisconnect = func(agent *distributed.AgentInfo) {
		fmt.Printf("\n[Master] Agent断开: %s (%s)\n", agent.Name, agent.Address)
	}

	master.OnTaskComplete = func(result *distributed.TaskResult) {
		fmt.Printf("\n[Master] 任务完成: %s, 测试: %d, 崩溃: %d\n",
			result.TaskID, result.TestsExecuted, result.CrashesFound)
	}

	master.OnCrashReported = func(report *distributed.CrashReport) {
		fmt.Printf("\n[Master] 收到Crash报告: Agent=%s, Type=%s\n",
			report.AgentID, report.CrashType)
	}

	ctx, cancel := context.WithCancel(context.Background())

	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		sig := <-sigChan
		fmt.Printf("\n[信号] 收到信号: %v, 正在停止...\n", sig)
		cancel()
	}()

	if enableJira {
		jiraClient, err := jira.NewClient(jira.Config{
			BaseURL:    jiraURL,
			Username:   jiraUser,
			APIToken:   jiraToken,
			ProjectKey: jiraProject,
			Component:  jiraComponent,
			Assignee:   jiraAssignee,
			Labels:     []string{"fuzzing", "security", "distributed"},
		})
		if err != nil {
			fmt.Printf("[警告] 创建JIRA客户端失败: %v\n", err)
		} else if err := jiraClient.TestConnection(); err != nil {
			fmt.Printf("[警告] JIRA连接测试失败: %v\n", err)
		} else {
			fmt.Println("[JIRA] 连接测试成功")
			master.OnCrashReported = func(report *distributed.CrashReport) {
				fmt.Printf("\n[Master] 收到Crash报告: Agent=%s, Type=%s\n",
					report.AgentID, report.CrashType)
				entry := crash.CrashEntry{
					ID:         fmt.Sprintf("%s-%d", report.AgentID, report.Timestamp.Unix()),
					Timestamp:  report.Timestamp,
					Input:      report.Input,
					Output:     report.Output,
					CrashType:  report.CrashType,
					StackTrace: report.StackTrace,
					Strategy:   report.Strategy,
				}
				go func() {
					key, err := jiraClient.CreateBugFromCrash(entry)
					if err != nil {
						fmt.Printf("[警告] JIRA Bug创建失败: %v\n", err)
					} else {
						fmt.Printf("[JIRA] 已创建Bug: %s\n", key)
					}
				}()
			}
		}
	}

	if protoFile != "" {
		protoData, err := os.ReadFile(protoFile)
		if err != nil {
			return fmt.Errorf("读取协议文件失败: %w", err)
		}

		task := &distributed.Task{
			ProtocolData:   protoData,
			Target:         fmt.Sprintf("%s:%d", targetHost, targetPort),
			TimeoutSeconds: int(timeout.Seconds()),
			MaxTests:       maxTests,
			WorkerCount:    numWorkers,
			PerturbProfile: perturbProfile,
			EnableSymbolic: enableSymbolic,
		}

		if err := master.SubmitTask(task); err != nil {
			fmt.Printf("[警告] 任务提交失败: %v\n", err)
		} else {
			fmt.Printf("[Master] 任务已提交: %s\n", task.ID)
		}
	}

	go func() {
		ticker := time.NewTicker(10 * time.Second)
		defer ticker.Stop()

		for {
			select {
			case <-ctx.Done():
				return
			case <-ticker.C:
				status := master.GetStatus()
				fmt.Printf("\r[Master] Agent数: %d/%d  任务队列: %d/%d  总崩溃: %d",
					status.ActiveAgents, status.TotalAgents,
					status.PendingTasks, status.TotalTasks,
					status.TotalCrashes)
			}
		}
	}()

	fmt.Println("\n========================================")
	fmt.Println("  Master已启动，等待Agent连接...")
	fmt.Println("========================================")

	if err := master.Start(ctx); err != nil {
		return fmt.Errorf("Master运行失败: %w", err)
	}

	master.Shutdown()
	fmt.Println("\n[Master] 已停止")
	return nil
}

func runAgent() error {
	fmt.Println("========================================")
	fmt.Println("  分布式Agent节点 v2.0")
	fmt.Println("========================================")

	masterAddr := fmt.Sprintf("%s:%d", masterHost, masterPort)
	fmt.Printf("\n[Agent] Master地址: %s\n", masterAddr)
	fmt.Printf("[Agent] Worker数量: %d\n", agentWorkers)

	if agentName == "" {
		hostname, _ := os.Hostname()
		agentName = fmt.Sprintf("agent-%s", hostname)
	}
	fmt.Printf("[Agent] 名称: %s\n", agentName)

	conn, err := net.DialTimeout("tcp", masterAddr, 5*time.Second)
	if err != nil {
		return fmt.Errorf("连接Master失败: %w", err)
	}
	defer conn.Close()

	agent, err := distributed.NewAgent(distributed.AgentConfig{
		Name:        agentName,
		MasterAddr:  masterAddr,
		WorkerCount: agentWorkers,
		Timeout:     timeout,
		BaseSeed:    baseSeed,
		QueueDir:    queueDir,
		CrashDir:    crashDir,
		AnomalyDir:  anomalyDir,
	})
	if err != nil {
		return fmt.Errorf("创建Agent失败: %w", err)
	}

	ctx, cancel := context.WithCancel(context.Background())

	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		sig := <-sigChan
		fmt.Printf("\n[信号] 收到信号: %v, 正在停止...\n", sig)
		cancel()
	}()

	fmt.Println("\n========================================")
	fmt.Println("  Agent已启动，等待任务...")
	fmt.Println("========================================")

	if err := agent.Run(ctx); err != nil {
		return fmt.Errorf("Agent运行失败: %w", err)
	}

	fmt.Println("\n[Agent] 已停止")
	return nil
}

func reportUnreportedCrashes(jiraClient *jira.Client, recorder *crash.Recorder) {
	defer func() {
		if r := recover(); r != nil {
			fmt.Fprintf(os.Stderr, "\n[警告] JIRA上报异常: %v\nStack trace:\n%s\n", r, debug.Stack())
		}
	}()

	unreported := recorder.GetUnreportedCrashes()
	for _, crashEntry := range unreported {
		jiraKey, err := jiraClient.CreateBugFromCrash(crashEntry)
		if err != nil {
			fmt.Fprintf(os.Stderr, "\n[警告] 创建JIRA Bug失败 (crash %s): %v\n", crashEntry.ID[:8], err)
			continue
		}

		binFilename := fmt.Sprintf("crash_input_%s.bin", crashEntry.ID[:8])
		if err := jiraClient.AddAttachment(jiraKey, binFilename, crashEntry.Input); err != nil {
			fmt.Fprintf(os.Stderr, "\n[警告] 添加附件失败: %v\n", err)
		}

		recorder.MarkAsReported(crashEntry.ID, jiraKey)
		fmt.Printf("\n[JIRA] 已创建Bug: %s (crash ID: %s)\n", jiraKey, crashEntry.ID[:8])
	}
}

func formatDuration(d time.Duration) string {
	hours := int(d.Hours())
	minutes := int(d.Minutes()) % 60
	seconds := int(d.Seconds()) % 60
	if hours > 0 {
		return fmt.Sprintf("%02d:%02d:%02d", hours, minutes, seconds)
	}
	return fmt.Sprintf("%02d:%02d", minutes, seconds)
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
