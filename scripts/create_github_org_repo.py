#!/usr/bin/env python3
"""
GitHub REST API (apiVersion=2026-03-10) — Create an Organization Repository
Endpoint: POST https://api.github.com/orgs/{org}/repos
Docs: https://docs.github.com/en/rest/repos/repos?apiVersion=2026-03-10#create-an-organization-repository

Supports:
  - All documented body parameters for `POST /orgs/{org}/repos`
  - Automatic token resolution from `GITHUB_TOKEN`, `GH_TOKEN`, or `gh auth token`
  - Automatic fallback to `POST /user/repos` (`--fallback-user`) when the user account
    is not yet part of an organization or when deploying directly to a personal account.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from typing import Any
import httpx

GITHUB_API_BASE = "https://api.github.com"
GITHUB_API_VERSION = "2026-03-10"


def resolve_github_token(explicit_token: str | None = None) -> str:
    """Resolves a GitHub Personal Access Token or OAuth token from env or `gh auth token`."""
    if explicit_token and explicit_token.strip():
        return explicit_token.strip()

    for env_key in ("GITHUB_TOKEN", "GH_TOKEN", "GITHUB_PAT"):
        val = os.environ.get(env_key, "").strip()
        if val:
            return val

    gh_bin = shutil.which("gh") or "/opt/homebrew/bin/gh"
    if os.path.exists(gh_bin):
        try:
            proc = subprocess.run(
                [gh_bin, "auth", "token"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                return proc.stdout.strip()
        except Exception:
            pass

    raise RuntimeError(
        "No GitHub token found. Set GITHUB_TOKEN or authenticate with `gh auth login`."
    )


def build_org_repo_payload(
    name: str,
    description: str | None = None,
    homepage: str | None = None,
    private: bool = False,
    visibility: str | None = None,
    has_issues: bool = True,
    has_projects: bool = True,
    has_wiki: bool = True,
    has_downloads: bool = True,
    is_template: bool = False,
    team_id: int | None = None,
    auto_init: bool = False,
    gitignore_template: str | None = None,
    license_template: str | None = None,
    allow_squash_merge: bool = True,
    allow_merge_commit: bool = True,
    allow_rebase_merge: bool = True,
    allow_auto_merge: bool = False,
    delete_branch_on_merge: bool = False,
    squash_merge_commit_title: str | None = None,
    squash_merge_commit_message: str | None = None,
    merge_commit_title: str | None = None,
    merge_commit_message: str | None = None,
    custom_properties: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Builds the exact JSON request body for `POST /orgs/{org}/repos` (API version 2026-03-10)."""
    payload: dict[str, Any] = {
        "name": name,
        "private": bool(private),
        "has_issues": bool(has_issues),
        "has_projects": bool(has_projects),
        "has_wiki": bool(has_wiki),
        "has_downloads": bool(has_downloads),
        "is_template": bool(is_template),
        "auto_init": bool(auto_init),
        "allow_squash_merge": bool(allow_squash_merge),
        "allow_merge_commit": bool(allow_merge_commit),
        "allow_rebase_merge": bool(allow_rebase_merge),
        "allow_auto_merge": bool(allow_auto_merge),
        "delete_branch_on_merge": bool(delete_branch_on_merge),
    }

    if description is not None:
        payload["description"] = description
    if homepage is not None:
        payload["homepage"] = homepage
    if visibility in ("public", "private"):
        payload["visibility"] = visibility
    if team_id is not None:
        payload["team_id"] = int(team_id)
    if gitignore_template:
        payload["gitignore_template"] = gitignore_template
    if license_template:
        payload["license_template"] = license_template
    if squash_merge_commit_title in ("PR_TITLE", "COMMIT_OR_PR_TITLE"):
        payload["squash_merge_commit_title"] = squash_merge_commit_title
    if squash_merge_commit_message in ("PR_BODY", "COMMIT_MESSAGES", "BLANK"):
        payload["squash_merge_commit_message"] = squash_merge_commit_message
    if merge_commit_title in ("PR_TITLE", "MERGE_MESSAGE"):
        payload["merge_commit_title"] = merge_commit_title
    if merge_commit_message in ("PR_BODY", "PR_TITLE", "BLANK"):
        payload["merge_commit_message"] = merge_commit_message
    if custom_properties:
        payload["custom_properties"] = custom_properties

    return payload


