#!/usr/bin/env python3
"""Compare a bounded local HAR numeric subset with explicit per-entry budgets."""
import argparse
from decimal import Decimal, InvalidOperation
import json
import os
import re
import stat
import sys

MAX_BYTES = 2 * 1024 * 1024
MAX_ENTRIES = 10000
MAX_DEPTH = 64
MAX_NODES = 100000
MAX_NUMBER_CHARS = 128
MAX_FINITE = Decimal("1.7976931348623157e308")
NUMBER = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\Z")
DEVICES = {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
DEVICES.update(prefix + digit for prefix in ("COM", "LPT") for digit in "123456789¹²³")


class InvalidInput(Exception):
    """A fixed diagnostic code, never untrusted exception text."""


def decimal_number(token):
    if len(token) > MAX_NUMBER_CHARS:
        raise InvalidInput("INVALID_NUMBER")
    try:
        value = Decimal(token)
        if not value.is_finite() or value.copy_abs() > MAX_FINITE:
            raise InvalidInput("INVALID_NUMBER")
        return value
    except (InvalidOperation, ValueError, OverflowError):
        raise InvalidInput("INVALID_NUMBER") from None


def integer_number(token):
    if len(token) > MAX_NUMBER_CHARS:
        raise InvalidInput("INVALID_NUMBER")
    return int(token)


def reject_constant(_token):
    raise InvalidInput("INVALID_NUMBER")


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InvalidInput("DUPLICATE_KEY")
        result[key] = value
    return result


def check_path(name):
    """Lexical refusal before filesystem access; this is not a backing-store audit."""
    if not name or name == "-" or any(ord(c) < 32 for c in name):
        raise InvalidInput("INVALID_PATH")
    normalized = name.replace("\\", "/")
    if normalized.startswith("//"):
        raise InvalidInput("INVALID_PATH")
    remainder = normalized
    if re.match(r"^[A-Za-z]:/", normalized):
        remainder = normalized[2:]
    if ":" in remainder:
        raise InvalidInput("INVALID_PATH")
    for part in remainder.split("/"):
        if part.rstrip(" .").split(".")[0].upper() in DEVICES:
            raise InvalidInput("INVALID_PATH")


def check_depth(text):
    depth = 0
    quoted = False
    escaped = False
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in "[{":
            depth += 1
            if depth > MAX_DEPTH:
                raise InvalidInput("DEPTH_LIMIT")
        elif char in "]}":
            depth -= 1


def check_nodes(document):
    pending = [document]
    nodes = 0
    while pending:
        value = pending.pop()
        nodes += 1
        if nodes > MAX_NODES:
            raise InvalidInput("NODE_LIMIT")
        if isinstance(value, str):
            if any(0xD800 <= ord(char) <= 0xDFFF for char in value):
                raise InvalidInput("INVALID_UNICODE")
        elif isinstance(value, list):
            pending.extend(value)
        elif isinstance(value, dict):
            pending.extend(value.keys())
            pending.extend(value.values())


def load_document(name):
    check_path(name)
    try:
        # Reject special files before open (notably FIFOs). fstat checks the
        # opened descriptor too; lexical checks cannot certify mount/symlink backing.
        info = os.stat(name)
        if not stat.S_ISREG(info.st_mode):
            raise InvalidInput("INVALID_FILE")
        if info.st_size > MAX_BYTES:
            raise InvalidInput("BYTE_LIMIT")
        with open(name, "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise InvalidInput("INVALID_FILE")
            raw = stream.read(MAX_BYTES + 1)
    except OSError:
        raise InvalidInput("FILE_ERROR") from None
    if len(raw) > MAX_BYTES:
        raise InvalidInput("BYTE_LIMIT")
    try:
        text = raw.decode("utf-8-sig", errors="strict")
        check_depth(text)
        document = json.loads(text, parse_int=integer_number,
                              parse_float=decimal_number,
                              parse_constant=reject_constant,
                              object_pairs_hook=unique_object)
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise InvalidInput("INVALID_JSON") from None
    check_nodes(document)
    return document


def inspect_document(document, time_budget, body_budget):
    if not isinstance(document, dict) or not isinstance(document.get("log"), dict):
        raise InvalidInput("INVALID_STRUCTURE")
    log = document["log"]
    entries = log.get("entries")
    if log.get("version") != "1.2" or not isinstance(entries, list):
        raise InvalidInput("INVALID_STRUCTURE")
    if len(entries) > MAX_ENTRIES:
        raise InvalidInput("ENTRY_LIMIT")
    findings = []
    counts = dict(time_over=0, body_over=0, time_unknown=0, body_unknown=0)
    for index, item in enumerate(entries, 1):
        if not isinstance(item, dict):
            raise InvalidInput("INVALID_ENTRY")
        time = item.get("time")
        if "time" in item and (type(time) not in (int, Decimal) or time < 0):
            raise InvalidInput("INVALID_TIME")
        if "response" in item and not isinstance(item["response"], dict):
            raise InvalidInput("INVALID_RESPONSE")
        response = item.get("response", {})
        body = response.get("bodySize")
        if "bodySize" in response and (type(body) is not int or body < -1):
            raise InvalidInput("INVALID_BODY_SIZE")
        for kind, value, budget in (("TIME", time, time_budget), ("BODY", body, body_budget)):
            if value is None or (kind == "BODY" and value == -1):
                counts[kind.lower() + "_unknown"] += 1
                findings.append({"entry": index, "code": kind + "_UNKNOWN"})
            elif value > budget:
                counts[kind.lower() + "_over"] += 1
                findings.append({"entry": index, "code": kind + "_OVER",
                                 "measurement": value, "budget": budget})
    return {"code": "FINDINGS" if findings else "CLEAN", "entries": len(entries),
            "budgets": {"max_time_ms": time_budget, "max_body_bytes": body_budget},
            "counts": counts, "findings": findings}


class Parser(argparse.ArgumentParser):
    def error(self, _message):
        raise InvalidInput("INVALID_ARGUMENTS")


def arguments(argv):
    parser = Parser(add_help=False, allow_abbrev=False)
    parser.add_argument("input", nargs="?")
    parser.add_argument("--max-time-ms")
    parser.add_argument("--max-body-bytes")
    parser.add_argument("--help", "-h", action="store_true")
    args = parser.parse_args(argv)
    if args.help:
        return None
    if args.input is None or args.max_time_ms is None or args.max_body_bytes is None:
        raise InvalidInput("INVALID_ARGUMENTS")
    try:
        if not NUMBER.fullmatch(args.max_time_ms):
            raise InvalidInput("INVALID_ARGUMENTS")
        time = decimal_number(args.max_time_ms)
        body_text = args.max_body_bytes
        if not re.fullmatch(r"[0-9]+", body_text) or len(body_text) > MAX_NUMBER_CHARS:
            raise InvalidInput("INVALID_ARGUMENTS")
        body = int(body_text)
        if time < 0:
            raise InvalidInput("INVALID_ARGUMENTS")
    except InvalidInput:
        raise InvalidInput("INVALID_ARGUMENTS") from None
    return args.input, time, body


def encode_report(value):
    """Emit Decimal as exact JSON numeric tokens, without float rounding."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return "{" + ",".join(json.dumps(key) + ":" + encode_report(item)
                              for key, item in value.items()) + "}"
    if isinstance(value, list):
        return "[" + ",".join(encode_report(item) for item in value) + "]"
    return json.dumps(value, allow_nan=False, separators=(",", ":"))


def main(argv=None):
    try:
        parsed = arguments(sys.argv[1:] if argv is None else argv)
        if parsed is None:
            report = {"code": "HELP", "usage_code": "INPUT_MAX_TIME_MS_MAX_BODY_BYTES_REQUIRED",
                      "limits": {"bytes": MAX_BYTES, "entries": MAX_ENTRIES,
                                 "depth": MAX_DEPTH, "nodes": MAX_NODES,
                                 "number_chars": MAX_NUMBER_CHARS}}
            status = 0
        else:
            name, time_budget, body_budget = parsed
            report = inspect_document(load_document(name), time_budget, body_budget)
            status = 1 if report["findings"] else 0
    except InvalidInput as error:
        report, status = {"code": error.args[0]}, 2
    except (OSError, ValueError, OverflowError, RecursionError):
        report, status = {"code": "OPERATIONAL_ERROR"}, 2
    try:
        sys.stdout.write(encode_report(report) + "\n")
        sys.stdout.flush()
    except OSError:
        # Avoid a second flush and Python's shutdown exit 120 on a closed pipe.
        os._exit(2)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
