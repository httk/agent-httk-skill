#!/usr/bin/env python3
"""Build deterministic skill and cross-client plugin ZIP packages."""

import argparse
import hashlib
import json
import re
import stat
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = ROOT / "skills" / "httk"
OPENAI_MANIFEST = ROOT / ".codex-plugin" / "plugin.json"
CLAUDE_MANIFEST = ROOT / ".claude-plugin" / "plugin.json"
AGENT_MANIFEST = ROOT / "plugin.json"
LICENSE_FILE = ROOT / "LICENSE"
PRIVACY_FILE = ROOT / "PRIVACY.md"
TERMS_FILE = ROOT / "TERMS.md"
DIST_DIR = ROOT / "dist"
FIXED_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
IGNORED_NAMES = {".DS_Store", "__pycache__"}
AGENT_PLUGIN_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
CLAUDE_PLUGIN_SCHEMA = "https://json.schemastore.org/claude-code-plugin-manifest.json"
COMMON_MANIFEST_KEYS = (
    "name",
    "version",
    "description",
    "author",
    "homepage",
    "repository",
    "license",
    "keywords",
)
AGENT_MANIFEST_KEYS = {"$schema", *COMMON_MANIFEST_KEYS, "extensions"}
CLAUDE_MANIFEST_KEYS = {"$schema", *COMMON_MANIFEST_KEYS, "displayName"}
SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)


def _files_under(directory: Path) -> list[Path]:
    """Return package files below *directory* in stable relative-path order."""
    files: list[Path] = []
    for path in directory.rglob("*"):
        if any(part in IGNORED_NAMES for part in path.relative_to(ROOT).parts):
            continue
        if path.is_symlink():
            raise ValueError(f"package source must not contain symlinks: {path}")
        if path.is_file():
            files.append(path)
    return sorted(files, key=lambda path: path.relative_to(ROOT).as_posix())


