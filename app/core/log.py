import logging
import os
import re
import shutil
import sys
import traceback
from datetime import datetime, timedelta
from enum     import Enum

from app.core.constants import DATE_FORMAT, PHNOM_PENH_TZ


LOG_DIR                      = os.getenv('LOG_DIR', 'logs')
ARCHIVED_LOG_DIR             = os.path.join(LOG_DIR, 'archived')
APP_LOG_PATH                 = os.path.join(LOG_DIR, 'app.log')
TRACE_LOG_PATH               = os.path.join(LOG_DIR, 'trace.log')
ARCHIVED_LOG_FILENAME_FORMAT = '{date}-{log_type}.log'  # YYYY-MM-DD-{log_type}.log

_LOG_LINE_DATE_PATTERN = re.compile(
    r'^(?:(?:\x1b\[[0-9;]*m|\s)*\[[A-Z0-9_-]+\]\s*)*(?:\x1b\[[0-9;]*m|\s)*\[?(\d{4}-\d{2}-\d{2})[T\s]|^\s*\{"ts":\s*"([^"]+)"'
)

os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(ARCHIVED_LOG_DIR, exist_ok=True)


def _now_phnom_penh() -> datetime:
    return datetime.now(PHNOM_PENH_TZ)


def get_archived_log_path(log_type: str, date_str: str | None = None) -> str:
    if date_str is None:
        date_str = _now_phnom_penh().strftime(DATE_FORMAT)
    filename = ARCHIVED_LOG_FILENAME_FORMAT.format(date=date_str, log_type=log_type)
    return os.path.join(ARCHIVED_LOG_DIR, filename)


def _extract_line_date(line: str) -> str | None:
    match = _LOG_LINE_DATE_PATTERN.match(line)
    if not match:
        return None
    if match.group(1):
        return match.group(1)
    timestamp_text = match.group(2)
    if timestamp_text:
        try:
            parsed = datetime.fromisoformat(timestamp_text)
            if parsed.tzinfo is not None:
                parsed = parsed.astimezone(PHNOM_PENH_TZ)
            return parsed.strftime(DATE_FORMAT)
        except ValueError:
            if len(timestamp_text) >= 10 and timestamp_text[4] == '-' and timestamp_text[7] == '-':
                return timestamp_text[:10]
    return None


def _open_archive_handle(archive_handles: dict, archived_dates: set[str], log_type: str, line_date: str):
    handle = archive_handles.get(line_date)
    if handle is None:
        handle = open(get_archived_log_path(log_type=log_type, date_str=line_date), 'a', encoding='utf-8')
        archive_handles[line_date] = handle
        archived_dates.add(line_date)
    return handle


def _remove_quietly(path: str) -> None:
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass


