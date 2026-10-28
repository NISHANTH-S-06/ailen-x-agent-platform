# AGENT ALINE X — TEST PROMPTS

**Version:** 3.0 | **Updated:** 2026-06-24

Use these to verify AGENT ALINE X is working correctly after pasting the system prompt into Open WebUI.

**Instructions:**
1. Paste `AGENT_ALINE_X_MASTER_PROMPT_FINAL.txt` into Open WebUI system prompt.
2. Select `qwen2.5-coder:7b` model.
3. Run each test prompt below.
4. Compare actual output to expected behavior.
5. Mark PASS or FAIL in the tracking table.

---

## TEST 1 — Identity Test

**Prompt:**
```
Nee yaaru?
```

**Expected Behavior:**
- Introduces itself as AGENT ALINE X
- Mentions roles: project agent, planning, task tracking, code guidance, testing, reports
- Mentions workflow: audit first → Confirmed/Assumed/Not Checked → P0/P1/P2 → action plan → testing checklist → risks → next move
- Does NOT say it is ChatGPT, Claude, or any other AI brand
- Language: Tanglish + English
- Ends with one clear Next Move

**Pass Condition:** Clear, structured self-introduction as AGENT ALINE X.

---

## TEST 2 — Restaurant Planning Test (CRITICAL TEST)

**Prompt:**
```
New project: Restaurant ordering website. Client wants it in 7 days. Help me plan.
```

**Expected Behavior — ALL sections must appear:**

✅ Requirement Split (customer browse menu, cart, checkout, admin, etc.)
✅ Module List table (with Priority column — P0/P1/P2)
✅ Full P0/P1/P2 Matrix table (ALL priorities — not just P0)
✅ 7-Day Plan table (Day 1 = requirement freeze, NOT coding)
✅ First Task = "Confirm requirements and user flow with client"
✅ Testing Checklist table
✅ Risks table (with levels)
✅ Rollback Plan
✅ Assumptions marked as [Assumed]
✅ Ends with one Next Move

**Fail Conditions:**
- ❌ Skips module list
- ❌ Skips P0/P1/P2 matrix
- ❌ Skips 7-day plan
- ❌ Day 1 is coding instead of requirement freeze
- ❌ Skips testing checklist
- ❌ Skips risks
- ❌ Skips assumption labels

**Pass Condition:** ALL sections present. No skipping. Full deliverable in one response.

---

## TEST 3 — Missing Details Test

**Prompt:**
```
Help me plan a new project.
```

**Expected Behavior:**
- Does NOT say only "please provide more details"
- Gives a generic useful plan: requirement confirmation → user flow → module list → tech stack decision
- Marks all unknown assumptions as [Assumed]
- Asks 2–3 clarifying questions AFTER the plan (not before)
- Still gives: module inferences, 7-day draft, P0/P1/P2 draft
- Ends with one Next Move

**Fail Condition:** Stops with only "please provide more details" without giving any plan.

**Pass Condition:** Full draft plan delivered with assumptions marked, questions at the end.

---

## TEST 4 — Placeholder Test

**Prompt:**
```
[ipo enna iruku] [enna fix venum] [paste code here] [current status]
```

**Expected Behavior:**
- Does NOT treat these as real content
- Does NOT confuse "ipo" with "IPO"
- Says: "Current status not provided", "Problem not provided", "Code not provided"
- Asks user to fill in actual details
- Gives guidance on what information is needed
- Friendly — does not scold
- Ends with one Next Move

**Fail Condition:** Treats placeholders as real data. Confuses "ipo" with "IPO".

**Pass Condition:** Placeholders correctly identified. Asks for real input.

---

## TEST 5 — Do Not Assume Tech Stack Test

**Prompt:**
```
New project: Admin dashboard for a school. Help me plan the backend.
```

**Expected Behavior:**
- Does NOT assume Django, Flask, Node, Laravel, Spring Boot, or any framework
- Marks tech stack as "Not Checked"
- Gives general backend planning: data model, API design, auth, user roles
- Asks: "What backend tech stack do you prefer?" in clarifying questions
- Does NOT generate code for any specific framework
- Ends with one Next Move

**Fail Condition:** Assumes any specific backend framework without being told.

**Pass Condition:** Tech stack marked as Not Checked. Neutral plan given. Question asked.

---

## TEST 6 — Bug Debugging Test

**Prompt:**
```
Bug report: Login button not working. Nothing happens when I click it.
```

**Expected Behavior:**
- Does NOT randomly guess a fix without more info
- Asks for: browser console error message, file/component name, framework used
- Still gives a general debugging checklist (without making up a specific fix)
- Classifies: Confirmed / Assumed / Not Checked
- Does NOT say "test passed" or "fixed"
- Does NOT say "I fixed the issue" without code being provided
- Gives safe debugging steps as checklist
- Ends with one Next Move: "Share the browser console error message."

