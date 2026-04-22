"""ProcessManager component — monitors a list of configured long-running processes,
restarting any that have stopped and notifying via RocketChat."""

import os
import signal
import subprocess
import time
from datetime import datetime

from nvp.nvp_component import NVPComponent
from nvp.nvp_context import NVPContext


def create_component(ctx: NVPContext):
    """Create an instance of the component"""
    return ProcessManager(ctx)


class ProcessManager(NVPComponent):
    """ProcessManager component — manages a list of watched processes defined in config."""

    def __init__(self, ctx: NVPContext):
        """Constructor"""
        NVPComponent.__init__(self, ctx)
        pname = self.get_hostname().lower()

        key = f"proc_manager.{pname}"
        self.config = ctx.get_config().get(key, None)
        if self.config is None:
            self.config = self.ctx.get_project("NervHome").get_config().get(key, {})

    # -------------------------------------------------------------------------
    # Command dispatch
    # -------------------------------------------------------------------------

    def process_cmd_path(self, cmd):
        """Handle CLI commands routed to this component."""

        if cmd == "check":
            # Called by cron every minute — check all watched processes.
            return self.cmd_check()

        if cmd == "restart":
            # Manually restart one or all watched processes.
            label = self.get_param("label", None)
            return self.cmd_restart(label)

        if cmd == "status":
            # Print running/stopped status for all watched processes.
            return self.cmd_status()

        if cmd == "stop":
            label = self.get_param("label", None)
            return self.cmd_stop(label)

        return False

    # -------------------------------------------------------------------------
    # High-level commands
    # -------------------------------------------------------------------------

    def cmd_check(self):
        """Check every configured process; start any that are not running."""
        procs = self._get_proc_descs()
        for desc in procs:
            if not desc.get("enabled", True):
                continue
            label = desc["label"]
            if not self._is_running(desc):
                self._log(desc, f"[{label}] Not running — starting...")
                self._start(desc, reason="monitor")
            # else: already up, nothing to do
        return True

    def cmd_restart(self, label=None):
        """Stop then start one process (by label) or all of them."""
        procs = self._get_proc_descs()
        targets = [d for d in procs if label is None or d["label"] == label]
        if not targets:
            self.warn("No process found matching label=%s", label)
            return False
        for desc in targets:
            self._stop(desc)
            self._start(desc, reason="manual restart")
        return True

    def cmd_stop(self, label=None):
        """Stop one process (by label) or all of them."""
        procs = self._get_proc_descs()
        targets = [d for d in procs if label is None or d["label"] == label]
        for desc in targets:
            self._stop(desc)
        return True

    def cmd_status(self):
        """Print running/stopped status for every configured process."""
        procs = self._get_proc_descs()
        for desc in procs:
            label = desc["label"]
            state = "RUNNING" if self._is_running(desc) else "STOPPED"
            pid_file = self._pid_file(desc)
            pid = ""
            if os.path.isfile(pid_file):
                pid = f"  (PID {open(pid_file).read().strip()})"
            print(f"  {state:8s}  {label}{pid}")
        return True

    # -------------------------------------------------------------------------
    # Process lifecycle helpers
    # -------------------------------------------------------------------------

    def _is_running(self, desc):
        """Return True if the process tracked by desc's PID file is alive
        and its /proc/<pid>/cmdline matches the configured pattern."""
        pid_file = self._pid_file(desc)
        if not os.path.isfile(pid_file):
            return False
        try:
            pid = int(open(pid_file).read().strip())
        except (ValueError, OSError):
            return False

        # Signal 0: existence check only, no actual signal sent.
        try:
            os.kill(pid, 0)
        except OSError:
            return False

        # Optionally verify the process identity via /proc/<pid>/cmdline.
        pattern = desc.get("cmd_pattern", None)
        if pattern:
            try:
                cmdline = open(f"/proc/{pid}/cmdline").read()
                if pattern not in cmdline:
                    return False
            except OSError:
                return False

        return True

    def _start(self, desc, reason=""):
        """Launch the process described by desc, redirect output to its log file,
        save the PID, and send a RocketChat notification."""
        label = desc["label"]
        cmd = self._build_cmd(desc)
        cwd = self._resolve(desc.get("cwd", self.get_cwd()))
        log_file = self._resolve(desc["log_file"])
        pid_file = self._pid_file(desc)

        # Ensure log directory exists.
        self.make_folder(os.path.dirname(log_file))

        # Merge any extra environment variables.
        env = os.environ.copy()
        for key, val in desc.get("env", {}).items():
            env[key] = self._resolve(val)

        self._log(desc, f"[{label}] Starting ({reason}): {' '.join(cmd)}")

        with open(log_file, "a", encoding="utf-8") as lf:
            lf.write(f"\n{'='*60}\n")
            lf.write(f"[{self._ts()}] Started by proc_manager ({reason})\n")
            lf.write(f"cmd: {' '.join(cmd)}\ncwd: {cwd}\n")
            lf.write(f"{'='*60}\n")
            proc = subprocess.Popen(
                cmd,
                cwd=cwd,
                env=env,
                stdout=lf,
                stderr=subprocess.STDOUT,
                start_new_session=True,  # detach from our own session
            )

        with open(pid_file, "w") as pf:
            pf.write(str(proc.pid))

        self._log(desc, f"[{label}] Started with PID {proc.pid}")
        self._notify(
            desc, f":white_check_mark: **[proc_manager]** `{label}` started (PID {proc.pid}) — reason: _{reason}_"
        )

    def _stop(self, desc, timeout=5):
        """Gracefully stop a process (SIGTERM → wait → SIGKILL)."""
        label = desc["label"]
        pid_file = self._pid_file(desc)

        if not os.path.isfile(pid_file):
            self._log(desc, f"[{label}] No PID file — was not running.")
            return

        try:
            pid = int(open(pid_file).read().strip())
        except (ValueError, OSError):
            os.remove(pid_file)
            return

        if not self._is_running(desc):
            self._log(desc, f"[{label}] PID {pid} not running (stale PID file removed).")
            os.remove(pid_file)
            return

        self._log(desc, f"[{label}] Stopping PID {pid}...")
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass

        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                os.kill(pid, 0)
            except OSError:
                break
            time.sleep(0.5)
        else:
            self._log(desc, f"[{label}] Did not stop cleanly — force killing PID {pid}.")
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass

        if os.path.isfile(pid_file):
            os.remove(pid_file)
        self._log(desc, f"[{label}] Stopped.")

    # -------------------------------------------------------------------------
    # Utilities
    # -------------------------------------------------------------------------

    def _get_proc_descs(self):
        """Return the list of process descriptors from config."""
        return self.config.get("processes", [])

    def _pid_file(self, desc):
        """Resolve the PID file path for a descriptor."""
        pid_dir = self._resolve(self.config.get("pid_dir", "/tmp"))
        default = os.path.join(pid_dir, f"nvp_{desc['label'].replace(' ', '_')}.pid")
        return self._resolve(desc.get("pid_file", default))

    def _build_cmd(self, desc):
        """Build the command list from a descriptor."""
        python = self._resolve(desc.get("python", "python3"))
        args = [self._resolve(a) for a in desc.get("args", [])]
        return [python] + args

    def _resolve(self, val):
        """Expand known NVP placeholders in a string value."""
        if val is None:
            return val
        return self.ctx.resolve_path(val)

    def _ts(self):
        """Return a formatted timestamp."""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _log(self, desc, message):
        """Write a timestamped line to both the shared process_manager log and
        to the process's own log file."""
        line = f"[{self._ts()}] {message}"

        # Shared manager log
        shared_log = self._resolve(self.config.get("log_file", "/tmp/process_manager.log"))
        self.make_folder(os.path.dirname(shared_log))
        with open(shared_log, "a", encoding="utf-8") as f:
            f.write(line + "\n")

        self.info(message)

    def _notify(self, desc, message):
        """Send a RocketChat message if configured and the process has notify=True."""
        if not desc.get("notify", True):
            return
        channel = desc.get("notify_channel", self.config.get("notify_channel", "problem-reports"))
        try:
            rchat = self.get_component("rchat")
            rchat.send_message(message, channel=channel)
        except Exception as exc:
            self.warn("RocketChat notification failed: %s", exc)


if __name__ == "__main__":
    context = NVPContext()
    comp = context.register_component("proc_man", ProcessManager(context))

    psr = context.build_parser("check")
    # psr.add_str("-v", "--vault", dest="vault", default="all")("Vault name(s) to query, comma-separated, or 'all'.")

    psr = context.build_parser("restart")
    psr.add_str("-l", "--label", dest="label")("Label of the process to restart")

    psr = context.build_parser("stop")
    psr.add_str("-l", "--label", dest="label")("Label of the process to stop")

    psr = context.build_parser("status")

    comp.run()
