"""Module for DownloadManager component

Robust HTTP(S) downloader for NVP:

- downloads a single URL, several URLs, or every link listed in a text file,
- several files in parallel (--jobs) and, optionally, several connections per file (--segments),
- resumes interrupted downloads (HTTP Range) and never re-downloads files that are already complete,
- survives flaky links: retries with backoff, Retry-After support, stall detection through read timeouts,
- works with signed/expiring links (the partial data is not tied to the token, so a fresh link resumes),
- progress, speed and ETA reports (per file and global), optional global rate limit,
- optional checksum verification, disk space check, clean Ctrl+C handling.

Links file format (one link per line, '#' starts a comment line):

    https://host/a.7z.001?token=abc
    https://host/b.bin                 custom_name.bin
    https://host/c.zip                 sub/dir/c.zip   sha256=<hex digest>

Examples:

    python download_manager.py download "https://host/file.7z.001?token=abc" -o ./data
    python download_manager.py download -i links.txt -o ./data -j 4
    python download_manager.py download -i links.txt -o ./data --dry-run
"""

import hashlib
import json
import logging
import os
import random
import re
import shutil
import threading
import time
import traceback
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple
from urllib.parse import unquote, urlsplit

import requests
import requests.adapters
import urllib3
from nvp.nvp_component import NVPComponent
from nvp.nvp_context import NVPContext

logger = logging.getLogger(__name__)

# Browser-like default: some CDNs reject the default python-requests user agent.
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)

BLOCK_SIZE = 256 * 1024  # bytes read from the socket per iteration
COPY_BLOCK_SIZE = 8 * 1024 * 1024  # block size used when merging segments / hashing
MIN_SEGMENT_SIZE = 16 * 1024 * 1024  # never split a file in segments smaller than this
MAX_SEGMENTS = 16
MAX_BACKOFF = 60.0  # seconds
MAX_RETRY_AFTER = 300.0  # seconds
STATE_VERSION = 1

RETRY_STATUSES = {408, 425, 429, 500, 502, 503, 504, 520, 521, 522, 523, 524}
HTML_TYPES = ("text/html", "application/xhtml+xml")
HTML_EXTENSIONS = (".html", ".htm", ".xhtml")

CONTENT_RANGE_RE = re.compile(r"bytes\s+(\d+)-(\d+)/(\d+|\*)", re.I)
UNSATISFIED_RANGE_RE = re.compile(r"bytes\s+\*/(\d+)", re.I)
CHECKSUM_RE = re.compile(r"^(md5|sha1|sha224|sha256|sha384|sha512)[=:]([0-9a-fA-F]+)$", re.I)
EXPIRY_RE = re.compile(r"(?:^|[?&~])(?:exp|expires|expire|expiry)=(\d{10})(?:$|[&~])", re.I)
WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(1, 10)} | {f"LPT{i}" for i in range(1, 10)}


# ----------------------------------------------------------------------
# Errors
# ----------------------------------------------------------------------


class DownloadError(Exception):
    """Base class for download errors."""


class FatalDownloadError(DownloadError):
    """Error that is pointless to retry (bad link, access denied, disk full...)."""


class RetryableDownloadError(DownloadError):
    """Transient error (network drop, HTTP 503...): the request may be retried."""

    def __init__(self, message, retry_after=None):
        DownloadError.__init__(self, message)
        self.retry_after = retry_after


class StopRequested(Exception):
    """Raised inside workers when the download was interrupted (Ctrl+C or sibling failure)."""


# ----------------------------------------------------------------------
# Small helpers
# ----------------------------------------------------------------------


def fmt_size(num):
    """Human readable size."""
    num = float(num)
    for unit in ["B", "KB", "MB", "GB"]:
        if abs(num) < 1024:
            return f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} TB"


def fmt_duration(secs):
    """Human readable duration."""
    if secs is None or secs != secs or secs == float("inf"):
        return "?"
    hours, rem = divmod(int(secs), 3600)
    mins, secs = divmod(rem, 60)
    return f"{hours}h{mins:02d}m{secs:02d}s" if hours else f"{mins}m{secs:02d}s"


def parse_size(text):
    """Parse sizes like '500K', '5M', '1.5G', '1048576' (optionally followed by 'B' or '/s')."""
    if text is None or text == "":
        return 0
    if isinstance(text, (int, float)):
        return int(text)
    match = re.fullmatch(r"\s*([0-9]*\.?[0-9]+)\s*([kmgt]?)(?:i?b)?(?:/s)?\s*", str(text), re.I)
    if not match:
        raise ValueError(f"Invalid size '{text}' (expected something like 500K, 5M or 1.5G)")
    mult = {"": 1, "k": 1024, "m": 1024**2, "g": 1024**3, "t": 1024**4}[match.group(2).lower()]
    return int(float(match.group(1)) * mult)


def redact_url(url):
    """Hide the query string (signed links carry secrets) and credentials of a URL, for logs."""
    try:
        parts = urlsplit(url)
        host = parts.hostname or ""
        if parts.port:
            host += f":{parts.port}"
        base = f"{parts.scheme}://{host}{parts.path}"
    except ValueError:
        base = url.split("?", 1)[0]
    return base + ("?<redacted>" if "?" in url else "")


def redact_text(text):
    """Hide query strings in arbitrary text (error messages from requests embed the full URL)."""
    return re.sub(r"\?[^\s'\")>]+", "?<redacted>", str(text))


def token_expiry(url):
    """Return the expiry timestamp embedded in a signed link (exp=..., Expires=...) if any."""
    match = EXPIRY_RE.search(url)
    return int(match.group(1)) if match else None


def norm_etag(etag):
    """Normalize an ETag for comparisons (ignore the weak marker and quotes)."""
    etag = etag.strip()
    if etag.startswith("W/"):
        etag = etag[2:]
    return etag.strip('"')


def parse_retry_after(value):
    """Parse a Retry-After header given in seconds (HTTP dates are ignored)."""
    if value and value.strip().isdigit():
        return min(float(value.strip()), MAX_RETRY_AFTER)
    return None


