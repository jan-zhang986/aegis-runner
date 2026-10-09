package main

import (
	"bufio"
	"crypto/sha1"
	"encoding/base64"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"sync"
)

const wsMagicGUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

// Message 统一广播消息结构
type Message struct {
	Type    string `json:"type"`              // "event" | "stdout" | "stderr" | "system"
	Payload any    `json:"payload"`           // 结构化数据
	RunID   string `json:"runId,omitempty"`   // 执行批次 ID
}

// Hub 管理所有 WebSocket 与 SSE 连接客户端
type Hub struct {
	mu         sync.RWMutex
	wsClients  map[net.Conn]bool
	sseClients map[chan []byte]bool
}

func NewHub() *Hub {
	return &Hub{
		wsClients:  make(map[net.Conn]bool),
		sseClients: make(map[chan []byte]bool),
	}
}

// Broadcast 广播消息到所有已连接的 Web 客户端
func (h *Hub) Broadcast(msgType string, payload any, runID string) {
	msg := Message{
		Type:    msgType,
		Payload: payload,
		RunID:   runID,
	}
	data, err := json.Marshal(msg)
	if err != nil {
		return
	}

	h.mu.Lock()
	defer h.mu.Unlock()

	// 1. 发送给 WebSocket 客户端
	for conn := range h.wsClients {
		if err := sendWebSocketFrame(conn, data); err != nil {
			conn.Close()
			delete(h.wsClients, conn)
		}
	}

	// 2. 发送给 SSE 客户端
	for ch := range h.sseClients {
		select {
		case ch <- data:
		default:
			// 避免慢客户端阻塞
		}
	}
}

// HandleWebSocket 处理浏览器 WebSocket 握手与连接 (标准 RFC 6455 零外部依赖实现)
func (h *Hub) HandleWebSocket(w http.ResponseWriter, r *http.Request) {
	if r.Header.Get("Upgrade") != "websocket" {
		http.Error(w, "Expected WebSocket Upgrade", http.StatusBadRequest)
		return
	}

	key := r.Header.Get("Sec-WebSocket-Key")
	if key == "" {
		http.Error(w, "Missing Sec-WebSocket-Key", http.StatusBadRequest)
		return
	}

	h1 := sha1.New()
	h1.Write([]byte(key + wsMagicGUID))
	acceptKey := base64.StdEncoding.EncodeToString(h1.Sum(nil))

	hj, ok := w.(http.Hijacker)
	if !ok {
		http.Error(w, "Webserver doesn't support hijacking", http.StatusInternalServerError)
		return
	}

	conn, bufrw, err := hj.Hijack()
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	// 写入 101 Switching Protocols 握手响应
	handshake := fmt.Sprintf("HTTP/1.1 101 Switching Protocols\r\n"+
		"Upgrade: websocket\r\n"+
		"Connection: Upgrade\r\n"+
		"Sec-WebSocket-Accept: %s\r\n\r\n", acceptKey)
	bufrw.WriteString(handshake)
	bufrw.Flush()

	h.mu.Lock()
	h.wsClients[conn] = true
	h.mu.Unlock()

	// 发送初始连接成功提示
	welcome, _ := json.Marshal(Message{
		Type:    "system",
		Payload: map[string]string{"message": "Connected to Aegis Local Companion WebSocket (127.0.0.1:8989)"},
	})
	_ = sendWebSocketFrame(conn, welcome)

	// 循环监听客户端断开或 Ping/Pong
	go func() {
		defer func() {
			h.mu.Lock()
			delete(h.wsClients, conn)
			h.mu.Unlock()
			conn.Close()
		}()

		reader := bufio.NewReader(conn)
		for {
			_, err := readWebSocketFrame(reader)
			if err != nil {
				break
			}
		}
	}()
}

// HandleSSE 处理 Server-Sent Events 流式端点
func (h *Hub) HandleSSE(w http.ResponseWriter, r *http.Request) {
	flusher, ok := w.(http.Flusher)
	if !ok {
		http.Error(w, "Streaming unsupported", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	w.Header().Set("Access-Control-Allow-Origin", "*")

	msgChan := make(chan []byte, 32)
	h.mu.Lock()
	h.sseClients[msgChan] = true
	h.mu.Unlock()

	defer func() {
		h.mu.Lock()
		delete(h.sseClients, msgChan)
		h.mu.Unlock()
	}()

	// 初始握手
	fmt.Fprintf(w, "data: {\"type\":\"system\",\"payload\":\"SSE Connected\"}\n\n")
	flusher.Flush()

	notify := r.Context().Done()
	for {
		select {
		case <-notify:
			return
		case data := <-msgChan:
			fmt.Fprintf(w, "data: %s\n\n", string(data))
			flusher.Flush()
		}
	}
}

// sendWebSocketFrame 向客户端发送 Unmasked 文本帧 (RFC 6455)
func sendWebSocketFrame(conn net.Conn, payload []byte) error {
	length := len(payload)
	header := []byte{0x81} // FIN + Text opcode (0x1)

	if length <= 125 {
		header = append(header, byte(length))
	} else if length <= 65535 {
		header = append(header, 126)
		b := make([]byte, 2)
		binary.BigEndian.PutUint16(b, uint16(length))
		header = append(header, b...)
	} else {
		header = append(header, 127)
		b := make([]byte, 8)
		binary.BigEndian.PutUint64(b, uint64(length))
		header = append(header, b...)
	}

	if _, err := conn.Write(header); err != nil {
		return err
	}
	_, err := conn.Write(payload)
	return err
}

// readWebSocketFrame 解析客户端发来的 Masked 帧
func readWebSocketFrame(r *bufio.Reader) ([]byte, error) {
	b1, err := r.ReadByte()
	if err != nil {
		return nil, err
	}
	opcode := b1 & 0x0f
	if opcode == 0x8 { // Connection close
		return nil, io.EOF
	}

	b2, err := r.ReadByte()
	if err != nil {
		return nil, err
	}
	isMasked := (b2 & 0x80) != 0
	length := int(b2 & 0x7f)

	if length == 126 {
		var l uint16
		if err := binary.Read(r, binary.BigEndian, &l); err != nil {
			return nil, err
		}
		length = int(l)
	} else if length == 127 {
		var l uint64
		if err := binary.Read(r, binary.BigEndian, &l); err != nil {
			return nil, err
		}
		length = int(l)
	}

	var mask [4]byte
	if isMasked {
		if _, err := io.ReadFull(r, mask[:]); err != nil {
			return nil, err
		}
	}

	payload := make([]byte, length)
	if _, err := io.ReadFull(r, payload); err != nil {
		return nil, err
	}

	if isMasked {
		for i := 0; i < length; i++ {
			payload[i] ^= mask[i%4]
		}
	}

	return payload, nil
}
