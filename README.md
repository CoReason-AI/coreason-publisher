# coreason-publisher

> **The Regulatory Gatekeeper & Artifact Packager**

[![CI](https://github.com/CoReason-AI/coreason_publisher/actions/workflows/ci.yml/badge.svg)](https://github.com/CoReason-AI/coreason_publisher/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.12%20%7C%203.13%20%7C%203.14-blue)
![License](https://img.shields.io/badge/License-Prosperity%203.0-blue.svg)
![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)

coreason-publisher is the "Final Gatekeeper" of the CoReason platform. It orchestrates the transition of an agent from a mutable "Development Experiment" to an immutable "Clinical-Grade Product."

It solves the "Big AI" problem in GxP environments. Agents are not just code; they are a complex dependency of Logic (Prompts), Evidence (Test Results), and Binary Assets (Fine-Tuned Weights). This package bundles these diverse assets into a verifiable package, manages the **Git LFS (Large File Storage)** pointers for heavy models, and enforces a strict **Two-Stage Governance Workflow** (Submission $\to$ SRB Approval) before any code reaches production.

## Functional Philosophy

The agent must implement the **Package-Propose-Approve-Merge Loop**:

1. **The "Thick" Artifact:** A release is monolithic. It must contain the *exact* Prompts, Code, Test Data, and Model Weights used during validation. If one piece is missing, the release is void.
2. **Governance as Code:** The Scientific Review Board (SRB) approval is a digital state transition, not an email. coreason-publisher blocks the Git merge until a cryptographically signed approval from an authorized SRB member is registered.
3. **Semantic Versioning (SemVer):** The tool manages versioning (v1.0 $\to$ v1.1) automatically based on the nature of the change (Patch/Minor/Major), preventing human error.
4. **Reproducibility:** The "Council of Models" (the specific LLM versions used for testing) must be locked in the release manifest to ensure the test results are reproducible 5 years from now.

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