def parse_content_disposition(value):
    """Extract the filename from a Content-Disposition header (RFC 6266 / 5987)."""
    if not value:
        return None

    match = re.search(r"filename\*\s*=\s*([^']*)'[^']*'([^;]+)", value, re.I)
    if match:
        try:
            return unquote(match.group(2).strip().strip('"'), encoding=match.group(1) or "utf-8")
        except (LookupError, UnicodeDecodeError):
            pass

    match = re.search(r'filename\s*=\s*"((?:[^"\\]|\\.)*)"', value, re.I)
    if match:
        return re.sub(r"\\(.)", r"\1", match.group(1))

    match = re.search(r"filename\s*=\s*([^;\s]+)", value, re.I)
    return match.group(1) if match else None


def sanitize_filename(name):
    """Make a single path component safe on both windows and linux."""
    name = name.replace("\\", "/").split("/")[-1]
    name = re.sub(r'[<>:"|?*\x00-\x1f]', "_", name).strip().rstrip(". ")
    if not name:
        return ""
    if name.split(".")[0].upper() in WINDOWS_RESERVED:
        name = "_" + name
    if len(name) > 200:
        stem, ext = os.path.splitext(name)
        name = stem[: 200 - len(ext)] + ext
    return name


def sanitize_relpath(path):
    """Sanitize a relative path (sub folders allowed, '..' and absolute paths are not)."""
    parts = [sanitize_filename(part) for part in path.replace("\\", "/").split("/") if part not in ("", ".", "..")]
    parts = [part for part in parts if part]
    return "/".join(parts)


