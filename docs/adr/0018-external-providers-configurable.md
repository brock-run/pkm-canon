# ADR 0018: External providers are configurable

**Status:** Proposed

## Context

LLM, embedding, reranking, telemetry, alerting, and cost capabilities vary by deployment and provider. Provider-specific requirements would unnecessarily constrain the product.

## Decision

External capabilities use configuration-backed adapter interfaces. Provider names, model names, vector dimensions, rate limits, budgets, and notification destinations are deployment configuration rather than product architecture requirements.

## Consequences

- No OpenAI-, Gemini-, Slack-, Cohere-, or Langfuse-specific API is required by the PRD.
- Database vector dimensions and reindex behavior follow configured embedding models.
- Cost controls support providers with and without usage APIs.
- Deployments may standardize on a provider without changing the canonical contract.
