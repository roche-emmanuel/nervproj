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
        for desc in self._get_proc_descs():
            if not desc.get("enabled", True):
                continue
            label = desc["label"]
            if not self._is_running(desc):
                self._log(f"[{label}] Not running — starting...")
                self._start(desc, reason="monitor")
        return True

    def cmd_restart(self, label=None):
        """Stop then start one process (by label) or all of them."""
        targets = self._get_targets(label)
        if not targets:
            self.warn("No process found matching label=%s", label)
            return False
        for desc in targets:
            self._stop(desc)
            self._start(desc, reason="manual restart")
        return True

    def cmd_stop(self, label=None):
        """Stop one process (by label) or all of them."""
        for desc in self._get_targets(label):
            self._stop(desc)
        return True

    def cmd_status(self):
        """Print running/stopped status for every configured process."""
        for desc in self._get_proc_descs():
            label = desc["label"]
            state = "RUNNING" if self._is_running(desc) else "STOPPED"
            pid_file = self._pid_file(desc)
            pid = ""
            if os.path.isfile(pid_file):
                with open(pid_file) as f:
                    pid = f"  (PID {f.read().strip()})"
            print(f"  {state:8s}  {label}{pid}")
        return True

    # -------------------------------------------------------------------------
    # Process lifecycle helpers
    # -------------------------------------------------------------------------

    def _is_running(self, desc):
        """Return True if the tracked PID is alive and matches the cmd_pattern."""
        pid_file = self._pid_file(desc)
        if not os.path.isfile(pid_file):
            return False
        try:
            with open(pid_file) as f:
                pid = int(f.read().strip())
        except (ValueError, OSError):
            return False

        try:
            os.kill(pid, 0)
        except OSError:
            return False

        # Optionally verify the process identity via /proc/<pid>/cmdline.
        pattern = desc.get("cmd_pattern", None)
        if pattern:
            try:
                with open(f"/proc/{pid}/cmdline") as f:
                    if pattern not in f.read():
                        return False
            except OSError:
                return False

        return True

    def _resolve_cmd(self, desc):
        """Use the Runner's resolution pipeline to expand ${PYTHON}, custom_python_env,
        python_path, env_vars, cwd, etc. — exactly as a script desc would be handled.

        Returns (cmd_list, cwd_str, env_dict).
        """
        runner = self.get_component("runner")

        # Build a minimal script desc that the Runner understands.
        # We pass through every key the runner knows about so placeholder
        # expansion, python env lookup and PATH injection all work correctly.
        script_desc = {
            k: v
            for k, v in desc.items()
            if k not in ("label", "enabled", "cmd_pattern", "notify", "notify_channel", "log_file", "pid_file")
        }

        # Resolve using the runner's full hlocs + pyenv pipeline.
        hlocs = self.ctx.get_known_vars()
        hlocs["${NVP_ROOT_DIR}"] = self.ctx.get_root_dir()
        hlocs["${HOME}"] = self.ctx.get_home_dir()

        # Resolve custom_python_env → ${PYTHON} exactly as the runner does.
        tools = self.get_component("tools")
        pdesc = tools.get_tool_desc("python")
        additional_paths = []

        env_name = desc.get("custom_python_env", None)
        if env_name is not None:
            pyenv = self.get_component("pyenvs")
            env_dir = pyenv.get_py_env_dir(env_name)
            pyenv_dir = self.get_path(env_dir, env_name)
            if not self.dir_exists(pyenv_dir):
                self.info("Creating python env %s...", env_name)
                pyenv.setup_py_env(env_name)
            py_path = self.get_path(pyenv_dir, pdesc["sub_path"])
            hlocs["${PYTHON_DIR}"] = self.get_parent_folder(py_path)
            additional_paths.append(self.get_parent_folder(py_path))
        else:
            py_path = tools.get_tool_path("python")

        hlocs["${PYTHON}"] = py_path
        hlocs["${PY_ENV_DIR}"] = self.get_parent_folder(py_path)

        # Resolve the cmd string → list.
        raw_cmd = self.ctx.resolve_object(desc, "cmd")
        if isinstance(raw_cmd, str):
            raw_cmd = runner.fill_placeholders(raw_cmd, hlocs)
            cmd = [c for c in raw_cmd.split(" ") if c]
        else:
            cmd = [runner.fill_placeholders(c, hlocs) for c in raw_cmd if c]

        # Resolve cwd.
        cwd = runner.fill_placeholders(desc.get("cwd", self.get_cwd()), hlocs)

        # Build environment: start from os.environ, add additional_paths, then env_vars.
        env = os.environ.copy()

        sep = ":" if self.is_linux else ";"
        if additional_paths:
            env["PATH"] = sep.join(additional_paths) + sep + env.get("PATH", "")

        for key, val in desc.get("env", {}).items():
            env[key] = runner.fill_placeholders(val, hlocs)

        # Inject PYTHONPATH if requested.
        if "python_path" in desc:
            elems = [runner.fill_placeholders(e, hlocs).replace("\\", "/") for e in desc["python_path"]]
            env["PYTHONPATH"] = sep.join(elems)

        env["PWD"] = cwd

        return cmd, cwd, env

    def _start(self, desc, reason=""):
        """Launch the process, redirect stdout/stderr to its log file, save the PID."""
        label = desc["label"]
        pid_file = self._pid_file(desc)
        log_file = self.ctx.resolve_path(desc["log_file"])

        self.make_folder(os.path.dirname(log_file))

        cmd, cwd, env = self._resolve_cmd(desc)

        self._log(f"[{label}] Starting ({reason}): {' '.join(cmd)}")

        with open(log_file, "a", encoding="utf-8") as lf:
            lf.write(f"\n{'=' * 60}\n")
            lf.write(f"[{self._ts()}] Started by proc_manager ({reason})\n")
            lf.write(f"cmd: {' '.join(cmd)}\ncwd: {cwd}\n")
            lf.write(f"{'=' * 60}\n")
            proc = subprocess.Popen(
                cmd,
                cwd=cwd,
                env=env,
                stdout=lf,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )

        with open(pid_file, "w") as pf:
            pf.write(str(proc.pid))

        self._log(f"[{label}] Started with PID {proc.pid}")
        self._notify(
            desc,
            f":white_check_mark: **[proc_manager]** `{label}` started (PID {proc.pid}) — reason: _{reason}_",
        )

    def _stop(self, desc, timeout=5):
        """Gracefully stop a process (SIGTERM → wait → SIGKILL)."""
        label = desc["label"]
        pid_file = self._pid_file(desc)

        if not os.path.isfile(pid_file):
            self._log(f"[{label}] No PID file — was not running.")
            return

        try:
            with open(pid_file) as f:
                pid = int(f.read().strip())
        except (ValueError, OSError):
            os.remove(pid_file)
            return

        if not self._is_running(desc):
            self._log(f"[{label}] PID {pid} not running (stale PID file removed).")
            os.remove(pid_file)
            return

        self._log(f"[{label}] Stopping PID {pid}...")
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
            self._log(f"[{label}] Did not stop cleanly — force killing PID {pid}.")
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass

        if os.path.isfile(pid_file):
            os.remove(pid_file)
        self._log(f"[{label}] Stopped.")

    # -------------------------------------------------------------------------
    # Utilities
    # -------------------------------------------------------------------------

    def _get_proc_descs(self):
        """Return the list of process descriptors from config."""
        return self.config.get("processes", [])

    def _get_targets(self, label):
        """Filter process descs by label (None = all)."""
        return [d for d in self._get_proc_descs() if label is None or d["label"] == label]

    def _pid_file(self, desc):
        """Resolve the PID file path for a descriptor."""
        pid_dir = self.ctx.resolve_path(self.config.get("pid_dir", "/tmp"))
        default = os.path.join(pid_dir, f"nvp_{desc['label'].replace(' ', '_')}.pid")
        return self.ctx.resolve_path(desc.get("pid_file", default))

    def _ts(self):
        """Return a formatted timestamp."""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _log(self, message):
        """Write a timestamped line to the shared process_manager log."""
        line = f"[{self._ts()}] {message}"
        shared_log = self.ctx.resolve_path(self.config.get("log_file"))
        self.make_folder(os.path.dirname(shared_log))
        with open(shared_log, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        self.info(message)

    def _notify(self, desc, message):
        """Send a RocketChat message if notify=True for this process."""
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

    context.build_parser("check")

    psr = context.build_parser("restart")
    psr.add_str("-l", "--label", dest="label")("Label of the process to restart")

    psr = context.build_parser("stop")
    psr.add_str("-l", "--label", dest="label")("Label of the process to stop")

    context.build_parser("status")

    comp.run()