def _archive_past_entries_from_log(log_path: str, log_type: str, today_str: str) -> set[str]:
    archived_dates: set[str] = set()
    if not os.path.isfile(log_path) or os.path.getsize(log_path) == 0:
        return archived_dates

    has_any_date  = False
    has_past_date = False
    try:
        with open(log_path, 'r', encoding='utf-8', errors='replace') as log_file:
            for line in log_file:
                line_date = _extract_line_date(line)
                if line_date:
                    has_any_date = True
                    if line_date < today_str:
                        has_past_date = True
                        break
    except OSError:
        return archived_dates

    if not has_any_date:
        try:
            modified_date = datetime.fromtimestamp(os.path.getmtime(log_path), tz=PHNOM_PENH_TZ).strftime(DATE_FORMAT)
            if modified_date < today_str:
                destination_path = get_archived_log_path(log_type=log_type, date_str=modified_date)
                with open(log_path, 'rb') as source, open(destination_path, 'ab') as destination:
                    shutil.copyfileobj(source, destination)
                open(log_path, 'w', encoding='utf-8').close()
                archived_dates.add(modified_date)
        except OSError:
            pass
        return archived_dates

    if not has_past_date:
        return archived_dates

    # Stream through the file, archiving lines from dates < today_str into logs/archived/YYYY-MM-DD-{log_type}.log
    temp_today_path                  = f'{log_path}.tmp.{os.getpid()}'
    archive_handles : dict[str, object] = {}
    pending_header_lines : list[str] = []
    current_date    : str | None     = None

    try:
        with open(log_path, 'r', encoding='utf-8', errors='replace') as source, \
             open(temp_today_path, 'w', encoding='utf-8') as today_output:
            for line in source:
                line_date = _extract_line_date(line)
                if line_date:
                    current_date = line_date

                if current_date is None:
                    pending_header_lines.append(line)
                    continue

                if pending_header_lines:
                    if current_date >= today_str:
                        today_output.writelines(pending_header_lines)
                    else:
                        _open_archive_handle(archive_handles, archived_dates, log_type, current_date).writelines(pending_header_lines)
                    pending_header_lines.clear()

                if current_date >= today_str:
                    today_output.write(line)
                else:
                    _open_archive_handle(archive_handles, archived_dates, log_type, current_date).write(line)

            if pending_header_lines:
                today_output.writelines(pending_header_lines)
                pending_header_lines.clear()
    except OSError:
        _remove_quietly(temp_today_path)
        return archived_dates
    finally:
        for handle in archive_handles.values():
            try:
                handle.close()
            except OSError:
                pass

    # Copy remaining today's lines back and truncate in place (safe for open file descriptors)
    try:
        with open(temp_today_path, 'rb') as source, open(log_path, 'wb') as destination:
            shutil.copyfileobj(source, destination)
    except OSError:
        pass
    _remove_quietly(temp_today_path)

    return archived_dates


def rotate_logs(archive_date: str | None = None, create_empty_archive_files: bool = False) -> dict:
    """Rotate app.log and trace.log into logs/archived/YYYY-MM-DD-{log_type}.log."""
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(ARCHIVED_LOG_DIR, exist_ok=True)

    now_phnom_penh = _now_phnom_penh()
    today_str      = now_phnom_penh.strftime(DATE_FORMAT)
    if archive_date is None:
        archive_date = (now_phnom_penh - timedelta(days=1)).strftime(DATE_FORMAT)

    rotated_files: list[dict] = []
    for log_path, log_type in (
        (APP_LOG_PATH, 'app')
        , (TRACE_LOG_PATH, 'trace')
    ):
        if not os.path.exists(log_path):
            open(log_path, 'a', encoding='utf-8').close()

        archived_dates = _archive_past_entries_from_log(
            log_path    = log_path
            , log_type  = log_type
            , today_str = today_str
        )

        target_archive_path = get_archived_log_path(log_type=log_type, date_str=archive_date)
        if create_empty_archive_files and not os.path.exists(target_archive_path):
            open(target_archive_path, 'a', encoding='utf-8').close()

        rotated_files.append({
            'log_type'         : log_type
            , 'source'         : log_path
            , 'archived_file'  : os.path.basename(target_archive_path)
            , 'archived_path'  : target_archive_path
            , 'archived_bytes' : os.path.getsize(target_archive_path) if os.path.isfile(target_archive_path) else 0
            , 'active_bytes'   : os.path.getsize(log_path) if os.path.isfile(log_path) else 0
            , 'archived_dates' : sorted(archived_dates)
        })

    return {
        'archive_date'    : archive_date
        , 'today_date'    : today_str
        , 'rotated_files' : rotated_files
    }


def _normalize_log_directory() -> None:
    rotate_logs(create_empty_archive_files=False)


_normalize_log_directory()


class DailyArchiveFileHandler(logging.FileHandler):
    """FileHandler that writes to logs/{log_type}.log and rotates past-day entries to
    logs/archived/YYYY-MM-DD-{log_type}.log when the date rolls over."""

    def __init__(self, filename: str, log_type: str, mode: str = 'a', encoding: str = 'utf-8', delay: bool = True):
        self.log_type      = log_type
        self._current_date = _now_phnom_penh().strftime(DATE_FORMAT)
        super().__init__(filename=filename, mode=mode, encoding=encoding, delay=delay)


    def emit(self, record: logging.LogRecord) -> None:
        today_str = _now_phnom_penh().strftime(DATE_FORMAT)
        if today_str != self._current_date:
            self._current_date = today_str
            if self.stream:
                try:
                    self.stream.flush()
                    self.stream.close()
                except OSError:
                    pass
                self.stream = None
            _normalize_log_directory()
        super().emit(record)


class RootOnlyFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return record.name == 'root'


def _resolve_log_target() -> tuple[str, str]:
    env_log_file = os.getenv('LOG_FILE')
    if env_log_file:
        base_name = os.path.basename(env_log_file)
        return os.path.join(LOG_DIR, base_name), os.path.splitext(base_name)[0]
    return APP_LOG_PATH, 'app'


log_file_path, _active_log_type = _resolve_log_target()

handler = DailyArchiveFileHandler(
    filename   = log_file_path
    , log_type = _active_log_type
    , mode     = 'a'
    , encoding = 'utf-8'
    , delay    = True  # Delay file open until first use
)
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
handler.addFilter(RootOnlyFilter())

logging.basicConfig(
    level      = logging.INFO
    , handlers = [handler]
)

# Trace log: one JSON line per request in logs/trace.log (archived as logs/archived/YYYY-MM-DD-trace.log)
_trace_handler = DailyArchiveFileHandler(
    filename   = TRACE_LOG_PATH
    , log_type = 'trace'
    , mode     = 'a'
    , encoding = 'utf-8'
    , delay    = True
)
_trace_handler.setFormatter(logging.Formatter('%(message)s'))

trace_logger           = logging.getLogger('trace')
trace_logger.propagate = False
trace_logger.setLevel(logging.INFO)
if not trace_logger.handlers:
    trace_logger.addHandler(_trace_handler)


def _join_arguments(arguments: tuple) -> str:
    return ''.join(f' {argument}' for argument in arguments)


class Logger:

    class ERROR_LEVER_ENUM(str, Enum):
        NONE     = 'NONE'
        LOW      = 'LOW'
        MEDIUM   = 'MEDIUM'
        HIGH     = 'HIGH'
        CRITICAL = 'CRITICAL'


    class StyleModifier:
        BLUE           = '\033[94m'
        GREEN          = '\033[92m'
        RED            = '\033[91m'
        YELLOW         = '\033[93m'
        TEXT_BOLD      = '\033[1m'
        TEXT_UNDERLINE = '\033[4m'
        ENDC           = '\033[0m'


    class Error:

        def __init__(self, logger_instance):
            self.logger_instance = logger_instance


        def __log(self, *arguments, include_traceback: bool = True) -> str:
            message = _join_arguments(arguments)

            # Automatically include traceback if we're in an exception context
            if include_traceback and sys.exc_info()[0] is not None and 'traceback:' not in message.lower():
                message = f'{message} traceback: {traceback.format_exc()}'

            logging.error(f'{Logger.StyleModifier.RED}{message}{Logger.StyleModifier.ENDC}')
            return message


        def __call__(self, *arguments) -> None:
            self.__log(*arguments)


        def low(self, *arguments) -> None:
            self.__log(f'[{Logger.ERROR_LEVER_ENUM.LOW.value}]', *arguments)


        def medium(self, *arguments) -> None:
            self.__log(f'[{Logger.ERROR_LEVER_ENUM.MEDIUM.value}]', *arguments)


        def high(self, *arguments) -> None:
            self.__log(f'[{Logger.ERROR_LEVER_ENUM.HIGH.value}]', *arguments)


        def critical(self, *arguments) -> None:
            self.__log(f'[{Logger.ERROR_LEVER_ENUM.CRITICAL.value}]', *arguments)


    def __init__(self):
        self.error = Logger.Error(self)


    @staticmethod
    def info(*arguments) -> None:
        logging.info(f'{Logger.StyleModifier.BLUE}{_join_arguments(arguments)}{Logger.StyleModifier.ENDC}')


    @staticmethod
    def warn(*arguments) -> None:
        logging.warning(f'{Logger.StyleModifier.YELLOW}{_join_arguments(arguments)}{Logger.StyleModifier.ENDC}')


    @staticmethod
    def track(*arguments) -> None:
        logging.info(f'{Logger.StyleModifier.GREEN}{_join_arguments(arguments)}{Logger.StyleModifier.ENDC}')


logger = Logger()