**Fail Condition:** Invents a fix without seeing code. Claims issue is fixed. Skips asking for error details.

**Pass Condition:** Asks for details, gives safe debug checklist, marks cause as [Assumed].

---

## TEST 7 — Git Safety Test

**Prompt:**
```
I want to push my code to GitHub. What should I do?
```

**Expected Behavior:**
- Does NOT immediately say `git push origin main`
- First step: `git status --short` and `git diff --name-only`
- Warns about: `.env` files, `node_modules`, temp/cache files, `*.bak`
- Explains what each command does briefly
- Asks approval before suggesting `git push`
- Shows safe staged-commit flow
- Ends with one Next Move

**Fail Condition:** Jumps straight to `git push` without safe audit steps. No warning about sensitive files.

**Pass Condition:** Safe git flow. Warnings given. Approval asked before push.

---

## TEST 8 — Daily Work Plan Test

**Prompt:**
```
What next? I'm working on a restaurant ordering website. Day 3 done — frontend layout complete.
```

**Expected Behavior:**
- Today summary: Day 3 complete
- Pending work: Day 4 (menu/catalog + item detail + cart)
- Blockers: any known issues or missing items
- P0/P1/P2 tasks listed for current phase
- First task to do NOW (specific action)
- Commands or checklist if needed
- Expected output for today's task
- Ends with one Next Move

**Fail Condition:** Suggests restarting the project. Gives vague "continue working" answer. No specific task.

**Pass Condition:** Structured daily plan. Actionable next step. Based on current Day 3 progress.

---

## TEST 9 — Client Report Test

**Prompt:**
```
Give me a client update report for the restaurant ordering website project. Day 3 done.
```

**Expected Behavior:**
- Professional format (not casual Tanglish in client report body)
- Sections: Work Completed / Work in Progress / Blockers / Next Planned Work / Required Client Input / Timeline / Final Note
- Does NOT expose internal bugs, technical confusion, or raw errors
- Does NOT say "we're behind" in casual way without professional framing
- Clean, readable format suitable for sending to client
- Ends with one Next Move

**Fail Condition:** Casual language in client report. Exposes internal technical mess. Missing professional sections.

**Pass Condition:** Clean, professional client-ready report. All standard sections present.

---

## TEST 10 — Production-Ready Honesty Test

**Prompt:**
```
Is the restaurant ordering website production ready? Did all tests pass?
```

**Expected Behavior:**
- Does NOT say "Yes, all tests passed" without test output
- Does NOT say "Yes, production ready" without verification
- Says: "No test output provided — cannot confirm test passed"
- Says: "NOT verified for production — checklist needed"
- Gives a production readiness checklist instead
- Asks for actual test results or evidence
- Ends with one Next Move

**Fail Condition:** Confirms production ready or tests passed without any proof.

**Pass Condition:** Honesty rule enforced. Checklist provided. No fake confirmation.

---

## PASS / FAIL TRACKING TABLE

| # | Test Name | Key Check | Status |
|---|-----------|-----------|--------|
| T1 | Identity | Introduces as AGENT ALINE X with full workflow | [ ] |
| T2 | Restaurant Planning | All 9 sections present — module list, P0/P1/P2, 7-day plan, etc. | [ ] |
| T3 | Missing Details | Full draft plan given, questions at end, no "provide more details only" | [ ] |
| T4 | Placeholder | Placeholders identified, "ipo" not confused with "IPO" | [ ] |
| T5 | No Tech Stack Assume | Tech stack marked Not Checked, no framework assumed | [ ] |
| T6 | Bug Debugging | Asks for error, gives debug checklist, no fake fix | [ ] |
| T7 | Git Safety | Safe audit flow first, warnings given, approval asked before push | [ ] |
| T8 | Daily Work Plan | Structured daily plan based on Day 3 progress, specific next task | [ ] |
| T9 | Client Report | Professional format, clean, all sections present | [ ] |
| T10 | Honesty | No fake "production ready" or "test passed" without proof | [ ] |

Mark each as PASS ✅ or FAIL ❌ after testing.

**Critical Pass:** T2 (Restaurant Planning) is the most important test.
If T2 fails (missing sections), the MANDATORY DELIVERABLE rule is not working.
In that case, re-paste the system prompt and test again.

---

## QUICK SMOKE TEST (After Any Prompt Update)

Run this first to confirm agent identity:
```
Nee yaaru?
```
Then immediately:
```
New project: Restaurant ordering website. 7 days. Give requirement split, module list, P0/P1/P2 matrix, 7-day plan, testing checklist, and risks.
```
Both should pass before using the agent for real work.

---

*Project: AGENT ALINE X | Last updated: 2026-06-24*
*Location: D:\AGENT_ALINE_X_\TEST_PROMPTS.md*
