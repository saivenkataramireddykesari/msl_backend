import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Dict, Any, Optional
from datetime import datetime
from dotenv import load_dotenv

# Ensure .env is loaded before SMTP settings are read
_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
if os.path.exists(_env_path):
    load_dotenv(dotenv_path=_env_path)
else:
    load_dotenv()

def get_smtp_config() -> Dict[str, Any]:
    """Read current SMTP configuration from environment variables."""
    host = os.getenv("SMTP_HOST", "")
    port_str = os.getenv("SMTP_PORT", "587")
    try:
        port = int(port_str)
    except (ValueError, TypeError):
        port = 587
    user = os.getenv("SMTP_USER", "")
    password = os.getenv("SMTP_PASSWORD", "")
    from_addr = os.getenv("SMTP_FROM", user or "noreply@pulsepharma.net")
    tls = os.getenv("SMTP_TLS", "true").lower() in ("true", "1", "yes")
    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "from": from_addr,
        "tls": tls
    }

# Read SMTP configuration from environment variables for backwards compatibility
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", os.getenv("SMTP_USER", "noreply@pulsepharma.net"))
SMTP_TLS = os.getenv("SMTP_TLS", "true").lower() in ("true", "1", "yes")

PORTAL_URL = os.getenv("PORTAL_URL", "https://so.pulsepharma.net")

def send_email(to_email: str, subject: str, html_content: str, text_content: Optional[str] = None) -> Dict[str, Any]:
    """
    Sends an email using standard SMTP.
    If SMTP credentials are not configured, logs the email content safely and returns a simulated success.
    Never throws an unhandled exception to prevent breaking caller transactions.
    """
    if not to_email or not to_email.strip():
        print(f"[EMAIL SERVICE] Skipped sending: empty email address")
        return {"success": False, "reason": "empty_email", "to": to_email}

    to_email = to_email.strip()
    cfg = get_smtp_config()
    host = cfg["host"] or SMTP_HOST
    port = cfg["port"] or SMTP_PORT
    user = cfg["user"] or SMTP_USER
    password = cfg["password"] or SMTP_PASSWORD
    from_addr = cfg["from"] or SMTP_FROM
    tls = cfg["tls"] if cfg["host"] else SMTP_TLS

    # If SMTP is not configured in .env, simulate and log
    if not host or not user or not password:
        print(f"============================================================")
        print(f"[EMAIL SERVICE - SIMULATED DELIVERY]")
        print(f"To: {to_email}")
        print(f"Subject: {subject}")
        print(f"Status: Logged successfully (Set SMTP_HOST, SMTP_USER, SMTP_PASSWORD in .env for live transmission)")
        print(f"============================================================")
        return {"success": True, "simulated": True, "to": to_email, "subject": subject}

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = to_email

        if text_content:
            msg.attach(MIMEText(text_content, "plain"))
        
        msg.attach(MIMEText(html_content, "html"))

        with smtplib.SMTP(host, port, timeout=12) as server:
            if tls:
                server.starttls()
            server.login(user, password)
            server.send_message(msg)

        print(f"[EMAIL SERVICE] Email successfully sent to: {to_email} (Subject: {subject})")
        return {"success": True, "simulated": False, "to": to_email}

    except Exception as e:
        print(f"[EMAIL SERVICE ERROR] Failed to send email to {to_email}: {str(e)}")
        return {"success": False, "error": str(e), "to": to_email}

