import sys
import inspect
import json
import traceback
import asyncio

class Tracer:
    def __init__(self):
        self.trace_log = []
        self.start_frame = None
        self.target_code = None
        self.log_file = open("tracer_debug.log", "w")

    def log(self, msg):
        self.log_file.write(msg + "\n")
        self.log_file.flush()

    def _serialize_value(self, value):
        try:
            # Try basic JSON serialization
            json.dumps(value)
            return value
        except (TypeError, OverflowError):
            # Fallback to string representation
            return str(value)

    def _trace_func(self, frame, event, arg):
        # self.log(f"Trace event: {event} in {frame.f_code.co_name} at {frame.f_lineno}")
        
        if self.start_frame is None:
            if self.target_code and frame.f_code == self.target_code:
                self.log(f"Found target code! Starting trace at {frame.f_lineno}")
                self.start_frame = frame
            else:
                # Keep tracing until we find the target
                # self.log(f"Skipping {frame.f_code.co_name}, waiting for target...")
                return self._trace_func

        # We have started tracing the target
        
        # Filter: Only trace lines in the same file as the start frame
        if frame.f_code.co_filename != self.start_frame.f_code.co_filename:
            return self._trace_func

        if event == 'line':
            locals_dict = {}
            for name, value in frame.f_locals.items():
                locals_dict[name] = self._serialize_value(value)

            # Get source line
            try:
                with open(frame.f_code.co_filename, 'r') as f:
                    all_lines = f.readlines()
                    if 0 <= frame.f_lineno - 1 < len(all_lines):
                        line_content = all_lines[frame.f_lineno - 1].strip()
                    else:
                        line_content = "<could not read source>"
            except Exception as e:
                line_content = f"<source unavailable: {e}>"

            entry = {
                "line": frame.f_lineno,
                "function": frame.f_code.co_name,
                "code": line_content,
                "locals": locals_dict
            }
            self.trace_log.append(entry)
            self.log(f"Captured line {frame.f_lineno}: {line_content}")

        return self._trace_func

    def run(self, func, *args, **kwargs):
        self.target_code = func.__code__
        self.log(f"Starting sync trace for {func.__name__}")
        sys.settrace(self._trace_func)
        try:
            return func(*args, **kwargs)
        finally:
            sys.settrace(None)
            self.log("Trace finished")

    async def run_async(self, func, *args, **kwargs):
        self.target_code = func.__code__
        self.log(f"Starting async trace for {func.__name__}")
        sys.settrace(self._trace_func)
        try:
            return await func(*args, **kwargs)
        finally:
            sys.settrace(None)
            self.log("Trace finished")

    def get_log(self):
        return self.trace_log
