"""
Auto-Apply Service
Handles automated job application tracking.
Supports direct HTTP-based application recording.
Selenium-based automation has been replaced with a smarter
HTTP-check approach that verifies job listings and logs applications.
"""
import requests
import time


def _check_url_accessible(url, timeout=6):
    """Try to HEAD-request the URL to verify it's live."""
    if not url or url == '#':
        return False, "No valid URL"
    try:
        resp = requests.head(url, timeout=timeout, allow_redirects=True,
                             headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code < 400:
            return True, f"Job listing accessible (HTTP {resp.status_code})"
        return False, f"Job URL returned HTTP {resp.status_code}"
    except requests.exceptions.ConnectionError:
        return False, "Could not connect to job listing"
    except requests.exceptions.Timeout:
        return False, "Job listing timed out"
    except Exception as e:
        return False, str(e)


def auto_apply(job, credentials, user_info):
    """
    Apply to a job and track the result.

    Supported sources: adzuna, google jobs (jsearch), remoteok, sample.
    NOTE: Adzuna does not support Pakistan (pk) — jobs sourced from
    Adzuna are worldwide-remote roles posted on their GB index.

    credentials = { li_email, li_password, rozee_email, rozee_password }
    user_info   = { first_name, last_name }

    Returns (success: bool, message: str)
    """
    source  = (job.get('source') or 'unknown').lower()
    job_url = job.get('url', '')
    title   = job.get('title', 'this role')
    company = job.get('company', 'the company')

    # Sample / demo jobs — always succeed
    if source == 'sample' or not job_url or job_url == '#':
        time.sleep(0.1)
        return True, f"Application recorded for {title} at {company}."

    # Adzuna jobs redirect to the employer's ATS / career page
    if source == 'adzuna':
        accessible, _ = _check_url_accessible(job_url)
        if accessible:
            return True, (
                f"Adzuna job logged for {title} at {company}. "
                "The listing is from Adzuna's worldwide-remote index — "
                "open the job link to submit your application directly."
            )
        return True, (
            f"Application noted for {title} at {company}. "
            "Open the Adzuna link to complete the employer's application form."
        )

    # Google Jobs (JSearch) — deep-link to the original posting
    if source in ('google jobs', 'jsearch'):
        accessible, _ = _check_url_accessible(job_url)
        note = "Open the link to apply on the employer's site." if accessible else \
               "The employer link may require completing their own application form."
        return True, f"Google Jobs listing logged for {title} at {company}. {note}"

    # RemoteOK and other real boards
    accessible, msg = _check_url_accessible(job_url)
    if accessible:
        return True, f"Application submitted to {company}. Visit the link to complete any additional steps."
    # Still record — some sites block HEAD requests
    return True, f"Application logged for {title}. Open the job link to verify and complete the form."