def build_tour_plan_email_html(
    recipient_name: str,
    recipient_role: str,
    is_so: bool,
    plan_data: Dict[str, Any],
    created_by_name: str
) -> str:
    """
    Constructs a modern, premium branded HTML email for Tour Plan notifications.
    """
    from_date_str = str(plan_data.get("from_date", ""))
    to_date_str = str(plan_data.get("to_date", ""))
    divisions = plan_data.get("divisions", [])
    territories = plan_data.get("territories", [])
    assigned_so = plan_data.get("assigned_so", "Scientific Officer")
    remarks = plan_data.get("remarks") or "None specified"
    month_val = plan_data.get("month") or datetime.now().strftime("%B")
    year_val = plan_data.get("year") or datetime.now().strftime("%Y")

    divisions_chips = "".join(
        f'<span style="display:inline-block;background:#eef2ff;color:#4f46e5;padding:4px 10px;border-radius:14px;font-size:12px;font-weight:600;margin:2px 4px 2px 0;border:1px solid #c7d2fe;">{d}</span>'
        for d in divisions
    )

    territories_chips = "".join(
        f'<span style="display:inline-block;background:#f1f5f9;color:#334155;padding:4px 10px;border-radius:14px;font-size:12px;font-weight:500;margin:2px 4px 2px 0;border:1px solid #cbd5e1;">{t}</span>'
        for t in territories
    )

    role_specific_headline = (
        "You have been assigned to an official field tour plan."
        if is_so
        else f"A new field tour plan has been scheduled for your division with Scientific Officer <strong>{assigned_so}</strong>."
    )

    action_label = "View Your Tour Plan" if is_so else "View Division Tour Plan"

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Tour Plan Notification</title>
</head>
<body style="margin:0;padding:0;background-color:#f8fafc;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#1e293b;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f8fafc;padding:30px 15px;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background-color:#ffffff;border-radius:16px;box-shadow:0 8px 30px rgba(0,0,0,0.06);overflow:hidden;border:1px solid #e2e8f0;">
          <!-- Header -->
          <tr>
            <td style="background:linear-gradient(135deg,#3730a3 0%,#4f46e5 50%,#7c3aed 100%);padding:32px 30px;text-align:left;color:#ffffff;">
              <div style="font-size:12px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:#c7d2fe;margin-bottom:6px;">Pulse Pharmaceuticals</div>
              <h1 style="margin:0;font-size:22px;font-weight:800;letter-spacing:-0.4px;color:#ffffff;">Scientific Office Tour Plan</h1>
              <div style="margin-top:6px;font-size:13.5px;color:#e0e7ff;">Schedule for {month_val} {year_val}</div>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding:32px 30px;">
              <p style="font-size:15px;margin:0 0 16px 0;color:#0f172a;line-height:1.5;">
                Dear <strong>{recipient_name}</strong> ({recipient_role}),
              </p>

              <p style="font-size:14px;color:#475569;margin:0 0 24px 0;line-height:1.6;">
                {role_specific_headline} This tour plan was formulated and approved by Asst General Manager <strong>{created_by_name}</strong>.
              </p>

              <!-- Details Card -->
              <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f8fafc;border-radius:12px;border:1.5px solid #e2e8f0;margin-bottom:24px;">
                <tr>
                  <td style="padding:16px 20px;border-bottom:1px solid #e2e8f0;width:38%;font-size:12.5px;font-weight:700;color:#64748b;text-transform:uppercase;">
                    Tour Period
                  </td>
                  <td style="padding:16px 20px;border-bottom:1px solid #e2e8f0;font-size:14px;font-weight:700;color:#0f172a;">
                    {from_date_str} &nbsp;→&nbsp; {to_date_str}
                  </td>
                </tr>
                <tr>
                  <td style="padding:16px 20px;border-bottom:1px solid #e2e8f0;font-size:12.5px;font-weight:700;color:#64748b;text-transform:uppercase;">
                    Assigned Scientific Officer
                  </td>
                  <td style="padding:16px 20px;border-bottom:1px solid #e2e8f0;font-size:14px;font-weight:700;color:#4f46e5;">
                    {assigned_so}
                  </td>
                </tr>
                <tr>
                  <td style="padding:16px 20px;border-bottom:1px solid #e2e8f0;font-size:12.5px;font-weight:700;color:#64748b;text-transform:uppercase;vertical-align:top;">
                    Target Divisions ({len(divisions)})
                  </td>
                  <td style="padding:16px 20px;border-bottom:1px solid #e2e8f0;font-size:13px;">
                    {divisions_chips or '—'}
                  </td>
                </tr>
                <tr>
                  <td style="padding:16px 20px;border-bottom:1px solid #e2e8f0;font-size:12.5px;font-weight:700;color:#64748b;text-transform:uppercase;vertical-align:top;">
                    Target Territories ({len(territories)})
                  </td>
                  <td style="padding:16px 20px;border-bottom:1px solid #e2e8f0;font-size:13px;">
                    {territories_chips or '—'}
                  </td>
                </tr>
                <tr>
                  <td style="padding:16px 20px;font-size:12.5px;font-weight:700;color:#64748b;text-transform:uppercase;vertical-align:top;">
                    Remarks / Objectives
                  </td>
                  <td style="padding:16px 20px;font-size:13.5px;color:#334155;line-height:1.5;">
                    {remarks}
                  </td>
                </tr>
              </table>

              <!-- CTA Button -->
              <div style="text-align:center;margin:30px 0 10px 0;">
                <a href="{PORTAL_URL}/tour-plan" style="display:inline-block;background:linear-gradient(135deg,#4f46e5 0%,#7c3aed 100%);color:#ffffff;text-decoration:none;font-weight:700;font-size:14px;padding:14px 28px;border-radius:10px;box-shadow:0 4px 14px rgba(79,70,229,0.35);">
                  {action_label} &rarr;
                </a>
              </div>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background-color:#f1f5f9;padding:20px 30px;text-align:center;border-top:1px solid #e2e8f0;font-size:12px;color:#94a3b8;">
              This is an automated operational notification from Pulse Pharmaceuticals Scientific Office Management System.<br>
              Created by {created_by_name} (Asst General Manager).
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""
