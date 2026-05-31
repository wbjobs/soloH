package tcp

import (
	"fmt"
	"net"
	"sync"
	"time"
)

type ConnectionPool struct {
	host        string
	port        int
	maxConns    int
	connections chan net.Conn
	mu          sync.Mutex
	created     int
	timeout     time.Duration
}

type Config struct {
	Host        string
	Port        int
	MaxConns    int
	Timeout     time.Duration
	DialTimeout time.Duration
}

func NewConnectionPool(cfg Config) (*ConnectionPool, error) {
	if cfg.MaxConns <= 0 {
		cfg.MaxConns = 10
	}
	if cfg.Timeout <= 0 {
		cfg.Timeout = 30 * time.Second
	}
	if cfg.DialTimeout <= 0 {
		cfg.DialTimeout = 5 * time.Second
	}

	pool := &ConnectionPool{
		host:        cfg.Host,
		port:        cfg.Port,
		maxConns:    cfg.MaxConns,
		connections: make(chan net.Conn, cfg.MaxConns),
		timeout:     cfg.Timeout,
	}

	return pool, nil
}

func (p *ConnectionPool) Get() (net.Conn, error) {
	select {
	case conn := <-p.connections:
		if p.isConnAlive(conn) {
			return conn, nil
		}
		conn.Close()
		p.mu.Lock()
		p.created--
		p.mu.Unlock()
		return p.createNew()
	default:
		p.mu.Lock()
		if p.created < p.maxConns {
			p.mu.Unlock()
			return p.createNew()
		}
		p.mu.Unlock()
		select {
		case conn := <-p.connections:
			if p.isConnAlive(conn) {
				return conn, nil
			}
			conn.Close()
			p.mu.Lock()
			p.created--
			p.mu.Unlock()
			return p.createNew()
		case <-time.After(p.timeout):
			return nil, fmt.Errorf("timeout waiting for connection")
		}
	}
}

func (p *ConnectionPool) Put(conn net.Conn) error {
	if conn == nil {
		return nil
	}
	if !p.isConnAlive(conn) {
		conn.Close()
		p.mu.Lock()
		p.created--
		p.mu.Unlock()
		return nil
	}
	select {
	case p.connections <- conn:
		return nil
	default:
		p.mu.Lock()
		p.created--
		p.mu.Unlock()
		return conn.Close()
	}
}

func (p *ConnectionPool) createNew() (net.Conn, error) {
	addr := fmt.Sprintf("%s:%d", p.host, p.port)
	conn, err := net.DialTimeout("tcp", addr, p.timeout)
	if err != nil {
		return nil, fmt.Errorf("failed to connect to %s: %w", addr, err)
	}
	p.mu.Lock()
	p.created++
	p.mu.Unlock()
	return conn, nil
}

func (p *ConnectionPool) isConnAlive(conn net.Conn) bool {
	if conn == nil {
		return false
	}
	conn.SetReadDeadline(time.Now().Add(1 * time.Millisecond))
	one := make([]byte, 1)
	_, err := conn.Read(one)
	if err != nil {
		if netErr, ok := err.(net.Error); ok && netErr.Timeout() {
			var zero time.Time
			conn.SetReadDeadline(zero)
			return true
		}
		return false
	}
	var zero time.Time
	conn.SetReadDeadline(zero)
	return true
}

func (p *ConnectionPool) Close() error {
	p.mu.Lock()
	defer p.mu.Unlock()

	close(p.connections)
	for conn := range p.connections {
		if conn != nil {
			conn.Close()
		}
	}
	p.created = 0
	p.connections = make(chan net.Conn, p.maxConns)
	return nil
}

func (p *ConnectionPool) Stats() (available, created, max int) {
	p.mu.Lock()
	defer p.mu.Unlock()
	return len(p.connections), p.created, p.maxConns
}

type TCPClient struct {
	conn    net.Conn
	timeout time.Duration
}

func NewTCPClient(conn net.Conn, timeout time.Duration) *TCPClient {
	return &TCPClient{
		conn:    conn,
		timeout: timeout,
	}
}

func (c *TCPClient) Send(data []byte) error {
	if c.conn == nil {
		return fmt.Errorf("connection is nil")
	}
	c.conn.SetWriteDeadline(time.Now().Add(c.timeout))
	_, err := c.conn.Write(data)
	if err != nil {
		return fmt.Errorf("failed to send data: %w", err)
	}
	return nil
}

func (c *TCPClient) Receive(maxSize int) ([]byte, error) {
	if c.conn == nil {
		return nil, fmt.Errorf("connection is nil")
	}
	c.conn.SetReadDeadline(time.Now().Add(c.timeout))
	buf := make([]byte, maxSize)
	n, err := c.conn.Read(buf)
	if err != nil {
		return nil, fmt.Errorf("failed to receive data: %w", err)
	}
	return buf[:n], nil
}

func (c *TCPClient) SendReceive(data []byte, maxRespSize int) ([]byte, error) {
	if err := c.Send(data); err != nil {
		return nil, err
	}
	return c.Receive(maxRespSize)
}

func (c *TCPClient) Close() error {
	if c.conn != nil {
		return c.conn.Close()
	}
	return nil
}

func (c *TCPClient) RawConn() net.Conn {
	return c.conn
}
