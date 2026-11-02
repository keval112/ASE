
#!/usr/bin/env python3

"""
Check requirements against PyPI.

Features:
- Check whether packages exist.
- Check whether pinned versions exist.
- Check Python 3.11 compatibility.
- Find the highest pinned requirement.

Usage:
    python main.py
    python main.py requirements.txt
"""

import json
import re
import sys
import ssl
import urllib.error
import urllib.request

import certifi

from packaging.specifiers import SpecifierSet
from packaging.version import Version


PYPI = "https://pypi.org/pypi"

# Python version to check
PYTHON_VERSION = "3.11"

# SSL certificate configuration
SSL_CONTEXT = ssl.create_default_context(
    cafile=certifi.where()
)

# Requirements line parser
LINE_RE = re.compile(
    r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*"
    r"(?:\[[^\]]+\])?\s*"
    r"(===|==|=|>=|<=|~=|!=|>|<)?\s*"
    r"([^\s;,#]+)?"
)

# Cache PyPI responses
_cache = {}


def fetch_json(url):
    """Fetch JSON data from PyPI."""

    if url in _cache:
        return _cache[url]

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "requirements-checker/1.0"
        }
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=15,
            context=SSL_CONTEXT
        ) as response:

            data = json.load(response)

    except urllib.error.HTTPError as error:

        if error.code == 404:
            data = None
        else:
            raise

    _cache[url] = data

    return data


def parse_line(raw):
    """Parse a requirements line."""

    line = raw.split("#", 1)[0].strip()

    if not line or line.startswith("-"):
        return None

    match = LINE_RE.match(line)

    if not match:
        return None

    return (
        match.group(1),
        match.group(2),
        match.group(3)
    )


def check_python_compatibility(release):
    """Check if a release supports Python 3.11."""

    requires_python = release.get(
        "info", {}
    ).get("requires_python")

    if not requires_python:
        return True, "Not specified"

    try:
        specifier = SpecifierSet(requires_python)

        compatible = Version(PYTHON_VERSION) in specifier

        return compatible, requires_python

    except Exception:
        return True, requires_python


def main(path):

    checked = 0

    missing_packages = []
    missing_versions = []
    incompatible_packages = []

    highest_requirement = None

    network_errors = []

    # Read requirements file
    try:

        with open(path, encoding="utf-8") as file:
            lines = file.readlines()

    except FileNotFoundError:

        print(f"Error: File '{path}' not found.")
        return

    print("\nChecking dependencies against PyPI...\n")

    for raw in lines:

        parsed = parse_line(raw)

        if parsed is None:
            continue

        name, operator, version = parsed

        checked += 1

        try:

            # Check package existence
            package = fetch_json(
                f"{PYPI}/{name}/json"
            )

            if package is None:

                missing_packages.append(name)

                print(f"[MISSING PACKAGE] {name}")

                continue

            print(f"[PACKAGE FOUND] {name}")

            # Find highest pinned version
            if operator in ("==", "=", "===") and version:

                try:

                    current_version = Version(version)

                    if (
                        highest_requirement is None
                        or current_version > highest_requirement[0]
                    ):

                        highest_requirement = (
                            current_version,
                            name,
                            version
                        )

                except Exception:
                    pass

            # Check exact pinned versions
            if operator in ("==", "=", "===") and version:

                release = fetch_json(
                    f"{PYPI}/{name}/{version}/json"
                )

                if release is None:

                    missing_versions.append(
                        f"{name}=={version}"
                    )

                    print(
                        f"[MISSING VERSION] {name}=={version}"
                    )

                    continue

                print(
                    f"[VERSION FOUND] {name}=={version}"
                )

                # Check Python 3.11 compatibility
                compatible, requirement = (
                    check_python_compatibility(release)
                )

                if not compatible:

                    incompatible_packages.append(
                        f"{name}=={version} "
                        f"(requires Python {requirement})"
                    )

                    print(
                        f"[INCOMPATIBLE] {name}=={version} "
                        f"requires Python {requirement}"
                    )

                else:

                    print(
                        f"[PYTHON {PYTHON_VERSION} COMPATIBLE] "
                        f"{name}=={version}"
                    )

        except (urllib.error.URLError, TimeoutError) as error:

            network_errors.append(name)

            print(
                f"[NETWORK ERROR] {name}: {error}"
            )

            continue

        except Exception as error:

            network_errors.append(name)

            print(
                f"[ERROR] {name}: {error}"
            )

            continue

    # Final results
    print("\n========== RESULTS ==========")

    print(f"Dependencies checked: {checked}")

    print(
        f"Packages not on PyPI: {len(missing_packages)}"
    )

    print(
        f"Versions not on PyPI: {len(missing_versions)}"
    )

    print(
        f"Incompatible with Python {PYTHON_VERSION}: "
        f"{len(incompatible_packages)}"
    )

    if highest_requirement:

        _, name, version = highest_requirement

        print(
            f"Highest requirement: {name}=={version}"
        )

    else:

        print("Highest requirement: none")

    # Details
    print("\n========== DETAILS ==========")

    for name in missing_packages:

        print(f"[no such package] {name}")

    for version in missing_versions:

        print(f"[no such version] {version}")

    for package in incompatible_packages:

        print(f"[Python 3.11 incompatible] {package}")

    if network_errors:

        print("\nWARNING: Some packages could not be checked:")

        for name in network_errors:

            print(f"[could not check] {name}")

    print("\n========== CHECK COMPLETE ==========")


if __name__ == "__main__":

    requirements_file = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "requirements.txt"
    )

    main(requirements_file)