def _read_json(path: Path, label: str) -> dict[str, object]:
    """Read a JSON object from *path* with a useful validation error."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(f"missing {label}: {path}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid {label} JSON: {error}") from error
    if not isinstance(value, dict):
        raise TypeError(f"{label} must contain a JSON object")
    return value


def _load_metadata() -> tuple[dict[str, object], str, str]:
    """Load and validate every plugin manifest and the skill frontmatter."""
    manifest = _read_json(OPENAI_MANIFEST, "OpenAI plugin manifest")

    required_manifest = (
        "name",
        "version",
        "description",
        "author",
        "skills",
        "interface",
    )
    missing_manifest = [key for key in required_manifest if not manifest.get(key)]
    if missing_manifest:
        raise ValueError(f"plugin manifest is missing: {', '.join(missing_manifest)}")
    if manifest["name"] != "httk":
        raise ValueError("plugin manifest name must be 'httk'")
    if not SEMVER_RE.fullmatch(str(manifest["version"])):
        raise ValueError("plugin manifest version must be strict SemVer")
    if manifest["skills"] != "./skills/":
        raise ValueError("plugin manifest skills path must be './skills/'")
    author = manifest["author"]
    if not isinstance(author, dict):
        raise TypeError("plugin manifest author must be an object")
    if not author.get("name"):
        raise ValueError("plugin manifest author.name must not be empty")

    interface = manifest["interface"]
    required_interface = (
        "displayName",
        "shortDescription",
        "longDescription",
        "developerName",
        "category",
        "capabilities",
    )
    if not isinstance(interface, dict):
        raise TypeError("plugin manifest interface must be an object")
    missing_interface = [key for key in required_interface if key not in interface]
    if missing_interface:
        raise ValueError(
            f"plugin manifest interface is missing: {', '.join(missing_interface)}"
        )
    if not isinstance(interface["capabilities"], list):
        raise TypeError("plugin manifest interface.capabilities must be an array")
    prompts = interface.get("defaultPrompt", [])
    if not isinstance(prompts, list):
        raise TypeError("plugin manifest defaultPrompt must be an array")
    if not 1 <= len(prompts) <= 3:
        raise ValueError("plugin manifest defaultPrompt must contain 1 to 3 prompts")
    if any(not isinstance(prompt, str) for prompt in prompts):
        raise TypeError("each plugin default prompt must be a string")
    if any(len(prompt) > 128 for prompt in prompts):
        raise ValueError("each plugin default prompt must be at most 128 characters")
    for key in ("homepage", "repository"):
        value = manifest.get(key)
        if value is not None and not isinstance(value, str):
            raise TypeError(f"plugin manifest {key} must be a string")
        if value is not None and not value.startswith("https://"):
            raise ValueError(f"plugin manifest {key} must be an absolute HTTPS URL")
    website = interface.get("websiteURL")
    if website is not None and not isinstance(website, str):
        raise TypeError("plugin manifest interface.websiteURL must be a string")
    if website is not None and not website.startswith("https://"):
        raise ValueError("plugin manifest interface.websiteURL must be an HTTPS URL")

    claude_manifest = _read_json(CLAUDE_MANIFEST, "Claude plugin manifest")
    if set(claude_manifest) - CLAUDE_MANIFEST_KEYS:
        extras = ", ".join(sorted(set(claude_manifest) - CLAUDE_MANIFEST_KEYS))
        raise ValueError(f"Claude plugin manifest has unsupported fields: {extras}")
    if claude_manifest.get("$schema") != CLAUDE_PLUGIN_SCHEMA:
        raise ValueError("Claude plugin manifest must target the canonical schema")
    if claude_manifest.get("displayName") != "httk":
        raise ValueError("Claude plugin displayName must be 'httk'")

    agent_manifest = _read_json(AGENT_MANIFEST, "Agent Plugins manifest")
    if set(agent_manifest) - AGENT_MANIFEST_KEYS:
        extras = ", ".join(sorted(set(agent_manifest) - AGENT_MANIFEST_KEYS))
        raise ValueError(f"Agent Plugins manifest has unsupported fields: {extras}")
    if agent_manifest.get("$schema") != AGENT_PLUGIN_SCHEMA:
        raise ValueError("Agent Plugins manifest must target version 1.0.0")
    if not SKILL_NAME_RE.fullmatch(str(agent_manifest.get("name", ""))):
        raise ValueError("Agent Plugins manifest has an invalid name")
    extensions = agent_manifest.get("extensions", {})
    if not isinstance(extensions, dict) or any(
        not isinstance(value, dict) for value in extensions.values()
    ):
        raise TypeError("Agent Plugins extensions must map names to objects")

    for label, other_manifest in (
        ("Claude", claude_manifest),
        ("Agent Plugins", agent_manifest),
    ):
        for key in COMMON_MANIFEST_KEYS:
            if other_manifest.get(key) != manifest.get(key):
                raise ValueError(f"{label} manifest {key} must match OpenAI metadata")

    skill_path = SKILL_DIR / "SKILL.md"
    try:
        skill_text = skill_path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise ValueError(f"missing skill entry point: {skill_path}") from error
    if not skill_text.startswith("---\n"):
        raise ValueError("SKILL.md must start with YAML frontmatter")
    try:
        frontmatter, _body = skill_text[4:].split("\n---\n", 1)
    except ValueError as error:
        raise ValueError("SKILL.md frontmatter is not terminated") from error

    frontmatter_keys = {
        line.partition(":")[0]
        for line in frontmatter.splitlines()
        if line and not line.startswith((" ", "\t")) and ":" in line
    }
    if frontmatter_keys != {"name", "description"}:
        raise ValueError("SKILL.md frontmatter must contain only name and description")

    name = ""
    description_lines: list[str] = []
    collecting_description = False
    for line in frontmatter.splitlines():
        if line.startswith("name:"):
            name = line.partition(":")[2].strip().strip("\"'")
            collecting_description = False
        elif line.startswith("description:"):
            value = line.partition(":")[2].strip()
            collecting_description = value in {">", ">-", "|", "|-"}
            if value and not collecting_description:
                description_lines.append(value.strip("\"'"))
        elif collecting_description and line.startswith("  "):
            description_lines.append(line.strip())
        elif line.strip():
            collecting_description = False

    description = " ".join(description_lines)
    if name != "httk":
        raise ValueError("skill frontmatter name must be 'httk'")
    if not SKILL_NAME_RE.fullmatch(name):
        raise ValueError("skill name must use lower-case letters, digits, and hyphens")
    if SKILL_DIR.name != name:
        raise ValueError("skill directory name must match its frontmatter name")
    if not description:
        raise ValueError("skill frontmatter description must not be empty")
    if len(description) > 200:
        raise ValueError(
            f"skill description is {len(description)} characters; "
            "keep it at or below Claude web's 200-character limit"
        )

    return manifest, name, description


def _write_zip(destination: Path, entries: list[tuple[Path, str]]) -> None:
    """Write *entries* to *destination* with stable metadata and ordering."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        destination,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for source, archive_name in sorted(entries, key=lambda entry: entry[1]):
            mode = stat.S_IMODE(source.stat().st_mode)
            info = zipfile.ZipInfo(archive_name, FIXED_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | mode) << 16
            archive.writestr(info, source.read_bytes(), compresslevel=9)


