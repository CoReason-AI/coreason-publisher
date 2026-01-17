# coreason-publisher

> **The Regulatory Gatekeeper & Artifact Packager**

coreason-publisher is the final gatekeeper for the CoReason platform. It orchestrates the transition of an agent from a mutable "Development Experiment" to an immutable "Clinical-Grade Product."

It solves the "Big AI" problem in GxP environments by bundling diverse assets (Code, Prompts, Evidence, Weights) into a verifiable package, managing Git LFS pointers for heavy models, and enforcing a strict **Two-Stage Governance Workflow** (Submission $\to$ SRB Approval).

[![CI](https://github.com/CoReason-AI/coreason_publisher/actions/workflows/ci.yml/badge.svg)](https://github.com/CoReason-AI/coreason_publisher/actions/workflows/ci.yml)

## Key Features

-   **Artifact Bundling:** Aggregates code, data, and models into a single deployment folder.
-   **Git LFS Management:** Automatically handles large files and model weights.
-   **Governance as Code:** Blocks merges until a cryptographically signed SRB approval is received.
-   **Automated Versioning:** Manages SemVer based on change types (Patch/Minor/Major).
-   **Reproducibility:** Locks the specific "Council of Models" used for validation.

## Documentation

For detailed documentation, please refer to the `docs/` directory or the deployed MkDocs site:

-   [Architecture](docs/architecture.md)
-   [Usage Guide](docs/usage.md)
-   [Product Requirements](docs/requirements.md)

## Quick Start

### Prerequisites

-   Python 3.12+
-   Poetry
-   Git LFS

### Installation

```bash
git clone https://github.com/CoReason-AI/coreason_publisher.git
cd coreason_publisher
poetry install
```

### Basic Usage

To propose a new release (as an SRE):

```bash
poetry run python -m coreason_publisher.main propose \
    --project-id <PROJECT_ID> \
    --draft-id <DRAFT_ID> \
    --bump minor \
    --user-id <USER_ID> \
    --description "Release description"
```

For more details, see the [Usage Guide](docs/usage.md).
