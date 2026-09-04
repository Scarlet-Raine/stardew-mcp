using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.WebSockets;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using StardewModdingAPI;

namespace StardewMCP;

/// <summary>
/// WebSocket server for communication with the AI bridge, built on System.Net.WebSockets.
/// Replaces the WebSocketSharp dependency, which is not thread-safe and drops connections
/// on bidirectional messaging.
/// </summary>
public class WebSocketServer
{
    private readonly IMonitor _monitor;
    private readonly GameStateSerializer _stateSerializer;
    private readonly CommandExecutor _commandExecutor;

    private HttpListener? _listener;
    private CancellationTokenSource _cts = new();
    private Task? _acceptLoop;

    private readonly ConcurrentDictionary<System.Net.WebSockets.WebSocket, int> _clients = new();
    private readonly ConcurrentDictionary<System.Net.WebSockets.WebSocket, SemaphoreSlim> _sendLocks = new();

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        PropertyNameCaseInsensitive = true
    };

    public WebSocketServer(IMonitor monitor, GameStateSerializer stateSerializer, CommandExecutor commandExecutor)
    {
        _monitor = monitor;
        _stateSerializer = stateSerializer;
        _commandExecutor = commandExecutor;
    }

    public void Start(int port)
    {
        try
        {
            _listener = new HttpListener();
            _listener.Prefixes.Add($"http://localhost:{port}/");
            _listener.Start();
            _cts = new CancellationTokenSource();
            _acceptLoop = Task.Run(() => AcceptLoop(_cts.Token));
            _monitor.Log($"WebSocket server started on ws://localhost:{port}/game", LogLevel.Info);
        }
        catch (Exception ex)
        {
            _monitor.Log($"Failed to start WebSocket server: {ex.Message}", LogLevel.Error);
        }
    }

    public void Stop()
    {
        _cts.Cancel();
        foreach (var ws in _clients.Keys.ToList())
        {
            try { ws.Abort(); } catch { /* ignore */ }
        }
        _clients.Clear();
        foreach (var sem in _sendLocks.Values)
        {
            try { sem.Dispose(); } catch { /* ignore */ }
        }
        _sendLocks.Clear();
        try { _listener?.Stop(); } catch { /* ignore */ }
        _listener?.Close();
    }

    /// <summary>Broadcast the current game state to all connected clients (called every second).</summary>
    public void BroadcastState()
    {
        string json = GetStateJson();
        foreach (var ws in _clients.Keys.ToList())
            _ = SendLoop(ws, json);
    }

    // ------------------------------------------------------------------ //
    // Networking
    // ------------------------------------------------------------------ //
    private async Task AcceptLoop(CancellationToken ct)
    {
        while (!ct.IsCancellationRequested)
        {
            try
            {
                var context = await _listener!.GetContextAsync().ConfigureAwait(false);
                _ = Task.Run(() => HandleContext(context, ct));
            }
            catch (Exception ex)
            {
                _monitor.Log($"WebSocket accept error: {ex.Message}", LogLevel.Debug);
                if (ct.IsCancellationRequested)
                    break;
            }
        }
    }

    private async Task HandleContext(HttpListenerContext context, CancellationToken ct)
    {
        if (!context.Request.IsWebSocketRequest)
        {
            context.Response.StatusCode = 400;
            context.Response.Close();
            return;
        }

        try
        {
            var socketContext = await context.AcceptWebSocketAsync(null).ConfigureAwait(false);
            {
                var socket = socketContext.WebSocket;
                _clients.TryAdd(socket, 0);
                _sendLocks.TryAdd(socket, new SemaphoreSlim(1, 1));
                _monitor.Log("Client connected to WebSocket", LogLevel.Info);
                try
                {
                    await SendLoop(socket, GetStateJson()).ConfigureAwait(false);
                    await ReceiveLoop(socket, ct).ConfigureAwait(false);
                }
                finally
                {
                    _clients.TryRemove(socket, out _);
                    if (_sendLocks.TryRemove(socket, out var sem))
                        sem.Dispose();
                    try { socket.Dispose(); } catch { /* ignore */ }
                }
            }
        }
        catch (OperationCanceledException)
        {
            // normal shutdown
        }
        catch (Exception ex)
        {
            _monitor.Log($"WebSocket error: {ex.Message}", LogLevel.Debug);
        }
    }

    private async Task ReceiveLoop(System.Net.WebSockets.WebSocket socket, CancellationToken ct)
    {
        var buffer = new byte[16384];
        while (socket.State == WebSocketState.Open)
        {
            WebSocketReceiveResult result;
            using (var ms = new MemoryStream())
            {
                do
                {
                    result = await socket.ReceiveAsync(new ArraySegment<byte>(buffer), ct).ConfigureAwait(false);
                    if (result.Count > 0)
                        ms.Write(buffer, 0, result.Count);
                }
                while (!result.EndOfMessage);

                if (result.MessageType == WebSocketMessageType.Close)
                {
                    if (socket.State == WebSocketState.Open)
                        await socket.CloseAsync(WebSocketCloseStatus.NormalClosure, "", CancellationToken.None).ConfigureAwait(false);
                    break;
                }

                if (result.MessageType == WebSocketMessageType.Text)
                    HandleMessage(socket, Encoding.UTF8.GetString(ms.ToArray()));
            }
        }
    }

    // Thread-safe, serialized send (System.Net.WebSockets only allows one SendAsync at a time).
    private async Task SendLoop(System.Net.WebSockets.WebSocket socket, string payload)
    {
        SemaphoreSlim sem = _sendLocks.GetOrAdd(socket, _ => new SemaphoreSlim(1, 1));
        await sem.WaitAsync().ConfigureAwait(false);
        try
        {
            if (socket.State == WebSocketState.Open)
            {
                var bytes = Encoding.UTF8.GetBytes(payload);
                await socket.SendAsync(new ArraySegment<byte>(bytes), WebSocketMessageType.Text, true, CancellationToken.None).ConfigureAwait(false);
            }
        }
        catch (Exception ex)
        {
            _monitor.Log($"WebSocket send failed: {ex.Message}", LogLevel.Debug);
        }
        finally
        {
            sem.Release();
        }
    }

    // ------------------------------------------------------------------ //
    // Protocol
    // ------------------------------------------------------------------ //
    private string GetStateJson()
    {
        string stateJson = _stateSerializer.GetGameStateJson();
        var response = new WebSocketResponse
        {
            Type = "state",
            Success = true,
            Data = JsonSerializer.Deserialize<object>(stateJson)
        };
        return JsonSerializer.Serialize(response, JsonOptions);
    }

    private void HandleMessage(System.Net.WebSockets.WebSocket socket, string payload)
    {
        try
        {
            var message = JsonSerializer.Deserialize<WebSocketMessage>(payload, JsonOptions);
            if (message == null)
            {
                _ = SendLoop(socket, ErrorJson("Invalid message format"));
                return;
            }

            switch (message.Type?.ToLower())
            {
                case "command":
                    HandleCommand(socket, message);
                    break;
                case "get_state":
                    _ = SendLoop(socket, GetStateJson());
                    break;
                case "ping":
                    _ = SendLoop(socket, PongJson(message.Id));
                    break;
                default:
                    _ = SendLoop(socket, ErrorJson($"Unknown message type: {message.Type}"));
                    break;
            }
        }
        catch (Exception ex)
        {
            _monitor.Log($"Error processing message: {ex.Message}", LogLevel.Error);
            _ = SendLoop(socket, ErrorJson(ex.Message));
        }
    }

    private void HandleCommand(System.Net.WebSockets.WebSocket socket, WebSocketMessage message)
    {
        var command = new GameCommand
        {
            Id = message.Id ?? Guid.NewGuid().ToString(),
            Action = message.Action ?? "",
            Params = message.Params ?? new Dictionary<string, object>(),
            OnComplete = response => _ = SendLoop(socket, ResponseJson(response))
        };

        // Commands execute on the game thread; the actual result arrives via OnComplete.
        _commandExecutor.QueueCommand(command);
    }

    private string ResponseJson(CommandResponse response) => JsonSerializer.Serialize(
        new WebSocketResponse { Id = response.Id, Type = "response", Success = response.Success, Message = response.Message, Data = response.Data },
        JsonOptions);

    private string ErrorJson(string message) => JsonSerializer.Serialize(
        new WebSocketResponse { Type = "error", Success = false, Message = message },
        JsonOptions);

    private string PongJson(string? id) => JsonSerializer.Serialize(
        new WebSocketResponse { Id = id ?? "", Type = "pong", Success = true },
        JsonOptions);
}

#region Message Classes

public class WebSocketMessage
{
    public string? Id { get; set; }
    public string? Type { get; set; }
    public string? Action { get; set; }
    public Dictionary<string, object>? Params { get; set; }
}

public class WebSocketResponse
{
    public string Id { get; set; } = "";
    public string Type { get; set; } = "";
    public bool Success { get; set; }
    public string? Message { get; set; }
    public object? Data { get; set; }
}

#endregion