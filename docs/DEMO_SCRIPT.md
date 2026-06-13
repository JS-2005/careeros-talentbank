# TalentScreen AI - Judge Walkthrough & Demo Script

## 2-Minute Quick Pitch
**Introduction:**
"Hi judges, we are presenting TalentScreen AI, a Career OS-compatible module. Currently, students struggle to know if they are truly ready for jobs, and employers waste hours on early-stage candidate screening. We solve both sides of this equation."

**Student Demo (Job Matcher):**
"For the student, our Job Matcher analyzes their resume against real market roles. *(Click Try Job Matcher -> View Sample AI Recommendation)* Instead of just listing jobs, we provide a Match Score, highlight Skill Gaps, and give actionable steps to improve. This builds career readiness."

**Employer Demo (AI Interview Report):**
"On the employer side, we help HR scale their screening. A candidate takes an AI-driven interview, and HR receives a structured decision-support report. *(Click View Employer Report Demo)* HR sees the overall readiness, strengths with direct evidence, and even suggested follow-up questions. It doesn’t make the final hiring decision; it saves HR time in deciding who to interview next."

**Closing:**
"By connecting student readiness to employer screening, TalentScreen AI brings immense value to the Career OS ecosystem."

---

## 3-Minute Extended Pitch
*(Follow the 2-minute pitch, but take time to physically execute the Live API flow instead of jumping straight to the sample fallback.)*

**Added details:**
- **Live Search (if fast):** "Notice how we extract deep job requirements and compare them to the candidate's core and soft skills."
- **Premium Model:** "The Employer Report is a premium B2B feature that Talentbank can monetize, offering deep value to enterprises using the OS."

---

## Exact Click Path

**Primary Flow (Recommended for Live Demo):**
1. **Landing Page:** Explain the concept briefly. Notice the Judge Walkthrough Path.
2. **Click:** `Try Job Matcher`
3. **If Demo Account has no resume (or to save time):** 
   - **Click:** `View Sample AI Recommendation` directly from the placeholder.
4. **Job Detail Drawer:** Explain the Match Score, Skill Gaps, and Recommended Actions.
5. **Drawer CTAs:** Scroll to bottom and explain the transition.
6. **Click:** `View Employer Report Demo`
7. **Employer Report:** Walk through the Candidate Overview, Score Breakdown, Evidence, and HR Follow-ups.
8. **Click:** `Print / Export Report` (to show exportability).
9. **Click:** `Back to Home` to return.

**Live API Flow (Use only if connection is fast):**
1. Upload resume / enter Search Query -> `Submit`
2. Wait for loading stages.
3. Show extracted jobs -> `Switch to Recommendations Tab`.
4. Open the top matched job.

---

## Backup Path (If Live API is Slow)
If the live APIs take too long, or the connection drops:
1. Explain: "Since we are running live semantic extraction over the web, it takes a few moments. The sample fallback is intentionally included for judging stability and is clearly labelled as demo data."
2. **Click:** The `View Sample AI Recommendation` button (available in the Error popup, No Resume alert, or default placeholder).
3. Immediately transition into the predefined `DemoTech Solutions` sample result. No awkward waiting.
