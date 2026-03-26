# Troubleshooting — Collective Access SaaS

## Cannot Log In to My Instance

**Symptoms:** Login page shows "Invalid credentials" or you've forgotten your password.

**Solutions:**
1. Make sure you're using the username `administrator` (not an email address) for the default admin account.
2. The administrator password was shown at the end of the installation wizard. If you missed it, you need to reset it via the database.
3. If you have multiple users, check that you're using the correct username for your account.
4. Clear browser cache and cookies, then try again.
5. Make sure you're navigating to the correct instance URL — find it in the portal → **Overview** page.

---

## Instance URL Shows an Error or Is Unreachable

**Symptoms:** Visiting your instance URL shows a 502, 503, or "site can't be reached" error.

**Solutions:**
1. Check the portal → **Overview** page to confirm the instance status. If it shows **Provisioning**, wait 2–3 more minutes.
2. If the status shows **Running** but the URL is unreachable, open a support ticket — the instance may need a restart.
3. Check that you are using HTTPS (not HTTP) in the URL.
4. If you see a certificate warning, click **Advanced → Proceed** — this is expected for new instances until the TLS certificate fully propagates (takes up to 60 seconds).

---

## Installation Wizard Appears Instead of Login

**Symptoms:** Visiting your instance URL shows the Collective Access installation wizard.

**Solutions:**
The installation wizard runs once on first visit. If it appears again:
1. The database may have been reset. Complete the wizard to reinitialise.
2. Navigate to `/install/index.php` to start the wizard manually.
3. Use any valid email during installation — the administrator username will be `administrator`.

---

## Images and Media Not Displaying

**Symptoms:** Objects have images attached but they do not display, or uploads fail.

**Solutions:**
1. Check your plan's storage limit in the portal → **Overview** page. If storage is full, uploads will fail.
2. Supported image formats: JPEG, PNG, TIFF, GIF. Very large files (>100 MB) may time out.
3. Make sure the media is attached to the object record under the **Media** tab in Collective Access.
4. If images were previously displaying and suddenly stopped, open a support ticket.

---

## Import Failed

**Symptoms:** CSV or XML import returns errors or imported records have missing fields.

**Solutions:**
1. Verify your CSV uses UTF-8 encoding (not Windows-1252 or Latin-1).
2. Column headers must match the Collective Access field codes exactly (case-sensitive).
3. Check **Manage → Import → Import Errors** for a detailed error log after the import.
4. Test with a small sample (10 rows) before importing the full dataset.
5. Ensure relationships in the import file reference existing records (e.g., entity names must already exist before linking to objects).

---

## Slow Performance

**Symptoms:** Pages load slowly, search takes a long time.

**Solutions:**
1. Large media files attached to many records will slow down list views. Use thumbnail-only display in lists.
2. Run **Manage → Maintenance → Rebuild search index** if search results are slow or missing records.
3. If performance consistently degrades over time, you may be approaching your plan's resource limits — consider upgrading.

---

## How to Reset the Administrator Password

If you have SSH/kubectl access (SaaS administrator only):
```bash
kubectl exec -n tenant-XXXXXXXX <ca-pod-name> -- php /var/www/html/support/utils/resetPassword.php -u administrator -p newpassword
```

If you do not have direct access, open a support ticket and we will reset it for you.

---

## Blank Page or PHP Error After Upgrade

**Symptoms:** After an upgrade, pages show a white screen or PHP fatal error.

**Solutions:**
1. Clear the Collective Access cache: navigate to `https://your-instance-url/index.php/administrate/maintenance/clearCache` while logged in as administrator.
2. Run **Manage → Maintenance → Rebuild search index**.
3. If the issue persists, open a support ticket with the error message.

---

## Certificate Warning in Browser

**Symptoms:** Browser shows "Your connection is not private" or "Certificate error".

**Solutions:**
- **Local/staging environment:** Click **Advanced → Proceed to site**. Self-signed certificates are used locally.
- **Production:** TLS certificates are issued automatically via Let's Encrypt and should be valid. If you see this in production, wait 2 minutes for certificate propagation, then try again. If it persists, open a support ticket.
