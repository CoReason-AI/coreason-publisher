# Usage

## Prerequisites

Before using `coreason-publisher`, ensure you have the following:

- **Python 3.12+**
- **Poetry** (for dependency management)
- **Git LFS** installed and initialized (`git lfs install`)
- **API Token** for your Git provider (GitLab/GitHub) with repository and user scopes.

## Installation

1.  Clone the repository:
    ```bash
    git clone https://github.com/CoReason-AI/coreason_publisher.git
    cd coreason_publisher
    ```

2.  Install dependencies using Poetry:
    ```bash
    poetry install
    ```

## Configuration

Set the following environment variables (or configure them via `.env`):

- `GITLAB_TOKEN`: Your GitLab API token.
- `GITLAB_PROJECT_ID`: The ID of the GitLab project.
- `SERVER_PORT`: Port for the API server (default: 8000).
- `WORKERS`: Number of worker processes (default: 1).

## Server Mode (REST API)

`coreason-publisher` can now run as a centralized governance service.

### Running the Server

**Using Docker:**
```bash
docker run -p 8000:8000 \
  -e GITLAB_TOKEN="<token>" \
  -e GITLAB_PROJECT_ID="<id>" \
  coreason-publisher:latest
```

**Using Uvicorn:**
```bash
poetry run uvicorn coreason_publisher.server:app --host 0.0.0.0 --port 8000
```

### API Endpoints

- **POST /propose**
  Triggers a release proposal (SRE).
  ```bash
  curl -X POST http://localhost:8000/propose \
       -H "Content-Type: application/json" \
       -d '{"project_id": "123", "draft_id": "draft-456", "bump_type": "minor", "user_id": "sre-user", "description": "New features"}'
  ```

- **POST /release**
  Finalizes a release (SRB).
  ```bash
  curl -X POST http://localhost:8000/release \
       -H "Content-Type: application/json" \
       -d '{"mr_id": 789, "srb_signature": "sig-hash", "srb_user_id": "srb-user"}'
  ```

- **POST /reject**
  Rejects a release.
  ```bash
  curl -X POST http://localhost:8000/reject \
       -H "Content-Type: application/json" \
       -d '{"mr_id": 789, "draft_id": "draft-456", "reason": "Audit failed"}'
  ```

- **GET /health**
  Checks system health (LFS, GitLab connection).
  ```bash
  curl http://localhost:8000/health
  ```

## CLI Commands

The package provides a CLI for managing the release lifecycle. You can run it using `poetry run python -m coreason_publisher.main`.

### 1. Propose a Release (SRE)

Bundles artifacts, calculates the new version, signs the candidate, and opens a Merge Request.

```bash
poetry run python -m coreason_publisher.main propose \
    --project-id <PROJECT_ID> \
    --draft-id <DRAFT_ID> \
    --bump <patch|minor|major> \
    --user-id <USER_ID> \
    --description "Release description"
```

**Options:**
- `--project-id`, `-p`: Assay Project ID.
- `--draft-id`, `-d`: Foundry Draft ID.
- `--bump`, `-b`: Version bump type (`patch`, `minor`, or `major`).
- `--user-id`, `-u`: SRE User ID.
- `--description`, `-m`: Description of the release.

### 2. Finalize a Release (System/SRB)

Verifies the signature, merges the MR, tags the release, and approves it in Foundry. This is typically triggered by the SRB approval action.

```bash
poetry run python -m coreason_publisher.main release \
    --mr-id <MR_ID> \
    --signature <SIGNATURE> \
    --srb-user-id <USER_ID>
```

**Options:**
- `--mr-id`: Merge Request ID.
- `--signature`: The SRB's cryptographic signature.
- `--srb-user-id`, `-u`: SRB User ID.

### 3. Reject a Release (SRB Kickback)

Rejects a release proposal, posts a comment to the MR, and unlocks the Foundry draft for further changes.

```bash
poetry run python -m coreason_publisher.main reject \
    --mr-id <MR_ID> \
    --draft-id <DRAFT_ID> \
    --reason "Reason for rejection"
```

**Options:**
- `--mr-id`: Merge Request ID.
- `--draft-id`, `-d`: Foundry Draft ID.
- `--reason`, `-r`: Reason for the rejection.

## Workflow Example

1.  **SRE** finishes development and wants to release a new feature (minor version).
2.  **SRE** runs the `propose` command:
    ```bash
    poetry run python -m coreason_publisher.main propose -p 123 -d draft-456 -b minor -u sre-user -m "Added new model"
    ```
3.  The system bundles the artifacts (including large models via LFS), creates a branch `candidate/v1.1.0`, and opens a Merge Request.
4.  **SRB** reviews the changes and the Certificate of Analysis (CoA).
5.  **SRB** approves the release, which triggers the `release` command (via CI/CD or system integration).
    ```bash
    poetry run python -m coreason_publisher.main release --mr-id 789 --signature "valid-signature" --srb-user-id srb-user
    ```
6.  The system merges the MR to `main`, tags it as `v1.1.0`, and marks the draft as `RELEASED`.
