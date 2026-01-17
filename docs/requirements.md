# Product Requirements Document: coreason-publisher

**(SRB Governance & Model Registry)**

**Domain:** Release Management, GxP Governance, & MLOps
**Architectural Role:** The Regulatory Gatekeeper & Artifact Packager
**Core Philosophy:** "Code + Weights + Evidence = The Release. Nothing merges without SRB Signature."
**Dependencies:** coreason-foundry (Drafts), coreason-assay (Evidence), coreason-vault (Secrets), GitLab/GitHub API (Upstream)

---

## 1. Executive Summary

coreason-publisher is the "Final Gatekeeper" of the CoReason platform. It orchestrates the transition of an agent from a mutable "Development Experiment" to an immutable "Clinical-Grade Product."

It solves the "Big AI" problem in GxP environments. Agents are not just code; they are a complex dependency of Logic (Prompts), Evidence (Test Results), and Binary Assets (Fine-Tuned Weights). This package bundles these diverse assets into a verifiable package, manages the **Git LFS (Large File Storage)** pointers for heavy models, and enforces a strict **Two-Stage Governance Workflow** (Submission $\to$ SRB Approval) before any code reaches production.

## 2. Functional Philosophy

The agent must implement the **Package-Propose-Approve-Merge Loop**:

1.  **The "Thick" Artifact:** A release is monolithic. It must contain the *exact* Prompts, Code, Test Data, and Model Weights used during validation. If one piece is missing, the release is void.
2.  **Governance as Code:** The Scientific Review Board (SRB) approval is a digital state transition, not an email. coreason-publisher blocks the Git merge until a cryptographically signed approval from an authorized SRB member is registered.
3.  **Semantic Versioning (SemVer):** The tool manages versioning (v1.0 $\to$ v1.1) automatically based on the nature of the change (Patch/Minor/Major), preventing human error.
4.  **Reproducibility:** The "Council of Models" (the specific LLM versions used for testing) must be locked in the release manifest to ensure the test results are reproducible 5 years from now.

---

## 3. Core Functional Requirements (Component Level)

### 3.1 The Artifact Bundler (The Heavy Lifter)

**Concept:** Aggregates scattered assets into a standardized deployment folder.

*   **Large File Support (LFS):** Automatically detects files $>100$MB (e.g., .pt, .safetensors, huge JSONL). Configures .gitattributes to handle these via Git LFS.
*   **Model Co-Location:**
    *   **Local Distillation:** Moves fine-tuned adapter weights (e.g., LoRA) into models/distilled/.
    *   **Remote Pointers:** If a model is too large for LFS (e.g., 70GB), creates a **Permanent Pointer** to immutable storage (S3/Artifactory) and hashes the remote file.
*   **Council Snapshot:** Generates council_manifest.lock.
    *   *Content:* {"proposer_a": "gpt-4-0613", "judge": "claude-3-opus-20240229"}.
    *   *Goal:* Locks the "Judges" used to validate the agent.

### 3.2 The Workflow Engine (The State Machine)

**Concept:** Manages the handoff between SRE (Developer) and SRB (Reviewer).

*   **Stage 1: Proposal (SRE):**
    *   Creates a feature branch (e.g., candidate/v1.2.0).
    *   Commits the Artifact Bundle.
    *   Opens a **Merge Request (MR)** via API.
    *   Locks the Foundry Draft (status: PENDING_SRB).
*   **Stage 2: Review (SRB):**
    *   Exposes a read-only "Review View" in the UI.
    *   Displays the CoA.md (Certificate of Analysis) and Diff.
*   **Stage 3: Release (System):**
    *   Triggered *only* by SRB Signature.
    *   Merges MR to main.
    *   Creates Git Tag v1.2.0.
    *   Unlocks Foundry (status: RELEASED).

### 3.3 The Version Manager (The Librarian)

**Concept:** Automates SemVer logic.

*   **Input:** Reads the last tag from Git (v1.1.0).
*   **Prompt:** Asks SRE: "Is this a Bugfix (Patch), Feature (Minor), or Breaking Change (Major)?"
*   **Action:** Calculates new string (v1.2.0) and updates agent.yaml and CHANGELOG.md.

### 3.4 The Electronic Signer (The GxP Lock)

**Concept:** 21 CFR Part 11 Compliance implementation.

*   **SRE Signature:** Captured at submission. Hashes the *Candidate Bundle*.
*   **SRB Signature:** Captured at approval. Hashes the *Final Release*.
*   **Audit:** Both signatures + Timestamp + UserID are injected into the Git Commit Message and sent to coreason-veritas.

---

## 4. Integration Requirements (The Ecosystem)

*   **Git Remote (GitLab/GitHub):**
    *   Requires an API Token with Repo and User scopes (for MR management).
    *   Must support SSH for LFS transfers.
*   **coreason-foundry (The UI):**
    *   Needs submit_for_review(draft_id, type) endpoint.
    *   Needs approve_release(mr_id, signature) endpoint.
*   **coreason-assay:**
    *   Publisher pulls the *latest* Passing Report. If the code has changed since the last test, it rejects the submission.

---

## 5. User Stories (Behavioral Expectations)

### Story A: The "Distilled Model" Release

**Trigger:** SRE releases an agent with a custom Fine-Tuned Llama-3 model.
**Action:** SRE selects "Submit Release" -> "Minor Version."
**Bundling:** Publisher detects adapter_model.bin (400MB). It initializes LFS tracking and moves it to models/.
**Result:** MR opened. The binary is uploaded to LFS storage, keeping the Git repo lean.

### Story B: The "SRB Kickback"

**Trigger:** SRB reviews Release v2.1.
**Finding:** The council_manifest.lock shows the agent was tested using gpt-3.5 instead of the required gpt-4.
**Action:** SRB clicks "Request Changes."
**Result:** MR is flagged "Changes Requested." Foundry Draft unlocks for SRE to re-run tests.

### Story C: The "Atomic Merge"

**Trigger:** SRB approves v2.1.
**Signature:** SRB performs MFA re-authentication.
**Execution:**

1.  System verifies hash integrity.
2.  System calls GitLab API to Merge.
3.  System Tags v2.1.
    **Result:** Production system automatically deploys v2.1 due to the new tag.

---

## 6. Data Structure (The Repository Structure)

The final directory structure in GitLab, managed by the Publisher:

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

---

## 7. Implementation Checklist for the Coding Agent

1.  **Git LFS Wrapper:** Implement a robust wrapper around git lfs. The system must check if LFS is installed and initialized before attempting a push.
2.  **API Abstraction:** Create a GitProvider abstract class. Implement GitLabProvider first, but allow for GitHubProvider later.
3.  **CoA Templating:** Use Jinja2 to render the CERTIFICATE.md file dynamically from the assay_report.json.
4.  **Atomic Rollback:** If the API call to "Merge MR" fails, the system must NOT mark the Foundry Draft as "Released." State consistency is paramount.
