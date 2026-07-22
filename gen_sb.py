import json, sys
auth = sys.argv[1]
host = sys.argv[2]
port = int(sys.argv[3])
peer = sys.argv[4]
insecure = sys.argv[5].lower() == 'true'
config = {
    "log": {"level": "info"},
    "dns": {"servers": [{"tag": "dns", "address": "https://1.1.1.1/dns-query", "strategy": "prefer_ipv4"}]},
    "inbounds": [
        {"type": "socks", "tag": "socks-in", "listen": "127.0.0.1", "listen_port": 1080},
        {"type": "http", "tag": "http-in", "listen": "127.0.0.1", "listen_port": 1081}
    ],
    "outbounds": [{
        "type": "hysteria2",
        "tag": "proxy",
        "server": host,
        "server_port": port,
        "up_mbps": 50,
        "down_mbps": 150,
        "password": auth,
        "tls": {"enabled": True, "server_name": peer, "insecure": insecure}
    }, {"type": "direct", "tag": "direct"}]
}
print(json.dumps(config, indent=2))