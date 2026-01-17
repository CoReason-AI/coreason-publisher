# Architecture

## Executive Summary

coreason-publisher acts as the **Regulatory Gatekeeper** and **Artifact Packager** for the CoReason platform. It ensures that any agent moving from a development state (mutable drafts) to a production state (immutable artifacts) adheres to strict GxP governance and MLOps best practices.

It addresses the "Big AI" problem where agents consist of code, prompts, test evidence, and model weights. The publisher bundles these into a verifiable package, manages Git LFS for large assets, and enforces a two-stage governance workflow (Submission -> SRB Approval).

## Functional Philosophy

The system implements the **Package-Propose-Approve-Merge Loop**:

1.  **The "Thick" Artifact:** A release is monolithic, containing exact prompts, code, test data, and model weights.
2.  **Governance as Code:** SRB approval is a cryptographic state transition blocking the merge until signed.
3.  **Semantic Versioning (SemVer):** Automatic version management based on change type (Patch/Minor/Major).
4.  **Reproducibility:** Locking the "Council of Models" (LLM versions used for testing) in the release manifest.

## Core Components

### 1. The Artifact Bundler
Aggregates assets into a standardized deployment folder.
- **Large File Support (LFS):** Automatically handles files >100MB via Git LFS.
- **Model Co-Location:** Manages local distilled models and remote pointers for very large models.
- **Council Snapshot:** Locks the judge models used for validation (`council_manifest.lock`).

### 2. The Workflow Engine
Manages the state transitions between SRE (Developer) and SRB (Reviewer).
- **Proposal (SRE):** Creates feature branch, bundles artifact, opens Merge Request (MR), locks Foundry Draft.
- **Review (SRB):** Reviews CoA and Diff.
- **Release (System):** Triggered by SRB Signature, merges MR, tags release, unlocks Foundry as RELEASED.

### 3. The Version Manager
Automates SemVer logic.
- Calculates new version string based on input (Bugfix/Feature/Breaking) and updates `agent.yaml` and `CHANGELOG.md`.

### 4. The Electronic Signer
Implements 21 CFR Part 11 Compliance.
- Captures SRE signature at submission and SRB signature at approval.
- Injects signatures into the Git Commit Message for audit trails.

## Integration Ecosystem

- **Git Remote (GitLab/GitHub):** For MR management and LFS storage.
- **coreason-foundry:** UI for submission and approval.
- **coreason-assay:** Source of the latest passing report (Evidence).

## Data Structure

The repository structure managed by the Publisher:

```text
/ (Root)
├── agent.yaml             # Config, Version, & Remote Model Hashes
├── CHANGELOG.md           # Auto-generated history
├── council_manifest.lock  # LLM Dependency Lockfile
├── CERTIFICATE.md         # The Signed CoA (Markdown)
├── src/
│   ├── system_prompt.txt
│   └── logic.py
├── models/                # GIT LFS MANAGED
│   ├── adapter_config.json
│   └── adapter_model.bin  # Fine-Tuned Weights
├── data/                  # GIT LFS MANAGED
│   ├── bec_corpus.jsonl   # The Verification Dataset
│   └── synthesis_map.json # Data Provenance
└── evidence/
    └── assay_report.json  # Pass/Fail Metrics
```
