"""Interactive Cloudflare R2 setup: prove the credentials, then write them to .env.

Run this on the host that owns the .env — the secret is read from a hidden
prompt, so it never enters shell history, a command line, an agent transcript,
or this file. Nothing prints it back.

    ssh -t <host> 'cd ~/horizon && .venv/bin/python scripts/setup_r2.py'

The -t matters: the prompt needs a TTY.

Credentials are saved the moment `list_buckets` answers, not at the end. An
earlier version wrote them only after every later check passed, so one failure
downstream threw away perfectly good keys and asked for them again.

The check is a real round trip: upload, fetch back over plain HTTPS with no
signature, delete. That is the only way to learn the thing no configuration
will tell you — whether a browser can play the file. `<audio src>` is fetched
unsigned, so a bucket that needs signed URLs is no use here, and finding that
out now beats debugging a silent player later.

Why R2 rather than Filebase, which this replaced: Filebase serves public
buckets only on a paid plan (measured — both URL shapes returned 403 on the
free tier), while R2 gives 10 GB, public buckets and unmetered egress for
nothing.
"""

import getpass
import os
import sys
import uuid
from pathlib import Path

import httpx

ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
REGION = "auto"
ACCOUNT_VAR = "R2_ACCOUNT_ID"
KEY_VAR = "R2_ACCESS_KEY"
SECRET_VAR = "R2_SECRET_KEY"
BUCKET_VAR = "R2_BUCKET"
# The name the narration driver actually reads. It is not R2_-prefixed on
# purpose: the value is the address the site links to, which is the Caddy
# vhost in front of the bucket, not the bucket's own r2.dev URL.
PUBLIC_VAR = "NARRATION_PUBLIC_BASE"


def read_env(path: Path) -> dict[str, str]:
    """Whatever is already in .env, so a rerun does not ask for it again."""
    if not path.exists():
        return {}
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator:
            values[key.strip()] = value.strip()
    return values


def upsert_env(path: Path, values: dict[str, str]) -> None:
    """Replace keys that are present, append the rest. Never reorders."""
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    for key, value in values.items():
        for i, line in enumerate(lines):
            if line.startswith(f"{key}="):
                lines[i] = f"{key}={value}"
                break
        else:
            lines.append(f"{key}={value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)


def ask(prompt: str, previous: str) -> str:
    shown = f"{prompt} [{previous}]: " if previous else f"{prompt}: "
    return input(shown).strip() or previous


def main() -> int:
    try:
        import boto3
        from botocore.client import Config
        from botocore.exceptions import ClientError
    except ImportError:
        print("boto3 is missing. Install the narration extra:")
        print("    uv sync --extra narration")
        return 1

    saved = read_env(ENV_PATH)
    account = ask("Account ID", saved.get(ACCOUNT_VAR, ""))
    bucket = ask("Bucket name", saved.get(BUCKET_VAR, ""))
    public_base = ask(
        "Public URL (the pub-….r2.dev one)", saved.get(PUBLIC_VAR, "")
    ).rstrip("/")
    if not (account and bucket and public_base):
        print("Account ID, bucket and public URL are all required.")
        return 1

    access_key = saved.get(KEY_VAR, "")
    secret_key = saved.get(SECRET_VAR, "")
    if access_key and secret_key:
        print(f"Using the keys already in {ENV_PATH.name} (…{access_key[-4:]}).")
    else:
        access_key = input("Access Key ID: ").strip()
        secret_key = getpass.getpass("Secret Access Key (hidden): ").strip()
        if not access_key or not secret_key:
            print("Both keys are required.")
            return 1

    client = boto3.client(
        "s3",
        endpoint_url=f"https://{account}.r2.cloudflarestorage.com",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=REGION,
        config=Config(signature_version="s3v4"),
    )

    try:
        names = [b["Name"] for b in client.list_buckets().get("Buckets", [])]
    except ClientError as error:
        code = error.response["Error"].get("Code", "?")
        print(f"Cannot list buckets ({code}): {error.response['Error'].get('Message')}")
        print("That is an authentication problem, not a bucket problem — check the")
        print("Account ID and the S3 API token in the Cloudflare dashboard.")
        return 1
    except Exception as error:  # noqa: BLE001 — a wrong account id fails at DNS
        print(f"Could not reach the endpoint: {type(error).__name__}: {error}")
        print(f"Is the Account ID right? Endpoint was https://{account}.r2.cloudflarestorage.com")
        return 1

    # The keys work. Persist before anything else can fail.
    upsert_env(ENV_PATH, {ACCOUNT_VAR: account, KEY_VAR: access_key, SECRET_VAR: secret_key})
    print("Buckets visible to this token: " + (", ".join(names) if names else "none"))
    if bucket not in names:
        print(f"'{bucket}' is not among them — check the name, or the token's scope.")
        return 1

    probe = f"_horizon-setup-probe-{uuid.uuid4().hex}.txt"
    try:
        client.put_object(
            Bucket=bucket, Key=probe, Body=b"horizon", ContentType="text/plain"
        )
    except ClientError as error:
        code = error.response["Error"].get("Code", "?")
        print(f"Upload failed ({code}): {error.response['Error'].get('Message')}")
        print("The token probably has read-only permissions; it needs Object Read & Write.")
        return 1

    url = f"{public_base}/{probe}"
    try:
        response = httpx.get(url, timeout=20, follow_redirects=True)
        status = response.status_code
        readable = status == 200 and response.text == "horizon"
        print(f"Unsigned read: HTTP {status}{' — readable' if readable else ''}")
    except httpx.HTTPError as error:
        print(f"Unsigned read failed: {type(error).__name__}: {error}")
        readable = False
    finally:
        client.delete_object(Bucket=bucket, Key=probe)

    if not readable:
        print()
        print("Upload works but the public URL does not serve it back.")
        print("In the bucket's Settings, enable the Public Development URL (r2.dev)")
        print("and make sure the value above matches it exactly.")
        return 1

    upsert_env(ENV_PATH, {BUCKET_VAR: bucket, PUBLIC_VAR: public_base})
    print()
    print(f"Upload, unsigned read and delete all worked. Saved to {ENV_PATH} (chmod 600).")
    print(f"Objects will be reachable at {public_base}/<name>.opus")
    print()
    print("The site will link them through audio.ninitux.com, which Caddy proxies")
    print("here — so the r2.dev host never appears in the pages themselves.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
