---
id: arch-scm
title: Supply Chain Management (SCM)
type: system
status: Active
last_updated: 2025-12-08
related:
  - "[[Projects/OTP.md]]"
---

# Supply Chain Management (SCM)

## Overview

SCM encompasses the logistics and fulfillment systems that power HelloFresh Group's delivery operations. Key systems include Demeter (UK legacy) and Odin (global).

## Key Systems

### Demeter (UK)
- **Type:** Legacy logistics system
- **Status:** Active but requires updates for OTP
- **Issue:** Needs "order grouping ID" update to recognize OTP orders

### Odin
- **Type:** Global logistics platform
- **Status:** Target for OTP scaling
- **Requirement:** Integration needed for global OTP rollout

## OTP Dependencies

For OTP to scale globally, local SCM systems need updates:
- **Order Grouping ID:** Local systems must recognize this field
- **Non-subscription handling:** Systems designed for subscription orders need adaptation

## Key Contacts

- **Operations/SCM:** Seb

## Blockers

- **Scaling Blocker (P0):** Legacy local logistics systems blocking global OTP rollout

## Changelog
- **2025-12-08:** Mentioned in daily context (4x)

- **2025-12-08:** Stub created from daily context synthesis