def create_organization_repository(
    org: str,
    name: str,
    token: str | None = None,
    fallback_to_user: bool = False,
    **kwargs: Any,
) -> dict[str, Any]:
    """
    Calls `POST /orgs/{org}/repos` with header `X-GitHub-Api-Version: 2026-03-10`.
    If `fallback_to_user=True` and the org is not found (404), falls back to `POST /user/repos`.
    """
    resolved_token = resolve_github_token(token)
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {resolved_token}",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
        "User-Agent": "Pawsport-Petstar-GitHub-Client/2026.03.10",
    }
    body = build_org_repo_payload(name=name, **kwargs)

    org_clean = (org or "").strip()
    url = f"{GITHUB_API_BASE}/orgs/{org_clean}/repos"

    with httpx.Client(timeout=20.0, follow_redirects=True) as client:
        resp = client.post(url, headers=headers, json=body)

        if resp.status_code == 404 and fallback_to_user:
            # Organization doesn't exist or user wants personal repo fallback
            user_body = {
                k: v
                for k, v in body.items()
                if k not in ("team_id", "custom_properties", "visibility")
            }
            user_url = f"{GITHUB_API_BASE}/user/repos"
            user_resp = client.post(user_url, headers=headers, json=user_body)
            return {
                "endpoint_used": "POST /user/repos (fallback from /orgs/{org}/repos 404)",
                "api_version": GITHUB_API_VERSION,
                "status_code": user_resp.status_code,
                "ok": user_resp.status_code in (200, 201),
                "response": user_resp.json() if user_resp.content else {},
            }

        return {
            "endpoint_used": f"POST /orgs/{org_clean}/repos",
            "api_version": GITHUB_API_VERSION,
            "status_code": resp.status_code,
            "ok": resp.status_code in (200, 201),
            "response": resp.json() if resp.content else {},
        }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a GitHub organization repository via REST API (2026-03-10)."
    )
    parser.add_argument("--org", required=True, help="Organization name (required path param)")
    parser.add_argument("--name", required=True, help="Repository name (required body param)")
    parser.add_argument(
        "--description",
        default="Pawsport.ai (Petstar) — 24-Hour Viral Pet Persona & Custom Merch Studio",
        help="Short repository description",
    )
    parser.add_argument("--homepage", default="https://www.madethis.com/business/petstar-hp5")
    parser.add_argument("--private", action="store_true", help="Create private repository")
    parser.add_argument("--visibility", choices=["public", "private"], default=None)
    parser.add_argument("--auto-init", action="store_true", help="Initialize with empty README")
    parser.add_argument("--gitignore-template", default=None, help="e.g. Python, Node")
    parser.add_argument("--license-template", default=None, help="e.g. mit, apache-2.0")
    parser.add_argument("--team-id", type=int, default=None, help="Team ID to grant access")
    parser.add_argument(
        "--fallback-user",
        action="store_true",
        help="Fallback to POST /user/repos if organization returns 404",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print request payload and exit")

    args = parser.parse_args()

    payload = build_org_repo_payload(
        name=args.name,
        description=args.description,
        homepage=args.homepage,
        private=args.private,
        visibility=args.visibility,
        auto_init=args.auto_init,
        gitignore_template=args.gitignore_template,
        license_template=args.license_template,
        team_id=args.team_id,
    )

    if args.dry_run:
        print(
            json.dumps(
                {
                    "method": "POST",
                    "url": f"{GITHUB_API_BASE}/orgs/{args.org}/repos",
                    "headers": {
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": GITHUB_API_VERSION,
                    },
                    "body": payload,
                },
                indent=2,
            )
        )
        return 0

    result = create_organization_repository(
        org=args.org,
        name=args.name,
        description=args.description,
        homepage=args.homepage,
        private=args.private,
        visibility=args.visibility,
        auto_init=args.auto_init,
        gitignore_template=args.gitignore_template,
        license_template=args.license_template,
        team_id=args.team_id,
        fallback_to_user=args.fallback_user,
    )
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
