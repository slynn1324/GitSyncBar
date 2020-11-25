# Git Sync Bar

A small macOS menu bar app to automatically sync (commit, push, and pull) a git repo for Dropbox like functionality.


## Configuration

On first launch, a configuration window will open with JSON content to gather the necessary configuration options.  The configuration can be updated via the 'Edit Configuration' menu item. 


- client_id : A unique client id value, the generated uuid is typically fine.  This is sent as the body of the mqtt message to announce that a new commmit has been pushed, and is used to identify messages that were sent by the local instance.

- sync_dir : The fully-qualified file path of a directory to sync.  This directory must be an existing git repo with a remote.

- watch_for_changes : [true|false] Enable a file system monitor (via python watchdog) to enable sync on file system events.  If false, the sync_dir will only be scanned every sync_poll_seconds.

- sync_delay_seconds : [int] The number of seconds to delay a sync on file system change.  Many applications may save a file multiple times rapidly, so a small delay is recommended to prevent extraneous syncs.

- sync_poll_seconds : [int] The number of seconds between polling operations.  Polling always occurs as a fallback in case of a missed filesystem event or mqtt message (or either of those are disabled).

- mqtt_enabled : [true|false] Enable MQTT integration for immediate notification of all sync clients.  (Recommended).

- mqtt_host : The mqtt broker host.

- mqtt_port : The mqtt broker port.

- mqtt_topic : The topic to announce/listen for pushed commits.  All instances that you want to keep in sync must use the same value for mqtt_topic.

- mqtt_keepalive_seconds : The keepalive interval for the mqtt connection. 

- mqtt_use_tls : [true|false] Enable TLS support on the mqtt connection.

- mqtt_tls_ca_cert_file : Path to the ca cert file for tls support.

- mqtt_tls_cert_file : Path to the client cert file for tls support.

- mqtt_tls_key_file : Path to the client key file for tls support.

- mqtt_tls_version : Currently must be "1.2". 


## MQTT

MQTT is used to notify all other instances that a push has been made and that they should sync immediately to pull new changes.  This greatly improves the 'real-time' sync between multiple clients and allows for a much lower 'sync_poll_seconds' value, which saves resources on both the client and git remote.

It should be relatively safe to use a public broker (such as the default test.mosquitto.org) as the only information transmitted is the topic name and the client_id that has made a push.  When a message is received on the topic, each client compares the message payload to it's local 'client_id' value, and if they do not match a sync is performed immediately.  The default values for both the client_id and mqtt_topic are random uuids so disclose no real identifying information.

Do note that the reliability of public mqtt brokers may have no service level guarantees.  To run your own broker for increased reliability and/or privacy, I recommend Eclipse Mosquitto[https://mosquitto.org/] - it's very light weight and trivial to set up.  Any other mqtt broker should work fine as well.



## Credits

python[https://www.python.org/]
rumps[https://rumps.readthedocs.io/en/latest/index.html]
py2app[https://py2app.readthedocs.io/en/latest/]
watchdog[https://github.com/gorakhargosh/watchdog]
paho-mqtt[https://pypi.org/project/paho-mqtt/]





