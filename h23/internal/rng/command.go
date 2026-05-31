package rng

import (
	"bufio"
	"fmt"
	"io"
	"os/exec"
	"strings"
)

type CommandRNG struct {
	command string
	args    []string
	cmd     *exec.Cmd
	stdout  io.ReadCloser
	reader  *bufio.Reader
}

func NewCommandRNG(command string) (*CommandRNG, error) {
	parts := strings.Fields(command)
	if len(parts) == 0 {
		return nil, fmt.Errorf("empty command")
	}

	return &CommandRNG{
		command: parts[0],
		args:    parts[1:],
	}, nil
}

func (r *CommandRNG) Start() error {
	cmd := exec.Command(r.command, r.args...)
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return err
	}

	if err := cmd.Start(); err != nil {
		return err
	}

	r.cmd = cmd
	r.stdout = stdout
	r.reader = bufio.NewReader(stdout)
	return nil
}

func (r *CommandRNG) ReadBits(n int) ([]int, error) {
	bits := make([]int, 0, n)
	buffer := make([]byte, (n+7)/8)

	totalRead := 0
	for totalRead < len(buffer) {
		nRead, err := r.reader.Read(buffer[totalRead:])
		if err != nil {
			if err == io.EOF && totalRead > 0 {
				break
			}
			return nil, err
		}
		totalRead += nRead
	}

	for i := 0; i < totalRead && len(bits) < n; i++ {
		for j := 7; j >= 0 && len(bits) < n; j-- {
			bit := (int(buffer[i]) >> uint(j)) & 1
			bits = append(bits, bit)
		}
	}

	return bits, nil
}

func (r *CommandRNG) ReadAllBits(maxBits int) ([]int, error) {
	bits := make([]int, 0, maxBits)
	buffer := make([]byte, 4096)

	for {
		nRead, err := r.reader.Read(buffer)
		if err != nil {
			if err == io.EOF {
				break
			}
			return nil, err
		}

		for i := 0; i < nRead; i++ {
			for j := 7; j >= 0; j-- {
				bit := (int(buffer[i]) >> uint(j)) & 1
				bits = append(bits, bit)
				if len(bits) >= maxBits {
					return bits, nil
				}
			}
		}
	}

	return bits, nil
}

func (r *CommandRNG) Stop() error {
	if r.cmd != nil && r.cmd.Process != nil {
		if err := r.cmd.Process.Kill(); err != nil {
			return err
		}
		return r.cmd.Wait()
	}
	return nil
}