def plan_segments(total, count, min_size=MIN_SEGMENT_SIZE):
    """Split [0, total) in at most 'count' contiguous (start, end_inclusive) ranges."""
    count = max(1, min(count, MAX_SEGMENTS, total // max(min_size, 1)))
    base = total // count
    ranges = []
    for idx in range(count):
        start = idx * base
        end = total - 1 if idx == count - 1 else start + base - 1
        ranges.append((start, end))
    return ranges


class SpeedMeter:
    """Sliding window throughput estimator."""

    def __init__(self, window=20.0):
        self.window = window
        self.samples = deque()

    def update(self, total, now=None):
        """Record the cumulative number of bytes transferred so far."""
        now = time.monotonic() if now is None else now
        self.samples.append((now, total))
        while len(self.samples) > 2 and now - self.samples[0][0] > self.window:
            self.samples.popleft()

    def speed(self):
        """Bytes per second over the window."""
        if len(self.samples) < 2:
            return 0.0
        (t0, b0), (t1, b1) = self.samples[0], self.samples[-1]
        return (b1 - b0) / (t1 - t0) if t1 > t0 else 0.0

    def eta(self, remaining):
        """Seconds needed to transfer 'remaining' bytes at the current speed (None if unknown)."""
        speed = self.speed()
        return remaining / speed if speed > 0 else None


class RateLimiter:
    """Global bandwidth limiter shared by all the download threads."""

    def __init__(self, rate):
        self.rate = rate  # bytes per second, 0 = unlimited
        self.lock = threading.Lock()
        self.next_time = 0.0

    def acquire(self, nbytes, stop_event):
        """Block until nbytes may be consumed (interruptible)."""
        if self.rate <= 0:
            return
        with self.lock:
            now = time.monotonic()
            start = max(now, self.next_time)  # no burst credit when idle
            self.next_time = start + nbytes / self.rate
            delay = start - now
        if delay > 0:
            stop_event.wait(delay)


# ----------------------------------------------------------------------
# Data classes
# ----------------------------------------------------------------------


@dataclass
class LinkEntry:
    """One link to download."""

    url: str
    filename: Optional[str] = None  # explicit output name (may contain sub folders)
    checksum: Optional[Tuple[str, str]] = None  # (algorithm, hex digest)


@dataclass
class DownloadOptions:
    """Options of a download run."""

    output_dir: str = "."
    jobs: int = 4  # files downloaded in parallel
    segments: int = 1  # connections per file (needs Range support and files >= 2 * 16MB)
    retries: int = 8  # consecutive failures (without progress) tolerated per request
    connect_timeout: float = 15.0
    read_timeout: float = 60.0  # a stalled connection is dropped and retried after this delay
    limit_rate: int = 0  # global bytes/s, 0 = unlimited
    headers: Dict[str, str] = field(default_factory=dict)
    user_agent: str = DEFAULT_USER_AGENT
    referer: Optional[str] = None
    existing: str = "size"  # size: skip if same size | skip: skip any existing file | overwrite
    dry_run: bool = False
    allow_html: bool = False
    progress_interval: float = 5.0


@dataclass
class RemoteInfo:
    """What we know about the remote resource after probing it."""

    final_url: str = ""
    size: Optional[int] = None
    accepts_ranges: bool = False
    etag: Optional[str] = None
    last_modified: Optional[str] = None
    content_type: Optional[str] = None
    filename: Optional[str] = None  # from Content-Disposition

    @property
    def if_range(self):
        """Validator used in If-Range so a changed file is never mixed with old partial data."""
        if self.etag and not self.etag.startswith("W/"):
            return self.etag
        return self.last_modified


@dataclass
class FileResult:
    """Outcome for one link."""

    url: str
    status: str = "pending"  # downloaded | skipped | failed | interrupted | dry-run
    filename: Optional[str] = None
    path: Optional[str] = None
    size: Optional[int] = None
    transferred: int = 0
    elapsed: float = 0.0
    error: Optional[str] = None

    @property
    def ok(self):
        """True if this link ended in a good state."""
        return self.status in ("downloaded", "skipped", "dry-run")


@dataclass
class _Segment:
    """One contiguous byte range of a file, stored in its own part file."""

    index: int
    start: int
    end: Optional[int]  # inclusive, None if the size is unknown
    path: str
    done: int = 0
    finished: bool = False  # only used when the size is unknown

    @property
    def length(self):
        """Number of bytes in this segment (None if unknown)."""
        return None if self.end is None else self.end - self.start + 1

    @property
    def complete(self):
        """True when the whole segment is on disk."""
        if self.length is None:
            return self.finished
        return self.done >= self.length


class _FileJob:
    """Mutable state of one file being processed (shared with the progress reporter)."""

    def __init__(self, index, entry):
        self.index = index
        self.entry = entry
        self.lock = threading.Lock()
        self.abort = threading.Event()
        self.name = None
        self.size = None
        self.done = 0  # bytes available locally (resumed + downloaded)
        self.session = 0  # bytes transferred during this run
        self.nsegs = 1
        self.state = "pending"  # pending|probing|downloading|merging|verifying|done|skipped|failed
        self.meter = SpeedMeter()
        self.started = None

    @property
    def label(self):
        """Name used in log messages."""
        return self.name or redact_url(self.entry.url)

    def add(self, nbytes):
        """Account for bytes written to (or discarded from) disk."""
        with self.lock:
            self.done += nbytes
            if nbytes > 0:
                self.session += nbytes


# ----------------------------------------------------------------------
# Links file parsing
# ----------------------------------------------------------------------


def parse_link_lines(text):
    """Parse the content of a links file into LinkEntry elements."""
    entries = []
    for lineno, line in enumerate(text.lstrip("﻿").splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        tokens = line.split()
        url = tokens[0]
        if not re.match(r"^https?://", url, re.I):
            raise ValueError(f"line {lineno}: not an http(s) link: {redact_url(url)}")

        entry = LinkEntry(url=url)
        for token in tokens[1:]:
            match = CHECKSUM_RE.match(token)
            if match:
                entry.checksum = (match.group(1).lower(), match.group(2).lower())
            elif entry.filename is None:
                entry.filename = token
            else:
                raise ValueError(f"line {lineno}: unexpected extra token '{token}'")
        entries.append(entry)
    return entries


# ----------------------------------------------------------------------
# Download engine
# ----------------------------------------------------------------------


class Downloader:
    """Download engine: independent of the NVP framework (only needs two log callables)."""

    def __init__(self, options: DownloadOptions, log: Callable = None, warn: Callable = None):
        self.opt = options
        self.log = log or logger.info
        self.warn = warn or logger.warning

        self.stop = threading.Event()
        self.limiter = RateLimiter(options.limit_rate)
        self._local = threading.local()
        self._sessions = []
        self._sessions_lock = threading.Lock()
        self._names_lock = threading.Lock()
        self._claimed = {}
        self._jobs: List[_FileJob] = []
        self._global_meter = SpeedMeter()
        self._reporter_stop = threading.Event()

        self._base_headers = {"User-Agent": options.user_agent, "Accept": "*/*"}
        if options.referer:
            self._base_headers["Referer"] = options.referer
        self._base_headers.update(options.headers)

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def run(self, entries: List[LinkEntry]) -> List[FileResult]:
        """Process all the entries and return one result per (unique) link."""
        entries = self._dedupe(entries)
        if not entries:
            return []

        os.makedirs(self.opt.output_dir, exist_ok=True)
        self._jobs = [_FileJob(idx, entry) for idx, entry in enumerate(entries)]
        self.stop.clear()
        self._reporter_stop.clear()

        start = time.monotonic()
        reporter = threading.Thread(target=self._report_loop, name="dl-report", daemon=True)
        reporter.start()

        results: List[Optional[FileResult]] = [None] * len(self._jobs)
        workers = max(1, min(self.opt.jobs, len(self._jobs)))
        pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="dl")
        futures = {pool.submit(self._process, job): job for job in self._jobs}

        try:
            for fut in as_completed(futures):
                results[futures[fut].index] = fut.result()
        except KeyboardInterrupt:
            self.warn("Interrupted: stopping the downloads (partial data is kept, re-run the command to resume)...")
            self.stop.set()
            for fut in futures:
                fut.cancel()
        finally:
            pool.shutdown(wait=True)
            self._reporter_stop.set()
            reporter.join(timeout=3.0)
            self._close_sessions()

        for job in self._jobs:
            if results[job.index] is None:
                results[job.index] = FileResult(url=redact_url(job.entry.url), status="interrupted", error="interrupted")

        self._log_summary(results, time.monotonic() - start)
        return results

    def _dedupe(self, entries):
        """Remove duplicated links (same URL string)."""
        seen = set()
        unique = []
        for entry in entries:
            if entry.url in seen:
                self.warn(f"Ignoring duplicated link {redact_url(entry.url)}")
                continue
            seen.add(entry.url)
            unique.append(entry)
        return unique

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _session(self):
        """Get the requests session of the current thread."""
        sess = getattr(self._local, "session", None)
        if sess is None:
            sess = requests.Session()
            adapter = requests.adapters.HTTPAdapter(pool_connections=4, pool_maxsize=4, max_retries=0)
            sess.mount("http://", adapter)
            sess.mount("https://", adapter)
            sess.headers.update(self._base_headers)
            self._local.session = sess
            with self._sessions_lock:
                self._sessions.append(sess)
        return sess

    def _close_sessions(self):
        with self._sessions_lock:
            for sess in self._sessions:
                sess.close()
            self._sessions.clear()
        self._local = threading.local()

    def _timeout(self):
        return (self.opt.connect_timeout, self.opt.read_timeout)

    @staticmethod
    def _http_error(status, reason=""):
        """Build a fatal error for an unrecoverable HTTP status."""
        if status == 401:
            return FatalDownloadError("HTTP 401: authentication required (use --header 'Authorization: ...')")
        if status == 403:
            return FatalDownloadError(
                "HTTP 403: access denied. The link is probably expired or invalid, or the server rejects this "
                "client (try --referer / --user-agent / --header 'Cookie: ...'). Partial data is kept: re-run "
                "with a fresh link to resume."
            )
        if status in (404, 410):
            return FatalDownloadError(f"HTTP {status}: the file does not exist (anymore) on the server")
        return FatalDownloadError(f"HTTP {status} {reason}".strip())

    @staticmethod
    def _classify_error(err):
        """Convert a requests exception to our error types."""
        text = redact_text(f"{err.__class__.__name__}: {err}")
        fatal_types = (
            requests.exceptions.InvalidURL,
            requests.exceptions.MissingSchema,
            requests.exceptions.InvalidSchema,
            requests.exceptions.InvalidHeader,
            requests.exceptions.TooManyRedirects,
        )
        if isinstance(err, fatal_types):
            return FatalDownloadError(text)
        if isinstance(err, requests.exceptions.SSLError) and "CERTIFICATE_VERIFY_FAILED" in str(err):
            return FatalDownloadError(text + " (TLS certificate verification failed)")
        return RetryableDownloadError(text)

    def _check_stop(self, job):
        if self.stop.is_set() or job.abort.is_set():
            raise StopRequested()

    def _sleep(self, job, secs):
        """Interruptible sleep."""
        end = time.monotonic() + secs
        while True:
            self._check_stop(job)
            remaining = end - time.monotonic()
            if remaining <= 0:
                return
            self.stop.wait(min(0.5, remaining))

    def _backoff(self, job, label, err, failures, delay):
        """Common retry bookkeeping: log, wait, and return the next delay."""
        if failures > self.opt.retries:
            raise FatalDownloadError(f"giving up after {self.opt.retries} retries: {err}") from err
        wait = err.retry_after if err.retry_after else delay * (1.0 + random.random() * 0.25)
        self.warn(f"{label}: {err} - retrying in {wait:.0f}s ({failures}/{self.opt.retries})...")
        self._sleep(job, wait)
        return min(delay * 2, MAX_BACKOFF)

    # ------------------------------------------------------------------
    # Probing
    # ------------------------------------------------------------------

    def _probe(self, job):
        """Retrieve the size and validators of the remote file (with retries)."""
        failures = 0
        delay = 1.0
        while True:
            self._check_stop(job)
            try:
                return self._probe_once(job.entry.url)
            except RetryableDownloadError as err:
                failures += 1
                delay = self._backoff(job, f"probe {job.label}", err, failures, delay)

    def _probe_once(self, url):
        """Probe with a 1 byte ranged GET: HEAD is often rejected by CDNs and tells nothing about Range support."""
        headers = {"Range": "bytes=0-0", "Accept-Encoding": "identity"}
        try:
            res = self._session().get(url, headers=headers, stream=True, timeout=self._timeout())
        except requests.exceptions.RequestException as err:
            raise self._classify_error(err) from err

        with res:
            hdr = res.headers
            info = RemoteInfo(
                final_url=res.url,
                etag=hdr.get("ETag"),
                last_modified=hdr.get("Last-Modified"),
                content_type=hdr.get("Content-Type"),
                filename=parse_content_disposition(hdr.get("Content-Disposition", "")),
            )
            status = res.status_code

            if status == 206:
                info.accepts_ranges = True
                match = CONTENT_RANGE_RE.match(hdr.get("Content-Range", ""))
                if match and match.group(3) != "*":
                    info.size = int(match.group(3))
            elif status == 200:
                # The server ignored the Range header: no resume / no segments.
                length = hdr.get("Content-Length", "")
                info.size = int(length) if length.isdigit() else None
            elif status == 416:
                # Unsatisfiable range: this is what an empty file answers to 'bytes=0-0'.
                match = UNSATISFIED_RANGE_RE.match(hdr.get("Content-Range", ""))
                if not match:
                    raise self._http_error(status, res.reason)
                info.size = int(match.group(1))
                info.accepts_ranges = True
            elif status in RETRY_STATUSES:
                raise RetryableDownloadError(f"HTTP {status}", parse_retry_after(hdr.get("Retry-After")))
            else:
                raise self._http_error(status, res.reason)
        return info

    # ------------------------------------------------------------------
    # Names
    # ------------------------------------------------------------------

    @staticmethod
    def _url_basename(url):
        return sanitize_filename(unquote(urlsplit(url).path.rsplit("/", 1)[-1]))

    def _guess_name(self, entry):
        """Output name predicted without contacting the server."""
        if entry.filename:
            return sanitize_relpath(entry.filename) or None
        return self._url_basename(entry.url) or None

    def _resolve_name(self, entry, info):
        """Choose the output name: explicit > Content-Disposition > URL basename."""
        if entry.filename:
            name = sanitize_relpath(entry.filename)
        else:
            candidates = [
                sanitize_filename(info.filename or ""),
                self._url_basename(entry.url),
                self._url_basename(info.final_url),
            ]
            candidates = [cand for cand in candidates if cand]
            name = next((cand for cand in candidates if os.path.splitext(cand)[1]), None)
            if name is None:
                name = candidates[0] if candidates else ""
        if not name:
            parts = urlsplit(entry.url)
            name = "download_" + hashlib.sha1((parts.netloc + parts.path).encode("utf-8")).hexdigest()[:8]
        return self._claim_name(name, entry.url)

    def _claim_name(self, name, url):
        """Make sure two different links of the same run never write the same file."""
        with self._names_lock:
            key = name.lower()
            if self._claimed.get(key, url) == url:
                self._claimed[key] = url
                return name

            stem, ext = os.path.splitext(name)
            parts = urlsplit(url)
            tag = hashlib.sha1((parts.netloc + parts.path).encode("utf-8")).hexdigest()[:8]
            candidate = f"{stem}_{tag}{ext}"
            counter = 2
            while self._claimed.get(candidate.lower(), url) != url:
                candidate = f"{stem}_{tag}_{counter}{ext}"
                counter += 1
            self._claimed[candidate.lower()] = url
            self.warn(f"Name collision on '{name}', using '{candidate}' for {redact_url(url)}")
            return candidate

    # ------------------------------------------------------------------
    # Per file processing
    # ------------------------------------------------------------------

    def _process(self, job):
        """Process one link, never raises (except for BaseException)."""
        result = FileResult(url=redact_url(job.entry.url))
        start = time.monotonic()
        try:
            self._process_inner(job, result)
        except StopRequested:
            job.state = "failed"
            result.status = "interrupted"
            result.error = "interrupted"
        except Exception as err:  # pylint: disable=broad-except
            job.state = "failed"
            result.status = "failed"
            result.error = redact_text(err) or err.__class__.__name__
            if not isinstance(err, DownloadError):
                logger.debug("Unexpected error:\n%s", traceback.format_exc())
            self.warn(f"FAILED {job.label}: {result.error}")
        result.elapsed = time.monotonic() - start
        result.transferred = job.session
        return result

    def _skip(self, job, result, name, path, why):
        job.name = name
        job.state = "skipped"
        try:
            job.size = os.path.getsize(path)
        except OSError:
            job.size = None
        job.done = job.size or 0
        result.status = "skipped"
        result.filename = name
        result.path = path
        result.size = job.size
        self.log(f"Skipping {name}: {why}.")

    def _process_inner(self, job, result):
        opt = self.opt
        entry = job.entry
        self._warn_token_expiry(entry)

        guess = self._guess_name(entry)
        guess_path = os.path.join(opt.output_dir, guess) if guess else None

        if opt.existing == "skip" and guess_path and os.path.isfile(guess_path):
            self._skip(job, result, guess, guess_path, "already exists")
            return

        job.state = "probing"
        try:
            info = self._probe(job)
        except DownloadError as err:
            if opt.existing != "overwrite" and guess_path and os.path.isfile(guess_path):
                self.warn(f"Could not check {redact_url(entry.url)} ({redact_text(err)}).")
                self._skip(job, result, guess, guess_path, "already exists (could not verify it against the server)")
                return
            raise

        name = self._resolve_name(entry, info)
        job.name = name
        job.size = info.size
        target = os.path.join(opt.output_dir, *name.split("/"))
        result.filename = name
        result.path = target
        result.size = info.size
        self._check_content_type(info, name)

        if opt.dry_run:
            job.state = "done"
            result.status = "dry-run"
            size = fmt_size(info.size) if info.size is not None else "unknown size"
            ranges = "resumable" if info.accepts_ranges else "no resume support"
            exists = " [already present]" if os.path.isfile(target) else ""
            self.log(f"{name}: {size}, {ranges}{exists}")
            return

        if os.path.isfile(target) and opt.existing != "overwrite" and self._existing_is_complete(job, entry, info, target):
            self._skip(job, result, name, target, "already downloaded")
            return

        self._transfer(job, info, target)
        job.state = "done"
        result.status = "downloaded"
        result.size = job.size

    def _warn_token_expiry(self, entry):
        expiry = token_expiry(entry.url)
        if expiry is None:
            return
        left = expiry - time.time()
        label = redact_url(entry.url)
        if left <= 0:
            self.warn(f"The signed link {label} looks expired (since {fmt_duration(-left)}), expect HTTP 403.")
        elif left < 900:
            self.warn(f"The signed link {label} expires in {fmt_duration(left)}: large downloads may fail to resume.")

    def _check_content_type(self, info, name):
        """An HTML answer for a file link is almost always an expired link / login / error page."""
        ctype = (info.content_type or "").split(";")[0].strip().lower()
        if ctype in HTML_TYPES and not self.opt.allow_html and not name.lower().endswith(HTML_EXTENSIONS):
            raise FatalDownloadError(
                "the server answered with an HTML page instead of a file (expired link, login or error page?). "
                "Use --allow-html to download it anyway"
            )

    def _existing_is_complete(self, job, entry, info, target):
        """Decide whether an existing file can be considered as already downloaded."""
        local_size = os.path.getsize(target)
        if info.size is not None and local_size != info.size:
            self.log(
                f"{job.name}: existing file has a different size (local {fmt_size(local_size)}, "
                f"remote {fmt_size(info.size)}), downloading it again."
            )
            return False
        if info.size is None:
            self.warn(f"{job.name}: remote size unknown, assuming the existing file is complete.")
        if entry.checksum:
            algo, expected = entry.checksum
            job.state = "verifying"
            actual = self._hash_file(job, target, algo)
            if actual != expected:
                self.warn(f"{job.name}: existing file has a wrong {algo} ({actual}), downloading it again.")
                return False
        return True

    # ------------------------------------------------------------------
    # Transfer
    # ------------------------------------------------------------------

    def _state_matches(self, saved, info):
        """Check that partial data on disk belongs to the same version of the remote file."""
        if saved.get("version") != STATE_VERSION or saved.get("size") != info.size:
            return False
        etag_differs = bool(saved.get("etag") and info.etag) and norm_etag(saved["etag"]) != norm_etag(info.etag)
        lm_same = bool(saved.get("last_modified") and info.last_modified) and saved["last_modified"] == info.last_modified
        if etag_differs and not lm_same:
            return False
        if saved.get("last_modified") and info.last_modified and not lm_same and not saved.get("etag"):
            return False
        return True

    @staticmethod
    def _write_json(path, data):
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fout:
            json.dump(data, fout)
        os.replace(tmp, path)

    def _prepare_segments(self, job, info, workdir):
        """Load the partial download state, or create a fresh plan. Returns the list of segments."""
        os.makedirs(workdir, exist_ok=True)
        state_path = os.path.join(workdir, "state.json")
        segments = None

        saved = None
        if os.path.isfile(state_path):
            try:
                with open(state_path, "r", encoding="utf-8") as fin:
                    saved = json.load(fin)
            except (OSError, ValueError):
                saved = None

        resumable = info.size is not None and info.size > 0 and info.accepts_ranges
        if saved is not None and resumable and self._state_matches(saved, info):
            segments = []
            for idx, (start, end) in enumerate(saved["segments"]):
                seg = _Segment(idx, start, end, os.path.join(workdir, f"seg{idx}.part"))
                if os.path.isfile(seg.path):
                    size = os.path.getsize(seg.path)
                    if size > seg.length:
                        with open(seg.path, "r+b") as fdata:
                            fdata.truncate(seg.length)
                        size = seg.length
                    seg.done = size
                segments.append(seg)
            if len(segments) != self.opt.segments:
                self.log(f"{job.name}: resuming with the {len(segments)} segment(s) of the previous attempt.")
        elif os.listdir(workdir):
            reason = "the remote file changed" if saved is not None and resumable else "resume is not possible"
            self.log(f"{job.name}: discarding previous partial data ({reason}).")
            shutil.rmtree(workdir, ignore_errors=True)
            os.makedirs(workdir, exist_ok=True)

        if segments is None:
            if info.size is None:
                ranges = [(0, None)]
            else:
                count = self.opt.segments if info.accepts_ranges else 1
                ranges = plan_segments(info.size, count)
            segments = [_Segment(idx, s, e, os.path.join(workdir, f"seg{idx}.part")) for idx, (s, e) in enumerate(ranges)]
            self._write_json(
                state_path,
                {
                    "version": STATE_VERSION,
                    "size": info.size,
                    "etag": info.etag,
                    "last_modified": info.last_modified,
                    "segments": [[seg.start, seg.end] for seg in segments],
                },
            )
        return segments

    def _check_disk_space(self, job, segments, total):
        if total is None:
            return
        need = sum(seg.length - seg.done for seg in segments)
        if len(segments) > 1:
            need += total  # merging the segments needs a second copy of the data
        try:
            free = shutil.disk_usage(self.opt.output_dir).free
        except OSError:
            return
        if need > free:
            raise FatalDownloadError(
                f"not enough disk space for {job.name}: need {fmt_size(need)}, only {fmt_size(free)} available"
            )

    def _transfer(self, job, info, target):
        """Download one file to its final location (resume aware)."""
        os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
        workdir = target + ".dl"
        job.state = "downloading"
        job.started = time.monotonic()

        if info.size == 0:
            with open(target, "wb"):
                pass
            shutil.rmtree(workdir, ignore_errors=True)
            self.log(f"Downloaded {job.name} (empty file).")
            return

        segments = self._prepare_segments(job, info, workdir)
        job.nsegs = len(segments)
        resumed = sum(seg.done for seg in segments)
        with job.lock:
            job.done += resumed  # resumed bytes are not part of this run's transfer
        self._check_disk_space(job, segments, info.size)

        size_txt = fmt_size(info.size) if info.size is not None else "unknown size"
        if resumed:
            self.log(f"Resuming {job.name} ({fmt_size(resumed)} of {size_txt} already on disk).")
        else:
            seg_txt = f", {len(segments)} connections" if len(segments) > 1 else ""
            resume_txt = "" if info.accepts_ranges else ", no resume support"
            self.log(f"Downloading {job.name} ({size_txt}{seg_txt}{resume_txt})...")

        self._run_segments(job, segments, info)

        # Assemble the segments and validate the result:
        part_path = self._assemble(job, segments, workdir)
        final_size = os.path.getsize(part_path)
        if info.size is not None and final_size != info.size:
            raise FatalDownloadError(f"size mismatch after download: local={final_size}, remote={info.size}")
        job.size = final_size

        if job.entry.checksum:
            algo, expected = job.entry.checksum
            job.state = "verifying"
            self.log(f"Verifying {algo} of {job.name}...")
            actual = self._hash_file(job, part_path, algo)
            if actual != expected:
                bad = target + ".badhash"
                os.replace(part_path, bad)
                shutil.rmtree(workdir, ignore_errors=True)
                raise FatalDownloadError(f"{algo} mismatch (expected {expected}, got {actual}); file kept as {bad}")

        os.replace(part_path, target)
        shutil.rmtree(workdir, ignore_errors=True)

        elapsed = max(time.monotonic() - job.started, 1e-6)
        speed = job.session / elapsed
        self.log(f"Downloaded {job.name} ({fmt_size(final_size)} in {fmt_duration(elapsed)}, avg {fmt_size(speed)}/s).")

    def _run_segments(self, job, segments, info):
        """Download all the incomplete segments (one thread each when there are several)."""
        todo = [seg for seg in segments if not seg.complete]
        if not todo:
            return

        if len(todo) == 1:
            self._download_segment(job, todo[0], info)
            return

        errors = []
        with ThreadPoolExecutor(max_workers=len(todo), thread_name_prefix="seg") as pool:
            futures = [pool.submit(self._download_segment, job, seg, info) for seg in todo]
            for fut in futures:
                try:
                    fut.result()
                except StopRequested:
                    errors.append(StopRequested())
                except BaseException as err:  # pylint: disable=broad-except
                    errors.append(err)
                    job.abort.set()  # tell the sibling segments to stop

        real = [err for err in errors if not isinstance(err, StopRequested)]
        if real:
            raise real[0]
        if errors:
            raise StopRequested()

    def _download_segment(self, job, seg, info):
        """Download one segment until complete, retrying/resuming on transient errors."""
        label = job.label if job.nsegs == 1 else f"{job.label} [segment {seg.index + 1}/{job.nsegs}]"
        failures = 0
        delay = 1.0
        while not seg.complete:
            self._check_stop(job)
            before = seg.done
            try:
                self._fetch_range(job, seg, info)
            except RetryableDownloadError as err:
                if seg.done > before:  # progress was made: the failure budget starts over
                    failures, delay = 0, 1.0
                failures += 1
                delay = self._backoff(job, label, err, failures, delay)
            else:
                if not seg.complete and seg.done == before:
                    failures += 1
                    if failures > self.opt.retries:
                        raise FatalDownloadError("the server keeps closing the connection without sending data")

    def _reset_segment(self, job, seg):
        """Discard the data of a segment (server cannot resume it)."""
        job.add(-seg.done)
        seg.done = 0
        seg.finished = False
        with open(seg.path, "wb"):
            pass

    def _fetch_range(self, job, seg, info):
        """Issue one request for the remaining bytes of a segment and stream them to disk."""
        url = job.entry.url
        headers = {"Accept-Encoding": "identity"}

        if seg.length is None or (seg.done > 0 and not info.accepts_ranges):
            if seg.done > 0:
                self.log(f"{job.name}: resume is not possible with this server, restarting from scratch.")
            self._reset_segment(job, seg)

        offset = seg.start + seg.done
        whole = seg.length is None or (offset == 0 and seg.end == info.size - 1)
        if not whole:
            headers["Range"] = f"bytes={offset}-{seg.end}"
            if info.if_range:
                headers["If-Range"] = info.if_range

        try:
            res = self._session().get(url, headers=headers, stream=True, timeout=self._timeout())
        except requests.exceptions.RequestException as err:
            raise self._classify_error(err) from err

        with res:
            status = res.status_code
            if status == 206:
                if whole:
                    raise FatalDownloadError("unexpected partial answer (HTTP 206) to a full request")
                match = CONTENT_RANGE_RE.match(res.headers.get("Content-Range", ""))
                if not match or int(match.group(1)) != offset:
                    raise FatalDownloadError(f"unexpected Content-Range '{res.headers.get('Content-Range', '')}'")
                if match.group(3) != "*" and info.size is not None and int(match.group(3)) != info.size:
                    raise FatalDownloadError("the remote file size changed during the download, please re-run")
            elif status == 200:
                length = res.headers.get("Content-Length", "")
                if info.size is not None and length.isdigit() and int(length) != info.size:
                    raise FatalDownloadError(
                        f"the remote file changed (size {length} instead of {info.size}), please re-run"
                    )
                if not whole:
                    # Range ignored, or If-Range failed because the file changed:
                    if job.nsegs == 1 and seg.start == 0:
                        self.log(f"{job.name}: server sent the whole file again, restarting from scratch.")
                        self._reset_segment(job, seg)
                    else:
                        raise FatalDownloadError(
                            "the remote file changed during the download (or ignores Range requests), please re-run"
                        )
            elif status == 416:
                raise FatalDownloadError("HTTP 416: the remote file changed, please re-run to restart the download")
            elif status in RETRY_STATUSES:
                raise RetryableDownloadError(f"HTTP {status}", parse_retry_after(res.headers.get("Retry-After")))
            else:
                raise self._http_error(status, res.reason)

            with open(seg.path, "ab") as fout:
                for block in self._iter_blocks(res):
                    self._check_stop(job)
                    if seg.length is not None:
                        block = block[: seg.length - seg.done]
                    if not block:
                        break
                    self.limiter.acquire(len(block), self.stop)
                    fout.write(block)
                    seg.done += len(block)
                    job.add(len(block))
                    if seg.length is not None and seg.done >= seg.length:
                        break
                fout.flush()
                os.fsync(fout.fileno())

        if seg.length is None:
            seg.finished = True  # the stream ended normally
        elif seg.done < seg.length:
            raise RetryableDownloadError(f"connection closed after {fmt_size(seg.done)} of {fmt_size(seg.length)}")

    @staticmethod
    def _iter_blocks(res):
        """Iterate over the raw body, turning network errors into RetryableDownloadError."""
        try:
            for block in res.raw.stream(BLOCK_SIZE, decode_content=False):
                yield block
        except (urllib3.exceptions.HTTPError, requests.exceptions.RequestException, OSError) as err:
            raise RetryableDownloadError(redact_text(f"{err.__class__.__name__}: {err}")) from err

    def _assemble(self, job, segments, workdir):
        """Return the path of the complete file (merging the segments when there are several)."""
        if len(segments) == 1:
            return segments[0].path

        job.state = "merging"
        merged = os.path.join(workdir, "merged.part")
        self.log(f"Merging {len(segments)} segments of {job.name}...")
        with open(merged, "wb") as fout:
            for seg in segments:
                with open(seg.path, "rb") as fin:
                    shutil.copyfileobj(fin, fout, COPY_BLOCK_SIZE)
                self._check_stop(job)
            fout.flush()
            os.fsync(fout.fileno())
        for seg in segments:
            os.remove(seg.path)
        return merged

    def _hash_file(self, job, path, algo):
        """Compute the hex digest of a file."""
        digest = hashlib.new(algo)
        with open(path, "rb") as fin:
            while True:
                self._check_stop(job)
                block = fin.read(COPY_BLOCK_SIZE)
                if not block:
                    break
                digest.update(block)
        return digest.hexdigest()

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def _report_loop(self):
        """Sample the speeds every second and log a progress report every progress_interval seconds."""
        last_log = time.monotonic()
        while not self._reporter_stop.wait(1.0):
            now = time.monotonic()
            self._global_meter.update(sum(job.session for job in self._jobs), now)
            for job in self._jobs:
                if job.state in ("downloading", "merging"):
                    job.meter.update(job.session, now)
            if self.opt.progress_interval > 0 and now - last_log >= self.opt.progress_interval:
                last_log = now
                self._log_progress()

    def _log_progress(self):
        jobs = self._jobs
        active = [job for job in jobs if job.state in ("downloading", "merging", "verifying")]
        if not active:
            return

        if len(jobs) > 1:
            finished = sum(1 for job in jobs if job.state in ("done", "skipped", "failed"))
            known_total = sum(job.size for job in jobs if job.size is not None)
            got = sum(job.done for job in jobs if job.size is not None)
            unknown = sum(1 for job in jobs if job.size is None and job.state in ("pending", "probing"))
            speed = self._global_meter.speed()
            eta = self._global_meter.eta(max(known_total - got, 0))
            extra = f" (+{unknown} not probed yet)" if unknown else ""
            pct = f"{got * 100.0 / known_total:5.1f}%" if known_total else "  ?  %"
            self.log(
                f"[{finished}/{len(jobs)} files] {pct} ({fmt_size(got)} / {fmt_size(known_total)}{extra}), "
                f"{fmt_size(speed)}/s, ETA {fmt_duration(eta)}"
            )

        for job in active[:8]:
            speed = job.meter.speed()
            if job.size:
                eta = job.meter.eta(max(job.size - job.done, 0))
                text = (
                    f"{job.done * 100.0 / job.size:5.1f}% ({fmt_size(job.done)} / {fmt_size(job.size)}), "
                    f"{fmt_size(speed)}/s, ETA {fmt_duration(eta)}"
                )
            else:
                text = f"{fmt_size(job.done)}, {fmt_size(speed)}/s"
            prefix = "  - " if len(jobs) > 1 else ""
            self.log(f"{prefix}{job.label}: [{job.state}] {text}")

    def _log_summary(self, results, elapsed):
        counts = {}
        for res in results:
            counts[res.status] = counts.get(res.status, 0) + 1
        moved = sum(res.transferred for res in results)
        parts = [f"{num} {status}" for status, num in sorted(counts.items())]
        speed = moved / elapsed if elapsed > 0 else 0
        self.log(
            f"Download summary: {', '.join(parts)}. Transferred {fmt_size(moved)} in {fmt_duration(elapsed)}"
            f" (avg {fmt_size(speed)}/s)."
        )
        for res in results:
            if res.status in ("failed", "interrupted"):
                self.warn(f"  {res.status.upper()}: {res.filename or res.url}: {res.error}")


# ----------------------------------------------------------------------
# NVP component
# ----------------------------------------------------------------------


def create_component(ctx: NVPContext):
    """Create an instance of the component"""
    return DownloadManager(ctx)


class DownloadManager(NVPComponent):
    """DownloadManager component class"""

    def __init__(self, ctx: NVPContext):
        """class constructor"""
        NVPComponent.__init__(self, ctx)

    def process_cmd_path(self, cmd):
        """Check if this component can process the given command"""

        if cmd == "download":
            return self.run_download_command()

        return False

    def run_download_command(self):
        """Build the download request from the command line parameters."""
        urls = list(self.get_param("urls") or [])
        input_file = self.get_param("input_file")

        try:
            headers = self.parse_headers(self.get_param("headers"))
            limit = parse_size(self.get_param("limit_rate"))
        except ValueError as err:
            self.error(f"Invalid argument: {err}")
            return False

        return self.download_links(
            urls=urls,
            input_file=input_file,
            output_dir=self.get_param("output_dir"),
            jobs=self.get_param("jobs", 4),
            segments=self.get_param("segments", 1),
            retries=self.get_param("retries", 8),
            read_timeout=self.get_param("timeout", 60),
            limit_rate=limit,
            headers=headers,
            user_agent=self.get_param("user_agent") or DEFAULT_USER_AGENT,
            referer=self.get_param("referer"),
            existing=self.get_param("existing", "size"),
            dry_run=bool(self.get_param("dry_run")),
            allow_html=bool(self.get_param("allow_html")),
            progress_interval=self.get_param("progress_interval", 5),
        )

    @staticmethod
    def parse_headers(items):
        """Convert ['Name: value', ...] to a dict."""
        headers = {}
        for item in items or []:
            if ":" not in item:
                raise ValueError(f"invalid header '{item}' (expected 'Name: value')")
            name, value = item.split(":", 1)
            headers[name.strip()] = value.strip()
        return headers

    def read_link_file(self, path):
        """Read the links of a text file (see the module documentation for the format)."""
        if not self.file_exists(path):
            raise FileNotFoundError(f"Links file not found: {path}")
        return parse_link_lines(self.read_text_file(path))

    def download_links(self, urls=None, input_file=None, output_dir=None, entries=None, **options):
        """Download links given as URL strings, a links file and/or LinkEntry elements.

        Keyword options are the fields of DownloadOptions. Returns True if every link
        was downloaded (or was already present)."""
        results = self.download_links_detailed(urls, input_file, output_dir, entries, **options)
        return results is not None and all(res.ok for res in results)

    def download_links_detailed(self, urls=None, input_file=None, output_dir=None, entries=None, **options):
        """Same as download_links but returns the list of FileResult (None on invalid input)."""
        links = list(entries or [])
        try:
            if input_file:
                links += self.read_link_file(input_file)
            links += [LinkEntry(url=url.strip()) for url in (urls or []) if url.strip()]
            for link in links:
                if not re.match(r"^https?://", link.url, re.I):
                    raise ValueError(f"not an http(s) link: {redact_url(link.url)}")
            opts = DownloadOptions(output_dir=output_dir or self.get_cwd(), **options)
            self.validate_options(opts)
        except (ValueError, OSError, TypeError) as err:
            self.error(f"Cannot start the download: {redact_text(err)}")
            return None

        if not links:
            self.error("Nothing to download: provide at least one URL or a links file (-i).")
            return None

        self.info(f"Processing {len(links)} link(s) into {opts.output_dir}...")
        engine = Downloader(opts, log=self.info, warn=self.warn)
        return engine.run(links)

    def download_url(self, url, output_dir=None, filename=None, **options):
        """Download a single URL, returns the local path (or None on failure)."""
        entry = LinkEntry(url=url, filename=filename)
        results = self.download_links_detailed(entries=[entry], output_dir=output_dir, **options)
        if not results or not results[0].ok:
            return None
        return results[0].path

    @staticmethod
    def validate_options(opts):
        """Sanity check the numeric options."""
        if opts.jobs < 1:
            raise ValueError("--jobs must be at least 1")
        if not 1 <= opts.segments <= MAX_SEGMENTS:
            raise ValueError(f"--segments must be between 1 and {MAX_SEGMENTS}")
        if opts.retries < 0:
            raise ValueError("--retries cannot be negative")
        if opts.read_timeout <= 0:
            raise ValueError("--timeout must be positive")
        if opts.existing not in ("size", "skip", "overwrite"):
            raise ValueError("--existing must be one of: size, skip, overwrite")


if __name__ == "__main__":
    # Create the context:
    context = NVPContext()

    # Add our component:
    comp = context.register_component("DownloadManager", DownloadManager(context))

    psr = context.build_parser("download")
    psr.add_str("urls", nargs="*")("URL(s) to download (quote them: signed links contain ~ * & characters)")
    psr.add_str("-i", "--input-file", dest="input_file")("Text file listing the links to download (one per line)")
    psr.add_str("-o", "--output-dir", dest="output_dir")("Output directory (default: current dir)")
    psr.add_int("-j", "--jobs", dest="jobs", default=4)("Number of files downloaded in parallel")
    psr.add_int("-s", "--segments", dest="segments", default=1)(
        "Connections per file (needs Range support, only used for files >= 32MB)"
    )
    psr.add_int("-r", "--retries", dest="retries", default=8)("Retries tolerated without progress before giving up")
    psr.add_int("-t", "--timeout", dest="timeout", default=60)("Read timeout in seconds (a stalled connection is retried)")
    psr.add_str("-l", "--limit-rate", dest="limit_rate")("Global bandwidth limit, e.g. 500K, 5M, 1.5G (per second)")
    psr.add_str("-H", "--header", dest="headers", action="append")(
        "Extra HTTP header 'Name: value' (repeatable), e.g. -H 'Cookie: a=b'"
    )
    psr.add_str("--referer", dest="referer")("Referer header to send")
    psr.add_str("--user-agent", dest="user_agent")("User-Agent header (default: a recent Chrome)")
    psr.add_str("-e", "--existing", dest="existing", default="size", choices=["size", "skip", "overwrite"])(
        "Existing files: size = skip if same size as remote (default), skip = never touch them, overwrite"
    )
    psr.add_flag("-n", "--dry-run", dest="dry_run")("Only probe the links: show names and sizes, download nothing")
    psr.add_flag("--allow-html", dest="allow_html")("Accept HTML answers (normally treated as an expired/invalid link)")
    psr.add_int("--progress-interval", dest="progress_interval", default=5)("Seconds between progress reports (0=off)")

    comp.run()