def _checksum(path: Path) -> str:
    """Return the SHA-256 digest of *path*."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate() -> None:
    """Validate source metadata and every referenced package input."""
    _load_metadata()
    skill_files = _files_under(SKILL_DIR)
    if not skill_files:
        raise ValueError("the httk skill has no package files")
    if not (SKILL_DIR / "agents" / "openai.yaml").is_file():
        raise ValueError("missing OpenAI skill UI metadata: agents/openai.yaml")
    for manifest_path in (OPENAI_MANIFEST, CLAUDE_MANIFEST, AGENT_MANIFEST):
        if manifest_path.is_symlink():
            raise ValueError(f"plugin manifest must not be a symlink: {manifest_path}")
    if not LICENSE_FILE.is_file():
        raise ValueError(f"missing distribution license: {LICENSE_FILE}")
    if LICENSE_FILE.is_symlink():
        raise ValueError("distribution license must not be a symlink")
    skill_license = SKILL_DIR / "LICENSE"
    if not skill_license.is_file():
        raise ValueError(f"missing skill license: {skill_license}")
    if skill_license.read_bytes() != LICENSE_FILE.read_bytes():
        raise ValueError("skill and repository licenses must be identical")
    for legal_file in (PRIVACY_FILE, TERMS_FILE):
        if not legal_file.is_file():
            raise ValueError(f"missing legal page: {legal_file}")
        if legal_file.is_symlink():
            raise ValueError(f"legal page must not be a symlink: {legal_file}")
    if (ROOT / "SKILL.md").exists():
        raise ValueError("SKILL.md belongs under skills/httk, not the plugin root")


def build() -> tuple[Path, Path, Path, Path]:
    """Build and return the skill plus OpenAI, Claude, and portable plugins."""
    validate()
    skill_files = _files_under(SKILL_DIR)

    skill_archive = DIST_DIR / "httk-skill.zip"
    skill_entries = [
        (path, f"httk/{path.relative_to(SKILL_DIR).as_posix()}") for path in skill_files
    ]
    _write_zip(skill_archive, skill_entries)

    common_plugin_files = skill_files + [LICENSE_FILE, PRIVACY_FILE, TERMS_FILE]

    openai_archive = DIST_DIR / "httk-plugin.zip"
    openai_files = _files_under(ROOT / ".codex-plugin") + common_plugin_files
    openai_entries = [
        (path, f"httk/{path.relative_to(ROOT).as_posix()}") for path in openai_files
    ]
    _write_zip(openai_archive, openai_entries)

    claude_archive = DIST_DIR / "httk-claude-plugin.zip"
    claude_files = _files_under(ROOT / ".claude-plugin") + common_plugin_files
    claude_entries = [
        (path, f"httk/{path.relative_to(ROOT).as_posix()}") for path in claude_files
    ]
    _write_zip(claude_archive, claude_entries)

    agent_archive = DIST_DIR / "httk-agent-plugin.zip"
    agent_files = [AGENT_MANIFEST] + common_plugin_files
    agent_entries = [
        (path, f"httk/{path.relative_to(ROOT).as_posix()}") for path in agent_files
    ]
    _write_zip(agent_archive, agent_entries)

    return skill_archive, openai_archive, claude_archive, agent_archive


def main() -> int:
    """Validate the source tree or build every distribution archive."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate package sources without writing archives",
    )
    args = parser.parse_args()

    if args.check:
        validate()
        print("package source validation passed")
        return 0

    archives = build()
    for archive in archives:
        print(
            f"built {archive.relative_to(ROOT)} "
            f"({archive.stat().st_size} bytes, sha256={_checksum(archive)})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
