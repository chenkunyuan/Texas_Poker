/**
 * Texas Hold'em Poker — WebSocket Client
 *
 * Lightweight wrapper around the browser WebSocket API with an
 * event-emitter pattern for registering typed message handlers.
 *
 * Usage::
 *
 *     const ws = new WSClient();
 *     ws.on("game_state", (msg) => { ... });
 *     ws.on("your_turn", (msg) => { ... });
 *     await ws.connect("ws://localhost:8000/ws/abc123");
 *     ws.send({ type: "player_action", action: "CALL", amount: 0 });
 */
var WSClient = (function () {
    "use strict";

    /**
     * @constructor
     */
    function WSClient() {
        /** @type {WebSocket|null} */
        this._ws = null;

        /** @type {string} */
        this._url = "";

        /** @type {Object<string, Function[]>} */
        this._handlers = {};

        /** @type {boolean} */
        this._manualClose = false;

        /** @type {number} */
        this._reconnectAttempts = 0;

        /** @type {number} */
        this._maxReconnectAttempts = 5;

        /** @type {number} */
        this._reconnectDelay = 2000;
    }

    /**
     * Connect to a WebSocket endpoint.
     *
     * @param {string} url — Full WebSocket URL, e.g. "ws://localhost:8000/ws/abc123"
     * @returns {Promise<void>} Resolves when the connection is open.
     */
    WSClient.prototype.connect = function (url) {
        var self = this;
        self._url = url;
        self._manualClose = false;

        return new Promise(function (resolve, reject) {
            try {
                self._ws = new WebSocket(url);
            } catch (err) {
                reject(err);
                return;
            }

            self._ws.onopen = function () {
                self._reconnectAttempts = 0;
                resolve();
            };

            self._ws.onmessage = function (event) {
                var msg;
                try {
                    msg = JSON.parse(event.data);
                } catch (e) {
                    console.warn("[WSClient] Invalid JSON received:", event.data);
                    return;
                }
                self._dispatch(msg);
            };

            self._ws.onerror = function (err) {
                console.error("[WSClient] WebSocket error:", err);
            };

            self._ws.onclose = function (event) {
                self._dispatch({ type: "_close", code: event.code, reason: event.reason });

                // Auto-reconnect unless the client called close() explicitly.
                if (!self._manualClose && self._reconnectAttempts < self._maxReconnectAttempts) {
                    self._reconnectAttempts++;
                    console.log(
                        "[WSClient] Reconnecting attempt " +
                            self._reconnectAttempts +
                            " in " +
                            self._reconnectDelay +
                            "ms..."
                    );
                    setTimeout(function () {
                        self.connect(self._url).catch(function () {
                            // Silently fail — onclose will retry if there are attempts left.
                        });
                    }, self._reconnectDelay);
                }
            };
        });
    };

    /**
     * Register a handler for a message type.
     *
     * @param {string} type — Message type, e.g. "game_state", "your_turn", "player_action",
     *     "ai_thinking", "hand_result", "game_over".
     * @param {Function} handler — Callback receiving the parsed message object.
     */
    WSClient.prototype.on = function (type, handler) {
        if (!this._handlers[type]) {
            this._handlers[type] = [];
        }
        this._handlers[type].push(handler);
    };

    /**
     * Remove a previously registered handler.
     *
     * @param {string} type
     * @param {Function} handler
     */
    WSClient.prototype.off = function (type, handler) {
        var handlers = this._handlers[type];
        if (!handlers) return;
        var idx = handlers.indexOf(handler);
        if (idx >= 0) {
            handlers.splice(idx, 1);
        }
    };

    /**
     * Send a JSON message to the server.
     *
     * @param {object} msg — The message object (will be JSON-stringified).
     */
    WSClient.prototype.send = function (msg) {
        if (!this._ws || this._ws.readyState !== WebSocket.OPEN) {
            console.warn("[WSClient] Cannot send — WebSocket is not open.");
            return;
        }
        this._ws.send(JSON.stringify(msg));
    };

    /**
     * Close the WebSocket connection. No auto-reconnect will be attempted.
     */
    WSClient.prototype.close = function () {
        this._manualClose = true;
        if (this._ws) {
            this._ws.close();
            this._ws = null;
        }
    };

    /**
     * Check whether the connection is currently open.
     *
     * @returns {boolean}
     */
    WSClient.prototype.isConnected = function () {
        return this._ws !== null && this._ws.readyState === WebSocket.OPEN;
    };

    // ------------------------------------------------------------------
    // Internal: dispatch a parsed message to registered handlers
    // ------------------------------------------------------------------

    /**
     * @param {object} msg
     * @private
     */
    WSClient.prototype._dispatch = function (msg) {
        var type = msg.type || "_unknown";
        var handlers = this._handlers[type];
        if (handlers) {
            for (var i = 0; i < handlers.length; i++) {
                try {
                    handlers[i](msg);
                } catch (err) {
                    console.error("[WSClient] Handler error for type '" + type + "':", err);
                }
            }
        }

        // Also dispatch to "*" wildcard handlers.
        var wildcard = this._handlers["*"];
        if (wildcard) {
            for (var j = 0; j < wildcard.length; j++) {
                try {
                    wildcard[j](msg);
                } catch (err) {
                    console.error("[WSClient] Wildcard handler error:", err);
                }
            }
        }
    };

    return WSClient;
})();
