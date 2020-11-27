import rumps
import subprocess
from datetime import datetime
import socket
from threading import Timer
from threading import Thread
import time
import ssl
import paho.mqtt.client as mqtt
import os
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler
import uuid
import json

APP_NAME = "Git Sync Bar"
ICON="icon.pdf"
ICON_50PCT="icon-50pct.png"
ICON_SYNC="icon-sync.pdf"
ICON_EXCLAMATION="icon-exclamation.pdf"

GIT_BIN = "/usr/local/bin/git"

if not os.path.exists(GIT_BIN):
	GIT_BIN = "/usr/bin/git"

if not os.path.exists(GIT_BIN):
	rumps.alert("No git binary in /usr/local/bin/git or /usr/bin/git")
	exit(1)

print("Found git binary at " + GIT_BIN)



def current_time_millis():
	return int(round(time.time() * 1000))

def uuidgen():
	return str(uuid.uuid4())


class WatchdogHandler(PatternMatchingEventHandler):

	def __init__(self, path, callback):
		super(WatchdogHandler, self).__init__(ignore_patterns = [os.path.join(path, ".git/**")], ignore_directories=True)
		self.callback = callback

	def on_any_event(self, event):
		self.callback(event)

class GitSyncBarApp(rumps.App):

	def __init__(self, *args, **kwargs):
		super(GitSyncBarApp, self).__init__(APP_NAME, *args, **kwargs)

		print("Starting " + self.name)
		self.icon = ICON
		self.template = True

		self.config_path = os.path.join(rumps.application_support(self.name), "config.json")
		self.config = self.load_or_create_config()

		# calculated configuration
		self.git_commit_message = "host: " + socket.gethostname()
				
		# build the menus
		self.menu_item_last_update = rumps.MenuItem("Syncing...")
		self.menu_item_sync_now = rumps.MenuItem("Sync Now", callback=self.on_click_sync_now)
		self.menu_item_show_in_finder = rumps.MenuItem("Show in Finder", callback=self.on_click_show_in_finder)
		self.menu_item_open_terminal = rumps.MenuItem("Open Terminal", callback=self.on_click_open_terminal)
		self.menu_item_edit_config = rumps.MenuItem("Edit Config", callback=self.on_click_edit_config)
		
		self.menu.add(self.menu_item_last_update)
		self.menu.add(self.menu_item_sync_now)
		self.menu.add(None)
		self.menu.add(self.menu_item_show_in_finder)		
		self.menu.add(self.menu_item_open_terminal)
		self.menu.add(None)
		self.menu.add(self.menu_item_edit_config)
		self.menu.add(None)

		self.last_sync_millis = 0

		# if a sync_poll_seconds config option is set, setup the timer.  this will also fire immediately on start,
		# so we can use that to perform an initial sync
		if self.config['sync_poll_seconds'] > 0:
			self.poll_timer = rumps.Timer(self.on_poll, self.config['sync_poll_seconds'])
			self.poll_timer.start()
		else:
			# if we did not schedule a timer, we need to scheduled a start-up sync.
			self.schedule_sync()

		# reference for the sync timer thread so that it can be cancelled if pending
		self.sync_timer = None

		# initialize a mqtt connection for sync notifications
		if self.config['mqtt_enabled']:	
			self.icon = ICON_50PCT
			self.mqtt_init()

		# setup a watchdog to track file changes
		if self.config['watch_for_changes']:
			self.watchdog_handler = WatchdogHandler(self.config['sync_dir'], self.on_watchdog_event)
			self.watchdog_observer = Observer()
			self.watchdog_observer.schedule(self.watchdog_handler, self.config['sync_dir'], recursive=True)
			self.watchdog_observer.start()

	
	def on_click_sync_now(self, sender):
		print("sync_now")
		self.schedule_sync(0)

	def on_click_show_in_finder(self, sender):
		print("show in finder: " + self.config['sync_dir'])
		subprocess.call(['open', self.config['sync_dir']])

	def on_click_open_terminal(self, sender):
		print("open in terminal: " + self.config['sync_dir'])
		subprocess.call(['open', '-a', 'terminal', self.config['sync_dir']])

	def on_click_edit_config(self, sender):
		print("Editing configuration...")
		self.edit_config()
		print("Configuration updated, need to restart.")
		rumps.alert(message="I gave up trying to figure out how to reload the app automatically, so please restart the app for changes to take effect.")
		

	def on_watchdog_event(self, event):
		print("watchdog event:")
		print(event)
		if self.git_has_changes():
			self.icon = ICON_EXCLAMATION
			self.schedule_sync(self.config['sync_delay_seconds'])

	def on_poll(self, timer):
		print("on_poll")

		if (current_time_millis() - self.last_sync_millis) > (self.config['sync_poll_seconds'] * 1000):
			print("No sync in the last " + str(self.config['sync_poll_seconds']) + " seconds, syncing now.")
			self.schedule_sync(0)
		else:
			print("Sync occured during last " + str(self.config['sync_poll_seconds']) + " seconds, not syncing now.")

	def load_or_create_config(self):

		valid_config = False

		while not valid_config:

			if not os.path.exists(self.config_path):
				print("No configuration found, will edit default")
				config = self.edit_config(config_txt=self.get_default_config())

			else:
				with open(self.config_path) as f:
					config = f.read()

			valid_config = self.validate_config(config)

			if not valid_config['valid']:
				self.edit_config(config_txt=config, message_text=valid_config['msg'])

		return json.loads(config)


	def edit_config(self, config_txt=None, message_text=None):

		txt = config_txt

		if txt == None:
			with open(self.config_path) as f:
				txt = f.read()

		msg = "Configuration:  (use <option+enter> to insert new line)"
		if message_text:
			msg += "\n" + message_text


		resp = rumps.Window(message=msg, title=self.name + " Configuration", default_text=txt, cancel="Quit", dimensions=(800,600)).run()

		if resp.clicked:

			validation_result = self.validate_config(resp.text)

			if validation_result['valid']:

				# save the config
				with open(self.config_path, 'w') as f:
					f.write(resp.text)

				return resp.text
			else:
				print("Configuration Error: " + validation_result['msg'])
				return self.edit_config(config_txt=resp.text, message_text=validation_result['msg'])
		else:
			print("Configuration cancelled, exiting.")
			rumps.quit_application();


	def validate_config(self, txt):

		try:
			config = json.loads(txt)

			if "client_id" not in config:
				raise NameError("client_id is required")

			if len(config["client_id"]) < 1:
				raise NameError("client_id may not be empty")

			if "sync_dir" not in config:
				raise NameError("sync_dir is required")

			if not os.path.exists(config['sync_dir']):
				raise NameError("sync_dir does not exist")

			if not self.git_is_git_dir(config['sync_dir']):
				raise NameError("sync_dir is not a git repo, `git init` it.")

			if not self.git_has_remote(config['sync_dir']):
				raise NameError("sync_dir has no git remote.")

			if "watch_for_changes" not in config:
				raise NameError("watch_for_changes is required")

			if type(config['watch_for_changes']) != bool:
				raise NameError("watch_for_changes must be true or false")

			if "sync_delay_seconds" not in config:
				raise NameError("sync_delay_seconds is required")

			if type(config['sync_delay_seconds']) != int:
				raise NameError("sync_delay_seconds must be an int")

			if "sync_poll_seconds" not in config:
				raise NameError("sync_poll_seconds is required")

			if type(config['sync_poll_seconds']) != int:
				raise NameError("sync_poll_seconds must be an int")

			if "mqtt_enabled" not in config:
				raise NameError("mqtt_enabled is required")

			if type(config['mqtt_enabled']) != bool:
				raise NameError("mqtt_enabled must be true or false")

			if config['mqtt_enabled']:

				if "mqtt_host" not in config:
					raise NameError("mqtt_host is required")

				if len(config['mqtt_host']) < 1:
					raise NameError("mqtt_host may not be empty")

				if "mqtt_port" not in config:
					raise NameErrror("mqtt_port is required")

				if type(config['mqtt_port']) != int:
					raise NameError("mqtt_port must be an int")

				if "mqtt_topic" not in config:
					raise NameError("mqtt_topic is required")

				if len(config['mqtt_topic']) < 1:
					raise NameError("mqtt_topic may not be empty")

				if "mqtt_keepalive_seconds" not in config:
					raise NameError("mqtt_keepalive_seconds is required")

				if type(config['mqtt_keepalive_seconds']) != int:
					raise NameError("mqtt_keepalive_seconds must be an int")

				if "mqtt_use_tls" not in config:
					raise NameError("mqtt_use_tls is required")

				if type(config['mqtt_use_tls']) != bool:
					raise NameError("mqtt_use_tls must be true or false")

				if config['mqtt_use_tls']:

					if "mqtt_tls_ca_cert_file" not in config:
						raise NameError("mqtt_tls_ca_cert_file is required")

					if len(config['mqtt_tls_ca_cert_file']) < 1:
						raise NameError("mqtt_tls_ca_cert_file must not be empty")

					if not os.path.exists(config['mqtt_tls_ca_cert_file']):
						raise NameError("mqtt_tls_ca_cert_file does not exist")

					if "mqtt_tls_cert_file" not in config:
						raise NameError("mqtt_tls_cert_file is required")

					if len(config['mqtt_tls_cert_file']) < 1:
						raise NameError("mqtt_tls_cert_file must not be empty")

					if not os.path.exists(config['mqtt_tls_cert_file']):
						raise NameError("mqtt_tls_cert_file does not exist")

					if "mqtt_tls_key_file" not in config:
						raise NameError("mqtt_tls_key_file is required")

					if len(config['mqtt_tls_key_file']) < 1:
						raise NameError("mqtt_tls_key_file must not be empty")

					if not os.path.exists(config["mqtt_tls_key_file"]):
						raise NameError("mqtt_tls_key_file does not exist")

					if "mqtt_tls_version" not in config:
						raise NameError("mqtt_tls_version is required")

					if config['mqtt_tls_version'] != '1.2':
						raise NameError("mqtt_tls_version must be 1.2")

			
			print("Valid Configuration")
			return { "valid": True, "msg": None }
		except Exception as e:
			print("Invalid Config: " + str(e))
			return { "valid": False, "msg": str(e) }



	def get_default_config(self):

		home_path = os.path.expanduser("~")
		sync_path = os.path.join(home_path, "GitSync")

		certs_path = os.path.join(rumps.application_support(self.name), "certs")

		config = {}
		config['client_id'] = uuidgen()
		config['sync_dir'] = sync_path
		config['watch_for_changes'] = True
		config['sync_delay_seconds'] = 10
		config['sync_poll_seconds'] = 3600
		config['mqtt_enabled'] = False
		config['mqtt_host'] = 'test.mosquitto.org'
		config['mqtt_port'] = 1883
		config['mqtt_topic'] = uuidgen()
		config['mqtt_keepalive_seconds'] = 900
		config['mqtt_use_tls'] = False
		config['mqtt_tls_ca_cert_file'] = os.path.join(certs_path, "ca.crt")
		config['mqtt_tls_cert_file'] = os.path.join(certs_path, "client.crt")
		config['mqtt_tls_key_file'] = os.path.join(certs_path, "client.key")
		config['mqtt_tls_version'] = "1.2"

		config_str = json.dumps(config, indent=2)

		return config_str		


	# launch a timer thread to invoke sync after a delay (delay=0 to invoke immediately)
	def schedule_sync(self, delay=0):
		if self.sync_timer:
			print("cancel existing timer to reschedule")
			self.sync_timer.cancel()


		self.sync_timer = Timer(delay, self.sync)
		print(f"will sync in {delay} seconds")
		self.sync_timer.start()
		


	# this must be invoked in a background thread, or it'll block the UI
	def sync(self):
		print("sync starting")
		self.icon = ICON_SYNC
		self.menu_item_last_update.title = "Syncing..."
		pushed_changes = self.git_sync()
		self.menu_item_last_update.title = "Last Sync: " + datetime.now().strftime("%m/%d/%y %H:%M:%S")
		self.icon = ICON

		if pushed_changes:
			self.mqtt_announce_change()

		self.last_sync_millis = current_time_millis()
		print("sync complete")


	def mqtt_init(self):
		self.mqtt_client = mqtt.Client(client_id=self.config['client_id'])
		self.mqtt_client.on_connect = self.mqtt_on_connect
		self.mqtt_client.on_message = self.mqtt_on_message
		self.mqtt_client.on_disconnect = self.mqtt_on_disconnect

		app_support_path = rumps.application_support(self.name)

		if self.config['mqtt_use_tls']:
			self.mqtt_client.tls_set(ca_certs=self.config['mqtt_tls_ca_cert_file'], 
				certfile=self.config['mqtt_tls_cert_file'], 
				keyfile=self.config['mqtt_tls_key_file'], 
				cert_reqs=ssl.CERT_REQUIRED, 
				tls_version=ssl.PROTOCOL_TLSv1_2)

		self.mqtt_client.connect_async(self.config['mqtt_host'], self.config['mqtt_port'], self.config['mqtt_keepalive_seconds'])

		self.mqtt_thread = Thread(target=self.mqtt_thread_run)
		self.mqtt_thread.start()
		print("Started MQTT Background Thread")

	def mqtt_on_connect(self, client, userdata, flags, rc):
		print("MQTT Connected")
		client.subscribe(self.config['mqtt_topic'])
		self.icon = ICON

	def mqtt_on_disconnect(self, client, userdata, rc):
		print("MQTT Disconnceted rc=" + str(rc))
		self.icon = ICON_50PCT

	def mqtt_on_message(self, client, userdata, msg):
		print("MQTT GOT MESSAGE: topic=" + msg.topic + " payload=" + str(msg.payload, 'utf8'))
		if str(msg.payload, 'utf8') == self.config['client_id']:
			print("ignore message from self")
		else:
			print("sync notification from client_id=" + str(msg.payload, 'utf8'))
			self.schedule_sync()

	def mqtt_thread_run(self):
		print("Starting mqtt loop")
		self.mqtt_client.loop_forever()

	def mqtt_announce_change(self):
		print("MQTT announcing change")
		self.mqtt_client.publish(self.config['mqtt_topic'], self.config['client_id'])


	#######################################################################
	## git invocations                                                   ##
	#######################################################################

	def git_is_git_dir(self, path):
		output = subprocess.check_output([GIT_BIN, 'rev-parse', '--git-dir'], cwd=path, encoding="utf8")
		return ".git" == output.strip()

	def git_has_remote(self, path):
		output = subprocess.check_output([GIT_BIN, 'remote'], cwd=path, encoding="utf8")
		return len(output.strip()) > 0

	def git_has_changes(self):
		print("git_has_changes")
		output = subprocess.check_output([GIT_BIN, 'status', '-s', '--porcelain'], cwd=self.config['sync_dir'], encoding="utf8")
		
		has_changes = len(output) > 0

		if has_changes:
			print("Found changes")
			print(output)
		else:
			print("No tracked changes")
		
		return has_changes

	def git_add_all_modified(self):
		print("add:")
		rc = subprocess.call([GIT_BIN, 'add', '-A'], cwd=self.config['sync_dir'])
		print(f"add rc = " + str(rc))

	def git_commit(self):
		print("commit:")
		rc = subprocess.call([GIT_BIN, 'commit', '-m', self.git_commit_message], cwd=self.config['sync_dir'])
		print(f"commit rc = {rc}")

	def git_pull_keep_ours(self):
		# this does a pull, and if there are any merge conflicts it takes our copy and uses the 
		# default generated merge message.  If there are no conflicts, its a normal pull.
		print("pull:")
		rc = subprocess.call([GIT_BIN, 'pull', '-Xours', '--no-edit'], cwd=self.config['sync_dir'])
		print(f"pull rc = {rc}")

	def git_push(self):
		print("push:")
		output = subprocess.check_output([GIT_BIN, 'push', '--porcelain'], cwd=self.config['sync_dir'], encoding="utf8")
		
		# TODO: this seems like a bad way to check this...
		pushed_changes = ("[up to date]" not in output)

		if pushed_changes:
			print("Pushed changes:")
			print(output)
		else:
			print("No changes to push - Everything up-to-date")

		return pushed_changes

	# add all modified files, commit them, pull (keeping our changes if conflicts), and then push.
	# this will stomp on conflicting changes with a last-one-in-wins approach, but the history will
	# be maintained in the git log
	def git_sync(self):

		# if we have changes, commit those first
		if self.git_has_changes() :
			print("found changes")
			self.git_add_all_modified()
			self.git_commit()

		# pull, keeping our copy for conflicts
		self.git_pull_keep_ours()
		
		# push our changes
		return self.git_push()


if __name__ == "__main__":
	GitSyncBarApp().run()
